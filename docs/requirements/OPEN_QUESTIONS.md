# Questões abertas

## Blocking M0

1. Qual licença e rules substrate?
2. Python 3.13 floor com CI 3.14 ou 3.14-only?
3. Qual retention default?
4. O CLI será `zgw`, `zugzwang`, ou ambos?

## Blocking first public release

5. Provider outputs podem ser redistribuídos em bundles públicos?
6. Stockfish é somente user-provided ou haverá downloader?
7. Qual estabilidade prometida aos plugin contracts?
8. Standard chess only ou Chess960 experimental?
9. Quem mantém price snapshots?
10. PT-BR ou English como canonical docs?

## Research design

11. Qual suite inicial e tamanho?
12. Quais modelos/providers cabem no budget?
13. WDL loss ou clipped CP loss como primary?
14. Qual renderer visual canônico?
15. Como construir packets corretos/errados sem leakage?
16. Quais licenses permitem redistribuir positions/rationales?
17. O primary report usa one call ou replicates?
18. Quais conditions entram em full-game?

## Engineering

19. ULID/UUIDv7/content-derived condition IDs?
20. SQLAlchemy async ou sync behind writer thread?
21. PyArrow ou Polars writer para Parquet?
22. Zstandard dependency para Python 3.13 ou conditional stdlib 3.14?
23. Assinatura de bundles entra antes de 1.0?
24. Plugin metadata sem import pesado é requisito inicial?
25. Encryption-at-rest é core ou external policy?

Open questions must be converted into ADRs or explicit backlog items before implementation relies on an answer.
