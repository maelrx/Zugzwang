---
id: ADR-015
title: "Parquet + DuckDB"
status: accepted
decision_owner: "Zugzwang maintainers"
human_gate: none
date: "2026-08-12"
source: "greenfield technical design 2026-08-11"
---

# ADR-015: Parquet + DuckDB


**Status recomendado:** aceitar como camada analítica.  
**Decisão:** materializar dados colunares e consultar diretamente.

### Opções

1. SQL no SQLite.
2. pandas/CSV.
3. Parquet + DuckDB.
4. warehouse remoto.

### Trade-offs

SQLite atende queries operacionais, não scans massivos portáveis. CSV perde tipos e é volumoso. DuckDB/Parquet entregam análise local sem serviço. Warehouse remoto contradiz local-first e cria custo.

### Impactos

- **Direto:** finalizer/exporter adicional.
- **Indireto:** notebooks e ferramentas externas consomem dados facilmente.
- **Exterior:** pesquisadores não precisam adotar o runtime para analisar resultados.
- **Subjetivo:** fortalece percepção de projeto científico, não apenas CLI de jogos.

### Reversibilidade

Baixa. Novos formatos podem coexistir.

### Reavaliar quando

Dados excederem um host ou queries multiusuário forem necessárias.

---
