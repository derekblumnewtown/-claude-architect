"""
agent_platform/cache.py
Prompt caching helpers for the Anthropic API.

Reduces repeated input token costs by 90% by marking content
that doesn't change between API calls — system prompts, tool
definitions, and large documents.

How it works:
    First call:  full price for marked content
    Every call after: 90% cheaper for the same marked content

Anthropic caches content for up to 5 minutes of inactivity.
Cache resets if you go 5 minutes without an API call.

Usage:
    # Mark your system prompt for caching
    system = add_cache_control("You are a helpful assistant...")
    
    # Mark a large document for caching
    document = add_cache_control(large_document_text)
"""

from agent_platform.logging import get_logger, log_event

# Get a logger for this module — __name__ = "agent_platform.cache"
logger = get_logger(__name__)


def add_cache_control(content: str) -> list[dict]:
    """
    Wraps a string in the Anthropic cache_control format.
    
    Pass the return value directly as the system= parameter in your API call.
    
    Args:
        content: The text you want cached — system prompt, tool definitions, or large document
    
    Returns:
        A list with one dict containing the content and
        cache_control marker that tells Anthropic to cache it
    
    Example:
        system = add_cache_control("You are a support agent...")
        response = client.messages.create( model="claude-haiku-4-5",
                                           system=system,   # pass directly here
                                           messages=[...])
    """

    # Log how many characters are being cached so we can verify caching is working
    log_event(logger, "cache_control_added", content_length=len(content),)

    # Return the format Anthropic expects for cached content.
    # This is a list containing one dict with two keys:
    #   type: always "text" for text content
    #   text: the actual content to cache
    #   cache_control: tells Anthropic to cache this block
    return [{"type": "text", "text": content,
             "cache_control": {"type": "ephemeral"},}]


def add_cache_control_to_messages(messages: list[dict], cache_last_n: int = 1,) -> list[dict]:
    """
    Adds cache_control to the last N messages in a conversation.
    
    Useful in long conversations where you want to cache
    the conversation history that won't change.
    
    Args:
        messages: Your conversation history list
        cache_last_n: How many messages from the end to cache
                      Default is 1 — just the last message
    
    Returns:
        The same messages list with cache_control added
        to the last N messages
    
    Example:
        # Cache the last 3 messages in a long conversation
        messages = add_cache_control_to_messages(
            messages=conversation_history,
            cache_last_n=3
        )
    """
    # Don't modify the original list — work on a copy
    cached_messages = messages.copy()

    # Find the last N messages and add cache_control
    # max() prevents going below index 0 if cache_last_n
    # is larger than the number of messages
    start_index = max(0, len(cached_messages) - cache_last_n)

    for i in range(start_index, len(cached_messages)):

        message = cached_messages[i]

        # Content can be a string or a list of blocks
        # We need it to be a list to add cache_control
        if isinstance(message["content"], str):
            # Convert string content to block format
            cached_messages[i] = {
                **message,
                "content": [
                    {
                        "type": "text",
                        "text": message["content"],
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        elif isinstance(message["content"], list):
            # Content is already a list — add cache_control
            # to the last block in the list
            content_copy = message["content"].copy()
            if content_copy:
                last_block = content_copy[-1].copy()
                last_block["cache_control"] = {"type": "ephemeral"}
                content_copy[-1] = last_block
                cached_messages[i] = {
                    **message,
                    "content": content_copy,
                }

    log_event(logger,"messages_cache_control_added",
        # Log how many messages got cache_control
        messages_cached=cache_last_n, total_messages=len(cached_messages),)

    return cached_messages