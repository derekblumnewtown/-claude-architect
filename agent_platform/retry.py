"""
agent_platform/retry.py
Retry logic with exponential backoff and error classification.

Handles the three types of errors you will encounter
when calling the Anthropic API:

    TRANSIENT   — temporary failures, always retry
                  (network timeout, rate limit, server error)

    VALIDATION  — your request was wrong, never retry
                  (bad parameters, invalid model name)

    PERMISSION  — access denied, never retry
                  (invalid API key, quota exceeded)

Usage:
    from agent_platform.retry import with_retry, RetryError

    # Wrap any API call with automatic retry
    response = with_retry(
        lambda: client.messages.create(...)
    )
"""

import time
import random
from enum import Enum
from dataclasses import dataclass
from typing import Callable, Any, Optional
from agent_platform.logging import get_logger, log_event

# Get a logger for this module
logger = get_logger(__name__)


class ErrorCategory(Enum):
    """
    The three categories of API errors.
    Only TRANSIENT errors get retried.
    """
    # Temporary — retry these
    TRANSIENT = "transient"

    # Your request was wrong — fix it, don't retry
    VALIDATION = "validation"

    # Access denied — don't retry
    PERMISSION = "permission"


@dataclass
class RetryConfig:
    """
    Controls how retry behaves.

    Defaults are sensible for most API calls:
    - Try up to 3 times
    - Wait longer between each attempt
    - Add randomness to prevent all retries hitting at once
    """
   
    max_attempts: int = 3              # Maximum number of attempts including the first try
    base_delay: float = 1.0           # How long to wait after the first failure (seconds)
    backoff_multiplier: float = 2.0   # Multiply delay by this after each failure, 1.0/wait 1s, 2.0 / wait 2s, 4.0 /wait 4s
    max_delay: float = 30.0           # Maximum wait time between retries (seconds)

    # Add random jitter to prevent thundering herd
    # All retries hitting the API at exactly the same time
    jitter: bool = True


@dataclass
class RetryError(Exception):
    """
    Structured error response returned when all retries fail
    or when the error is not retryable.

    Every project imports this to handle failures consistently.
    """
    # Which category of error this is
    error_category: ErrorCategory

    # Can this error be retried
    is_retryable: bool

    # Human readable description of what went wrong
    description: str

    # The original exception that caused the error
    original_error: Optional[Exception] = None

    # How many attempts were made before giving up
    attempts_made: int = 0

    def __post_init__(self):
        super().__init__(self.description)


def classify_error(error: Exception) -> ErrorCategory:
    """
    Looks at an exception and decides which category it is.
    
    This determines whether we retry or give up immediately.
    
    Args:
        error: The exception that was raised during the API call
        
    Returns:
        ErrorCategory — TRANSIENT, VALIDATION, or PERMISSION
    """
    # Get the error type name as a string for easy checking
    error_type = type(error).__name__
    error_message = str(error).lower()

    # Import here to avoid circular imports - These are Anthropic SDK specific error types
    try:
        import anthropic
        
        # Rate limit — we sent too many requests too fast - Wait and retry
        if isinstance(error, anthropic.RateLimitError):
            return ErrorCategory.TRANSIENT

        # Server error — Anthropic's servers had a problem - Not our fault, retry
        if isinstance(error, anthropic.InternalServerError):
            return ErrorCategory.TRANSIENT

        # Bad request — something wrong with our parameters - Retrying won't help — we need to fix the request
        if isinstance(error, anthropic.BadRequestError):
            return ErrorCategory.VALIDATION

        # Authentication error — wrong API key - Retrying won't help — we need to fix the key
        if isinstance(error, anthropic.AuthenticationError):
            return ErrorCategory.PERMISSION

        # Permission denied — quota exceeded or access denied
        if isinstance(error, anthropic.PermissionDeniedError):
            return ErrorCategory.PERMISSION

    except ImportError:
        # Anthropic not installed — classify by error message
        pass

    # Validation errors — bad request, invalid parameters
    if any(keyword in error_message for keyword in ["invalid_request", "bad_request", "invalid parameter", "bad parameter", "validation", "invalid model"]):
        return ErrorCategory.VALIDATION

    # Permission errors — authentication or access denied
    if any(keyword in error_message for keyword in ["authentication", "unauthorized", "permission denied", "forbidden", "invalid key", "api_key"]):
        return ErrorCategory.PERMISSION

    # Network errors — connection problems, timeouts
    # These are always transient — retry
    if any(keyword in error_message for keyword in ["timeout", "connection", "network","temporary", "unavailable", "503", "502"]):
        return ErrorCategory.TRANSIENT

    # Unknown errors — assume transient to be safe
    return ErrorCategory.TRANSIENT


