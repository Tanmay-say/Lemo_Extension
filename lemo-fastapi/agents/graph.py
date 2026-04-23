r"""Pipeline wiring for the LEMO multi-agent flow.

Primary mode uses LangGraph when installed.
Fallback mode runs the same nodes sequentially so `/query` still works when the
optional `langgraph` package is unavailable in the active interpreter.
"""

from __future__ import annotations

import importlib.util
import logging
from functools import lru_cache

from agents.intent_tracker import intent_tracker_node, route_after_intent
from agents.lemo_agent import lemo_agent_node
from agents.scraper_agent import scraper_agent_node
from agents.state import LemoState

logger = logging.getLogger(__name__)


def langgraph_available() -> bool:
    return importlib.util.find_spec("langgraph.graph") is not None


def pipeline_backend_name() -> str:
    return "langgraph" if langgraph_available() else "sequential-fallback"


@lru_cache(maxsize=1)
def _compile():
    from langgraph.graph import END, StateGraph  # type: ignore

    graph = StateGraph(LemoState)
    graph.add_node("intent", intent_tracker_node)
    graph.add_node("scraper", scraper_agent_node)
    graph.add_node("lemo", lemo_agent_node)

    graph.set_entry_point("intent")
    graph.add_conditional_edges(
        "intent",
        route_after_intent,
        {
            "needs_scrape": "scraper",
            "direct_answer": "lemo",
        },
    )
    graph.add_edge("scraper", "lemo")
    graph.add_edge("lemo", END)

    compiled = graph.compile()
    logger.info("[graph] LEMO StateGraph compiled: intent -> (scraper?) -> lemo")
    return compiled


def get_graph():
    """Return the compiled graph when LangGraph is installed."""
    return _compile()


async def _run_without_langgraph(initial_state: dict) -> dict:
    logger.warning("[graph] `langgraph` not installed; using sequential fallback pipeline")

    state = dict(initial_state)

    update = await intent_tracker_node(state) or {}
    state.update(update)

    if route_after_intent(state) == "needs_scrape":
        update = await scraper_agent_node(state) or {}
        state.update(update)

    update = await lemo_agent_node(state) or {}
    state.update(update)

    return state


async def run_lemo_pipeline(initial_state: dict) -> dict:
    """Run the multi-agent pipeline and return the final merged state."""
    if not langgraph_available():
        return await _run_without_langgraph(initial_state)

    try:
        graph = get_graph()
        result = await graph.ainvoke(initial_state)
        return dict(result) if result else {}
    except ModuleNotFoundError as exc:
        if "langgraph" not in str(exc).lower():
            raise
        logger.warning("[graph] LangGraph import failed at runtime (%s); falling back", exc)
        return await _run_without_langgraph(initial_state)
