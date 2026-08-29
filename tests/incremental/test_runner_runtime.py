"""Regressoes do orçamento global do runner incremental."""

from unittest.mock import patch

from etl.incremental.runner import _remaining_runtime_s


def test_remaining_runtime_uses_global_deadline():
    with patch("etl.incremental.runner.time.monotonic", return_value=125.9):
        assert _remaining_runtime_s(200.0) == 74


def test_remaining_runtime_never_returns_negative():
    with patch("etl.incremental.runner.time.monotonic", return_value=201.0):
        assert _remaining_runtime_s(200.0) == 0
