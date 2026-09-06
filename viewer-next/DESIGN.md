# Zugzwang Match Desk

## Contexto

O operador lê partidas, falhas e métricas por períodos longos, inclusive à noite, na interface escura já usada. Preservar o tema escuro com contraste claro e menos ruído.

## Direção

Produto com neutros escuros levemente quentes, um acento cobre reservado a seleção e ações. Tipografia Geist Sans e Geist Mono local. Sem hero promocional, gradientes, cartões de métricas repetidos ou animação decorativa.

## Estrutura

Navegação estável à esquerda; uma biblioteca principal, sem lista duplicada. Título e ferramentas na mesma faixa. Detalhe com identidade contínua e abas Partida, Análise e Evidências. Tabuleiro e folha de lances lado a lado; estatísticas progressivas.

## Tokens

Cores OKLCH em src/index.css: ink/panel/panel2/line/paper/muted/faint/accent/ok/warn/err/info. Escala de espaçamento 4/8/12/16/24/32; corpo 14px, controles 13px, títulos 24px. Foco de 2px; alvos de 36px ou maiores; superfícies com borda discreta de 1px.

## Estados

Carregamento inicial estruturado; atualização discreta; erro com última leitura preservada; resultados vazios recuperáveis; metadata ausente identificada; comparabilidade desconhecida declarada. Sem usar a cor verde para uma derrota apenas porque o processo completou.
