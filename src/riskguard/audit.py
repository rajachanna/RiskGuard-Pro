"""Minimal SQLite audit trail with no secrets and no order execution."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


class AuditStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS control (id INTEGER PRIMARY KEY CHECK(id=1), halted INTEGER NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS review (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                       "ts TEXT NOT NULL, venue TEXT NOT NULL, symbol TEXT NOT NULL, "
                       "side TEXT NOT NULL, decision TEXT NOT NULL, failed_rules TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS control_event (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                       "ts TEXT NOT NULL, action TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO control(id,halted) VALUES(1,0)")

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=15000")
        return db

    def halted(self) -> bool:
        with self._connect() as db:
            return bool(db.execute("SELECT halted FROM control WHERE id=1").fetchone()[0])

    def set_halt(self, new_state: bool) -> bool:
        with self._connect() as db:
            db.execute("UPDATE control SET halted=? WHERE id=1", (int(new_state),))
            db.execute("INSERT INTO control_event(ts, action) VALUES(?,?)", (
                datetime.now(timezone.utc).isoformat(), "HALTED" if new_state else "RESUMED"))
        return new_state

    def save_review(self, venue: str, symbol: str, side: str, decision: str, failed_rules: list[str]):
        with self._connect() as db:
            db.execute("INSERT INTO review(ts,venue,symbol,side,decision,failed_rules) "
                       "VALUES(?,?,?,?,?,?)", (datetime.now(timezone.utc).isoformat(),
                                              venue, symbol, side, decision, ",".join(failed_rules)))

    def history(self) -> dict:
        with self._connect() as db:
            return {
                "reviews": [dict(row) for row in db.execute("SELECT * FROM review ORDER BY id DESC LIMIT 100")],
                "control_events": [dict(row) for row in db.execute("SELECT * FROM control_event ORDER BY id DESC LIMIT 30")],
            }
