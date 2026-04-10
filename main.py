import asyncio
import logging
import os
import re

import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from analyzer import fetch_economic_calendar, fetch_forex_data, fetch_meme_data, compute_meme_signal
from ai_narrator import generate_narrative, generate_meme_narrative
from history import add_to_history, format_history_message
from signals import compute_forex_signal
from user_session import clear_pending, clear_profile, get_session, set_session, update_session

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

AWAITING_EQUITY = 1
AWAITING_GAMEPLAN_CONFIRM = 2
AWAITING_CUSTOM_GAMEPLAN = 3

SOLANA_CA_PATTERN = re.compile(r"^[A-HJ-NP-Za-km-z1-9]{32,44}$")


def is_solana_ca(text: str) -> bool:
    return bool(SOLANA_CA_PATTERN.match(text.strip()))


def determine_gameplan(equity: float) -> dict:
    if equity <= 50:
        return {"name": "Super Scalping", "max_sl_pips": 30, "style": "Very tight SL, quick in/out trades"}
    elif equity <= 100:
        return {"name": "Normal Scalping", "max_sl_pips": 60, "style": "Short timeframe, moderate SL"}
    elif equity <= 500:
        return {"name": "Intraday Trading", "max_sl_pips": 100, "style": "Hold hours, use S&R zones"}
    else:
        return {"name": "Day Trading", "max_sl_pips": 200, "style": "Larger moves, hold full day"}


