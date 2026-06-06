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
    python -m projects.p1_customer_support.src.agent
"""
 
import anthropic
from agent_platform.config import config
from agent_platform.logging import get_logger, log_event
from agent_platform.tracing import start_run
from agent_platform.cache import add_cache_control, add_cache_control_to_messages
from agent_platform.retry import with_retry
from .tools import handle_tool_call
from .hooks import HookContext, hook_pre_lookup_order, hook_pre_process_refund, hook_post_process_refund
 
 
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
 
 
class AgentSession:
    """
    A persistent customer support session.
 
    Holds state across multiple customer messages:
    - messages: full conversation history sent to Claude each turn
    - hook_context: tracks what has been verified (customer, order)
      so hooks don't reset between turns
 
    Usage:
        session = AgentSession()
        session.send("I want a refund")
        session.send("My email is john@example.com")
        session.send("Order #10001")
    """
 
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self.messages = []
        self.hook_context = HookContext()   # persists for the whole session
        self.turn = 0
 
        log_event(logger, "session_started")
 
    def send(self, customer_message: str) -> str:
        """
        Send a customer message and run the agentic loop until Claude responds.
 
        The loop:
        1. Append customer message to history
        2. Call Claude with full history
        3. If stop_reason == tool_use → execute tools, append results, loop
        4. If stop_reason == end_turn → return Claude's response
        """
        self.turn += 1
        log_event(logger, "turn_started", turn=self.turn, message_preview=customer_message[:50])
 
        # Append customer message to persistent history
        self.messages.append({"role": "user", "content": customer_message})
 
        # Start tracing this turn
        run = start_run(
            run_id=f"customer-support-turn-{self.turn}",
            project="p1_customer_support"
        )
 
        iteration = 0
        max_iterations = 10
 
        while iteration < max_iterations:
            iteration += 1
            log_event(logger, "agent_iteration", turn=self.turn, iteration=iteration)
 
            # Call Claude with full conversation history
            tool = run.start_tool("claude_api_call")
 
            response = with_retry(
                func=lambda: self.client.messages.create(
                    model=config.dev_model,
                    max_tokens=1024,
                    system=add_cache_control(SYSTEM_PROMPT),
                    tools=TOOLS,
                    messages=add_cache_control_to_messages(self.messages, cache_last_n=1)
                ),
                operation_name="agent_api_call"
            )
 
            run.end_tool(tool,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens
            )
 
            log_event(logger, "claude_response",
                stop_reason=response.stop_reason,
                turn=self.turn,
                iteration=iteration
            )
 
            # Check stop_reason — this drives the loop, not Claude's words
            if response.stop_reason == "end_turn":
                # Claude is done — extract response text
                assistant_message = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        assistant_message += block.text
 
                # Append to history so future turns have full context
                self.messages.append({"role": "assistant", "content": assistant_message})
 
                log_event(logger, "turn_complete",
                    turn=self.turn,
                    iterations=iteration,
                    final_message_preview=assistant_message[:50]
                )
 
                run.finish()
                return assistant_message
 
            elif response.stop_reason == "tool_use":
                # Claude wants to call tools — build assistant content block
                assistant_content = []
                for block in response.content:
                    if hasattr(block, "text"):
                        assistant_content.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        assistant_content.append(block)
 
                self.messages.append({"role": "assistant", "content": assistant_content})
 
                # Execute each tool Claude requested
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        log_event(logger, "tool_execution",
                            tool_name=block.name,
                            turn=self.turn,
                            iteration=iteration
                        )
 
                        # Check PreToolUse hooks
                        hook_error = None
 
                        if block.name == "lookup_order":
                            hook_error = hook_pre_lookup_order(block.input, self.hook_context)
 
                        elif block.name == "process_refund":
                            hook_error = hook_pre_process_refund(block.input, self.hook_context)
 
                        if hook_error:
                            # Hook blocked — return error to Claude so it can self-correct
                            log_event(logger, "hook_blocked_tool_call",
                                tool_name=block.name,
                                reason=hook_error.get("description")
                            )
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": str(hook_error),
                                "is_error": True
                            })
                            continue
 
                        # Execute the tool
                        tool_result = handle_tool_call(block.name, block.input)
 
                        # Check PostToolUse hooks
                        if block.name == "process_refund":
                            tool_result = hook_post_process_refund(
                                tool_result, block.input, self.hook_context
                            )
 
                        # Update hook context on success
                        if tool_result.get("success"):
                            if block.name == "get_customer":
                                self.hook_context.set_customer_verified(tool_result["customer_id"])
                            elif block.name == "lookup_order":
                                self.hook_context.set_order_verified(tool_result["order_id"])
 
                        log_event(logger, "tool_result",
                            tool_name=block.name,
                            success=tool_result.get("success", False)
                        )
 
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(tool_result)
                        })
 
                # Append tool results to history
                self.messages.append({"role": "user", "content": tool_results})
 
            else:
                log_event(logger, "unexpected_stop_reason",
                    stop_reason=response.stop_reason
                )
                break
 
        # Max iterations reached — escalate
        log_event(logger, "agent_max_iterations", max_iterations=max_iterations)
        run.finish()
        return "I'm having trouble processing your request. Connecting you with a human agent."
 
 
if __name__ == "__main__":
    session = AgentSession()
    print("AcmeCorp Customer Support")
    print("Type 'quit' to exit\n")
 
    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() == "quit":
            print("Session ended.")
            break
 
        response = session.send(user_input)
        print(f"\nAgent: {response}\n")