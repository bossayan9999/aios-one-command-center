from __future__ import annotations

import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any

LIVE_TERMS = {
    "live",
    "latest",
    "current",
    "today",
    "right now",
    "breaking",
    "news",
    "market",
    "price",
    "technology",
    "business",
    "stock",
    "gold",
    "bitcoin",
    "crypto",
    "search",
    "research",
    "web",
    "online",
    "look up",
}

MARKETS = {
    "gold": ("GC=F", "Gold futures", "USD", "troy ounce"),
    "silver": ("SI=F", "Silver futures", "USD", "troy ounce"),
    "bitcoin": ("BTC-USD", "Bitcoin", "USD", "BTC"),
    "ethereum": ("ETH-USD", "Ethereum", "USD", "ETH"),
    "oil": ("CL=F", "WTI crude oil", "USD", "barrel"),
    "s&p": ("^GSPC", "S&P 500", "points", "index"),
    "nasdaq": ("^IXIC", "NASDAQ Composite", "points", "index"),
}


def requires_live_research(query: str) -> bool:
    lowered = query.casefold()
    return any(term in lowered for term in LIVE_TERMS)


def _market_matches(query: str) -> list[tuple[str, str, str, str]]:
    lowered = query.casefold()
    return [metadata for term, metadata in MARKETS.items() if term in lowered]


