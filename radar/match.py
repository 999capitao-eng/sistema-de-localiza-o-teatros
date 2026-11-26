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
