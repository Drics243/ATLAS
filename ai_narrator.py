import os
import httpx


async def generate_narrative(data: dict, signal: dict, client: httpx.AsyncClient) -> str:
    """Generate AI narrative for the analysis using Groq API."""
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        return _fallback_narrative(data, signal)

    pair = data.get("pair", "this market")
    direction = signal.get("direction")
    market_type = data.get("market_type", "forex")
    current = signal.get("current_price", 0)
    rsi = signal.get("rsi", 50)
    structure = signal.get("structure", "RANGING")
    bias = signal.get("overall_bias", "NEUTRAL")
    atr = signal.get("atr", 0)

    sr_result = signal.get("sr_result", {})
    zone_status = signal.get("zone_status", "FREE")
    zone_detail = signal.get("zone_detail", "")
    sr_analysis = sr_result.get("sr_analysis", "SR channel data unavailable.")
    structure_detail = signal.get("structure_detail", "")

    if direction in ["LONG", "SHORT"]:
        entry = signal.get("entry_price", current)
        sl = signal.get("stop_loss", 0)
        tp1 = signal.get("tp1", 0)
        reasons = signal.get("active_reasons", [])
        reasons_text = "\n".join(f"- {r}" for r in reasons)
        prompt = f"""You are ATLAS, an elite trading analyst using institutional-grade SR channel analysis.

=== INTERNAL PRE-ANALYSIS (do this silently before writing) ===
Study the SR channel data below. Understand which zone the price is currently at, whether this is a high-probability reversal point, and how the zone aligns with the proposed trade direction.

{sr_analysis}

Zone Status: {zone_status}
Zone Context: {zone_detail}
Market Structure: {structure} — {structure_detail}
=== END PRE-ANALYSIS ===

Now write a concise, professional narrative (3-4 sentences) for this {market_type} trade setup.

Market: {pair}
Direction: {direction}
Current Price: {current}
Entry: {entry}  |  Stop Loss: {sl}  |  TP1: {tp1}
RSI: {rsi}  |  Trend Bias: {bias}

Key confluence reasons:
{reasons_text}

Rules:
- Reference the specific SR zone the price is interacting with
- Explain WHY hitting this zone creates the edge
- Mention 1-2 indicators as supporting evidence
- No bullet points — flowing sentences only
- Max 4 sentences. Be confident and precise."""
    else:
        reasons = signal.get("reasons", [signal.get("message", "")])
        reasons_text = "\n".join(f"- {r}" for r in reasons)
        prompt = f"""You are ATLAS, an elite trading analyst using institutional-grade SR channel analysis.

=== INTERNAL PRE-ANALYSIS (do this silently before writing) ===
Study the SR channel data below. Understand the current price position relative to all known zones.

{sr_analysis}

Zone Status: {zone_status}
Zone Context: {zone_detail}
Market Structure: {structure} — {structure_detail}
=== END PRE-ANALYSIS ===

Now write a brief analysis (2-3 sentences) explaining why there is NO valid entry for {pair} right now.

Market: {pair}  |  Current Price: {current}
RSI: {rsi}  |  Trend Bias: {bias}

Reasons for no entry:
{reasons_text}

Rules:
- Reference the SR zone context — where must price go to create a valid setup?
- What should the trader watch for?
- No bullet points. Max 3 sentences."""

    try:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama3-8b-8192",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.65,
            },
            timeout=20,
        )
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
    except Exception:
        pass

    return _fallback_narrative(data, signal)


def _fallback_narrative(data: dict, signal: dict) -> str:
    """Generate a rule-based narrative when AI is unavailable."""
    pair = data.get("pair", "this market")
    direction = signal.get("direction")
    rsi = signal.get("rsi", 50)
    structure = signal.get("structure", "RANGING")
    bias = signal.get("overall_bias", "NEUTRAL")

    if direction == "LONG":
        return (
            f"{pair} is showing a {bias.lower()} bias with {structure.lower()} market structure. "
            f"RSI at {rsi:.1f} suggests momentum is building for upside. "
            f"The EMA alignment supports buying dips toward key support zones. "
            f"Manage risk carefully and trail your stop as the trade develops."
        )
    elif direction == "SHORT":
        return (
            f"{pair} is showing a {bias.lower()} bias with {structure.lower()} market structure. "
            f"RSI at {rsi:.1f} indicates downside pressure remains. "
            f"The EMA configuration favors selling into resistance zones. "
            f"Keep position size appropriate and watch for reversal signals."
        )
    else:
        return (
            f"{pair} is currently in a {structure.lower()} phase with RSI at {rsi:.1f}. "
            f"No clear directional setup presents itself — patience is the trade here. "
            f"Wait for price to reach a key S/R zone before considering an entry."
        )


async def generate_meme_narrative(data: dict, signal: dict, client: httpx.AsyncClient) -> str:
    """Generate narrative for meme token analysis."""
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        return _fallback_meme_narrative(data, signal)

    name = data.get("name", "Unknown")
    symbol = data.get("symbol", "???")
    price_usd = data.get("price_usd", 0)
    volume = data.get("volume_24h", 0)
    liquidity = data.get("liquidity_usd", 0)
    mc = data.get("market_cap", 0)
    change_1h = data.get("price_change_1h", 0)
    change_24h = data.get("price_change_24h", 0)
    sig = signal.get("signal", "NEUTRAL")
    risk_flags = signal.get("risk_flags", [])
    flags_text = "\n".join(risk_flags) if risk_flags else "None"

    prompt = f"""You are ATLAS, a crypto analyst specializing in meme coins. Write a brief, honest analysis (3-4 sentences) for this token.

Token: {name} ({symbol})
Price: ${price_usd}
24h Volume: ${volume:,.0f}
Liquidity: ${liquidity:,.0f}
Market Cap: ${mc:,.0f}
1h Change: {change_1h:+.2f}%
24h Change: {change_24h:+.2f}%
Signal: {sig}
Risk Flags: {flags_text}

Be direct and honest about risks. Do not hype the token. Warn about rug pull risks if liquidity is very low. Max 3 sentences."""

    try:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama3-8b-8192",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 150,
                "temperature": 0.6,
            },
            timeout=20,
        )
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
    except Exception:
        pass

    return _fallback_meme_narrative(data, signal)


def _fallback_meme_narrative(data: dict, signal: dict) -> str:
    name = data.get("name", "This token")
    liquidity = data.get("liquidity_usd", 0)
    change_24h = data.get("price_change_24h", 0)

    if liquidity < 10000:
        return f"{name} has critically low liquidity — this is a very high-risk token with potential rug pull risk. Do not allocate more than you can afford to lose entirely."
    elif change_24h > 50:
        return f"{name} has pumped significantly in the last 24 hours. Chasing parabolic moves is extremely risky — wait for consolidation or a pullback before considering entry."
    else:
        return f"{name} shows mixed signals. Always DYOR — check the contract for honeypot flags and verify team/liquidity lock before trading."