def calculate_delay(attempt: int, config: RetryConfig,) -> float:
    """
    Calculates how long to wait before the next retry.
    Uses exponential backoff — waits longer after each failure.
    
    Args:
        attempt: Which attempt just failed (1-based)
        config: The retry configuration
        
    Returns:
        How many seconds to wait before retrying
        
    Example with defaults:
        Attempt 1 fails → wait 1.0s
        Attempt 2 fails → wait 2.0s
        Attempt 3 fails → wait 4.0s (capped at max_delay)
    """
    # Exponential backoff formula: delay = base_delay * (backoff_multiplier ^ (attempt - 1))
    delay = config.base_delay * (config.backoff_multiplier ** (attempt - 1))

    # Never wait longer than max_delay
    delay = min(delay, config.max_delay)

    # Add jitter — random amount between 0 and 1 second / Prevents all retries hitting the API at exactly the same time
    if config.jitter:
        delay += random.uniform(0, 1.0)

    return delay


def with_retry(func: Callable[[], Any], config: Optional[RetryConfig] = None, operation_name: str = "api_call",) -> Any:
    """
    Wraps any function call with automatic retry logic.
    
    Pass a lambda that makes your API call.
    with_retry handles all retry logic automatically.
    
    Args:
        func: A callable that makes the API call
              Use a lambda: lambda: client.messages.create(...)
        config: Retry configuration — uses defaults if not provided
        operation_name: Name for logging — helps identify which
                       call is being retried in the logs
                       
    Returns:
        The return value of func() if successful
        
    Raises:
        RetryError: If all retries fail or error is not retryable
        
    Example:
        # Simple usage with defaults
        response = with_retry(
            lambda: client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=1000,
                messages=[{"role": "user", "content": "Hello"}]
            )
        )
        
        # Custom config — more attempts for important calls
        response = with_retry(
            lambda: client.messages.create(...),
            config=RetryConfig(max_attempts=5, base_delay=2.0),
            operation_name="process_refund"
        )
    """

    # Use default config if none provided
    if config is None:
        config = RetryConfig()

    # Track which attempt we are on
    attempt = 0

    # Keep trying until we succeed or run out of attempts
    while attempt < config.max_attempts:
        attempt += 1

        try:
            log_event(logger, "retry_attempt", operation=operation_name, attempt=attempt, max_attempts=config.max_attempts,)

            # Try the API call — if it works, return immediately
            result = func()

            # Success — log it and return the result
            log_event(logger, "retry_success", operation=operation_name, attempt=attempt,)

            return result

        except Exception as error:

            # Classify the error to decide what to do
            category = classify_error(error)

            log_event(logger, "retry_error", operation=operation_name, attempt=attempt, error_category=category.value,
                      error_type=type(error).__name__, error_message=str(error)[:200],)

            # VALIDATION and PERMISSION errors — give up immediately - Retrying won't help — the request itself is wrong
            if category != ErrorCategory.TRANSIENT:
                raise RetryError( error_category=category, is_retryable=False,
                                  description=f"{category.value} error on {operation_name}: {str(error)[:200]}",
                                  original_error=error, attempts_made=attempt,)

            # TRANSIENT error — check if we have attempts left
            if attempt >= config.max_attempts:
                # Ran out of attempts — give up
                raise RetryError(error_category=ErrorCategory.TRANSIENT, is_retryable=True,
                                 description=f"All {config.max_attempts} attempts failed for {operation_name}",
                                 original_error=error, attempts_made=attempt,)

            # Calculate how long to wait before next attempt
            delay = calculate_delay(attempt, config)

            log_event(logger, "retry_waiting", operation=operation_name, attempt=attempt, waiting_seconds=round(delay, 2), next_attempt=attempt + 1,)

            # Wait before trying again
            time.sleep(delay)