"""
projects/p1_customer_support/src/agent.py
The agentic loop for the customer support agent.

This is where everything comes together:
- Takes customer messages
- Sends to Claude
- Executes tools Claude requests
- Handles hooks
- Stops when Claude is done

Run with:
    python projects/p1_customer_support/src/agent.py
"""

import anthropic
from agent_platform.config import config
from agent_platform.logging import get_logger, log_event
from agent_platform.tracing import start_run
from agent_platform.cache import add_cache_control, add_cache_control_to_messages
from agent_platform.retry import with_retry
from .tools import handle_tool_call

logger = get_logger(__name__)


# System prompt — tells Claude what to do
SYSTEM_PROMPT = """
You are a helpful customer support agent for AcmeCorp.

Your job is to help customers with refund requests.

You have access to four tools:
1. get_customer - Look up a customer by email. ALWAYS call this first.
2. lookup_order - Find an order for a verified customer
3. process_refund - Process a refund for a verified order
4. escalate_to_human - Hand off to a human agent

RULES:
- Always verify the customer first with get_customer
- Always look up the order before processing a refund
- Never process a refund without verifying both customer and order
- If the customer asks for a human, escalate immediately
- If anything fails, escalate to a human
- Be friendly and clear in all responses
"""


# Tool definitions for Claude
TOOLS = [
    {
        "name": "get_customer",
        "description": "Look up a customer by email address. Must call this first before any other tool.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {
                    "type": "string",
                    "description": "Customer's email address"
                }
            },
            "required": ["email"]
        }
    },
    {
        "name": "lookup_order",
        "description": "Find an order for a verified customer. Requires customer_id from get_customer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "Verified customer ID from get_customer"
                },
                "order_number": {
                    "type": "string",
                    "description": "Order number (e.g. #10001)"
                }
            },
            "required": ["customer_id", "order_number"]
        }
    },
    {
        "name": "process_refund",
        "description": "Process a refund. Requires verified customer_id and order_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "string",
                    "description": "Verified customer ID"
                },
                "order_id": {
                    "type": "string",
                    "description": "Verified order ID"
                },
                "refund_amount": {
                    "type": "number",
                    "description": "Amount to refund in dollars"
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for refund"
                }
            },
            "required": ["customer_id", "order_id", "refund_amount", "reason"]
        }
    },
    {
        "name": "escalate_to_human",
        "description": "Hand off to a human agent",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why we are escalating"
                },
                "conversation_summary": {
                    "type": "string",
                    "description": "Summary of what happened"
                },
                "recommended_action": {
                    "type": "string",
                    "description": "What the human should do"
                },
                "customer_id": {
                    "type": "string",
                    "description": "Customer ID if known"
                },
                "order_id": {
                    "type": "string",
                    "description": "Order ID if known"
                }
            },
            "required": ["reason", "conversation_summary", "recommended_action"]
        }
    }
]


def run_agent(customer_message: str):
    """
    Run the agent loop for a customer message.
    
    This is the main agentic loop:
    1. Send customer message to Claude
    2. Claude responds — check stop_reason
    3. If stop_reason == "tool_use" → execute tool, send result back, loop
    4. If stop_reason == "end_turn" → done, return response
    """
    log_event(logger, "agent_loop_started", message_preview=customer_message[:50])
    
    # Create client
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    
    # Start tracing this run
    run = start_run(run_id="customer-support-001", project="p1_customer_support")
    
    # Messages list — will grow as we loop
    messages = [
        {"role": "user", "content": customer_message}
    ]
    
    iteration = 0
    max_iterations = 10
    
    while iteration < max_iterations:
        iteration += 1
        log_event(logger, "agent_iteration", iteration=iteration)
        
        # Call Claude
        tool = run.start_tool("claude_api_call")
        
        response = with_retry(
            func=lambda: client.messages.create(
                model=config.dev_model,
                max_tokens=1024,
                system=add_cache_control(SYSTEM_PROMPT),
                tools=TOOLS,
                messages=add_cache_control_to_messages(messages, cache_last_n=1)
            ),
            operation_name="agent_api_call"
        )
        
        run.end_tool(tool,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens
        )
        
        log_event(logger, "claude_response",
            stop_reason=response.stop_reason,
            iteration=iteration
        )
        
        # Check stop_reason
        if response.stop_reason == "end_turn":
            # Claude is done — extract and return response
            assistant_message = ""
            for block in response.content:
                if hasattr(block, "text"):
                    assistant_message += block.text
            
            log_event(logger, "agent_loop_complete",
                iterations=iteration,
                final_message_preview=assistant_message[:50]
            )
            
            print("\n" + "="*50)
            print("AGENT RESPONSE")
            print("="*50)
            print(assistant_message)
            print("="*50 + "\n")
            
            run.finish()
            return assistant_message
        
        elif response.stop_reason == "tool_use":
            # Claude wants to call a tool
            # Add Claude's response to messages
            messages.append({"role": "assistant", "content": response.content})
            
            # Execute the tool
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    log_event(logger, "tool_execution",
                        tool_name=block.name,
                        iteration=iteration
                    )
                    
                    # Call the tool
                    tool_result = handle_tool_call(block.name, block.input)
                    
                    log_event(logger, "tool_result",
                        tool_name=block.name,
                        success=tool_result.get("success", False)
                    )
                    
                    # Collect result
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(tool_result)
                    })
            
            # Add tool results to messages
            messages.append({"role": "user", "content": tool_results})
        
        else:
            # Unexpected stop_reason
            log_event(logger, "unexpected_stop_reason",
                stop_reason=response.stop_reason
            )
            break
    
    # Max iterations reached
    log_event(logger, "agent_max_iterations",
        max_iterations=max_iterations
    )
    
    run.finish()
    return "I'm having trouble processing your request. Connecting you with a human agent."


if __name__ == "__main__":
    # Test the agent with a sample customer message
    customer_message = "Hi, I want to get a refund for my order. My email is john.smith@email.com and the order number is #10001."
    
    run_agent(customer_message)