"""
projects/p1_customer_support/src/tools.py
The four MCP tools for the customer support agent.
"""

import sqlite3
import json
import uuid
from datetime import datetime
from agent_platform.logging import get_logger, log_event
from projects.p1_customer_support.src.database import get_connection

logger = get_logger(__name__)


def get_customer(email: str) -> dict:
    """
    Look up and verify a customer by email address.
    This is the first tool called in the agent loop.
    """
    log_event(logger, "get_customer_called", email=email)
    
    if "@" not in email or "." not in email:
        return {"success": False, "errorCategory": "validation", "isRetryable": True, "description": f"Invalid email format: {email}"}
    
    conn = get_connection()
    try:

        row = conn.execute("SELECT * FROM customers WHERE email = ?", (email.lower().strip(),)).fetchone()
        
        # The email does not exist
        if not row:
            return {"success": False,"errorCategory": "validation", "isRetryable": True,
                    "description": f"No account found for {email}"}
        
        # The Account has been suspended
        if row["account_status"] == "suspended":
            return {"success": False, "errorCategory": "permission", "isRetryable": False,
                    "description": "Account is suspended", "requires_escalation": True }
        
        # Found the email
        log_event(logger, "get_customer_success", customer_id=row["customer_id"])
        return {"success": True, "customer_id": row["customer_id"], "full_name": row["full_name"],
                "email": row["email"], "account_status": row["account_status"], "customer_tier": row["customer_tier"],}
        
    finally:
        conn.close()


def lookup_order(customer_id: str, order_number: str) -> dict:
    """
    Find and verify an order for a verified customer.
    """
    log_event(logger, "lookup_order_called", customer_id=customer_id, order_number=order_number)
    
    conn = get_connection()
    
    try:
        row = conn.execute(
            "SELECT * FROM orders WHERE order_number = ?", (order_number.strip(),)).fetchone()
        
        if not row:
            return {"success": False,"errorCategory": "validation","isRetryable": True,
                    "description": f"Order {order_number} not found"}
        
        if row["customer_id"] != customer_id:
            return {"success": False,"errorCategory": "permission", "isRetryable": False,
                    "description": "Order does not belong to this account",
                    "requires_escalation": True}
        
        items = json.loads(row["items"])
        
        log_event(logger, "lookup_order_success", order_id=row["order_id"])
        
        return {"success": True, "order_id": row["order_id"], "order_number": row["order_number"], "items": items, "order_date": row["order_date"],
                "delivery_date": row["delivery_date"], "order_status": row["order_status"], "total_amount": row["total_amount"], 
                "already_refunded": bool(row["already_refunded"]),}
        
    finally:
        conn.close()


def process_refund(customer_id: str, order_id: str, refund_amount: float, reason: str) -> dict:
    """
    Process a refund for a verified customer and order.
    Hook 1 intercepts this after execution if amount > $500.
    """
    log_event(logger, "process_refund_called", customer_id=customer_id, refund_amount=refund_amount)
    
    conn = get_connection()
    
    try:
        order = conn.execute("SELECT * FROM orders WHERE order_id = ? AND customer_id = ?",
                             (order_id, customer_id)).fetchone()
        
        if not order:
            return {"success": False, "errorCategory": "validation", "isRetryable": False,
                    "description": "Order not found",
                    "requires_escalation": True
            }
        
        if order["already_refunded"]:
            return {"success": False, "errorCategory": "validation", "isRetryable": False,
                    "description": f"Order {order['order_number']} already refunded"}
        
        if order["order_status"] != "delivered":
            return {"success": False, "errorCategory": "validation", "isRetryable": False,
                    "description": f"Order status is {order['order_status']}, not eligible"}
        
        confirmation_number = f"REF-{uuid.uuid4().hex[:8].upper()}"
        refund_id = f"RFD-{uuid.uuid4().hex[:8].upper()}"
        
        conn.execute("""INSERT INTO refunds
                       (refund_id, order_id, customer_id, refund_amount, reason, status, confirmation_number, created_at)
                       VALUES (?, ?, ?, ?, ?, 'approved', ?, ?)""",
                      (refund_id, order_id, customer_id, refund_amount, reason, confirmation_number, datetime.now().isoformat()))
        
        conn.execute("UPDATE orders SET already_refunded = 1 WHERE order_id = ?", (order_id,))
        
        conn.commit()
        
        log_event(logger, "process_refund_success", confirmation_number=confirmation_number)
        
        return {"success": True, "refund_id": refund_id, "confirmation_number": confirmation_number, "refund_amount": refund_amount, 
                "timeline": "3-5 business days",}
        
    finally:
        conn.close()


def escalate_to_human(reason: str, conversation_summary: str, recommended_action: str,
                     customer_id: str = None, order_id: str = None,
                     handoff_context: dict = None) -> dict:
    """
    Escalate the case to a human agent.
    """
    log_event(logger, "escalate_to_human_called", reason=reason, has_handoff_context=handoff_context is not None)

    # Append structured handoff facts to the summary so nothing is lost
    full_summary = conversation_summary
    if handoff_context:
        import json
        full_summary = (
            conversation_summary
            + "\n\n[SYSTEM HANDOFF CONTEXT]\n"
            + json.dumps(handoff_context, indent=2)
        )
    
    conn = get_connection()
    
    try:
        escalation_id = f"ESC-{uuid.uuid4().hex[:8].upper()}"
        
        conn.execute(
            """INSERT INTO escalations
            (escalation_id, customer_id, order_id, reason,
             conversation_summary, recommended_action, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'open', ?)""",
            (escalation_id,
             handoff_context.get("customer_id") if handoff_context else customer_id,
             handoff_context.get("order_id") if handoff_context else order_id,
             reason, full_summary, recommended_action,
             datetime.now().isoformat())
        )
        
        conn.commit()
        log_event(logger, "escalation_created", escalation_id=escalation_id)
        return {
            "success": True,
            "escalation_id": escalation_id,
            "message_to_customer": f"I'm connecting you with a human agent. Reference: {escalation_id}. Wait time: 5-10 minutes.",
        }
        
    finally:
        conn.close()

def handle_tool_call(tool_name: str, tool_input: dict,
                     handoff_context: dict = None) -> dict:
    """
    Route tool calls from Claude to the correct function.
    """

    log_event(logger, "tool_call_routing", tool_name=tool_name)
    
    if tool_name == "get_customer":
        return get_customer(email=tool_input["email"])
    
    elif tool_name == "lookup_order":
        return lookup_order(
            customer_id=tool_input["customer_id"],
            order_number=tool_input["order_number"]
        )
    
    elif tool_name == "process_refund":
        return process_refund(
            customer_id=tool_input["customer_id"],
            order_id=tool_input["order_id"],
            refund_amount=tool_input["refund_amount"],
            reason=tool_input["reason"]
        )
    
    elif tool_name == "escalate_to_human":
        return escalate_to_human(
            reason=tool_input["reason"],
            conversation_summary=tool_input["conversation_summary"],
            recommended_action=tool_input["recommended_action"],
            handoff_context=handoff_context,
        )
    
    
    else:
        return {
            "success": False,
            "errorCategory": "validation",
            "description": f"Unknown tool: {tool_name}"
        }
    
