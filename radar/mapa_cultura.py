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
