# Mini PRD de teste (ZGW-0087)

Documento sintético para os testes offline do contexto de retrieval
determinístico. Estrutura espelha o PRD real: front matter, seções `#`,
subseções `##`, um bloco longo maior que 1800 caracteres e headings de
workflows (ADR, work order, gate, PR, revisão, testes).

# 17. Retrieval e memória

## 17.1. Classificação das afirmações

Toda afirmação do documento é BASELINE, PROPOSTA ou HIPÓTESE. A
classificação aparece junto do texto e nunca é inferida silenciosamente
pelo agente de codificação.

## 17.2. Gates de decisão humana

Um gate pendente não é uma recomendação aceita. Só o operador humano
ratifica gates de licença, retenção e matriz de modelos. O agente
prepara o pacote de decisão e para.

## 17.6. Quando considerar BM25 e embeddings

BM25 cobre termos exatos; embeddings cobrem paráfrases. O híbrido RRF
funde as duas listas com k=60. Substring exata serve apenas para
citação literal do documento.

# 38. Governança de implementação

## 38.7. Definição de pronto de uma PR

Uma PR precisa de testes offline verdes, revisão por perspectivas e
merge limpo na main. Branch sai de main atualizada.

## 38.2. Revisão por perspectivas

A revisão avalia contrato, testes e rastreabilidade. Comentários não
ratificam gates nem autorizam gastos.

## 35.2. Metas de cobertura de testes

Cobertura de linhas e de ramos é medida por pacote. Testes default não
fazem chamadas de rede nem gastam dinheiro.

## ADR-CB-013. Retrieval elegível antes de ranking

Retrieval elegível (filtrar por estado e permissão) vem antes de
ranking denso. Nenhum reranker substitui o filtro determinístico.

## 38.10. CB-WO-09: memória condicionada

A work order CB-WO-09 entrega memória condicionada por snapshot
imutável, com overlay da decisão e verificação de compatibilidade.

## 38.11. Bloco longo para split determinístico

PARA_LONGO_1 A fritadeira de dados não existe aqui: cada linha desta
seção existe para exercitar o split de parágrafos em pedaços menores
que o limite de 1800 caracteres mantendo cobertura total de linhas.
O contexto de retrieval precisa preservar a ordem determinística dos
pedaços, numerar as partes de cada subseção e manter os spans de linha
sem lacuna nem sobreposição para qualquer documento de entrada.
REPETE_PREENCHIMENTO AAAA BBBB CCCC DDDD EEEE FFFF GGGG HHHH IIII JJJJ.
REPETE_PREENCHIMENTO AAAA BBBB CCCC DDDD EEEE FFFF GGGG HHHH IIII JJJJ.
REPETE_PREENCHIMENTO AAAA BBBB CCCC DDDD EEEE FFFF GGGG HHHH IIII JJJJ.
REPETE_PREENCHIMENTO AAAA BBBB CCCC DDDD EEEE FFFF GGGG HHHH IIII JJJJ.
REPETE_PREENCHIMENTO AAAA BBBB CCCC DDDD EEEE FFFF GGGG HHHH IIII JJJJ.
REPETE_PREENCHIMENTO AAAA BBBB CCCC DDDD EEEE FFFF GGGG HHHH IIII JJJJ.
REPETE_PREENCHIMENTO AAAA BBBB CCCC DDDD EEEE FFFF GGGG HHHH IIII JJJJ.
REPETE_PREENCHIMENTO AAAA BBBB CCCC DDDD EEEE FFFF GGGG HHHH IIII JJJJ.
REPETE_PREENCHIMENTO AAAA BBBB CCCC DDDD EEEE FFFF GGGG HHHH IIII JJJJ.
REPETE_PREENCHIMENTO AAAA BBBB CCCC DDDD EEEE FFFF GGGG HHHH IIII JJJJ.
REPETE_PREENCHIMENTO AAAA BBBB CCCC DDDD EEEE FFFF GGGG HHHH IIII JJJJ.
REPETE_PREENCHIMENTO AAAA BBBB CCCC DDDD EEEE FFFF GGGG HHHH IIII JJJJ.

