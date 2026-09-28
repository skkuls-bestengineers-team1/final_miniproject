'''SQLite 연결.

담당: 김동규
'''

import sqlite3
from pathlib import Path

from app.config import settings


def get_conn() -> sqlite3.Connection:
    '''행을 dict처럼 읽는 연결을 연다. 호출한 쪽에서 close한다.'''

    path = Path(settings.sqlite_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')

    return conn


def fetch_all(
        sql: str,
        params: tuple = ()
) -> list[dict]:
    conn = get_conn()

    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    finally:
        conn.close()


def fetch_one(
        sql: str,
        params: tuple = ()
) -> dict | None:
    rows = fetch_all(sql, params)

    if not rows:
        return None

    return rows[0]


def execute(
        sql: str,
        params: tuple = ()
) -> int:
    conn = get_conn()

    try:
        cursor = conn.execute(sql, params)
        conn.commit()
        return int(cursor.lastrowid or 0)

    finally:
        conn.close()


def fail(
        error_code: str,
        message: str
) -> dict:
    return {
        'ok': False,
        'error_code': error_code,
        'message': message,
    }
