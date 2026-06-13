#!/usr/bin/env python3
"""Local Anthropic-compatible adapter for NVIDIA NIM chat completions."""

from __future__ import annotations

import argparse
import json
import os
import queue
import sys
import threading
import uuid
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


DEFAULT_ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_MODEL = "minimaxai/minimax-m3"


@dataclass(frozen=True)
class ProxyConfig:
    endpoint: str
    api_key: str
    model: str
    timeout: float
    stream_ping_seconds: float


class ProviderError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def make_message_id() -> str:
    return "msg_" + uuid.uuid4().hex


def make_tool_id() -> str:
    return "toolu_" + uuid.uuid4().hex


def normalize_endpoint(endpoint: str) -> str:
    endpoint = endpoint.strip().rstrip("/")
    if endpoint.endswith("/chat/completions"):
        return endpoint
    if endpoint.endswith("/v1"):
        return endpoint + "/chat/completions"
    return endpoint.rstrip("/") + "/v1/chat/completions"


def parse_json_object(value: str) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {"_raw": value}
    if isinstance(parsed, dict):
        return parsed
    return {"value": parsed}


def content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                block_type = block.get("type")
                if block_type == "text":
                    parts.append(str(block.get("text", "")))
                elif block_type == "tool_result":
                    parts.append(content_to_text(block.get("content")))
                elif block_type == "image":
                    parts.append("[image omitted]")
                elif "text" in block:
                    parts.append(str(block.get("text", "")))
        return "\n".join(part for part in parts if part)
    if isinstance(content, dict):
        if content.get("type") == "text":
            return str(content.get("text", ""))
        return json_dumps(content)
    return str(content)


def system_to_text(system: Any) -> str:
    if not system:
        return ""
    if isinstance(system, str):
        return system
    if isinstance(system, list):
        return content_to_text(system)
    return str(system)


def append_user_blocks(messages: list[dict[str, Any]], content: Any) -> None:
    if isinstance(content, str):
        messages.append({"role": "user", "content": content})
        return

    blocks = content if isinstance(content, list) else [content]
    text_parts: list[str] = []

    def flush_text() -> None:
        nonlocal text_parts
        if text_parts:
            messages.append({"role": "user", "content": "\n".join(text_parts)})
            text_parts = []

    for block in blocks:
        if isinstance(block, str):
            text_parts.append(block)
            continue
        if not isinstance(block, dict):
            text_parts.append(str(block))
            continue

        block_type = block.get("type")
        if block_type == "text":
            text_parts.append(str(block.get("text", "")))
        elif block_type == "tool_result":
            flush_text()
            messages.append({
                "role": "tool",
                "tool_call_id": block.get("tool_use_id", ""),
                "content": content_to_text(block.get("content")),
            })
        elif block_type == "image":
            text_parts.append("[image omitted]")
        else:
            text = content_to_text(block)
            if text:
                text_parts.append(text)

    flush_text()
    if not messages or messages[-1]["role"] not in ("user", "tool"):
        messages.append({"role": "user", "content": ""})


def append_assistant_blocks(messages: list[dict[str, Any]], content: Any) -> None:
    if isinstance(content, str):
        messages.append({"role": "assistant", "content": content})
        return

    blocks = content if isinstance(content, list) else [content]
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []

    for block in blocks:
        if isinstance(block, str):
            text_parts.append(block)
            continue
        if not isinstance(block, dict):
            text_parts.append(str(block))
            continue

        block_type = block.get("type")
        if block_type == "text":
            text_parts.append(str(block.get("text", "")))
        elif block_type == "tool_use":
            tool_input = block.get("input")
            tool_calls.append({
                "id": block.get("id") or make_tool_id(),
                "type": "function",
                "function": {
                    "name": block.get("name", ""),
                    "arguments": json_dumps(tool_input if tool_input is not None else {}),
                },
            })

    message: dict[str, Any] = {
        "role": "assistant",
        "content": "\n".join(text_parts) if text_parts else None,
    }
    if tool_calls:
        message["tool_calls"] = tool_calls
    messages.append(message)


