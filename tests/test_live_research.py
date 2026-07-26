from agentic.live_research import (
    deterministic_research_answer,
    requires_live_research,
    research_context,
)


def test_live_intent_detects_prices_news_business_and_technology():
    for query in (
        "What is the live price of gold?",
        "What happened in technology news today?",
        "Explain current business and market news",
    ):
        assert requires_live_research(query) is True
    assert requires_live_research("Summarize my saved project") is False


def test_grounded_market_answer_has_timestamp_source_and_warning():
    result = {
        "query": "live gold price",
        "collected_at": "2026-07-26T05:00:00+00:00",
        "quotes": [
            {
                "name": "Gold futures",
                "symbol": "GC=F",
                "price": 2412.5,
                "currency": "USD",
                "unit": "troy ounce",
                "change": 12.5,
                "change_percent": 0.52,
                "market_state": "REGULAR",
                "observed_at": "2026-07-26T04:59:00+00:00",
                "source": "Yahoo Finance chart API",
                "url": "https://finance.yahoo.com/quote/GC%3DF",
            }
        ],
        "news": [],
        "errors": [],
        "is_live": True,
    }

    context = research_context(result)
    answer = deterministic_research_answer(result)
    assert "2412.5 USD per troy ounce" in answer
    assert "2026-07-26T05:00:00+00:00" in answer
    assert "[1]" in answer
    assert "may be delayed" in answer
    assert "Use only this evidence" in context


def test_no_live_evidence_never_guesses():
    result = {
        "query": "gold price",
        "collected_at": "2026-07-26T05:00:00+00:00",
        "quotes": [],
        "news": [],
        "errors": ["Gold futures quote unavailable: TimeoutError"],
        "is_live": False,
    }
    answer = deterministic_research_answer(result)
    assert "will not guess" in answer
    assert "TimeoutError" in answer