def format_forex_message(pair, data, signal, narrative, gameplan) -> str:
    current = signal.get("current_price", 0)
    direction = signal.get("direction")
    gp_name = gameplan.get("name", "Intraday")
    equity = gameplan.get("equity", 0)
    max_sl = gameplan.get("max_sl_pips", 100)

    structure_detail = signal.get("structure_detail", "")
    pivot_highs = signal.get("pivot_highs", [])
    pivot_lows = signal.get("pivot_lows", [])

    msg = f"""📊 <b>BUAT SENDIRI — Market Analysis</b>
━━━━━━━━━━━━━━━━━━━━

💱 <b>PAIR: {pair}</b>
Current Price: <b>{current}</b>
💼 Game Plan: <b>{gp_name}</b> (Equity: ${equity} | Max SL: {max_sl} pips)

📐 <b>TECHNICAL OVERVIEW</b>
Trend Bias: <b>{signal.get('overall_bias', '—')}</b>
Market Structure: <b>{signal.get('structure', '—')}</b>
<i>{structure_detail}</i>
EMA Signal: <b>{signal.get('ema_bias', '—')}</b>
RSI (14): <b>{signal.get('rsi', '—')}</b>
ATR (14): <b>{signal.get('atr', '—')}</b>

"""

    # Pivot highs table (HH / LH)
    if pivot_highs:
        recent_ph = pivot_highs[-3:]
        ph_labels = "  ".join(f"<b>{p['label']}</b> <code>{p['price']}</code>" for p in recent_ph)
        msg += f"📈 <b>Pivot Highs:</b> {ph_labels}\n"

    # Pivot lows table (HL / LL)
    if pivot_lows:
        recent_pl = pivot_lows[-3:]
        pl_labels = "  ".join(f"<b>{p['label']}</b> <code>{p['price']}</code>" for p in recent_pl)
        msg += f"📉 <b>Pivot Lows:</b>  {pl_labels}\n"

    if pivot_highs or pivot_lows:
        msg += "\n"

    # ── SR Channels (primary) ───────────────────────────────────────────────
    sr_result = signal.get("sr_result", {})
    zone_status = signal.get("zone_status", "FREE")
    zone_detail = signal.get("zone_detail", "")

    zone_status_emoji = {
        "AT_RESISTANCE": "🔴 AT RESISTANCE",
        "NEAR_RESISTANCE": "🟠 NEAR RESISTANCE",
        "AT_SUPPORT": "🟢 AT SUPPORT",
        "NEAR_SUPPORT": "🟡 NEAR SUPPORT",
        "INSIDE_CHANNEL": "⬜ INSIDE CHANNEL",
        "RESISTANCE_BROKEN": "🚀 RESISTANCE BROKEN",
        "SUPPORT_BROKEN": "💥 SUPPORT BROKEN",
        "FREE": "⬛ BETWEEN ZONES",
    }.get(zone_status, zone_status)

    msg += f"📍 <b>Zone Status: {zone_status_emoji}</b>\n"
    if zone_detail:
        msg += f"<i>{zone_detail}</i>\n\n"

    sr_res = sr_result.get("resistance", [])
    sr_sup = sr_result.get("support", [])
    sr_ins = sr_result.get("inside", [])

    if sr_res:
        msg += "🔴 <b>Resistance Channels:</b>\n"
        for i, ch in enumerate(sr_res[:3], 1):
            msg += f"   R{i}: <code>{ch['lo']:.5f}</code> – <code>{ch['hi']:.5f}</code>\n"
        msg += "\n"
    elif signal.get("resistances"):
        msg += "🔴 <b>Resistance Zones:</b>\n"
        for i, r in enumerate(signal["resistances"][:3], 1):
            msg += f"   R{i}: <code>{r}</code>\n"
        msg += "\n"

    if sr_ins:
        msg += "⬜ <b>Current Channel (price inside):</b>\n"
        for ch in sr_ins[:2]:
            msg += f"   <code>{ch['lo']:.5f}</code> – <code>{ch['hi']:.5f}</code>\n"
        msg += "\n"

    if sr_sup:
        msg += "🟢 <b>Support Channels:</b>\n"
        for i, ch in enumerate(sr_sup[:3], 1):
            msg += f"   S{i}: <code>{ch['lo']:.5f}</code> – <code>{ch['hi']:.5f}</code>\n"
        msg += "\n"
    elif signal.get("supports"):
        msg += "🟢 <b>Support Zones:</b>\n"
        for i, s in enumerate(signal["supports"][:3], 1):
            msg += f"   S{i}: <code>{s}</code>\n"
        msg += "\n"

    msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"📡 <b>ATLAS SIGNAL: {signal.get('signal', '—')}</b>\n\n"

    if direction in ["LONG", "SHORT"]:
        entry_type = signal.get("entry_type", "—")
        entry_price = signal.get("entry_price", current)
        sl = signal.get("stop_loss")
        sl_pips = signal.get("sl_pips", "—")
        rr_warn = "\n⚠️ R:R below 1.5 — consider waiting for better entry.\n" if signal.get("rr_warning") else ""

        msg += f"""🎯 <b>TRADE SETUP</b>
Direction: <b>{'📈 LONG (BUY)' if direction == 'LONG' else '📉 SHORT (SELL)'}</b>

⚡ <b>ENTRY: {entry_type}</b>
<code>{entry_price}</code>
💬 {signal.get('entry_rationale', '')}

🛑 <b>Stop Loss:</b> <code>{sl}</code>
   (-{signal.get('sl_pct', 0):.3f}% | {sl_pips} pips)
"""
        if signal.get("sl_note"):
            msg += f"   {signal['sl_note']}\n"

        msg += f"""
🎯 <b>Take Profit Levels:</b>
   TP1: <code>{signal.get('tp1')}</code> (+{signal.get('tp1_pct', 0):.3f}%) — Take 40%
   TP2: <code>{signal.get('tp2')}</code> (+{signal.get('tp2_pct', 0):.3f}%) — Take 35%
   TP3: <code>{signal.get('tp3')}</code> (+{signal.get('tp3_pct', 0):.3f}%) — Trail 25%

📐 <b>Risk:Reward</b>
   → TP1: 1:{signal.get('rr1', 0):.2f}
   → TP2: 1:{signal.get('rr2', 0):.2f}
{rr_warn}
📋 <b>Why this setup:</b>
"""
        for r in signal.get("active_reasons", []):
            msg += f"   • {r}\n"

        msg += f"\n🔄 <b>Setup invalidated if:</b>\n   {signal.get('flip_condition', '—')}\n"

    else:
        msg += "⏸️ <b>No valid entry at this time.</b>\n\n"
        for r in signal.get("reasons", [signal.get("message", "")]):
            msg += f"   • {r}\n"
        if signal.get("supports"):
            msg += f"\n👀 Watch for price to reach S1: {signal['supports'][0]} for potential long setup."
        if signal.get("resistances"):
            msg += f"\n👀 Or reach R1: {signal['resistances'][0]} for potential short setup."

    msg += f"\n\n🤖 <b>AI ANALYSIS</b>\n{narrative}\n"
    msg += f"\n━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🔗 Share: /analyze {pair}\n"
    msg += f"📅 Economic news: /calendar"

    return msg


