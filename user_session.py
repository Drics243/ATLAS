import json
import os

SESSION_FILE = "sessions.json"


def load_sessions() -> dict:
    if not os.path.exists(SESSION_FILE):
        return {}
    try:
        with open(SESSION_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_sessions(data: dict):
    with open(SESSION_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_session(user_id: int) -> dict:
    return load_sessions().get(str(user_id), {})


def set_session(user_id: int, data: dict):
    sessions = load_sessions()
    sessions[str(user_id)] = data
    save_sessions(sessions)


def update_session(user_id: int, key: str, value):
    session = get_session(user_id)
    session[key] = value
    set_session(user_id, session)


def clear_pending(user_id: int):
    session = get_session(user_id)
    session.pop("pending_analysis", None)
    session.pop("state", None)
    set_session(user_id, session)


def clear_profile(user_id: int):
    session = get_session(user_id)
    session.pop("equity", None)
    session.pop("gameplan", None)
    session.pop("max_sl_pips", None)
    session.pop("pending_analysis", None)
    session.pop("state", None)
    set_session(user_id, session)
