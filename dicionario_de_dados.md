# Dicionário de dados

Chaves naturais em todo o modelo (estáveis entre execuções, sem *surrogate keys* que mudam a cada carga).

## Camadas
| Camada | Tabelas | Regra |
|---|---|---|
| raw | `raw_processo` | JSON original, imutável. Chave: (tribunal, número, hash do payload). |
| staging | `stg_processo`, `stg_movimento`, `stg_assunto` | Tipos corretos, datas normalizadas, 1 linha por processo (versão mais recente). |
| marts | `dim_*`, `fato_*`, `mart_*` | Modelo dimensional e tabelas de consumo. Só processos válidos. |
| qualidade | `dq_quarentena`, `dq_resultado` | O que foi excluído e por quê; resultado de cada regra por execução. |

## `fato_processo` (grão: 1 linha por processo válido)
| Coluna | Descrição |
|---|---|
| `processo_key` | `tribunal\|numero_processo`. Chave de relacionamento única para o Power BI. |
| `tribunal`, `classe_codigo`, `orgao_key`, `assunto_principal_codigo` | Chaves das dimensões. |
| `data_ajuizamento` | Data de ajuizamento normalizada. |
| `data_primeiro_julgamento` | Primeira movimentação da categoria `julgamento` (proxy; ver decisões técnicas). |
| `dias_ate_primeiro_julgamento` | Nulo se ainda não houve julgamento (censura). |
| `flag_sem_julgamento` | 1 = ainda sem julgamento na data de corte. **Não** é "0 dias". |
| `flag_baixado` | 1 = houve movimentação de baixa/arquivamento. |
| `idade_dias` | Dias entre ajuizamento e data de corte. |
| `dias_sem_movimento` | Dias entre a última movimentação e a data de corte. |
| `qtd_movimentacoes` | Movimentações válidas (exclui as anteriores ao ajuizamento). |

## `fato_movimentacao` (grão: 1 linha por movimentação de processo válido)
| Coluna | Descrição |
|---|---|
| `processo_key`, `seq` | Processo e ordem da movimentação. |
| `categoria` | Classificação por padrões em `seeds/categoria_movimento.csv`; `outros` se nada casa. |
| `categoria_anterior`, `dias_desde_anterior` | Base do mart de gargalos. |
| `anterior_ao_ajuizamento` | 1 = data anterior ao ajuizamento (mantida, mas fora dos tempos). |

## Marts de consumo
| Tabela | Grão | Pergunta que responde |
|---|---|---|
| `mart_tempo_primeiro_julgamento` | tribunal × classe × ano de ajuizamento | Quanto tempo até o 1º julgamento? Quanto da coorte já foi julgada? |
| `mart_gargalo_fase` | tribunal × classe × categoria de origem | Onde o processo fica parado? |
| `mart_carga_mensal` | tribunal × classe × mês | Entrada de novos processos vs. julgamentos. |
| `mart_acervo_pendente` | tribunal × classe × faixa de idade | Quanto do acervo está sem julgamento e parado há mais de 90 dias? |
