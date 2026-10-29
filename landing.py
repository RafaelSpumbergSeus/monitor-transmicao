"""Zona de pouso: JSONL por tribunal em data/raw/ (um documento por linha)."""
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Iterator


def escrever_jsonl(docs: Iterable[tuple[str, dict]], pasta: Path) -> dict[str, int]:
    pasta.mkdir(parents=True, exist_ok=True)
    for antigo in pasta.glob("*.jsonl"):
        antigo.unlink()
    contagem = defaultdict(int)
    abertos = {}
    try:
        for alias, doc in docs:
            if alias not in abertos:
                abertos[alias] = (pasta / f"{alias}.jsonl").open("w", encoding="utf-8")
            abertos[alias].write(json.dumps(doc, ensure_ascii=False) + "\n")
            contagem[alias] += 1
    finally:
        for f in abertos.values():
            f.close()
    return dict(contagem)


def ler_jsonl(pasta: Path) -> Iterator[tuple[str, dict]]:
    for arq in sorted(pasta.glob("*.jsonl")):
        alias = arq.stem
        with arq.open(encoding="utf-8") as f:
            for linha in f:
                if linha.strip():
                    yield alias, json.loads(linha)
