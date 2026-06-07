"""
tests/test_context.py
Unit tests for ContextManager — no API calls, fake token counts.
"""

from agent_platform.context import ContextManager, KEEP_LAST_N


def test_not_approaching_limit_when_under_threshold():
    manager = ContextManager()
    manager.update_token_count(100000)  # 50% of 200k
    print(manager.max_tokens)
    assert manager.is_approaching_limit() == False


def test_approaching_limit_when_over_threshold():
    manager = ContextManager()
    manager.update_token_count(160000)  # 80% of 200k — at default threshold
    assert manager.is_approaching_limit() == True


def test_exactly_at_threshold_triggers_limit():
    manager = ContextManager()
    threshold_tokens = int(manager.max_tokens * manager.threshold)
    manager.update_token_count(threshold_tokens)
    assert manager.is_approaching_limit() == True


def test_messages_unchanged_when_under_limit():
    manager = ContextManager()
    manager.update_token_count(100000)  # under threshold
    messages = [{"role": "user", "content": f"message {i}"} for i in range(10)]
    result = manager.maybe_summarize(messages, client=None)
    assert result == messages  # unchanged, no API call needed


def test_too_few_messages_skips_summarize():
    manager = ContextManager()
    manager.update_token_count(160000)  # over threshold
    # Only KEEP_LAST_N messages — nothing old to summarize
    messages = [{"role": "user", "content": f"message {i}"} for i in range(KEEP_LAST_N)]
    result = manager.maybe_summarize(messages, client=None)
    assert result == messages  # unchanged


def test_token_count_updates_correctly():
    manager = ContextManager()
    manager.update_token_count(50000)
    assert manager.current_tokens == 50000
    manager.update_token_count(75000)
    assert manager.current_tokens == 75000


def test_summarization_count_starts_at_zero():
    manager = ContextManager()
    assert manager.summarization_count == 0