# Viewer experimental em revisão

ZGW-0085 organiza fontes originalmente commitadas até `18c98ae` no worktree overnight. Base: PR #11. Snapshot de código sem dados novos de runs; `viewer/data.js` contém somente uma fixture vazia. Bancos, CAS, `viewer/data.json` e public/data não foram publicados.

## Bloqueios

- Depende de #9/#10/#11; não representa aprovação de escopo Web UI pelo roadmap.
- Registrar separação entre avaliação oficial e engine visual SF18 WASM; verificar proveniência e limites no UI.
- Validar build, comportamento do worker, isolamento de recursos e atualização do snapshot antes de merge.
- `analyze_deep.py` no snapshot possui quatro findings Ruff, em correção no Hermes/ZGW-0084. Não incorporar arquivos mutáveis sem commit/revisão.
- O validator atual interpreta tsconfig JSONC como JSON e pode varrer node_modules. Issue #15 acompanha a correção sem enfraquecer os checks de fontes.

Não editar nem rebasear `overnight/h3-runs` para revisar esta branch. Manter as alterações futuras como deltas explícitos.
