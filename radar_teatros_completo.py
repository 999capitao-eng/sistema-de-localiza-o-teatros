#!/usr/bin/env python3
"""
Radar de Teatros - instalador COMPLETO (projeto + painel de busca por cidade).

Como usar:
  1. Crie a pasta "projeto_indios" e abra no VS Code.
  2. Salve este arquivo dentro dela como setup_projeto.py
  3. No terminal do VS Code rode:   python setup_projeto.py
     (no Mac/Linux:                 python3 setup_projeto.py)

O script cria todas as pastas e arquivos, monta o ambiente virtual (.venv),
instala as bibliotecas, roda os testes e (se voce quiser) ja faz a coleta.
Para recriar arquivos que ja existem, rode com:  python setup_projeto.py --forcar
"""
import subprocess
import sys
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
FORCAR = "--forcar" in sys.argv

ARQUIVOS = {
    # ------------------------------------------------------------------
    "requirements.txt": r'''
requests>=2.31
beautifulsoup4>=4.12
unidecode>=1.3
rapidfuzz>=3.0
pytest>=8.0
ruff>=0.5
''',
    # ------------------------------------------------------------------
    ".gitignore": r'''
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
data/raw/
data/processed/
web/teatros.geojson
.env
''',
    # ------------------------------------------------------------------
    "README.md": r'''
# Radar de Teatros

Coleta, cruza e valida a capacidade de publico dos teatros brasileiros
usando OpenStreetMap, Wikidata e Mapa da Cultura, mais uma planilha manual.

## Rodar

    python -m radar.cli tudo        # pipeline completo
    python -m radar.cli sites       # gera candidatos de capacidade (revisao humana)
    python -m pytest                # testes

Depois de `tudo`, veja `data/processed/relatorio.md`, `teatros.csv`, `revisar.csv`.
Para o mapa: `cd web` e `python -m http.server 8000`, depois abra
http://localhost:8000/mapa.html

## Licencas e atribuicoes

- OpenStreetMap: ODbL. Citar "(c) colaboradores do OpenStreetMap".
- Wikidata: CC0 (dominio publico).
- Mapa da Cultura: dado aberto do poder publico; confirme a licenca no portal.
- Sites oficiais: guardar so o numero e o link de origem.
''',
    # ------------------------------------------------------------------
    "conftest.py": r'''
# Arquivo vazio de proposito: faz o pytest enxergar a pasta raiz do projeto.
''',
    # ------------------------------------------------------------------
    "data/manual/capacidades.csv": r'''
nome,cidade,uf,capacidade,tipo_capacidade,site,url_fonte,observacao
''',
    # ------------------------------------------------------------------
    ".vscode/settings.json": r'''
{
  "python.testing.pytestEnabled": true,
  "python.testing.unittestEnabled": false,
  "python.testing.pytestArgs": ["tests"],
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff"
  },
  "files.encoding": "utf8",
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/Scripts/python.exe"
}
''',
    # ------------------------------------------------------------------
    ".vscode/launch.json": r'''
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Radar: OSM",
      "type": "debugpy",
      "request": "launch",
      "module": "radar.cli",
      "args": ["osm"],
      "console": "integratedTerminal"
    },
    {
      "name": "Radar: consolidar",
      "type": "debugpy",
      "request": "launch",
      "module": "radar.cli",
      "args": ["consolidar"],
      "console": "integratedTerminal"
    },
    {
      "name": "Radar: tudo",
      "type": "debugpy",
      "request": "launch",
      "module": "radar.cli",
      "args": ["tudo"],
      "console": "integratedTerminal"
    }
  ]
}
''',
    # ------------------------------------------------------------------
    ".vscode/tasks.json": r'''
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Radar: pipeline completo",
      "type": "shell",
      "command": "python -m radar.cli tudo",
      "problemMatcher": []
    },
    {
      "label": "Radar: testes",
      "type": "shell",
      "command": "python -m pytest",
      "problemMatcher": []
    },
    {
      "label": "Radar: servir mapa",
      "type": "shell",
      "command": "python -m http.server 8000",
      "options": { "cwd": "${workspaceFolder}/web" },
      "problemMatcher": []
    }
  ]
}
''',
    # ------------------------------------------------------------------
    "radar/__init__.py": r'''
''',
    # ------------------------------------------------------------------
    "radar/config.py": r'''
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "manual"
WEB = ROOT / "web"
DB_PATH = PROCESSED / "radar.sqlite"

USER_AGENT = "RadarDeTeatros/0.1 (contato: @@EMAIL@@)"
REQUEST_DELAY = 1.5  # segundos de pausa entre requisicoes ao mesmo servidor

for pasta in (RAW, PROCESSED, MANUAL, WEB):
    pasta.mkdir(parents=True, exist_ok=True)
''',
    # ------------------------------------------------------------------
    "radar/http.py": r'''
import time

import requests

from .config import USER_AGENT


def get_session():
    sessao = requests.Session()
    sessao.headers.update({"User-Agent": USER_AGENT})
    return sessao


def request_with_retry(sessao, metodo, url, retries=4, backoff=5, timeout=180, **kwargs):
    ultimo_erro = None
    for tentativa in range(1, retries + 1):
        try:
            resp = sessao.request(metodo, url, timeout=timeout, **kwargs)
            if resp.status_code in (429, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {resp.status_code}")
            resp.raise_for_status()
            return resp
        except requests.RequestException as erro:
            ultimo_erro = erro
            espera = backoff * tentativa
            print(f"[aviso] tentativa {tentativa}/{retries} falhou: {erro}. "
                  f"Aguardando {espera}s")
            time.sleep(espera)
    raise RuntimeError(f"Falha apos {retries} tentativas: {ultimo_erro}")
''',
    # ------------------------------------------------------------------
    "radar/models.py": r'''
from dataclasses import dataclass, field
from datetime import datetime, timezone


def agora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Registro:
    fonte: str
    id_fonte: str
    nome: str
    cidade: str | None = None
    uf: str | None = None
    lat: float | None = None
    lon: float | None = None
    capacidade: int | None = None
    tipo_capacidade: str | None = None
    site: str | None = None
    telefone: str | None = None
    endereco: str | None = None
    url_fonte: str | None = None
    coletado_em: str = field(default_factory=agora)
''',
    # ------------------------------------------------------------------
    "radar/db.py": r'''
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
''',
    # ------------------------------------------------------------------
    "radar/normalize.py": r'''
import re

from unidecode import unidecode

PREFIXOS = re.compile(
    r"^(?:cine teatro|cineteatro|cine|teatro|auditorio|sala|centro cultural|"
    r"espaco cultural|casa de espetaculos)\s+"
)


def normalizar_nome(texto):
    s = unidecode(texto or "").lower()
    for variante in ("theatro", "theater", "theatre"):
        s = s.replace(variante, "teatro")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def nome_sem_prefixo(texto):
    s = normalizar_nome(texto)
    while True:
        novo = PREFIXOS.sub("", s)
        if novo == s:
            return s
        s = novo


def parse_capacidade(valor):
    """Converte '1.200', '350 lugares' etc. em inteiro. Fora de 10..20000 vira None."""
    if valor is None:
        return None
    achados = re.findall(r"\d[\d.,]*", str(valor))
    if not achados:
        return None
    bruto = achados[0].replace(".", "").replace(",", "")
    try:
        n = int(bruto)
    except ValueError:
        return None
    return n if 10 <= n <= 20000 else None
''',
    # ------------------------------------------------------------------
    "radar/osm.py": r'''
import json

from .config import RAW
from .db import salvar_registros
from .http import get_session, request_with_retry
from .models import Registro
from .normalize import parse_capacidade

SERVIDORES = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

CONSULTA = """
[out:json][timeout:180];
area["ISO3166-1"="BR"]->.br;
nwr["amenity"="theatre"](area.br);
out center tags;
"""


def coletar():
    sessao = get_session()
    ultimo_erro = None
    for url in SERVIDORES:
        try:
            resp = request_with_retry(sessao, "POST", url, data={"data": CONSULTA},
                                      timeout=300)
            dados = resp.json()
            break
        except RuntimeError as erro:
            ultimo_erro = erro
    else:
        raise ultimo_erro
    caminho = RAW / "osm_teatros.json"
    caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    print(f"[osm] resposta crua salva em {caminho}")
    return dados


def para_registros(dados):
    registros = []
    for el in dados.get("elements", []):
        tags = el.get("tags", {})
        nome = tags.get("name")
        if not nome:
            continue
        centro = el.get("center", {})
        lat = el.get("lat", centro.get("lat"))
        lon = el.get("lon", centro.get("lon"))
        capacidade = parse_capacidade(tags.get("capacity"))
        rua = " ".join(x for x in (tags.get("addr:street"),
                                   tags.get("addr:housenumber")) if x)
        registros.append(Registro(
            fonte="osm",
            id_fonte=f"{el['type']}/{el['id']}",
            nome=nome,
            cidade=tags.get("addr:city"),
            uf=tags.get("addr:state"),
            lat=lat,
            lon=lon,
            capacidade=capacidade,
            tipo_capacidade="desconhecido" if capacidade else None,
            site=tags.get("website") or tags.get("contact:website"),
            telefone=tags.get("phone") or tags.get("contact:phone"),
            endereco=rua or None,
            url_fonte=f"https://www.openstreetmap.org/{el['type']}/{el['id']}",
        ))
    return registros


def executar():
    dados = coletar()
    total = len(dados.get("elements", []))
    registros = para_registros(dados)
    com_cap = sum(1 for r in registros if r.capacidade)
    print(f"[osm] elementos: {total} | com nome: {len(registros)} | "
          f"com capacidade: {com_cap}")
    salvar_registros(registros, "osm")
    return registros
''',
    # ------------------------------------------------------------------
    "radar/wikidata.py": r'''
import json
import re

from .config import RAW
from .db import salvar_registros
from .http import get_session, request_with_retry
from .models import Registro

ENDPOINT = "https://query.wikidata.org/sparql"

CONSULTA = """
SELECT ?item ?itemLabel ?capacidade ?coord ?cidadeLabel ?site WHERE {
  ?item wdt:P31 wd:Q24354;
        wdt:P17 wd:Q155.
  OPTIONAL { ?item wdt:P1083 ?capacidade. }
  OPTIONAL { ?item wdt:P625 ?coord. }
  OPTIONAL { ?item wdt:P131 ?cidade. }
  OPTIONAL { ?item wdt:P856 ?site. }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "pt,en". }
}
"""


def coletar():
    sessao = get_session()
    resp = request_with_retry(
        sessao, "GET", ENDPOINT,
        params={"query": CONSULTA, "format": "json"},
        headers={"Accept": "application/sparql-results+json"},
        timeout=120,
    )
    dados = resp.json()
    caminho = RAW / "wikidata_teatros.json"
    caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    print(f"[wikidata] resposta crua salva em {caminho}")
    return dados


def valor(binding, chave):
    return binding.get(chave, {}).get("value")


def parse_ponto(wkt):
    """Converte 'Point(lon lat)' em (lat, lon)."""
    m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", wkt or "")
    return (float(m.group(2)), float(m.group(1))) if m else (None, None)


def para_registros(dados):
    vistos, saida = set(), []
    for b in dados["results"]["bindings"]:
        qid = valor(b, "item").rsplit("/", 1)[-1]
        nome = valor(b, "itemLabel")
        if not nome or re.fullmatch(r"Q\d+", nome):
            continue  # entidade sem rotulo: sem nome utilizavel
        try:
            cap = int(float(valor(b, "capacidade")))
        except (TypeError, ValueError):
            cap = None
        if (qid, cap) in vistos:
            continue
        vistos.add((qid, cap))
        lat, lon = parse_ponto(valor(b, "coord"))
        saida.append(Registro(
            fonte="wikidata", id_fonte=qid, nome=nome,
            cidade=valor(b, "cidadeLabel"), lat=lat, lon=lon, capacidade=cap,
            tipo_capacidade="desconhecido" if cap else None,
            site=valor(b, "site"),
            url_fonte=f"https://www.wikidata.org/wiki/{qid}",
        ))
    # se o item tem alguma linha com capacidade, descarta a linha sem capacidade
    com_cap = {r.id_fonte for r in saida if r.capacidade}
    return [r for r in saida if r.capacidade or r.id_fonte not in com_cap]


def executar():
    dados = coletar()
    registros = para_registros(dados)
    com_cap = sum(1 for r in registros if r.capacidade)
    print(f"[wikidata] registros: {len(registros)} | com capacidade: {com_cap}")
    salvar_registros(registros, "wikidata")
    return registros
''',
    # ------------------------------------------------------------------
    "radar/mapa_cultura.py": r'''
import json
import time

from .config import RAW, REQUEST_DELAY
from .db import salvar_registros
from .http import get_session, request_with_retry
from .models import Registro
from .normalize import parse_capacidade

BASE = "https://mapacultura.cultura.gov.br"  # confirme no navegador se der erro
CAMPOS = "id,name,location,endereco,En_Municipio,En_Estado,site,telefonePublico,capacidade"
TERMOS = ["teatro", "theatro"]


def coletar(por_pagina=200, max_paginas=100):
    sessao = get_session()
    todos = {}
    for termo in TERMOS:
        for pagina in range(1, max_paginas + 1):
            params = {
                "@select": CAMPOS,
                "@limit": por_pagina,
                "@page": pagina,
                "@order": "id ASC",
                "name": f"ILIKE(*{termo}*)",
            }
            resp = request_with_retry(sessao, "GET", f"{BASE}/api/space/find",
                                      params=params, timeout=60)
            lote = resp.json()
            if not isinstance(lote, list):
                raise RuntimeError(f"Resposta inesperada da API: {str(lote)[:200]}")
            if not lote:
                break
            for espaco in lote:
                todos[espaco["id"]] = espaco
            time.sleep(REQUEST_DELAY)
    lista = list(todos.values())
    caminho = RAW / "mapa_cultura_espacos.json"
    caminho.write_text(json.dumps(lista, ensure_ascii=False), encoding="utf-8")
    print(f"[mapa] {len(lista)} espacos salvos em {caminho}")
    return lista


def para_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def para_registros(espacos):
    registros = []
    for e in espacos:
        nome = (e.get("name") or "").strip()
        if not nome:
            continue
        local = e.get("location") or {}
        cap = parse_capacidade(e.get("capacidade"))
        registros.append(Registro(
            fonte="mapa_cultura",
            id_fonte=str(e["id"]),
            nome=nome,
            cidade=e.get("En_Municipio"),
            uf=e.get("En_Estado"),
            lat=para_float(local.get("latitude")),
            lon=para_float(local.get("longitude")),
            capacidade=cap,
            tipo_capacidade="desconhecido" if cap else None,
            site=e.get("site"),
            telefone=e.get("telefonePublico"),
            endereco=e.get("endereco"),
            url_fonte=f"{BASE}/espaco/{e['id']}",
        ))
    return registros


def executar():
    registros = para_registros(coletar())
    com_cap = sum(1 for r in registros if r.capacidade)
    print(f"[mapa] registros: {len(registros)} | com capacidade: {com_cap}")
    salvar_registros(registros, "mapa_cultura")
    return registros
''',
    # ------------------------------------------------------------------
    "radar/sites.py": r'''
import csv
import re
import time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup

from .config import PROCESSED, REQUEST_DELAY, USER_AGENT
from .db import conectar
from .http import get_session, request_with_retry

NUM = r"(?<![\d.])(\d{1,2}\.\d{3}|\d{2,4})(?!\d)"
PADROES = [
    re.compile(NUM + r"\s*(?:lugares|poltronas|assentos|espectadores|pessoas)", re.I),
    re.compile(r"(?:capacidade|lota[cç][aã]o)\D{0,40}?" + NUM, re.I),
]
LINKS_UTEIS = re.compile(r"sobre|hist|espa[cç]o|ficha|estrutura|alug|loca[cç]|institucional")


def permitido(url):
    partes = urlparse(url)
    robo = RobotFileParser()
    robo.set_url(f"{partes.scheme}://{partes.netloc}/robots.txt")
    try:
        robo.read()
    except Exception:
        return True  # sem robots.txt acessivel: segue com cautela
    return robo.can_fetch(USER_AGENT, url)


def links_relevantes(soup, base):
    achados = []
    for a in soup.find_all("a", href=True):
        alvo = urljoin(base, a["href"]).split("#")[0]
        rotulo = (a.get_text(" ") + " " + a["href"]).lower()
        mesmo_site = urlparse(alvo).netloc == urlparse(base).netloc
        if mesmo_site and alvo != base and alvo not in achados and LINKS_UTEIS.search(rotulo):
            achados.append(alvo)
    return achados[:3]


def baixar(sessao, url):
    try:
        resp = request_with_retry(sessao, "GET", url, retries=2, timeout=30)
        return BeautifulSoup(resp.text, "html.parser")
    except RuntimeError:
        return None


def buscar_candidatos(sessao, url):
    if not permitido(url):
        return []
    soup = baixar(sessao, url)
    if soup is None:
        return []
    paginas = [(url, soup)]
    for extra in links_relevantes(soup, url):
        if permitido(extra):
            time.sleep(REQUEST_DELAY)
            s = baixar(sessao, extra)
            if s is not None:
                paginas.append((extra, s))
    achados = []
    for endereco, pagina in paginas:
        texto = pagina.get_text(" ", strip=True)
        for padrao in PADROES:
            for m in padrao.finditer(texto):
                n = int(m.group(1).replace(".", ""))
                if 30 <= n <= 10000:
                    ini, fim = max(0, m.start() - 60), min(len(texto), m.end() + 60)
                    achados.append((endereco, n, texto[ini:fim]))
    return achados


def executar(limite=50):
    con = conectar()
    teatros = con.execute(
        "SELECT DISTINCT nome, site FROM registros "
        "WHERE site IS NOT NULL AND site != '' AND capacidade IS NULL LIMIT ?",
        (limite,),
    ).fetchall()
    con.close()
    sessao = get_session()
    saida = PROCESSED / "candidatos_capacidade.csv"
    with saida.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.writer(f)
        escritor.writerow(["teatro", "site", "pagina", "numero", "trecho"])
        for t in teatros:
            url = t["site"] if t["site"].startswith("http") else "https://" + t["site"]
            print(f"[sites] {t['nome']} -> {url}")
            for pagina, numero, trecho in buscar_candidatos(sessao, url):
                escritor.writerow([t["nome"], url, pagina, numero, trecho])
            time.sleep(REQUEST_DELAY)
    print(f"[sites] candidatos salvos em {saida}")
''',
    # ------------------------------------------------------------------
    "radar/manual.py": r'''
import csv

from .config import MANUAL
from .db import salvar_registros
from .models import Registro

ARQUIVO = MANUAL / "capacidades.csv"
COLUNAS = ["nome", "cidade", "uf", "capacidade", "tipo_capacidade", "site",
           "url_fonte", "observacao"]


def executar():
    if not ARQUIVO.exists():
        ARQUIVO.write_text(",".join(COLUNAS) + "\n", encoding="utf-8")
        print(f"[manual] arquivo criado: {ARQUIVO}")
    registros = []
    with ARQUIVO.open(encoding="utf-8-sig", newline="") as f:
        for i, linha in enumerate(csv.DictReader(f), start=2):
            nome = (linha.get("nome") or "").strip()
            if not nome:
                continue
            cap = (linha.get("capacidade") or "").strip()
            registros.append(Registro(
                fonte="manual",
                id_fonte=f"linha-{i}",
                nome=nome,
                cidade=(linha.get("cidade") or "").strip() or None,
                uf=(linha.get("uf") or "").strip() or None,
                capacidade=int(cap) if cap.isdigit() else None,
                tipo_capacidade=(linha.get("tipo_capacidade") or "").strip() or "desconhecido",
                site=(linha.get("site") or "").strip() or None,
                url_fonte=(linha.get("url_fonte") or "").strip() or None,
            ))
    salvar_registros(registros, "manual")
    return registros
''',
    # ------------------------------------------------------------------
    "radar/match.py": r'''
from collections import defaultdict
from math import asin, cos, floor, radians, sin, sqrt

from rapidfuzz import fuzz

from .normalize import nome_sem_prefixo, normalizar_nome


def haversine_m(lat1, lon1, lat2, lon2):
    raio = 6371000
    p1, p2 = radians(lat1), radians(lat2)
    dp, dl = p2 - p1, radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * raio * asin(sqrt(a))


def sao_o_mesmo(a, b):
    na, nb = nome_sem_prefixo(a["nome"]), nome_sem_prefixo(b["nome"])
    if not na or not nb:
        return False
    ordenada = fuzz.token_sort_ratio(na, nb)
    conjunto = fuzz.token_set_ratio(na, nb)
    tem_geo = all(x is not None for x in (a["lat"], a["lon"], b["lat"], b["lon"]))
    if tem_geo:
        d = haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
        if d <= 150:
            return max(ordenada, conjunto) >= 60
        if d <= 1000:
            return ordenada >= 85
        return False
    cidade_a = normalizar_nome(a["cidade"] or "")
    cidade_b = normalizar_nome(b["cidade"] or "")
    if cidade_a and cidade_a == cidade_b:
        return ordenada >= 90
    return False


def agrupar(registros):
    """Recebe lista de dicts e devolve lista de grupos (listas de dicts)."""
    pai = list(range(len(registros)))

    def achar(i):
        while pai[i] != i:
            pai[i] = pai[pai[i]]
            i = pai[i]
        return i

    def tentar_unir(i, j):
        if achar(i) != achar(j) and sao_o_mesmo(registros[i], registros[j]):
            pai[achar(i)] = achar(j)

    celulas = defaultdict(list)
    por_cidade = defaultdict(list)
    for i, r in enumerate(registros):
        if r["lat"] is not None and r["lon"] is not None:
            celulas[(floor(r["lat"] * 100), floor(r["lon"] * 100))].append(i)
        cidade = normalizar_nome(r["cidade"] or "")
        if cidade:
            por_cidade[cidade].append(i)

    for (cx, cy), indices in celulas.items():
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in celulas.get((cx + dx, cy + dy), []):
                    for i in indices:
                        if i < j:
                            tentar_unir(i, j)

    for i, r in enumerate(registros):
        if r["lat"] is None or r["lon"] is None:
            for j in por_cidade.get(normalizar_nome(r["cidade"] or ""), []):
                if i != j:
                    tentar_unir(i, j)

    grupos = defaultdict(list)
    for i, r in enumerate(registros):
        grupos[achar(i)].append(r)
    return list(grupos.values())
''',
    # ------------------------------------------------------------------
    "radar/consolidate.py": r'''
from .db import conectar
from .match import agrupar

PRIORIDADE = {"manual": 0, "wikidata": 1, "mapa_cultura": 2, "osm": 3}
ORDEM_COORD = ["osm", "wikidata", "mapa_cultura"]


def avaliar(capacidades):
    """capacidades: lista de (valor, fonte). Retorna (valor, fonte, confianca, conflito)."""
    if not capacidades:
        return None, None, "sem_dado", 0
    ordenadas = sorted(capacidades, key=lambda x: PRIORIDADE[x[1]])
    escolhido, fonte = ordenadas[0]
    valores = [v for v, _ in ordenadas]
    conflito = int(max(valores) > min(valores) * 1.10)
    concordam = {f for v, f in ordenadas if abs(v - escolhido) <= escolhido * 0.10}
    if fonte == "manual" or len(concordam) >= 2:
        confianca = "alta"
    elif conflito:
        confianca = "baixa"
    else:
        confianca = "media"
    return escolhido, fonte, confianca, conflito


def primeiro_valor(membros, campo):
    for m in sorted(membros, key=lambda m: PRIORIDADE[m["fonte"]]):
        if m[campo] not in (None, ""):
            return m[campo]
    return None


def consolidar():
    con = conectar()
    registros = [dict(r) for r in con.execute("SELECT * FROM registros")]
    grupos = agrupar(registros)
    with con:
        con.execute("DELETE FROM vinculos")
        con.execute("DELETE FROM teatros")
        for membros in grupos:
            caps = [(m["capacidade"], m["fonte"]) for m in membros if m["capacidade"]]
            cap, fonte_cap, confianca, conflito = avaliar(caps)
            geo = next((m for f in ORDEM_COORD for m in membros
                        if m["fonte"] == f and m["lat"] is not None), None)
            cur = con.execute(
                "INSERT INTO teatros (nome, cidade, uf, lat, lon, capacidade, "
                "fonte_capacidade, confianca, conflito, site, telefone, endereco, "
                "qtd_fontes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (primeiro_valor(membros, "nome"), primeiro_valor(membros, "cidade"),
                 primeiro_valor(membros, "uf"),
                 geo["lat"] if geo else None, geo["lon"] if geo else None,
                 cap, fonte_cap, confianca, conflito,
                 primeiro_valor(membros, "site"), primeiro_valor(membros, "telefone"),
                 primeiro_valor(membros, "endereco"),
                 len({m["fonte"] for m in membros})),
            )
            con.executemany("INSERT INTO vinculos VALUES (?, ?)",
                            [(cur.lastrowid, m["id"]) for m in membros])
    con.close()
    print(f"[consolidar] {len(registros)} registros viraram {len(grupos)} teatros")
''',
    # ------------------------------------------------------------------
    "radar/report.py": r'''
from .config import PROCESSED
from .db import conectar


def pct(parte, total):
    return 100 * (parte or 0) / total if total else 0


def gerar():
    con = conectar()
    linhas = ["# Relatorio do Radar de Teatros", "", "## Registros por fonte", ""]
    for r in con.execute(
        "SELECT fonte, COUNT(*) total, SUM(capacidade IS NOT NULL) com_cap "
        "FROM registros GROUP BY fonte ORDER BY total DESC"
    ):
        linhas.append(f"- {r['fonte']}: {r['total']} registros, "
                      f"{r['com_cap'] or 0} com capacidade "
                      f"({pct(r['com_cap'], r['total']):.1f}%)")
    t = con.execute(
        "SELECT COUNT(*) total, SUM(capacidade IS NOT NULL) com_cap, "
        "SUM(conflito) conflitos FROM teatros"
    ).fetchone()
    linhas += ["", "## Teatros consolidados", "",
               f"- Total: {t['total']}",
               f"- Com capacidade: {t['com_cap'] or 0} ({pct(t['com_cap'], t['total']):.1f}%)",
               f"- Com conflito entre fontes: {t['conflitos'] or 0}"]
    linhas += ["", "## Confianca da capacidade", ""]
    for r in con.execute("SELECT confianca, COUNT(*) n FROM teatros "
                         "GROUP BY confianca ORDER BY n DESC"):
        linhas.append(f"- {r['confianca']}: {r['n']}")
    linhas += ["", "## Teatros por quantidade de fontes", ""]
    for r in con.execute("SELECT qtd_fontes, COUNT(*) n FROM teatros "
                         "GROUP BY qtd_fontes ORDER BY qtd_fontes"):
        linhas.append(f"- {r['qtd_fontes']} fonte(s): {r['n']}")
    fora = con.execute(
        "SELECT COUNT(*) FROM registros WHERE lat IS NOT NULL AND "
        "(lat NOT BETWEEN -34 AND 6 OR lon NOT BETWEEN -74 AND -34)"
    ).fetchone()[0]
    linhas += ["", "## Checagens de sanidade", "",
               f"- Registros com coordenadas fora do Brasil: {fora}"]
    con.close()
    texto = "\n".join(linhas)
    (PROCESSED / "relatorio.md").write_text(texto, encoding="utf-8")
    print(texto)
''',
    # ------------------------------------------------------------------
    "radar/export.py": r'''
import csv
import json

from .config import PROCESSED, WEB
from .db import conectar


def salvar_csv(caminho, linhas):
    if not linhas:
        print(f"[export] nada para gravar em {caminho.name}")
        return
    with caminho.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        escritor.writeheader()
        escritor.writerows(linhas)
    print(f"[export] {len(linhas)} linhas em {caminho}")


def exportar():
    con = conectar()
    teatros = [dict(r) for r in con.execute(
        "SELECT * FROM teatros ORDER BY uf, cidade, nome")]
    con.close()
    salvar_csv(PROCESSED / "teatros.csv", teatros)
    revisar = [t for t in teatros if t["conflito"] or t["confianca"] == "baixa"]
    salvar_csv(PROCESSED / "revisar.csv", revisar)
    features = [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [t["lon"], t["lat"]]},
        "properties": {k: t[k] for k in ("nome", "cidade", "uf", "capacidade",
                                         "confianca", "site")},
    } for t in teatros if t["lat"] is not None and t["lon"] is not None]
    geojson = {"type": "FeatureCollection", "features": features}
    (WEB / "teatros.geojson").write_text(json.dumps(geojson, ensure_ascii=False),
                                         encoding="utf-8")
    print(f"[export] {len(features)} pontos em web/teatros.geojson")
''',
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    "tests/test_normalize.py": r'''
from radar.normalize import nome_sem_prefixo, normalizar_nome, parse_capacidade


def test_normalizar_nome():
    assert normalizar_nome("Theatro São Pedro") == "teatro sao pedro"


def test_nome_sem_prefixo():
    assert nome_sem_prefixo("Centro Cultural Teatro Guaíra") == "guaira"
    assert nome_sem_prefixo("Theatro da Paz") == "da paz"


def test_parse_capacidade():
    assert parse_capacidade("1.200") == 1200
    assert parse_capacidade("350 lugares") == 350
    assert parse_capacidade("abc") is None
    assert parse_capacidade("5") is None
    assert parse_capacidade(None) is None
''',
    # ------------------------------------------------------------------
    "tests/test_match.py": r'''
from radar.consolidate import avaliar
from radar.match import agrupar, haversine_m, sao_o_mesmo


def reg(nome, lat=None, lon=None, cidade=None):
    return {"nome": nome, "lat": lat, "lon": lon, "cidade": cidade}


def test_distancia_zero():
    assert haversine_m(-23.5, -46.6, -23.5, -46.6) == 0


def test_mesmo_teatro_com_grafias_diferentes():
    a = reg("Theatro da Paz", -1.4558, -48.5039)
    b = reg("Teatro da Paz", -1.4559, -48.5040)
    assert sao_o_mesmo(a, b)


def test_teatros_diferentes_vizinhos():
    a = reg("Teatro Alfa", -23.5500, -46.6300)
    b = reg("Teatro Beta", -23.5501, -46.6301)
    assert not sao_o_mesmo(a, b)


def test_sem_coordenada_exige_mesma_cidade():
    a = reg("Teatro Horizonte", cidade="Teresina")
    b = reg("Teatro Horizonte", cidade="Teresina")
    c = reg("Teatro Horizonte", cidade="Recife")
    assert sao_o_mesmo(a, b)
    assert not sao_o_mesmo(a, c)


def test_agrupar():
    regs = [reg("Teatro Alfa", -5.0, -42.8), reg("Theatro Alfa", -5.0001, -42.8001),
            reg("Teatro Beta", -9.0, -40.0)]
    assert len(agrupar(regs)) == 2


def test_avaliar_conflito_e_confianca():
    assert avaliar([]) == (None, None, "sem_dado", 0)
    assert avaliar([(900, "osm"), (910, "wikidata")])[2] == "alta"
    valor, fonte, confianca, conflito = avaliar([(906, "wikidata"), (1100, "wikidata")])
    assert (confianca, conflito) == ("baixa", 1)
    assert avaliar([(500, "osm"), (800, "manual")])[0:3] == (800, "manual", "alta")
''',
    # ------------------------------------------------------------------
    "web/mapa.html": r'''
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>Radar de Teatros</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <style>html, body, #mapa { height: 100%; margin: 0; }</style>
</head>
<body>
  <div id="mapa"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const esc = s => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const mapa = L.map("mapa").setView([-14.2, -51.9], 4);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors"
    }).addTo(mapa);
    fetch("teatros.geojson").then(r => r.json()).then(dados => {
      L.geoJSON(dados, {
        onEachFeature: (f, camada) => {
          const p = f.properties;
          camada.bindPopup(
            `<b>${esc(p.nome)}</b><br>${esc(p.cidade)}<br>` +
            `Capacidade: ${esc(p.capacidade || "sem dado")} (${esc(p.confianca)})`
          );
        }
      }).addTo(mapa);
    });
  </script>
</body>
</html>
''',
    # ------------------------------------------------------------------
    "radar/cidades.py": r"""
import json
import time

from .config import RAW
from .db import conectar
from .http import get_session, request_with_retry

CACHE = RAW / "cache_cidades.json"
URL = "https://nominatim.openstreetmap.org/reverse"
PAUSA = 1.1  # o Nominatim aceita no maximo 1 consulta por segundo


def _chave(lat, lon):
    return f"{lat:.3f},{lon:.3f}"


def _ler_cache():
    if CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    return {}


def _salvar_cache(cache):
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def _buscar(sessao, lat, lon):
    resp = request_with_retry(
        sessao, "GET", URL, retries=3, timeout=30,
        params={"format": "jsonv2", "lat": lat, "lon": lon, "zoom": 10,
                "accept-language": "pt-BR", "addressdetails": 1},
    )
    end = resp.json().get("address", {})
    cidade = (end.get("city") or end.get("town") or end.get("municipality")
              or end.get("village") or end.get("county"))
    iso = end.get("ISO3166-2-lvl4", "")
    uf = iso.split("-")[-1] if iso.startswith("BR-") else None
    return {"cidade": cidade, "uf": uf}


def executar():
    con = conectar()
    linhas = con.execute(
        "SELECT id, lat, lon, cidade, uf FROM teatros "
        "WHERE lat IS NOT NULL AND lon IS NOT NULL "
        "AND (cidade IS NULL OR cidade = '' OR uf IS NULL OR uf = '')"
    ).fetchall()
    cache = _ler_cache()
    faltam = sum(1 for t in linhas if _chave(t["lat"], t["lon"]) not in cache)
    print(f"[cidades] {len(linhas)} teatros sem cidade/UF; {faltam} consultas novas "
          f"(~{int(faltam * PAUSA / 60) + 1} min). Ctrl+C para parar e continuar depois.")
    sessao = get_session()
    novos = 0
    try:
        for t in linhas:
            k = _chave(t["lat"], t["lon"])
            if k in cache:
                continue
            try:
                cache[k] = _buscar(sessao, t["lat"], t["lon"])
            except RuntimeError as erro:
                print(f"[cidades] pulei {k}: {erro}")
                continue
            novos += 1
            time.sleep(PAUSA)
            if novos % 25 == 0:
                _salvar_cache(cache)
                print(f"[cidades] {novos}/{faltam} consultas feitas")
    except KeyboardInterrupt:
        print("[cidades] parado. O progresso foi salvo; rode de novo para continuar.")
    _salvar_cache(cache)
    with con:
        for t in linhas:
            achado = cache.get(_chave(t["lat"], t["lon"]))
            if not achado:
                continue
            con.execute(
                "UPDATE teatros SET cidade = ?, uf = ? WHERE id = ?",
                (t["cidade"] or achado["cidade"], t["uf"] or achado["uf"], t["id"]),
            )
    con.close()
    print("[cidades] banco atualizado")
""",
    # ------------------------------------------------------------------
    "radar/painel.py": r"""
import json

from .config import WEB
from .db import conectar

TEMPLATE = r'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Radar de Teatros - Contatos</title>
<style>
:root{color-scheme:light dark;--bg:#f6f7f9;--card:#fff;--txt:#1b1f24;--mut:#667085;--bd:#dfe3e8;--wa:#16a34a}
@media (prefers-color-scheme:dark){:root{--bg:#14171a;--card:#1d2125;--txt:#eceff1;--mut:#9aa4ad;--bd:#2c3238;--wa:#22c55e}}
*{box-sizing:border-box}
body{margin:0;font:16px/1.45 system-ui,sans-serif;background:var(--bg);color:var(--txt)}
header{position:sticky;top:0;background:var(--bg);padding:14px 16px;border-bottom:1px solid var(--bd);z-index:5}
h1{margin:0 0 10px;font-size:20px}
.linha{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
input[type=search],select,textarea{font:inherit;padding:10px 12px;border:1px solid var(--bd);border-radius:8px;background:var(--card);color:var(--txt)}
#q{flex:1;min-width:220px;font-size:18px}
main{max-width:1000px;margin:0 auto;padding:16px}
details{margin-top:10px}
textarea{width:100%;min-height:90px}
.info{color:var(--mut);margin:4px 0 14px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:14px;margin-bottom:12px}
.card h3{margin:0 0 4px;font-size:18px}
.mut{color:var(--mut);font-size:14px}
.tags{margin:8px 0;display:flex;gap:6px;flex-wrap:wrap}
.tag{font-size:13px;padding:2px 8px;border-radius:99px;border:1px solid var(--bd)}
.acoes{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;align-items:center}
.btn{display:inline-block;padding:8px 12px;border-radius:8px;border:1px solid var(--bd);text-decoration:none;color:var(--txt);font-size:15px}
.btn.zap{background:var(--wa);border-color:var(--wa);color:#fff;font-weight:600}
</style>
</head>
<body>
<header>
  <h1>Radar de Teatros</h1>
  <div class="linha">
    <input id="q" type="search" list="cidades" placeholder="Digite a cidade (ex: Teresina) ou o nome do teatro" autofocus>
    <label><input type="checkbox" id="soTel"> só com telefone</label>
    <select id="stF"></select>
  </div>
  <details>
    <summary>Mensagem padrão do WhatsApp (pode editar)</summary>
    <p class="mut">Use {teatro} e {cidade}. Troque ____ pelo seu nome. O botão só abre o WhatsApp: você aperta enviar.</p>
    <textarea id="msg"></textarea>
  </details>
</header>
<main>
  <div class="info" id="info"></div>
  <div id="lista"></div>
</main>
<datalist id="cidades"></datalist>
<script>
const DADOS = /*DADOS*/[];
const STATUS = [["novo","Novo"],["contatado","Contatado"],["respondeu","Respondeu"],["negociando","Negociando"],["fechado","Show fechado"],["descartado","Descartado"]];
const MSG_PADRAO = "Olá! Meu nome é ____ e produzo shows. Tenho interesse em apresentar um espetáculo no {teatro}, em {cidade}. Poderia me passar informações sobre pauta, valores e a capacidade da casa? Obrigado!";
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
const norm = s => String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().trim();
const ler = (k, pad) => { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : pad; } catch (e) { return pad; } };
const guardar = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };

let status = ler("radar_status", {});
$("msg").value = ler("radar_msg", MSG_PADRAO);
$("stF").innerHTML = '<option value="">Todos os status</option>' + STATUS.map(s => `<option value="${s[0]}">${s[1]}</option>`).join("");

const contagem = {};
DADOS.forEach(t => { if (t.cidade) contagem[t.cidade] = (contagem[t.cidade] || 0) + 1; });
$("cidades").innerHTML = Object.keys(contagem).sort().map(c => `<option value="${esc(c)}">`).join("");

const primeiroTel = t => String(t.telefone || "").split(/[;,\/]/)[0].trim();
function zap(tel) {
  let d = String(tel || "").replace(/\D/g, "").replace(/^0+/, "");
  if (!d) return null;
  if (!d.startsWith("55") && (d.length === 10 || d.length === 11)) d = "55" + d;
  return d.length >= 12 ? d : null;
}
function siteUrl(s) {
  if (!s) return null;
  return /^https?:\/\//i.test(s) ? s : "https://" + s;
}

function card(t) {
  const tel = primeiroTel(t), z = zap(tel), site = siteUrl(t.site);
  const msg = $("msg").value.replace(/\{teatro\}/g, t.nome).replace(/\{cidade\}/g, t.cidade || "sua cidade");
  const mapa = "https://www.google.com/maps/search/?api=1&query=" +
    (t.lat != null ? t.lat + "," + t.lon : encodeURIComponent(t.nome + " " + (t.cidade || "")));
  const google = "https://www.google.com/search?q=" + encodeURIComponent(t.nome + " " + (t.cidade || "") + " contato telefone");
  const atual = status[t.id] || "novo";
  const opts = STATUS.map(s => `<option value="${s[0]}"${s[0] === atual ? " selected" : ""}>${s[1]}</option>`).join("");
  const capa = t.capacidade ? "Capacidade: " + t.capacidade + " (confiança " + esc(t.confianca) + ")" : "Capacidade: sem dado";
  return `<div class="card">
    <h3>${esc(t.nome)}</h3>
    <div class="mut">${esc(t.cidade || "cidade não informada")}${t.uf ? " - " + esc(t.uf) : ""}${t.endereco ? " · " + esc(t.endereco) : ""}</div>
    <div class="tags">
      <span class="tag">${capa}</span>
      <span class="tag">${tel ? "Tel: " + esc(tel) : "Sem telefone na base"}</span>
    </div>
    <div class="acoes">
      ${z ? '<a class="btn zap" target="_blank" rel="noopener" href="https://wa.me/' + z + "?text=" + encodeURIComponent(msg) + '">WhatsApp</a>' : ""}
      ${tel ? '<a class="btn" href="tel:' + esc(tel) + '">Ligar</a>' : ""}
      ${site ? '<a class="btn" target="_blank" rel="noopener" href="' + esc(site) + '">Site</a>' : ""}
      <a class="btn" target="_blank" rel="noopener" href="${esc(mapa)}">Mapa</a>
      <a class="btn" target="_blank" rel="noopener" href="${esc(google)}">Buscar contato</a>
      <select data-id="${esc(t.id)}">${opts}</select>
    </div>
  </div>`;
}

function desenhar() {
  const q = norm($("q").value), soTel = $("soTel").checked, st = $("stF").value;
  const semCidade = DADOS.filter(t => !t.cidade).length;
  if (!q) {
    $("info").textContent = DADOS.length + " teatros na base. Digite uma cidade para começar." +
      (semCidade ? " (" + semCidade + " ainda sem cidade: rode o comando cidades.)" : "");
    $("lista").innerHTML = "";
    return;
  }
  const lista = DADOS.filter(t => {
    const achou = norm(t.cidade).includes(q) || norm(t.nome).includes(q) || norm(t.uf) === q;
    if (!achou) return false;
    if (soTel && !primeiroTel(t)) return false;
    if (st && (status[t.id] || "novo") !== st) return false;
    return true;
  });
  lista.sort((a, b) => (!!primeiroTel(b) - !!primeiroTel(a)) || ((b.capacidade || 0) - (a.capacidade || 0)) || a.nome.localeCompare(b.nome));
  const com = lista.filter(t => primeiroTel(t)).length;
  $("info").textContent = lista.length + " teatros encontrados, " + com + " com telefone." +
    (lista.length > 100 ? " Mostrando os 100 primeiros." : "");
  $("lista").innerHTML = lista.slice(0, 100).map(card).join("") || "<p>Nenhum teatro encontrado.</p>";
}

$("q").addEventListener("input", desenhar);
$("soTel").addEventListener("change", desenhar);
$("stF").addEventListener("change", desenhar);
$("msg").addEventListener("input", () => { guardar("radar_msg", $("msg").value); desenhar(); });
$("lista").addEventListener("change", e => {
  const id = e.target.dataset.id;
  if (id) { status[id] = e.target.value; guardar("radar_status", status); }
});
desenhar();
</script>
</body>
</html>
'''


def gerar():
    con = conectar()
    teatros = [dict(r) for r in con.execute(
        "SELECT id, nome, cidade, uf, lat, lon, capacidade, confianca, site, "
        "telefone, endereco FROM teatros ORDER BY uf, cidade, nome")]
    con.close()
    dados = json.dumps(teatros, ensure_ascii=False).replace("</", "<\\/")
    destino = WEB / "sistema.html"
    destino.write_text(TEMPLATE.replace("/*DADOS*/[]", dados), encoding="utf-8")
    com_cidade = sum(1 for t in teatros if t["cidade"])
    com_tel = sum(1 for t in teatros if t["telefone"])
    print(f"[painel] {len(teatros)} teatros | {com_cidade} com cidade | "
          f"{com_tel} com telefone")
    print(f"[painel] painel gerado em {destino}")
""",
    # ------------------------------------------------------------------
    "radar/cli.py": r"""
import argparse
import sys

from . import (cidades, consolidate, export, manual, mapa_cultura, osm, painel,
               report, sites, wikidata)

COMANDOS = {
    "osm": osm.executar,
    "wikidata": wikidata.executar,
    "mapa": mapa_cultura.executar,
    "manual": manual.executar,
    "sites": sites.executar,
    "consolidar": consolidate.consolidar,
    "cidades": cidades.executar,
    "relatorio": report.gerar,
    "exportar": export.exportar,
    "painel": painel.gerar,
}
PIPELINE = ["osm", "wikidata", "mapa", "manual", "consolidar", "cidades",
            "relatorio", "exportar", "painel"]


def main():
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8")
        except Exception:
            pass
    parser = argparse.ArgumentParser(prog="radar", description="Radar de Teatros")
    parser.add_argument("comando", choices=[*COMANDOS, "tudo"])
    args = parser.parse_args()
    if args.comando != "tudo":
        COMANDOS[args.comando]()
        return
    for nome in PIPELINE:
        print(f"\n=== {nome} ===")
        try:
            COMANDOS[nome]()
        except Exception as erro:
            print(f"[erro] etapa '{nome}' falhou: {erro}")


if __name__ == "__main__":
    main()
""",
}


