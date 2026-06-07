"""
projects/p1_customer_support/src/handoff.py

Builds the structured handoff package for human agents.

The problem this solves: when escalation fires, Claude writes a narrative
summary from conversation context. That's useful but unreliable — it's
probabilistic, can miss details, and doesn't include system-level facts
Claude doesn't know (like whether a DB write committed before a hook blocked).

HandoffContext accumulates structured facts from the system as the session
progresses. When escalate_to_human fires, it gets injected alongside
Claude's narrative so the human agent has both:
  - Guaranteed structured fields they can act on immediately
  - Claude's narrative for context

This covers TS 1.4: multi-step workflows with handoff patterns.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class HandoffContext:
    """
    Structured facts accumulated during a session.
    Built by AgentSession, injected into escalate_to_human.

    The system builds this — not Claude. These fields are
    guaranteed to be accurate regardless of what Claude says.
    """

    # Customer facts
    customer_id: Optional[str] = None
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None
    customer_tier: Optional[str] = None

    # Order facts
    order_id: Optional[str] = None
    order_number: Optional[str] = None
    order_amount: Optional[float] = None

    # What was attempted
    attempted_action: Optional[str] = None
    block_reason: Optional[str] = None

    # Critical: did a refund execute in the DB before a hook blocked it?
    # If True, the human agent must NOT refund again — money may have moved.
    refund_executed_in_db: bool = False
    confirmation_number: Optional[str] = None
    refund_amount_attempted: Optional[float] = None

    def set_customer(self, customer_id: str, email: str,
                     name: str, tier: str) -> None:
        self.customer_id = customer_id
        self.customer_email = email
        self.customer_name = name
        self.customer_tier = tier

    def set_order(self, order_id: str, order_number: str,
                  amount: float) -> None:
        self.order_id = order_id
        self.order_number = order_number
        self.order_amount = amount

    def set_attempted_action(self, action: str, block_reason: str) -> None:
        self.attempted_action = action
        self.block_reason = block_reason

    def set_refund_executed(self, confirmation_number: str,
                            amount: float) -> None:
        """
        Call this when process_refund commits to DB successfully.
        Even if a PostToolUse hook blocks the result afterward,
        the human agent needs to know the refund exists in the DB.
        """
        self.refund_executed_in_db = True
        self.confirmation_number = confirmation_number
        self.refund_amount_attempted = amount

    def to_dict(self) -> dict:
        """Serializes to dict for injection into escalate_to_human."""
        return {
            "customer_id": self.customer_id,
            "customer_email": self.customer_email,
            "customer_name": self.customer_name,
            "customer_tier": self.customer_tier,
            "order_id": self.order_id,
            "order_number": self.order_number,
            "order_amount": self.order_amount,
            "attempted_action": self.attempted_action,
            "block_reason": self.block_reason,
            "refund_executed_in_db": self.refund_executed_in_db,
            "confirmation_number": self.confirmation_number,
            "refund_amount_attempted": self.refund_amount_attempted,
        }

    def to_agent_context_string(self) -> str:
        """
        Formats the handoff context as a string for the escalation ticket.
        """
        lines = ["[SYSTEM HANDOFF CONTEXT]"]

        if self.customer_id:
            lines.append(f"Customer: {self.customer_name} ({self.customer_id}) "
                        f"{self.customer_email} tier={self.customer_tier}")
        if self.order_id:
            lines.append(f"Order: {self.order_number} ({self.order_id}) "
                        f"${self.order_amount}")
        if self.attempted_action:
            lines.append(f"Attempted: {self.attempted_action}")
            lines.append(f"Block reason: {self.block_reason}")
        if self.refund_executed_in_db:
            lines.append(
                f"WARNING REFUND EXECUTED IN DB: {self.confirmation_number} "
                f"for ${self.refund_amount_attempted} — "
                f"DO NOT process refund again. Verify payment processor."
            )

        return "\n".join(lines)
    
    def reset_attempted_action(self) -> None:
        self.attempted_action = None
        self.block_reason = None    