# Power BI: modelo e medidas

> Status: estas medidas e relacionamentos foram escritos mas **não foram validados no Power BI Desktop**
> (não havia como abri-lo no ambiente onde o repositório foi montado). Valide cada medida contra
> `mart_tempo_primeiro_julgamento` antes de publicar. O `.pbix` não está no repositório.

## Carga
Importe os CSV de `data/exports/` (gerados por `python -m src.pipeline.run`).

## Relacionamentos (1 → *)
| Dimensão | Fato | Coluna |
|---|---|---|
| `dim_tribunal[tribunal_alias]` | `fato_processo[tribunal]` | |
| `dim_classe[classe_codigo]` | `fato_processo[classe_codigo]` | |
| `dim_orgao_julgador[orgao_key]` | `fato_processo[orgao_key]` | |
| `dim_assunto[assunto_codigo]` | `fato_processo[assunto_principal_codigo]` | |
| `dim_calendario[data]` | `fato_processo[data_ajuizamento]` | ativo |
| `fato_processo[processo_key]` | `fato_movimentacao[processo_key]` | |
| `dim_categoria_movimento[categoria]` | `fato_movimentacao[categoria]` | |

Marque `dim_calendario` como tabela de datas. Deixe os `mart_*` como tabelas desconectadas (consumo direto) ou use-os só para conferir as medidas.

## Medidas
```dax
Processos = COUNTROWS ( fato_processo )

Processos Julgados =
CALCULATE ( [Processos], fato_processo[flag_sem_julgamento] = 0 )

% Julgados = DIVIDE ( [Processos Julgados], [Processos] )

Mediana Dias até Julgamento =
MEDIAN ( fato_processo[dias_ate_primeiro_julgamento] )

P90 Dias até Julgamento =
PERCENTILE.INC ( fato_processo[dias_ate_primeiro_julgamento], 0.9 )

Acervo Pendente =
CALCULATE ( [Processos], fato_processo[flag_sem_julgamento] = 1, fato_processo[flag_baixado] = 0 )

Pendentes Parados > 90d =
CALCULATE ( [Acervo Pendente], fato_processo[dias_sem_movimento] > 90 )

% Pendentes Parados = DIVIDE ( [Pendentes Parados > 90d], [Acervo Pendente] )

Novos = [Processos]

Novos MM3 =
DIVIDE (
    CALCULATE ( [Novos], DATESINPERIOD ( dim_calendario[data], MAX ( dim_calendario[data] ), -3, MONTH ) ),
    3
)

Mediana Ano Anterior =
CALCULATE ( [Mediana Dias até Julgamento], SAMEPERIODLASTYEAR ( dim_calendario[data] ) )

Var. Mediana YoY =
DIVIDE ( [Mediana Dias até Julgamento] - [Mediana Ano Anterior], [Mediana Ano Anterior] )
```

## Páginas
1. **Visão geral:** cartões (Processos, % Julgados, Mediana, P90), novos por mês com MM3, segmentadores de tribunal/classe. Sempre exiba **% Julgados** ao lado da mediana, para não esconder a censura.
2. **Gargalos:** barras de `mart_gargalo_fase` (mediana e P90 de dias parado após cada categoria).
3. **Acervo parado:** `mart_acervo_pendente` por faixa de idade, com % parado há mais de 90 dias.
