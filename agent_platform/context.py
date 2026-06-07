"""
agent_platform/context.py

Context window management for agentic loops.

The problem: self.messages grows every turn. Long sessions hit
the 200k token limit and crash with no recovery.

The solution: before each API call, check if we're approaching
the limit. If yes, call Claude to summarize old messages, replace
them with the summary, keep the last N messages verbatim.

Configured via environment variables:
    CONTEXT_WINDOW_LIMIT        default 200000
    CONTEXT_SUMMARIZE_THRESHOLD default 0.75
"""

import anthropic
from agent_platform.logging import get_logger, log_event
from agent_platform.config import config

logger = get_logger(__name__)

KEEP_LAST_N = 6  # always keep this many recent messages verbatim


class ContextManager:
    """
    Tracks token usage and summarizes old messages when
    approaching the context window limit.
    """

    def __init__(self):
        self.max_tokens = config.context_window_limit
        self.threshold = config.context_summarize_threshold
        self.current_tokens = 0
        self.summarization_count = 0

    def update_token_count(self, input_tokens: int) -> None:
        """Call this after every API response with input_tokens used."""
        self.current_tokens = input_tokens
        log_event(logger, "context_token_update",
                  current=self.current_tokens,
                  max=self.max_tokens,
                  percent=round(self.current_tokens / self.max_tokens * 100, 1))

    def is_approaching_limit(self) -> bool:
        """Returns True if current usage exceeds the threshold."""
        return self.current_tokens >= (self.max_tokens * self.threshold)

    def maybe_summarize(self, messages: list, client: anthropic.Anthropic) -> list:
        """
        Check if approaching limit. If yes, summarize old messages
        and return compressed list. Otherwise return unchanged.

        Always keeps KEEP_LAST_N recent messages verbatim so Claude
        has full context on what just happened.
        """
        if not self.is_approaching_limit():
            return messages

        if len(messages) <= KEEP_LAST_N:
            # Not enough messages to summarize
            log_event(logger, "context_summarize_skipped",
                      reason="too_few_messages")
            return messages

        log_event(logger, "context_summarize_started",
                  total_messages=len(messages),
                  keeping_last=KEEP_LAST_N,
                  summarization_count=self.summarization_count + 1)

        # Split: old messages to summarize, recent to keep verbatim
        old_messages = messages[:-KEEP_LAST_N]
        recent_messages = messages[-KEEP_LAST_N:]

        # Build the conversation text to summarize
        conversation_text = self._messages_to_text(old_messages)

        # Call Claude to summarize
        summary = self._summarize(conversation_text, client)

        # Replace old messages with a single summary message
        summary_message = {
            "role": "user",
            "content": f"[CONVERSATION SUMMARY - earlier messages compressed]\n{summary}"
        }

        compressed = [summary_message] + recent_messages

        self.summarization_count += 1
        log_event(logger, "context_summarize_complete",
                  before=len(messages),
                  after=len(compressed),
                  summarization_count=self.summarization_count)

        return compressed

    def _messages_to_text(self, messages: list) -> str:
        """Convert messages list to readable text for summarization."""
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            if isinstance(content, list):
                # Tool use blocks — extract text parts only
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        lines.append(f"{role}: {block['text']}")
                    elif isinstance(block, dict) and block.get("type") == "tool_result":
                        lines.append(f"TOOL RESULT: {block.get('content', '')}")
            else:
                lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _summarize(self, conversation_text: str,
                   client: anthropic.Anthropic) -> str:
        """Call Claude to summarize old conversation messages."""
        response = client.messages.create(
            model=config.dev_model,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": (
                    "Summarize this customer support conversation concisely. "
                    "Preserve: customer name, email, verified IDs, order details, "
                    "what was attempted, what failed and why, any confirmation numbers. "
                    "Be factual and brief.\n\n"
                    f"{conversation_text}"
                )
            }]
        )
        summary = response.content[0].text
        log_event(logger, "context_summarized",
                  summary_length=len(summary))
        return summary