import asyncio
import httpx
from markets import resolve_symbol
from datetime import datetime, timedelta


def parse_yahoo_ohlcv(response) -> list:
    try:
        data = response.json()
        chart = data.get("chart", {})
        result = chart.get("result", [])
        if not result:
            return []
        r = result[0]
        timestamps = r.get("timestamp", [])
        indicators = r.get("indicators", {})
        quote = indicators.get("quote", [{}])[0]
        opens = quote.get("open", [])
        highs = quote.get("high", [])
        lows = quote.get("low", [])
        closes = quote.get("close", [])
        volumes = quote.get("volume", [])
        candles = []
        for i, ts in enumerate(timestamps):
            try:
                c = closes[i]
                if c is None:
                    continue
                candles.append({
                    "timestamp": ts,
                    "open": opens[i] or c,
                    "high": highs[i] or c,
                    "low": lows[i] or c,
                    "close": c,
                    "volume": volumes[i] or 0,
                })
            except (IndexError, TypeError):
                continue
        return candles
    except Exception:
        return []


async def _try_yahoo_fetch(symbol: str, client: httpx.AsyncClient, interval: str = "1h", range_: str = "5d") -> list:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    urls_to_try = [
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
        f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}",
    ]
    for url in urls_to_try:
        try:
            r = await client.get(url, params={"interval": interval, "range": range_}, headers=headers, timeout=15)
            if r.status_code == 200:
                parsed = parse_yahoo_ohlcv(r)
                if parsed:
                    return parsed
        except Exception:
            continue
    return []


async def fetch_forex_data(user_input: str, client: httpx.AsyncClient) -> dict:
    yahoo_symbol, display_name, market_type = resolve_symbol(user_input)

    if not yahoo_symbol:
        clean = user_input.upper().replace("/", "").replace("-", "").strip()
        fallback_attempts = [
            f"{clean}=X",
            f"{clean[:3]}=F",
            f"^{clean}",
        ]
        for attempt in fallback_attempts:
            test = await _try_yahoo_fetch(attempt, client)
            if test:
                yahoo_symbol = attempt
                market_type = "forex"
                break

        if not yahoo_symbol:
            return {"error": f"Market '{user_input}' not recognized. Try: EURUSD, XAUUSD, NAS100, US30, DXY"}

    results = await asyncio.gather(
        _try_yahoo_fetch(yahoo_symbol, client, interval="1h", range_="5d"),
        _try_yahoo_fetch(yahoo_symbol, client, interval="15m", range_="1d"),
        return_exceptions=True,
    )

    ohlcv_1h = results[0] if not isinstance(results[0], Exception) and results[0] else []
    ohlcv_15m = results[1] if not isinstance(results[1], Exception) and results[1] else []

    if not ohlcv_1h and not ohlcv_15m:
        return {"error": f"Could not fetch data for {display_name}. Market may be closed or symbol unavailable."}

    current = ohlcv_1h[-1]["close"] if ohlcv_1h else (ohlcv_15m[-1]["close"] if ohlcv_15m else 0)

    return {
        "type": "forex",
        "pair": display_name,
        "yahoo_symbol": yahoo_symbol,
        "market_type": market_type,
        "ohlcv_1h": ohlcv_1h,
        "ohlcv_15m": ohlcv_15m,
        "current_price": current,
    }


async def fetch_meme_data(contract_address: str, client: httpx.AsyncClient) -> dict:
    """Fetch meme/Solana token data from DexScreener"""
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{contract_address}"
        r = await client.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return {"error": "Could not fetch token data from DexScreener."}

        data = r.json()
        pairs = data.get("pairs", [])
        if not pairs:
            return {"error": "Token not found on DexScreener. Make sure you have the correct contract address."}

        pair = pairs[0]
        base = pair.get("baseToken", {})
        price_usd = float(pair.get("priceUsd", 0) or 0)
        price_native = float(pair.get("priceNative", 0) or 0)
        volume_24h = pair.get("volume", {}).get("h24", 0) or 0
        liquidity = pair.get("liquidity", {}).get("usd", 0) or 0
        price_change = pair.get("priceChange", {})
        mc = pair.get("marketCap", 0) or 0
        fdv = pair.get("fdv", 0) or 0

        return {
            "type": "meme",
            "name": base.get("name", "Unknown"),
            "symbol": base.get("symbol", "???"),
            "contract": contract_address,
            "price_usd": price_usd,
            "price_native": price_native,
            "volume_24h": volume_24h,
            "liquidity_usd": liquidity,
            "market_cap": mc,
            "fdv": fdv,
            "price_change_5m": price_change.get("m5", 0) or 0,
            "price_change_1h": price_change.get("h1", 0) or 0,
            "price_change_6h": price_change.get("h6", 0) or 0,
            "price_change_24h": price_change.get("h24", 0) or 0,
            "dex": pair.get("dexId", "unknown"),
            "chain": pair.get("chainId", "solana"),
            "pair_address": pair.get("pairAddress", ""),
            "url": pair.get("url", ""),
        }
    except Exception as e:
        return {"error": f"Error fetching token data: {str(e)}"}


