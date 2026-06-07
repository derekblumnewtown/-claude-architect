if 1==2:
    import sqlite3

    conn = sqlite3.connect('projects/p1_customer_support/data/support.db')
    conn.execute("UPDATE orders SET already_refunded=0 WHERE order_number='#10003'")
    conn.execute("DELETE FROM escalations")
    conn.commit()
    conn.close()
    print('reset')
    exit()
if 1==1:
    import sqlite3
    conn = sqlite3.connect('projects/p1_customer_support/data/support.db')
    conn.row_factory = sqlite3.Row
    r = conn.execute('SELECT * FROM escalations ORDER BY created_at DESC LIMIT 1').fetchone()
    if r is not None:
        print(dict(r)['conversation_summary'])
    conn.close()

if 1==2:
    from projects.p1_customer_support.src.tools import handle_tool_call
    print('tools imported successfully')

if 1==2:

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

if 1==2:
    from agent_platform.cache import add_cache_control; 

    result = add_cache_control('You are a helpful assistant'); 
    print(result)

if 1==2:
    from agent_platform.cache import add_cache_control_to_messages
    messages = [{'role': 'user', 'content': 'My order is wrong'}, {'role': 'assistant', 'content': 'I can help with that'}, {'role': 'user', 'content': 'Order 12345'}]
    result = add_cache_control_to_messages(messages, cache_last_n=2)
    print(result)
    """
    [{'role': 'user', 'content': 'My order is wrong'}, 
     {'role': 'assistant', 'content': [{'type': 'text', 'text': 'I can help with that', 'cache_control': {'type': 'ephemeral'}}]}, 
     {'role': 'user', 'content': [{'type': 'text', 'text': 'Order 12345', 'cache_control': {'type': 'ephemeral'}}]}]
    """

if 1==2:
    from agent_platform.retry import with_retry, RetryConfig, ErrorCategory, classify_error

    # Test error classification
    class FakeTimeout(Exception):
        pass

    error = FakeTimeout('connection timeout')
    category = classify_error(error)
    print('Error category:', category.value)

    # Test delay calculation
    from agent_platform.retry import calculate_delay
    config = RetryConfig()
    print('Attempt 1 delay:', round(calculate_delay(1, config), 2))
    print('Attempt 2 delay:', round(calculate_delay(2, config), 2))
    print('Attempt 3 delay:', round(calculate_delay(3, config), 2))    

