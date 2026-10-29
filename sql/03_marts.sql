-- Camada MARTS: modelo dimensional + tabelas prontas para o Power BI.
-- Snapshot consistente: tudo é calculado "como em" pipeline_meta.data_corte.

-- ---------- Validade e quarentena ----------
DROP TABLE IF EXISTS proc_valido;
CREATE TABLE proc_valido AS
SELECT p.*,
       CASE
         WHEN p.dt_ajuizamento IS NULL THEN 'dt_ajuizamento_invalida'
         WHEN p.classe_codigo  IS NULL THEN 'classe_nula'
         WHEN date(p.dt_ajuizamento) > (SELECT valor FROM pipeline_meta WHERE chave = 'data_corte')
              THEN 'ajuizamento_futuro'
       END AS motivo_quarentena
FROM stg_processo p;

DROP TABLE IF EXISTS dq_quarentena;
CREATE TABLE dq_quarentena AS
SELECT tribunal, numero_processo, motivo_quarentena, dt_ajuizamento_original
FROM proc_valido WHERE motivo_quarentena IS NOT NULL;

DROP TABLE IF EXISTS proc_ok;
CREATE TABLE proc_ok AS
SELECT * FROM proc_valido WHERE motivo_quarentena IS NULL;

-- ---------- Dimensões (chaves naturais: estáveis entre execuções) ----------
DROP TABLE IF EXISTS dim_tribunal;
CREATE TABLE dim_tribunal AS
SELECT DISTINCT tribunal AS tribunal_alias, UPPER(tribunal) AS tribunal_nome FROM proc_ok;

DROP TABLE IF EXISTS dim_classe;
CREATE TABLE dim_classe AS
SELECT classe_codigo, MAX(classe_nome) AS classe_nome FROM proc_ok GROUP BY classe_codigo;

DROP TABLE IF EXISTS dim_orgao_julgador;
CREATE TABLE dim_orgao_julgador AS
SELECT tribunal || '-' || orgao_codigo AS orgao_key, tribunal AS tribunal_alias,
       orgao_codigo, MAX(orgao_nome) AS orgao_nome
FROM proc_ok WHERE orgao_codigo IS NOT NULL
GROUP BY tribunal, orgao_codigo;

DROP TABLE IF EXISTS dim_assunto;
CREATE TABLE dim_assunto AS
SELECT assunto_codigo, MAX(assunto_nome) AS assunto_nome
FROM stg_assunto WHERE assunto_codigo IS NOT NULL GROUP BY assunto_codigo;

DROP TABLE IF EXISTS dim_categoria_movimento;
CREATE TABLE dim_categoria_movimento AS
SELECT categoria, MIN(ordem_fase) AS ordem_fase FROM ref_categoria_movimento GROUP BY categoria
UNION ALL SELECT 'outros', 0;

DROP TABLE IF EXISTS dim_calendario;
CREATE TABLE dim_calendario AS
WITH RECURSIVE d(data) AS (
    SELECT (SELECT MIN(date(dt_ajuizamento)) FROM proc_ok)
    UNION ALL
    SELECT date(data, '+1 day') FROM d
    WHERE data < (SELECT valor FROM pipeline_meta WHERE chave = 'data_corte')
)
SELECT data,
       CAST(strftime('%Y', data) AS INTEGER) AS ano,
       CAST(strftime('%m', data) AS INTEGER) AS mes,
       strftime('%Y-%m', data)               AS ano_mes,
       ((CAST(strftime('%m', data) AS INTEGER) - 1) / 3) + 1 AS trimestre
FROM d;

-- ---------- Fato de movimentações ----------
DROP TABLE IF EXISTS tmp_mov;
CREATE TABLE tmp_mov AS
SELECT m.tribunal, m.numero_processo,
       m.tribunal || '|' || m.numero_processo AS processo_key,
       m.mov_codigo, m.mov_nome, m.dt_movimento,
       date(m.dt_movimento) AS data_movimento,
       COALESCE((SELECT r.categoria FROM ref_categoria_movimento r
                 WHERE m.mov_nome LIKE r.padrao
                 ORDER BY r.prioridade, r.padrao LIMIT 1), 'outros') AS categoria,
       CASE WHEN date(m.dt_movimento) < date(p.dt_ajuizamento) THEN 1 ELSE 0 END
           AS anterior_ao_ajuizamento
FROM stg_movimento m
JOIN proc_ok p ON p.tribunal = m.tribunal AND p.numero_processo = m.numero_processo
WHERE m.dt_movimento IS NOT NULL
  AND date(m.dt_movimento) <= (SELECT valor FROM pipeline_meta WHERE chave = 'data_corte');

