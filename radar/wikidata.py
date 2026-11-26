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
