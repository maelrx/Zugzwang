# Visão do produto

## Declaração

O Zugzwang Research Kernel será a infraestrutura aberta de referência para descrever, executar, retomar, auditar e comparar sistemas de decisão baseados em modelos dentro de ambientes verificáveis, começando pelo xadrez.

A ambição não é possuir o melhor bot. A ambição é fornecer a gramática experimental que permita dizer, com precisão, de onde veio cada ganho.

## Problema

Resultados de “LLMs jogando xadrez” frequentemente misturam:

- capacidade do modelo;
- familiaridade com o formato;
- estado fornecido pelo harness;
- movimentos legais expostos;
- retries;
- tools;
- memória externa;
- candidatos ou valores de engine;
- budgets de reasoning;
- seleção entre amostras;
- bugs e forfeits de protocolo.

O resultado final pode parecer um número simples, mas representa sistemas materialmente distintos. Sem um protocolo comum, não há cumulatividade científica.

## Futuro desejado

Um pesquisador deve conseguir:

1. declarar uma condição experimental de forma legível e estrita;
2. executar o mesmo protocolo em modelos, providers e strategies diferentes;
3. interromper e retomar sem corromper a trajetória;
4. publicar um bundle verificável;
5. permitir que outro grupo reavalie o resultado sem acessar o provider original;
6. comparar força, tracking, legalidade, custo, robustez e assistência separadamente;
7. promover um experimento do modo local barato para partidas completas somente após evidência suficiente.

## Princípios

### Attribution first

Competência externa nunca é invisível. Parser, rules engine, legal actions, knowledge packets, search e engine live carregam classes próprias.

### Protocol is data

Prompt, imagem, histórico, legal moves, retries, orçamento, seletor e tool policy fazem parte da condição.

### Artifact first

O resultado público é um bundle portável com checksums, não uma linha efêmera num banco local.

### Local first

O caminho feliz deve funcionar numa máquina de desenvolvimento sem servidor, conta cloud ou cluster.

### Chess first

O domínio inicial recebe profundidade real. A generalização para outros ambientes só ocorre quando contratos estáveis emergirem da implementação.

### Failure is evidence

Timeout, parse failure, illegal move, retry, fallback e protocolo violado não desaparecem em agregados convenientes.

### Cheap before grandiose

A primeira suite usa decisões locais pareadas. Elo e full-game só entram quando a condição demonstra sinal, estabilidade e custo defensável.

## North star

> Tornar impossível confundir uma melhoria de sistema com uma melhoria de modelo sem deixar rastros auditáveis dessa confusão.