def compute_meme_signal(data: dict) -> dict:
    """Compute buy/sell signal for meme tokens"""
    price_change_1h = data.get("price_change_1h", 0)
    price_change_24h = data.get("price_change_24h", 0)
    volume_24h = data.get("volume_24h", 0)
    liquidity = data.get("liquidity_usd", 0)
    mc = data.get("market_cap", 0)

    risk_flags = []
    score = 0

    if liquidity < 10000:
        risk_flags.append("⚠️ Very low liquidity — high slippage risk")
    elif liquidity < 50000:
        risk_flags.append("⚠️ Low liquidity — watch slippage")
        score += 1
    else:
        score += 2

    if volume_24h > 100000:
        score += 2
    elif volume_24h > 10000:
        score += 1
    else:
        risk_flags.append("⚠️ Low 24h volume — poor market activity")

    if price_change_1h > 20:
        risk_flags.append("🚨 Parabolic move — extreme dump risk")
        score -= 2
    elif price_change_1h > 5:
        score += 1
    elif price_change_1h < -20:
        risk_flags.append("🚨 Sharp drop — possible rug or panic sell")
        score -= 1

    if mc > 0 and mc < 100000:
        risk_flags.append("⚠️ Very small market cap — high volatility")
    elif mc > 1000000:
        score += 1

    if score >= 4:
        signal = "BULLISH 🟢"
        action = "Momentum looks favorable. Small position only."
    elif score >= 2:
        signal = "NEUTRAL 🟡"
        action = "Mixed signals. Watch for breakout or breakdown."
    else:
        signal = "BEARISH / HIGH RISK 🔴"
        action = "Poor setup or extreme risk. Avoid or use minimal size."

    return {
        "signal": signal,
        "action": action,
        "score": score,
        "risk_flags": risk_flags,
    }


async def fetch_economic_calendar(client: httpx.AsyncClient) -> list:
    """Fetch economic calendar from multiple sources with fallback."""
    today = datetime.utcnow()
    week_end = today + timedelta(days=7)

    events = []

    try:
        url = "https://economic-calendar.tradingview.com/events"
        params = {
            "from": today.strftime("%Y-%m-%dT00:00:00.000Z"),
            "to": week_end.strftime("%Y-%m-%dT23:59:59.000Z"),
            "countries": "US,EU,GB,JP,AU,CA,CH,CN,NZ,DE,FR",
        }
        r = await client.get(
            url, params=params, timeout=15,
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.tradingview.com"},
        )
        if r.status_code == 200:
            data = r.json()
            result = data if isinstance(data, list) else data.get("result", [])
            for ev in result:
                importance = ev.get("importance", 0)
                if importance >= 1:
                    events.append({
                        "date": ev.get("date", "")[:10],
                        "time": ev.get("date", "")[11:16] if len(ev.get("date", "")) > 10 else "All Day",
                        "currency": ev.get("country", ""),
                        "name": ev.get("title", ""),
                        "importance": "🔴" if importance >= 3 else "🟡" if importance == 2 else "🟢",
                        "actual": ev.get("actual", "—") or "—",
                        "forecast": ev.get("forecast", "—") or "—",
                        "previous": ev.get("previous", "—") or "—",
                    })
    except Exception:
        pass

    if not events:
        try:
            r = await client.get(
                "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
                timeout=15,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if r.status_code == 200:
                data = r.json()
                for ev in data:
                    imp = ev.get("impact", "Low")
                    events.append({
                        "date": ev.get("date", "")[:10],
                        "time": ev.get("date", "")[11:16] if ev.get("date", "") else "—",
                        "currency": ev.get("country", ""),
                        "name": ev.get("title", ""),
                        "importance": "🔴" if imp == "High" else "🟡" if imp == "Medium" else "🟢",
                        "actual": ev.get("actual", "—") or "—",
                        "forecast": ev.get("forecast", "—") or "—",
                        "previous": ev.get("previous", "—") or "—",
                    })
        except Exception:
            pass

    if not events:
        return [{"error": "Calendar data temporarily unavailable. Check: https://www.forexfactory.com/calendar"}]

    return sorted(events, key=lambda x: x.get("date", "") + x.get("time", ""))
