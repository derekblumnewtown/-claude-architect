"""
tests/test_handoff.py
Unit tests for HandoffContext — the structured handoff package.

These tests prove the handoff always contains the right facts
regardless of which escalation path triggered it.
No API calls, no DB — pure unit tests.
"""

from projects.p1_customer_support.src.handoff import HandoffContext


def test_empty_handoff_serializes_without_error():
    h = HandoffContext()
    result = h.to_dict()
    assert result["customer_id"] is None
    assert result["refund_executed_in_db"] is False


def test_set_refund_executed_flags_correctly():
    h = HandoffContext()
    h.set_refund_executed("REF-ABC123", 749.99)
    assert h.refund_executed_in_db is True
    assert h.confirmation_number == "REF-ABC123"
    assert h.refund_amount_attempted == 749.99


def test_context_string_includes_warning_when_refund_executed():
    h = HandoffContext()
    h.set_customer("CUST-002", "sarah.jones@email.com", "Sarah Jones", "vip")
    h.set_order("ORD-003", "#10003", 749.99)
    h.set_refund_executed("REF-ABC123", 749.99)
    result = h.to_agent_context_string()
    assert "DO NOT process refund again" in result
    assert "REF-ABC123" in result


def test_context_string_no_warning_when_no_refund():
    h = HandoffContext()
    h.set_customer("CUST-001", "john.smith@email.com", "John Smith", "standard")
    h.set_attempted_action("lookup_order", "permission")
    result = h.to_agent_context_string()
    assert "DO NOT process refund again" not in result
    assert "lookup_order" in result