"""Live-API smoke tests for the three LEMO agents.

These tests hit the real Gemini API and are automatically skipped if
`GEMINI_API_KEY` is not configured. They're designed to be fast (each under
~15s) and to catch obvious regressions in the agent wiring — not to be a
full test suite.

Run manually from the lemo-fastapi directory:

    python -m pytest tests/test_agents_smoke.py -v

Or, if pytest is unavailable:

    python tests/test_agents_smoke.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Ensure the repo's modules are importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import pytest  # type: ignore
    HAS_PYTEST = True
except ImportError:
    pytest = None  # type: ignore
    HAS_PYTEST = False


def _has_gemini_key() -> bool:
    key = (os.getenv("GEMINI_API_KEY") or "").strip().strip('"').strip("'")
    return bool(key) and "PLACEHOLDER" not in key.upper() and len(key) > 10


if HAS_PYTEST:
    requires_gemini = pytest.mark.skipif(
        not _has_gemini_key(),
        reason="GEMINI_API_KEY is not set — skipping live smoke test",
    )
else:
    def requires_gemini(fn):
        return fn


# ---------------------------------------------------------------------------
# Intent tracker
# ---------------------------------------------------------------------------


@requires_gemini
def test_intent_tracker_classifies_compare_query():
    from agents.intent_tracker import intent_tracker_node

    state = {
        "user_query": "Can you find the same product on flipkart?",
        "session_id": "smoke-intent-1",
        "user_id": "smoke",
        "domain": "amazon.in",
        "current_page_url": "https://www.amazon.in/dp/B0ABCDEFG1",
        "chat_history": [],
    }

    result = asyncio.run(intent_tracker_node(state))
    assert result.get("scope") in {"product", "current_page"}, result
    assert result.get("next_action") in {
        "discover_and_compare",
        "scrape_current_page",
        "direct_answer",
    }, result


# ---------------------------------------------------------------------------
# Scraper agent (no live SERP required — validates routing behaviour)
# ---------------------------------------------------------------------------


def test_scraper_agent_noop_for_direct_answer():
    from agents.scraper_agent import scraper_agent_node

    state = {"next_action": "direct_answer"}
    result = asyncio.run(scraper_agent_node(state))
    assert result == {}, result


def test_scraper_agent_skips_non_scrapable_url():
    from agents.scraper_agent import scraper_agent_node

    state = {
        "next_action": "scrape_current_page",
        "current_page_url": "chrome://newtab",
    }
    result = asyncio.run(scraper_agent_node(state))
    assert result.get("current_product") is None
    assert result.get("scraped_data") == []
    assert any("non-scrapable" in err for err in result.get("errors", []))


# ---------------------------------------------------------------------------
# Lemo agent
# ---------------------------------------------------------------------------


@requires_gemini
def test_lemo_agent_synthesizes_answer():
    from agents.lemo_agent import lemo_agent_node

    state = {
        "user_query": "What do you know about this product?",
        "current_page_url": "https://example.com",
        "next_action": "scrape_current_page",
        "chat_history": [],
        "current_product": {
            "platform": "Amazon",
            "title": "Sony WH-1000XM5 Wireless Headphones",
            "price": "₹29999",
            "rating": "4.5",
            "rating_text": "4.5 out of 5 stars",
            "reviewCount": "1,234 ratings",
            "description": "Noise cancelling over-ear headphones.",
            "features": "Bluetooth 5.2 | 30h battery | Adaptive NC",
            "image": "",
            "url": "https://www.amazon.in/dp/B09XS7JWHH",
        },
    }

    result = asyncio.run(lemo_agent_node(state))
    answer = result.get("final_answer", "")
    assert isinstance(answer, str) and len(answer) > 20, answer
    assert result.get("product") is not None


# ---------------------------------------------------------------------------
# Script-mode runner
# ---------------------------------------------------------------------------


def _run_all_manual():
    """Allow `python tests/test_agents_smoke.py` without pytest."""
    print("=== LEMO agent smoke tests (script mode) ===")
    if not _has_gemini_key():
        print("GEMINI_API_KEY missing — only offline tests will run.")

    tests = [
        ("scraper_agent_noop_for_direct_answer", test_scraper_agent_noop_for_direct_answer),
        ("scraper_agent_skips_non_scrapable_url", test_scraper_agent_skips_non_scrapable_url),
    ]
    if _has_gemini_key():
        tests.extend(
            [
                ("intent_tracker_classifies_compare_query", test_intent_tracker_classifies_compare_query),
                ("lemo_agent_synthesizes_answer", test_lemo_agent_synthesizes_answer),
            ]
        )

    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  FAIL  {name}: {exc}")

    print(f"\n{len(tests) - failed}/{len(tests)} tests passed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(_run_all_manual())
