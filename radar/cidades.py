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
