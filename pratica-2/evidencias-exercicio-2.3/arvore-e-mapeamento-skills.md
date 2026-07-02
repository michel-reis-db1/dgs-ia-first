# Estratégia de Skills — NovaTech Assistant (Ex. 2.3 — Desenvolvedor)

> Gerado com **Claude (chat)**. Referências: cenário completo, **Anexo C**
> (estrutura do repositório — hierarquia `/skills/foundation/`,
> `/skills/domain/`, `/skills/artifact/`) e o estado real do **Anexo D —
> Starter Repo**, onde as 9 pastas/arquivos de skill já existem vazios
> (`skills/foundation/{typescript-conventions,error-handling,project-structure}.md`,
> `skills/domain/{azure-functions-endpoint,azure-ai-search-integration,react-components,testing-patterns}.md`,
> `skills/artifact/{create-rag-endpoint,create-integration-test,create-react-card}.md`).
> A árvore abaixo confirma esse conjunto como base e propõe 2 extensões para
> cobrir lacunas identificadas na lista de artefatos recorrentes do projeto.

---

## 1. Árvore de skills (Foundation → Domain → Artifact)

```
skills/
├── foundation/                          # convenções globais — todo agente lê antes de gerar qualquer .ts/.tsx
│   ├── typescript-conventions.md        # strict mode, imports ESM, naming, z.infer em vez de tipos manuais
│   ├── error-handling.md                # AppError/subclasses, logging via pino, retry/backoff
│   └── project-structure.md             # onde cada tipo de arquivo mora (Anexo C), limites entre módulos
│
├── domain/                              # padrões por camada — como uma família de artefatos é estruturada
│   ├── azure-functions-endpoint.md      # padrão HTTP trigger (handler/validator/response-builder)
│   ├── azure-ai-search-integration.md   # padrão de query/embedding/indexação contra Azure AI Search
│   ├── react-components.md              # padrão de componentes do painel web (cards, forms, hooks)
│   └── testing-patterns.md              # Vitest + msw + fixtures, arrange/act/assert
│
└── artifact/                            # receitas de geração — de spec/task a arquivo pronto
    ├── create-rag-endpoint.md           # receita completa: endpoint com padrão RAG (query, futuros)
    ├── create-integration-test.md       # receita completa: teste de integração para um endpoint
    └── create-react-card.md             # receita completa: card de resposta/feedback no painel web
```

### Lacuna identificada e proposta de extensão

A lista de artefatos recorrentes do projeto tem 5 itens (endpoints RAG, testes
de integração, componentes React, **documentação técnica de endpoints
(ADRs, README de módulos)** e **specs de produto SDD**). Os 9 arquivos acima
— que já existem como placeholders no Anexo D — cobrem os 3 primeiros, mas
não os últimos dois. Isso significa que, hoje, um agente gerando uma ADR ou
um `requirements.md` não tem skill nenhuma para seguir e seria "genérico" —
exatamente o risco que o conceito de skill existe para evitar.

Proposta (não criada nesta entrega — fica registrada como backlog para não
inflar o escopo deste exercício, que pede a *estratégia*, não a criação de
todas as skills):

| Skill proposta | Nível | Cobre | Dono sugerido |
|---|---|---|---|
| `technical-documentation.md` | Domain | Estrutura comum a ADRs e README de módulo (o que vai em cada seção, tom, nível de detalhe) | Tech Lead |
| `create-adr.md` | Artifact | Receita para gerar uma nova ADR a partir de `docs/adr/template.md` | Tech Lead |
| `create-spec-requirements.md` | Artifact | Receita para gerar `requirements.md` de um novo módulo seguindo o formato SDD (outcomes, scope boundaries, constraints, prior decisions, verification criteria) | Product Specialist |

Sem essas 3, o time continua dependendo de um humano lembrar manualmente o
formato de ADR e de spec toda vez — o que é exatamente o padrão que já
falhou no cenário 1 (documentação inconsistente no SharePoint/Confluence).

---

## 2. Mapeamento por skill — criação, consumo e frequência

