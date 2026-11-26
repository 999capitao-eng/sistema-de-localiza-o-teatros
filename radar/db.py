import sqlite3
from dataclasses import asdict, fields

from .config import DB_PATH
from .models import Registro

CAMPOS = [f.name for f in fields(Registro)]
INSERT = (f"INSERT INTO registros ({', '.join(CAMPOS)}) "
          f"VALUES ({', '.join(':' + c for c in CAMPOS)})")

SCHEMA = """
CREATE TABLE IF NOT EXISTS registros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fonte TEXT NOT NULL,
    id_fonte TEXT NOT NULL,
    nome TEXT NOT NULL,
    cidade TEXT, uf TEXT,
    lat REAL, lon REAL,
    capacidade INTEGER,
    tipo_capacidade TEXT,
    site TEXT, telefone TEXT, endereco TEXT, url_fonte TEXT,
    coletado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS teatros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    cidade TEXT, uf TEXT,
    lat REAL, lon REAL,
    capacidade INTEGER,
    fonte_capacidade TEXT,
    confianca TEXT,
    conflito INTEGER DEFAULT 0,
    site TEXT, telefone TEXT, endereco TEXT,
    qtd_fontes INTEGER
);
CREATE TABLE IF NOT EXISTS vinculos (
    teatro_id INTEGER,
    registro_id INTEGER,
    PRIMARY KEY (teatro_id, registro_id)
);
"""


def conectar():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def salvar_registros(registros, fonte):
    """Substitui todos os registros de uma fonte pelos novos (idempotente)."""
    con = conectar()
    with con:
        con.execute("DELETE FROM registros WHERE fonte = ?", (fonte,))
        con.executemany(INSERT, [asdict(r) for r in registros])
    con.close()
    print(f"[db] {len(registros)} registros salvos para a fonte '{fonte}'")