def convert_messages(body: dict[str, Any]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    system_text = system_to_text(body.get("system"))
    if system_text:
        messages.append({"role": "system", "content": system_text})

    for message in body.get("messages") or []:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = message.get("content", "")
        if role == "assistant":
            append_assistant_blocks(messages, content)
        else:
            append_user_blocks(messages, content)
    return messages or [{"role": "user", "content": ""}]


def convert_tools(tools: Any) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    if not isinstance(tools, list):
        return converted
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        name = tool.get("name")
        if not name:
            continue
        converted.append({
            "type": "function",
            "function": {
                "name": name,
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema") or {"type": "object", "properties": {}},
            },
        })
    return converted


def convert_tool_choice(tool_choice: Any) -> Any:
    if not isinstance(tool_choice, dict):
        return None
    choice_type = tool_choice.get("type")
    if choice_type == "auto":
        return "auto"
    if choice_type == "any":
        return "required"
    if choice_type == "none":
        return "none"
    if choice_type == "tool" and tool_choice.get("name"):
        return {
            "type": "function",
            "function": {"name": tool_choice["name"]},
        }
    return None


def build_openai_payload(body: dict[str, Any], config: ProxyConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": convert_messages(body),
        "stream": bool(body.get("stream")),
    }

    for source, target in (
        ("max_tokens", "max_tokens"),
        ("temperature", "temperature"),
        ("top_p", "top_p"),
    ):
        if source in body and body[source] is not None:
            payload[target] = body[source]

    if body.get("stop_sequences"):
        payload["stop"] = body["stop_sequences"]

    tools = convert_tools(body.get("tools"))
    if tools:
        payload["tools"] = tools
        tool_choice = convert_tool_choice(body.get("tool_choice"))
        if tool_choice:
            payload["tool_choice"] = tool_choice

    return payload


def anthropic_usage(openai_usage: dict[str, Any] | None) -> dict[str, int]:
    openai_usage = openai_usage or {}
    return {
        "input_tokens": int(openai_usage.get("prompt_tokens") or 0),
        "output_tokens": int(openai_usage.get("completion_tokens") or 0),
    }


def stop_reason(finish_reason: str | None, has_tool_calls: bool = False) -> str:
    if has_tool_calls or finish_reason == "tool_calls":
        return "tool_use"
    if finish_reason == "length":
        return "max_tokens"
    if finish_reason == "stop":
        return "end_turn"
    return "end_turn"


def text_from_openai_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text = block.get("text")
                    if isinstance(text, dict):
                        parts.append(str(text.get("value", "")))
                    else:
                        parts.append(str(text or ""))
                elif "text" in block:
                    parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(part for part in parts if part)
    return ""


def convert_openai_response(data: dict[str, Any], model: str) -> dict[str, Any]:
    choices = data.get("choices") or []
    choice = choices[0] if choices else {}
    message = choice.get("message") or {}
    content: list[dict[str, Any]] = []

    text = text_from_openai_content(message.get("content"))
    if text:
        content.append({"type": "text", "text": text})

    tool_calls = message.get("tool_calls") or []
    for tool_call in tool_calls:
        function = tool_call.get("function") or {}
        content.append({
            "type": "tool_use",
            "id": tool_call.get("id") or make_tool_id(),
            "name": function.get("name", ""),
            "input": parse_json_object(function.get("arguments", "")),
        })

    return {
        "id": make_message_id(),
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": stop_reason(choice.get("finish_reason"), bool(tool_calls)),
        "stop_sequence": None,
        "usage": anthropic_usage(data.get("usage")),
    }


def provider_request(config: ProxyConfig, payload: dict[str, Any]) -> Any:
    body = json_dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        config.endpoint,
        data=body,
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if payload.get("stream") else "application/json",
            "User-Agent": "nvidiaclaude/1.0",
        },
        method="POST",
    )
    try:
        return urllib.request.urlopen(request, timeout=config.timeout)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise ProviderError(error.code, detail or str(error)) from error
    except urllib.error.URLError as error:
        raise ProviderError(502, str(error.reason)) from error


def stream_provider(
    config: ProxyConfig,
    payload: dict[str, Any],
    events: queue.Queue[tuple[str, Any]],
) -> None:
    try:
        with provider_request(config, payload) as response:
            for raw_line in response:
                events.put(("line", raw_line))
    except ProviderError as error:
        events.put(("provider_error", error))
    except Exception as error:
        events.put(("exception", error))
    finally:
        events.put(("done", None))


