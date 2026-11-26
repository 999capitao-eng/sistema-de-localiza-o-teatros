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
