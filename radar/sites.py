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
