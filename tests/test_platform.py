"""
tests/test_platform.py
Tests for the agent_platform foundation modules.

Run with: pytest tests/
Each test verifies one specific behavior of our platform modules.
A passing test means that module is working correctly.
"""

import pytest
import time
from agent_platform.config import Config
from agent_platform.tracing import RunTrace, ToolTrace, start_run


# ─── CONFIG TESTS ───────────────────────────────────────────────────────────


def test_config_loads():
    """
    Config should load from .env without raising an error.
    If ANTHROPIC_API_KEY is missing this test will fail —
    that means your .env file is not set up correctly.
    """
    
    config = Config.from_env() # Load config from environment
    assert config.anthropic_api_key # Verify the API key loaded — we don't print it, just check it exists
    assert config.default_model # Verify default model is set
    assert config.environment == "development" # Verify environment defaults to development


def test_config_default_model():
    """
    When DEFAULT_MODEL is not set in .env,
    config should fall back to claude-haiku-4-5.
    """
    config = Config.from_env()

    # Haiku is our default development model to keep costs low
    assert config.default_model == "claude-haiku-4-5"


# ─── TRACING TESTS ──────────────────────────────────────────────────────────

def test_run_trace_records_tool():
    """
    When we start and end a tool call,
    RunTrace should record it correctly.
    """
    # Create a new run for project 1
    run = start_run(run_id="test-001", project="p1_customer_support")

    # Start a tool call
    tool = run.start_tool("get_customer")

    # Simulate the tool doing some work
    time.sleep(0.01)

    # End the tool call with fake token counts
    # In real usage these come from response.usage.input_tokens
    run.end_tool(tool, input_tokens=100, output_tokens=50)

    # Verify one tool was recorded
    assert len(run.tool_traces) == 1

    # Verify the tool name was recorded correctly
    assert run.tool_traces[0].tool_name == "get_customer"

    # Verify latency was measured — should be around 10ms
    assert run.tool_traces[0].latency_ms > 0

    # Verify tokens were recorded
    assert run.total_input_tokens == 100
    assert run.total_output_tokens == 50


def test_run_trace_records_multiple_tools():
    """
    A real agent run calls multiple tools.
    RunTrace should record all of them and sum the tokens correctly.
    """
    # Create a new run
    run = start_run(run_id="test-002", project="p1_customer_support")

    # First tool call — get customer info
    tool1 = run.start_tool("get_customer")
    run.end_tool(tool1, input_tokens=100, output_tokens=50)

    # Second tool call — look up their order
    tool2 = run.start_tool("lookup_order")
    run.end_tool(tool2, input_tokens=200, output_tokens=80)

    # Third tool call — process the refund
    tool3 = run.start_tool("process_refund")
    run.end_tool(tool3, input_tokens=150, output_tokens=60)

    # Verify all three tools were recorded
    assert len(run.tool_traces) == 3

    # Verify tokens are summed correctly across all tool calls
    assert run.total_input_tokens == 450   # 100 + 200 + 150
    assert run.total_output_tokens == 190  # 50 + 80 + 60


def test_tool_trace_cost_calculation():
    """
    Verify the cost math is correct using Haiku 4.5 rates:
    Input:  $1.00 per million tokens
    Output: $5.00 per million tokens
    """
    # Create a tool trace manually with known token counts
    trace = ToolTrace(
        tool_name="test_tool",
        started_at=time.time()
    )
    trace.ended_at = time.time()

    # Use exactly 1 million of each to make the math easy to verify
    trace.input_tokens = 1_000_000
    trace.output_tokens = 1_000_000

    # Expected: $1.00 input + $5.00 output = $6.00 total
    # pytest.approx handles floating point rounding
    assert trace.cost_usd == pytest.approx(6.0, rel=0.01)


def test_tool_trace_latency():
    """
    Latency should be None before a tool finishes,
    and a positive number after it finishes.
    """
    # Create a tool trace — ended_at is None at this point
    trace = ToolTrace(
        tool_name="test_tool",
        started_at=time.time()
    )

    # Before finishing — latency should be None
    assert trace.latency_ms is None

    # Simulate tool finishing after 10ms
    time.sleep(0.01)
    trace.ended_at = time.time()

    # After finishing — latency should be a positive number
    assert trace.latency_ms > 0