def fetch_market_quote(
    symbol: str, name: str, currency: str, unit: str, timeout: float = 8
) -> dict[str, Any]:
    encoded = urllib.parse.quote(symbol, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?interval=1m&range=1d"
    request = urllib.request.Request(url, headers={"User-Agent": "AIOS-LiveResearch/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    result = payload["chart"]["result"][0]
    meta = result["meta"]
    price = meta.get("regularMarketPrice")
    previous = meta.get("chartPreviousClose") or meta.get("previousClose")
    change = None if price is None or not previous else price - previous
    change_percent = None if change is None else change / previous * 100
    market_time = meta.get("regularMarketTime")
    observed_at = (
        datetime.fromtimestamp(int(market_time), tz=UTC).isoformat()
        if market_time
        else datetime.now(UTC).isoformat()
    )
    return {
        "kind": "market_quote",
        "symbol": symbol,
        "name": name,
        "price": price,
        "currency": meta.get("currency") or currency,
        "unit": unit,
        "change": change,
        "change_percent": change_percent,
        "market_state": meta.get("marketState", "unknown"),
        "observed_at": observed_at,
        "source": "Yahoo Finance chart API",
        "url": f"https://finance.yahoo.com/quote/{urllib.parse.quote(symbol)}",
    }


def fetch_news(query: str, limit: int = 6, timeout: float = 8) -> list[dict[str, Any]]:
    encoded = urllib.parse.quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    request = urllib.request.Request(url, headers={"User-Agent": "AIOS-LiveResearch/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        root = ET.fromstring(response.read())
    items = []
    for node in root.findall("./channel/item")[:limit]:
        source = node.find("source")
        items.append(
            {
                "kind": "news",
                "title": (node.findtext("title") or "").strip(),
                "url": (node.findtext("link") or "").strip(),
                "published_at": (node.findtext("pubDate") or "").strip(),
                "source": (source.text or "").strip() if source is not None else "Google News",
            }
        )
    return items


def fetch_brave_search(
    query: str, api_key: str, limit: int = 8, timeout: float = 10
) -> list[dict[str, Any]]:
    url = (
        "https://api.search.brave.com/res/v1/web/search?"
        + urllib.parse.urlencode({"q": query, "count": min(limit, 20), "safesearch": "moderate"})
    )
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
            "User-Agent": "AIOS-LiveResearch/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return [
        {
            "kind": "web",
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("description", ""),
            "published_at": item.get("age", ""),
            "source": "Brave Search",
        }
        for item in payload.get("web", {}).get("results", [])[:limit]
        if item.get("url")
    ]


def fetch_tavily_search(
    query: str, api_key: str, limit: int = 8, timeout: float = 15
) -> list[dict[str, Any]]:
    body = {
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "max_results": min(limit, 20),
        "include_answer": False,
        "include_raw_content": False,
    }
    request = urllib.request.Request(
        "https://api.tavily.com/search",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "AIOS-LiveResearch/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return [
        {
            "kind": "web",
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", ""),
            "published_at": item.get("published_date", ""),
            "source": "Tavily Search",
        }
        for item in payload.get("results", [])[:limit]
        if item.get("url")
    ]


def collect_live_research(
    query: str, *, brave_key: str = "", tavily_key: str = ""
) -> dict[str, Any]:
    collected_at = datetime.now(UTC).isoformat()
    quotes: list[dict[str, Any]] = []
    news: list[dict[str, Any]] = []
    web: list[dict[str, Any]] = []
    errors: list[str] = []
    for metadata in _market_matches(query):
        try:
            quotes.append(fetch_market_quote(*metadata))
        except Exception as exc:
            errors.append(f"{metadata[1]} quote unavailable: {type(exc).__name__}")
    try:
        news = fetch_news(query)
    except Exception as exc:
        errors.append(f"News search unavailable: {type(exc).__name__}")
    if brave_key:
        try:
            web = fetch_brave_search(query, brave_key)
        except Exception as exc:
            errors.append(f"Brave Search unavailable: {type(exc).__name__}")
    elif tavily_key:
        try:
            web = fetch_tavily_search(query, tavily_key)
        except Exception as exc:
            errors.append(f"Tavily Search unavailable: {type(exc).__name__}")
    return {
        "query": query,
        "collected_at": collected_at,
        "quotes": quotes,
        "news": news,
        "web": web,
        "web_provider": "brave-search" if brave_key else "tavily" if tavily_key else "not-configured",
        "errors": errors,
        "is_live": bool(quotes or news or web),
    }


def research_context(result: dict[str, Any]) -> str:
    lines = [
        "LIVE RESEARCH EVIDENCE",
        f"Collected at: {result['collected_at']}",
        "Use only this evidence for time-sensitive claims. Cite sources as [1], [2], etc.",
    ]
    source_number = 1
    for quote in result["quotes"]:
        change = ""
        if quote["change"] is not None:
            change = f", change {quote['change']:+.2f} ({quote['change_percent']:+.2f}%)"
        lines.append(
            f"[{source_number}] {quote['name']} ({quote['symbol']}): "
            f"{quote['price']} {quote['currency']} per {quote['unit']}{change}; "
            f"market state {quote['market_state']}; observed {quote['observed_at']}; "
            f"source {quote['source']}; URL {quote['url']}"
        )
        source_number += 1
    for item in result["news"]:
        lines.append(
            f"[{source_number}] {item['title']} — {item['source']}; "
            f"published {item['published_at']}; URL {item['url']}"
        )
        source_number += 1
    for item in result.get("web", []):
        lines.append(
            f"[{source_number}] {item['title']} — {item['source']}; "
            f"published {item['published_at'] or 'not supplied'}; "
            f"summary {item['snippet']}; URL {item['url']}"
        )
        source_number += 1
    for error in result["errors"]:
        lines.append(f"DATA WARNING: {error}")
    if not result["is_live"]:
        lines.append("No live evidence was retrieved. Do not provide a current price or claim.")
    return "\n".join(lines)


def deterministic_research_answer(result: dict[str, Any]) -> str:
    lines = [f"Live research checked at {result['collected_at']}."]
    for index, quote in enumerate(result["quotes"], 1):
        price = quote["price"]
        if price is None:
            continue
        change = ""
        if quote["change"] is not None:
            change = (
                f" ({quote['change']:+.2f}, {quote['change_percent']:+.2f}% versus prior close)"
            )
        lines.append(
            f"{quote['name']}: {price} {quote['currency']} per {quote['unit']}{change}. [{index}]"
        )
    offset = len(result["quotes"])
    if result["news"]:
        lines.append("Current coverage:")
        lines.extend(
            f"- {item['title']} — {item['source']} ({item['published_at']}) [{offset + index}]"
            for index, item in enumerate(result["news"], 1)
        )
    web = result.get("web", [])
    if web:
        lines.append("Web research:")
        web_offset = len(result["quotes"]) + len(result["news"])
        lines.extend(
            f"- {item['title']} — {item['source']} [{web_offset + index}]"
            for index, item in enumerate(web, 1)
        )
    if not result["is_live"]:
        lines.append("I could not retrieve a live source, so I will not guess the current value.")
    if result["errors"]:
        lines.append("Data warnings: " + "; ".join(result["errors"]))
    sources = result["quotes"] + result["news"] + web
    if sources:
        lines.append("Sources:")
        lines.extend(f"[{index}] {item['url']}" for index, item in enumerate(sources, 1))
    lines.append("Market data may be delayed; verify with your broker before trading.")
    return "\n".join(lines)
