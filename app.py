"""Dra. Waleska Paula — Aplicativo + Painel Administrativo.

Servidor Flask. Persistencia principal: PostgreSQL/Supabase via DATABASE_URL.
SQLite em data/waleska.db permanece como fallback local.
Serve as paginas publicas existentes e a area administrativa /admin.
"""

import json
import os
import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, jsonify, redirect, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

from db import backend_label, close_db as close_db_connection, get_db, using_postgres

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "waleska.db")
SECRET_PATH = os.path.join(DATA_DIR, "secret_key")
ENV_PATH = os.path.join(BASE_DIR, ".env")

os.makedirs(DATA_DIR, exist_ok=True)


def load_env_file(path):
    """Carrega variáveis de um arquivo .env sem dependências externas.

    Formato suportado: linhas CHAVE=valor, comentários com # e valores
    opcionalmente entre aspas. Não sobrescreve variáveis já definidas no
    ambiente do processo.
    """
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                chave, _, valor = line.partition("=")
                chave = chave.strip()
                valor = valor.strip()
                if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ("'", '"'):
                    valor = valor[1:-1]
                if chave:
                    os.environ.setdefault(chave, valor)
    except OSError:
        pass


load_env_file(ENV_PATH)

# postgres/supabase = DATABASE_URL; sqlite = fallback local.
DB_BACKEND = backend_label()

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

@app.teardown_appcontext
def close_db(exc):
    close_db_connection(exc)


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


def decode_json(value, default=None):
    if default is None:
        default = []
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def init_db():
    if using_postgres():
        return
    import sqlite3

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

        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            patient_name TEXT NOT NULL,
            service_id INTEGER,
            service_name TEXT NOT NULL DEFAULT '',
            dupla_id INTEGER,
            starts_at TEXT NOT NULL,
            ends_at TEXT,
            duration_min INTEGER NOT NULL DEFAULT 50,
            status TEXT NOT NULL DEFAULT 'Agendado',
            notes TEXT NOT NULL DEFAULT '',
            criadoEm TEXT NOT NULL,
            atualizadoEm TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_appointments_starts ON appointments(starts_at);
        CREATE INDEX IF NOT EXISTS idx_appointments_patient ON appointments(patient_id);

        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            patient_name TEXT NOT NULL DEFAULT '',
            appointment_id INTEGER,
            service_id INTEGER,
            amount REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'Pendente',
            paid_at TEXT,
            notes TEXT NOT NULL DEFAULT '',
            criadoEm TEXT NOT NULL,
            atualizadoEm TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            patient_name TEXT NOT NULL DEFAULT '',
            evaluated_at TEXT NOT NULL,
            queixa TEXT NOT NULL DEFAULT '',
            objetivos TEXT NOT NULL DEFAULT '',
            historico TEXT NOT NULL DEFAULT '',
            avaliacao_funcional TEXT NOT NULL DEFAULT '',
            plano TEXT NOT NULL DEFAULT '',
            observacoes TEXT NOT NULL DEFAULT '',
            profissional TEXT NOT NULL DEFAULT 'Waleska Paula',
            criadoEm TEXT NOT NULL,
            atualizadoEm TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS evolutions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            patient_name TEXT NOT NULL DEFAULT '',
            appointment_id INTEGER,
            evolution_date TEXT NOT NULL,
            procedimentos TEXT NOT NULL DEFAULT '',
            exercicios TEXT NOT NULL DEFAULT '',
            resposta TEXT NOT NULL DEFAULT '',
            observacoes TEXT NOT NULL DEFAULT '',
            proxima_conduta TEXT NOT NULL DEFAULT '',
            profissional TEXT NOT NULL DEFAULT 'Waleska Paula',
            criadoEm TEXT NOT NULL,
            atualizadoEm TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            descricao TEXT NOT NULL DEFAULT '',
            categoria TEXT NOT NULL DEFAULT '',
            regiao TEXT NOT NULL DEFAULT '',
            objetivo TEXT NOT NULL DEFAULT '',
            instrucoes TEXT NOT NULL DEFAULT '',
            criadoEm TEXT NOT NULL,
            atualizadoEm TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            patient_name TEXT NOT NULL DEFAULT '',
            titulo TEXT NOT NULL,
            tipo TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            criadoEm TEXT NOT NULL
        );
        """
    )
    db.commit()

    def ensure_column(table, column, ddl):
        cols = [r[1] for r in db.execute("PRAGMA table_info(" + table + ")").fetchall()]
        if column not in cols:
            db.execute("ALTER TABLE " + table + " ADD COLUMN " + ddl)

    ensure_column("admins", "nome", "nome TEXT NOT NULL DEFAULT 'Waleska Paula'")
    ensure_column("admins", "role", "role TEXT NOT NULL DEFAULT 'Administradora'")
    ensure_column("services", "duracao_min", "duracao_min INTEGER NOT NULL DEFAULT 50")
    ensure_column("services", "categoria", "categoria TEXT NOT NULL DEFAULT ''")
    ensure_column("registrations", "forma_pagamento", "forma_pagamento TEXT NOT NULL DEFAULT ''")
    ensure_column("payments", "method", "method TEXT NOT NULL DEFAULT ''")
    ensure_column("payments", "service_name", "service_name TEXT NOT NULL DEFAULT ''")
    ensure_column("payments", "registration_id", "registration_id INTEGER")
    db.execute(
        "UPDATE payments SET status = 'Pago' WHERE status = 'Recebido'"
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

    cur = db.execute("SELECT COUNT(*) AS c FROM exercises")
    if cur.fetchone()["c"] == 0:
        ts = now_iso()
        for ex in (
            ("Respiração diafragmática", "Controle respiratório para estabilidade do core.", "Pilates", "Core", "Consciência corporal", "Inspire pelo nariz expandindo o abdômen; expire pela boca suavemente."),
            ("Ponte", "Fortalecimento de glúteos e posterior de coxa.", "Fortalecimento", "Quadril", "Estabilidade pélvica", "Deitada, pés apoiados, eleve o quadril mantendo o alinhamento."),
            ("Gato-vaca", "Mobilidade da coluna em flexão e extensão.", "Mobilidade", "Coluna", "Alívio de tensão", "Em quatro apoios, alterne convexidade e concavidade da coluna."),
            ("Alongamento de peitoral", "Abre o tórax e reduz tensão anterior.", "Alongamento", "Tórax", "Postura", "Com o braço apoiado, gire o tronco até sentir o alongamento."),
        ):
            db.execute(
                """INSERT INTO exercises
                   (nome, descricao, categoria, regiao, objetivo, instrucoes, criadoEm, atualizadoEm)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ex + (ts, ts),
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
            cfg[row["chave"]] = decode_json(row["valor"], [])
        except (ValueError, TypeError):
            cfg[row["chave"]] = []
    return cfg


CLINIC_DEFAULTS = {
    "nome": "Dra. Waleska Paula",
    "whatsapp": "(83) 99900-2456",
    "email": "Walesca1912@hotmail.com",
    "endereco": "João Pessoa / Caaporã",
    "horarios": "Segunda a sexta, 8h às 18h",
    "crefito": "CREFITO 356057-F",
}


def digits_only(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def clinic_whatsapp_link(whatsapp):
    digits = digits_only(whatsapp)
    if not digits:
        digits = digits_only(CLINIC_DEFAULTS["whatsapp"])
    if digits and not digits.startswith("55"):
        digits = "55" + digits
    return "https://wa.me/" + digits


def get_setting_text(db, chave, default=""):
    row = db.execute("SELECT valor FROM settings WHERE chave = ?", (chave,)).fetchone()
    if not row:
        return default
    raw = row["valor"]
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return json.dumps(raw, ensure_ascii=False) if raw else default
    if not isinstance(raw, str):
        return str(raw)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, str):
            return parsed
    except (ValueError, TypeError):
        pass
    return raw


def get_clinic_settings(db=None):
    db = db or get_db()
    data = dict(CLINIC_DEFAULTS)
    for chave in CLINIC_DEFAULTS:
        data[chave] = get_setting_text(db, "clinica_" + chave, data[chave])
    data["whatsapp_link"] = clinic_whatsapp_link(data["whatsapp"])
    return data