DROP TABLE IF EXISTS fato_movimentacao;
CREATE TABLE fato_movimentacao AS
SELECT t.*,
       ROW_NUMBER() OVER w AS seq,
       LAG(categoria) OVER w AS categoria_anterior,
       CAST(julianday(data_movimento) - julianday(LAG(data_movimento) OVER w) AS INTEGER)
           AS dias_desde_anterior
FROM tmp_mov t
WINDOW w AS (PARTITION BY tribunal, numero_processo, anterior_ao_ajuizamento
             ORDER BY dt_movimento, mov_codigo, mov_nome);
DROP TABLE tmp_mov;

-- ---------- Fato de processos ----------
DROP TABLE IF EXISTS fato_processo;
CREATE TABLE fato_processo AS
WITH marcos AS (
    SELECT tribunal, numero_processo,
           MIN(CASE WHEN categoria = 'julgamento' THEN data_movimento END) AS data_primeiro_julgamento,
           MAX(data_movimento)                                              AS data_ultimo_movimento,
           COUNT(*)                                                         AS qtd_movimentacoes,
           MAX(CASE WHEN categoria = 'baixa' THEN 1 ELSE 0 END)             AS flag_baixado
    FROM fato_movimentacao
    WHERE anterior_ao_ajuizamento = 0
    GROUP BY tribunal, numero_processo
)
SELECT
    p.tribunal || '|' || p.numero_processo AS processo_key,
    p.tribunal, p.numero_processo, p.classe_codigo,
    a.assunto_codigo AS assunto_principal_codigo,
    CASE WHEN p.orgao_codigo IS NULL THEN NULL ELSE p.tribunal || '-' || p.orgao_codigo END AS orgao_key,
    date(p.dt_ajuizamento)                    AS data_ajuizamento,
    m.data_primeiro_julgamento,
    CASE WHEN m.data_primeiro_julgamento IS NOT NULL THEN
        CAST(julianday(m.data_primeiro_julgamento) - julianday(date(p.dt_ajuizamento)) AS INTEGER)
    END                                       AS dias_ate_primeiro_julgamento,
    COALESCE(m.data_ultimo_movimento, date(p.dt_ajuizamento)) AS data_ultimo_movimento,
    COALESCE(m.qtd_movimentacoes, 0)          AS qtd_movimentacoes,
    COALESCE(m.flag_baixado, 0)               AS flag_baixado,
    -- censura à direita: sem julgamento NÃO significa "demorou 0 dias"; significa "ainda não aconteceu"
    CASE WHEN m.data_primeiro_julgamento IS NULL THEN 1 ELSE 0 END AS flag_sem_julgamento,
    CAST(julianday((SELECT valor FROM pipeline_meta WHERE chave = 'data_corte'))
         - julianday(date(p.dt_ajuizamento)) AS INTEGER)            AS idade_dias,
    CAST(julianday((SELECT valor FROM pipeline_meta WHERE chave = 'data_corte'))
         - julianday(COALESCE(m.data_ultimo_movimento, date(p.dt_ajuizamento))) AS INTEGER)
                                                                     AS dias_sem_movimento
FROM proc_ok p
LEFT JOIN marcos m ON m.tribunal = p.tribunal AND m.numero_processo = p.numero_processo
LEFT JOIN stg_assunto a ON a.tribunal = p.tribunal AND a.numero_processo = p.numero_processo AND a.ordem = 0;

-- ---------- Marts de consumo ----------
-- Tempo até o primeiro julgamento por COORTE de ajuizamento.
-- Mediana e P90 só entre os já julgados; pct_julgados mostra o quanto da coorte
-- ainda está "no escuro" (coortes recentes têm mediana artificialmente baixa).
DROP TABLE IF EXISTS mart_tempo_primeiro_julgamento;
CREATE TABLE mart_tempo_primeiro_julgamento AS
WITH base AS (
    SELECT tribunal, classe_codigo,
           CAST(strftime('%Y', data_ajuizamento) AS INTEGER) AS ano_ajuizamento,
           dias_ate_primeiro_julgamento AS dias
    FROM fato_processo
    WHERE dias_ate_primeiro_julgamento IS NOT NULL AND dias_ate_primeiro_julgamento >= 0
), rk AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY tribunal, classe_codigo, ano_ajuizamento ORDER BY dias) AS rn,
           COUNT(*)     OVER (PARTITION BY tribunal, classe_codigo, ano_ajuizamento)               AS n
    FROM base
), agg AS (
    SELECT tribunal, classe_codigo, ano_ajuizamento, MAX(n) AS n_julgados,
           AVG(CASE WHEN rn IN ((n + 1) / 2, (n + 2) / 2) THEN dias END) AS mediana_dias,
           MAX(CASE WHEN rn = (9 * n + 9) / 10 THEN dias END)            AS p90_dias
    FROM rk GROUP BY tribunal, classe_codigo, ano_ajuizamento
), tot AS (
    SELECT tribunal, classe_codigo,
           CAST(strftime('%Y', data_ajuizamento) AS INTEGER) AS ano_ajuizamento,
           COUNT(*) AS n_processos
    FROM fato_processo GROUP BY tribunal, classe_codigo, ano_ajuizamento
)
SELECT t.tribunal, t.classe_codigo, t.ano_ajuizamento, t.n_processos,
       COALESCE(a.n_julgados, 0) AS n_julgados,
       ROUND(1.0 * COALESCE(a.n_julgados, 0) / t.n_processos, 4) AS pct_julgados,
       a.mediana_dias, a.p90_dias
