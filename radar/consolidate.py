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
