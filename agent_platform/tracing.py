
"""
agent_platform/tracing.py
Token accounting and latency tracking per tool call and agent run.

Answers:
- How many tokens did this agent run use?
- How long did each tool call take?
- What did this run cost in dollars?

Usage pattern:
    run = start_run('session-001', 'p1_customer_support')    
    tool = run.start_tool('get_customer')
    
    # ... tool executes ...
    run.end_tool(tool, input_tokens=150, output_tokens=80)
    
    run.finish()  # logs complete summary to JSON

"""

import time # built into Python, gives us timestamps in seconds
from dataclasses import dataclass, field #  needed when a default value is a mutable object like a list
from typing import Optional # a type hint meaning "this can be this type OR None"
from agent_platform.logging import get_logger, log_event #  importing our own module we just built

logger = get_logger(__name__)

# Tracks a single tool call from start to finish.
# One ToolTrace is created per tool call and stored inside RunTrace.
# latency_ms and cost_usd are computed properties — they calculate
# fresh every time you access them, they are not stored fields.

@dataclass
class ToolTrace:
    tool_name: str
    started_at: float
    ended_at: Optional[float] = None
    input_tokens: int = 0
    output_tokens: int = 0
    error: Optional[str] = None

    # @property means access this like an attribute, not a method.
    # trace.latency_ms  ← correct, no parentheses
    # trace.latency_ms() ← wrong, will raise TypeError
    # Returns None if the tool hasn't finished yet (ended_at is still None)
    @property
    def latency_ms(self) -> Optional[float]:
        if self.ended_at:
            return round((self.ended_at - self.started_at) * 1000, 2)
        return None


    # Haiku 4.5 pricing as of June 2026:
    # Input:  $1.00 per million tokens
    # Output: $5.00 per million tokens  
    # Update these rates if Anthropic changes pricing.
    # 1_000_000 is Python's readable way of writing 1000000 — same value.
    @property
    def cost_usd(self) -> float:
        """Approximate cost using Haiku 4.5 rates."""
        input_cost = (self.input_tokens / 1_000_000) * 1.00
        output_cost = (self.output_tokens / 1_000_000) * 5.00
        return round(input_cost + output_cost, 6)

@dataclass

# Tracks an entire agent session from first message to final response.
# Holds a list of ToolTrace objects, one per tool call.
# 
# field(default_factory=time.time) is required instead of = time.time()
# because dataclasses evaluate default values once at class definition.
# default_factory calls time.time() fresh each time a new RunTrace is created.
#
# field(default_factory=list) is required for the same reason —
# without it, all RunTrace instances would share the same list object.
class RunTrace:
    run_id: str
    project: str
    started_at: float = field(default_factory=time.time)
    ended_at: Optional[float] = None
    tool_traces: list[ToolTrace] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    # Call this immediately before executing a tool.
    # Returns the ToolTrace object — hold onto it, you need it for end_tool().
    # The ToolTrace is automatically added to self.tool_traces.
    def start_tool(self, tool_name: str) -> ToolTrace:
        trace = ToolTrace(
            tool_name=tool_name,
            started_at=time.time(),
        )
        self.tool_traces.append(trace)
        return trace

    # Call this immediately after a tool finishes executing.
    # Pass the ToolTrace returned by start_tool().
    # input_tokens and output_tokens come from the API response:
    #     response.usage.input_tokens
    #     response.usage.output_tokens
    # Pass error= if the tool raised an exception, otherwise leave as None.
    def end_tool(
        self,
        trace: ToolTrace,
        input_tokens: int = 0,
        output_tokens: int = 0,
        error: Optional[str] = None,
    ) -> None:
        trace.ended_at = time.time()
        trace.input_tokens = input_tokens
        trace.output_tokens = output_tokens
        trace.error = error
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

    def finish(self) -> None:
        self.ended_at = time.time()
        total_cost = sum(t.cost_usd for t in self.tool_traces)
        log_event(
            logger,
            "run_complete",
            run_id=self.run_id,
            project=self.project,
            duration_ms=round(
                (self.ended_at - self.started_at) * 1000, 2
            ),
            total_input_tokens=self.total_input_tokens,
            total_output_tokens=self.total_output_tokens,
            estimated_cost_usd=total_cost,
            tool_count=len(self.tool_traces),
        )


# Convenience function for starting a new run
def start_run(run_id: str, project: str) -> RunTrace:
    return RunTrace(run_id=run_id, project=project)