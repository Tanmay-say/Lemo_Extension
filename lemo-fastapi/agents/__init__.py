"""LEMO multi-agent system (LangGraph).

Three cooperating nodes:

    intent_tracker  -> gemini-3.1-flash, context-aware scope + routing
    scraper_agent   -> ScrapingBee (page + Google SERP) + rapidfuzz filter
    lemo_agent      -> gemini-3.1-pro, final synthesized answer

The compiled StateGraph is exposed via `agents.graph.compiled_graph`.
"""

from agents.state import LemoState  # noqa: F401