def save_clinic_settings(db, payload):
    ts = now_iso()
    saved = get_clinic_settings(db)
    for chave in CLINIC_DEFAULTS:
        if chave not in payload or payload.get(chave) is None:
            continue
        valor = str(payload.get(chave) or "").strip() or CLINIC_DEFAULTS[chave]
        db.execute(
            """INSERT INTO settings (chave, valor, atualizadoEm)
               VALUES (?, ?, ?)
               ON CONFLICT(chave) DO UPDATE SET
                   valor = excluded.valor,
                   atualizadoEm = excluded.atualizadoEm""",
            ("clinica_" + chave, json.dumps(valor, ensure_ascii=False), ts),
        )
        saved[chave] = valor
    saved["whatsapp_link"] = clinic_whatsapp_link(saved["whatsapp"])
    return saved


@app.route("/api/cadastro-config")
def api_public_cadastro_config():
    return jsonify({"ok": True, "data": get_cadastro_config()})


@app.route("/api/clinica")
def api_public_clinica():
    return jsonify({"ok": True, "data": get_clinic_settings()})


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
    forma_pagamento = normalize_payment_method(data.get("forma_pagamento") or data.get("pagamento"))

    if not nome or not telefone:
        return jsonify({"ok": False, "error": "Nome e telefone são obrigatórios."}), 400
    if not forma_pagamento:
        return jsonify({"ok": False, "error": "Escolha a forma de pagamento: Pix ou Dinheiro."}), 400

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
           (nome, nascimento, telefone, servico_id, servico, valor, dias, frequencia, motivos, observacoes, status, forma_pagamento, criadoEm, atualizadoEm)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (nome, nascimento, telefone, service["id"], servico_final, service["valor"],
         json.dumps(dias, ensure_ascii=False), frequencia,
         json.dumps(motivos, ensure_ascii=False), observacoes, status, forma_pagamento, ts, ts),
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

    create_payment_record(
        db,
        patient_id=registration_id,
        patient_name=nome,
        service_id=service["id"],
        service_name=servico_final,
        amount=service["valor"],
        method=forma_pagamento,
        status="Pendente",
        notes="Cadastro pelo site",
        registration_id=registration_id,
    )

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
    ativo = 0 if data.get("ativo") is False else 1
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
    ativo = 0 if data.get("ativo") is False else 1
    lista_espera = 1 if data.get("lista_espera") else 0
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

PAYMENT_METHODS = ("Pix", "Dinheiro")
PAYMENT_STATUS = ("Pendente", "Pago", "Cancelado")


def normalize_payment_method(value):
    raw = (value or "").strip()
    for opt in PAYMENT_METHODS:
        if raw.lower() == opt.lower():
            return opt
    return ""


def normalize_payment_status(value, fallback="Pendente"):
    raw = (value or "").strip()
    if raw.lower() in ("recebido", "pago"):
        return "Pago"
    for opt in PAYMENT_STATUS:
        if raw.lower() == opt.lower():
            return opt
    return fallback


def row_to_payment(row):
    if not row:
        return None
    d = dict(row)
    d["status"] = normalize_payment_status(d.get("status"), "Pendente")
    d["method"] = normalize_payment_method(d.get("method"))
    return d