PARA_LONGO_2 A segunda continuação mantém o mesmo tamanho do
primeiro parágrafo para forçar um segundo corte de peças. O índice
guardado no manifesto registra o sha256 do documento fonte e a
configuração completa, sem timestamp, para que dois rebuilds produzam
artefatos byte idênticos em qualquer máquina do projeto.
REPETE_PREENCHIMENTO KKKK LLLL MMMM NNNN OOOO PPPP QQQQ RRRR SSSS TTTT.
REPETE_PREENCHIMENTO KKKK LLLL MMMM NNNN OOOO PPPP QQQQ RRRR SSSS TTTT.
REPETE_PREENCHIMENTO KKKK LLLL MMMM NNNN OOOO PPPP QQQQ RRRR SSSS TTTT.
REPETE_PREENCHIMENTO KKKK LLLL MMMM NNNN OOOO PPPP QQQQ RRRR SSSS TTTT.
REPETE_PREENCHIMENTO KKKK LLLL MMMM NNNN OOOO PPPP QQQQ RRRR SSSS TTTT.
REPETE_PREENCHIMENTO KKKK LLLL MMMM NNNN OOOO PPPP QQQQ RRRR SSSS TTTT.
REPETE_PREENCHIMENTO KKKK LLLL MMMM NNNN OOOO PPPP QQQQ RRRR SSSS TTTT.
REPETE_PREENCHIMENTO KKKK LLLL MMMM NNNN OOOO PPPP QQQQ RRRR SSSS TTTT.
REPETE_PREENCHIMENTO KKKK LLLL MMMM NNNN OOOO PPPP QQQQ RRRR SSSS TTTT.
REPETE_PREENCHIMENTO KKKK LLLL MMMM NNNN OOOO PPPP QQQQ RRRR SSSS TTTT.
REPETE_PREENCHIMENTO KKKK LLLL MMMM NNNN OOOO PPPP QQQQ RRRR SSSS TTTT.
REPETE_PREENCHIMENTO KKKK LLLL MMMM NNNN OOOO PPPP QQQQ RRRR SSSS TTTT.

PARA_LONGO_3 O terceiro bloco fecha a subseção longa. Depois dele vem
uma subseção curta que encerra o documento e permite verificar que o
último pedaço termina na última linha do arquivo sem deixar linha
órfã fora de qualquer pedaço do contexto.
REPETE_PREENCHIMENTO UUUU VVVV WWWW XXXX YYYY ZZZZ 0000 1111 2222 3333.
REPETE_PREENCHIMENTO UUUU VVVV WWWW XXXX YYYY ZZZZ 0000 1111 2222 3333.
REPETE_PREENCHIMENTO UUUU VVVV WWWW XXXX YYYY ZZZZ 0000 1111 2222 3333.
REPETE_PREENCHIMENTO UUUU VVVV WWWW XXXX YYYY ZZZZ 0000 1111 2222 3333.
REPETE_PREENCHIMENTO UUUU VVVV WWWW XXXX YYYY ZZZZ 0000 1111 2222 3333.
REPETE_PREENCHIMENTO UUUU VVVV WWWW XXXX YYYY ZZZZ 0000 1111 2222 3333.
REPETE_PREENCHIMENTO UUUU VVVV WWWW XXXX YYYY ZZZZ 0000 1111 2222 3333.
REPETE_PREENCHIMENTO UUUU VVVV WWWW XXXX YYYY ZZZZ 0000 1111 2222 3333.
REPETE_PREENCHIMENTO UUUU VVVV WWWW XXXX YYYY ZZZZ 0000 1111 2222 3333.
REPETE_PREENCHIMENTO UUUU VVVV WWWW XXXX YYYY ZZZZ 0000 1111 2222 3333.
REPETE_PREENCHIMENTO UUUU VVVV WWWW XXXX YYYY ZZZZ 0000 1111 2222 3333.
REPETE_PREENCHIMENTO UUUU VVVV WWWW XXXX YYYY ZZZZ 0000 1111 2222 3333.

## 38.12. Subseção final curta

Fim do documento de teste. Nenhuma linha deve ficar fora de um chunk.
