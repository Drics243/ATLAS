import statistics
from sr_channels import compute_sr_channels


def compute_ema(closes: list, period: int) -> list:
    if len(closes) < period:
        return []
    k = 2 / (period + 1)
    ema = [sum(closes[:period]) / period]
    for price in closes[period:]:
        ema.append(price * k + ema[-1] * (1 - k))
    return ema


def compute_rsi(closes: list, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d for d in deltas[-period:] if d > 0]
    losses = [-d for d in deltas[-period:] if d < 0]
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def compute_atr(candles: list, period: int = 14) -> float:
    if len(candles) < 2:
        return 0.0
    trs = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i - 1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    return sum(trs[-period:]) / min(period, len(trs))


def find_swing_levels(candles: list, lookback: int = 50) -> dict:
    if len(candles) < 5:
        return {"support": [], "resistance": []}

    current = candles[-1]["close"]
    atr = compute_atr(candles)

    # ── PASS 1: strict 5-bar pivots over full lookback ─────────────
    recent = candles[-lookback:] if len(candles) >= lookback else candles

    swing_highs = []
    swing_lows = []

    for i in range(2, len(recent) - 2):
        h = recent[i]["high"]
        if h > recent[i - 1]["high"] and h > recent[i - 2]["high"] and h > recent[i + 1]["high"] and h > recent[i + 2]["high"]:
            swing_highs.append(h)
        l = recent[i]["low"]
        if l < recent[i - 1]["low"] and l < recent[i - 2]["low"] and l < recent[i + 1]["low"] and l < recent[i + 2]["low"]:
            swing_lows.append(l)

    supports = sorted([s for s in swing_lows if s < current], reverse=True)[:5]
    resistances = sorted([r for r in swing_highs if r > current])[:5]

    # ── PASS 2: looser 3-bar pivots if still missing levels ────────
    if not resistances or not supports:
        for i in range(1, len(recent) - 1):
            h = recent[i]["high"]
            if h > recent[i - 1]["high"] and h > recent[i + 1]["high"]:
                swing_highs.append(h)
            l = recent[i]["low"]
            if l < recent[i - 1]["low"] and l < recent[i + 1]["low"]:
                swing_lows.append(l)

        if not supports:
            supports = sorted([s for s in swing_lows if s < current], reverse=True)[:5]
        if not resistances:
            resistances = sorted([r for r in swing_highs if r > current])[:5]

    # ── PASS 3: use recent candle highs/lows as zone anchors ───────
    if not resistances:
        # Grab the top N distinct highs from recent candles above current
        all_highs = sorted(
            {round(c["high"], 6) for c in recent if c["high"] > current},
            reverse=True,
        )
        # Deduplicate levels that are within 0.1% of each other
        deduped = []
        for h in reversed(all_highs):  # ascending order
            if not deduped or (h - deduped[-1]) / current > 0.001:
                deduped.append(h)
        resistances = deduped[:5]

    if not supports:
        all_lows = sorted(
            {round(c["low"], 6) for c in recent if c["low"] < current},
        )
        deduped = []
        for l in reversed(all_lows):  # descending order
            if not deduped or (deduped[-1] - l) / current > 0.001:
                deduped.append(l)
        supports = deduped[:5]

    # ── PASS 4: ATR projection fallback — always ensure levels exist ─
    if not resistances:
        resistances = [
            round(current + atr * 1.5, 6),
            round(current + atr * 3.0, 6),
            round(current + atr * 5.0, 6),
        ]

    if not supports:
        supports = [
            round(current - atr * 1.5, 6),
            round(current - atr * 3.0, 6),
            round(current - atr * 5.0, 6),
        ]

    return {"support": supports[:5], "resistance": resistances[:5]}


def get_pip_value(pair: str, market_type: str) -> float:
    """Returns the value of 1 pip in price units"""
    p = pair.upper()
    if market_type == "index":
        return 1.0
    if market_type == "energy":
        return 0.01
    if "XAU" in p or "GOLD" in p:
        return 0.10
    if "XAG" in p or "SILVER" in p:
        return 0.001
    if "JPY" in p:
        return 0.01
    return 0.0001


