"""
tests/test_retry.py
Tests for agent_platform/retry.py

Run with: pytest tests/ -v
"""

import pytest
import time
from agent_platform.retry import (
    ErrorCategory,
    RetryConfig,
    RetryError,
    classify_error,
    calculate_delay,
    with_retry,
)


# ─── ERROR CLASSIFICATION TESTS ─────────────────────────────────────────────


def test_classify_timeout_as_transient():
    """
    Network timeouts are temporary — should be classified
    as TRANSIENT so they get retried automatically.
    """
    # Create a fake timeout exception
    error = Exception("connection timeout")

    # Classify it
    category = classify_error(error)

    # Should be transient — retry it
    assert category == ErrorCategory.TRANSIENT


def test_classify_network_error_as_transient():
    """
    Network connection errors are temporary —
    should be classified as TRANSIENT.
    """
    error = Exception("network unavailable")
    category = classify_error(error)
    assert category == ErrorCategory.TRANSIENT


def test_classify_unknown_error_as_transient():
    """
    Unknown errors default to TRANSIENT.
    Better to retry something that didn't need it
    than to give up on something that would have worked.
    """
    error = Exception("something completely unexpected happened")
    category = classify_error(error)
    assert category == ErrorCategory.TRANSIENT


# ─── DELAY CALCULATION TESTS ─────────────────────────────────────────────────


def test_delay_increases_with_attempts():
    """
    Each retry should wait longer than the previous one.
    This is exponential backoff — gives the API time to recover.
    """
    # Use jitter=False so delays are predictable in tests
    config = RetryConfig(jitter=False)

    delay1 = calculate_delay(1, config)
    delay2 = calculate_delay(2, config)
    delay3 = calculate_delay(3, config)

    # Each delay should be larger than the previous
    assert delay2 > delay1
    assert delay3 > delay2


def test_delay_respects_max_delay():
    """
    No matter how many retries, delay should never
    exceed max_delay. Prevents waiting forever.
    """
    # Set a very small max_delay
    config = RetryConfig(
        max_delay=5.0,
        backoff_multiplier=10.0,  # would grow very fast without cap
        jitter=False
    )

    # Even attempt 10 should not exceed max_delay
    delay = calculate_delay(10, config)
    assert delay <= 5.0


def test_delay_base_values():
    """
    Verify the exact delay values with known inputs.
    Attempt 1: 1.0 * (2.0 ^ 0) = 1.0
    Attempt 2: 1.0 * (2.0 ^ 1) = 2.0
    Attempt 3: 1.0 * (2.0 ^ 2) = 4.0
    """
    # jitter=False gives us predictable exact values
    config = RetryConfig(jitter=False)

    assert calculate_delay(1, config) == pytest.approx(1.0)
    assert calculate_delay(2, config) == pytest.approx(2.0)
    assert calculate_delay(3, config) == pytest.approx(4.0)


# ─── WITH_RETRY TESTS ────────────────────────────────────────────────────────


def test_with_retry_succeeds_on_first_attempt():
    """
    When the API call works first time,
    with_retry should return the result immediately.
    """
    # A function that always succeeds
    # This simulates a successful API call
    def successful_call():
        return {"content": "Hello from Claude"}

    # with_retry should return the result
    result = with_retry(
        func=successful_call,
        operation_name="test_success"
    )

    assert result == {"content": "Hello from Claude"}


def test_with_retry_succeeds_after_one_failure():
    """
    When the first attempt fails but the second succeeds,
    with_retry should return the successful result.
    This simulates a transient network hiccup.
    """
    # Track how many times the function was called
    call_count = {"count": 0}

    def flaky_call():
        call_count["count"] += 1
        # Fail on first call, succeed on second
        if call_count["count"] == 1:
            raise Exception("connection timeout")
        return {"content": "Success on retry"}

    # Use fast retry for testing — no real waiting
    config = RetryConfig(
        max_attempts=3,
        base_delay=0.01,  # 10ms instead of 1 second
        jitter=False
    )

    result = with_retry(
        func=flaky_call,
        config=config,
        operation_name="test_flaky"
    )

    # Should have succeeded on second attempt
    assert result == {"content": "Success on retry"}
    assert call_count["count"] == 2


def test_with_retry_raises_after_max_attempts():
    """
    When all attempts fail, with_retry should raise
    a RetryError with details about what happened.
    """
    # A function that always fails
    def always_fails():
        raise Exception("connection timeout")

    # Use fast retry for testing
    config = RetryConfig(
        max_attempts=3,
        base_delay=0.01,
        jitter=False
    )

    # Should raise RetryError after 3 attempts
    with pytest.raises(RetryError) as exc_info:
        with_retry(
            func=always_fails,
            config=config,
            operation_name="test_always_fails"
        )

    # Verify the RetryError has correct information
    error = exc_info.value
    assert error.attempts_made == 3
    assert error.error_category == ErrorCategory.TRANSIENT
    assert error.is_retryable == True


def test_with_retry_gives_up_immediately_on_validation_error():
    """
    VALIDATION errors mean our request is wrong.
    Retrying won't help — give up immediately.
    Should only make 1 attempt, not 3.
    """
    # Track attempts
    call_count = {"count": 0}

    def bad_request():
        call_count["count"] += 1
        # Simulate a validation error — bad parameters
        try:
            import anthropic
            raise anthropic.BadRequestError(
                message="Invalid model name",
                response=None,
                body=None
            )
        except (ImportError, Exception):
            # If anthropic not available or constructor differs,
            # raise a generic error that we'll classify manually
            raise Exception("invalid_request: bad parameters")

    config = RetryConfig(max_attempts=3, base_delay=0.01)

    # This will either raise RetryError or Exception
    # depending on how classify_error handles it
    try:
        with_retry(
            func=bad_request,
            config=config,
            operation_name="test_validation"
        )
    except (RetryError, Exception):
        pass

    # Should have only tried once — no retries for validation errors
    assert call_count["count"] == 1


