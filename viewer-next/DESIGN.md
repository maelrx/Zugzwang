---
name: Zugzwang Chess Desk
description: Arena local de xadrez e revisão de partidas
colors:
  background: "oklch(0.13 0.006 70)"
  surface: "oklch(0.18 0.009 70)"
  elevated: "oklch(0.225 0.012 70)"
  line: "oklch(0.33 0.015 70)"
  text: "oklch(0.94 0.014 85)"
  secondary: "oklch(0.74 0.018 80)"
  accent: "oklch(0.8 0.09 75)"
typography:
  title:
    fontFamily: "Geist Sans, system-ui, sans-serif"
    fontSize: "24px"
    fontWeight: 550
  body:
    fontFamily: "Geist Sans, system-ui, sans-serif"
    fontSize: "14px"
    lineHeight: 1.5
  notation:
    fontFamily: "Geist Mono, monospace"
    fontSize: "14px"
rounded:
  control: "7px"
  panel: "12px"
spacing:
  tight: "8px"
  group: "16px"
  section: "24px"
---

# Design System: Zugzwang

## Overview

Ferramenta de uso pessoal para jogar e estudar por períodos longos. O tema
escuro foi solicitado pelo operador, com marrom/dourado claro como acento.
O redesenho coloca o tabuleiro ao lado de um painel de contexto estável;
configuração e jogo ativo têm hierarquias diferentes.

## Colors

Neutros quase pretos levemente quentes. Dourado para ação principal,
seleção e avaliação; verde e vermelho reservados a estado/resultado. O
modo Claro continua disponível, usando os tokens existentes do app.

## Typography

Uma família de UI; monoespaçada para notação e valores. Títulos 24px,
controles 13–14px e metadados 11–12px, evitando texto minúsculo para ações.

## Elevation

Um painel de contexto ao lado do tabuleiro. Divisores e superfícies definem
as seções, sem cartões dentro de cartões e sem efeitos de vidro.

## Components

Navegação lateral compacta nos modos de xadrez. Controles de 40px ou mais,
44px no toque. Formulário com oponente/modelo/cor e opções avançadas
recolhidas. Durante o jogo, status e lista de lances substituem o formulário.
Histórico usa linhas tabulares; a revisão reúne avaliação, linha principal,
lista de lances e transporte de replay. Movimento restrito a feedback curto,
sem animação decorativa na entrada ou na navegação por teclado.

## Do's and Don'ts

Manter contraste e foco claros. Usar links para navegar e botões para ações.
Não inventar precisão, Elo ou resultados. Nunca trocar o backend ou dados
para produzir uma aparência de funcionalidade. Não esconder lances em favor
de cabeçalhos grandes ou configurações durante a partida.


## Pensamento do modelo — ZGW-0114

Painel de divulgação progressiva no Jogar: aberto enquanto o modelo responde,
recolhido após concluir e reabrível. Resumos são do provedor, não geração da UI.
Rodada e duração substituem porcentagens inventadas. Sem resumo disponível,
mostrar mensagem honesta e etapas reais. Rolagem acompanha o final somente
quando o leitor permanece nele. Tema, tabuleiro e controles mantêm a hierarquia.
