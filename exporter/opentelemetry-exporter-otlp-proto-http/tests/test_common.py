# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import time
import unittest
from email.utils import formatdate

from requests.models import Response

from opentelemetry.exporter.otlp.proto.http._common import (
    _get_retry_after,
    _is_retryable,
)


def _response(status_code=200, headers=None):
    resp = Response()
    resp.status_code = status_code
    if headers:
        resp.headers.update(headers)
    return resp


class TestIsRetryable(unittest.TestCase):
    def test_retryable_status_codes(self):
        for code in (408, 429, 500, 502, 503, 504, 599):
            self.assertTrue(_is_retryable(_response(code)), code)

    def test_non_retryable_status_codes(self):
        for code in (200, 301, 400, 401, 403, 404, 413):
            self.assertFalse(_is_retryable(_response(code)), code)


class TestGetRetryAfter(unittest.TestCase):
    def test_missing_header(self):
        self.assertIsNone(_get_retry_after(_response(429)))

    def test_delay_seconds(self):
        resp = _response(429, {"Retry-After": "7"})
        self.assertEqual(_get_retry_after(resp), 7.0)

    def test_delay_seconds_with_whitespace(self):
        resp = _response(429, {"Retry-After": "  3  "})
        self.assertEqual(_get_retry_after(resp), 3.0)

    def test_negative_delay_clamped_to_zero(self):
        resp = _response(429, {"Retry-After": "-5"})
        self.assertEqual(_get_retry_after(resp), 0.0)

    def test_non_finite_delay_rejected(self):
        for value in ("inf", "-inf", "nan"):
            resp = _response(429, {"Retry-After": value})
            self.assertIsNone(_get_retry_after(resp), value)

    def test_malformed_value_rejected(self):
        for value in ("", "later", "12 seconds"):
            resp = _response(429, {"Retry-After": value})
            self.assertIsNone(_get_retry_after(resp), value)

    def test_http_date_in_future(self):
        resp = _response(
            429,
            {"Retry-After": formatdate(time.time() + 100, usegmt=True)},
        )
        delay = _get_retry_after(resp)
        self.assertIsNotNone(delay)
        # formatdate has one-second resolution, so allow some slack.
        self.assertTrue(90 < delay <= 101, delay)

    def test_http_date_in_past_clamped_to_zero(self):
        resp = _response(
            429,
            {"Retry-After": formatdate(time.time() - 100, usegmt=True)},
        )
        self.assertEqual(_get_retry_after(resp), 0.0)
