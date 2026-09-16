"""Dra. Waleska Paula — Aplicativo + Painel Administrativo.

Servidor Flask com banco SQLite persistente.
Serve as páginas públicas existentes e a área administrativa /admin.
"""

import json
import os
import secrets
import sqlite3
from datetime import datetime
from functools import wraps

from flask import Flask, g, jsonify, redirect, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "waleska.db")
SECRET_PATH = os.path.join(DATA_DIR, "secret_key")

os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__, static_folder=None)

if os.path.exists(SECRET_PATH):
    with open(SECRET_PATH, "r") as f:
        app.secret_key = f.read().strip()
else:
    app.secret_key = secrets.token_hex(32)
    with open(SECRET_PATH, "w") as f:
        f.write(app.secret_key)
    os.chmod(SECRET_PATH, 0o600)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False,
)


@app.after_request
def add_no_cache_headers(response):
    if request.path.startswith(("/css/", "/js/", "/admin/css/", "/admin/js/")):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

STATUS_LIST = [
    "Novo",
    "Aguardando avaliação",
    "Aguardando dupla",
    "Em atendimento",
    "Lista de espera",
    "Finalizado",
]

DEFAULT_SERVICES = [
    {
        "nome": "Pilates Clínico",
        "descricao": "Exercícios individualizados que fortalecem o corpo com segurança, respeitando limitações e histórico de cada pessoa.",
        "valor": 90.0,
        "info_adicional": "Sessões de 50 minutos. Pacote mensal com condições especiais.",
        "ativo": 1,
        "ordem": 1,
        "icone": "pilates",
        "lista_espera": 1,
    },
    {
        "nome": "Fisioterapia Ortopédica",
        "descricao": "Tratamento de dores e lesões musculoesqueléticas com técnicas manuais e exercícios terapêuticos.",
        "valor": 120.0,
        "info_adicional": "Avaliação inicial incluída na primeira sessão.",
        "ativo": 1,
        "ordem": 2,
        "icone": "ortopedica",
        "lista_espera": 0,
    },
    {
        "nome": "RPG — Reeducação Postural",
        "descricao": "Correção postural por posturas globais que alongam e reequilibram cadeias musculares.",
        "valor": 140.0,
        "info_adicional": "Sessões de 60 minutos com acompanhamento individual.",
        "ativo": 1,
        "ordem": 3,
        "icone": "rpg",
        "lista_espera": 0,
    },
    {
        "nome": "Liberação Miofascial",
        "descricao": "Técnicas manuais que aliviam tensões, melhoram a mobilidade e reduzem dores crônicas.",
        "valor": 100.0,
        "info_adicional": "Ótima opção para quem sente tensões diárias.",
        "ativo": 1,
        "ordem": 4,
        "icone": "miofascial",
        "lista_espera": 0,
    },
    {
        "nome": "Pilates para Gestantes",
        "descricao": "Acompanhamento especializado para manter o corpo forte e preparado durante a gestação.",
        "valor": 90.0,
        "info_adicional": "Aulas adaptadas a cada fase da gestação, com liberação do obstetra.",
        "ativo": 1,
        "ordem": 5,
        "icone": "gestantes",
        "lista_espera": 1,
    },
    {
        "nome": "Fisioterapia Esportiva",
        "descricao": "Prevenção e recuperação de lesões para quem pratica atividades físicas e esportes.",
        "valor": 120.0,
        "info_adicional": "Atendimento voltado a atletas e praticantes de atividades físicas.",
        "ativo": 1,
        "ordem": 6,
        "icone": "esportiva",
        "lista_espera": 0,
    },
]


