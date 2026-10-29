# Relatório de qualidade de dados

- Fonte: **sintetico**  (DADOS SINTÉTICOS com defeitos injetados de propósito)
- Data de corte: 2025-12-31
- Execução: 2026-10-29T01:30:22+00:00

| Regra | Severidade | Falhas | Total | % | Limite | Status |
|---|---|---:|---:|---:|---:|---|
| `chave_duplicada_staging` | error | 0 | 3000 | 0.00% | 0.00% | ok |
| `data_ajuizamento_invalida` | error | 17 | 3000 | 0.57% | 2.00% | ok |
| `classe_ausente` | error | 29 | 3000 | 0.97% | 5.00% | ok |
| `ajuizamento_no_futuro` | error | 0 | 3000 | 0.00% | 0.00% | ok |
| `quarentena_excessiva` | error | 46 | 3000 | 1.53% | 10.00% | ok |
| `integridade_referencial_movimentacao` | error | 0 | 22425 | 0.00% | 0.00% | ok |
| `movimentacao_antes_do_ajuizamento` | warn | 29 | 2954 | 0.98% | 0.50% | alerta |
| `processo_sem_movimentacao` | warn | 9 | 2954 | 0.30% | 1.00% | ok |
| `movimentacao_com_data_invalida` | warn | 0 | 22773 | 0.00% | 1.00% | ok |

## Quarentena (excluídos dos indicadores)

- `classe_nula`: 29
- `dt_ajuizamento_invalida`: 17

## Descrição das regras

- `chave_duplicada_staging` — Mais de uma linha por (tribunal, numero_processo) em stg_processo.
- `data_ajuizamento_invalida` — dataAjuizamento ausente ou em formato/valor inválido (vai para quarentena).
- `classe_ausente` — Processo sem classe processual (vai para quarentena).
- `ajuizamento_no_futuro` — Data de ajuizamento posterior à data de corte.
- `quarentena_excessiva` — Proporção de processos em quarentena acima do tolerável: a fonte provavelmente mudou.
- `integridade_referencial_movimentacao` — Movimentação sem processo correspondente em fato_processo.
- `movimentacao_antes_do_ajuizamento` — Processos com movimentação datada antes do ajuizamento (mantidas, mas excluídas dos tempos).
- `processo_sem_movimentacao` — Processos sem nenhuma movimentação válida.
- `movimentacao_com_data_invalida` — Movimentações cuja data não pôde ser interpretada.
