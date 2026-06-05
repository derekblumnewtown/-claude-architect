"""
first_api_call.py
Our first real API call to Claude using the agent_platform.

This brings together every module we built in pre-work:
- config.py    → provides the API key and model
- logging.py   → logs what happens
- tracing.py   → tracks tokens and cost
- cache.py     → caches the system prompt
- retry.py     → handles any failures

Run with: python first_api_call.py
"""

import anthropic
from agent_platform.config import config
from agent_platform.logging import get_logger, log_event
from agent_platform.tracing import start_run
from agent_platform.cache import add_cache_control
from agent_platform.retry import with_retry, RetryError

# Get a logger for this script
logger = get_logger(__name__)

def main():

    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    run = start_run( run_id="first-call-001", project="pre-work") # Start tracking this run

    log_event(logger, "first_api_call_starting", model=config.dev_model, environment=config.environment)

    # Our system prompt — cached so repeated calls cost 90% less
    system_prompt = """
        You are a helpful assistant being tested as part of a Claude Certified Architect learning program.

        Respond concisely and clearly. Always mention how many words are in your response.
    """

    # Start tracing the API call
    tool = run.start_tool("messages_create")

    try:
        # Make the real API call — wrapped in retry logic
        response = with_retry(

            func=lambda: client.messages.create(
                model=config.dev_model,
                max_tokens=200,

                # Cache the system prompt — 90% cheaper after first call
                system=add_cache_control(system_prompt),

                # Our message to Claude
                messages=[
                    {
                        "role": "user",
                        "content": "Hello Claude! This is my first API call. What can you tell me about the Anthropic API in 2-3 sentences?"
                    }
                ]
            ),
            operation_name="first_api_call"
        )

        # Record the real token counts from the API response
        run.end_tool(tool, input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens)

        # Log what Claude said
        log_event(logger, "first_api_call_success",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            stop_reason=response.stop_reason
        )

        # Print Claude's response to the terminal
        print("\n" + "="*50)
        print("CLAUDE SAYS:")
        print("="*50)
        print(response.content[0].text)
        print("="*50 + "\n")

        # Finish the run — logs total cost and duration
        run.finish()

    except RetryError as e:
        log_event(logger, "first_api_call_failed",
            error_category=e.error_category.value,
            attempts_made=e.attempts_made,
            description=e.description
        )
        print(f"API call failed: {e.description}")

if __name__ == "__main__":
    main()