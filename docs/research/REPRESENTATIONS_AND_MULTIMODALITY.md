# Representações, multimodalidade e injeção de conhecimento

## 1. O que já foi testado

### Representação textual

A literatura usa FEN, ASCII, PGN, SAN, UCI, board matrices e histórico puro. Os formatos não são equivalentes:

- FEN entrega estado atual compacto, mas não repetição completa;
- ASCII explicita geometria em texto e custa mais tokens;
- PGN/histórico preserva trajetória, mas exige tracking;
- SAN carrega peça, captura, check, mate e desambiguação;
- UCI é mecânico e inequívoco, com menos leakage semântico.

### Visual

[LMAct](https://arxiv.org/abs/2412.01441) avaliou chess com ASCII, FEN, PGN e RGB, além de demonstrações expert e Chain-of-Thought. A imagem não venceu automaticamente os formatos textuais, e centenas de demonstrações não resolveram a tarefa.

[MET-Bench](https://arxiv.org/abs/2502.10886) isolou tracking de entidades em mudanças textuais e visuais. O resultado relevante para Zugzwang é que visual tracking constitui um gargalo próprio.

### Legal actions

LLM CHESS, ChessArena e Chess-R1 mostram que fornecer ações legais aumenta validade e frequentemente melhora o resultado. ChessArena também sugere que a lista pode alterar a profundidade aparente do reasoning.

### Expert knowledge

- MATE usa estratégia e tática anotadas por experts para candidate reranking.
- UniMaia controla uma policy especialista congelada com linguagem.
- Strategy Verbalization comprime análise em descrições estratégicas.
- Three-Body Alignment mostra que rationales de GMs, humanos assistidos e LLMs não são semanticamente equivalentes.
- ACT-Eval mostra que comentários fluentemente convincentes ainda contêm claims verificavelmente falsos.

## 2. Perguntas ainda abertas

1. Imagem redundante ajuda quando FEN perfeito já está disponível?
2. A melhoria visual vem de perception ou de um scaffold espacial auxiliar?
3. Qual fonte vence quando FEN e imagem discordam?
4. Uma knowledge packet correta melhora policy além de persona e token priming?
5. Uma skill errada prejudica de forma previsível?
6. Few-shot semanticamente pareado supera many-shot aleatório sob o mesmo budget?
7. Legal grounding tardio preserva reasoning sem pagar o custo de ilegalidade?
8. SAN ajuda por familiaridade, por informação semântica ou pelos dois?
9. Histórico curto e estado atual são complementares ou redundantes?
10. O modelo usa o conteúdo da explicação ou apenas muda seu modo de geração?

## 3. Decomposição obrigatória

Para cada input multimodal:

```text
perception
→ state reconstruction
→ legal affordances
→ local decision
→ explanation claims
```

Um `best move` correto não prova perception correta. O modelo pode ignorar a imagem e usar FEN; pode perceber uma posição errada e acertar por prior; pode gerar comentário plausível após a decisão.

## 4. Controles causais

### Redundância

- FEN A + image A;
- PGN A + image A;
- FEN A + PGN A + image A.

### Conflito mínimo

- FEN A + image B, com uma peça deslocada;
- side-to-move conflict;
- castling-right conflict somente textual;
- orientation conflict;
- coordinate labels conflitantes.

### Autoridade declarada

- texto autoritativo;
- imagem autoritativa;
- nenhuma autoridade declarada;
- tool para resolver conflito.

### Skills

- baseline;
- persona GM;
- princípios genéricos;
- packet correto;
- packet errado plausível;
- packet irrelevante token-pareado;
- packet contraditório;
- current-position engine verbalization como positive control separado.

## 5. Requisitos de renderização

Toda imagem de tabuleiro deve registrar:

- source state hash;
- renderer ID e versão;
- resolução;
- orientação;
- tema;
- piece set;
- coordinates on/off;
- side-to-move marker;
- cropping;
- MIME;
- hash do artifact.

Sem isso, “RGB input” não é reproduzível.

## 6. Política para knowledge packets

Knowledge packets devem ser:

- estáticos no v0.1;
- versionados;
- menores que o prompt inteiro;
- livres de best move/current eval salvo quando classificados `K7`;
- acompanhados de origem, licença, curador e data;
- comparáveis por token budget;
- isolados de retrieval para permitir causal attribution.

O nome “skill” no experimento não deve ser confundido com agent skills do Codex. O tipo de domínio é `KnowledgePacket`.
