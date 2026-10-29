"""Cliente da API Pública do DataJud (CNJ).

ATENÇÃO: este módulo foi escrito a partir da documentação pública da API
(Elasticsearch com paginação `search_after`), mas NÃO foi executado contra a
API real no ambiente em que o repositório foi montado (sem acesso à rede).
Antes de confiar nos dados: rode com `--max-docs 200`, inspecione os JSONL em
data/raw/ e confira nomes de campos, limites e termos de uso na documentação
oficial do CNJ.

A chave pública é divulgada pelo CNJ; configure em DATAJUD_API_KEY (nunca
versione a chave).
"""
import logging
import os
import time
from typing import Iterator

import requests

log = logging.getLogger(__name__)
URL = "https://api-publica.datajud.cnj.jus.br/api_publica_{alias}/_search"


class DataJudErro(RuntimeError):
    pass


def _post_com_retry(url, headers, body, tentativas=5, timeout=60):
    espera = 2.0
    for i in range(1, tentativas + 1):
        try:
            r = requests.post(url, headers=headers, json=body, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                log.warning("HTTP %s (tentativa %s/%s); aguardando %.0fs", r.status_code, i, tentativas, espera)
            else:
                raise DataJudErro(f"HTTP {r.status_code}: {r.text[:300]}")
        except requests.RequestException as e:
            log.warning("Erro de rede (%s); tentativa %s/%s", e, i, tentativas)
        time.sleep(espera)
        espera *= 2
    raise DataJudErro("Falha após várias tentativas")


def buscar(alias: str, classes: list[int], ajuizamento_de: str, ajuizamento_ate: str,
           api_key: str | None = None, page_size: int = 1000,
           max_docs: int | None = None, pausa: float = 0.3) -> Iterator[dict]:
    """Gera os `_source` dos processos do tribunal `alias` (ex.: 'tjrs')."""
    api_key = api_key or os.environ.get("DATAJUD_API_KEY")
    if not api_key:
        raise DataJudErro("Defina DATAJUD_API_KEY (chave pública do DataJud).")
    headers = {"Authorization": f"APIKey {api_key}", "Content-Type": "application/json"}
    body = {
        "size": page_size,
        "query": {"bool": {"must": [
            {"terms": {"classe.codigo": classes}},
            {"range": {"dataAjuizamento": {"gte": ajuizamento_de, "lte": ajuizamento_ate}}},
        ]}},
        "sort": [{"@timestamp": {"order": "asc"}}],
    }
    total = 0
    while True:
        resp = _post_com_retry(URL.format(alias=alias), headers, body)
        hits = resp.get("hits", {}).get("hits", [])
        if not hits:
            return
        for h in hits:
            yield h["_source"]
            total += 1
            if max_docs and total >= max_docs:
                return
        body["search_after"] = hits[-1]["sort"]
        log.info("%s: %s documentos", alias, total)
        time.sleep(pausa)
