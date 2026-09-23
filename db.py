"""Camada de acesso ao banco: PostgreSQL/Supabase (principal) ou SQLite (fallback).

Nao imprime DATABASE_URL nem senhas. Nao altera schema do Postgres.
"""

from __future__ import annotations

import os
import re
import sqlite3
from datetime import date, datetime, time
from decimal import Decimal

from flask import g

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "waleska.db")

CAMEL_COLS = ("criadoEm", "atualizadoEm", "criadaEm")
BOOL_COLS = frozenset({"lista_espera", "ativo"})
QUOTED_CAMEL = {name: '"%s"' % name for name in CAMEL_COLS}


def env_database_url():
    return (os.environ.get("DATABASE_URL") or "").strip()


def resolve_backend():
    backend = (os.environ.get("DB_BACKEND") or "").strip().lower()
    url = env_database_url()
    if backend in ("sqlite", "local"):
        return "sqlite"
    if url:
        return "postgres"
    if backend in ("supabase", "postgres", "postgresql"):
        return "postgres"
    return "sqlite"


def using_postgres():
    return resolve_backend() == "postgres"


class CompatRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return dict.__getitem__(self, key)

    def keys(self):
        return dict.keys(self)


def _fmt_dt(value):
    if value.tzinfo is not None:
        value = value.replace(tzinfo=None)
    if value.hour == 0 and value.minute == 0 and value.second == 0 and value.microsecond == 0:
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value.strftime("%Y-%m-%d %H:%M:%S")


def normalize_value(value):
    if isinstance(value, datetime):
        return _fmt_dt(value)
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, time):
        return value.strftime("%H:%M:%S")
    if isinstance(value, Decimal):
        return float(value)
    return value


def wrap_row(row):
    if row is None:
        return None
    if isinstance(row, CompatRow):
        return row
    if isinstance(row, sqlite3.Row):
        return CompatRow({k: normalize_value(row[k]) for k in row.keys()})
    if isinstance(row, dict):
        return CompatRow({k: normalize_value(v) for k, v in row.items()})
    return row


def quote_camel_sql(sql):
    out = sql
    for name, quoted in QUOTED_CAMEL.items():
        out = re.sub(r'(?<!")\b' + name + r'\b(?!")', quoted, out)
    return out


def sqlite_to_postgres_sql(sql):
    text = sql.strip()
    text = quote_camel_sql(text)
    text = re.sub(r"\bdate\s*\(\s*", "DATE(", text, flags=re.I)
    text = re.sub(
        r'\b(ativo|lista_espera)\s*=\s*1\b',
        r"\1 = TRUE",
        text,
        flags=re.I,
    )
    text = re.sub(
        r'\b(ativo|lista_espera)\s*=\s*0\b',
        r"\1 = FALSE",
        text,
        flags=re.I,
    )
    text = re.sub(r"\bLIKE\b", "ILIKE", text, flags=re.I)
    text = re.sub(
        r'\b("?starts_at"?)\s+ILIKE\b',
        r"CAST(\1 AS TEXT) ILIKE",
        text,
        flags=re.I,
    )
    text = text.replace("?", "%s")
    return text


def adapt_bool_params(sql, params):
    if not params:
        return params
    values = list(params)
    insert = re.match(
        r"INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]+)\)",
        sql,
        flags=re.I,
    )
    if insert:
        cols = [c.strip().strip('"') for c in insert.group(2).split(",")]
        for i, col in enumerate(cols):
            if col in BOOL_COLS and i < len(values) and values[i] is not None:
                values[i] = bool(values[i])
        return tuple(values)
    set_m = re.search(r"\bSET\s+(.+?)\s+WHERE\b", sql, flags=re.I | re.S)
    if set_m:
        assignments = [part.strip() for part in set_m.group(1).split(",")]
        idx = 0
        for part in assignments:
            col = part.split("=")[0].strip().strip('"')
            if "?" in part or "%s" in part:
                if col in BOOL_COLS and idx < len(values) and values[idx] is not None:
                    values[idx] = bool(values[idx])
                idx += 1
        return tuple(values)
    return tuple(values)


def maybe_returning(sql):
    stripped = sql.strip().rstrip(";")
    upper = stripped.upper()
    if not upper.startswith("INSERT"):
        return stripped
    if "RETURNING" in upper:
        return stripped
    if re.search(r"INSERT\s+INTO\s+settings\b", stripped, flags=re.I):
        return stripped
    return stripped + " RETURNING id"


class PostgresCursor:
    def __init__(self, conn):
        self._conn = conn
        self.lastrowid = None
        self.rowcount = -1
        self._rows = []

    def execute(self, sql, params=None):
        raw = sql.strip()
        if raw.upper().startswith("PRAGMA"):
            self._rows = []
            self.rowcount = -1
            self.lastrowid = None
            return self
        converted = sqlite_to_postgres_sql(raw)
        converted = maybe_returning(converted)
        values = adapt_bool_params(raw, params or ())
        from psycopg.rows import dict_row
        from psycopg.types.json import Jsonb
        if values:
            adapted = []
            for item in values:
                if isinstance(item, (dict, list)):
                    adapted.append(Jsonb(item))
                else:
                    adapted.append(item)
            values = tuple(adapted)

        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(converted, values)
            self.rowcount = cur.rowcount
            self.lastrowid = None
            if cur.description:
                rows = cur.fetchall()
                self._rows = [wrap_row(r) for r in rows]
                if converted.upper().find("RETURNING") != -1 and self._rows:
                    first = self._rows[0]
                    if "id" in first:
                        self.lastrowid = first["id"]
            else:
                self._rows = []
        return self

    def fetchone(self):
        if not self._rows:
            return None
        row = self._rows[0]
        self._rows = self._rows[1:]
        return row

    def fetchall(self):
        rows = list(self._rows)
        self._rows = []
        return rows


class PostgresCompat:
    def __init__(self, conn):
        self._conn = conn
        self.lastrowid = None

    def execute(self, sql, params=None):
        cur = PostgresCursor(self._conn)
        cur.execute(sql, params)
        self.lastrowid = cur.lastrowid
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


class SqliteCompat:
    def __init__(self, conn):
        self._conn = conn
        self.lastrowid = None

    def execute(self, sql, params=None):
        raw = sql.strip()
        if params is None:
            cur = self._conn.execute(raw)
        else:
            cur = self._conn.execute(raw, params)
        self.lastrowid = cur.lastrowid
        return SqliteCursor(cur)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


class SqliteCursor:
    def __init__(self, cur):
        self._cur = cur
        self.lastrowid = cur.lastrowid
        self.rowcount = cur.rowcount

    def fetchone(self):
        return wrap_row(self._cur.fetchone())

    def fetchall(self):
        return [wrap_row(r) for r in self._cur.fetchall()]


def connect_sqlite():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return SqliteCompat(conn)


def connect_postgres():
    url = env_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL nao definida para o backend PostgreSQL.")
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("psycopg nao instalado. Instale psycopg[binary].") from exc
    kwargs = {}
    if "sslmode=" not in url.lower():
        kwargs["sslmode"] = "require"
    conn = psycopg.connect(url, connect_timeout=20, **kwargs)
    conn.autocommit = False
    return PostgresCompat(conn)


def get_db():
    if "db" not in g:
        if using_postgres():
            g.db = connect_postgres()
        else:
            g.db = connect_sqlite()
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def backend_label():
    return "postgres" if using_postgres() else "sqlite"
