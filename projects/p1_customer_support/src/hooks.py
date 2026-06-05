"""
projects/p1_customer_support/src/hooks.py
Hook implementations for enforcing business rules.

Hooks intercept tool calls and enforce deterministic rules
that prompts alone cannot guarantee.

Three hooks:
1. PreToolUse on lookup_order - require verified customer_id
2. PreToolUse on process_refund - require verified customer_id AND order_id
3. PostToolUse on process_refund - block refunds over $500
"""

from agent_platform.logging import get_logger, log_event

logger = get_logger(__name__)


class HookContext:
    """
    Tracks verified data during the agent loop.
    
    As tools execute and return results, we record what's been verified.
    Hooks check this context to enforce prerequisites.
    """
    
    def __init__(self):
        self.verified_customer_id = None
        self.verified_order_id = None
    
    def set_customer_verified(self, customer_id: str):
        """Record that a customer has been verified."""
        log_event(logger, "hook_customer_verified", customer_id=customer_id)
        self.verified_customer_id = customer_id
    
    def set_order_verified(self, order_id: str):
        """Record that an order has been verified."""
        log_event(logger, "hook_order_verified", order_id=order_id)
        self.verified_order_id = order_id
    
    def is_customer_verified(self) -> bool:
        """Check if customer is verified."""
        return self.verified_customer_id is not None
    
    def is_order_verified(self) -> bool:
        """Check if order is verified."""
        return self.verified_order_id is not None

def hook_pre_lookup_order(tool_input: dict, context: HookContext) -> dict:
    """
    Hook 2 — PreToolUse on lookup_order
    Block unless customer_id is verified AND has been passed correctly.
    """
    log_event(logger, "hook_pre_lookup_order",
        customer_verified=context.is_customer_verified()
    )
    
    # Check: is customer verified in our context?
    if not context.is_customer_verified():
        error = {
            "success": False,
            "errorCategory": "permission",
            "isRetryable": False,
            "description": "Must verify customer identity first. Call get_customer first and wait for the result."
        }
        log_event(logger, "hook_lookup_order_blocked", reason="customer_not_verified")
        return error
    
    # Check: did Claude pass the correct verified customer_id?
    passed_customer_id = tool_input.get("customer_id")
    if passed_customer_id != context.verified_customer_id:
        error = {
            "success": False,
            "errorCategory": "permission",
            "isRetryable": False,
            "description": f"Customer ID mismatch. You verified {context.verified_customer_id} but passed {passed_customer_id}. Use the verified customer ID."
        }
        log_event(logger, "hook_lookup_order_blocked", reason="customer_id_mismatch")
        return error
    
    # Allow the call
    return None


def hook_pre_process_refund(tool_input: dict, context: HookContext) -> dict:
    """
    Hook 3 — PreToolUse on process_refund
    
    Block process_refund unless both customer_id AND order_id are verified.
    
    Args:
        tool_input: The arguments Claude passed to process_refund
        context: HookContext tracking verified data
        
    Returns:
        None if allowed
        Error dict if blocked
    """
    log_event(logger, "hook_pre_process_refund",
        customer_verified=context.is_customer_verified(),
        order_verified=context.is_order_verified()
    )
    
    # Check: is customer verified?
    if not context.is_customer_verified():
        error = {
            "success": False,
            "errorCategory": "permission",
            "isRetryable": False,
            "description": "Must verify customer identity first before processing refunds"
        }
        log_event(logger, "hook_process_refund_blocked", reason="customer_not_verified")
        return error
    
    # Check: is order verified?
    if not context.is_order_verified():
        error = {
            "success": False,
            "errorCategory": "permission",
            "isRetryable": False,
            "description": "Must verify order first before processing refunds"
        }
        log_event(logger, "hook_process_refund_blocked", reason="order_not_verified")
        return error
    
    # Allow the call
    return None


def hook_post_process_refund(tool_result: dict, tool_input: dict, context: HookContext) -> dict:
    """
    Hook 1 — PostToolUse on process_refund
    
    Block refunds over $500 and redirect to escalation.
    
    Args:
        tool_result: What process_refund returned
        tool_input: The arguments Claude passed to process_refund
        context: HookContext tracking verified data
        
    Returns:
        Modified tool_result or escalation redirect
    """
    refund_amount = tool_input.get("refund_amount", 0)
    
    log_event(logger, "hook_post_process_refund",
        refund_amount=refund_amount,
        over_threshold=refund_amount > 500
    )
    
    # Check: is refund over $500?
    if refund_amount > 500:
        log_event(logger, "hook_process_refund_blocked",
            reason="amount_over_500",
            refund_amount=refund_amount
        )
        
        # Block the refund and redirect to escalation
        return {
            "success": False,
            "blocked_by_hook": True,
            "reason": "Refunds over $500 require manager approval",
            "requires_escalation": True,
            "escalation_reason": f"Refund of ${refund_amount} exceeds $500 threshold"
        }
    
    # Allow the refund
    return tool_result