FROM tot t
LEFT JOIN agg a ON a.tribunal = t.tribunal AND a.classe_codigo = t.classe_codigo
               AND a.ano_ajuizamento = t.ano_ajuizamento;

-- Gargalos: quanto tempo o processo fica parado DEPOIS de cada tipo de movimentação.
DROP TABLE IF EXISTS mart_gargalo_fase;
CREATE TABLE mart_gargalo_fase AS
WITH base AS (
    SELECT p.tribunal, p.classe_codigo, m.categoria_anterior AS categoria_origem,
           m.dias_desde_anterior AS dias
    FROM fato_movimentacao m
    JOIN fato_processo p ON p.processo_key = m.processo_key
    WHERE m.anterior_ao_ajuizamento = 0
      AND m.categoria_anterior IS NOT NULL AND m.dias_desde_anterior IS NOT NULL
), rk AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY tribunal, classe_codigo, categoria_origem ORDER BY dias) AS rn,
           COUNT(*)     OVER (PARTITION BY tribunal, classe_codigo, categoria_origem)               AS n
    FROM base
)
SELECT tribunal, classe_codigo, categoria_origem, MAX(n) AS n_transicoes,
       ROUND(AVG(dias), 1) AS media_dias_ate_proximo,
       AVG(CASE WHEN rn IN ((n + 1) / 2, (n + 2) / 2) THEN dias END) AS mediana_dias_ate_proximo,
       MAX(CASE WHEN rn = (9 * n + 9) / 10 THEN dias END)            AS p90_dias_ate_proximo
FROM rk GROUP BY tribunal, classe_codigo, categoria_origem;

DROP TABLE IF EXISTS mart_carga_mensal;
CREATE TABLE mart_carga_mensal AS
WITH novos AS (
    SELECT tribunal, classe_codigo, strftime('%Y-%m', data_ajuizamento) AS ano_mes, COUNT(*) AS novos
    FROM fato_processo GROUP BY 1, 2, 3
), jul AS (
    SELECT tribunal, classe_codigo, strftime('%Y-%m', data_primeiro_julgamento) AS ano_mes, COUNT(*) AS julgados
    FROM fato_processo WHERE data_primeiro_julgamento IS NOT NULL GROUP BY 1, 2, 3
), chaves AS (
    SELECT tribunal, classe_codigo, ano_mes FROM novos
    UNION SELECT tribunal, classe_codigo, ano_mes FROM jul
)
SELECT k.tribunal, k.classe_codigo, k.ano_mes,
       COALESCE(n.novos, 0) AS novos, COALESCE(j.julgados, 0) AS julgados
FROM chaves k
LEFT JOIN novos n ON n.tribunal = k.tribunal AND n.classe_codigo = k.classe_codigo AND n.ano_mes = k.ano_mes
LEFT JOIN jul   j ON j.tribunal = k.tribunal AND j.classe_codigo = k.classe_codigo AND j.ano_mes = k.ano_mes;

-- Acervo pendente (sem julgamento e sem baixa), por faixa de idade.
DROP TABLE IF EXISTS mart_acervo_pendente;
CREATE TABLE mart_acervo_pendente AS
SELECT tribunal, classe_codigo,
       CASE WHEN idade_dias <= 90  THEN '1. 0-90'
            WHEN idade_dias <= 180 THEN '2. 91-180'
            WHEN idade_dias <= 365 THEN '3. 181-365'
            ELSE '4. >365' END AS faixa_idade_dias,
       COUNT(*) AS pendentes,
       SUM(CASE WHEN dias_sem_movimento > 90 THEN 1 ELSE 0 END) AS parados_mais_90d
FROM fato_processo
WHERE flag_sem_julgamento = 1 AND flag_baixado = 0
GROUP BY tribunal, classe_codigo, faixa_idade_dias;
