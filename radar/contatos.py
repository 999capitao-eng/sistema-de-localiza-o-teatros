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