def compute_pivot_structure(candles: list, left: int = 10, right: int = 10) -> dict:
    """
    Pine Script-style pivot analysis: classifies pivot highs/lows as
    HH (Higher High), LH (Lower High), HL (Higher Low), LL (Lower Low).
    Returns current market structure based on the sequence of recent pivots.
    """
    if len(candles) < left + right + 1:
        return {"structure": "RANGING", "pivot_highs": [], "pivot_lows": [], "detail": "Insufficient data"}

    pivot_highs = []
    pivot_lows = []

    # Scan for confirmed pivots (need `right` bars to the right to confirm)
    for i in range(left, len(candles) - right):
        h = candles[i]["high"]
        l = candles[i]["low"]

        is_ph = all(h >= candles[i - j]["high"] for j in range(1, left + 1)) and \
                all(h >= candles[i + j]["high"] for j in range(1, right + 1))
        is_pl = all(l <= candles[i - j]["low"] for j in range(1, left + 1)) and \
                all(l <= candles[i + j]["low"] for j in range(1, right + 1))

        if is_ph:
            pivot_highs.append({"index": i, "price": round(h, 6)})
        if is_pl:
            pivot_lows.append({"index": i, "price": round(l, 6)})

    # Label each pivot high as HH or LH
    for i in range(len(pivot_highs)):
        if i == 0:
            pivot_highs[i]["label"] = "PH"
        else:
            prev = pivot_highs[i - 1]["price"]
            curr = pivot_highs[i]["price"]
            pivot_highs[i]["label"] = "HH" if curr > prev else "LH"

    # Label each pivot low as HL or LL
    for i in range(len(pivot_lows)):
        if i == 0:
            pivot_lows[i]["label"] = "PL"
        else:
            prev = pivot_lows[i - 1]["price"]
            curr = pivot_lows[i]["price"]
            pivot_lows[i]["label"] = "HL" if curr > prev else "LL"

    # Determine structure from the last 2 pivot highs + 2 pivot lows
    recent_ph = pivot_highs[-2:] if len(pivot_highs) >= 2 else pivot_highs
    recent_pl = pivot_lows[-2:] if len(pivot_lows) >= 2 else pivot_lows

    last_ph_label = recent_ph[-1]["label"] if recent_ph else None
    last_pl_label = recent_pl[-1]["label"] if recent_pl else None

    if last_ph_label == "HH" and last_pl_label == "HL":
        structure = "UPTREND"
        detail = "HH + HL — Bullish market structure confirmed"
    elif last_ph_label == "LH" and last_pl_label == "LL":
        structure = "DOWNTREND"
        detail = "LH + LL — Bearish market structure confirmed"
    elif last_ph_label == "LH" and last_pl_label == "HL":
        structure = "RANGING"
        detail = "LH + HL — Consolidation / range structure"
    elif last_ph_label == "HH" and last_pl_label == "LL":
        structure = "RANGING"
        detail = "HH + LL — Expanding / volatile structure"
    elif last_ph_label == "HH":
        structure = "UPTREND"
        detail = "HH forming — potential uptrend developing"
    elif last_pl_label == "HL":
        structure = "UPTREND"
        detail = "HL forming — buyers defending higher lows"
    elif last_ph_label == "LH":
        structure = "DOWNTREND"
        detail = "LH forming — sellers capping each rally"
    elif last_pl_label == "LL":
        structure = "DOWNTREND"
        detail = "LL forming — bears pushing to new lows"
    else:
        structure = "RANGING"
        detail = "No clear pivot sequence — market ranging"

    return {
        "structure": structure,
        "pivot_highs": pivot_highs[-5:],
        "pivot_lows": pivot_lows[-5:],
        "detail": detail,
    }


