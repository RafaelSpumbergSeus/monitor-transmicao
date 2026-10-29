"""Gerador de dados SINTÉTICOS no formato do DataJud.

Serve para: (1) rodar o pipeline de ponta a ponta sem rede, (2) testes
determinísticos, (3) exercitar as regras de qualidade com defeitos
INJETADOS de propósito. Nenhum número produzido a partir daqui descreve a
Justiça real. Números de processo, órgãos e códigos de classe são fictícios/
ilustrativos.
"""
import math
import random
from datetime import date, datetime, timedelta

CORTE_PADRAO = date(2025, 12, 31)

# classe: (codigo, nome, mediana_dias_ate_julgamento, sigma, prob_audiencia)
TRIBUNAIS = {
    "tjrs": {
        "peso": 0.7, "j": "8", "tr": "21",
        "classes": [
            (7, "Procedimento Comum Cível", 220, 0.6, 0.5),
            (1116, "Execução Fiscal", 420, 0.9, 0.1),
            (436, "Procedimento do Juizado Especial Cível", 110, 0.5, 0.4),
        ],
        "orgaos": [(1001, "1ª Vara Cível (fictícia)"), (1002, "2ª Vara Cível (fictícia)"),
                   (2001, "Vara de Execuções Fiscais (fictícia)"), (3001, "Juizado Especial Cível (fictício)")],
        "assuntos": [(7771, "Indenização por Dano Moral"), (7772, "Contratos Bancários"),
                     (7773, "Direito do Consumidor"), (7774, "Dívida Ativa")],
    },
    "trt4": {
        "peso": 0.3, "j": "5", "tr": "04",
        "classes": [
            (985, "Ação Trabalhista - Rito Ordinário", 260, 0.55, 0.9),
            (1125, "Ação Trabalhista - Rito Sumaríssimo", 120, 0.5, 0.9),
        ],
        "orgaos": [(4001, "1ª Vara do Trabalho (fictícia)"), (4002, "2ª Vara do Trabalho (fictícia)")],
        "assuntos": [(8881, "Verbas Rescisórias"), (8882, "Horas Extras"), (8883, "Vínculo Empregatício")],
    },
}
INTERMEDIARIAS = [("Juntada", 581), ("Expedição de documento", 60), ("Publicação", 92),
                  ("Petição", 85), ("Mero expediente", 11010)]
JULGAMENTOS = [("Julgamento", 193), ("Procedência", 219), ("Improcedência", 220)]


def _fmt(dt: datetime, rnd: random.Random) -> str:
    """Mistura os dois formatos reais: ISO com 'Z' e 14 dígitos."""
    if rnd.random() < 0.3:
        return dt.strftime("%Y%m%d%H%M%S")
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def gerar(n: int = 2000, seed: int = 42, corte: date = CORTE_PADRAO, defeitos: bool = True):
    """Devolve lista de (alias_tribunal, documento). Determinístico para um dado seed."""
    rnd = random.Random(seed)
    corte_dt = datetime.combine(corte, datetime.max.time()).replace(microsecond=0)
    inicio, fim = datetime(2023, 1, 1), datetime(2025, 9, 30)
    aliases = list(TRIBUNAIS)
    pesos = [TRIBUNAIS[a]["peso"] for a in aliases]
    saida = []
    for i in range(1, n + 1):
        alias = rnd.choices(aliases, weights=pesos)[0]
        cfg = TRIBUNAIS[alias]
        cod, nome, med, sig, p_aud = rnd.choice(cfg["classes"])
        aj = inicio + timedelta(seconds=rnd.randint(0, int((fim - inicio).total_seconds())))
        alvo = aj + timedelta(days=rnd.lognormvariate(math.log(med), sig))
        tem_julg = alvo <= corte_dt
        limite = min(alvo, corte_dt)
        span = max((limite - aj).total_seconds(), 1.0)

        movs = [("Distribuição", 26, aj),
                ("Conclusão", 51, aj + timedelta(days=rnd.randint(0, 4), hours=rnd.randint(1, 8)))]
        for _ in range(rnd.randint(1, 6)):
            nm, cd = rnd.choice(INTERMEDIARIAS)
            movs.append((nm, cd, aj + timedelta(seconds=rnd.uniform(0.02, 0.98) * span)))
        if rnd.random() < p_aud:
            movs.append(("Audiência", 970, aj + timedelta(seconds=rnd.uniform(0.3, 0.9) * span)))
        if tem_julg:
            nm, cd = rnd.choice(JULGAMENTOS)
            movs.append((nm, cd, alvo))
            t = alvo + timedelta(days=rnd.randint(15, 45))
            if t <= corte_dt and rnd.random() < 0.6:
                movs.append(("Trânsito em julgado", 848, t))
                t2 = t + timedelta(days=rnd.randint(5, 60))
                if t2 <= corte_dt and rnd.random() < 0.7:
                    movs.append(("Baixa Definitiva", 22, t2))
        movs.sort(key=lambda m: m[2])

        orgao = rnd.choice(cfg["orgaos"])
        assuntos = rnd.sample(cfg["assuntos"], rnd.randint(1, 2))
        numero = f"{i:07d}-{rnd.randint(0, 99):02d}.{aj.year}.{cfg['j']}.{cfg['tr']}.{rnd.randint(1, 9999):04d}"
        ultima = movs[-1][2] if movs else aj
        doc = {
            "numeroProcesso": numero,
            "classe": {"codigo": cod, "nome": nome},
            "tribunal": alias.upper(),
            "grau": "G1",
            "dataAjuizamento": _fmt(aj, rnd),
            "dataHoraUltimaAtualizacao": ultima.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "orgaoJulgador": {"codigo": orgao[0], "nome": orgao[1]},
            "assuntos": [{"codigo": c, "nome": n_} for c, n_ in assuntos],
            "movimentos": [{"codigo": cd, "nome": nm, "dataHora": _fmt(t, rnd)} for nm, cd, t in movs],
        }

        if defeitos:
            r = rnd.random()
            if r < 0.01:
                doc["classe"] = {}                       # classe ausente
            elif r < 0.015:
                doc["dataAjuizamento"] = "31/02/2024"    # data impossível/formato desconhecido
            if rnd.random() < 0.01 and doc["movimentos"]:
                antes = aj - timedelta(days=10)          # movimentação anterior ao ajuizamento
                doc["movimentos"].append({"codigo": 85, "nome": "Petição", "dataHora": _fmt(antes, rnd)})
            if rnd.random() < 0.003:
                doc["movimentos"] = []                   # processo sem movimentações
            saida.append((alias, doc))
            if rnd.random() < 0.02 and doc["movimentos"]:
                velho = {**doc, "movimentos": doc["movimentos"][:-1],
                         "dataHoraUltimaAtualizacao": aj.strftime("%Y-%m-%dT%H:%M:%S.000Z")}
                saida.append((alias, velho))             # versão antiga reingerida DEPOIS da nova
        else:
            saida.append((alias, doc))
    return saida
