import queue
import sys
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


def make_config(keys=("token-a", "token-b")):
    cooldown = 60.0
    return proxy.ProxyConfig(
        endpoint="https://example.test/v1/chat/completions",
        api_keys=list(keys),
        model="test-model",
        timeout=1.0,
        stream_ping_seconds=0.1,
        token_cooldown_seconds=cooldown,
        token_manager=proxy.TokenManager(
            len(keys),
            cooldown,
        ),
    )


class FailoverTests(unittest.TestCase):
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
        self.assertIn("All configured NVIDIA API tokens failed", raised.exception.message)
        self.assertEqual(calls, [0, 1])

    def test_provider_request_with_failover_switches_token_after_429(self):
        config = make_config()
        calls = []

        def fake_provider_request(_config, _payload, token_index):
            calls.append(token_index)
            if token_index == 0:
                raise proxy.ProviderError(429, "rate limit", {"Retry-After": "2"})
            return DummyResponse()

        with patch.object(proxy, "provider_request", side_effect=fake_provider_request):
            response, token_index = proxy.provider_request_with_failover(config, {"stream": False})

        self.assertIsInstance(response, DummyResponse)
        self.assertEqual(token_index, 1)
        self.assertEqual(calls, [0, 1])

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
