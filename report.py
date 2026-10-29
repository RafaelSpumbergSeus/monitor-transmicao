"""Relatório de qualidade (markdown) e figura-resumo.

A fonte dos dados (sintetico|datajud) é lida de pipeline_meta e aparece na
figura e no relatório: um gráfico de dados sintéticos nunca pode ser
confundido com um achado real.
"""
import sqlite3
from pathlib import Path


def _meta(conn, chave, padrao=""):
    r = conn.execute("SELECT valor FROM pipeline_meta WHERE chave = ?", (chave,)).fetchone()
    return r[0] if r else padrao


def escrever_relatorio_qualidade(conn: sqlite3.Connection, destino: Path) -> None:
    fonte, corte = _meta(conn, "fonte"), _meta(conn, "data_corte")
    ultimo = conn.execute("SELECT MAX(executado_em) FROM dq_resultado").fetchone()[0]
    linhas = conn.execute(
        "SELECT nome, severidade, falhas, total, pct, limite_pct, status, descricao "
        "FROM dq_resultado WHERE executado_em = ? ORDER BY rowid", (ultimo,)).fetchall()
    q = conn.execute("SELECT motivo_quarentena, COUNT(*) FROM dq_quarentena GROUP BY 1 ORDER BY 2 DESC").fetchall()
    md = [f"# Relatório de qualidade de dados", "",
          f"- Fonte: **{fonte}**" + ("  (DADOS SINTÉTICOS com defeitos injetados de propósito)" if fonte == "sintetico" else ""),
          f"- Data de corte: {corte}", f"- Execução: {ultimo}", "",
          "| Regra | Severidade | Falhas | Total | % | Limite | Status |", "|---|---|---:|---:|---:|---:|---|"]
    for nome, sev, f, t, pct, lim, st, _ in linhas:
        md.append(f"| `{nome}` | {sev} | {f} | {t} | {pct:.2%} | {lim:.2%} | {st} |")
    md += ["", "## Quarentena (excluídos dos indicadores)", ""]
    md += [f"- `{m}`: {n}" for m, n in q] or ["- nenhum"]
    md += ["", "## Descrição das regras", ""]
    md += [f"- `{r[0]}` — {r[7]}" for r in linhas]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(md) + "\n", encoding="utf-8")


def gerar_figura(conn: sqlite3.Connection, destino: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fonte = _meta(conn, "fonte")
    nomes = dict(conn.execute("SELECT classe_codigo, classe_nome FROM dim_classe").fetchall())
    dados = conn.execute(
        "SELECT tribunal, classe_codigo, ano_ajuizamento, n_processos, pct_julgados, mediana_dias, p90_dias "
        "FROM mart_tempo_primeiro_julgamento ORDER BY tribunal, classe_codigo, ano_ajuizamento").fetchall()
    series = {}
    for t, c, ano, n, pct, med, p90 in dados:
        series.setdefault((t, c), []).append((ano, pct, med, p90))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.8))
    for (t, c), pts in series.items():
        rot = f"{t.upper()} · {nomes.get(c, c)}"
        ax1.plot([p[0] for p in pts], [p[1] * 100 for p in pts], marker="o", label=rot)
        validos = [p for p in pts if p[2] is not None]
        ax2.plot([p[0] for p in validos], [p[2] for p in validos], marker="o", label=rot)
    ax1.set_title("% da coorte já julgada (censura à direita)")
    ax1.set_xlabel("Ano de ajuizamento"); ax1.set_ylabel("%"); ax1.set_xticks(sorted({p[0] for s in series.values() for p in s}))
    ax2.set_title("Mediana de dias até o 1º julgamento (só julgados)")
    ax2.set_xlabel("Ano de ajuizamento"); ax2.set_ylabel("dias"); ax2.set_xticks(ax1.get_xticks())
    ax2.legend(fontsize=7, loc="best")
    sufixo = "  —  DADOS SINTÉTICOS, NÃO REPRESENTAM A JUSTIÇA REAL" if fonte == "sintetico" else ""
    fig.suptitle(f"Tempo de tramitação por coorte{sufixo}", fontsize=11, color="#b00020" if sufixo else "black")
    fig.tight_layout()
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, dpi=130)
    plt.close(fig)
