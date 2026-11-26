from .config import PROCESSED
from .db import conectar


def pct(parte, total):
    return 100 * (parte or 0) / total if total else 0


def gerar():
    con = conectar()
    linhas = ["# Relatorio do Radar de Teatros", "", "## Registros por fonte", ""]
    for r in con.execute(
        "SELECT fonte, COUNT(*) total, SUM(capacidade IS NOT NULL) com_cap "
        "FROM registros GROUP BY fonte ORDER BY total DESC"
    ):
        linhas.append(f"- {r['fonte']}: {r['total']} registros, "
                      f"{r['com_cap'] or 0} com capacidade "
                      f"({pct(r['com_cap'], r['total']):.1f}%)")
    t = con.execute(
        "SELECT COUNT(*) total, SUM(capacidade IS NOT NULL) com_cap, "
        "SUM(conflito) conflitos FROM teatros"
    ).fetchone()
    linhas += ["", "## Teatros consolidados", "",
               f"- Total: {t['total']}",
               f"- Com capacidade: {t['com_cap'] or 0} ({pct(t['com_cap'], t['total']):.1f}%)",
               f"- Com conflito entre fontes: {t['conflitos'] or 0}"]
    linhas += ["", "## Confianca da capacidade", ""]
    for r in con.execute("SELECT confianca, COUNT(*) n FROM teatros "
                         "GROUP BY confianca ORDER BY n DESC"):
        linhas.append(f"- {r['confianca']}: {r['n']}")
    linhas += ["", "## Teatros por quantidade de fontes", ""]
    for r in con.execute("SELECT qtd_fontes, COUNT(*) n FROM teatros "
                         "GROUP BY qtd_fontes ORDER BY qtd_fontes"):
        linhas.append(f"- {r['qtd_fontes']} fonte(s): {r['n']}")
    fora = con.execute(
        "SELECT COUNT(*) FROM registros WHERE lat IS NOT NULL AND "
        "(lat NOT BETWEEN -34 AND 6 OR lon NOT BETWEEN -74 AND -34)"
    ).fetchone()[0]
    linhas += ["", "## Checagens de sanidade", "",
               f"- Registros com coordenadas fora do Brasil: {fora}"]
    con.close()
    texto = "\n".join(linhas)
    (PROCESSED / "relatorio.md").write_text(texto, encoding="utf-8")
    print(texto)