def format_meme_message(data: dict, signal: dict, narrative: str) -> str:
    name = data.get("name", "Unknown")
    symbol = data.get("symbol", "???")
    price = data.get("price_usd", 0)
    vol = data.get("volume_24h", 0)
    liq = data.get("liquidity_usd", 0)
    mc = data.get("market_cap", 0)
    c5m = data.get("price_change_5m", 0)
    c1h = data.get("price_change_1h", 0)
    c6h = data.get("price_change_6h", 0)
    c24h = data.get("price_change_24h", 0)
    dex = data.get("dex", "unknown")
    chain = data.get("chain", "solana")
    url = data.get("url", "")

    def fmt_change(v):
        return f"+{v:.2f}%" if v > 0 else f"{v:.2f}%"

    msg = f"""🪙 <b>BUAT SENDIRI — Meme Token Analysis</b>
━━━━━━━━━━━━━━━━━━━━

🏷️ <b>{name}</b> ({symbol})
Chain: {chain.upper()} | DEX: {dex}
Contract: <code>{data.get('contract', '—')}</code>

💰 <b>PRICE DATA</b>
Price: <b>${price:.10f}</b>
24h Volume: <b>${vol:,.0f}</b>
Liquidity: <b>${liq:,.0f}</b>
Market Cap: <b>${mc:,.0f}</b>

📊 <b>PRICE CHANGES</b>
5m:  {fmt_change(c5m)}
1h:  {fmt_change(c1h)}
6h:  {fmt_change(c6h)}
24h: {fmt_change(c24h)}

━━━━━━━━━━━━━━━━━━━━
📡 <b>ATLAS SIGNAL: {signal.get('signal', '—')}</b>
💡 {signal.get('action', '—')}

"""
    if signal.get("risk_flags"):
        msg += "⚠️ <b>Risk Flags:</b>\n"
        for flag in signal["risk_flags"]:
            msg += f"   {flag}\n"
        msg += "\n"

    msg += f"━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🤖 <b>AI ANALYSIS</b>\n{narrative}\n"
    msg += f"\n━━━━━━━━━━━━━━━━━━━━\n"
    if url:
        msg += f"🔗 <a href='{url}'>View on DexScreener</a>\n"
    msg += "⚠️ <i>DYOR — Meme coins are extremely high risk. Never invest more than you can afford to lose.</i>"

    return msg


async def run_forex_analysis(update: Update, pair: str, session: dict, context=None):
    """Run the full forex/market analysis and send result."""
    user_id = update.effective_user.id
    gameplan_name = session.get("gameplan", "Intraday Trading")
    max_sl_pips = session.get("max_sl_pips", 100)
    equity = session.get("equity", 0)

    gameplan = {
        "name": gameplan_name,
        "max_sl_pips": max_sl_pips,
        "equity": equity,
    }

    status_msg = await update.message.reply_text(f"🔍 Analyzing {pair}...")

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            data = await fetch_forex_data(pair, client)

            if "error" in data:
                await status_msg.edit_text(f"❌ {data['error']}")
                return

            signal = compute_forex_signal(data, gameplan)
            narrative = await generate_narrative(data, signal, client)

        display_pair = data.get("pair", pair)
        msg = format_forex_message(display_pair, data, signal, narrative, gameplan)

        add_to_history(
            user_id,
            display_pair,
            signal.get("signal", "—"),
            signal.get("direction"),
        )

        clear_pending(user_id)
        await _send_long_message(update, status_msg, msg)

    except Exception as e:
        logger.error(f"Error in forex analysis: {e}", exc_info=True)
        try:
            await status_msg.edit_text(f"❌ Analysis failed: {str(e)[:200]}")
        except Exception:
            pass


async def _send_long_message(update: Update, status_msg, msg: str):
    """Send a possibly-long HTML message, splitting if needed. Only deletes status on success."""
    MAX = 4096
    chunks = [msg[i:i + MAX] for i in range(0, len(msg), MAX)]
    try:
        for chunk in chunks:
            await update.message.reply_text(chunk, parse_mode="HTML")
        # Only delete status AFTER successful send
        try:
            await status_msg.delete()
        except Exception:
            pass
    except Exception as html_err:
        logger.warning(f"HTML send failed ({html_err}), retrying as plain text")
        try:
            import re as _re
            plain = _re.sub(r"<[^>]+>", "", msg)
            for chunk in [plain[i:i + MAX] for i in range(0, len(plain), MAX)]:
                await update.message.reply_text(chunk)
            try:
                await status_msg.delete()
            except Exception:
                pass
        except Exception as plain_err:
            logger.error(f"Plain text send also failed: {plain_err}")
            try:
                await status_msg.edit_text("❌ Could not send analysis. Please try again.")
            except Exception:
                pass