# ----------------------------------------------------------------------
# Daqui para baixo e o instalador em si
# ----------------------------------------------------------------------
def perguntar(texto, padrao):
    try:
        resp = input(texto).strip()
    except EOFError:
        resp = ""
    return resp or padrao


def rodar(comando, **kw):
    return subprocess.run(comando, cwd=RAIZ, **kw)


def main():
    if sys.version_info < (3, 10):
        sys.exit("Precisa de Python 3.10 ou maior (o ideal e 3.11+).")

    print("=== Radar de Teatros: instalador ===")
    print(f"Pasta do projeto: {RAIZ}\n")
    email = perguntar(
        "Seu e-mail de contato (as APIs publicas pedem isso; Enter para usar um de exemplo): ",
        "seu-email@exemplo.com",
    )

    print("\n[1/5] Criando pastas e arquivos...")
    for pasta in ("data/raw", "data/processed", "data/manual"):
        (RAIZ / pasta).mkdir(parents=True, exist_ok=True)
    for caminho, conteudo in ARQUIVOS.items():
        destino = RAIZ / caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        if destino.exists() and not FORCAR:
            print(f"  [pulado] {caminho} (ja existe)")
            continue
        texto = conteudo.lstrip("\n").replace("@@EMAIL@@", email)
        destino.write_text(texto, encoding="utf-8", newline="\n")
        print(f"  [criado] {caminho}")

    print("\n[2/5] Criando o ambiente virtual (.venv)...")
    venv = RAIZ / ".venv"
    if not venv.exists():
        rodar([sys.executable, "-m", "venv", str(venv)], check=True)
    py = venv / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")
    if not sys.platform.startswith("win"):
        # em Mac/Linux o caminho do interpretador e diferente no settings.json
        cfg = RAIZ / ".vscode" / "settings.json"
        if cfg.exists():
            cfg.write_text(
                cfg.read_text(encoding="utf-8").replace(
                    "Scripts/python.exe", "bin/python"),
                encoding="utf-8",
            )

    print("\n[3/5] Instalando as bibliotecas (pode levar um minuto)...")
    rodar([str(py), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    rodar([str(py), "-m", "pip", "install", "-r", "requirements.txt"], check=True)

    print("\n[4/5] Rodando os testes...")
    teste = rodar([str(py), "-m", "pytest", "-q"])
    if teste.returncode == 0:
        print("  Testes OK.")
    else:
        print("  Algum teste falhou. Veja a mensagem acima.")

    if not (RAIZ / ".git").exists():
        try:
            rodar(["git", "init"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            pass

    print("\n[5/5] Coleta de dados")
    resp = perguntar(
        "Rodar a coleta agora? Leva uns 30 minutos (descobrir a cidade de cada\n"
        "teatro e a parte lenta). Pode parar com Ctrl+C e continuar depois com:\n"
        "  python -m radar.cli tudo\n[S/n]: ", "s").lower()
    if resp.startswith("s"):
        try:
            rodar([str(py), "-m", "radar.cli", "tudo"])
        except KeyboardInterrupt:
            print("\nParado. Para continuar depois:  python -m radar.cli tudo")
        print("\nPronto! Veja data/processed/relatorio.md e data/processed/teatros.csv")
    else:
        print("Ok. Para coletar depois, rode:  python -m radar.cli tudo")

    print("\n=== Fim ===")
    print("No VS Code: Ctrl+Shift+P > Python: Select Interpreter > escolha o da pasta .venv")
    print("Depois, no terminal do VS Code, ative o ambiente:")
    print("  Windows:    .venv\\Scripts\\Activate.ps1")
    print("  Mac/Linux:  source .venv/bin/activate")
    sistema = RAIZ / "web" / "sistema.html"
    if sistema.exists():
        print(f"Abrindo o painel: {sistema}")
        webbrowser.open(sistema.as_uri())
    print("Para abrir o painel depois: de duplo clique em web/sistema.html")


if __name__ == "__main__":
    main()