| Skill | Nível | Frase de ativação (o que o agente reconhece) | Quem cria | Quem consome (papel + agente) | Frequência estimada |
|---|---|---|---|---|---|
| `typescript-conventions` | Foundation | "Todo arquivo `.ts`/`.tsx` gerado ou editado no repositório" | Tech Lead (com Dev Sênior) | Todos os Devs, via Copilot e Claude Code; Tech Lead no code review | **Altíssima** — toda linha de código TS do projeto |
| `error-handling` | Foundation | "Uma função pode falhar por causa externa (Azure, input inválido, timeout)" | Tech Lead | Devs (Pleno/Sênior) via Copilot | **Alta** — todo `service`/`handler` que cruza uma fronteira externa |
| `project-structure` | Foundation | "Preciso decidir em qual pasta um novo arquivo entra, ou criar um novo módulo" | Tech Lead | Devs + Copilot (scaffolding de novo módulo) | **Média** — a cada novo módulo/endpoint, não a cada arquivo |
| `azure-functions-endpoint` | Domain | "Preciso criar ou alterar um HTTP trigger do Azure Functions" | Tech Lead + Dev Sênior | Devs via Copilot (query, feedback, health e futuros endpoints) | **Alta** — 5 endpoints conhecidos hoje + manutenção contínua |
| `azure-ai-search-integration` | Domain | "Preciso ler ou escrever no índice do Azure AI Search (busca, embedding, indexação)" | Dev Sênior | Dev responsável por `services/search.ts`, `pipeline/indexer.ts` | **Média** — poucos arquivos tocam isso, mas são críticos (guardrail de alucinação) |
| `react-components` | Domain | "Preciso criar um componente do painel web" | Dev Pleno (painel web), com input do Product Specialist para copy/UX | Dev do painel web via Copilot | **Média** — cresce com o número de telas do dashboard |
| `testing-patterns` | Domain | "Preciso escrever qualquer teste (unit ou integration)" | QA + Dev Sênior | Todos os Devs via Copilot; QA no review | **Alta** — todo código de produção deveria ter teste acompanhando |
| `create-rag-endpoint` | Artifact | "Preciso de um novo endpoint que segue o padrão RAG completo (busca + prompt + completion)" | Dev Sênior (extraída da 1ª implementação real — query endpoint) | Devs via Copilot para endpoints RAG futuros | **Média** — receita cara de errar, usada poucas vezes mas de alto impacto |
| `create-integration-test` | Artifact | "Preciso do teste de integração de um endpoint recém-implementado" | QA (mesma skill produzida no Ex. 2.3 da QA) | Devs via Copilot, a cada task de implementação | **Altíssima** — praticamente todo PR de endpoint |
| `create-react-card` | Artifact | "Preciso de um card (resposta ou feedback) no painel web ou no Teams" | Dev Pleno | Dev do painel web / bot via Copilot | **Baixa-média** — poucos tipos de card, reuso alto depois de criados |

**Leitura importante:** a coluna "quem consome" nunca é só "o Dev" — QA
consome `testing-patterns` e `create-integration-test` no review, Product
Specialist consome `react-components` para garantir que a copy do painel bate
com a linguagem ubíqua, e Tech Lead consome todas no code review. Skills não
são uma ferramenta só de dev; são o mecanismo pelo qual o padrão do time vira
algo que o agente de qualquer papel consegue seguir.

---

## 3. Escolha da skill Foundation mais importante

**Escolhida: `typescript-conventions`.**

Justificativa: as outras duas skills Foundation (`error-handling`,
`project-structure`) são convenções específicas de um recorte (como tratar
falhas; onde um arquivo mora). `typescript-conventions` é a única que é
**pré-requisito de leitura de todas as outras 8 skills** — toda skill
Domain e Artifact deste projeto produz código TypeScript, e os exemplos de
código dentro delas só fazem sentido se o agente já souber os padrões
básicos (strict mode, como tipar com `z.infer` em vez de duplicar
interfaces manualmente, convenção de import ESM, quando usar `class` vs
`type`). É a skill que, se ausente ou mal escrita, degrada a qualidade de
**tudo** que é gerado depois — inclusive o próprio `error-handling.md` (que
define `class AppError extends Error`) e os exemplos de código dentro de
`azure-functions-endpoint.md` ou `testing-patterns.md`.

O `SKILL.md` completo desta skill está em
[`../../Anexo-D-starter-repo-novatech-assistant/novatech-assistant/skills/foundation/typescript-conventions.md`](../Anexo-D-starter-repo-novatech-assistant/novatech-assistant/skills/foundation/typescript-conventions.md)
(gerado com apoio do GitHub Copilot/Claude Code, cópia em
[`skill-md/typescript-conventions.md`](skill-md/typescript-conventions.md)).
