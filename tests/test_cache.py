"""
tests/test_cache.py
Tests for agent_platform/cache.py

Run with: pytest tests/ -v
"""

import pytest
from agent_platform.cache import add_cache_control, add_cache_control_to_messages


# ─── add_cache_control TESTS ─────────────────────────────────────────────────


def test_add_cache_control_returns_list():
    """
    add_cache_control should always return a list.
    The Anthropic API expects system= as a list when caching.
    """
    # Pass in a plain string
    result = add_cache_control("You are a helpful assistant")

    # Should return a list
    assert isinstance(result, list)


def test_add_cache_control_returns_one_item():
    """
    The list should contain exactly one dict.
    One system prompt = one cached block.
    """
    result = add_cache_control("You are a helpful assistant")

    # Should have exactly one item
    assert len(result) == 1


def test_add_cache_control_has_correct_type():
    """
    The dict should have type: text.
    This tells Anthropic the content is plain text.
    """
    result = add_cache_control("You are a helpful assistant")

    # First item should have type: text
    assert result[0]["type"] == "text"


def test_add_cache_control_preserves_content():
    """
    The original text should be preserved exactly.
    add_cache_control should not modify the content.
    """
    original = "You are a customer support agent for AcmeCorp."
    result = add_cache_control(original)

    # Text should be exactly what we passed in
    assert result[0]["text"] == original


def test_add_cache_control_has_cache_control_marker():
    """
    The dict must have cache_control with type ephemeral.
    This is what tells Anthropic to cache this content.
    Without this marker caching does not happen.
    """
    result = add_cache_control("You are a helpful assistant")

    # Must have cache_control key
    assert "cache_control" in result[0]

    # Must be ephemeral type
    assert result[0]["cache_control"]["type"] == "ephemeral"


def test_add_cache_control_with_long_system_prompt():
    """
    Should work with a long system prompt — the kind
    you would actually cache in a real project.
    """
    # Simulate a real system prompt with tool definitions
    long_prompt = """
        You are a customer support agent for AcmeCorp.
        
        You have access to four tools:
        - get_customer: look up customer by ID or email
        - lookup_order: find order details by order number
        - process_refund: issue refunds under $500
        - escalate_to_human: hand off to human agent
        
        Refund policy:
        - Standard items: full refund within 30 days
        - Electronics: exchange only after 14 days
        - Refunds over $500 require manager approval
        
        Always verify customer identity before accessing
        account information.
    """ * 10  # repeat to make it realistically long

    result = add_cache_control(long_prompt)

    # Should still work correctly
    assert result[0]["text"] == long_prompt
    assert result[0]["cache_control"]["type"] == "ephemeral"


# ─── add_cache_control_to_messages TESTS ─────────────────────────────────────


def test_messages_cache_returns_list():
    """
    Should always return a list — same structure as input.
    """
    messages = [
        {"role": "user", "content": "My order is damaged"}
    ]

    result = add_cache_control_to_messages(messages, cache_last_n=1)

    assert isinstance(result, list)


def test_messages_cache_preserves_length():
    """
    Should return the same number of messages.
    Caching should not add or remove messages.
    """
    messages = [
        {"role": "user", "content": "My order is damaged"},
        {"role": "assistant", "content": "I can help"},
        {"role": "user", "content": "Order #12345"},
    ]

    result = add_cache_control_to_messages(messages, cache_last_n=1)

    # Same number of messages
    assert len(result) == 3


def test_messages_cache_last_message_has_cache_control():
    """
    The last message should have cache_control added.
    This is the marker that tells Anthropic where to cache up to.
    """
    messages = [
        {"role": "user", "content": "My order is damaged"},
        {"role": "assistant", "content": "I can help"},
        {"role": "user", "content": "Order #12345"},
    ]

    result = add_cache_control_to_messages(messages, cache_last_n=1)

    # Last message content should be a list with cache_control
    last_message = result[-1]
    assert isinstance(last_message["content"], list)
    assert last_message["content"][-1]["cache_control"]["type"] == "ephemeral"


def test_messages_cache_does_not_modify_original():
    """
    Should not modify the original messages list.
    Always work on a copy — never mutate the input.
    """
    messages = [
        {"role": "user", "content": "My order is damaged"},
        {"role": "assistant", "content": "I can help"},
    ]

    # Store original content for comparison
    original_content = messages[0]["content"]

    # Call the function
    add_cache_control_to_messages(messages, cache_last_n=1)

    # Original should be unchanged
    assert messages[0]["content"] == original_content


def test_messages_cache_last_n_2():
    """
    With cache_last_n=2, the last 2 messages should
    have cache_control markers added.
    """
    messages = [
        {"role": "user", "content": "Message 1"},
        {"role": "assistant", "content": "Response 1"},
        {"role": "user", "content": "Message 2"},
        {"role": "assistant", "content": "Response 2"},
    ]

    result = add_cache_control_to_messages(messages, cache_last_n=2)

    # Last two messages should have cache_control
    assert isinstance(result[-1]["content"], list)
    assert isinstance(result[-2]["content"], list)

    # First two messages should be unchanged
    assert isinstance(result[0]["content"], str)
    assert isinstance(result[1]["content"], str)


def test_messages_cache_handles_empty_list():
    """
    Should handle an empty messages list without crashing.
    Edge case — agent loop might start with no messages.
    """
    messages = []

    # Should not raise an error
    result = add_cache_control_to_messages(messages, cache_last_n=1)

    assert result == []
