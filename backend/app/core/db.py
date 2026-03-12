from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from hashlib import pbkdf2_hmac, sha256
from typing import Any


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data.db")
_LOCK = threading.RLock()


def _utc_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _utc_plus_days(days: int) -> str:
    return (datetime.now(tz=timezone.utc) + timedelta(days=days)).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True)


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


@contextmanager
def connect() -> sqlite3.Connection:
    with _LOCK:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            PRAGMA journal_mode = WAL;
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS watchlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                symbols_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS lab_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                run_type TEXT NOT NULL,
                name TEXT NOT NULL,
                params_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS paper_accounts (
                user_id INTEGER PRIMARY KEY,
                cash REAL NOT NULL,
                positions_json TEXT NOT NULL,
                last_prices_json TEXT NOT NULL,
                fills_json TEXT NOT NULL,
                equity_curve_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                threshold REAL NOT NULL,
                message TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                last_triggered_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS dashboard_layouts (
                user_id INTEGER PRIMARY KEY,
                layout_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        _, salt, expected = hashed.split("$", 2)
    except ValueError:
        return False
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()
    return secrets.compare_digest(digest, expected)


def create_user(email: str, password: str, display_name: str) -> dict:
    email_n = email.strip().lower()
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    now = _utc_iso()
    pw_hash = hash_password(password)
    with connect() as conn:
        try:
            conn.execute(
                "INSERT INTO users (email, password_hash, display_name, created_at) VALUES (?, ?, ?, ?)",
                (email_n, pw_hash, display_name.strip() or "Trader", now),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Email is already registered.") from exc
        row = conn.execute("SELECT id, email, display_name, created_at FROM users WHERE email = ?", (email_n,)).fetchone()
    return dict(row)


def get_user_by_email(email: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, email, display_name, password_hash, created_at FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
    return dict(row) if row else None


def create_session(user_id: int, ttl_days: int = 30) -> str:
    token_raw = secrets.token_urlsafe(36)
    token = sha256(token_raw.encode("utf-8")).hexdigest()
    now = _utc_iso()
    exp = _utc_plus_days(ttl_days)
    with connect() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, now, exp),
        )
    return token


def delete_session(token: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def get_user_by_session(token: str) -> dict | None:
    if not token:
        return None
    now = _utc_iso()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.email, u.display_name, u.created_at
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ? AND s.expires_at > ?
            """,
            (token, now),
        ).fetchone()
    return dict(row) if row else None


def list_watchlists(user_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, name, symbols_json, created_at, updated_at FROM watchlists WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    out = []
    for row in rows:
        d = dict(row)
        d["symbols"] = _json_loads(d.pop("symbols_json", "[]"), [])
        out.append(d)
    return out


def upsert_watchlist(user_id: int, name: str, symbols: list[str]) -> dict:
    clean_symbols = [x.strip().upper() for x in symbols if x and x.strip()][:80]
    if not clean_symbols:
        raise ValueError("Watchlist must contain at least one symbol.")
    now = _utc_iso()
    with connect() as conn:
        existing = conn.execute(
            "SELECT id FROM watchlists WHERE user_id = ? AND name = ?",
            (user_id, name.strip()),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE watchlists SET symbols_json = ?, updated_at = ? WHERE id = ?",
                (_json_dumps(clean_symbols), now, int(existing["id"])),
            )
            watch_id = int(existing["id"])
        else:
            cur = conn.execute(
                "INSERT INTO watchlists (user_id, name, symbols_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, name.strip(), _json_dumps(clean_symbols), now, now),
            )
            watch_id = int(cur.lastrowid)
        row = conn.execute(
            "SELECT id, name, symbols_json, created_at, updated_at FROM watchlists WHERE id = ?",
            (watch_id,),
        ).fetchone()
    data = dict(row)
    data["symbols"] = _json_loads(data.pop("symbols_json", "[]"), [])
    return data


def delete_watchlist(user_id: int, watchlist_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM watchlists WHERE id = ? AND user_id = ?", (watchlist_id, user_id))


def save_lab_run(user_id: int, run_type: str, name: str, params: dict, result: dict) -> dict:
    now = _utc_iso()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO lab_runs (user_id, run_type, name, params_json, result_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, run_type, name, _json_dumps(params), _json_dumps(result), now),
        )
        run_id = int(cur.lastrowid)
    return {"id": run_id, "user_id": user_id, "run_type": run_type, "name": name, "created_at": now}


def list_lab_runs(user_id: int, limit: int = 50) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, run_type, name, params_json, result_json, created_at FROM lab_runs WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    out = []
    for row in rows:
        d = dict(row)
        d["params"] = _json_loads(d.pop("params_json", "{}"), {})
        d["result"] = _json_loads(d.pop("result_json", "{}"), {})
        out.append(d)
    return out


def _default_paper_account() -> dict:
    return {
        "cash": 100000.0,
        "positions": {},
        "last_prices": {},
        "fills": [],
        "equity_curve": [],
    }


def get_paper_account(user_id: int) -> dict:
    with connect() as conn:
        row = conn.execute(
            "SELECT cash, positions_json, last_prices_json, fills_json, equity_curve_json FROM paper_accounts WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return _default_paper_account()
    data = dict(row)
    return {
        "cash": float(data["cash"]),
        "positions": _json_loads(data.get("positions_json"), {}),
        "last_prices": _json_loads(data.get("last_prices_json"), {}),
        "fills": _json_loads(data.get("fills_json"), []),
        "equity_curve": _json_loads(data.get("equity_curve_json"), []),
    }


def set_paper_account(user_id: int, account: dict) -> dict:
    now = _utc_iso()
    with connect() as conn:
        existing = conn.execute("SELECT user_id FROM paper_accounts WHERE user_id = ?", (user_id,)).fetchone()
        payload = (
            float(account.get("cash", 0.0)),
            _json_dumps(account.get("positions", {})),
            _json_dumps(account.get("last_prices", {})),
            _json_dumps(account.get("fills", [])),
            _json_dumps(account.get("equity_curve", [])),
            now,
            user_id,
        )
        if existing:
            conn.execute(
                """
                UPDATE paper_accounts
                SET cash = ?, positions_json = ?, last_prices_json = ?, fills_json = ?, equity_curve_json = ?, updated_at = ?
                WHERE user_id = ?
                """,
                payload,
            )
        else:
            conn.execute(
                """
                INSERT INTO paper_accounts
                (cash, positions_json, last_prices_json, fills_json, equity_curve_json, updated_at, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                payload,
            )
    return get_paper_account(user_id)


def list_alerts(user_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, symbol, direction, threshold, message, enabled, created_at, last_triggered_at
            FROM alerts
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()
    return [dict(x) for x in rows]


def create_alert(user_id: int, symbol: str, direction: str, threshold: float, message: str) -> dict:
    direction_n = direction.strip().lower()
    if direction_n not in {"above", "below"}:
        raise ValueError("Direction must be 'above' or 'below'.")
    symbol_n = symbol.strip().upper()
    if threshold <= 0:
        raise ValueError("Threshold must be positive.")
    now = _utc_iso()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO alerts (user_id, symbol, direction, threshold, message, enabled, created_at, last_triggered_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, NULL)
            """,
            (user_id, symbol_n, direction_n, float(threshold), message.strip() or f"{symbol_n} {direction_n} {threshold}", now),
        )
        alert_id = int(cur.lastrowid)
        row = conn.execute(
            """
            SELECT id, symbol, direction, threshold, message, enabled, created_at, last_triggered_at
            FROM alerts
            WHERE id = ?
            """,
            (alert_id,),
        ).fetchone()
    return dict(row)


def delete_alert(user_id: int, alert_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM alerts WHERE id = ? AND user_id = ?", (alert_id, user_id))


def set_alert_enabled(user_id: int, alert_id: int, enabled: bool) -> dict | None:
    with connect() as conn:
        conn.execute(
            "UPDATE alerts SET enabled = ? WHERE id = ? AND user_id = ?",
            (1 if enabled else 0, alert_id, user_id),
        )
        row = conn.execute(
            "SELECT id, symbol, direction, threshold, message, enabled, created_at, last_triggered_at FROM alerts WHERE id = ? AND user_id = ?",
            (alert_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def mark_alert_triggered(user_id: int, alert_id: int) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE alerts SET last_triggered_at = ? WHERE id = ? AND user_id = ?",
            (_utc_iso(), alert_id, user_id),
        )


def get_dashboard_layout(user_id: int) -> dict:
    with connect() as conn:
        row = conn.execute(
            "SELECT layout_json, updated_at FROM dashboard_layouts WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return {"layout": {}, "updated_at": None}
    d = dict(row)
    return {"layout": _json_loads(d.get("layout_json"), {}), "updated_at": d.get("updated_at")}


def upsert_dashboard_layout(user_id: int, layout: dict) -> dict:
    now = _utc_iso()
    with connect() as conn:
        existing = conn.execute("SELECT user_id FROM dashboard_layouts WHERE user_id = ?", (user_id,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE dashboard_layouts SET layout_json = ?, updated_at = ? WHERE user_id = ?",
                (_json_dumps(layout), now, user_id),
            )
        else:
            conn.execute(
                "INSERT INTO dashboard_layouts (user_id, layout_json, updated_at) VALUES (?, ?, ?)",
                (user_id, _json_dumps(layout), now),
            )
    return get_dashboard_layout(user_id)


def create_note(user_id: int, title: str, body: str) -> dict:
    title_n = title.strip() or "Untitled Note"
    body_n = body.strip()
    now = _utc_iso()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO notes (user_id, title, body, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, title_n, body_n, now, now),
        )
        note_id = int(cur.lastrowid)
        row = conn.execute(
            "SELECT id, title, body, created_at, updated_at FROM notes WHERE id = ? AND user_id = ?",
            (note_id, user_id),
        ).fetchone()
    return dict(row)


def update_note(user_id: int, note_id: int, title: str, body: str) -> dict | None:
    now = _utc_iso()
    with connect() as conn:
        conn.execute(
            "UPDATE notes SET title = ?, body = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (title.strip() or "Untitled Note", body.strip(), now, note_id, user_id),
        )
        row = conn.execute(
            "SELECT id, title, body, created_at, updated_at FROM notes WHERE id = ? AND user_id = ?",
            (note_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def delete_note(user_id: int, note_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id))


def list_notes(user_id: int, limit: int = 100) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, title, body, created_at, updated_at FROM notes WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, max(1, min(limit, 500))),
        ).fetchall()
    return [dict(x) for x in rows]
