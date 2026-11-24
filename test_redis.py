"""Integration tests for the Redis-backed rate limiter."""

from __future__ import annotations

import sys
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor

import redis

from Redis import RateLimiter, connect_from_environment


class RateLimiterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.client = connect_from_environment()
        except ConnectionError as exc:
            raise unittest.SkipTest(str(exc)) from exc
        cls.client_id = f"udb-test:{uuid.uuid4().hex}"

    def setUp(self) -> None:
        self.limiter = RateLimiter(
            self.client, max_requests=5, window_seconds=2, key_prefix=self.client_id
        )

    def test_first_five_allowed_and_sixth_rejected(self) -> None:
        results = [self.limiter.check_request("same-user") for _ in range(6)]
        self.assertEqual([result.allowed for result in results], [True] * 5 + [False])
        self.assertEqual(results[-1].request_count, 5)

    def test_different_users_have_independent_limits(self) -> None:
        for _ in range(5):
            self.assertTrue(self.limiter.check_request("user-a").allowed)
        self.assertFalse(self.limiter.check_request("user-a").allowed)
        self.assertTrue(self.limiter.check_request("user-b").allowed)

    def test_expired_records_are_removed(self) -> None:
        for _ in range(5):
            self.assertTrue(self.limiter.check_request("expiring-user").allowed)
        time.sleep(2.1)
        result = self.limiter.check_request("expiring-user")
        self.assertTrue(result.allowed)
        self.assertEqual(result.request_count, 1)

    def test_retry_time_is_reported(self) -> None:
        for _ in range(5):
            self.limiter.check_request("retry-user")
        result = self.limiter.check_request("retry-user")
        self.assertFalse(result.allowed)
        self.assertGreaterEqual(result.retry_after, 1)
        self.assertLessEqual(result.retry_after, 2)

    def test_concurrent_requests_cannot_bypass_limit(self) -> None:
        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(lambda _: self.limiter.check_request("busy-user"), range(20)))
        self.assertEqual(sum(result.allowed for result in results), 5)
        self.assertEqual(max(result.request_count for result in results), 5)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "client"):
            cls.client.delete(*cls.client.scan_iter(match=f"{cls.client_id}:*"))


if __name__ == "__main__":
    result = unittest.main(exit=False)
    sys.exit(not result.result.wasSuccessful())
