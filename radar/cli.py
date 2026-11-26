import argparse
import sys

from . import (cidades, consolidate, contatos, export, manual, mapa_cultura, osm,
               painel, report, sites, wikidata)

COMANDOS = {
    "osm": osm.executar,
    "wikidata": wikidata.executar,
    "mapa": mapa_cultura.executar,
    "manual": manual.executar,
    "sites": sites.executar,
    "consolidar": consolidate.consolidar,
    "cidades": cidades.executar,
    "contatos": contatos.executar,
    "relatorio": report.gerar,
    "exportar": export.exportar,
    "painel": painel.gerar,
}
PIPELINE = ["osm", "wikidata", "mapa", "manual", "consolidar", "cidades", "contatos",
            "relatorio", "exportar", "painel"]


def main():
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8")
        except Exception:
            pass
    parser = argparse.ArgumentParser(prog="radar", description="Radar de Teatros")
    parser.add_argument("comando", choices=[*COMANDOS, "tudo"])
    args = parser.parse_args()
    if args.comando != "tudo":
        COMANDOS[args.comando]()
        return
    for nome in PIPELINE:
        print(f"\n=== {nome} ===")
        try:
            COMANDOS[nome]()
        except Exception as erro:
            print(f"[erro] etapa '{nome}' falhou: {erro}")


if __name__ == "__main__":
    main()
