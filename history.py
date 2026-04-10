import json
import os
from datetime import datetime

HISTORY_FILE = "analysis_history.json"
MAX_HISTORY = 10


def load_history() -> dict:
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_history(data: dict):
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=2)


def add_to_history(user_id: int, pair: str, signal_type: str, direction: str = None):
    """Add an analysis entry to the user's history."""
    history = load_history()
    uid = str(user_id)
    if uid not in history:
        history[uid] = []

    entry = {
        "pair": pair,
        "signal": signal_type,
        "direction": direction,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }

    history[uid].insert(0, entry)
    history[uid] = history[uid][:MAX_HISTORY]
    save_history(history)


def get_history(user_id: int) -> list:
    """Get the user's analysis history."""
    history = load_history()
    return history.get(str(user_id), [])


def format_history_message(user_id: int) -> str:
    entries = get_history(user_id)
    if not entries:
        return "📋 No analysis history yet.\n\nRun /analyze &lt;pair&gt; to get started."

    msg = "📋 <b>Your Last 10 Analyses</b>\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

    for i, e in enumerate(entries, 1):
        direction = e.get("direction")
        if direction == "LONG":
            arrow = "📈"
        elif direction == "SHORT":
            arrow = "📉"
        else:
            arrow = "⏸️"

        msg += f"{i}. {arrow} <b>{e['pair']}</b>\n"
        msg += f"   Signal: {e['signal']}\n"
        msg += f"   🕐 {e['timestamp']}\n\n"

    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += "Run /analyze &lt;pair&gt; to get a fresh analysis."
    return msg
