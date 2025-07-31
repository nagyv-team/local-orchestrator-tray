Your job is to fix all the failing tests. Follow this process step-by-step:

1. Start a new generic sub-agent to troubleshoot the test failures:
    1. Run the tests
    2. Using the TodoWrite tool, create a todo for every single failure separately to analyse the failure 1-by-1 using the root-cause-detective.
    3. Process the first unresolved todo item. Note that the agent is only analysing the failure and related codebase. It is not allowed to resolve the failure!
    4. Iterate from (3)
2. Query the memory-troubleshooter for analysed test failures and using the TodoWrite tool create a new task to fix them. Fixing each should follow the following sub-process:
    1. Start a new generic sub-agent to manage fixing a single test failure
    2. This agent should first run the test in focus, and check whether it fails or not
    3. If the test failed, then study the related entry in memory-troubleshooter
    4. Based on the findings from the previous task, ask the tdd-implementor OR the tdd-test-writer agent to fix the issue
    5. Run the test in focus, and check that it is fixed indeed.
    6. If the test still fails, iterate from (3)
    7. Remove the fixed test from memory-troubleshooter
3. Check the tests again. Iterate from (1) if there are any test failures.