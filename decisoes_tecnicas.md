# Decisões técnicas

Formato: contexto, decisão, alternativa descartada, consequência.

## 1. Censura à direita nos tempos de tramitação
**Contexto:** processos recentes ainda não foram julgados. Calcular a mediana só dos julgados faz coortes recentes parecerem mais rápidas.
**Decisão:** indicadores por *coorte de ajuizamento*, sempre acompanhados de `pct_julgados`; processos sem julgamento ficam com `flag_sem_julgamento = 1` e nulo no tempo.
**Descartado:** preencher com `data_corte - ajuizamento` (subestima) ou ignorar os pendentes (viés).
**Consequência:** a leitura correta exige olhar mediana **e** % julgado. O dashboard mostra os dois lado a lado. Uma evolução natural é Kaplan-Meier.

## 2. Quarentena em vez de descarte silencioso
**Decisão:** registros inválidos (data impossível, classe ausente, ajuizamento no futuro) vão para `dq_quarentena` com o motivo, e a camada staging não os apaga.
**Consequência:** a conta fecha (`stg = fato + quarentena`, coberta por teste) e há um limite (10%) acima do qual o pipeline falha, porque uma explosão de inválidos indica que a fonte mudou.

## 3. Idempotência e versões
**Decisão:** `raw_processo` tem chave (tribunal, número, hash do payload) e `INSERT OR IGNORE`. Staging escolhe a versão com maior `dataHoraUltimaAtualizacao`, desempatando por ingestão.
**Consequência:** reprocessar um arquivo não duplica; uma versão antiga reingerida depois não sobrescreve a nova (coberto por teste).

## 4. "Primeiro julgamento" é uma aproximação
**Contexto:** a Tabela Processual Unificada tem centenas de tipos de movimentação; nomes variam entre tribunais.
**Decisão:** classificar por padrões de nome (`seeds/categoria_movimento.csv`), versionado e editável; "decisão" genérica **não** conta como julgamento (pode ser interlocutória).
**Risco assumido:** classificação por nome erra. O correto, com dados reais, é mapear por **código TPU** e validar uma amostra manualmente. Isso está listado em Limitações.

## 5. Fuso horário
O sufixo `Z` das datas ISO é descartado (tratado como horário civil). Para métricas em dias o erro é no máximo de 1 dia em parte dos registros; documentado, não corrigido.

## 6. SQLite no repositório, PostgreSQL no mundo real
**Decisão:** SQLite (biblioteca padrão) para o repositório rodar em qualquer máquina e no CI sem serviços. O SQL é padrão (CTEs, janelas); o README lista as trocas para PostgreSQL.
**Descartado:** exigir Docker/Postgres para quem só quer avaliar o projeto.

## 7. Chaves naturais
`tribunal`, `classe_codigo` e `orgao_key` são estáveis; *surrogate keys* gerados com `ROW_NUMBER()` mudariam a cada carga e quebrariam relatórios publicados. `processo_key` existe porque o Power BI exige coluna única nos relacionamentos.

## 8. Dados sintéticos com defeitos injetados
Permitem testar as regras de qualidade de forma determinística e rodar o projeto sem rede. A fonte (`sintetico`/`datajud`) fica em `pipeline_meta` e é impressa em figuras e relatórios para que dado sintético nunca passe por achado real.