async def handle_start(update: Update, context) -> None:
    msg = """👋 <b>Welcome to BUAT SENDIRI</b>
<i>Blockchain Utility Analytics Tool</i>
━━━━━━━━━━━━━━━━━━━━

🚀 <b>What I can analyze:</b>

💱 <b>Forex</b> — All major, minor &amp; exotic pairs
   EURUSD, GBPUSD, USDJPY, AUDUSD...

🥇 <b>Metals &amp; Energy</b>
   XAUUSD (Gold), XAGUSD (Silver)
   XTIUSD (WTI Oil), XBRUSD (Brent)

📊 <b>Indices</b>
   NAS100, SPX500, US30, GER40, UK100...

📈 <b>Currency Index</b>
   DXY, JPYX...

🪙 <b>Meme Coins</b> — Paste any Solana CA

━━━━━━━━━━━━━━━━━━━━
<b>Commands:</b>
/analyze &lt;pair or CA&gt; — Run full analysis
/calendar — Today's economic events
/calendar week — Full week calendar
/history — Your last 10 analyses
/reset_profile — Reset equity &amp; game plan
/help — Full guide"""
    await update.message.reply_text(msg, parse_mode="HTML")


async def handle_help(update: Update, context) -> None:
    msg = """📖 <b>BUAT SENDIRI — Help Guide</b>
━━━━━━━━━━━━━━━━━━━━

<b>How to use:</b>

1️⃣ Run /analyze &lt;pair&gt;
   Example: /analyze EURUSD
   Example: /analyze XAUUSD
   Example: /analyze NAS100

2️⃣ Set your equity (first time only)
   The bot recommends a game plan based on your balance

3️⃣ Get your full analysis:
   • Trend bias &amp; market structure
   • Key support/resistance zones
   • Entry type (BUY NOW / BUY LIMIT)
   • Stop loss &amp; take profit levels
   • Risk:Reward ratio
   • AI narrative

<b>Supported Markets:</b>
• All major/minor/exotic forex pairs
• Gold, Silver, Platinum, Copper
• WTI Oil, Brent, Natural Gas
• US30, NAS100, SPX500, GER40, UK100 &amp; more
• DXY (Dollar Index)
• BTC, ETH, SOL, XRP
• Any Solana meme coin (paste CA)

<b>Commands:</b>
/analyze — Market analysis
/calendar — Economic calendar
/history — Your analysis history
/reset_profile — Reset equity &amp; game plan settings
/start — Welcome message"""
    await update.message.reply_text(msg, parse_mode="HTML")


async def handle_history(update: Update, context) -> None:
    user_id = update.effective_user.id
    msg = format_history_message(user_id)
    await update.message.reply_text(msg, parse_mode="HTML")


async def handle_reset_profile(update: Update, context) -> None:
    user_id = update.effective_user.id
    clear_profile(user_id)
    await update.message.reply_text(
        "✅ Profile reset!\n\n"
        "Your equity and game plan settings have been cleared.\n"
        "Next time you run /analyze, I'll ask for your equity again.",
        parse_mode="HTML",
    )