def create_payment_record(db, *, patient_id, patient_name, service_id, service_name,
                          amount, method, status="Pendente", notes="", appointment_id=None,
                          registration_id=None):
    try:
        amount = float(amount or 0)
    except (TypeError, ValueError):
        amount = 0
    if amount <= 0:
        return None
    method = normalize_payment_method(method)
    status = normalize_payment_status(status)
    ts = now_iso()

    if appointment_id:
        existing = db.execute(
            "SELECT id FROM payments WHERE appointment_id = ? AND status != 'Cancelado'",
            (appointment_id,),
        ).fetchone()
        if existing:
            return existing["id"]
        if patient_id:
            orphan = db.execute(
                """SELECT id FROM payments
                   WHERE (patient_id = ? OR registration_id = ?)
                     AND (appointment_id IS NULL OR appointment_id = 0)
                     AND status = 'Pendente'
                   ORDER BY id DESC LIMIT 1""",
                (patient_id, patient_id),
            ).fetchone()
            if orphan:
                db.execute(
                    """UPDATE payments SET appointment_id = ?, service_id = COALESCE(?, service_id),
                       service_name = CASE WHEN ? != '' THEN ? ELSE service_name END,
                       atualizadoEm = ? WHERE id = ?""",
                    (appointment_id, service_id, service_name or "", service_name or "", now_iso(), orphan["id"]),
                )
                return orphan["id"]

    cur = db.execute(
        """INSERT INTO payments
           (patient_id, patient_name, appointment_id, service_id, amount, status, paid_at,
            notes, criadoEm, atualizadoEm, method, service_name, registration_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (patient_id, (patient_name or "").strip(), appointment_id, service_id, amount, status,
         ts if status == "Pago" else None, (notes or "").strip(), ts, ts, method,
         (service_name or "").strip(), registration_id),
    )
    return cur.lastrowid


def row_to_registration(r):
    d = dict(r) if r else {}
    return {
        "id": d.get("id"),
        "nome": d.get("nome"),
        "nascimento": d.get("nascimento"),
        "idade": calc_idade(d.get("nascimento")),
        "telefone": d.get("telefone"),
        "servico_id": d.get("servico_id"),
        "servico": d.get("servico"),
        "valor": d.get("valor"),
        "dias": decode_json(d.get("dias"), []),
        "frequencia": d.get("frequencia"),
        "motivos": decode_json(d.get("motivos"), []),
        "observacoes": d.get("observacoes"),
        "status": d.get("status"),
        "forma_pagamento": d.get("forma_pagamento") or "",
        "criadoEm": d.get("criadoEm"),
        "atualizadoEm": d.get("atualizadoEm"),
    }


def link_appointments_to_registration(db, registration_id, nome, appointment_ids=None):
    ts = now_iso()
    nome_limpo = (nome or "").strip()
    ids = []
    for raw in appointment_ids or []:
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    if ids:
        placeholders = ",".join("?" * len(ids))
        db.execute(
            "UPDATE appointments SET patient_id = ?, patient_name = ?, atualizadoEm = ? WHERE id IN ("
            + placeholders
            + ")",
            [registration_id, nome_limpo, ts] + ids,
        )
    if nome_limpo:
        db.execute(
            """UPDATE appointments SET patient_id = ?, patient_name = ?, atualizadoEm = ?
               WHERE (patient_id IS NULL OR patient_id = 0)
                 AND LOWER(TRIM(patient_name)) = LOWER(?)""",
            (registration_id, nome_limpo, ts, nome_limpo),
        )


@app.route("/api/admin/cadastros", methods=["POST"])
@login_required
def api_admin_cadastro_create():
    data = request.get_json(silent=True) or {}
    nome = (data.get("nome") or "").strip()
    nascimento = (data.get("nascimento") or "").strip() or None
    telefone = (data.get("telefone") or "").strip()
    observacoes = (data.get("observacoes") or "").strip()
    frequencia = (data.get("frequencia") or "").strip()
    dias = data.get("dias") or []
    motivos = data.get("motivos") or []
    status = (data.get("status") or "Em atendimento").strip() or "Em atendimento"
    incluir_espera = bool(data.get("lista_espera"))
    forma_pagamento = normalize_payment_method(data.get("forma_pagamento") or data.get("pagamento"))

    if not nome or not telefone:
        return jsonify({"ok": False, "error": "Nome e telefone são obrigatórios."}), 400

    db = get_db()
    service = None
    servico_id = data.get("servico_id")
    servico_nome = (data.get("servico") or "").strip()
    if servico_id:
        service = db.execute("SELECT * FROM services WHERE id = ?", (servico_id,)).fetchone()
    if not service and servico_nome:
        service = db.execute("SELECT * FROM services WHERE nome = ?", (servico_nome,)).fetchone()

    if not service:
        return jsonify({"ok": False, "error": "Selecione um serviço."}), 400

    ts = now_iso()
    cur = db.execute(
        """INSERT INTO registrations
           (nome, nascimento, telefone, servico_id, servico, valor, dias, frequencia, motivos, observacoes, status, forma_pagamento, criadoEm, atualizadoEm)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (nome, nascimento, telefone, service["id"], service["nome"], service["valor"],
         json.dumps(dias, ensure_ascii=False), frequencia,
         json.dumps(motivos, ensure_ascii=False), observacoes, status, forma_pagamento, ts, ts),
    )
    registration_id = cur.lastrowid

    if incluir_espera or (service["lista_espera"] and status in ("Lista de espera", "Aguardando dupla")):
        idade = calc_idade(nascimento)
        dificuldades = "; ".join(motivos) if motivos else (observacoes or "Não informado")
        db.execute(
            """INSERT INTO waitlist
               (registration_id, nome, nascimento, idade, telefone, servico, dificuldades, observacoes, status, criadoEm, atualizadoEm)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (registration_id, nome, nascimento, idade, telefone, service["nome"],
             dificuldades, observacoes, status if status in ("Lista de espera", "Aguardando dupla") else "Lista de espera",
             ts, ts),
        )

    appointment_ids = list(data.get("appointment_ids") or [])
    if data.get("appointment_id"):
        appointment_ids.append(data.get("appointment_id"))
    link_appointments_to_registration(db, registration_id, nome, appointment_ids)
    if forma_pagamento:
        apt_id = None
        for raw in appointment_ids:
            try:
                apt_id = int(raw)
                break
            except (TypeError, ValueError):
                continue
        create_payment_record(
            db,
            patient_id=registration_id,
            patient_name=nome,
            service_id=service["id"],
            service_name=service["nome"],
            amount=service["valor"],
            method=forma_pagamento,
            status="Pendente",
            notes="Cadastro pelo painel",
            appointment_id=apt_id,
            registration_id=registration_id,
        )
    db.commit()
    row = db.execute("SELECT * FROM registrations WHERE id = ?", (registration_id,)).fetchone()
    return jsonify({"ok": True, "data": row_to_registration(row)}), 201


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


@app.route("/api/admin/cadastros/<int:reg_id>/prontuario")
@login_required
def api_admin_cadastro_prontuario(reg_id):
    db = get_db()
    row = db.execute("SELECT * FROM registrations WHERE id = ?", (reg_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Cadastro não encontrado."}), 404
    patient = row_to_registration(row)
    nome = patient.get("nome") or ""
    evals = [dict(r) for r in db.execute(
        """SELECT * FROM evaluations
           WHERE patient_id = ? OR (patient_id IS NULL AND LOWER(TRIM(patient_name)) = LOWER(?))
           ORDER BY evaluated_at DESC, id DESC""",
        (reg_id, nome),
    ).fetchall()]
    evos = [dict(r) for r in db.execute(
        """SELECT * FROM evolutions
           WHERE patient_id = ? OR (patient_id IS NULL AND LOWER(TRIM(patient_name)) = LOWER(?))
           ORDER BY evolution_date DESC, id DESC""",
        (reg_id, nome),
    ).fetchall()]
    agenda = [row_to_appointment(r) for r in db.execute(
        """SELECT * FROM appointments
           WHERE patient_id = ? OR (patient_id IS NULL AND LOWER(TRIM(patient_name)) = LOWER(?))
           ORDER BY starts_at DESC, id DESC""",
        (reg_id, nome),
    ).fetchall()]
    docs = [dict(r) for r in db.execute(
        """SELECT * FROM documents
           WHERE patient_id = ? OR (patient_id IS NULL AND LOWER(TRIM(patient_name)) = LOWER(?))
           ORDER BY id DESC""",
        (reg_id, nome),
    ).fetchall()]
    pays = payments_query({"patient_id": reg_id})
    return jsonify({
        "ok": True,
        "data": {
            "paciente": patient,
            "avaliacoes": evals,
            "evolucoes": evos,
            "agenda": agenda,
            "documentos": docs,
            "financeiro": pays,
            "resumo_financeiro": payments_summary(pays),
        },
    })


@app.route("/api/admin/cadastros/<int:reg_id>", methods=["PUT"])
@login_required
def api_admin_cadastro_update(reg_id):
    data = request.get_json(silent=True) or {}
    db = get_db()
    row = db.execute("SELECT * FROM registrations WHERE id = ?", (reg_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Cadastro não encontrado."}), 404

    nome = (data.get("nome") if data.get("nome") is not None else row["nome"] or "").strip()
    nascimento = ((data.get("nascimento") if data.get("nascimento") is not None else row["nascimento"]) or "").strip() or None
    telefone = (data.get("telefone") if data.get("telefone") is not None else row["telefone"] or "").strip()
    observacoes = (data.get("observacoes") if data.get("observacoes") is not None else row["observacoes"] or "").strip()
    status = (data.get("status") if data.get("status") is not None else row["status"] or "").strip()
    dias = data.get("dias") if data.get("dias") is not None else decode_json(row["dias"], [])
    frequencia = ((data.get("frequencia") if data.get("frequencia") is not None else row["frequencia"]) or "").strip()
    motivos = data.get("motivos") if data.get("motivos") is not None else decode_json(row["motivos"], [])

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

def parse_json_list(value):
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


def tokenize_text(value):
    raw = (value or "").lower()
    for ch in ",.;:/|()[]{}+":
        raw = raw.replace(ch, " ")
    stop = {
        "de", "da", "do", "das", "dos", "e", "ou", "a", "o", "as", "os", "em",
        "para", "com", "sem", "na", "no", "nas", "nos", "um", "uma",
    }
    return [t for t in raw.split() if len(t) > 2 and t not in stop]


def periodo_from_frequencia(frequencia):
    txt = (frequencia or "").lower()
    if any(k in txt for k in ("manhã", "manha", "manhãzinha")):
        return "manhã"
    if "tarde" in txt:
        return "tarde"
    if "noite" in txt:
        return "noite"
    return ""


def waitlist_profile(row, registration=None):
    data = dict(row) if row else {}
    reg = dict(registration) if registration else {}
    dias = parse_json_list(reg.get("dias"))
    motivos = parse_json_list(reg.get("motivos"))
    frequencia = (reg.get("frequencia") or "").strip()
    dificuldades = (data.get("dificuldades") or "").strip()
    observacoes = (data.get("observacoes") or reg.get("observacoes") or "").strip()
    return {
        "id": data.get("id"),
        "registration_id": data.get("registration_id"),
        "nome": data.get("nome"),
        "nascimento": data.get("nascimento"),
        "idade": data.get("idade"),
        "telefone": data.get("telefone"),
        "servico": data.get("servico") or reg.get("servico") or "",
        "dificuldades": dificuldades,
        "observacoes": observacoes,
        "status": data.get("status"),
        "criadoEm": data.get("criadoEm"),
        "atualizadoEm": data.get("atualizadoEm"),
        "dias": dias,
        "frequencia": frequencia,
        "motivos": motivos,
        "periodo": periodo_from_frequencia(frequencia),
    }


def row_to_waitlist(r, registration=None):
    return waitlist_profile(r, registration)


def load_waitlist_profiles(db, rows):
    profiles = []
    cache = {}
    for row in rows:
        rid = row["registration_id"]
        reg = None
        if rid:
            if rid not in cache:
                cache[rid] = db.execute(
                    "SELECT * FROM registrations WHERE id = ?", (rid,)
                ).fetchone()
            reg = cache[rid]
        profiles.append(waitlist_profile(row, reg))
    return profiles


def score_dupla_pair(a, b):
    checks = []
    score = 0
    max_score = 0

    max_score += 25
    serv_a = (a.get("servico") or "").strip().lower()
    serv_b = (b.get("servico") or "").strip().lower()
    if serv_a and serv_b and serv_a == serv_b:
        score += 25
        checks.append({"ok": True, "texto": "Mesmo serviço: " + (a.get("servico") or "")})
    elif serv_a and serv_b:
        checks.append({"ok": False, "texto": "Serviços diferentes"})
    else:
        checks.append({"ok": False, "texto": "Serviço incompleto"})

    max_score += 20
    dias_a = set((d or "").strip() for d in (a.get("dias") or []) if d)
    dias_b = set((d or "").strip() for d in (b.get("dias") or []) if d)
    comuns = sorted(dias_a & dias_b)
    if comuns:
        score += 20 if len(comuns) >= 2 else 14
        checks.append({"ok": True, "texto": "Dias em comum: " + ", ".join(comuns)})
    elif dias_a and dias_b:
        checks.append({"ok": False, "texto": "Dias disponíveis diferentes"})
    else:
        checks.append({"ok": False, "texto": "Dias ainda não informados"})

    max_score += 15
    freq_a = (a.get("frequencia") or "").strip().lower()
    freq_b = (b.get("frequencia") or "").strip().lower()
    per_a = a.get("periodo") or ""
    per_b = b.get("periodo") or ""
    if freq_a and freq_b and freq_a == freq_b:
        score += 15
        checks.append({"ok": True, "texto": "Mesma frequência"})
    elif per_a and per_b and per_a == per_b:
        score += 10
        checks.append({"ok": True, "texto": "Mesmo período: " + per_a})
    elif freq_a and freq_b:
        checks.append({"ok": False, "texto": "Frequência diferente"})
    else:
        checks.append({"ok": False, "texto": "Horário/frequência incompletos"})

    max_score += 15
    mot_a = set((m or "").strip().lower() for m in (a.get("motivos") or []) if m)
    mot_b = set((m or "").strip().lower() for m in (b.get("motivos") or []) if m)
    mot_comum = sorted(mot_a & mot_b)
    if mot_comum:
        score += 15 if len(mot_comum) >= 2 else 10
        checks.append({"ok": True, "texto": "Objetivos compatíveis"})
    elif mot_a and mot_b:
        checks.append({"ok": False, "texto": "Objetivos distintos"})
    else:
        checks.append({"ok": False, "texto": "Objetivos ainda não informados"})

    max_score += 15
    tokens_a = set(tokenize_text(a.get("dificuldades")) + tokenize_text(" ".join(a.get("motivos") or [])))
    tokens_b = set(tokenize_text(b.get("dificuldades")) + tokenize_text(" ".join(b.get("motivos") or [])))
    overlap = tokens_a & tokens_b
    if overlap:
        score += 15 if len(overlap) >= 2 else 9
        checks.append({"ok": True, "texto": "Necessidades compatíveis"})
    elif (a.get("dificuldades") or "").strip() and (b.get("dificuldades") or "").strip():
        checks.append({"ok": False, "texto": "Necessidades diferentes"})
    else:
        checks.append({"ok": False, "texto": "Necessidades ainda não informadas"})

    max_score += 10
    idade_a = a.get("idade")
    idade_b = b.get("idade")
    if idade_a is not None and idade_b is not None:
        diff = abs(int(idade_a) - int(idade_b))
        if diff <= 8:
            score += 10
            checks.append({"ok": True, "texto": "Faixa etária próxima"})
        elif diff <= 15:
            score += 5
            checks.append({"ok": True, "texto": "Faixa etária aceitável"})
        else:
            checks.append({"ok": False, "texto": "Faixa etária distante"})
    else:
        checks.append({"ok": False, "texto": "Idade incompleta"})

    pct = int(round((score / max_score) * 100)) if max_score else 0
    if pct >= 75:
        nivel = "alta"
        rotulo = "Compatibilidade alta"
    elif pct >= 50:
        nivel = "media"
        rotulo = "Compatibilidade média"
    else:
        nivel = "baixa"
        rotulo = "Compatibilidade baixa"

    return {
        "paciente1": a,
        "paciente2": b,
        "paciente1_id": a.get("id"),
        "paciente2_id": b.get("id"),
        "score": pct,
        "nivel": nivel,
        "rotulo": rotulo,
        "checks": checks,
        "dias_comuns": comuns,
        "servico": a.get("servico") if serv_a == serv_b else ((a.get("servico") or "") + " / " + (b.get("servico") or "")).strip(" /"),
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
    db = get_db()
    rows = db.execute(sql, params).fetchall()
    return jsonify({"ok": True, "data": load_waitlist_profiles(db, rows)})


@app.route("/api/admin/lista-espera/<int:wl_id>", methods=["PUT"])
@login_required
def api_admin_waitlist_update(wl_id):
    data = request.get_json(silent=True) or {}
    db = get_db()
    row = db.execute("SELECT * FROM waitlist WHERE id = ?", (wl_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Registro não encontrado."}), 404

    nome = (data.get("nome") if data.get("nome") is not None else row["nome"] or "").strip()
    nascimento = ((data.get("nascimento") if data.get("nascimento") is not None else row["nascimento"]) or "").strip() or None
    telefone = (data.get("telefone") if data.get("telefone") is not None else row["telefone"] or "").strip()
    dificuldades = (data.get("dificuldades") if data.get("dificuldades") is not None else row["dificuldades"] or "").strip()
    observacoes = (data.get("observacoes") if data.get("observacoes") is not None else row["observacoes"] or "").strip()
    status = (data.get("status") if data.get("status") is not None else row["status"] or "").strip()
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
        "paciente1": decode_json(r["paciente1"], {}),
        "paciente2": decode_json(r["paciente2"], {}),
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


@app.route("/api/admin/duplas/sugestoes")
@login_required
def api_admin_duplas_sugestoes():
    db = get_db()
    rows = db.execute(
        """SELECT * FROM waitlist
           WHERE status IN ('Lista de espera', 'Aguardando dupla')
           ORDER BY criadoEm ASC, id ASC"""
    ).fetchall()
    people = load_waitlist_profiles(db, rows)
    pairs = []
    used = set()
    for i, a in enumerate(people):
        for b in people[i + 1:]:
            scored = score_dupla_pair(a, b)
            pairs.append(scored)
    pairs.sort(key=lambda p: (-p["score"], p["paciente1"].get("nome") or "", p["paciente2"].get("nome") or ""))

    sugestoes = []
    for item in pairs:
        id1 = item["paciente1_id"]
        id2 = item["paciente2_id"]
        if id1 in used or id2 in used:
            continue
        if item["score"] < 45:
            continue
        used.add(id1)
        used.add(id2)
        sugestoes.append(item)
        if len(sugestoes) >= 8:
            break

    return jsonify({
        "ok": True,
        "data": sugestoes,
        "candidatos": len(people),
        "pares_avaliados": len(pairs),
    })


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
        old = decode_json(old_patient, {}) if not isinstance(old_patient, dict) else old_patient
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
        p = decode_json(patient, {}) if not isinstance(patient, dict) else patient
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
# Agenda / Agendamentos
# ---------------------------------------------------------------

APPOINTMENT_STATUS = (
    "Agendado",
    "Confirmado",
    "Realizado",
    "Cancelado",
    "Faltou",
    "Reagendado",
)


def parse_iso_dt(value):
    if not value:
        return None
    raw = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw[:19] if len(raw) >= 19 else raw, fmt)
        except ValueError:
            continue
    return None


def fmt_dt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def row_to_appointment(row):
    if not row:
        return None
    d = dict(row)
    return d


def resolve_patient_name(db, patient_id, fallback=""):
    if patient_id:
        reg = db.execute("SELECT nome FROM registrations WHERE id = ?", (patient_id,)).fetchone()
        if reg:
            return reg["nome"]
        wl = db.execute("SELECT nome FROM waitlist WHERE id = ?", (patient_id,)).fetchone()
        if wl:
            return wl["nome"]
    return (fallback or "").strip()


def resolve_service_name(db, service_id, fallback=""):
    if service_id:
        svc = db.execute("SELECT nome FROM services WHERE id = ?", (service_id,)).fetchone()
        if svc:
            return svc["nome"]
    return (fallback or "").strip()


@app.route("/api/admin/agenda", methods=["GET"])
@login_required
def api_admin_agenda():
    db = get_db()
    view = (request.args.get("view") or "month").strip().lower()
    date_str = (request.args.get("date") or "").strip()
    anchor = parse_iso_dt(date_str + "T00:00") if date_str else datetime.now()
    if not anchor:
        anchor = datetime.now()

    if view == "day":
        start = anchor.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(hour=23, minute=59, second=59)
    elif view == "week":
        start = (anchor - timedelta(days=anchor.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    else:
        start = anchor.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            next_month = start.replace(year=start.year + 1, month=1)
        else:
            next_month = start.replace(month=start.month + 1)
        end = next_month - timedelta(seconds=1)

    rows = db.execute(
        """SELECT * FROM appointments
           WHERE starts_at >= ? AND starts_at <= ?
           ORDER BY starts_at ASC""",
        (fmt_dt(start), fmt_dt(end)),
    ).fetchall()

    return jsonify({
        "ok": True,
        "data": {
            "view": view if view in ("day", "week", "month") else "month",
            "date": start.strftime("%Y-%m-%d"),
            "start": fmt_dt(start),
            "end": fmt_dt(end),
            "items": [row_to_appointment(r) for r in rows],
        },
    })


@app.route("/api/admin/agenda", methods=["POST"])
@login_required
def api_admin_agenda_create():
    data = request.get_json(silent=True) or {}
    db = get_db()

    patient_id = data.get("patient_id")
    patient_name = resolve_patient_name(db, patient_id, data.get("patient_name") or "")
    if not patient_name:
        return jsonify({"ok": False, "error": "Informe o paciente."}), 400

    starts = parse_iso_dt(data.get("starts_at"))
    if not starts:
        return jsonify({"ok": False, "error": "Informe data e horário válidos."}), 400

    duration = data.get("duration_min")
    try:
        duration = int(duration) if duration not in (None, "") else 50
    except (TypeError, ValueError):
        duration = 50
    if duration <= 0:
        duration = 50

    ends = parse_iso_dt(data.get("ends_at"))
    if not ends:
        ends = starts + timedelta(minutes=duration)

    service_id = data.get("service_id")
    service_name = resolve_service_name(db, service_id, data.get("service_name") or "")
    status = data.get("status") or "Agendado"
    if status not in APPOINTMENT_STATUS:
        status = "Agendado"
    notes = (data.get("notes") or "").strip()
    dupla_id = data.get("dupla_id") or None
    ts = now_iso()

    cur = db.execute(
        """INSERT INTO appointments
           (patient_id, patient_name, service_id, service_name, dupla_id,
            starts_at, ends_at, duration_min, status, notes, criadoEm, atualizadoEm)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (patient_id, patient_name, service_id, service_name, dupla_id,
         fmt_dt(starts), fmt_dt(ends), duration, status, notes, ts, ts),
    )
    apt_id = cur.lastrowid
    amount = 0
    method = normalize_payment_method(data.get("forma_pagamento") or data.get("method"))
    if service_id:
        svc = db.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
        if svc:
            amount = svc["valor"]
            service_name = svc["nome"]
    if patient_id and not method:
        reg = db.execute("SELECT forma_pagamento FROM registrations WHERE id = ?", (patient_id,)).fetchone()
        if reg:
            method = normalize_payment_method(reg["forma_pagamento"])
    if status != "Cancelado" and amount:
        create_payment_record(
            db,
            patient_id=patient_id,
            patient_name=patient_name,
            service_id=service_id,
            service_name=service_name,
            amount=amount,
            method=method,
            status="Pendente",
            notes="Agendamento",
            appointment_id=apt_id,
            registration_id=patient_id,
        )
    db.commit()
    row = db.execute("SELECT * FROM appointments WHERE id = ?", (apt_id,)).fetchone()
    return jsonify({"ok": True, "data": row_to_appointment(row)}), 201


