-- Camada STAGING: tipos corretos, datas normalizadas, 1 linha por processo
-- (versão mais recente). Nenhuma linha é descartada aqui por qualidade;
-- quem julga validade é a camada MARTS (quarentena), para que o descarte
-- seja visível e contável.

DROP TABLE IF EXISTS stg_processo;
CREATE TABLE stg_processo AS
WITH versoes AS (
    SELECT r.rowid AS raw_id, r.*,
           ROW_NUMBER() OVER (
               PARTITION BY r.tribunal_alias, r.numero_processo
               ORDER BY norm_ts(json_extract(r.payload, '$.dataHoraUltimaAtualizacao')) DESC,
                        r.ingested_at DESC, r.rowid DESC
           ) AS rn
    FROM raw_processo r
)
SELECT
    raw_id,
    tribunal_alias                                         AS tribunal,
    numero_processo,
    json_extract(payload, '$.classe.codigo')               AS classe_codigo,
    json_extract(payload, '$.classe.nome')                 AS classe_nome,
    json_extract(payload, '$.orgaoJulgador.codigo')        AS orgao_codigo,
    json_extract(payload, '$.orgaoJulgador.nome')          AS orgao_nome,
    json_extract(payload, '$.grau')                        AS grau,
    norm_ts(json_extract(payload, '$.dataAjuizamento'))    AS dt_ajuizamento,
    norm_ts(json_extract(payload, '$.dataHoraUltimaAtualizacao')) AS dt_ultima_atualizacao,
    json_extract(payload, '$.dataAjuizamento')             AS dt_ajuizamento_original,
    batch_id
FROM versoes
WHERE rn = 1;

DROP TABLE IF EXISTS stg_movimento;
CREATE TABLE stg_movimento AS
SELECT DISTINCT
    p.tribunal,
    p.numero_processo,
    json_extract(m.value, '$.codigo')                AS mov_codigo,
    json_extract(m.value, '$.nome')                  AS mov_nome,
    norm_ts(json_extract(m.value, '$.dataHora'))     AS dt_movimento
FROM stg_processo p
JOIN raw_processo r ON r.rowid = p.raw_id,
     json_each(r.payload, '$.movimentos') m;

DROP TABLE IF EXISTS stg_assunto;
CREATE TABLE stg_assunto AS
SELECT DISTINCT
    p.tribunal,
    p.numero_processo,
    CAST(a.key AS INTEGER)                      AS ordem,
    json_extract(a.value, '$.codigo')           AS assunto_codigo,
    json_extract(a.value, '$.nome')             AS assunto_nome
FROM stg_processo p
JOIN raw_processo r ON r.rowid = p.raw_id,
     json_each(r.payload, '$.assuntos') a;
