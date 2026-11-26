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
