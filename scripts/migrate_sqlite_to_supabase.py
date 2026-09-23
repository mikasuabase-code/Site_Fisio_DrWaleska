#!/usr/bin/env python3
"""Migracao SQLite -> PostgreSQL/Supabase (somente quando --execute).

Padrao: DRY-RUN (le o SQLite, valida, nao insere, nao conecta).

Uso:
  python3 scripts/migrate_sqlite_to_supabase.py
  python3 scripts/migrate_sqlite_to_supabase.py --dry-run
  DATABASE_URL=... python3 scripts/migrate_sqlite_to_supabase.py --execute

Variaveis de ambiente (so no --execute):
  DATABASE_URL  connection string Postgres do projeto (obrigatoria)

Nao le service_role, anon key nem senhas avulsas. Nao imprime hashes nem URL.
Nao altera o SQLite nem o Flask. Nao cria sqlite_sequence.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SQLITE = REPO_DIR / "data" / "waleska.db"
TZ_SAO_PAULO = ZoneInfo("America/Sao_Paulo")

TABLE_ORDER = [
    "admins",
    "services",
    "registrations",
    "settings",
    "exercises",
    "waitlist",
    "duplas",
    "appointments",
    "payments",
    "evaluations",
    "evolutions",
    "documents",
]

SKIP_TABLES = frozenset({"sqlite_sequence"})


class RowError(Exception):
    def __init__(self, table: str, pk, message: str):
        super().__init__(message)
        self.table = table
        self.pk = pk
        self.message = message


def parse_bool(value):
    if value is None or value == "":
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("1", "true", "t", "yes"):
        return True
    if text in ("0", "false", "f", "no"):
        return False
    raise ValueError(f"booleano invalido: {value!r}")


def parse_int(value):
    if value is None or value == "":
        return None
    return int(value)


def parse_fk(value):
    number = parse_int(value)
    if number is None or number == 0:
        return None
    return number


def parse_money(value):
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"valor monetario invalido: {value!r}") from exc


def parse_money_required(value):
    parsed = parse_money(value)
    return Decimal("0") if parsed is None else parsed


def parse_json(value, default):
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list, bool, int, float)):
        return value
    return json.loads(value)


def parse_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"data invalida: {value!r}")


def parse_naive_timestamp(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text, fmt)
            if fmt == "%Y-%m-%d":
                dt = datetime.combine(dt.date(), datetime.min.time())
            return dt
        except ValueError:
            continue
    raise ValueError(f"timestamp naive invalido: {value!r}")


def parse_timestamptz(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=TZ_SAO_PAULO)
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text, fmt)
            if fmt == "%Y-%m-%d":
                dt = datetime.combine(dt.date(), datetime.min.time())
            return dt.replace(tzinfo=TZ_SAO_PAULO)
        except ValueError:
            continue
    raise ValueError(f"timestamptz invalido: {value!r}")


def parse_text(value, default=""):
    if value is None:
        return default
    return str(value)


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def transform_admins(row: dict) -> dict:
    return {
        "id": parse_int(row["id"]),
        "email": parse_text(row["email"]),
        "password_hash": parse_text(row["password_hash"]),
        "nome": parse_text(row.get("nome"), "Waleska Paula"),
        "role": parse_text(row.get("role"), "Administradora"),
        "criadoEm": parse_timestamptz(row.get("criadoEm")),
    }


def transform_services(row: dict) -> dict:
    return {
        "id": parse_int(row["id"]),
        "nome": parse_text(row["nome"]),
        "descricao": parse_text(row.get("descricao")),
        "valor": parse_money_required(row.get("valor")),
        "info_adicional": parse_text(row.get("info_adicional")),
        "icone": parse_text(row.get("icone"), "padrao"),
        "lista_espera": parse_bool(row.get("lista_espera")),
        "ativo": parse_bool(row.get("ativo") if row.get("ativo") is not None else 1),
        "ordem": parse_int(row.get("ordem")) or 0,
        "duracao_min": parse_int(row.get("duracao_min")) or 50,
        "categoria": parse_text(row.get("categoria")),
        "criadoEm": parse_timestamptz(row.get("criadoEm")),
        "atualizadoEm": parse_timestamptz(row.get("atualizadoEm")),
    }


def transform_registrations(row: dict) -> dict:
    return {
        "id": parse_int(row["id"]),
        "nome": parse_text(row["nome"]),
        "nascimento": parse_date(row.get("nascimento")),
        "telefone": parse_text(row["telefone"]),
        "servico_id": parse_fk(row.get("servico_id")),
        "servico": parse_text(row["servico"]),
        "valor": parse_money(row.get("valor")),
        "dias": parse_json(row.get("dias"), []),
        "frequencia": parse_text(row.get("frequencia"), None),
        "motivos": parse_json(row.get("motivos"), []),
        "observacoes": parse_text(row.get("observacoes")),
        "status": parse_text(row.get("status"), "Novo"),
        "forma_pagamento": parse_text(row.get("forma_pagamento")),
        "criadoEm": parse_timestamptz(row.get("criadoEm")),
        "atualizadoEm": parse_timestamptz(row.get("atualizadoEm")),
    }


def transform_settings(row: dict) -> dict:
    return {
        "chave": parse_text(row["chave"]),
        "valor": parse_json(row.get("valor"), []),
        "atualizadoEm": parse_timestamptz(row.get("atualizadoEm")),
    }


def transform_exercises(row: dict) -> dict:
    return {
        "id": parse_int(row["id"]),
        "nome": parse_text(row["nome"]),
        "descricao": parse_text(row.get("descricao")),
        "categoria": parse_text(row.get("categoria")),
        "regiao": parse_text(row.get("regiao")),
        "objetivo": parse_text(row.get("objetivo")),
        "instrucoes": parse_text(row.get("instrucoes")),
        "criadoEm": parse_timestamptz(row.get("criadoEm")),
        "atualizadoEm": parse_timestamptz(row.get("atualizadoEm")),
    }


def transform_waitlist(row: dict) -> dict:
    return {
        "id": parse_int(row["id"]),
        "registration_id": parse_fk(row.get("registration_id")),
        "nome": parse_text(row["nome"]),
        "nascimento": parse_date(row.get("nascimento")),
        "idade": parse_int(row.get("idade")),
        "telefone": parse_text(row["telefone"]),
        "servico": parse_text(row["servico"]),
        "dificuldades": parse_text(row.get("dificuldades")),
        "observacoes": parse_text(row.get("observacoes")),
        "status": parse_text(row.get("status"), "Lista de espera"),
        "criadoEm": parse_timestamptz(row.get("criadoEm")),
        "atualizadoEm": parse_timestamptz(row.get("atualizadoEm")),
    }


def transform_duplas(row: dict) -> dict:
    return {
        "id": parse_int(row["id"]),
        "paciente1": parse_json(row.get("paciente1"), None),
        "paciente2": parse_json(row.get("paciente2"), None),
        "servico": parse_text(row["servico"]),
        "observacoes": parse_text(row.get("observacoes")),
        "status": parse_text(row.get("status"), "Em dupla"),
        "criadaEm": parse_timestamptz(row.get("criadaEm")),
        "atualizadoEm": parse_timestamptz(row.get("atualizadoEm")),
    }


def transform_appointments(row: dict) -> dict:
    return {
        "id": parse_int(row["id"]),
        "patient_id": parse_fk(row.get("patient_id")),
        "patient_name": parse_text(row["patient_name"]),
        "service_id": parse_fk(row.get("service_id")),
        "service_name": parse_text(row.get("service_name")),
        "dupla_id": parse_fk(row.get("dupla_id")),
        "starts_at": parse_naive_timestamp(row["starts_at"]),
        "ends_at": parse_naive_timestamp(row.get("ends_at")),
        "duration_min": parse_int(row.get("duration_min")) or 50,
        "status": parse_text(row.get("status"), "Agendado"),
        "notes": parse_text(row.get("notes")),
        "criadoEm": parse_timestamptz(row.get("criadoEm")),
        "atualizadoEm": parse_timestamptz(row.get("atualizadoEm")),
    }


def transform_payments(row: dict) -> dict:
    patient_id = parse_fk(row.get("patient_id"))
    registration_id = parse_fk(row.get("registration_id"))
    if patient_id is None and registration_id is None:
        shared = None
    elif patient_id is None:
        shared = registration_id
        patient_id = shared
    elif registration_id is None:
        shared = patient_id
        registration_id = shared
    elif patient_id == registration_id:
        shared = patient_id
    else:
        shared = None
    if shared is not None:
        patient_id = shared
        registration_id = shared
    return {
        "id": parse_int(row["id"]),
        "patient_id": patient_id,
        "patient_name": parse_text(row.get("patient_name")),
        "appointment_id": parse_fk(row.get("appointment_id")),
        "service_id": parse_fk(row.get("service_id")),
        "amount": parse_money_required(row.get("amount")),
        "status": parse_text(row.get("status"), "Pendente"),
        "paid_at": parse_timestamptz(row.get("paid_at")),
        "notes": parse_text(row.get("notes")),
        "method": parse_text(row.get("method")),
        "service_name": parse_text(row.get("service_name")),
        "registration_id": registration_id,
        "criadoEm": parse_timestamptz(row.get("criadoEm")),
        "atualizadoEm": parse_timestamptz(row.get("atualizadoEm")),
    }


def transform_evaluations(row: dict) -> dict:
    return {
        "id": parse_int(row["id"]),
        "patient_id": parse_fk(row.get("patient_id")),
        "patient_name": parse_text(row.get("patient_name")),
        "evaluated_at": parse_date(row.get("evaluated_at")) or date.today(),
        "queixa": parse_text(row.get("queixa")),
        "objetivos": parse_text(row.get("objetivos")),
        "historico": parse_text(row.get("historico")),
        "avaliacao_funcional": parse_text(row.get("avaliacao_funcional")),
        "plano": parse_text(row.get("plano")),
        "observacoes": parse_text(row.get("observacoes")),
        "profissional": parse_text(row.get("profissional"), "Waleska Paula"),
        "criadoEm": parse_timestamptz(row.get("criadoEm")),
        "atualizadoEm": parse_timestamptz(row.get("atualizadoEm")),
    }


def transform_evolutions(row: dict) -> dict:
    return {
        "id": parse_int(row["id"]),
        "patient_id": parse_fk(row.get("patient_id")),
        "patient_name": parse_text(row.get("patient_name")),
        "appointment_id": parse_fk(row.get("appointment_id")),
        "evolution_date": parse_date(row.get("evolution_date")) or date.today(),
        "procedimentos": parse_text(row.get("procedimentos")),
        "exercicios": parse_text(row.get("exercicios")),
        "resposta": parse_text(row.get("resposta")),
        "observacoes": parse_text(row.get("observacoes")),
        "proxima_conduta": parse_text(row.get("proxima_conduta")),
        "profissional": parse_text(row.get("profissional"), "Waleska Paula"),
        "criadoEm": parse_timestamptz(row.get("criadoEm")),
        "atualizadoEm": parse_timestamptz(row.get("atualizadoEm")),
    }


def transform_documents(row: dict) -> dict:
    return {
        "id": parse_int(row["id"]),
        "patient_id": parse_fk(row.get("patient_id")),
        "patient_name": parse_text(row.get("patient_name")),
        "titulo": parse_text(row["titulo"]),
        "tipo": parse_text(row.get("tipo")),
        "notes": parse_text(row.get("notes")),
        "criadoEm": parse_timestamptz(row.get("criadoEm")),
    }


TRANSFORMERS = {
    "admins": transform_admins,
    "services": transform_services,
    "registrations": transform_registrations,
    "settings": transform_settings,
    "exercises": transform_exercises,
    "waitlist": transform_waitlist,
    "duplas": transform_duplas,
    "appointments": transform_appointments,
    "payments": transform_payments,
    "evaluations": transform_evaluations,
    "evolutions": transform_evolutions,
    "documents": transform_documents,
}

JSON_COLUMNS = {
    "registrations": ("dias", "motivos"),
    "duplas": ("paciente1", "paciente2"),
    "settings": ("valor",),
}

PK_COLUMN = {table: "id" for table in TABLE_ORDER}
PK_COLUMN["settings"] = "chave"

HAS_INTEGER_IDENTITY = {table: table != "settings" for table in TABLE_ORDER}


def open_sqlite(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(f"SQLite nao encontrado: {path}")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_sqlite_rows(conn: sqlite3.Connection, table: str) -> list[dict]:
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    return [dict(row) for row in rows]


def sqlite_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {row[0] for row in rows}


def pk_of(table: str, payload: dict):
    return payload[PK_COLUMN[table]]


def validate_payload(table: str, payload: dict) -> None:
    pk = pk_of(table, payload)
    if pk is None or pk == "":
        raise RowError(table, pk, "PK ausente")
    if table == "admins":
        if not payload["email"] or not payload["password_hash"]:
            raise RowError(table, pk, "email ou password_hash vazio")
    if table == "duplas":
        if not isinstance(payload["paciente1"], dict) or not isinstance(payload["paciente2"], dict):
            raise RowError(table, pk, "paciente1/paciente2 devem ser objetos JSON")
    if table == "appointments" and payload["starts_at"] is None:
        raise RowError(table, pk, "starts_at obrigatorio")
    if table == "payments":
        if payload["amount"] is None:
            raise RowError(table, pk, "amount obrigatorio")


def transform_table(table: str, raw_rows: list[dict]) -> tuple[list[dict], list[str]]:
    transformer = TRANSFORMERS[table]
    ready = []
    errors = []
    for raw in raw_rows:
        pk = raw.get(PK_COLUMN[table])
        try:
            payload = transformer(raw)
            validate_payload(table, payload)
            ready.append(payload)
        except Exception as exc:
            errors.append(f"{table} pk={pk}: {exc}")
    return ready, errors


def json_ready(table: str, payload: dict) -> dict:
    cols = JSON_COLUMNS.get(table, ())
    if not cols:
        return payload
    out = dict(payload)
    for col in cols:
        out[col] = json.dumps(out[col], ensure_ascii=False)
    return out


def build_insert_sql(table: str, columns: list[str]) -> str:
    col_sql = ", ".join(quote_ident(c) for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    pk = PK_COLUMN[table]
    overriding = " OVERRIDING SYSTEM VALUE" if HAS_INTEGER_IDENTITY[table] else ""
    return (
        f"INSERT INTO {quote_ident(table)} ({col_sql})"
        f"{overriding} VALUES ({placeholders}) "
        f"ON CONFLICT ({quote_ident(pk)}) DO NOTHING"
    )


def existing_pks(pg_conn, table: str) -> set:
    pk = PK_COLUMN[table]
    with pg_conn.cursor() as cur:
        cur.execute(f"SELECT {quote_ident(pk)} FROM {quote_ident(table)}")
        return {row[0] for row in cur.fetchall()}


def pg_count(pg_conn, table: str) -> int:
    with pg_conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {quote_ident(table)}")
        return int(cur.fetchone()[0])


def adjust_identity(pg_conn, table: str) -> None:
    if not HAS_INTEGER_IDENTITY[table]:
        return
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT pg_get_serial_sequence(%s, 'id')",
            (table,),
        )
        seq = cur.fetchone()[0]
        if not seq:
            raise RuntimeError(f"sequence nao encontrada para {table}.id")
        cur.execute(f"SELECT MAX(id) FROM {quote_ident(table)}")
        max_id = cur.fetchone()[0]
        if max_id is None:
            cur.execute("SELECT setval(%s, 1, false)", (seq,))
        else:
            cur.execute("SELECT setval(%s, %s, true)", (seq, int(max_id)))


def connect_postgres():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit(
            "DATABASE_URL nao definida. Defina a connection string do Postgres "
            "somente no ambiente do servidor, nunca no codigo."
        )
    try:
        import psycopg
        from psycopg.rows import tuple_row
    except ImportError as exc:
        raise SystemExit(
            "psycopg nao instalado. Instale psycopg[binary] para --execute."
        ) from exc
    conn = psycopg.connect(url, row_factory=tuple_row, autocommit=False)
    return conn


def payload_values(table: str, payload: dict, columns: list[str]):
    try:
        from psycopg.types.json import Jsonb
    except ImportError:
        Jsonb = None
    values = []
    json_cols = set(JSON_COLUMNS.get(table, ()))
    for col in columns:
        value = payload[col]
        if col in json_cols and Jsonb is not None:
            values.append(Jsonb(value))
        else:
            values.append(value)
    return tuple(values)


def print_report(rows: list[dict], mode: str) -> None:
    print()
    print(f"Relatorio ({mode})")
    header = (
        f"{'tabela':<16} {'sqlite':>8} {'inseridos':>10} "
        f"{'ignorados':>10} {'erros':>7}"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['tabela']:<16} {row['sqlite']:>8} {row['inseridos']:>10} "
            f"{row['ignorados']:>10} {row['erros']:>7}"
        )
    print("-" * len(header))
    totals = {
        "sqlite": sum(r["sqlite"] for r in rows),
        "inseridos": sum(r["inseridos"] for r in rows),
        "ignorados": sum(r["ignorados"] for r in rows),
        "erros": sum(r["erros"] for r in rows),
    }
    print(
        f"{'TOTAL':<16} {totals['sqlite']:>8} {totals['inseridos']:>10} "
        f"{totals['ignorados']:>10} {totals['erros']:>7}"
    )


def run_dry_run(sqlite_path: Path) -> int:
    conn = open_sqlite(sqlite_path)
    try:
        found = sqlite_tables(conn)
        missing = [t for t in TABLE_ORDER if t not in found]
        if missing:
            print("Tabelas ausentes no SQLite:", ", ".join(missing))
            return 1
        extra = sorted(found - set(TABLE_ORDER) - SKIP_TABLES)
        if extra:
            print("Tabelas SQLite ignoradas:", ", ".join(extra))

        print(f"DRY-RUN | SQLite: {sqlite_path}")
        print("Nenhuma conexao Postgres. Nenhum INSERT.")
        print("Fuso de auditoria: America/Sao_Paulo")
        print(f"DATABASE_URL definida: {'sim' if os.environ.get('DATABASE_URL') else 'nao'}")

        report = []
        all_errors = []
        for table in TABLE_ORDER:
            raw = fetch_sqlite_rows(conn, table)
            ready, errors = transform_table(table, raw)
            ids = [pk_of(table, item) for item in ready]
            unique = set(ids)
            if len(ids) != len(unique):
                errors.append(f"{table}: PKs duplicadas no SQLite")
            report.append(
                {
                    "tabela": table,
                    "sqlite": len(raw),
                    "inseridos": 0,
                    "ignorados": 0,
                    "erros": len(errors),
                }
            )
            all_errors.extend(errors)
            print(
                f"  {table}: sqlite={len(raw)} validos={len(ready)} "
                f"erros={len(errors)} ids={sorted(unique, key=lambda x: (str(type(x)), x))}"
            )

        print_report(report, "dry-run")
        if all_errors:
            print("\nErros de validacao:")
            for item in all_errors:
                print(" -", item)
            return 1
        print("\nValidacao OK. Nenhuma migracao executada.")
        return 0
    finally:
        conn.close()


def run_execute(sqlite_path: Path) -> int:
    sqlite_conn = open_sqlite(sqlite_path)
    pg_conn = None
    try:
        found = sqlite_tables(sqlite_conn)
        missing = [t for t in TABLE_ORDER if t not in found]
        if missing:
            print("Tabelas ausentes no SQLite:", ", ".join(missing))
            return 1

        prepared = {}
        all_errors = []
        sqlite_counts = {}
        for table in TABLE_ORDER:
            raw = fetch_sqlite_rows(sqlite_conn, table)
            sqlite_counts[table] = len(raw)
            ready, errors = transform_table(table, raw)
            prepared[table] = ready
            all_errors.extend(errors)
        if all_errors:
            print("Validacao falhou. Nenhum INSERT.")
            for item in all_errors:
                print(" -", item)
            return 1

        pg_conn = connect_postgres()
        print("EXECUTE | Postgres conectado (URL nao exibida)")
        print(f"SQLite: {sqlite_path}")

        report = []
        with pg_conn:
            with pg_conn.cursor() as cur:
                for table in TABLE_ORDER:
                    rows = prepared[table]
                    before = pg_count(pg_conn, table)
                    present = existing_pks(pg_conn, table)
                    inserted = 0
                    ignored = 0
                    errors = 0
                    if not rows:
                        adjust_identity(pg_conn, table)
                        after = pg_count(pg_conn, table)
                        report.append(
                            {
                                "tabela": table,
                                "sqlite": sqlite_counts[table],
                                "inseridos": 0,
                                "ignorados": 0,
                                "erros": 0,
                            }
                        )
                        print(
                            f"  {table}: sqlite=0 pg_antes={before} "
                            f"inseridos=0 ignorados=0 pg_depois={after}"
                        )
                        continue

                    columns = list(rows[0].keys())
                    sql = build_insert_sql(table, columns)
                    for payload in rows:
                        pk = pk_of(table, payload)
                        if pk in present:
                            ignored += 1
                            continue
                        try:
                            cur.execute(sql, payload_values(table, payload, columns))
                            if cur.rowcount == 0:
                                ignored += 1
                            else:
                                inserted += 1
                                present.add(pk)
                        except Exception as exc:
                            errors += 1
                            print(f"  ERRO {table} pk={pk}: {exc}")
                            raise
                    adjust_identity(pg_conn, table)
                    after = pg_count(pg_conn, table)
                    report.append(
                        {
                            "tabela": table,
                            "sqlite": sqlite_counts[table],
                            "inseridos": inserted,
                            "ignorados": ignored,
                            "erros": errors,
                        }
                    )
                    print(
                        f"  {table}: sqlite={sqlite_counts[table]} "
                        f"pg_antes={before} inseridos={inserted} "
                        f"ignorados={ignored} pg_depois={after}"
                    )
                    if after < sqlite_counts[table]:
                        raise RuntimeError(
                            f"contagem {table}: postgres={after} < sqlite={sqlite_counts[table]}"
                        )

            print_report(report, "execute")
            print("\nSequences ajustadas. SQLite intacto.")
        return 0
    finally:
        sqlite_conn.close()
        if pg_conn is not None:
            pg_conn.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrar waleska.db para Postgres/Supabase (dry-run padrao)."
    )
    parser.add_argument(
        "--sqlite",
        default=str(DEFAULT_SQLITE),
        help="Caminho do SQLite (somente leitura)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Somente ler e validar (padrao)",
    )
    mode.add_argument(
        "--execute",
        action="store_true",
        help="Inserir no Postgres usando DATABASE_URL",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    sqlite_path = Path(args.sqlite)
    if args.execute:
        return run_execute(sqlite_path)
    return run_dry_run(sqlite_path)


if __name__ == "__main__":
    sys.exit(main())
