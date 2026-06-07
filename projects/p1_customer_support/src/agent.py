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
from .hooks import HookContext, hook_pre_lookup_order, hook_pre_process_refund, hook_post_process_refund
from .handoff import HandoffContext
from agent_platform.context import ContextManager

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
        self.handoff_context = HandoffContext()  # accumulates facts for human handoff
        self.context_manager = ContextManager()

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
        run = start_run( run_id=f"customer-support-turn-{self.turn}", project="p1_customer_support")
 
        iteration = 0
        max_iterations = 10
 
        # Agentic Loop
        while iteration < max_iterations:
            
            iteration += 1

            log_event(logger, "AGENT_ITERATION", turn=self.turn, iteration=iteration)
 
            # Call Claude with full conversation history
            tool = run.start_tool("claude_api_call")
 
            # Summarize if approaching context limit
            self.messages = self.context_manager.maybe_summarize(
                self.messages, self.client
            )

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
 
            run.end_tool(tool, input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens)
            self.context_manager.update_token_count(response.usage.input_tokens)

            log_event(logger, "claude_response", stop_reason=response.stop_reason, turn=self.turn, iteration=iteration)
 
            # Claude is done — return the response
            if response.stop_reason == "end_turn":
                
                assistant_message = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        assistant_message += block.text
 
                # Append to history so future turns have full context
                self.messages.append({"role": "assistant", "content": assistant_message})
 
                log_event(logger, "turn_complete", turn=self.turn, iterations=iteration, final_message_preview=assistant_message[:50])
 
                run.finish()
                return assistant_message
 
            # Claude wants to call tools — build assistant content block
            elif response.stop_reason == "tool_use":
                
                assistant_content = []
                for block in response.content:
                    if hasattr(block, "text"):
                        assistant_content.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        assistant_content.append(block)
 
                self.messages.append({"role": "assistant", "content": assistant_content})
 
                # Claude may have requested multiple tool calls in one response — handle them in order
                tool_results = []
                for block in response.content:

                    if block.type == "tool_use":
            
                        log_event(logger, "tool_execution", tool_name=block.name,turn=self.turn, iteration=iteration)
                        hook_error = None
 
                        # Pre Hooks - these run before the tool is executed, they can block the tool execution if prerequisites aren't met, or if something in # the tool input looks wrong. They return an error object with details if they want to block, or None if it's all good.
                        if block.name == "lookup_order":
                            hook_error = hook_pre_lookup_order(block.input, self.hook_context)
 
                        elif block.name == "process_refund":
                            hook_error = hook_pre_process_refund(block.input, self.hook_context)

                        # Hook blocked — return error to Claude so it can self-correct  
                        if hook_error:
 
                            self.handoff_context.set_attempted_action(action=block.name, block_reason=hook_error.get("block_reason", "unknown"))

                            log_event(logger, "hook_blocked_tool_call", tool_name=block.name, reason=hook_error.get("description"))
                            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(hook_error), "is_error": True})

                            # There is an error in the tool call that prevents us from executing the tool in the steps below without executing this one. 
                            # Claude should respond to the error and try again.
                            continue

                        # We got here so no Pre Tool Block Occured so Execute the tool
                        tool_result = handle_tool_call(block.name, block.input,
                                                       handoff_context=self.handoff_context.to_dict() if block.name == "escalate_to_human" else None)
                        
                        # Check PostToolUse hooks
                        if block.name == "process_refund":
                            tool_result = hook_post_process_refund( tool_result, block.input, self.hook_context)
                            if not tool_result.get("success"):
                                self.handoff_context.set_attempted_action(action="process_refund", block_reason="amount_over_500")
 
                        # The tool call was succcessful, this only happens with get_customer and lookup_order, so we can mark them as verified in our context for hooks to check in future tool calls.
                        if tool_result.get("success"):
    
                            self.handoff_context.reset_attempted_action()  # clear any previous block
                            
                            # The get_customer was found to be successful, we can mark the customer_id as verified in our context so that future tool calls # # # that require customer verification can check this.
                            if block.name == "get_customer":
                                self.hook_context.set_customer_verified(tool_result["customer_id"])
                                self.handoff_context.set_customer(
                                    customer_id=tool_result["customer_id"],
                                    email=block.input.get("email", ""),
                                    name=tool_result.get("full_name", ""),
                                    tier=tool_result.get("customer_tier", "standard")
                                )

                            # The lookup_order was found to be successful, we can mark the order_id as verified in our context so that future tool calls that # # require order verification can check this.
                            elif block.name == "lookup_order":
                                self.hook_context.set_order_verified(tool_result["order_id"])
                                self.handoff_context.set_order(
                                    order_id=tool_result["order_id"],
                                    order_number=block.input.get("order_number", ""),
                                    amount=tool_result.get("total_amount", 0)
                                )
                            elif block.name == "process_refund" and tool_result.get("confirmation_number"):
                                self.handoff_context.set_refund_executed(
                                    confirmation_number=tool_result["confirmation_number"],
                                    amount=block.input.get("refund_amount", 0))


                        log_event(logger, "tool_result", tool_name=block.name, success=tool_result.get("success", False)
                        )
 
                        tool_results.append({ "type": "tool_result", "tool_use_id": block.id, "content": str(tool_result)})
 
                # Append the user message to messages so Claude has the full context in the next loop, including the tool results we just executed.
                self.messages.append({"role": "user", "content": tool_results})
 
            else:
                log_event(logger, "unexpected_stop_reason", stop_reason=response.stop_reason)
                break
 
        # It looped too many times without stopping — something went wrong. Log and return a generic error message.
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
        