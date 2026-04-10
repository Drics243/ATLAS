"""
Python port of the Pine Script 'Support Resistance Channels' indicator
by LonesomeTheBlue — adapted for BUAT SENDIRI / ATLAS bot.

Key differences from the Pine version:
  • We work on a list of OHLC candle dicts (most-recent LAST).
  • No drawing — we just return classified channel zones.
  • We add a zone-interaction classifier that drives BUY / SELL signals.
"""


def compute_sr_channels(
    candles: list,
    prd: int = 10,
    channel_width_pct: float = 5.0,
    min_strength: int = 1,
    max_sr: int = 6,
    loopback: int = 290,
) -> dict:
    """
    Parameters
    ----------
    candles           : list of {open, high, low, close} dicts, oldest → newest
    prd               : pivot period (left & right bars, default 10)
    channel_width_pct : max channel width as % of 300-bar range (default 5)
    min_strength      : minimum pivot count to qualify (default 1 → 20 pts)
    max_sr            : maximum channels returned (default 6)
    loopback          : bars to look back for pivots & touches (default 290)

    Returns
    -------
    {
        channels   : all qualified channels sorted by hi price (strongest SR)
        resistance : channels entirely above current price
        support    : channels entirely below current price
        inside     : channel(s) that contain current price
        in_channel : bool — price is inside a channel
        zone_status: 'AT_RESISTANCE' | 'AT_SUPPORT' | 'INSIDE_CHANNEL' |
                     'NEAR_RESISTANCE' | 'NEAR_SUPPORT' |
                     'RESISTANCE_BROKEN' | 'SUPPORT_BROKEN' | 'FREE'
        nearest_resistance : nearest resistance channel dict or None
        nearest_support    : nearest support channel dict or None
        sr_analysis        : human-readable internal analysis string for AI
    }
    """
    n = len(candles)
    if n < prd * 2 + 2:
        return _empty_result()

    # Cap to loopback + some buffer for pivot detection
    use_n = min(n, loopback + prd * 2 + 10)
    candles = candles[-use_n:]
    n = len(candles)

    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    closes = [c["close"] for c in candles]
    opens = [c["open"] for c in candles]

    current = closes[-1]
    prev_close = closes[-2] if n >= 2 else current

    # --- Channel width: (highest - lowest) over last 300 bars × ChannelW% ---
    look300 = min(300, n)
    prdhighest = max(highs[-look300:])
    prdlowest = min(lows[-look300:])
    cwidth = (prdhighest - prdlowest) * channel_width_pct / 100

    # --- Collect pivot highs & lows (need prd bars each side) ---
    # Source: High/Low (same as Pine default ppsrc = 'High/Low')
    pivot_prices = []

    for i in range(prd, n - prd):
        bar_offset = n - 1 - i  # 0 = most recent

        # Pivot High
        h = highs[i]
        if all(h >= highs[i - j] for j in range(1, prd + 1)) and \
           all(h >= highs[i + j] for j in range(1, prd + 1)):
            pivot_prices.append(h)

        # Pivot Low
        l = lows[i]
        if all(l <= lows[i - j] for j in range(1, prd + 1)) and \
           all(l <= lows[i + j] for j in range(1, prd + 1)):
            pivot_prices.append(l)

    if not pivot_prices:
        return _empty_result(current=current)

    # --- Build SR channel for each pivot ---
    def get_sr_vals(base_price):
        lo = base_price
        hi = base_price
        numpp = 0
        for cpp in pivot_prices:
            wdth = (hi - cpp) if cpp <= hi else (cpp - lo)
            if wdth <= cwidth:
                if cpp <= hi:
                    lo = min(lo, cpp)
                else:
                    hi = max(hi, cpp)
                numpp += 20
        return hi, lo, numpp

    # --- Score each pivot's channel + count bar touches ---
    supres = []
    for base_price in pivot_prices:
        hi, lo, strength = get_sr_vals(base_price)

        # Add 1 per bar where high OR low touches the channel band
        touch_count = 0
        for i in range(max(0, n - loopback), n):
            if (highs[i] <= hi and highs[i] >= lo) or \
               (lows[i] <= hi and lows[i] >= lo):
                touch_count += 1

        supres.append({
            "hi": hi,
            "lo": lo,
            "strength": strength + touch_count,
        })

    # --- Pick strongest non-overlapping channels (Pine: "strongest SRs") ---
    used = [False] * len(supres)
    channels = []

    for _ in range(max_sr):
        best_idx = -1
        best_str = min_strength * 20 - 1  # must beat min threshold

        for i, sr in enumerate(supres):
            if not used[i] and sr["strength"] > best_str:
                best_str = sr["strength"]
                best_idx = i

        if best_idx < 0:
            break

        best = supres[best_idx]
        channels.append({
            "hi": round(best["hi"], 6),
            "lo": round(best["lo"], 6),
            "strength": best["strength"],
            "mid": round((best["hi"] + best["lo"]) / 2, 6),
        })

        # Mark all overlapping channels as consumed
        for i, sr in enumerate(supres):
            if (sr["hi"] <= best["hi"] and sr["hi"] >= best["lo"]) or \
               (sr["lo"] <= best["hi"] and sr["lo"] >= best["lo"]):
                used[i] = True

    if not channels:
        return _empty_result(current=current)

    # Sort descending by hi price
    channels.sort(key=lambda x: x["hi"], reverse=True)

    # --- Classify channels relative to current price ---
    resistance = []
    support = []
    inside = []

    for ch in channels:
        if ch["lo"] > current:
            resistance.append(ch)
        elif ch["hi"] < current:
            support.append(ch)
        else:
            inside.append(ch)

    in_channel = len(inside) > 0

    nearest_resistance = resistance[0] if resistance else (inside[0] if inside else None)
    nearest_support = support[0] if support else (inside[-1] if inside else None)

    # --- Zone interaction status ---
    zone_status = "FREE"
    zone_detail = ""

    # Proximity threshold: price within 0.2% of zone boundary
    prox_pct = 0.002

    if in_channel and inside:
        ch = inside[0]
        dist_to_top = (ch["hi"] - current) / current
        dist_to_bot = (current - ch["lo"]) / current

        if dist_to_top < prox_pct:
            zone_status = "AT_RESISTANCE"
            zone_detail = (f"Price is AT resistance channel top "
                           f"({ch['lo']:.5f} – {ch['hi']:.5f}). "
                           f"High-probability SELL zone.")
        elif dist_to_bot < prox_pct:
            zone_status = "AT_SUPPORT"
            zone_detail = (f"Price is AT support channel bottom "
                           f"({ch['lo']:.5f} – {ch['hi']:.5f}). "
                           f"High-probability BUY zone.")
        elif dist_to_top < 0.005:
            zone_status = "NEAR_RESISTANCE"
            zone_detail = (f"Price is near the top of channel "
                           f"({ch['lo']:.5f} – {ch['hi']:.5f}). "
                           f"Watch for rejection or breakout.")
        elif dist_to_bot < 0.005:
            zone_status = "NEAR_SUPPORT"
            zone_detail = (f"Price is near the bottom of channel "
                           f"({ch['lo']:.5f} – {ch['hi']:.5f}). "
                           f"Watch for bounce or breakdown.")
        else:
            zone_status = "INSIDE_CHANNEL"
            zone_detail = (f"Price is inside SR channel "
                           f"({ch['lo']:.5f} – {ch['hi']:.5f}). "
                           f"No clear directional edge — wait for boundary test.")

    elif resistance:
        ch = resistance[0]  # lowest resistance above price
        dist = (ch["lo"] - current) / current
        if dist < prox_pct:
            zone_status = "AT_RESISTANCE"
            zone_detail = (f"Price is testing resistance zone bottom at {ch['lo']:.5f}. "
                           f"Expect rejection — prime SELL setup.")
        elif dist < 0.005:
            zone_status = "NEAR_RESISTANCE"
            zone_detail = (f"Price is approaching resistance "
                           f"({ch['lo']:.5f} – {ch['hi']:.5f}). "
                           f"Prepare SELL LIMIT or watch for rejection.")

    # Check broken levels (Pine: close[1] was below/above, now above/below)
    if zone_status == "FREE" or zone_status not in ("AT_RESISTANCE", "AT_SUPPORT"):
        for ch in channels:
            # Resistance broken: prev close ≤ channel top, current > channel top
            if prev_close <= ch["hi"] and current > ch["hi"]:
                zone_status = "RESISTANCE_BROKEN"
                zone_detail = (f"Resistance broken! Price broke above "
                               f"{ch['hi']:.5f}. Bullish breakout — "
                               f"that channel now acts as support.")
                break
            # Support broken: prev close ≥ channel bottom, current < channel bottom
            if prev_close >= ch["lo"] and current < ch["lo"]:
                zone_status = "SUPPORT_BROKEN"
                zone_detail = (f"Support broken! Price broke below "
                               f"{ch['lo']:.5f}. Bearish breakdown — "
                               f"that channel now acts as resistance.")
                break

    if not zone_detail:
        if support:
            ch = support[0]
            dist = (current - ch["hi"]) / current
            if dist < prox_pct:
                zone_status = "AT_SUPPORT"
                zone_detail = (f"Price touching top of support zone "
                               f"({ch['lo']:.5f} – {ch['hi']:.5f}). "
                               f"High-probability BUY zone.")
            elif dist < 0.005:
                zone_status = "NEAR_SUPPORT"
                zone_detail = (f"Price approaching support "
                               f"({ch['lo']:.5f} – {ch['hi']:.5f}). "
                               f"Prepare BUY LIMIT.")
            else:
                zone_detail = "Price is between SR zones — no immediate zone test."
        else:
            zone_detail = "No significant SR zones detected in this range."

    # --- Build human-readable SR analysis for the AI prompt ---
    res_lines = []
    for i, ch in enumerate(resistance[:3], 1):
        res_lines.append(f"  R{i}: {ch['lo']:.5f} – {ch['hi']:.5f} (strength {ch['strength']})")
    sup_lines = []
    for i, ch in enumerate(support[:3], 1):
        sup_lines.append(f"  S{i}: {ch['lo']:.5f} – {ch['hi']:.5f} (strength {ch['strength']})")
    ins_lines = []
    for ch in inside:
        ins_lines.append(f"  INSIDE: {ch['lo']:.5f} – {ch['hi']:.5f} (strength {ch['strength']})")

    sr_analysis = (
        f"SR Channel Analysis (LonesomeTheBlue algorithm, prd={prd}, "
        f"max_width={channel_width_pct}%):\n"
        f"Current price: {current}\n"
    )
    if res_lines:
        sr_analysis += "Resistance zones:\n" + "\n".join(res_lines) + "\n"
    if sup_lines:
        sr_analysis += "Support zones:\n" + "\n".join(sup_lines) + "\n"
    if ins_lines:
        sr_analysis += "Price-in-channel:\n" + "\n".join(ins_lines) + "\n"
    sr_analysis += f"Zone status: {zone_status}\n{zone_detail}"

    return {
        "channels": channels,
        "resistance": resistance,
        "support": support,
        "inside": inside,
        "in_channel": in_channel,
        "zone_status": zone_status,
        "zone_detail": zone_detail,
        "nearest_resistance": nearest_resistance,
        "nearest_support": nearest_support,
        "sr_analysis": sr_analysis,
        "current_price": current,
        "cwidth": round(cwidth, 6),
    }


def _empty_result(current: float = 0.0) -> dict:
    return {
        "channels": [],
        "resistance": [],
        "support": [],
        "inside": [],
        "in_channel": False,
        "zone_status": "FREE",
        "zone_detail": "Insufficient data for SR channel analysis.",
        "nearest_resistance": None,
        "nearest_support": None,
        "sr_analysis": "SR channel analysis unavailable — insufficient data.",
        "current_price": current,
        "cwidth": 0.0,
    }
