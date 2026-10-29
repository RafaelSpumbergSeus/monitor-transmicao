# Como apresentar este projeto

Preencha os colchetes **somente** com números do SEU run com dados reais do DataJud. Com dados sintéticos, não publique nenhuma conclusão como se fosse sobre a Justiça.

## Linha de currículo
- Construí pipeline de dados ponta a ponta (Python, SQL, modelo dimensional, Power BI) sobre [X] mil processos públicos do DataJud/CNJ ([tribunais]), com [N] regras automatizadas de qualidade, quarentena de registros inválidos e [N] testes em CI. Repositório: [link].
- Tratei viés de censura à direita nos tempos de tramitação (indicadores por coorte + % julgado), evitando que processos recentes distorcessem a mediana.

## Post de LinkedIn (rascunho)
> Passei [N] semanas construindo um monitor de tramitação processual com dados públicos do DataJud.
> O que mais me ensinou: [sua lição real, ex.: como tratar processos ainda sem julgamento].
> O repositório tem pipeline em camadas (raw → staging → marts), [N] testes, relatório de qualidade e as decisões técnicas documentadas, inclusive onde o método erra.
> [link do GitHub]

## Perguntas de entrevista que este projeto prepara você para responder
- Por que a mediana da coorte 2025 parece melhor? (censura à direita)
- Por que não descartar registros inválidos? (rastreabilidade, conta que fecha, limite de quarentena)
- O que acontece se o mesmo processo chegar duas vezes? (idempotência, versão mais recente)
- Onde esta classificação pode estar errada? (nomes vs. códigos TPU, `decisao` genérica)
- Como levaria isso para produção? (Postgres, orquestração, carga incremental, observabilidade)
