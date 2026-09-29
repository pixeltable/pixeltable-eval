"""
Grader for tool_calling eval.

The agent loop is declarative: tools via pxt.tools()/invoke_tools and a
computed-column chain on the conversation table, not a while-loop driver.
"""

POSITIVE_PATTERNS = [
    (r"import pixeltable|from pixeltable", "uses pixeltable"),
    (r"pxt\.tools|invoke_tools|tool_calls?", "declares/invokes tools via pixeltable"),
    (r"pxt\.create_table|TableModel|model_base", "creates the conversation table"),
    (r"anthropic|chat_completions|messages\.create|messages=", "calls an LLM for tool selection"),
    (r"def\s+\w+\s*\(.*\)\s*->|def\s+get_weather|def\s+search", "defines tool functions"),
    (r"\.insert\s*\(", "drives the agent by inserting a user message"),
    (r"add_computed_column|=\s*.*messages|@pxt\.udf", "agent steps are computed columns"),
]

NEGATIVE_PATTERNS = [
    (r"while\s+(not\s+\w+|True)\s*:", "hand-rolled agent loop (insert a row instead)"),
    (r"AgentExecutor|from langchain|langgraph|from llama_index",
     "framework agent machinery (use pxt.tools)"),
    (r"for\s+\w+\s+in\s+.*:\s*\n\s*.*(?:anthropic|openai|client\.|messages\.create)",
     "imperative loop calling the model"),
    (r"import pandas|from pandas", "uses pandas as working store"),
]
