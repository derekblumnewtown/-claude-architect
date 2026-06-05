from agent_platform.tracing import start_run
import time

# Pass in RunId and Project
run = start_run('test-001', 'test')

#Pass in Tool Name
tool = run.start_tool('get_customer')
time.sleep(0.01)

#Pass in the tool that started and the tokens, we will get those tokens from the API
run.end_tool(tool, input_tokens=100, output_tokens=50)
run.finish()