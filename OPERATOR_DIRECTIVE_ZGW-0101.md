# OPERATOR DIRECTIVE — ZGW-0101 (Mestre Mael, autoridade humana final)

**Data:** 2026-09-06 · **Escopo:** todos os runs do pilot ZGW-0101 e qualquer run futuro deste workspace.

## Diretriz (obrigatória, não é recomendação)

Todo run real deste workspace usa **exclusivamente** o modelo:

```
model: muse-spark-1.3-contributor
provider: opencode-router        # loopback http://127.0.0.1:8788/v1
profile: openai-responses
```

**Nenhum outro modelo. Em particular: nada de `kimi-*`** (kimi-k2.5, kimi-k2.6, kimi-k2.7-code, kimi-k3 etc.), nem como primário, nem como fallback, nem em comentários/nomes de arquivo. Não há exceção sem nova diretiva escrita do operador.

## Por que esta diretiva existe

Manifests do pilot foram rotulados com "kimi" no nome do arquivo e no campo `metadata.name`, embora sempre tenham apontado para `muse-spark-1.3-contributor`. Isso gerou confusão de identidade de modelo nos relatórios. O operador determinou: zero resíduo do rótulo "kimi".

## Ações já executadas (pelo monitor, a pedido do operador)

1. `experiments/cb-pilot-roundtrip-kimi-real.yaml` → renomeado para **`experiments/cb-pilot-roundtrip-muse-real.yaml`** (conteúdo intacto; `metadata.name` atualizado para `cb-pilot-roundtrip-muse-real`).
2. `experiments/cb-pilot-directed-explore-kimi-real.yaml` → renomeado para **`experiments/cb-pilot-directed-explore-muse-real.yaml`** (conteúdo intacto; `metadata.name` atualizado para `cb-pilot-directed-explore-muse-real`).
3. Verificado: nenhum `model: kimi*` em nenhum manifest de `experiments/`; nenhuma referência "kimi" restante em YAML/TOML/MD fora dos registros históricos imutáveis (raw evidence não é apagada).

## Instruções para os próximos passos do pilot

- **Casos dirigidos:** usar `experiments/cb-pilot-directed-explore-muse-real.yaml` (o caminho antigo `-kimi-` não existe mais).
- **Jogos progressivos / resume / novos manifests:** nomear arquivos e workspaces com prefixo `muse`/`musespark` (padrão já usado em `experiments/local-musespark-*`), nunca `kimi`.
- Ao reportar resultados, identificar o modelo pelo que está gravado no wire request (campo `model`), não por apelidos.
- Não alterar `provider_id`, `base_url` nem `profile`: roteador local opencode, loopback, `openai-responses`.