# ---------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def calc_idade(nascimento):
    if not nascimento:
        return None
    try:
        dt = datetime.strptime(nascimento, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    hoje = datetime.now()
    idade = hoje.year - dt.year - ((hoje.month, hoje.day) < (dt.month, dt.day))
    return max(idade, 0)


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            criadoEm TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            descricao TEXT NOT NULL DEFAULT '',
            valor REAL NOT NULL DEFAULT 0,
            info_adicional TEXT NOT NULL DEFAULT '',
            icone TEXT NOT NULL DEFAULT 'padrao',
            lista_espera INTEGER NOT NULL DEFAULT 0,
            ativo INTEGER NOT NULL DEFAULT 1,
            ordem INTEGER NOT NULL DEFAULT 0,
            criadoEm TEXT NOT NULL,
            atualizadoEm TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            nascimento TEXT,
            telefone TEXT NOT NULL,
            servico_id INTEGER,
            servico TEXT NOT NULL,
            valor REAL,
            dias TEXT,
            frequencia TEXT,
            motivos TEXT,
            observacoes TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Novo',
            criadoEm TEXT NOT NULL,
            atualizadoEm TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS waitlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_id INTEGER,
            nome TEXT NOT NULL,
            nascimento TEXT,
            idade INTEGER,
            telefone TEXT NOT NULL,
            servico TEXT NOT NULL,
            dificuldades TEXT NOT NULL DEFAULT '',
            observacoes TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Lista de espera',
            criadoEm TEXT NOT NULL,
            atualizadoEm TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS duplas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paciente1 TEXT NOT NULL,
            paciente2 TEXT NOT NULL,
            servico TEXT NOT NULL,
            observacoes TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Em dupla',
            criadaEm TEXT NOT NULL,
            atualizadoEm TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL DEFAULT '[]',
            atualizadoEm TEXT NOT NULL
        );
        """
    )
    db.commit()

    # Seed default admin
    cur = db.execute("SELECT COUNT(*) AS c FROM admins")
    if cur.fetchone()["c"] == 0:
        default_email = os.environ.get("ADMIN_EMAIL", "admin@waleskapaula.com.br")
        default_password = os.environ.get("ADMIN_PASSWORD", "waleska2024")
        db.execute(
            "INSERT INTO admins (email, password_hash, criadoEm) VALUES (?, ?, ?)",
            (default_email.lower(), generate_password_hash(default_password), now_iso()),
        )

    # Seed default services
    cur = db.execute("SELECT COUNT(*) AS c FROM services")
    if cur.fetchone()["c"] == 0:
        for s in DEFAULT_SERVICES:
            db.execute(
                """INSERT INTO services
                   (nome, descricao, valor, info_adicional, icone, lista_espera, ativo, ordem, criadoEm, atualizadoEm)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (s["nome"], s["descricao"], s["valor"], s["info_adicional"], s["icone"],
                 s["lista_espera"], s["ativo"], s["ordem"], now_iso(), now_iso()),
            )

    # Seed formulário de cadastro (opções dos chips)
    cur = db.execute("SELECT COUNT(*) AS c FROM settings")
    if cur.fetchone()["c"] == 0:
        form_defaults = {
            "dias": ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"],
            "frequencias": ["1x por semana", "2x por semana", "3x por semana", "Mais de 3x por semana"],
            "motivos": [
                "Fortalecer o corpo",
                "Melhorar a postura",
                "Aliviar dores",
                "Ganhar flexibilidade",
                "Cuidar da mente",
                "Reabilitação",
            ],
        }
        for chave, valores in form_defaults.items():
            db.execute(
                "INSERT INTO settings (chave, valor, atualizadoEm) VALUES (?, ?, ?)",
                (chave, json.dumps(valores, ensure_ascii=False), now_iso()),
            )
    db.commit()
    db.close()


# ---------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------

