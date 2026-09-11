---
id: ADR-062
title: "Histórico local e análise pós-partida da arena"
status: accepted
decision_owner: "Mestre Mael"
date: "2026-09-09"
source: "Pedido direto do operador; ZGW-0110"
---

# ADR-062: Histórico e análise da arena

A arena já é uma experiência local autorizada (ZGW-0108), com JSON/PGN
salvos por lance. O operador solicitou histórico e análise automática depth
20 ao terminar cada jogo. Esses jogos continuam não canônicos e privados.

A gravação existente permanece compatível. Um helper no adapter de xadrez
reconstrói posições a partir do FEN inicial e da sequência UCI. O HTTP
apenas expõe esse replay e chama o serviço de análise da aplicação.

O runtime mantém uma fila local com um worker, checkpoints JSON atômicos e
transcrições de tentativas append-only. Não contém regras enxadrísticas ou
imports de engines. Recebe o avaliador na composição do serviço. O plugin
Stockfish reutiliza o cliente UCI existente e aplica go depth 20 a todas as
posições com histórico, força máxima, Threads=2, Hash=128, MultiPV=1. O
perfil inclui versão, hash do executável e do código. Falhas não viram zero.

Uma posição terminal não precisa de busca; mate comprovado pelo engine pode
encerrar antes do limite. Profundidade solicitada e efetiva são distintas e
exibidas. Avaliações são sempre pela perspectiva das brancas. CPL é a queda
entre avaliações adjacentes, com piso zero, apenas quando ambas são em cp;
é uma medida exploratória, não precisão ou rating. Mate é mostrado separado.

Finalizar por regra ou desistência dispara análise. Chamadas repetidas não
duplicam jobs; reiniciar o serviço retoma checkpoints. Pedir análise de
partida em andamento é rejeitado. Resultados nunca são enviados ao provider.

API local aditiva: positions no estado; GET/POST games/{id}/analysis;
analysis status no histórico. Clientes anteriores continuam compatíveis.
Nenhuma mudança nos contratos públicos do kernel ou nos gates de release.
