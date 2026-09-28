'''PostgreSQL 연결.

담당: 김동규
'''

import psycopg
from psycopg.rows import dict_row

from app.config import settings


def get_conn() -> psycopg.Connection:
    '''행을 dict로 읽는 연결을 연다. 호출한 쪽에서 close한다.'''

    conn = psycopg.connect(
        settings.database_url,
        row_factory=dict_row,
        connect_timeout=3,
    )

    try:
        from pgvector.psycopg import register_vector
        register_vector(conn)

    except Exception:
        pass

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
    '''INSERT ... RETURNING id 가 있으면 그 값을, 없으면 0을 반환한다.'''

    conn = get_conn()

    try:
        cursor = conn.execute(sql, params)
        conn.commit()

        if cursor.description:
            row = cursor.fetchone()

            if row:
                first = next(iter(row.values()))
                return int(first)

        return 0

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
