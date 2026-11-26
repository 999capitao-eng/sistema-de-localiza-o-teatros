#!/usr/bin/env python3
r"""
Radar de Teatros - investigador de contatos.

Rode na pasta do projeto (com o .venv ja criado):
    .\.venv\Scripts\python.exe melhorar_contatos.py

O que faz:
  - cria radar/contatos.py: procura WhatsApp, telefone, e-mail e Instagram
    (1) nas etiquetas do OpenStreetMap que ja foram baixadas e
    (2) nos sites dos teatros (respeitando o robots.txt)
  - refaz radar/painel.py: painel com botao de WhatsApp em cada teatro
  - atualiza radar/cli.py: novo comando "contatos"
  - roda a investigacao, gera o painel e abre no navegador
"""
import subprocess
import sys
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

ARQUIVOS = {
    # ------------------------------------------------------------------
    "radar/contatos.py": r"""
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from .config import RAW, USER_AGENT
from .db import conectar
from .models import agora

LIMITE_MIN = 15  # minutos maximos de coleta de sites por rodada
THREADS = 8      # sites diferentes ao mesmo tempo (cada site recebe 1 pedido por vez)

DDDS = set(
    "11 12 13 14 15 16 17 18 19 21 22 24 27 28 31 32 33 34 35 37 38 41 42 43 44 45 "
    "46 47 48 49 51 53 54 55 61 62 63 64 65 66 67 68 69 71 73 74 75 77 79 81 82 83 "
    "84 85 86 87 88 89 91 92 93 94 95 96 97 98 99".split()
)

RE_TEL = re.compile(r"(?<!\d)(?:\+?55[\s.-]?)?\(?0?(\d{2})\)?[\s.-]?(9?\d{4})[\s.-]?(\d{4})(?!\d)")
RE_ZAP = re.compile(r"(?:wa\.me/|whatsapp\.com/send/?\?[^\"'\s>]*?phone=|whatsapp://send/?\?[^\"'\s>]*?phone=)\+?(\d{10,15})", re.I)
RE_ZAP_MSG = re.compile(r"https?://wa\.me/message/[A-Za-z0-9]+", re.I)
RE_TELHREF = re.compile(r"href=[\"']tel:([^\"']+)[\"']", re.I)
RE_MAIL = re.compile(r"mailto:([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})", re.I)
RE_INSTA = re.compile(r"instagram\.com/([A-Za-z0-9_.]{2,30})", re.I)
RE_FACE = re.compile(r"facebook\.com/([A-Za-z0-9_.\-]{3,60})", re.I)
LINKS = re.compile(r"contato|contact|fale|atendimento|loca[c\xe7]|alug|pauta|produ[c\xe7]|sobre|institucional|quem", re.I)
IGNORAR = {"p", "reel", "reels", "explore", "accounts", "tv", "stories", "share", "sharer",
           "sharer.php", "plugins", "tr", "dialog", "login", "pages", "groups", "events",
           "watch", "hashtag", "profile.php", "policies", "privacy"}
TIPOS_FONE = ("whatsapp", "celular", "fixo")

SCHEMA = '''
CREATE TABLE IF NOT EXISTS contatos (
    chave TEXT, tipo TEXT, valor TEXT, origem TEXT, confianca TEXT,
    PRIMARY KEY (chave, tipo, valor)
);
CREATE TABLE IF NOT EXISTS contatos_sites (
    site TEXT PRIMARY KEY, feito_em TEXT
);
'''


def criar_tabelas(con):
    con.executescript(SCHEMA)


def norm_fone(texto):
    # devolve (numero_com_55, tipo) ou None. tipo: celular ou fixo
    m = RE_TEL.search(texto or "")
    if not m:
        return None
    ddd, a, b = m.groups()
    if ddd not in DDDS:
        return None
    n = a + b
    if len(n) == 9 and n[0] == "9":
        return "55" + ddd + n, "celular"
    if len(n) == 8 and n[0] in "2345":
        return "55" + ddd + n, "fixo"
    return None


def norm_num(texto):
    d = re.sub(r"\D", "", texto or "").lstrip("0")
    if len(d) in (10, 11):
        d = "55" + d
    return d if 12 <= len(d) <= 13 else None


def _robots_ok(sessao, cache, url):
    partes = urlparse(url)
    if partes.netloc not in cache:
        rp = RobotFileParser()
        try:
            r = sessao.get(f"{partes.scheme}://{partes.netloc}/robots.txt", timeout=10)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except requests.RequestException:
            rp.parse([])
        cache[partes.netloc] = rp
    return cache[partes.netloc].can_fetch(USER_AGENT, url)


def raspar_site(site):
    url = site if site.startswith("http") else "https://" + site
    host = urlparse(url).netloc.lower()
    achados = {}

    def add(tipo, valor, origem, conf):
        achados.setdefault((tipo, valor), (origem, conf))

    if "instagram.com" in host:
        add("instagram", url, url, "alta")
        return achados
    if "facebook.com" in host:
        add("facebook", url, url, "alta")
        return achados

    sessao = requests.Session()
    sessao.headers.update({"User-Agent": USER_AGENT})
    robots = {}

    def baixar(u):
        if not _robots_ok(sessao, robots, u):
            return None
        try:
            r = sessao.get(u, timeout=15)
            if r.status_code != 200 or "html" not in r.headers.get("content-type", "html"):
                return None
            return r.text
        except requests.RequestException:
            return None

    home = baixar(url)
    if home is None:
        return achados
    paginas = [(url, home)]
    extras = []
    for a in BeautifulSoup(home, "html.parser").find_all("a", href=True):
        alvo = urljoin(url, a["href"]).split("#")[0]
        if (urlparse(alvo).netloc == urlparse(url).netloc and alvo != url
                and alvo not in extras and LINKS.search(a.get_text(" ") + " " + a["href"])):
            extras.append(alvo)
    for alvo in extras[:4]:
        time.sleep(1.0)
        h = baixar(alvo)
        if h:
            paginas.append((alvo, h))

    for pagina, h in paginas:
        for n in RE_ZAP.findall(h):
            num = norm_num(n)
            if num:
                add("whatsapp", num, pagina, "alta")
        for link in RE_ZAP_MSG.findall(h):
            add("whatsapp", link, pagina, "alta")
        for t in RE_TELHREF.findall(h):
            r = norm_fone(t)
            if r:
                add(r[1], r[0], pagina, "alta")
        for e in RE_MAIL.findall(h):
            add("email", e.lower(), pagina, "alta")
        for u in RE_INSTA.findall(h):
            if u.lower() not in IGNORAR:
                add("instagram", "https://www.instagram.com/" + u.strip("."), pagina, "media")
        for u in RE_FACE.findall(h):
            if u.lower() not in IGNORAR:
                add("facebook", "https://www.facebook.com/" + u.strip("."), pagina, "media")
        sopa = BeautifulSoup(h, "html.parser")
        for tag in sopa(["script", "style"]):
            tag.decompose()
        txt = sopa.get_text(" ", strip=True)
        for m in RE_TEL.finditer(txt):
            r = norm_fone(m.group(0))
            if r:
                perto = txt[max(0, m.start() - 40):m.start()].lower()
                tipo = "whatsapp" if (r[1] == "celular" and ("whats" in perto or "zap" in perto)) else r[1]
                add(tipo, r[0], pagina, "media")

    fones = sorted((kv for kv in achados.items() if kv[0][0] in TIPOS_FONE),
                   key=lambda kv: TIPOS_FONE.index(kv[0][0]))
    for chave, _ in fones[6:]:
        del achados[chave]
    for tipo in ("instagram", "facebook"):
        extras_social = [k for k in achados if k[0] == tipo]
        for k in extras_social[1:]:
            del achados[k]
    return achados


def _osm_cru(con):
    caminho = RAW / "osm_teatros.json"
    if not caminho.exists():
        print("[contatos] arquivo cru do OSM nao encontrado; pulei essa parte")
        return
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    total = 0
    with con:
        con.execute("DELETE FROM contatos WHERE chave LIKE 'osm:%'")

        def add(chave, tipo, valor, conf):
            nonlocal total
            cur = con.execute(
                "INSERT OR IGNORE INTO contatos VALUES (?,?,?,?,?)",
                (chave, tipo, valor, "OpenStreetMap", conf))
            total += cur.rowcount

        for el in dados.get("elements", []):
            tags = el.get("tags", {})
            chave = f"osm:{el['type']}/{el['id']}"
            for k in ("whatsapp", "contact:whatsapp"):
                for v in str(tags.get(k, "")).split(";"):
                    num = norm_num(v)
                    if num:
                        add(chave, "whatsapp", num, "alta")
            for k in ("phone", "contact:phone", "mobile", "contact:mobile"):
                for v in str(tags.get(k, "")).split(";"):
                    r = norm_fone(v)
                    if r:
                        add(chave, r[1], r[0], "media")
            for k in ("email", "contact:email"):
                v = str(tags.get(k, "")).strip().lower()
                if "@" in v:
                    add(chave, "email", v.split(";")[0], "alta")
            for k in ("contact:instagram", "instagram"):
                v = str(tags.get(k, "")).strip()
                if v:
                    add(chave, "instagram",
                        v if v.startswith("http") else "https://www.instagram.com/" + v.lstrip("@"),
                        "alta")
            for k in ("contact:facebook", "facebook"):
                v = str(tags.get(k, "")).strip()
                if v:
                    add(chave, "facebook",
                        v if v.startswith("http") else "https://www.facebook.com/" + v, "alta")
    print(f"[contatos] {total} contatos vindos das etiquetas do OpenStreetMap")


def _gravar(con, site, achados):
    with con:
        for (tipo, valor), (origem, conf) in achados.items():
            con.execute("INSERT OR IGNORE INTO contatos VALUES (?,?,?,?,?)",
                        (f"site:{site}", tipo, valor, origem, conf))
        con.execute("INSERT OR REPLACE INTO contatos_sites VALUES (?,?)", (site, agora()))


def executar():
    con = conectar()
    criar_tabelas(con)
    _osm_cru(con)
    sites = [r["site"] for r in con.execute(
        "SELECT DISTINCT site FROM registros WHERE site IS NOT NULL AND site != ''")]
    feitos = {r["site"] for r in con.execute("SELECT site FROM contatos_sites")}
    pendentes = [s for s in sites if s not in feitos]
    print(f"[contatos] {len(sites)} sites na base; {len(pendentes)} ainda nao visitados "
          f"(maximo {LIMITE_MIN} min por rodada; Ctrl+C para parar)")
    inicio = time.time()
    ex = ThreadPoolExecutor(max_workers=THREADS)
    futuros = {ex.submit(raspar_site, s): s for s in pendentes}
    prontos = 0
    try:
        for fut in as_completed(futuros):
            try:
                achados = fut.result()
            except Exception:
                continue
            _gravar(con, futuros[fut], achados)
            prontos += 1
            if prontos % 20 == 0:
                print(f"[contatos] {prontos}/{len(pendentes)} sites visitados")
            if time.time() - inicio > LIMITE_MIN * 60:
                print("[contatos] tempo da rodada acabou; rode de novo para continuar")
                break
    except KeyboardInterrupt:
        print("[contatos] parado; o progresso foi salvo")
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
    resumo = con.execute("SELECT tipo, COUNT(*) n FROM contatos GROUP BY tipo").fetchall()
    print("[contatos] total guardado: " + ", ".join(f"{r['tipo']}={r['n']}" for r in resumo))
    con.close()
""",
    # ------------------------------------------------------------------
    "radar/painel.py": r"""
import json
from collections import defaultdict

from .config import WEB
from .contatos import criar_tabelas, norm_fone
from .db import conectar

ORDEM = {"whatsapp": 0, "celular": 1, "fixo": 2}

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
input,select,textarea{font:inherit;padding:10px 12px;border:1px solid var(--bd);border-radius:8px;background:var(--card);color:var(--txt)}
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
.btn{display:inline-block;padding:8px 12px;border-radius:8px;border:1px solid var(--bd);background:var(--card);text-decoration:none;color:var(--txt);font-size:15px;cursor:pointer}
.btn.zap{background:var(--wa);border-color:var(--wa);color:#fff;font-weight:600}
.btn.zap.prov{opacity:.82}
.man{width:230px;padding:8px 10px}
</style>
</head>
<body>
<header>
  <h1>Radar de Teatros</h1>
  <div class="linha">
    <input id="q" type="search" list="cidades" placeholder="Digite a cidade (ex: Teresina) ou o nome do teatro" autofocus>
    <label><input type="checkbox" id="soNum"> só com telefone/WhatsApp</label>
    <select id="stF"></select>
  </div>
  <details>
    <summary>Mensagem padrão (pode editar)</summary>
    <p class="mut">Use {teatro} e {cidade}. Troque ____ pelo seu nome. Os botões só abrem o WhatsApp ou o e-mail: você aperta enviar.</p>
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
const chave = t => norm(t.nome) + "|" + norm(t.cidade);

let status = ler("radar_status2", {});
let manual = ler("radar_manual", {});
$("msg").value = ler("radar_msg", MSG_PADRAO);
$("stF").innerHTML = '<option value="">Todos os status</option>' + STATUS.map(s => `<option value="${s[0]}">${s[1]}</option>`).join("");

const contagem = {};
DADOS.forEach(t => { if (t.cidade) contagem[t.cidade] = (contagem[t.cidade] || 0) + 1; });
$("cidades").innerHTML = Object.keys(contagem).sort().map(c => `<option value="${esc(c)}">`).join("");

function fonesDe(t) {
  const lista = (t.contatos || []).filter(c => ["whatsapp","celular","fixo"].includes(c.t)).map(c => ({n: c.v, t: c.t, o: c.o}));
  (manual[chave(t)] || []).forEach(n => lista.push({n: n, t: "whatsapp", o: "colado por você"}));
  return lista;
}
function fmt(n) {
  if (!/^55\d{10,11}$/.test(n)) return n.startsWith("http") ? "(link)" : n;
  const r = n.slice(4);
  return "(" + n.slice(2, 4) + ") " + r.slice(0, r.length - 4) + "-" + r.slice(-4);
}
const achar = (t, tipo) => (t.contatos || []).find(c => c.t === tipo);

function card(t) {
  const msg = $("msg").value.replace(/\{teatro\}/g, t.nome).replace(/\{cidade\}/g, t.cidade || "sua cidade");
  const k = chave(t), fones = fonesDe(t);
  const zaps = fones.filter(f => f.t !== "fixo").slice(0, 3);
  const fixos = fones.filter(f => f.t === "fixo").slice(0, 2);
  const email = achar(t, "email"), insta = achar(t, "instagram"), face = achar(t, "facebook");
  const hrefZap = f => f.n.startsWith("http") ? f.n : "https://wa.me/" + f.n + "?text=" + encodeURIComponent(msg);
  const site = t.site ? (/^https?:\/\//i.test(t.site) ? t.site : "https://" + t.site) : null;
  const mapa = "https://www.google.com/maps/search/?api=1&query=" +
    (t.lat != null ? t.lat + "," + t.lon : encodeURIComponent(t.nome + " " + (t.cidade || "")));
  const google = "https://www.google.com/search?q=" + encodeURIComponent(t.nome + " " + (t.cidade || "") + " contato whatsapp");
  const atual = status[k] || "novo";
  const opts = STATUS.map(s => `<option value="${s[0]}"${s[0] === atual ? " selected" : ""}>${s[1]}</option>`).join("");
  const capa = t.capacidade ? "Capacidade: " + t.capacidade + " (confiança " + esc(t.confianca) + ")" : "Capacidade: sem dado";
  const link = (url, texto) => '<a class="btn" target="_blank" rel="noopener" href="' + esc(url) + '">' + texto + "</a>";
  return `<div class="card">
    <h3>${esc(t.nome)}</h3>
    <div class="mut">${esc(t.cidade || "cidade não informada")}${t.uf ? " - " + esc(t.uf) : ""}${t.endereco ? " · " + esc(t.endereco) : ""}</div>
    <div class="tags"><span class="tag">${capa}</span><span class="tag">${fones.length ? fones.length + " número(s) achado(s)" : "Nenhum número achado"}</span></div>
    <div class="acoes">
      ${zaps.map(f => `<a class="btn zap${f.t === "celular" ? " prov" : ""}" target="_blank" rel="noopener" href="${esc(hrefZap(f))}" title="${esc(f.o)}">WhatsApp ${esc(fmt(f.n))}</a>`).join("")}
      ${fixos.map(f => `<a class="btn" href="tel:+${esc(f.n)}" title="${esc(f.o)}">Ligar ${esc(fmt(f.n))}</a>`).join("")}
      ${email ? link("mailto:" + email.v + "?subject=" + encodeURIComponent("Proposta de show - " + t.nome) + "&body=" + encodeURIComponent(msg), "E-mail") : ""}
      ${insta ? link(insta.v, "Instagram") : ""}
      ${face ? link(face.v, "Facebook") : ""}
      ${site ? link(site, "Site") : ""}
      ${link(mapa, "Mapa")}
      ${link(google, "Buscar contato")}
    </div>
    ${zaps.some(f => f.t === "celular") ? '<div class="mut">Botão mais claro = celular achado em texto (provável WhatsApp). Passe o mouse para ver de onde veio.</div>' : ""}
    <div class="acoes">
      <input class="man" data-k="${esc(k)}" placeholder="Colar WhatsApp (ex: 86 99999-1111)">
      <button class="btn" data-salvar="${esc(k)}">Salvar número</button>
      <select data-k="${esc(k)}">${opts}</select>
    </div>
  </div>`;
}

function desenhar() {
  const q = norm($("q").value), soNum = $("soNum").checked, st = $("stF").value;
  const semCidade = DADOS.filter(t => !t.cidade).length;
  const comNum = DADOS.filter(t => fonesDe(t).length).length;
  if (!q) {
    $("info").textContent = DADOS.length + " teatros na base, " + comNum + " com número achado. Digite uma cidade para começar." +
      (semCidade ? " (" + semCidade + " ainda sem cidade: rode o comando cidades.)" : "");
    $("lista").innerHTML = "";
    return;
  }
  const lista = DADOS.filter(t => {
    if (!(norm(t.cidade).includes(q) || norm(t.nome).includes(q) || norm(t.uf) === q)) return false;
    if (soNum && !fonesDe(t).length) return false;
    if (st && (status[chave(t)] || "novo") !== st) return false;
    return true;
  });
  const peso = t => fonesDe(t).some(f => f.t !== "fixo") ? 2 : (fonesDe(t).length ? 1 : 0);
  lista.sort((a, b) => (peso(b) - peso(a)) || ((b.capacidade || 0) - (a.capacidade || 0)) || a.nome.localeCompare(b.nome));
  $("info").textContent = lista.length + " teatros encontrados, " + lista.filter(t => fonesDe(t).length).length + " com número." +
    (lista.length > 100 ? " Mostrando os 100 primeiros." : "");
  $("lista").innerHTML = lista.slice(0, 100).map(card).join("") || "<p>Nenhum teatro encontrado.</p>";
}

$("q").addEventListener("input", desenhar);
$("soNum").addEventListener("change", desenhar);
$("stF").addEventListener("change", desenhar);
$("msg").addEventListener("input", () => { guardar("radar_msg", $("msg").value); desenhar(); });
$("lista").addEventListener("change", e => {
  const k = e.target.dataset.k;
  if (k && e.target.tagName === "SELECT") { status[k] = e.target.value; guardar("radar_status2", status); }
});
$("lista").addEventListener("click", e => {
  const k = e.target.dataset.salvar;
  if (!k) return;
  const campo = e.target.parentElement.querySelector("input.man");
  let d = campo.value.replace(/\D/g, "").replace(/^0+/, "");
  if (d.length === 10 || d.length === 11) d = "55" + d;
  if (d.length < 12) { campo.value = ""; campo.placeholder = "Número inválido. Use DDD + número"; return; }
  manual[k] = (manual[k] || []).concat(d);
  guardar("radar_manual", manual);
  desenhar();
});
desenhar();
</script>
</body>
</html>
'''


def gerar():
    con = conectar()
    criar_tabelas(con)
    teatros = [dict(r) for r in con.execute(
        "SELECT id, nome, cidade, uf, lat, lon, capacidade, confianca, site, endereco "
        "FROM teatros ORDER BY uf, cidade, nome")]
    membros = defaultdict(list)
    for r in con.execute(
        "SELECT v.teatro_id, r.fonte, r.id_fonte, r.site, r.telefone "
        "FROM vinculos v JOIN registros r ON r.id = v.registro_id"
    ):
        membros[r["teatro_id"]].append(dict(r))
    guardados = defaultdict(list)
    for r in con.execute("SELECT chave, tipo, valor, origem FROM contatos"):
        guardados[r["chave"]].append(dict(r))
    con.close()

    for t in teatros:
        achados = {}

        def juntar(tipo, valor, origem):
            k = valor if tipo in ORDEM else tipo + "|" + valor
            atual = achados.get(k)
            if atual is None or ORDEM.get(tipo, 9) < ORDEM.get(atual["t"], 9):
                achados[k] = {"t": tipo, "v": valor, "o": origem}

        for m in membros[t["id"]]:
            chaves = [f"{m['fonte']}:{m['id_fonte']}"]
            if m["site"]:
                chaves.append(f"site:{m['site']}")
            for ch in chaves:
                for c in guardados.get(ch, []):
                    juntar(c["tipo"], c["valor"], c["origem"])
            for texto in (m["telefone"] or "").split(";"):
                r = norm_fone(texto)
                if r:
                    juntar(r[1], r[0], "cadastro " + m["fonte"])
        t["contatos"] = sorted(achados.values(), key=lambda c: ORDEM.get(c["t"], 9))[:10]

    dados = json.dumps(teatros, ensure_ascii=False).replace("</", "<\\/")
    destino = WEB / "sistema.html"
    destino.write_text(TEMPLATE.replace("/*DADOS*/[]", dados), encoding="utf-8")
    com_zap = sum(1 for t in teatros if any(c["t"] in ("whatsapp", "celular") for c in t["contatos"]))
    com_fone = sum(1 for t in teatros if any(c["t"] in ORDEM for c in t["contatos"]))
    print(f"[painel] {len(teatros)} teatros | {com_zap} com WhatsApp/celular | "
          f"{com_fone} com algum telefone")
    print(f"[painel] painel gerado em {destino}")
""",
    # ------------------------------------------------------------------
    "radar/cli.py": r"""
import argparse
import sys

from . import (cidades, consolidate, contatos, export, manual, mapa_cultura, osm,
               painel, report, sites, wikidata)

COMANDOS = {
    "osm": osm.executar,
    "wikidata": wikidata.executar,
    "mapa": mapa_cultura.executar,
    "manual": manual.executar,
    "sites": sites.executar,
    "consolidar": consolidate.consolidar,
    "cidades": cidades.executar,
    "contatos": contatos.executar,
    "relatorio": report.gerar,
    "exportar": export.exportar,
    "painel": painel.gerar,
}
PIPELINE = ["osm", "wikidata", "mapa", "manual", "consolidar", "cidades", "contatos",
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


def rodar(py, comando):
    try:
        subprocess.run([str(py), "-m", "radar.cli", comando], cwd=RAIZ)
    except KeyboardInterrupt:
        print("\nParado. O progresso foi salvo.")


def main():
    win = sys.platform.startswith("win")
    py = RAIZ / ".venv" / ("Scripts/python.exe" if win else "bin/python")
    if not py.exists() or not (RAIZ / "radar" / "db.py").exists():
        sys.exit("Nao achei o projeto nesta pasta. Rode antes o radar_teatros_completo.py")
    if not (RAIZ / "radar" / "cidades.py").exists():
        sys.exit("Falta o painel base. Rode antes o radar_teatros_completo.py")

    print("=== Atualizando o Radar de Teatros: investigador de contatos ===")
    for caminho, conteudo in ARQUIVOS.items():
        (RAIZ / caminho).write_text(conteudo.lstrip("\n"), encoding="utf-8", newline="\n")
        print(f"  [ok] {caminho}")

    print("\nInvestigando contatos (OpenStreetMap + sites dos teatros)...")
    rodar(py, "contatos")
    rodar(py, "painel")

    sistema = RAIZ / "web" / "sistema.html"
    print(f"\nPronto! Abrindo {sistema}")
    webbrowser.open(sistema.as_uri())


if __name__ == "__main__":
    main()
