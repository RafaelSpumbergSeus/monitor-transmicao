-- Camada RAW: JSON exatamente como veio da fonte. Nunca é alterada.
-- A chave inclui o hash do payload: reprocessar o mesmo arquivo não duplica,
-- e uma versão nova do mesmo processo entra como linha nova (histórico).
CREATE TABLE IF NOT EXISTS raw_processo (
    tribunal_alias  TEXT NOT NULL,
    numero_processo TEXT NOT NULL,
    payload_hash    TEXT NOT NULL,
    payload         TEXT NOT NULL,
    batch_id        TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    PRIMARY KEY (tribunal_alias, numero_processo, payload_hash)
);

CREATE TABLE IF NOT EXISTS pipeline_meta (
    chave TEXT PRIMARY KEY,
    valor TEXT
);

CREATE TABLE IF NOT EXISTS ref_categoria_movimento (
    padrao      TEXT    NOT NULL,   -- padrão LIKE aplicado ao nome da movimentação
    categoria   TEXT    NOT NULL,
    prioridade  INTEGER NOT NULL,   -- menor vence quando mais de um padrão casa
    ordem_fase  INTEGER NOT NULL
);