async def handle_calendar(update: Update, context) -> None:
    arg = " ".join(context.args).lower().strip() if context.args else ""
    show_week = "week" in arg or "minggu" in arg

    status = await update.message.reply_text("📅 Fetching economic calendar...")

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            events = await fetch_economic_calendar(client)

        if events and events[0].get("error"):
            await status.edit_text(events[0]["error"])
            return

        from datetime import datetime
        today_str = datetime.utcnow().strftime("%Y-%m-%d")

        if not show_week:
            events = [e for e in events if e.get("date") == today_str]
            title_label = f"📅 Economic Calendar — Today ({today_str})"
        else:
            title_label = "📅 Economic Calendar — This Week"

        high_events = [e for e in events if e["importance"] in ["🔴", "🟡"]]

        if not high_events:
            await status.edit_text(
                f"📅 No high-impact events {'today' if not show_week else 'this week'}.\n\n"
                f"Use /calendar week for full week view."
            )
            return

        msg = f"<b>{title_label}</b>\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

        current_date = ""
        for ev in high_events[:25]:
            if ev["date"] != current_date:
                current_date = ev["date"]
                try:
                    from datetime import datetime as dt
                    d = dt.strptime(current_date, "%Y-%m-%d")
                    msg += f"\n📆 <b>{d.strftime('%A, %d %B %Y')}</b>\n"
                except Exception:
                    msg += f"\n📆 <b>{current_date}</b>\n"

            msg += (
                f"{ev['importance']} <b>{ev['currency']}</b> | {ev['time']} UTC\n"
                f"   📌 {ev['name']}\n"
                f"   Actual: <b>{ev['actual']}</b> | "
                f"Forecast: {ev['forecast']} | "
                f"Prev: {ev['previous']}\n\n"
            )

        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += "🔴 High Impact  🟡 Medium Impact\n"
        msg += "Use /calendar week for full week view."

        await status.delete()

        if len(msg) > 4096:
            for i in range(0, len(msg), 4096):
                await update.message.reply_text(msg[i:i + 4096], parse_mode="HTML")
        else:
            await update.message.reply_text(msg, parse_mode="HTML")

    except Exception as e:
        await status.edit_text(f"❌ Calendar error: {str(e)}")


async def analyze_start(update: Update, context) -> int:
    """Entry point for /analyze command."""
    user_id = update.effective_user.id
    args = context.args

    if not args:
        await update.message.reply_text(
            "❓ Please provide a pair or contract address.\n\n"
            "Examples:\n"
            "  /analyze EURUSD\n"
            "  /analyze XAUUSD\n"
            "  /analyze NAS100\n"
            "  /analyze &lt;Solana CA&gt;",
            parse_mode="HTML",
        )
        return ConversationHandler.END

    user_input = args[0].strip()

    if is_solana_ca(user_input):
        await _handle_meme_analysis(update, user_input)
        return ConversationHandler.END

    session = get_session(user_id)

    if session.get("equity") and session.get("gameplan"):
        await run_forex_analysis(update, user_input, session, context)
        return ConversationHandler.END

    update_session(user_id, "pending_analysis", user_input)
    update_session(user_id, "state", "awaiting_equity")

    await update.message.reply_text(
        f"💼 Before I analyze <b>{user_input}</b>, I need to know your trading equity.\n\n"
        f"What is your current trading account balance?\n"
        f"Reply with a number (e.g: 50, 150, 500)\n\n"
        f"This helps me recommend the right Game Plan and risk parameters for you.",
        parse_mode="HTML",
    )
    return AWAITING_EQUITY


async def receive_equity(update: Update, context) -> int:
    """Handle equity input from user."""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    try:
        equity = float(text.replace(",", "").replace("$", ""))
        if equity <= 0:
            raise ValueError("Equity must be positive")
    except ValueError:
        await update.message.reply_text(
            "❌ Please enter a valid number.\n\nExample: 50, 150, 500"
        )
        return AWAITING_EQUITY

    gp = determine_gameplan(equity)
    update_session(user_id, "equity", equity)
    update_session(user_id, "recommended_gp", gp["name"])
    update_session(user_id, "recommended_max_sl", gp["max_sl_pips"])

    await update.message.reply_text(
        f"📊 Based on your equity of <b>${equity:,.0f}</b>:\n\n"
        f"🎯 Recommended Game Plan: <b>{gp['name']}</b>\n"
        f"📏 Max SL: <b>{gp['max_sl_pips']} pips</b>\n"
        f"📋 Style: {gp['style']}\n\n"
        f"Apakah mau menggunakan Game Plan Trading yang saya rekomendasikan sesuai Margin anda?\n\n"
        f"Reply <b>YES</b> to confirm or <b>NO</b> to choose your own.",
        parse_mode="HTML",
    )
    return AWAITING_GAMEPLAN_CONFIRM


