"""
tests/test_hooks.py
Unit tests for business rule hooks — no API calls, fully deterministic.
"""

from projects.p1_customer_support.src.hooks import (
    HookContext,
    hook_pre_lookup_order,
    hook_pre_process_refund,
    hook_post_process_refund,
)


def test_lookup_order_blocked_when_customer_not_verified():
    context = HookContext()  # nothing verified
    result = hook_pre_lookup_order({"customer_id": "C001", "order_number": "#10001"}, context)
    assert result is not None
    assert result["success"] is False
    assert result["block_reason"] == "customer_not_verified"


def test_lookup_order_allowed_when_customer_verified():
    context = HookContext()
    context.set_customer_verified("C001")
    result = hook_pre_lookup_order({"customer_id": "C001", "order_number": "#10001"}, context)
    assert result is None  # None means allowed


def test_lookup_order_blocked_on_customer_id_mismatch():
    context = HookContext()
    context.set_customer_verified("C001")
    result = hook_pre_lookup_order({"customer_id": "C999", "order_number": "#10001"}, context)
    assert result is not None
    assert "mismatch" in result["description"].lower()


# Your turn — write these four:

def test_process_refund_blocked_when_order_not_verified():
    # customer verified, order NOT verified → should block
    ...

def test_refund_over_500_blocked_by_post_hook():
    # refund_amount=500.01 → blocked, requires_escalation=True
    ...

def test_refund_at_exactly_500_allowed():
    # refund_amount=500.00 → passes through unchanged
    # (this pins down the > vs >= decision in code)
    ...

def test_refund_under_500_passes_result_through():
    context = HookContext()
    original = {"success": True, "confirmation_number": "REF-123", "amount": 250.00}
    result = hook_post_process_refund(original, {"refund_amount": 250.00}, context)
    assert result is original   # not just equal — the same object, unmodified