@app.route("/api/admin/agenda/<int:apt_id>", methods=["GET"])
@login_required
def api_admin_agenda_get(apt_id):
    row = get_db().execute("SELECT * FROM appointments WHERE id = ?", (apt_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Agendamento não encontrado."}), 404
    return jsonify({"ok": True, "data": row_to_appointment(row)})


@app.route("/api/admin/agenda/<int:apt_id>", methods=["PUT"])
@login_required
def api_admin_agenda_update(apt_id):
    db = get_db()
    row = db.execute("SELECT * FROM appointments WHERE id = ?", (apt_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Agendamento não encontrado."}), 404

    data = request.get_json(silent=True) or {}
    patient_id = data.get("patient_id", row["patient_id"])
    patient_name = resolve_patient_name(db, patient_id, data.get("patient_name") or row["patient_name"])
    service_id = data.get("service_id", row["service_id"])
    service_name = resolve_service_name(db, service_id, data.get("service_name") or row["service_name"])

    starts = parse_iso_dt(data.get("starts_at")) or parse_iso_dt(row["starts_at"])
    duration = data.get("duration_min", row["duration_min"])
    try:
        duration = int(duration) if duration not in (None, "") else 50
    except (TypeError, ValueError):
        duration = 50
    ends = parse_iso_dt(data.get("ends_at"))
    if not ends and starts:
        ends = starts + timedelta(minutes=duration)

    status = data.get("status") or row["status"]
    if status not in APPOINTMENT_STATUS:
        status = row["status"]
    notes = data.get("notes") if "notes" in data else row["notes"]
    notes = (notes or "").strip()
    dupla_id = data.get("dupla_id", row["dupla_id"])
    ts = now_iso()

    db.execute(
        """UPDATE appointments SET
           patient_id = ?, patient_name = ?, service_id = ?, service_name = ?,
           dupla_id = ?, starts_at = ?, ends_at = ?, duration_min = ?,
           status = ?, notes = ?, atualizadoEm = ?
           WHERE id = ?""",
        (patient_id, patient_name, service_id, service_name, dupla_id,
         fmt_dt(starts), fmt_dt(ends) if ends else row["ends_at"], duration,
         status, notes, ts, apt_id),
    )
    db.commit()
    updated = db.execute("SELECT * FROM appointments WHERE id = ?", (apt_id,)).fetchone()
    return jsonify({"ok": True, "data": row_to_appointment(updated)})


@app.route("/api/admin/agenda/<int:apt_id>", methods=["DELETE"])
@login_required
def api_admin_agenda_delete(apt_id):
    db = get_db()
    row = db.execute("SELECT id FROM appointments WHERE id = ?", (apt_id,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Agendamento não encontrado."}), 404
    db.execute("DELETE FROM appointments WHERE id = ?", (apt_id,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/agenda/sem-cadastro")
@login_required
def api_admin_agenda_sem_cadastro():
    db = get_db()
    rows = db.execute(
        """SELECT a.id, a.patient_name, a.patient_id, a.service_id, a.service_name, a.starts_at, a.status
           FROM appointments a
           LEFT JOIN registrations r ON r.id = a.patient_id
           WHERE a.patient_id IS NULL OR a.patient_id = 0 OR r.id IS NULL
           ORDER BY a.starts_at DESC"""
    ).fetchall()

    grouped = {}
    for r in rows:
        nome = (r["patient_name"] or "").strip()
        if not nome:
            continue
        chave = nome.lower()
        item = grouped.get(chave)
        if not item:
            grouped[chave] = {
                "nome": nome,
                "service_id": r["service_id"],
                "servico": r["service_name"] or "",
                "appointments_count": 0,
                "last_at": r["starts_at"],
                "appointment_ids": [],
            }
            item = grouped[chave]
        item["appointments_count"] += 1
        item["appointment_ids"].append(r["id"])
        if r["starts_at"] and (not item["last_at"] or r["starts_at"] > item["last_at"]):
            item["last_at"] = r["starts_at"]
            if r["service_name"]:
                item["servico"] = r["service_name"]
                item["service_id"] = r["service_id"]

    data = sorted(grouped.values(), key=lambda x: x["nome"].lower())
    return jsonify({"ok": True, "data": data})


@app.route("/api/admin/agenda/pacientes")
@login_required
def api_admin_agenda_pacientes():
    q = (request.args.get("q") or "").strip()
    db = get_db()
    if q:
        like = "%" + q + "%"
        rows = db.execute(
            """SELECT id, nome, telefone, servico, status FROM registrations
               WHERE nome LIKE ? OR telefone LIKE ?
               ORDER BY nome LIMIT 40""",
            (like, like),
        ).fetchall()
    else:
        rows = db.execute(
            """SELECT id, nome, telefone, servico, status FROM registrations
               ORDER BY atualizadoEm DESC LIMIT 40"""
        ).fetchall()
    return jsonify({"ok": True, "data": [dict(r) for r in rows]})


# ---------------------------------------------------------------
# Configurações
# ---------------------------------------------------------------

@app.route("/api/admin/config", methods=["GET"])
@login_required
def api_admin_config_get():
    admin = current_admin()
    clinic = get_clinic_settings()
    data = {
        "email": admin["email"],
        "nome": clinic.get("nome") or "",
        "whatsapp": clinic.get("whatsapp") or "",
        "email_clinica": clinic.get("email") or "",
        "endereco": clinic.get("endereco") or "",
        "horarios": clinic.get("horarios") or "",
        "crefito": clinic.get("crefito") or "",
        "whatsapp_link": clinic.get("whatsapp_link") or "",
        "clinica": clinic,
    }
    return jsonify({"ok": True, "data": data})


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

    clinic_payload = {
        "nome": data.get("nome") or data.get("clinica_nome"),
        "whatsapp": data.get("whatsapp"),
        "email": data.get("email_clinica") or data.get("clinica_email"),
        "endereco": data.get("endereco"),
        "horarios": data.get("horarios"),
        "crefito": data.get("crefito"),
    }
    clinic = save_clinic_settings(db, clinic_payload)
    db.commit()
    return jsonify({
        "ok": True,
        "data": {
            "email": email,
            "nome": clinic.get("nome") or "",
            "whatsapp": clinic.get("whatsapp") or "",
            "email_clinica": clinic.get("email") or "",
            "endereco": clinic.get("endereco") or "",
            "horarios": clinic.get("horarios") or "",
            "crefito": clinic.get("crefito") or "",
            "whatsapp_link": clinic.get("whatsapp_link") or "",
        },
    })


@app.route("/api/admin/overview")
@login_required
def api_admin_overview():
    db = get_db()
    hoje = datetime.now().strftime("%Y-%m-%d")
    mes_ini = datetime.now().strftime("%Y-%m-01")
    if datetime.now().month == 12:
        prox = datetime(datetime.now().year + 1, 1, 1)
    else:
        prox = datetime(datetime.now().year, datetime.now().month + 1, 1)
    mes_fim = (prox - timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")

    total = db.execute("SELECT COUNT(*) AS c FROM registrations").fetchone()["c"]
    ativos = db.execute(
        "SELECT COUNT(*) AS c FROM registrations WHERE status != 'Finalizado'"
    ).fetchone()["c"]
    aguardando = db.execute(
        "SELECT COUNT(*) AS c FROM registrations WHERE status IN ('Novo', 'Aguardando avaliação', 'Aguardando dupla')"
    ).fetchone()["c"]
    lista_espera = db.execute(
        "SELECT COUNT(*) AS c FROM waitlist WHERE status IN ('Lista de espera', 'Aguardando dupla')"
    ).fetchone()["c"]
    duplas = db.execute("SELECT COUNT(*) AS c FROM duplas").fetchone()["c"]
    servicos_ativos = db.execute("SELECT COUNT(*) AS c FROM services WHERE ativo = 1").fetchone()["c"]
    hoje_count = db.execute(
        """SELECT COUNT(*) AS c FROM appointments
           WHERE starts_at LIKE ? AND status NOT IN ('Cancelado')""",
        (hoje + "%",),
    ).fetchone()["c"]
    confirmacao = db.execute(
        "SELECT COUNT(*) AS c FROM appointments WHERE status = 'Agendado' AND starts_at >= ?",
        (hoje + " 00:00:00",),
    ).fetchone()["c"]
    avaliacoes_pendentes = db.execute(
        """SELECT COUNT(*) AS c FROM registrations
           WHERE status IN ('Novo', 'Aguardando avaliação')"""
    ).fetchone()["c"]

    rec_row = db.execute(
        """SELECT COALESCE(SUM(amount), 0) AS s FROM payments
           WHERE status IN ('Pago', 'Recebido') AND (paid_at >= ? OR criadoEm >= ?)""",
        (mes_ini, mes_ini),
    ).fetchone()
    pend_row = db.execute(
        "SELECT COALESCE(SUM(amount), 0) AS s FROM payments WHERE status = 'Pendente'"
    ).fetchone()
    receita_mes = float(rec_row["s"] or 0)
    pendente_mes = float(pend_row["s"] or 0)

    proximos = [dict(r) for r in db.execute(
        """SELECT * FROM appointments
           WHERE starts_at >= ? AND status NOT IN ('Cancelado', 'Realizado', 'Faltou')
           ORDER BY starts_at ASC LIMIT 6""",
        (now_iso(),),
    ).fetchall()]
    recentes = [dict(r) for r in db.execute(
        "SELECT id, nome, status, criadoEm FROM registrations ORDER BY id DESC LIMIT 5"
    ).fetchall()]

    alertas = []
    if confirmacao:
        alertas.append({"tipo": "agenda", "href": "#/agenda", "texto": str(confirmacao) + " atendimento(s) aguardando confirmação"})
    if avaliacoes_pendentes:
        alertas.append({"tipo": "avaliacao", "href": "#/avaliacoes", "texto": str(avaliacoes_pendentes) + " avaliação(ões) pendente(s)"})
    if pendente_mes:
        alertas.append({"tipo": "financeiro", "href": "#/financeiro", "texto": "Pagamentos em aberto no valor de R$ " + ("%.2f" % pendente_mes).replace(".", ",")})
    if lista_espera:
        alertas.append({"tipo": "espera", "href": "#/lista-espera", "texto": str(lista_espera) + " pessoa(s) na lista de espera"})
    if lista_espera >= 2:
        alertas.append({"tipo": "dupla", "href": "#/duplas", "texto": "Há pacientes suficientes para sugerir novas duplas"})

    admin = current_admin()
    return jsonify({
        "ok": True,
        "data": {
            "total_cadastros": total,
            "pacientes_ativos": ativos,
            "aguardando_atendimento": aguardando,
            "lista_espera": lista_espera,
            "duplas": duplas,
            "servicos_ativos": servicos_ativos,
            "atendimentos_hoje": hoje_count,
            "receita_mes": receita_mes,
            "pendente_mes": pendente_mes,
            "proximos": proximos,
            "recentes": recentes,
            "alertas": alertas,
            "admin_nome": (admin["nome"] if admin and "nome" in admin.keys() else None) or "Waleska",
            "admin_role": (admin["role"] if admin and "role" in admin.keys() else None) or "Administradora",
            "admin_email": admin["email"] if admin else "",
        },
    })


def _list_rows(table, order="id DESC"):
    rows = get_db().execute("SELECT * FROM " + table + " ORDER BY " + order).fetchall()
    return jsonify({"ok": True, "data": [dict(r) for r in rows]})


def payments_query(args):
    sql = "SELECT * FROM payments WHERE 1=1"
    params = []
    q = (args.get("q") or args.get("paciente") or "").strip()
    status = normalize_payment_status(args.get("status") or "", "")
    method = normalize_payment_method(args.get("method") or args.get("forma") or "")
    servico = (args.get("servico") or "").strip()
    patient_id = args.get("patient_id")
    de = (args.get("de") or args.get("from") or "").strip()
    ate = (args.get("ate") or args.get("to") or "").strip()
    periodo = (args.get("periodo") or "").strip().lower()
    hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if periodo == "hoje":
        de = hoje.strftime("%Y-%m-%d")
        ate = hoje.strftime("%Y-%m-%d")
    elif periodo == "semana":
        ini = hoje - timedelta(days=hoje.weekday())
        de = ini.strftime("%Y-%m-%d")
        ate = (ini + timedelta(days=6)).strftime("%Y-%m-%d")
    elif periodo == "mes":
        de = hoje.replace(day=1).strftime("%Y-%m-%d")
        ate = hoje.strftime("%Y-%m-%d")
    if q:
        sql += " AND (patient_name LIKE ? OR service_name LIKE ?)"
        params += ["%" + q + "%", "%" + q + "%"]
    if status:
        sql += " AND status = ?"
        params.append(status)
    if method:
        sql += " AND method = ?"
        params.append(method)
    if servico:
        sql += " AND service_name = ?"
        params.append(servico)
    if patient_id:
        try:
            sql += " AND (patient_id = ? OR registration_id = ?)"
            params += [int(patient_id), int(patient_id)]
        except (TypeError, ValueError):
            pass
    if de:
        sql += " AND date(criadoEm) >= date(?)"
        params.append(de[:10])
    if ate:
        sql += " AND date(criadoEm) <= date(?)"
        params.append(ate[:10])
    sql += " ORDER BY criadoEm DESC, id DESC"
    rows = get_db().execute(sql, params).fetchall()
    return [row_to_payment(r) for r in rows]


def payments_summary(items):
    rec = pend = canc = pix = din = 0.0
    rec_pix = rec_din = 0.0
    for r in items:
        valor = float(r.get("amount") or 0)
        st = r.get("status")
        method = r.get("method")
        if st == "Pago":
            rec += valor
            if method == "Pix":
                rec_pix += valor
            elif method == "Dinheiro":
                rec_din += valor
        elif st == "Cancelado":
            canc += valor
        else:
            pend += valor
        if method == "Pix":
            pix += valor
        elif method == "Dinheiro":
            din += valor
    return {
        "recebido": rec,
        "pendente": pend,
        "cancelado": canc,
        "pix": pix,
        "dinheiro": din,
        "recebido_pix": rec_pix,
        "recebido_dinheiro": rec_din,
        "faturado": rec + pend,
        "quantidade": len(items),
    }


def clinic_report(args):
    db = get_db()
    de = (args.get("de") or args.get("from") or "").strip()[:10]
    ate = (args.get("ate") or args.get("to") or "").strip()[:10]
    apt_sql = "SELECT * FROM appointments WHERE 1=1"
    evo_sql = "SELECT * FROM evolutions WHERE 1=1"
    eval_sql = "SELECT * FROM evaluations WHERE 1=1"
    params = []
    evo_params = []
    eval_params = []
    if de:
        apt_sql += " AND date(starts_at) >= date(?)"
        params.append(de)
        evo_sql += " AND date(evolution_date) >= date(?)"
        evo_params.append(de)
        eval_sql += " AND date(evaluated_at) >= date(?)"
        eval_params.append(de)
    if ate:
        apt_sql += " AND date(starts_at) <= date(?)"
        params.append(ate)
        evo_sql += " AND date(evolution_date) <= date(?)"
        evo_params.append(ate)
        eval_sql += " AND date(evaluated_at) <= date(?)"
        eval_params.append(ate)
    appointments = [dict(r) for r in db.execute(apt_sql, params).fetchall()]
    evolutions = db.execute(evo_sql, evo_params).fetchall()
    evaluations = db.execute(eval_sql, eval_params).fetchall()

    def count_status(status):
        return sum(1 for a in appointments if (a.get("status") or "") == status)

    realizados = count_status("Realizado")
    faltas = count_status("Faltou")
    cancelados = count_status("Cancelado")
    agendados = count_status("Agendado") + count_status("Confirmado")
    total_apt = len(appointments)
    ocupacao = int(round((realizados / total_apt) * 100)) if total_apt else 0

    pacientes_total = db.execute("SELECT COUNT(*) AS c FROM registrations").fetchone()["c"]
    pacientes_ativos = db.execute(
        "SELECT COUNT(*) AS c FROM registrations WHERE status != 'Finalizado'"
    ).fetchone()["c"]
    lista_espera = db.execute(
        "SELECT COUNT(*) AS c FROM waitlist WHERE status IN ('Lista de espera', 'Aguardando dupla')"
    ).fetchone()["c"]
    novos_sql = "SELECT COUNT(*) AS c FROM registrations WHERE 1=1"
    novos_params = []
    if de:
        novos_sql += " AND date(criadoEm) >= date(?)"
        novos_params.append(de)
    if ate:
        novos_sql += " AND date(criadoEm) <= date(?)"
        novos_params.append(ate)
    novos = db.execute(novos_sql, novos_params).fetchone()["c"]

    payments = payments_query(args)
    return {
        "pacientes": {
            "total": pacientes_total,
            "ativos": pacientes_ativos,
            "novos": novos,
            "lista_espera": lista_espera,
        },
        "atendimentos": {
            "total": total_apt,
            "realizados": realizados,
            "agendados": agendados,
            "faltas": faltas,
            "cancelamentos": cancelados,
            "ocupacao": ocupacao,
        },
        "evolucoes": len(evolutions),
        "avaliacoes": len(evaluations),
        "financeiro": payments_summary(payments),
        "lancamentos": payments,
    }


@app.route("/api/admin/relatorios")
@login_required
def api_admin_relatorios():
    data = clinic_report(request.args)
    return jsonify({"ok": True, "data": data})


@app.route("/api/admin/payments", methods=["GET"])
@login_required
def api_payments_list():
    items = payments_query(request.args)
    return jsonify({"ok": True, "data": items, "resumo": payments_summary(items)})


@app.route("/api/admin/payments/relatorio")
@login_required
def api_payments_relatorio():
    items = payments_query(request.args)
    resumo = payments_summary(items)
    if request.args.get("formato") == "json":
        return jsonify({"ok": True, "data": items, "resumo": resumo})

    def money(v):
        return "R$ " + ("%.2f" % float(v or 0)).replace(".", ",")

    linhas = []
    for r in items:
        linhas.append(
            "<tr><td>{nome}</td><td>{servico}</td><td>{valor}</td><td>{forma}</td>"
            "<td>{status}</td><td>{data}</td></tr>".format(
                nome=(r.get("patient_name") or "—"),
                servico=(r.get("service_name") or "—"),
                valor=money(r.get("amount")),
                forma=(r.get("method") or "—"),
                status=(r.get("status") or "—"),
                data=(r.get("criadoEm") or "")[:10],
            )
        )
    html = """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8"><title>Relatório financeiro</title>
<style>
body{{font-family:Georgia,serif;color:#14331f;padding:32px;}}
h1{{font-size:22px;margin:0 0 8px}}
p{{color:#5b6b62}}
table{{width:100%;border-collapse:collapse;margin-top:18px;font-size:13px}}
th,td{{border-bottom:1px solid #e4e8e4;padding:8px 6px;text-align:left}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:18px 0}}
.card{{border:1px solid #d7ddd8;border-radius:12px;padding:12px}}
.card b{{display:block;font-size:18px;margin-top:4px}}
@media print {{ button {{ display:none }} }}
</style></head><body>
<button onclick="window.print()">Gerar PDF</button>
<h1>Relatório financeiro — Dra. Waleska Paula</h1>
<p>Gerado em {hoje}</p>
<div class="grid">
<div class="card">Faturado<b>{faturado}</b></div>
<div class="card">Recebido<b>{recebido}</b></div>
<div class="card">Pendente<b>{pendente}</b></div>
<div class="card">Cancelado<b>{cancelado}</b></div>
<div class="card">Recebido Pix<b>{rpix}</b></div>
<div class="card">Recebido dinheiro<b>{rdin}</b></div>
</div>
<p>{qtd} lançamento(s)</p>
<table><thead><tr><th>Paciente</th><th>Serviço</th><th>Valor</th><th>Forma</th><th>Status</th><th>Data</th></tr></thead>
<tbody>{linhas}</tbody></table>
</body></html>""".format(
        hoje=datetime.now().strftime("%d/%m/%Y %H:%M"),
        faturado=money(resumo["faturado"]),
        recebido=money(resumo["recebido"]),
        pendente=money(resumo["pendente"]),
        cancelado=money(resumo["cancelado"]),
        rpix=money(resumo["recebido_pix"]),
        rdin=money(resumo["recebido_dinheiro"]),
        qtd=resumo["quantidade"],
        linhas="".join(linhas) or "<tr><td colspan='6'>Nenhum lançamento no período.</td></tr>",
    )
    return html


@app.route("/api/admin/payments", methods=["POST"])
@login_required
def api_payments_create():
    data = request.get_json(silent=True) or {}
    db = get_db()
    pid = create_payment_record(
        db,
        patient_id=data.get("patient_id"),
        patient_name=data.get("patient_name") or "",
        service_id=data.get("service_id"),
        service_name=data.get("service_name") or data.get("servico") or "",
        amount=data.get("amount"),
        method=data.get("method") or data.get("forma_pagamento"),
        status=data.get("status") or "Pendente",
        notes=data.get("notes") or "",
        appointment_id=data.get("appointment_id"),
        registration_id=data.get("registration_id") or data.get("patient_id"),
    )
    db.commit()
    if not pid:
        return jsonify({"ok": False, "error": "Informe um valor válido."}), 400
    row = db.execute("SELECT * FROM payments WHERE id = ?", (pid,)).fetchone()
    return jsonify({"ok": True, "data": row_to_payment(row)}), 201


@app.route("/api/admin/payments/<int:pid>", methods=["PUT"])
@login_required
def api_payments_update(pid):
    db = get_db()
    row = db.execute("SELECT * FROM payments WHERE id = ?", (pid,)).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Pagamento não encontrado."}), 404
    data = request.get_json(silent=True) or {}
    status = normalize_payment_status(data.get("status") or row["status"])
    paid_at = data.get("paid_at", row["paid_at"])
    if status == "Pago" and not paid_at:
        paid_at = now_iso()
    if status != "Pago":
        paid_at = None if status != "Pago" else paid_at
    try:
        amount = float(data.get("amount") if "amount" in data else row["amount"])
    except (TypeError, ValueError):
        amount = row["amount"]
    method = normalize_payment_method(data.get("method") if "method" in data else row["method"])
    db.execute(
        """UPDATE payments SET patient_name = ?, amount = ?, status = ?, paid_at = ?, notes = ?,
           method = ?, service_name = ?, atualizadoEm = ?
           WHERE id = ?""",
        ((data.get("patient_name") or row["patient_name"]), amount, status, paid_at,
         data.get("notes") if "notes" in data else row["notes"], method,
         data.get("service_name") if "service_name" in data else row["service_name"],
         now_iso(), pid),
    )
    db.commit()
    updated = db.execute("SELECT * FROM payments WHERE id = ?", (pid,)).fetchone()
    return jsonify({"ok": True, "data": row_to_payment(updated)})


@app.route("/api/admin/payments/<int:pid>", methods=["DELETE"])
@login_required
def api_payments_delete(pid):
    db = get_db()
    if not db.execute("SELECT id FROM payments WHERE id = ?", (pid,)).fetchone():
        return jsonify({"ok": False, "error": "Pagamento não encontrado."}), 404
    db.execute("DELETE FROM payments WHERE id = ?", (pid,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/evaluations", methods=["GET"])
@login_required
def api_evaluations_list():
    return _list_rows("evaluations", "id DESC")


@app.route("/api/admin/evaluations", methods=["POST"])
@login_required
def api_evaluations_create():
    data = request.get_json(silent=True) or {}
    nome = (data.get("patient_name") or "").strip()
    if not nome:
        return jsonify({"ok": False, "error": "Informe o paciente."}), 400
    db = get_db()
    ts = now_iso()
    cur = db.execute(
        """INSERT INTO evaluations
           (patient_id, patient_name, evaluated_at, queixa, objetivos, historico,
            avaliacao_funcional, plano, observacoes, profissional, criadoEm, atualizadoEm)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (data.get("patient_id"), nome, data.get("evaluated_at") or ts[:10],
         (data.get("queixa") or "").strip(), (data.get("objetivos") or "").strip(),
         (data.get("historico") or "").strip(), (data.get("avaliacao_funcional") or "").strip(),
         (data.get("plano") or "").strip(), (data.get("observacoes") or "").strip(),
         (data.get("profissional") or "Waleska Paula").strip(), ts, ts),
    )
    db.commit()
    row = db.execute("SELECT * FROM evaluations WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify({"ok": True, "data": dict(row)}), 201


@app.route("/api/admin/evaluations/<int:eid>", methods=["DELETE"])
@login_required
def api_evaluations_delete(eid):
    db = get_db()
    if not db.execute("SELECT id FROM evaluations WHERE id = ?", (eid,)).fetchone():
        return jsonify({"ok": False, "error": "Avaliação não encontrada."}), 404
    db.execute("DELETE FROM evaluations WHERE id = ?", (eid,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/evolutions", methods=["GET"])
@login_required
def api_evolutions_list():
    return _list_rows("evolutions", "id DESC")


@app.route("/api/admin/evolutions", methods=["POST"])
@login_required
def api_evolutions_create():
    data = request.get_json(silent=True) or {}
    nome = (data.get("patient_name") or "").strip()
    if not nome:
        return jsonify({"ok": False, "error": "Informe o paciente."}), 400
    db = get_db()
    ts = now_iso()
    cur = db.execute(
        """INSERT INTO evolutions
           (patient_id, patient_name, appointment_id, evolution_date, procedimentos, exercicios,
            resposta, observacoes, proxima_conduta, profissional, criadoEm, atualizadoEm)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (data.get("patient_id"), nome, data.get("appointment_id"),
         data.get("evolution_date") or ts[:10],
         (data.get("procedimentos") or "").strip(), (data.get("exercicios") or "").strip(),
         (data.get("resposta") or "").strip(), (data.get("observacoes") or "").strip(),
         (data.get("proxima_conduta") or "").strip(),
         (data.get("profissional") or "Waleska Paula").strip(), ts, ts),
    )
    db.commit()
    row = db.execute("SELECT * FROM evolutions WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify({"ok": True, "data": dict(row)}), 201


@app.route("/api/admin/evolutions/<int:eid>", methods=["DELETE"])
@login_required
def api_evolutions_delete(eid):
    db = get_db()
    if not db.execute("SELECT id FROM evolutions WHERE id = ?", (eid,)).fetchone():
        return jsonify({"ok": False, "error": "Evolução não encontrada."}), 404
    db.execute("DELETE FROM evolutions WHERE id = ?", (eid,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/exercises", methods=["GET"])
@login_required
def api_exercises_list():
    return _list_rows("exercises", "nome ASC")


@app.route("/api/admin/exercises", methods=["POST"])
@login_required
def api_exercises_create():
    data = request.get_json(silent=True) or {}
    nome = (data.get("nome") or "").strip()
    if not nome:
        return jsonify({"ok": False, "error": "Informe o nome do exercício."}), 400
    db = get_db()
    ts = now_iso()
    cur = db.execute(
        """INSERT INTO exercises
           (nome, descricao, categoria, regiao, objetivo, instrucoes, criadoEm, atualizadoEm)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (nome, (data.get("descricao") or "").strip(), (data.get("categoria") or "").strip(),
         (data.get("regiao") or "").strip(), (data.get("objetivo") or "").strip(),
         (data.get("instrucoes") or "").strip(), ts, ts),
    )
    db.commit()
    row = db.execute("SELECT * FROM exercises WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify({"ok": True, "data": dict(row)}), 201


@app.route("/api/admin/exercises/<int:eid>", methods=["DELETE"])
@login_required
def api_exercises_delete(eid):
    db = get_db()
    if not db.execute("SELECT id FROM exercises WHERE id = ?", (eid,)).fetchone():
        return jsonify({"ok": False, "error": "Exercício não encontrado."}), 404
    db.execute("DELETE FROM exercises WHERE id = ?", (eid,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/documents", methods=["GET"])
@login_required
def api_documents_list():
    return _list_rows("documents", "id DESC")


@app.route("/api/admin/documents", methods=["POST"])
@login_required
def api_documents_create():
    data = request.get_json(silent=True) or {}
    titulo = (data.get("titulo") or "").strip()
    if not titulo:
        return jsonify({"ok": False, "error": "Informe o título."}), 400
    db = get_db()
    ts = now_iso()
    cur = db.execute(
        """INSERT INTO documents (patient_id, patient_name, titulo, tipo, notes, criadoEm)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (data.get("patient_id"), (data.get("patient_name") or "").strip(), titulo,
         (data.get("tipo") or "").strip(), (data.get("notes") or "").strip(), ts),
    )
    db.commit()
    row = db.execute("SELECT * FROM documents WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify({"ok": True, "data": dict(row)}), 201


@app.route("/api/admin/documents/<int:did>", methods=["DELETE"])
@login_required
def api_documents_delete(did):
    db = get_db()
    if not db.execute("SELECT id FROM documents WHERE id = ?", (did,)).fetchone():
        return jsonify({"ok": False, "error": "Documento não encontrado."}), 404
    db.execute("DELETE FROM documents WHERE id = ?", (did,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/users")
@login_required
def api_users_list():
    rows = get_db().execute("SELECT id, email, nome, role, criadoEm FROM admins ORDER BY id").fetchall()
    return jsonify({"ok": True, "data": [dict(r) for r in rows]})


init_db()

if __name__ == "__main__":
    print("=" * 60)
    print("Dra. Waleska Paula — servidor iniciado")
    print("Backend        : " + backend_label())
    print("Página pública : http://localhost:8000/")
    print("Painel admin   : http://localhost:8000/admin")
    print("=" * 60)
    app.run(host="0.0.0.0", port=8000, debug=False, threaded=True)