def compute_forex_signal(data: dict, gameplan: dict) -> dict:
    candles_1h = data.get("ohlcv_1h", [])
    candles_15m = data.get("ohlcv_15m", [])
    pair = data.get("pair", "UNKNOWN")
    market_type = data.get("market_type", "forex")

    if not candles_1h or len(candles_1h) < 20:
        return {"signal": "INSUFFICIENT DATA ❌", "direction": None, "reason": "Not enough candle data."}

    closes_1h = [c["close"] for c in candles_1h]
    current = closes_1h[-1]

    max_sl_pips = gameplan.get("max_sl_pips", 100)
    gp_name = gameplan.get("name", "Intraday")

    ema20 = compute_ema(closes_1h, 20)
    ema50 = compute_ema(closes_1h, 50)
    ema200 = compute_ema(closes_1h, 200) if len(closes_1h) >= 200 else []
    rsi = compute_rsi(closes_1h)
    atr = compute_atr(candles_1h)

    ema_bull = len(ema20) > 0 and len(ema50) > 0 and ema20[-1] > ema50[-1]
    ema_strong_bull = ema_bull and (len(ema200) > 0 and closes_1h[-1] > ema200[-1])
    ema_strong_bear = not ema_bull and (len(ema200) > 0 and closes_1h[-1] < ema200[-1])

    overall_bias = "BULLISH" if ema_bull else "BEARISH"

    # ── Market structure (HH/HL/LH/LL) ────────────────────────────────────────
    pivot_struct = compute_pivot_structure(candles_1h)
    structure = pivot_struct["structure"]
    pivot_highs = pivot_struct["pivot_highs"]
    pivot_lows = pivot_struct["pivot_lows"]
    structure_detail = pivot_struct["detail"]

    # ── Primary S/R: Pine Script SR Channel algorithm ─────────────────────────
    sr_result = compute_sr_channels(candles_1h)
    zone_status = sr_result["zone_status"]
    zone_detail = sr_result["zone_detail"]

    # Flatten channels into price lists for TP/SL targets
    # Use channel midpoints sorted by distance from current price
    sr_supports = []
    sr_resistances = []
    for ch in sr_result["support"]:
        sr_supports.append(ch["hi"])   # top of support channel = nearest price
        sr_supports.append(ch["mid"])
    for ch in sr_result["resistance"]:
        sr_resistances.append(ch["lo"])  # bottom of resistance channel = nearest
        sr_resistances.append(ch["mid"])
    sr_supports.sort(reverse=True)
    sr_resistances.sort()

    # Fall back to swing-level detection if SR channels found nothing
    if not sr_supports or not sr_resistances:
        fallback = find_swing_levels(candles_1h)
        sr_supports = sr_supports or fallback["support"]
        sr_resistances = sr_resistances or fallback["resistance"]

    supports = sr_supports[:5]
    resistances = sr_resistances[:5]

    nearest_support = supports[0] if supports else None
    nearest_resist = resistances[0] if resistances else None

    dist_to_support = abs(current - nearest_support) / current * 100 if nearest_support else 999
    dist_to_resist = abs(current - nearest_resist) / current * 100 if nearest_resist else 999

    # Zone-proximity flags (kept for backward-compat with TP/SL logic below)
    at_support = zone_status == "AT_SUPPORT"
    near_support = zone_status in ("NEAR_SUPPORT", "RESISTANCE_BROKEN")
    at_resist = zone_status == "AT_RESISTANCE"
    near_resist = zone_status in ("NEAR_RESISTANCE", "SUPPORT_BROKEN")

    # ── Scoring ────────────────────────────────────────────────────────────────
    long_score = 0
    long_reasons = []

    if ema_bull:
        long_score += 1
        long_reasons.append("EMA20 > EMA50 (bullish bias)")
    if ema_strong_bull:
        long_score += 1
        long_reasons.append("Price above EMA200 (strong uptrend)")
    if 40 <= rsi <= 65:
        long_score += 1
        long_reasons.append(f"RSI {rsi:.1f} — room to run upward")
    if structure == "UPTREND":
        long_score += 1
        long_reasons.append(f"Market structure: {structure_detail}")

    # Zone-based scoring (SR Channel algorithm is the strongest signal)
    if zone_status == "AT_SUPPORT":
        long_score += 3
        ch = sr_result.get("nearest_support") or {}
        zone_str = f"{ch.get('lo', nearest_support):.5f} – {ch.get('hi', nearest_support):.5f}" if ch else f"{nearest_support:.5f}"
        long_reasons.append(f"Price AT support zone ({zone_str}) — high-probability BUY")
    elif zone_status == "NEAR_SUPPORT":
        long_score += 2
        long_reasons.append(f"Price approaching support zone — prepare BUY LIMIT")
    elif zone_status == "RESISTANCE_BROKEN":
        long_score += 2
        long_reasons.append(f"Resistance broken — bullish breakout, zone flipped to support")
    elif at_support or near_support:
        long_score += 1
        long_reasons.append(f"Price {'at' if at_support else 'near'} key support ({nearest_support:.5f})")

    short_score = 0
    short_reasons = []

    if not ema_bull:
        short_score += 1
        short_reasons.append("EMA20 < EMA50 (bearish bias)")
    if ema_strong_bear:
        short_score += 1
        short_reasons.append("Price below EMA200 (strong downtrend)")
    if 35 <= rsi <= 60:
        short_score += 1
        short_reasons.append(f"RSI {rsi:.1f} — room to fall")
    if structure == "DOWNTREND":
        short_score += 1
        short_reasons.append(f"Market structure: {structure_detail}")

    # Zone-based scoring
    if zone_status == "AT_RESISTANCE":
        short_score += 3
        ch = sr_result.get("nearest_resistance") or {}
        zone_str = f"{ch.get('lo', nearest_resist):.5f} – {ch.get('hi', nearest_resist):.5f}" if ch else f"{nearest_resist:.5f}"
        short_reasons.append(f"Price AT resistance zone ({zone_str}) — high-probability SELL")
    elif zone_status == "NEAR_RESISTANCE":
        short_score += 2
        short_reasons.append(f"Price approaching resistance zone — prepare SELL LIMIT")
    elif zone_status == "SUPPORT_BROKEN":
        short_score += 2
        short_reasons.append(f"Support broken — bearish breakdown, zone flipped to resistance")
    elif at_resist or near_resist:
        short_score += 1
        short_reasons.append(f"Price {'at' if at_resist else 'near'} key resistance ({nearest_resist:.5f})")

    no_entry_reasons = []

    if zone_status == "INSIDE_CHANNEL":
        no_entry_reasons.append(f"Price inside SR channel — {zone_detail}")
    if structure == "RANGING" and long_score < 3 and short_score < 3:
        no_entry_reasons.append("Market is ranging — no clear directional bias")
    if 45 <= rsi <= 55 and zone_status not in ("AT_SUPPORT", "AT_RESISTANCE", "NEAR_SUPPORT", "NEAR_RESISTANCE"):
        no_entry_reasons.append("RSI neutral and price not at any key zone")
    if dist_to_support > 1.0 and dist_to_resist > 1.0 and zone_status == "FREE":
        no_entry_reasons.append("Price is between zones — far from any valid entry")

    if no_entry_reasons and long_score < 4 and short_score < 4:
        direction = "NO ENTRY"
    elif long_score >= 3 and long_score > short_score:
        direction = "LONG"
    elif short_score >= 3 and short_score > long_score:
        direction = "SHORT"
    elif long_score == short_score:
        direction = "NO ENTRY"
        no_entry_reasons.append("Conflicting signals — bullish and bearish equally weighted")
    else:
        direction = "NO ENTRY"
        no_entry_reasons.append("Insufficient confluence for a valid setup")

    if direction == "NO ENTRY":
        return {
            "signal": "NO ENTRY ⏸️",
            "direction": None,
            "overall_bias": overall_bias,
            "structure": structure,
            "structure_detail": structure_detail,
            "pivot_highs": pivot_highs,
            "pivot_lows": pivot_lows,
            "rsi": rsi,
            "ema_bias": "Bullish" if ema_bull else "Bearish",
            "atr": atr,
            "supports": supports,
            "resistances": resistances,
            "reasons": no_entry_reasons,
            "message": "No valid setup at this time. " + " | ".join(no_entry_reasons),
            "current_price": current,
            "zone_status": zone_status,
            "zone_detail": zone_detail,
            "sr_result": sr_result,
        }

    pip_value = get_pip_value(pair, market_type)
    max_sl_price = max_sl_pips * pip_value
    sl_note = None

    if direction == "LONG":
        active_reasons = long_reasons
        if at_support:
            entry_type = "BUY NOW 🔥"
            entry_price = current
            entry_rationale = f"Price is AT support zone ({nearest_support:.5f}). Enter immediately."
        elif near_support:
            entry_type = "BUY LIMIT 📌"
            entry_price = round(nearest_support + (atr * 0.05), 6)
            entry_rationale = f"Set BUY LIMIT at {entry_price:.5f} — wait for pullback to support zone."
        else:
            entry_type = "BUY LIMIT 📌"
            entry_price = round(nearest_support + (atr * 0.05), 6) if nearest_support else round(current - atr, 6)
            entry_rationale = f"Support at {nearest_support:.5f if nearest_support else 'N/A'} — zone is far. Wait for price to come to you."

        raw_sl = entry_price - (atr * 1.5)
        sl_distance = entry_price - raw_sl

        if sl_distance > max_sl_price:
            raw_sl = entry_price - max_sl_price
            sl_note = f"⚠️ SL adjusted to {max_sl_pips} pip limit for your {gp_name} game plan"

        sl = round(raw_sl, 6)
        tp1 = round(resistances[0], 6) if resistances else round(entry_price + atr * 2, 6)
        tp2 = round(resistances[1], 6) if len(resistances) > 1 else round(entry_price + atr * 3.5, 6)
        tp3 = round(entry_price + (tp1 - entry_price) * 2, 6)

    else:  # SHORT
        active_reasons = short_reasons
        if at_resist:
            entry_type = "SELL NOW 🔥"
            entry_price = current
            entry_rationale = f"Price is AT resistance zone ({nearest_resist:.5f}). Enter immediately."
        elif near_resist:
            entry_type = "SELL LIMIT 📌"
            entry_price = round(nearest_resist - (atr * 0.05), 6)
            entry_rationale = f"Set SELL LIMIT at {entry_price:.5f} — wait for price to reach resistance."
        else:
            entry_type = "SELL LIMIT 📌"
            entry_price = round(nearest_resist - (atr * 0.05), 6) if nearest_resist else round(current + atr, 6)
            entry_rationale = f"Resistance at {nearest_resist:.5f if nearest_resist else 'N/A'} — zone is far. Set limit and wait."

        raw_sl = entry_price + (atr * 1.5)
        sl_distance = raw_sl - entry_price

        if sl_distance > max_sl_price:
            raw_sl = entry_price + max_sl_price
            sl_note = f"⚠️ SL adjusted to {max_sl_pips} pip limit for your {gp_name} game plan"

        sl = round(raw_sl, 6)
        tp1 = round(supports[0], 6) if supports else round(entry_price - atr * 2, 6)
        tp2 = round(supports[1], 6) if len(supports) > 1 else round(entry_price - atr * 3.5, 6)
        tp3 = round(entry_price - (entry_price - tp1) * 2, 6)

    rr1 = abs(tp1 - entry_price) / abs(entry_price - sl) if abs(entry_price - sl) > 0 else 0
    rr2 = abs(tp2 - entry_price) / abs(entry_price - sl) if abs(entry_price - sl) > 0 else 0
    sl_pips = round(abs(entry_price - sl) / pip_value, 1)

    flip_condition = (
        f"EMA cross below + break of {round(supports[0], 5) if supports else 'recent low'}"
        if direction == "LONG"
        else f"EMA cross above + break of {round(resistances[0], 5) if resistances else 'recent high'}"
    )

    return {
        "signal": f"{'LONG 📈' if direction == 'LONG' else 'SHORT 📉'}",
        "direction": direction,
        "entry_type": entry_type,
        "entry_price": entry_price,
        "entry_rationale": entry_rationale,
        "stop_loss": sl,
        "sl_pips": sl_pips,
        "sl_pct": round(abs(entry_price - sl) / entry_price * 100, 3),
        "sl_note": sl_note,
        "tp1": tp1, "tp1_pct": round(abs(tp1 - entry_price) / entry_price * 100, 3),
        "tp2": tp2, "tp2_pct": round(abs(tp2 - entry_price) / entry_price * 100, 3),
        "tp3": tp3, "tp3_pct": round(abs(tp3 - entry_price) / entry_price * 100, 3),
        "rr1": round(rr1, 2), "rr2": round(rr2, 2),
        "rr_warning": rr1 < 1.5,
        "rsi": rsi,
        "overall_bias": overall_bias,
        "structure": structure,
        "structure_detail": structure_detail,
        "pivot_highs": pivot_highs,
        "pivot_lows": pivot_lows,
        "ema_bias": "Bullish (EMA20>EMA50)" if ema_bull else "Bearish (EMA20<EMA50)",
        "atr": round(atr, 6),
        "supports": supports,
        "resistances": resistances,
        "active_reasons": active_reasons,
        "flip_condition": flip_condition,
        "current_price": current,
        "gameplan": gp_name,
        "max_sl_pips": max_sl_pips,
        "zone_status": zone_status,
        "zone_detail": zone_detail,
        "sr_result": sr_result,
    }
