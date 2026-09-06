---
id: ADR-046
title: "Observação multimodal: renderer Pillow determinístico, CAS e lowering explícito"
status: accepted
decision_owner: "Mestre Mael (operador)"
human_gate: GATE-011 (matriz de modelos: ratifica o modelo de visão para execuções pagas)
date: "2026-08-16"
accepted_date: "2026-08-16"
source: "ZGW-0073"
---

# ADR-046: Observação multimodal

## Contexto

REP-001 (RGB, FEN+RGB) e MM-002 (conflito cross-modal) exigem imagem do tabuleiro.
FR-056 exige partes tipadas (imagem) no contrato canônico; FR-058 exige que a
ausência de image input falhe ou pule explicitamente; FR-066 exige probe de
autoridade entre fontes. Os critérios de aceite exigem renderers FEN/ASCII/history/image,
bytes como CAS artifacts, metadata completa do renderer e nenhum fallback
silencioso imagem→texto.

## Decisão

1. `ImagePart` no contrato canônico (`ports/model.py`): mime, dimensões,
   `content_sha256`, `data_base64`, metadata do renderer e `artifact_ref`
   opcional. Sem URL remota mutável.
2. Renderer determinístico em Pillow (`zugzwang_chess/codecs/board_png.py`):
   PNG byte-reprodutível com tema, orientação, coordenadas e tamanho como
   variáveis controladas; metadata completa inclui versão do renderer,
   hash da fonte (FEN) e hash do arquivo de fonte tipográfica.
3. Observação declara `image {enabled, theme, orientation, coordinates,
   square_size_px, fen_override}` e `modality_authority: text|image`.
   `fen_override` diferente do estado simbólico gera `image_conflict` com
   `delta_squares` explícito — mismatch acidental nunca passa silencioso.
4. Bytes da imagem persistem como CAS artifact via `DecisionContext.artifact_store`;
   a part carrega payload base64 + hash para o request canônico.
5. Lowering por adapter: opencode vira `FilePart` com data URL (validado por
   probe real com mimo-v2.5); openai-compatible vira `content` do tipo
   `image_url`. A capacidade MULTIMODAL_IMAGE é declarada pelo operador no
   `backend_config.image_input` e exigida por preflight antes do primeiro call.
6. Modelo de texto principal (deepseek-v4-flash) tem `attachment=false`; as
   condições RGB usam modelo de visão ratificado em GATE-011
   (candidato 80/20: `opencode-go/mimo-v2.5`, já na assinatura do operador).

## Alternativas

1. python-chess SVG + cairosvg;
2. depender de URL remota de imagem;
3. fallback imagem→texto silencioso;
4. bytes inline sem CAS;
5. capacidade inferida automaticamente do registro de modelos.

## Trade-offs

SVG+cairosvg adiciona dependência nativa e tema menos controlável. URL remota
quebra local-first e imutabilidade. Fallback silencioso falsificaria a
interface experimental (FR-058). Inferência automática esconderia o regime do
modelo; declaração explícita é auditável.

## Impactos

- `ImagePart` no contrato público; strategy exige capability quando emite imagem;
- protocol fingerprint muda quando `image`/`modality_authority` estão presentes;
- adapters ganham opção `image_input` declarada;
- runs com imagem em backend sem capability falham antes do primeiro call.

## Reversibilidade

Alta: ImagePart é aditivo ao union de parts; renderer é plugin interno; a
declaração de capacidade é config, não contrato de wire.

## Emenda 2026-09-06 — modelo de visão padrão (GATE-011 ratificado, ZGW-0086)

Com a ratificação do GATE-011 pelo operador, o modelo de visão padrão da matriz
paga passa a ser o próprio `muse-spark-1.3` (`muse-spark-1.3-contributor` no
plano Go, com `muse-spark-1.3-free` como fallback até esgotar a cota), que
possui visão nativa e é acessado via `provider.openai_compatible` no router
opencode local (`127.0.0.1:8788`, perfil `openai-responses`) — o padrão de
acesso validado operacionalmente nas baterias overnight (ZGW-0083/0084).

- Substitui `mimo-v2.5` e `deepseek-v4-flash` na matriz inaugural; ambos deixam
  de ser referenciados pela suite 0.1 (Emenda 002 da preregistration).
- Nada desta ADR muda no contrato: `ImagePart` tipado, renderer Pillow
  determinístico, CAS, `modality_authority` e bloqueio de fallback silencioso
  imagem→texto permanecem exatamente como decididos.
- Efeito científico positivo: texto e visão passam a usar o mesmo modelo,
  eliminando o confundimento modelo×condição registrado na Emenda 001 da suite.