async def receive_gameplan_confirm(update: Update, context) -> int:
    """Handle YES/NO to recommended game plan."""
    user_id = update.effective_user.id
    text = update.message.text.strip().upper()

    if text in ["YES", "Y", "YA", "YEP", "CONFIRM", "OK"]:
        session = get_session(user_id)
        gp_name = session.get("recommended_gp", "Intraday Trading")
        max_sl = session.get("recommended_max_sl", 100)

        update_session(user_id, "gameplan", gp_name)
        update_session(user_id, "max_sl_pips", max_sl)

        pair = session.get("pending_analysis", "")
        await update.message.reply_text(f"✅ Game Plan <b>{gp_name}</b> confirmed! Running analysis...", parse_mode="HTML")

        updated_session = get_session(user_id)
        await run_forex_analysis(update, pair, updated_session, context)
        return ConversationHandler.END

    elif text in ["NO", "N", "TIDAK", "NOPE"]:
        await update.message.reply_text(
            "🎮 Game Plan Trading yang kamu inginkan seperti apa?\n\n"
            "Choose one:\n"
            "1️⃣ Scalping\n"
            "2️⃣ Intraday\n"
            "3️⃣ Day Trade\n\n"
            "Reply with the number or name.",
        )
        return AWAITING_CUSTOM_GAMEPLAN

    else:
        await update.message.reply_text("Please reply with YES or NO.")
        return AWAITING_GAMEPLAN_CONFIRM


async def receive_custom_gameplan(update: Update, context) -> int:
    """Handle custom game plan selection."""
    user_id = update.effective_user.id
    text = update.message.text.strip().upper()

    if text in ["1", "SCALPING", "SCALP"]:
        gp_name = "Scalping"
        max_sl = 60
    elif text in ["2", "INTRADAY", "INTRA"]:
        gp_name = "Intraday"
        max_sl = 100
    elif text in ["3", "DAY TRADE", "DAY TRADING", "DAY"]:
        gp_name = "Day Trading"
        max_sl = 200
    else:
        await update.message.reply_text(
            "❓ Please choose:\n1️⃣ Scalping\n2️⃣ Intraday\n3️⃣ Day Trade\n\nReply with the number or name."
        )
        return AWAITING_CUSTOM_GAMEPLAN

    update_session(user_id, "gameplan", gp_name)
    update_session(user_id, "max_sl_pips", max_sl)

    session = get_session(user_id)
    pair = session.get("pending_analysis", "")

    await update.message.reply_text(f"✅ Got it! Using <b>{gp_name}</b> Game Plan. Running analysis...", parse_mode="HTML")
    await run_forex_analysis(update, pair, session, context)
    return ConversationHandler.END


async def cancel(update: Update, context) -> int:
    """Cancel ongoing conversation."""
    user_id = update.effective_user.id
    clear_pending(user_id)
    await update.message.reply_text("❌ Analysis cancelled.")
    return ConversationHandler.END


async def _handle_meme_analysis(update: Update, contract_address: str):
    """Handle meme token analysis."""
    user_id = update.effective_user.id
    status = await update.message.reply_text(f"🔍 Fetching token data for <code>{contract_address[:12]}...</code>", parse_mode="HTML")

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            data = await fetch_meme_data(contract_address, client)

            if "error" in data:
                await status.edit_text(f"❌ {data['error']}")
                return

            signal = compute_meme_signal(data)
            narrative = await generate_meme_narrative(data, signal, client)

        msg = format_meme_message(data, signal, narrative)
        add_to_history(user_id, data.get("symbol", contract_address[:8]), signal.get("signal", "—"), None)

        await status.delete()
        await update.message.reply_text(msg, parse_mode="HTML", disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Meme analysis error: {e}")
        await status.edit_text(f"❌ Error fetching token data: {str(e)}")


async def handle_text_message(update: Update, context) -> None:
    """Handle plain text messages that look like Solana CAs."""
    text = update.message.text.strip()
    if is_solana_ca(text):
        await _handle_meme_analysis(update, text)
    else:
        await update.message.reply_text(
            "💡 Use /analyze &lt;pair&gt; to get a market analysis.\n\n"
            "Examples: /analyze EURUSD | /analyze XAUUSD | /analyze NAS100",
            parse_mode="HTML",
        )


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set! Please add it to environment variables.")
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required.")

    application = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("analyze", analyze_start)],
        states={
            AWAITING_EQUITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_equity)],
            AWAITING_GAMEPLAN_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_gameplan_confirm)],
            AWAITING_CUSTOM_GAMEPLAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_gameplan)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(CommandHandler("help", handle_help))
    application.add_handler(CommandHandler("history", handle_history))
    application.add_handler(CommandHandler("reset_profile", handle_reset_profile))
    application.add_handler(CommandHandler("calendar", handle_calendar))
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    logger.info("ATLAS 1.0 (BUAT SENDIRI) bot starting...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