def estimate_tokens(body: dict[str, Any]) -> int:
    pieces: list[str] = [system_to_text(body.get("system"))]
    for message in body.get("messages") or []:
        if isinstance(message, dict):
            pieces.append(str(message.get("role", "")))
            pieces.append(content_to_text(message.get("content", "")))
    for tool in body.get("tools") or []:
        if isinstance(tool, dict):
            pieces.append(tool.get("name", ""))
            pieces.append(tool.get("description", ""))
            pieces.append(json_dumps(tool.get("input_schema") or {}))
    chars = sum(len(piece) for piece in pieces)
    return max(1, (chars + 3) // 4)


class NvidiaClaudeHandler(BaseHTTPRequestHandler):
    config: ProxyConfig
    server_version = "nvidiaclaude/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(fmt % args, file=sys.stderr)

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length > 0 else b"{}"
        if not raw:
            return {}
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON body: {error}") from error
        if not isinstance(parsed, dict):
            raise ValueError("JSON body must be an object.")
        return parsed

    def send_json(self, status: int, data: dict[str, Any]) -> None:
        body = (json_dumps(data) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status: int, message: str, error_type: str = "api_error") -> None:
        self.send_json(status, {
            "type": "error",
            "error": {
                "type": error_type,
                "message": message,
            },
        })

    def send_sse(self, event: str, data: dict[str, Any]) -> None:
        self.wfile.write(f"event: {event}\n".encode("utf-8"))
        self.wfile.write(f"data: {json_dumps(data)}\n\n".encode("utf-8"))
        self.wfile.flush()

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/healthz"):
            self.send_json(200, {"ok": True, "model": self.config.model})
            return
        if path in ("/v1/models", "/models"):
            self.send_json(200, {
                "data": [{
                    "type": "model",
                    "id": self.config.model,
                    "display_name": self.config.model,
                    "created_at": "2024-01-01T00:00:00Z",
                }],
                "has_more": False,
                "first_id": self.config.model,
                "last_id": self.config.model,
            })
            return
        self.send_error_json(404, f"Unknown endpoint: {path}", "not_found_error")

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        try:
            body = self.read_json_body()
        except ValueError as error:
            self.send_error_json(400, str(error), "invalid_request_error")
            return

        if path in ("/v1/messages/count_tokens", "/messages/count_tokens"):
            self.send_json(200, {"input_tokens": estimate_tokens(body)})
            return
        if path in ("/v1/messages", "/messages"):
            self.handle_messages(body)
            return
        self.send_error_json(404, f"Unknown endpoint: {path}", "not_found_error")

    def handle_messages(self, body: dict[str, Any]) -> None:
        payload = build_openai_payload(body, self.config)
        if payload.get("stream"):
            self.handle_streaming_message(payload)
            return

        try:
            with provider_request(self.config, payload) as response:
                data = json.loads(response.read().decode("utf-8"))
        except ProviderError as error:
            self.send_error_json(error.status, f"NVIDIA NIM error: {error.message}")
            return
        except Exception as error:
            self.send_error_json(502, f"NVIDIA NIM request failed: {error}")
            return

        self.send_json(200, convert_openai_response(data, self.config.model))

    def handle_streaming_message(self, payload: dict[str, Any]) -> None:
        message_id = make_message_id()
        usage = {"input_tokens": 0, "output_tokens": 0}
        text_started = False
        text_index: int | None = None
        next_index = 0
        finish_reason: str | None = None
        tool_states: dict[int, dict[str, Any]] = {}
        events: queue.Queue[tuple[str, Any]] = queue.Queue()
        provider_thread = threading.Thread(
            target=stream_provider,
            args=(self.config, payload, events),
            daemon=True,
        )
        provider_thread.start()

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

        self.send_sse("message_start", {
            "type": "message_start",
            "message": {
                "id": message_id,
                "type": "message",
                "role": "assistant",
                "model": self.config.model,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": usage,
            },
        })

        try:
            while True:
                try:
                    event_type, event_data = events.get(
                        timeout=self.config.stream_ping_seconds
                        if self.config.stream_ping_seconds > 0
                        else None
                    )
                except queue.Empty:
                    self.send_sse("ping", {"type": "ping"})
                    continue

                if event_type == "done":
                    break

                if event_type == "provider_error":
                    error = event_data
                    self.send_sse("error", {
                        "type": "error",
                        "error": {
                            "type": "api_error",
                            "message": f"NVIDIA NIM error: {error.message}",
                        },
                    })
                    return

                if event_type == "exception":
                    self.send_sse("error", {
                        "type": "error",
                        "error": {
                            "type": "api_error",
                            "message": f"NVIDIA NIM stream failed: {event_data}",
                        },
                    })
                    return

                if event_type != "line":
                    continue

                line = event_data.decode("utf-8", errors="replace").strip()
                if not line or line.startswith(":"):
                    continue
                if not line.startswith("data:"):
                    continue
                chunk_text = line[5:].strip()
                if chunk_text == "[DONE]":
                    break
                try:
                    chunk = json.loads(chunk_text)
                except json.JSONDecodeError:
                    continue

                if isinstance(chunk.get("usage"), dict):
                    usage = anthropic_usage(chunk.get("usage"))

                choices = chunk.get("choices") or []
                if not choices:
                    continue
                choice = choices[0]
                finish_reason = choice.get("finish_reason") or finish_reason
                delta = choice.get("delta") or {}

                content_delta = delta.get("content")
                if content_delta:
                    if not text_started:
                        text_index = next_index
                        next_index += 1
                        text_started = True
                        self.send_sse("content_block_start", {
                            "type": "content_block_start",
                            "index": text_index,
                            "content_block": {"type": "text", "text": ""},
                        })
                    self.send_sse("content_block_delta", {
                        "type": "content_block_delta",
                        "index": text_index,
                        "delta": {"type": "text_delta", "text": content_delta},
                    })

                for tool_call in delta.get("tool_calls") or []:
                    openai_index = int(tool_call.get("index", len(tool_states)))
                    state = tool_states.setdefault(openai_index, {
                        "block_index": None,
                        "id": None,
                        "name": None,
                    })
                    if tool_call.get("id"):
                        state["id"] = tool_call["id"]
                    function = tool_call.get("function") or {}
                    if function.get("name"):
                        state["name"] = function["name"]

                    if state["block_index"] is None and (state.get("id") or state.get("name")):
                        state["block_index"] = next_index
                        next_index += 1
                        self.send_sse("content_block_start", {
                            "type": "content_block_start",
                            "index": state["block_index"],
                            "content_block": {
                                "type": "tool_use",
                                "id": state.get("id") or make_tool_id(),
                                "name": state.get("name") or "tool",
                                "input": {},
                            },
                        })

                    arguments = function.get("arguments") or ""
                    if arguments and state["block_index"] is not None:
                        self.send_sse("content_block_delta", {
                            "type": "content_block_delta",
                            "index": state["block_index"],
                            "delta": {
                                "type": "input_json_delta",
                                "partial_json": arguments,
                            },
                        })

            if text_started and text_index is not None:
                self.send_sse("content_block_stop", {
                    "type": "content_block_stop",
                    "index": text_index,
                })
            for state in sorted(tool_states.values(), key=lambda item: item["block_index"] or 0):
                if state["block_index"] is not None:
                    self.send_sse("content_block_stop", {
                        "type": "content_block_stop",
                        "index": state["block_index"],
                    })

            self.send_sse("message_delta", {
                "type": "message_delta",
                "delta": {
                    "stop_reason": stop_reason(finish_reason, bool(tool_states)),
                    "stop_sequence": None,
                },
                "usage": {"output_tokens": usage.get("output_tokens", 0)},
            })
            self.send_sse("message_stop", {"type": "message_stop"})
        except BrokenPipeError:
            return
        except Exception as error:
            try:
                self.send_sse("error", {
                    "type": "error",
                    "error": {
                        "type": "api_error",
                        "message": f"NVIDIA NIM stream failed: {error}",
                    },
                })
            except BrokenPipeError:
                return


def make_handler(config: ProxyConfig) -> type[NvidiaClaudeHandler]:
    class Handler(NvidiaClaudeHandler):
        pass

    Handler.config = config
    return Handler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Anthropic-compatible NVIDIA NIM proxy.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--ready-file")
    parser.add_argument("--timeout", type=float, default=300.0)
    return parser.parse_args()


def env_float(name: str, default: float) -> float:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    try:
        return max(0.0, float(value))
    except ValueError:
        return default


def main() -> int:
    args = parse_args()
    api_key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not api_key:
        print("NVIDIA_API_KEY is required.", file=sys.stderr)
        return 1

    config = ProxyConfig(
        endpoint=normalize_endpoint(os.environ.get("NVIDIA_NIM_ENDPOINT", DEFAULT_ENDPOINT)),
        api_key=api_key,
        model=os.environ.get("NVIDIA_NIM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        timeout=args.timeout,
        stream_ping_seconds=env_float("NVIDIACLAUDE_STREAM_PING_SECONDS", 2.0),
    )

    server = ThreadingHTTPServer((args.host, args.port), make_handler(config))
    server.daemon_threads = True
    port = server.server_address[1]

    if args.ready_file:
        with open(args.ready_file, "w", encoding="ascii") as ready:
            ready.write(str(port))

    print(f"nvidiaclaude proxy listening on {args.host}:{port}", file=sys.stderr)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
