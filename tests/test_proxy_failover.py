import contextlib
import io
import os
import queue
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import nvidiaclaude_proxy as proxy  # noqa: E402


class DummyResponse:
    def __init__(self, lines=None, body=b"{}"):
        self.lines = lines or []
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def __iter__(self):
        return iter(self.lines)

    def read(self):
        return self.body


def make_config(
    keys=("token-a", "token-b"),
    rate_limit_rpm=38.0,
    rate_limit_scope="global",
    rate_limit_window_seconds=60.0,
):
    cooldown = 60.0
    return proxy.ProxyConfig(
        endpoint="https://example.test/v1/chat/completions",
        api_keys=list(keys),
        model="test-model",
        timeout=1.0,
        stream_ping_seconds=0.1,
        token_cooldown_seconds=cooldown,
        rate_limit_rpm=rate_limit_rpm,
        rate_limit_scope=rate_limit_scope,
        rate_limit_window_seconds=rate_limit_window_seconds,
        token_manager=proxy.TokenManager(
            len(keys),
            cooldown,
            rate_limit_rpm,
            rate_limit_scope,
            rate_limit_window_seconds,
        ),
    )


class FailoverTests(unittest.TestCase):
    def test_normalize_endpoint_accepts_full_chat_completions_url(self):
        endpoint = "https://api.tokenrouter.com/v1/chat/completions"

        self.assertEqual(proxy.normalize_endpoint(endpoint), endpoint)

    def test_normalize_endpoint_appends_chat_completions_to_v1_base(self):
        self.assertEqual(
            proxy.normalize_endpoint("https://api.tokenrouter.com/v1"),
            "https://api.tokenrouter.com/v1/chat/completions",
        )

    def test_normalize_endpoint_appends_v1_chat_completions_to_provider_root(self):
        self.assertEqual(
            proxy.normalize_endpoint("https://api.tokenrouter.com"),
            "https://api.tokenrouter.com/v1/chat/completions",
        )

    def test_load_api_keys_prefers_generic_env_over_legacy_env(self):
        env = {
            "NVIDIACLAUDE_API_KEYS": " generic-a, generic-b ",
            "NVIDIA_API_KEYS": "legacy-a,legacy-b",
        }

        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(proxy.load_api_keys_from_env(), ["generic-a", "generic-b"])

    def test_load_endpoint_prefers_generic_env_over_legacy_env(self):
        env = {
            "NVIDIACLAUDE_API_ENDPOINT": "https://api.tokenrouter.com/v1",
            "NVIDIA_NIM_ENDPOINT": "https://legacy.example/v1",
        }

        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(
                proxy.load_endpoint_from_env(),
                "https://api.tokenrouter.com/v1",
            )

    def test_load_model_prefers_generic_env_over_legacy_env(self):
        env = {
            "NVIDIACLAUDE_MODEL": "provider/model",
            "NVIDIA_NIM_MODEL": "legacy/model",
        }

        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(proxy.load_model_from_env(), "provider/model")

    def test_split_api_keys_trims_and_deduplicates(self):
        self.assertEqual(proxy.split_api_keys(" a, b ,,a , c "), ["a", "b", "c"])

    def test_provider_request_with_failover_retries_next_token_for_auth_failure(self):
        config = make_config()
        calls = []

        def fake_provider_request(_config, _payload, token_index):
            calls.append(token_index)
            if token_index == 0:
                raise proxy.ProviderError(401, "invalid api key")
            return DummyResponse()

        with patch.object(proxy, "provider_request", side_effect=fake_provider_request):
            response, token_index = proxy.provider_request_with_failover(config, {"stream": False})

        self.assertIsInstance(response, DummyResponse)
        self.assertEqual(token_index, 1)
        self.assertEqual(calls, [0, 1])

    def test_provider_request_with_failover_does_not_retry_non_token_error(self):
        config = make_config()
        calls = []

        def fake_provider_request(_config, _payload, token_index):
            calls.append(token_index)
            raise proxy.ProviderError(400, "bad request")

        with patch.object(proxy, "provider_request", side_effect=fake_provider_request):
            with self.assertRaises(proxy.ProviderError) as raised:
                proxy.provider_request_with_failover(config, {"stream": False})

        self.assertEqual(raised.exception.status, 400)
        self.assertEqual(calls, [0])

    def test_provider_request_with_failover_reports_all_token_failures(self):
        config = make_config()
        calls = []

        def fake_provider_request(_config, _payload, token_index):
            calls.append(token_index)
            raise proxy.ProviderError(401, "invalid api key")

        with patch.object(proxy, "provider_request", side_effect=fake_provider_request):
            with self.assertRaises(proxy.ProviderError) as raised:
                proxy.provider_request_with_failover(config, {"stream": False})

        self.assertEqual(raised.exception.status, 401)
        self.assertIn("All configured provider API tokens failed", raised.exception.message)
        self.assertEqual(calls, [0, 1])

    def test_provider_request_with_failover_switches_token_after_429(self):
        config = make_config()
        calls = []

        def fake_provider_request(_config, _payload, token_index):
            calls.append(token_index)
            if token_index == 0:
                raise proxy.ProviderError(429, "rate limit", {"Retry-After": "2"})
            return DummyResponse()

        stderr = io.StringIO()
        with (
            contextlib.redirect_stderr(stderr),
            patch.object(proxy, "provider_request", side_effect=fake_provider_request),
        ):
            response, token_index = proxy.provider_request_with_failover(config, {"stream": False})

        self.assertIsInstance(response, DummyResponse)
        self.assertEqual(token_index, 1)
        self.assertEqual(calls, [0, 1])
        self.assertEqual(stderr.getvalue(), "")

    def test_provider_request_with_failover_reports_all_tokens_rate_limited(self):
        config = make_config()
        calls = []

        def fake_provider_request(_config, _payload, token_index):
            calls.append(token_index)
            raise proxy.ProviderError(429, "rate limit")

        with patch.object(proxy, "provider_request", side_effect=fake_provider_request):
            with self.assertRaises(proxy.ProviderError) as raised:
                proxy.provider_request_with_failover(config, {"stream": False})

        self.assertEqual(raised.exception.status, 429)
        self.assertIn("currently rate limited", raised.exception.message)
        self.assertEqual(calls, [0, 1])

    def test_provider_request_with_failover_fails_fast_when_all_tokens_cooling(self):
        config = make_config()
        config.token_manager.mark_token_limited(0)
        config.token_manager.mark_token_limited(1)

        with patch.object(proxy, "provider_request") as provider_request:
            with self.assertRaises(proxy.ProviderError) as raised:
                proxy.provider_request_with_failover(config, {"stream": False})

        provider_request.assert_not_called()
        self.assertEqual(raised.exception.status, 429)
        self.assertIn("currently cooling down", raised.exception.message)

    def test_stream_provider_uses_failover_before_emitting_error(self):
        config = make_config()
        calls = []

        def fake_provider_request(_config, _payload, token_index):
            calls.append(token_index)
            if token_index == 0:
                raise proxy.ProviderError(401, "invalid api key")
            return DummyResponse(lines=[b"data: [DONE]\n"])

        events: queue.Queue[tuple[str, object]] = queue.Queue()
        with patch.object(proxy, "provider_request", side_effect=fake_provider_request):
            proxy.stream_provider(config, {"stream": True}, events)

        collected = []
        while not events.empty():
            collected.append(events.get_nowait())

        self.assertEqual(calls, [0, 1])
        self.assertEqual(collected[0][0], "line")
        self.assertEqual(collected[-1][0], "done")
        self.assertNotIn("provider_error", [event_type for event_type, _ in collected])

    def test_token_manager_skips_cooling_tokens_without_waiting(self):
        manager = proxy.TokenManager(
            token_count=2,
            cooldown_seconds=60.0,
        )

        manager.mark_token_limited(0)

        self.assertEqual(manager.acquire_token(), 1)

    def test_token_manager_waits_silently_for_shared_rate_limit(self):
        manager = proxy.TokenManager(
            token_count=2,
            cooldown_seconds=60.0,
            rate_limit_rpm=1.0,
            rate_limit_scope="global",
            rate_limit_window_seconds=0.01,
        )

        self.assertEqual(manager.acquire_token(), 0)
        self.assertGreater(manager.rate_wait_seconds(1, time.time()), 0)

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(manager.acquire_token(), 0)

        self.assertEqual(stderr.getvalue(), "")

    def test_token_manager_per_token_rate_limit_can_use_other_token(self):
        manager = proxy.TokenManager(
            token_count=2,
            cooldown_seconds=60.0,
            rate_limit_rpm=1.0,
            rate_limit_scope="per-token",
            rate_limit_window_seconds=60.0,
        )

        self.assertEqual(manager.acquire_token(), 0)
        self.assertEqual(manager.acquire_token(), 1)

    def test_token_manager_rate_limit_can_be_disabled(self):
        manager = proxy.TokenManager(
            token_count=1,
            cooldown_seconds=60.0,
            rate_limit_rpm=0.0,
            rate_limit_scope="global",
            rate_limit_window_seconds=60.0,
        )

        self.assertEqual(manager.acquire_token(), 0)
        self.assertEqual(manager.rate_wait_seconds(0, time.time()), 0.0)
        self.assertEqual(manager.acquire_token(), 0)

    def test_token_manager_returns_none_when_every_available_token_is_cooling(self):
        manager = proxy.TokenManager(
            token_count=2,
            cooldown_seconds=60.0,
        )

        manager.mark_token_limited(0)
        manager.mark_token_limited(1)

        self.assertIsNone(manager.acquire_token())


if __name__ == "__main__":
    unittest.main()
