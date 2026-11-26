from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import ActivityEntry, ChatEntry, Inspection, InspectionStatus


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        create table if not exists inspections(id text primary key, status text not null, data text not null, updated_at text not null);
        create table if not exists activity(id integer primary key autoincrement, inspection_id text, action text, detail text, at text);
        create table if not exists processed_boxes(file_id text primary key, sha256 text, outcome text);
        create table if not exists airlock_state(id integer primary key check(id=1), state text not null);
        insert or ignore into airlock_state(id,state) values(1,'clean');
        """)
        self.db.commit()

    def save(self, inspection: Inspection) -> Inspection:
        self.db.execute("insert or replace into inspections(id,status,data,updated_at) values(?,?,?,?)", (inspection.id, inspection.status.value, inspection.model_dump_json(), inspection.updated_at.isoformat()))
        self.db.commit(); return inspection

    def get(self, inspection_id: str) -> Inspection | None:
        row = self.db.execute("select data from inspections where id=?", (inspection_id,)).fetchone()
        return Inspection.model_validate_json(row["data"]) if row else None

    def list(self, status: InspectionStatus | None = None) -> list[Inspection]:
        rows = self.db.execute("select data from inspections where (? is null or status=?) order by updated_at desc", (status.value if status else None, status.value if status else None)).fetchall()
        return [Inspection.model_validate_json(r["data"]) for r in rows]

    def add_chat(self, inspection: Inspection, entry: ChatEntry) -> Inspection:
        inspection.chat.append(entry); inspection.touch() if hasattr(inspection, "touch") else None
        return self.save(inspection)

    def processed_box(self, file_id: str) -> bool:
        return self.db.execute("select 1 from processed_boxes where file_id=?", (file_id,)).fetchone() is not None

    def mark_box(self, file_id: str, sha256: str, outcome: str) -> None:
        self.db.execute("insert or replace into processed_boxes(file_id,sha256,outcome) values(?,?,?)", (file_id, sha256, outcome)); self.db.commit()

    def activity(self, entry: ActivityEntry) -> None:
        import json
        self.db.execute("insert into activity(inspection_id,action,detail,at) values(?,?,?,?)", (entry.inspection_id, entry.action, json.dumps(entry.detail), entry.at.isoformat())); self.db.commit()

    def set_airlock_state(self, state: str) -> None:
        self.db.execute("update airlock_state set state=? where id=1", (state,)); self.db.commit()

    def close(self) -> None:
        self.db.close()
