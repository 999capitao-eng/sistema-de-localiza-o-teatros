import csv

from .config import MANUAL
from .db import salvar_registros
from .models import Registro

ARQUIVO = MANUAL / "capacidades.csv"
COLUNAS = ["nome", "cidade", "uf", "capacidade", "tipo_capacidade", "site",
           "url_fonte", "observacao"]


def executar():
    if not ARQUIVO.exists():
        ARQUIVO.write_text(",".join(COLUNAS) + "\n", encoding="utf-8")
        print(f"[manual] arquivo criado: {ARQUIVO}")
    registros = []
    with ARQUIVO.open(encoding="utf-8-sig", newline="") as f:
        for i, linha in enumerate(csv.DictReader(f), start=2):
            nome = (linha.get("nome") or "").strip()
            if not nome:
                continue
            cap = (linha.get("capacidade") or "").strip()
            registros.append(Registro(
                fonte="manual",
                id_fonte=f"linha-{i}",
                nome=nome,
                cidade=(linha.get("cidade") or "").strip() or None,
                uf=(linha.get("uf") or "").strip() or None,
                capacidade=int(cap) if cap.isdigit() else None,
                tipo_capacidade=(linha.get("tipo_capacidade") or "").strip() or "desconhecido",
                site=(linha.get("site") or "").strip() or None,
                url_fonte=(linha.get("url_fonte") or "").strip() or None,
            ))
    salvar_registros(registros, "manual")
    return registros