def current_admin():
    admin_id = session.get("admin_id")
    if not admin_id:
        return None
    return get_db().execute("SELECT * FROM admins WHERE id = ?", (admin_id,)).fetchone()


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_admin():
            return jsonify({"ok": False, "error": "Não autenticado"}), 401
        return f(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------
# Static pages (públicas preservadas)
# ---------------------------------------------------------------

@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/css/<path:filename>")
def public_css(filename):
    return send_from_directory(os.path.join(BASE_DIR, "css"), filename)


@app.route("/js/<path:filename>")
def public_js(filename):
    return send_from_directory(os.path.join(BASE_DIR, "js"), filename)


@app.route("/assets/<path:filename>")
def public_assets(filename):
    return send_from_directory(os.path.join(BASE_DIR, "assets"), filename)


# ---------------------------------------------------------------
# Admin pages
# ---------------------------------------------------------------

@app.route("/admin-login")
def admin_login_page():
    return send_from_directory(BASE_DIR, "admin-login.html")


@app.route("/admin")
@app.route("/admin/")
@app.route("/admin/<path:section>")
def admin_page(section=None):
    if not current_admin():
        return redirect("/admin-login")
    return send_from_directory(BASE_DIR, "admin.html")


@app.route("/admin/css/<path:filename>")
def admin_css(filename):
    return send_from_directory(os.path.join(BASE_DIR, "admin", "css"), filename)


@app.route("/admin/js/<path:filename>")
def admin_js(filename):
    return send_from_directory(os.path.join(BASE_DIR, "admin", "js"), filename)


# ---------------------------------------------------------------
# Auth API
# ---------------------------------------------------------------

@app.route("/api/admin/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    senha = data.get("senha") or ""

    if not email or not senha:
        return jsonify({"ok": False, "error": "Informe e-mail e senha."}), 400

    admin = get_db().execute("SELECT * FROM admins WHERE email = ?", (email,)).fetchone()
    if not admin or not check_password_hash(admin["password_hash"], senha):
        return jsonify({"ok": False, "error": "E-mail ou senha incorretos."}), 401

    session.clear()
    session["admin_id"] = admin["id"]
    return jsonify({"ok": True, "data": {"email": admin["email"]}})


@app.route("/api/admin/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/admin/me")
def api_me():
    admin = current_admin()
    if not admin:
        return jsonify({"ok": False, "error": "Não autenticado"}), 401
    return jsonify({"ok": True, "data": {"email": admin["email"]}})


# ---------------------------------------------------------------
# Serviços — API pública (apenas ativos)
# ---------------------------------------------------------------

def row_to_service(r):
    return {
        "id": r["id"],
        "nome": r["nome"],
        "descricao": r["descricao"],
        "valor": r["valor"],
        "info_adicional": r["info_adicional"],
        "icone": r["icone"],
        "lista_espera": bool(r["lista_espera"]),
        "ativo": bool(r["ativo"]),
        "ordem": r["ordem"],
        "criadoEm": r["criadoEm"],
        "atualizadoEm": r["atualizadoEm"],
    }


@app.route("/api/services")
def api_public_services():
    rows = get_db().execute(
        "SELECT * FROM services WHERE ativo = 1 ORDER BY ordem, nome"
    ).fetchall()
    return jsonify({"ok": True, "data": [row_to_service(r) for r in rows]})


def get_cadastro_config():
    db = get_db()
    cfg = {"dias": [], "frequencias": [], "motivos": []}
    rows = db.execute(
        "SELECT chave, valor FROM settings WHERE chave IN ('dias', 'frequencias', 'motivos')"
    ).fetchall()
    for row in rows:
        try:
            cfg[row["chave"]] = json.loads(row["valor"] or "[]")
        except (ValueError, TypeError):
            cfg[row["chave"]] = []
    return cfg


@app.route("/api/cadastro-config")
def api_public_cadastro_config():
    return jsonify({"ok": True, "data": get_cadastro_config()})


# ---------------------------------------------------------------
# Cadastro público
# ---------------------------------------------------------------

@app.route("/api/cadastros", methods=["POST"])
def api_public_cadastro():
    data = request.get_json(silent=True) or {}
    nome = (data.get("nome") or "").strip()
    nascimento = (data.get("nascimento") or "").strip() or None
    telefone = (data.get("telefone") or "").strip()
    servico_id = data.get("servico_id")
    servico_nome = (data.get("servico") or "").strip()
    dias = data.get("dias") or []
    frequencia = (data.get("frequencia") or "").strip()
    motivos = data.get("motivos") or []
    observacoes = (data.get("observacoes") or "").strip()

    if not nome or not telefone:
        return jsonify({"ok": False, "error": "Nome e telefone são obrigatórios."}), 400

    db = get_db()
    service = None
    if servico_id:
        service = db.execute("SELECT * FROM services WHERE id = ?", (servico_id,)).fetchone()
    if not service and servico_nome:
        service = db.execute("SELECT * FROM services WHERE nome = ?", (servico_nome,)).fetchone()

    if not service:
        return jsonify({"ok": False, "error": "Serviço não encontrado. Escolha um serviço válido."}), 400

    servico_final = service["nome"]
    status = "Lista de espera" if service["lista_espera"] else "Novo"
    ts = now_iso()

    cur = db.execute(
        """INSERT INTO registrations
           (nome, nascimento, telefone, servico_id, servico, valor, dias, frequencia, motivos, observacoes, status, criadoEm, atualizadoEm)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (nome, nascimento, telefone, service["id"], servico_final, service["valor"],
         json.dumps(dias, ensure_ascii=False), frequencia,
         json.dumps(motivos, ensure_ascii=False), observacoes, status, ts, ts),
    )
    registration_id = cur.lastrowid

    entrou_lista = False
    if service["lista_espera"]:
        idade = calc_idade(nascimento)
        dificuldades = "; ".join(motivos) if motivos else "Não informado"
        db.execute(
            """INSERT INTO waitlist
               (registration_id, nome, nascimento, idade, telefone, servico, dificuldades, observacoes, status, criadoEm, atualizadoEm)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Lista de espera', ?, ?)""",
            (registration_id, nome, nascimento, idade, telefone, servico_final,
             dificuldades, observacoes, ts, ts),
        )
        entrou_lista = True

    db.commit()

    return jsonify({
        "ok": True,
        "data": {
            "id": registration_id,
            "lista_espera": entrou_lista,
            "status": status,
        },
    }), 201


# ---------------------------------------------------------------
# Serviços — API administrativa
# ---------------------------------------------------------------

@app.route("/api/admin/services", methods=["GET"])
@login_required
def api_admin_services():
    rows = get_db().execute("SELECT * FROM services ORDER BY ordem, nome").fetchall()
    return jsonify({"ok": True, "data": [row_to_service(r) for r in rows]})


@app.route("/api/admin/services", methods=["POST"])
@login_required
def api_admin_services_create():
    data = request.get_json(silent=True) or {}
    nome = (data.get("nome") or "").strip()
    descricao = (data.get("descricao") or "").strip()
    valor = data.get("valor")
    info_adicional = (data.get("info_adicional") or "").strip()
    icone = (data.get("icone") or "padrao").strip()
    lista_espera = 1 if data.get("lista_espera") else 0
    ativo = 1 if data.get("ativo") is not False else 1
    ordem = data.get("ordem")

    if not nome:
        return jsonify({"ok": False, "error": "O nome do serviço é obrigatório."}), 400
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        valor = 0.0

    db = get_db()
    if ordem is None:
        row = db.execute("SELECT COALESCE(MAX(ordem), 0) AS m FROM services").fetchone()
        ordem = row["m"] + 1

    ts = now_iso()
    cur = db.execute(
        """INSERT INTO services
           (nome, descricao, valor, info_adicional, icone, lista_espera, ativo, ordem, criadoEm, atualizadoEm)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (nome, descricao, valor, info_adicional, icone, lista_espera, ativo, ordem, ts, ts),
    )
    db.commit()
    row = db.execute("SELECT * FROM services WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify({"ok": True, "data": row_to_service(row)}), 201


@app.route("/api/admin/services/<int:service_id>", methods=["PUT"])
@login_required
def api_admin_services_update(service_id):
    data = request.get_json(silent=True) or {}
    db = get_db()
    row = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Serviço não encontrado."}), 404

    nome = (data.get("nome") if data.get("nome") is not None else row["nome"]).strip()
    descricao = (data.get("descricao") if data.get("descricao") is not None else row["descricao"]).strip()
    info_adicional = (data.get("info_adicional") if data.get("info_adicional") is not None else row["info_adicional"]).strip()
    icone = (data.get("icone") if data.get("icone") is not None else row["icone"]).strip()
    ativo = 1 if data.get("ativo") is not False else (1 if row["ativo"] else 0)
    lista_espera = 1 if data.get("lista_espera") else (1 if row["lista_espera"] else 0)
    ordem = data.get("ordem") if data.get("ordem") is not None else row["ordem"]

    if not nome:
        return jsonify({"ok": False, "error": "O nome do serviço é obrigatório."}), 400
    try:
        valor = float(data.get("valor", row["valor"]))
    except (TypeError, ValueError):
        valor = row["valor"]

    db.execute(
        """UPDATE services SET nome = ?, descricao = ?, valor = ?, info_adicional = ?,
           icone = ?, lista_espera = ?, ativo = ?, ordem = ?, atualizadoEm = ?
           WHERE id = ?""",
        (nome, descricao, valor, info_adicional, icone, lista_espera, ativo, ordem, now_iso(), service_id),
    )
    db.commit()
    updated = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    return jsonify({"ok": True, "data": row_to_service(updated)})


@app.route("/api/admin/services/<int:service_id>", methods=["DELETE"])
@login_required
def api_admin_services_delete(service_id):
    db = get_db()
    row = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Serviço não encontrado."}), 404
    db.execute("DELETE FROM services WHERE id = ?", (service_id,))
    db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------
# Cadastros — API administrativa
# ---------------------------------------------------------------

def row_to_registration(r):
    return {
        "id": r["id"],
        "nome": r["nome"],
        "nascimento": r["nascimento"],
        "idade": calc_idade(r["nascimento"]),
        "telefone": r["telefone"],
        "servico_id": r["servico_id"],
        "servico": r["servico"],
        "valor": r["valor"],
        "dias": json.loads(r["dias"]) if r["dias"] else [],
        "frequencia": r["frequencia"],
        "motivos": json.loads(r["motivos"]) if r["motivos"] else [],
        "observacoes": r["observacoes"],
        "status": r["status"],
        "criadoEm": r["criadoEm"],
        "atualizadoEm": r["atualizadoEm"],
    }


@app.route("/api/admin/cadastros")
@login_required
def api_admin_cadastros():
    q = (request.args.get("q") or "").strip()
    servico = (request.args.get("servico") or "").strip()
    status = (request.args.get("status") or "").strip()

    sql = "SELECT * FROM registrations WHERE 1=1"
    params = []
    if q:
        sql += " AND (nome LIKE ? OR telefone LIKE ?)"
        params += ["%" + q + "%", "%" + q + "%"]
    if servico:
        sql += " AND servico = ?"
        params.append(servico)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY criadoEm DESC, id DESC"

    rows = get_db().execute(sql, params).fetchall()
    return jsonify({"ok": True, "data": [row_to_registration(r) for r in rows]})


@app.route("/api/admin/cadastros/<int:reg_id>", methods=["GET"])
@login_required
def api_admin_cadastro_get(reg_id):
    row = get_db().execute("SELECT * FROM registrations WHERE id = ?", (reg_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Cadastro não encontrado."}), 404
    return jsonify({"ok": True, "data": row_to_registration(row)})


@app.route("/api/admin/cadastros/<int:reg_id>", methods=["PUT"])
@login_required
def api_admin_cadastro_update(reg_id):
    data = request.get_json(silent=True) or {}
    db = get_db()
    row = db.execute("SELECT * FROM registrations WHERE id = ?", (reg_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Cadastro não encontrado."}), 404

    nome = (data.get("nome") if data.get("nome") is not None else row["nome"]).strip()
    nascimento = (data.get("nascimento") if data.get("nascimento") is not None else row["nascimento"]).strip() or None
    telefone = (data.get("telefone") if data.get("telefone") is not None else row["telefone"]).strip()
    observacoes = (data.get("observacoes") if data.get("observacoes") is not None else row["observacoes"]).strip()
    status = (data.get("status") if data.get("status") is not None else row["status"]).strip()
    dias = data.get("dias") if data.get("dias") is not None else json.loads(row["dias"]) if row["dias"] else []
    frequencia = (data.get("frequencia") if data.get("frequencia") is not None else row["frequencia"]).strip()
    motivos = data.get("motivos") if data.get("motivos") is not None else json.loads(row["motivos"]) if row["motivos"] else []

    if not nome or not telefone:
        return jsonify({"ok": False, "error": "Nome e telefone são obrigatórios."}), 400

    db.execute(
        """UPDATE registrations SET nome = ?, nascimento = ?, telefone = ?, dias = ?,
           frequencia = ?, motivos = ?, observacoes = ?, status = ?, atualizadoEm = ?
           WHERE id = ?""",
        (nome, nascimento, telefone, json.dumps(dias, ensure_ascii=False), frequencia,
         json.dumps(motivos, ensure_ascii=False), observacoes, status, now_iso(), reg_id),
    )
    db.commit()

    # Mantém a lista de espera sincronizada quando o status é alterado
    wl = db.execute("SELECT * FROM waitlist WHERE registration_id = ?", (reg_id,)).fetchone()
    if wl:
        if status == "Finalizado" or status == "Em atendimento":
            db.execute("UPDATE waitlist SET status = ?, atualizadoEm = ? WHERE id = ?",
                       (status, now_iso(), wl["id"]))
        elif status == "Lista de espera" or status == "Aguardando dupla":
            db.execute("UPDATE waitlist SET status = ?, atualizadoEm = ? WHERE id = ?",
                       (status, now_iso(), wl["id"]))
        db.commit()

    updated = db.execute("SELECT * FROM registrations WHERE id = ?", (reg_id,)).fetchone()
    return jsonify({"ok": True, "data": row_to_registration(updated)})


@app.route("/api/admin/cadastros/<int:reg_id>", methods=["DELETE"])
@login_required
def api_admin_cadastro_delete(reg_id):
    db = get_db()
    db.execute("DELETE FROM waitlist WHERE registration_id = ?", (reg_id,))
    db.execute("DELETE FROM registrations WHERE id = ?", (reg_id,))
    db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------
# Lista de espera — API administrativa
# ---------------------------------------------------------------

def row_to_waitlist(r):
    return {
        "id": r["id"],
        "registration_id": r["registration_id"],
        "nome": r["nome"],
        "nascimento": r["nascimento"],
        "idade": r["idade"],
        "telefone": r["telefone"],
        "servico": r["servico"],
        "dificuldades": r["dificuldades"],
        "observacoes": r["observacoes"],
        "status": r["status"],
        "criadoEm": r["criadoEm"],
        "atualizadoEm": r["atualizadoEm"],
    }


@app.route("/api/admin/lista-espera")
@login_required
def api_admin_waitlist():
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip()
    sql = "SELECT * FROM waitlist WHERE 1=1"
    params = []
    if q:
        sql += " AND (nome LIKE ? OR telefone LIKE ?)"
        params += ["%" + q + "%", "%" + q + "%"]
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY criadoEm DESC, id DESC"
    rows = get_db().execute(sql, params).fetchall()
    return jsonify({"ok": True, "data": [row_to_waitlist(r) for r in rows]})


@app.route("/api/admin/lista-espera/<int:wl_id>", methods=["PUT"])
@login_required
def api_admin_waitlist_update(wl_id):
    data = request.get_json(silent=True) or {}
    db = get_db()
    row = db.execute("SELECT * FROM waitlist WHERE id = ?", (wl_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Registro não encontrado."}), 404

    nome = (data.get("nome") if data.get("nome") is not None else row["nome"]).strip()
    nascimento = (data.get("nascimento") if data.get("nascimento") is not None else row["nascimento"]).strip() or None
    telefone = (data.get("telefone") if data.get("telefone") is not None else row["telefone"]).strip()
    dificuldades = (data.get("dificuldades") if data.get("dificuldades") is not None else row["dificuldades"]).strip()
    observacoes = (data.get("observacoes") if data.get("observacoes") is not None else row["observacoes"]).strip()
    status = (data.get("status") if data.get("status") is not None else row["status"]).strip()
    idade = calc_idade(nascimento)

    db.execute(
        """UPDATE waitlist SET nome = ?, nascimento = ?, idade = ?, telefone = ?,
           dificuldades = ?, observacoes = ?, status = ?, atualizadoEm = ? WHERE id = ?""",
        (nome, nascimento, idade, telefone, dificuldades, observacoes, status, now_iso(), wl_id),
    )
    db.commit()
    updated = db.execute("SELECT * FROM waitlist WHERE id = ?", (wl_id,)).fetchone()
    return jsonify({"ok": True, "data": row_to_waitlist(updated)})


@app.route("/api/admin/lista-espera/<int:wl_id>", methods=["DELETE"])
@login_required
def api_admin_waitlist_delete(wl_id):
    db = get_db()
    row = db.execute("SELECT * FROM waitlist WHERE id = ?", (wl_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Registro não encontrado."}), 404
    db.execute("DELETE FROM waitlist WHERE id = ?", (wl_id,))
    db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------
# Duplas — API administrativa
# ---------------------------------------------------------------

def row_to_dupla(r):
    return {
        "id": r["id"],
        "paciente1": json.loads(r["paciente1"]),
        "paciente2": json.loads(r["paciente2"]),
        "servico": r["servico"],
        "observacoes": r["observacoes"],
        "status": r["status"],
        "criadaEm": r["criadaEm"],
        "atualizadoEm": r["atualizadoEm"],
    }


@app.route("/api/admin/duplas", methods=["GET"])
@login_required
def api_admin_duplas():
    rows = get_db().execute("SELECT * FROM duplas ORDER BY criadaEm DESC, id DESC").fetchall()
    return jsonify({"ok": True, "data": [row_to_dupla(r) for r in rows]})


@app.route("/api/admin/duplas", methods=["POST"])
@login_required
def api_admin_duplas_create():
    data = request.get_json(silent=True) or {}
    wl1_id = data.get("paciente1_id")
    wl2_id = data.get("paciente2_id")
    observacoes = (data.get("observacoes") or "").strip()

    if not wl1_id or not wl2_id:
        return jsonify({"ok": False, "error": "Selecione os dois pacientes."}), 400
    if wl1_id == wl2_id:
        return jsonify({"ok": False, "error": "Os dois pacientes devem ser diferentes."}), 400

    db = get_db()
    wl1 = db.execute("SELECT * FROM waitlist WHERE id = ?", (wl1_id,)).fetchone()
    wl2 = db.execute("SELECT * FROM waitlist WHERE id = ?", (wl2_id,)).fetchone()
    if not wl1 or not wl2:
        return jsonify({"ok": False, "error": "Paciente não encontrado na lista de espera."}), 404

    servico = wl1["servico"] if wl1["servico"] == wl2["servico"] else (wl1["servico"] + " / " + wl2["servico"])
    ts = now_iso()

    def snapshot(wl):
        return {
            "waitlist_id": wl["id"],
            "registration_id": wl["registration_id"],
            "nome": wl["nome"],
            "nascimento": wl["nascimento"],
            "idade": wl["idade"],
            "telefone": wl["telefone"],
            "servico": wl["servico"],
            "dificuldades": wl["dificuldades"],
            "observacoes": wl["observacoes"],
        }

    cur = db.execute(
        """INSERT INTO duplas (paciente1, paciente2, servico, observacoes, status, criadaEm, atualizadoEm)
           VALUES (?, ?, ?, ?, 'Em dupla', ?, ?)""",
        (json.dumps(snapshot(wl1), ensure_ascii=False),
         json.dumps(snapshot(wl2), ensure_ascii=False),
         servico, observacoes, ts, ts),
    )

    # Remove os dois da lista de espera e atualiza status dos cadastros
    db.execute("DELETE FROM waitlist WHERE id IN (?, ?)", (wl1_id, wl2_id))
    for wl in (wl1, wl2):
        if wl["registration_id"]:
            db.execute(
                "UPDATE registrations SET status = 'Em atendimento', atualizadoEm = ? WHERE id = ?",
                (ts, wl["registration_id"]),
            )

    db.commit()
    dupla = db.execute("SELECT * FROM duplas WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify({"ok": True, "data": row_to_dupla(dupla)}), 201


@app.route("/api/admin/duplas/<int:dupla_id>", methods=["GET"])
@login_required
def api_admin_dupla_get(dupla_id):
    row = get_db().execute("SELECT * FROM duplas WHERE id = ?", (dupla_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Dupla não encontrada."}), 404
    return jsonify({"ok": True, "data": row_to_dupla(row)})


@app.route("/api/admin/duplas/<int:dupla_id>", methods=["PUT"])
@login_required
def api_admin_dupla_update(dupla_id):
    data = request.get_json(silent=True) or {}
    db = get_db()
    row = db.execute("SELECT * FROM duplas WHERE id = ?", (dupla_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Dupla não encontrada."}), 404

    observacoes = (data.get("observacoes") if data.get("observacoes") is not None else row["observacoes"]).strip()
    status = (data.get("status") if data.get("status") is not None else row["status"]).strip()

    paciente1 = row["paciente1"]
    paciente2 = row["paciente2"]
    servico = row["servico"]

    # Trocar paciente: data pode trazer paciente1/paciente2 como IDs da waitlist
    swap_p1 = data.get("trocar_paciente1")
    swap_p2 = data.get("trocar_paciente2")

    def snapshot(wl):
        return {
            "waitlist_id": wl["id"],
            "registration_id": wl["registration_id"],
            "nome": wl["nome"],
            "nascimento": wl["nascimento"],
            "idade": wl["idade"],
            "telefone": wl["telefone"],
            "servico": wl["servico"],
            "dificuldades": wl["dificuldades"],
            "observacoes": wl["observacoes"],
        }

    ts = now_iso()
    # Manter os pacientes atuais fora da lista de espera (já removidos na criação)
    # Para "trocar um paciente": o paciente que sai volta para a lista de espera
    def return_to_waitlist(old_patient):
        if not old_patient:
            return
        old = json.loads(old_patient) if isinstance(old_patient, str) else old_patient
        db.execute(
            """INSERT INTO waitlist
               (registration_id, nome, nascimento, idade, telefone, servico, dificuldades, observacoes, status, criadoEm, atualizadoEm)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Lista de espera', ?, ?)""",
            (old.get("registration_id"), old.get("nome"), old.get("nascimento"),
             old.get("idade"), old.get("telefone"), old.get("servico"),
             old.get("dificuldades"), old.get("observacoes"), ts, ts),
        )
        if old.get("registration_id"):
            db.execute(
                "UPDATE registrations SET status = 'Lista de espera', atualizadoEm = ? WHERE id = ?",
                (ts, old["registration_id"]),
            )

    if swap_p1:
        wl_new = db.execute("SELECT * FROM waitlist WHERE id = ?", (swap_p1,)).fetchone()
        if not wl_new:
            return jsonify({"ok": False, "error": "Paciente substituto não encontrado."}), 404
        return_to_waitlist(paciente1)
        db.execute("DELETE FROM waitlist WHERE id = ?", (swap_p1,))
        paciente1 = json.dumps(snapshot(wl_new), ensure_ascii=False)

    if swap_p2:
        wl_new = db.execute("SELECT * FROM waitlist WHERE id = ?", (swap_p2,)).fetchone()
        if not wl_new:
            return jsonify({"ok": False, "error": "Paciente substituto não encontrado."}), 404
        return_to_waitlist(paciente2)
        db.execute("DELETE FROM waitlist WHERE id = ?", (swap_p2,))
        paciente2 = json.dumps(snapshot(wl_new), ensure_ascii=False)

    db.execute(
        """UPDATE duplas SET paciente1 = ?, paciente2 = ?, servico = ?, observacoes = ?,
           status = ?, atualizadoEm = ? WHERE id = ?""",
        (paciente1, paciente2, servico, observacoes, status, ts, dupla_id),
    )
    db.commit()
    updated = db.execute("SELECT * FROM duplas WHERE id = ?", (dupla_id,)).fetchone()
    return jsonify({"ok": True, "data": row_to_dupla(updated)})


@app.route("/api/admin/duplas/<int:dupla_id>", methods=["DELETE"])
@login_required
def api_admin_dupla_delete(dupla_id):
    """Desfaz a dupla: remove-a e devolve os pacientes à lista de espera."""
    db = get_db()
    row = db.execute("SELECT * FROM duplas WHERE id = ?", (dupla_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Dupla não encontrada."}), 404

    ts = now_iso()
    for patient in (row["paciente1"], row["paciente2"]):
        p = json.loads(patient) if isinstance(patient, str) else patient
        db.execute(
            """INSERT INTO waitlist
               (registration_id, nome, nascimento, idade, telefone, servico, dificuldades, observacoes, status, criadoEm, atualizadoEm)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Lista de espera', ?, ?)""",
            (p.get("registration_id"), p.get("nome"), p.get("nascimento"),
             p.get("idade"), p.get("telefone"), p.get("servico"),
             p.get("dificuldades"), p.get("observacoes"), ts, ts),
        )
        if p.get("registration_id"):
            db.execute(
                "UPDATE registrations SET status = 'Lista de espera', atualizadoEm = ? WHERE id = ?",
                (ts, p["registration_id"]),
            )

    db.execute("DELETE FROM duplas WHERE id = ?", (dupla_id,))
    db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------
# Configurações
# ---------------------------------------------------------------

@app.route("/api/admin/config", methods=["GET"])
@login_required
def api_admin_config_get():
    admin = current_admin()
    return jsonify({"ok": True, "data": {"email": admin["email"]}})


@app.route("/api/admin/cadastro-config", methods=["GET"])
@login_required
def api_admin_cadastro_config_get():
    return jsonify({"ok": True, "data": get_cadastro_config()})


@app.route("/api/admin/cadastro-config", methods=["PUT"])
@login_required
def api_admin_cadastro_config_update():
    data = request.get_json(silent=True) or {}
    db = get_db()
    ts = now_iso()
    updated = {}
    for chave in ("dias", "frequencias", "motivos"):
        if chave not in data:
            continue
        valores = data[chave]
        if not isinstance(valores, list):
            return jsonify({"ok": False, "error": "Formato inválido para " + chave + "."}), 400
        limpos = []
        vistos = set()
        for v in valores:
            v = str(v).strip()
            if v and v not in vistos:
                limpos.append(v)
                vistos.add(v)
        if not limpos:
            return jsonify({"ok": False, "error": "Cada grupo precisa de ao menos uma opção."}), 400
        db.execute(
            """INSERT INTO settings (chave, valor, atualizadoEm)
               VALUES (?, ?, ?)
               ON CONFLICT(chave) DO UPDATE SET
                   valor = excluded.valor,
                   atualizadoEm = excluded.atualizadoEm""",
            (chave, json.dumps(limpos, ensure_ascii=False), ts),
        )
        updated[chave] = limpos
    db.commit()
    return jsonify({"ok": True, "data": updated})


@app.route("/api/admin/config", methods=["PUT"])
@login_required
def api_admin_config_update():
    data = request.get_json(silent=True) or {}
    db = get_db()
    admin = current_admin()

    email = (data.get("email") or admin["email"]).strip().lower()
    senha_atual = data.get("senha_atual") or ""
    nova_senha = data.get("nova_senha") or ""
    confirmar = data.get("confirmar") or ""

    if not email:
        return jsonify({"ok": False, "error": "Informe um e-mail válido."}), 400

    # Troca de senha exige confirmação da senha atual
    if nova_senha or senha_atual:
        if not check_password_hash(admin["password_hash"], senha_atual):
            return jsonify({"ok": False, "error": "Senha atual incorreta."}), 400
        if len(nova_senha) < 6:
            return jsonify({"ok": False, "error": "A nova senha deve ter ao menos 6 caracteres."}), 400
        if nova_senha != confirmar:
            return jsonify({"ok": False, "error": "As senhas não conferem."}), 400
        novo_hash = generate_password_hash(nova_senha)
        db.execute("UPDATE admins SET email = ?, password_hash = ? WHERE id = ?",
                   (email, novo_hash, admin["id"]))
    else:
        db.execute("UPDATE admins SET email = ? WHERE id = ?", (email, admin["id"]))

    db.commit()
    return jsonify({"ok": True, "data": {"email": email}})


@app.route("/api/admin/overview")
@login_required
def api_admin_overview():
    db = get_db()
    total = db.execute("SELECT COUNT(*) AS c FROM registrations").fetchone()["c"]
    aguardando = db.execute(
        "SELECT COUNT(*) AS c FROM registrations WHERE status IN ('Novo', 'Aguardando avaliação', 'Aguardando dupla')"
    ).fetchone()["c"]
    lista_espera = db.execute(
        "SELECT COUNT(*) AS c FROM waitlist WHERE status IN ('Lista de espera', 'Aguardando dupla')"
    ).fetchone()["c"]
    duplas = db.execute("SELECT COUNT(*) AS c FROM duplas").fetchone()["c"]
    servicos_ativos = db.execute("SELECT COUNT(*) AS c FROM services WHERE ativo = 1").fetchone()["c"]

    return jsonify({
        "ok": True,
        "data": {
            "total_cadastros": total,
            "aguardando_atendimento": aguardando,
            "lista_espera": lista_espera,
            "duplas": duplas,
            "servicos_ativos": servicos_ativos,
        },
    })


init_db()

if __name__ == "__main__":
    print("=" * 60)
    print("Dra. Waleska Paula — servidor iniciado")
    print("Página pública : http://localhost:8000/")
    print("Painel admin   : http://localhost:8000/admin")
    print("=" * 60)
    app.run(host="0.0.0.0", port=8000, debug=False, threaded=True)
