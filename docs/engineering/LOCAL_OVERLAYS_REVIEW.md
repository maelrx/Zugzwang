# Overlays locais preservados para revisão

ZGW-0085 conserva arquivos não rastreados do checkout principal na fotografia de 2026-09-05. Base: PR #12. O objetivo é tornar diferenças visíveis; esta branch não é recomendação de integração.

## Conteúdo

- Dois manifestos de replicação MuseSpark/GLM.
- Versão local de ZGW-0077 e migration 0006.
- Fontes alternativas do builder e viewer legado.
- Migrações 0003/0004/0005 já eram idênticas à base e não geram delta.

## Bloqueios

Reconciliar migration 0006 com a fundação e o trabalho do Hermes sem editar migrations aplicadas silenciosamente. Comparar os builders/viewers antes de escolher uma implementação; evitar sobrescrever a branch separada de viewer-next. Os manifestos de replicação permanecem exploratórios e precisam dos contratos corrigidos de #14. Não executar automaticamente.

Snapshots privados, bancos, CAS, secrets e links de skills não foram incluídos. Os arquivos originais e seus hashes foram preservados em backup privado; qualquer reorganização local deve verificar que não mudaram após a fotografia.
