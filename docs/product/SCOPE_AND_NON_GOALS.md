# Escopo e não objetivos

## Fronteira positiva

O Zugzwang controla:

- descrição do protocolo;
- resolução de configuração;
- execução e lifecycle;
- contracts entre ambiente, strategy, model backend, tools e evaluators;
- persistência operacional;
- evidência e proveniência;
- avaliação e export;
- classificação de assistência;
- portabilidade do resultado.

## Fronteira negativa

O Zugzwang não deve absorver responsabilidade por:

- implementar todos os SDKs de todos os providers;
- administrar contas e billing de terceiros;
- fornecer uma engine;
- redistribuir datasets sem licença clara;
- executar código produzido pelo modelo;
- oferecer treinamento de modelos no v0.1;
- garantir reprodutibilidade bit a bit de APIs mutáveis;
- transformar qualquer jogo ou ambiente numa abstração genérica antes de haver demanda comprovada;
- operar serviço público ou ranking como requisito do kernel;
- determinar sozinho a verdade pedagógica de explicações em linguagem natural.

## Teste de entrada de feature

Uma feature pertence ao kernel se responder “sim” a pelo menos uma das perguntas:

1. Ela é necessária para descrever fielmente uma condição experimental?
2. Ela impede atribuição incorreta de competência?
3. Ela é necessária para retomar, auditar ou portar a execução?
4. Ela representa uma fronteira estável entre domínio e infraestrutura?
5. Ela precisa ser compartilhada por CLI e uma futura API?

Caso contrário, tende a pertencer a:

- plugin;
- reporter;
- domínio chess;
- suite de pesquisa;
- ferramenta de desenvolvimento;
- produto hosted futuro.

## Anti-roadmap

Não inserir antes de M6:

- React, Vite, Next.js;
- FastAPI como dependência do core;
- autenticação e tenancy;
- S3 obrigatório;
- Postgres obrigatório;
- Kafka, RabbitMQ, Redis ou Celery;
- Kubernetes;
- LangGraph ou Temporal como runtime central;
- vector DB;
- notebook como fonte de verdade;
- LLM-as-judge como métrica primária;
- download automático de binários sem política de supply chain.
