# Tasks — Query Endpoint

> Gerado a partir de `plan.md` (Ex. 2.2 — Dev, com apoio de IA). Cada task é uma
> unidade atômica: um módulo/arquivo do Anexo C, com critérios de aceite
> verificáveis e testável de forma isolada (mocks para tudo que é externo).
> Aprovação: Tech Lead (Gate 2 — Tasks → Implement, ver AGENTS.md).

---

## QE-01 — Setup do endpoint com validação de input

**Descrição:** Criar a fundação do endpoint `POST /api/query`: utilitários
compartilhados (`shared/config.ts`, `shared/logger.ts`, `shared/errors.ts`),
contratos de dados (`shared/types.ts`), validação de input via Zod
(`functions/query/validator.ts`) e o HTTP trigger no Azure Functions v4
(`functions/query/handler.ts`). Sem lógica de busca/completion ainda — a
resposta de sucesso é um placeholder explícito.

**Critérios de aceite:**
- `config.ts` exporta um objeto `config` validado via Zod a partir de
  `process.env`; lança erro na inicialização se uma variável obrigatória
  estiver ausente (nunca falha silenciosamente em runtime).
- `logger.ts` exporta uma instância única de `pino`; nenhum arquivo do projeto
  usa `console.log`/`console.error`.
- `errors.ts` exporta `ValidationError` e `UpstreamServiceError`, cada uma com
  `statusCode` e `code` machine-readable.
- `types.ts` define `QueryRequest` e `QueryResponse` (via `z.infer`);
  `QueryResponse.source_document` é obrigatório (nunca opcional — guardrail do
  cenário, mesmo em respostas de baixa confiança).
- `validator.ts` exporta `parseQueryRequest(body: unknown)`: aceita `question`
  (string não vazia) e `conversationHistory` opcional com **no máximo 3
  turnos** (ADR-0002); lança `ValidationError` com detalhes por campo quando
  inválido.
- `handler.ts` registra `POST /api/query` (`app.http`): body válido → 200 com
  payload no formato `QueryResponse` (placeholder); body inválido → 400 com
  `{ code, message, details }`; exceção não mapeada → 500 sem vazar stack
  trace no corpo (mas logada via `logger`).
- Testes cobrindo: env inválido em `config`, `parseQueryRequest` com payload
  válido/`question` ausente/`question` vazia/>3 turnos, e o handler nos 3
  cenários de resposta (200/400/500).

**Dependências:** nenhuma.
**Estimativa:** M

---

## QE-02 — Serviço de busca semântica (`services/search.ts`)

**Descrição:** Implementar `embedQuery` (Azure OpenAI embeddings) e
`searchTopChunks` (Azure AI Search, top-5), com retry exponencial para
chamadas Azure.

**Critérios de aceite:**
- Retry configurável, máx. 3 tentativas com backoff exponencial; erros de
  upstream mapeados para `UpstreamServiceError` (QE-01) após esgotar
  tentativas.
- `searchTopChunks` retorna no máximo 5 chunks, cada um com `content`,
  `sourceDocument`, `section` e `score`.
- Testes unitários com mock do cliente Azure cobrindo: sucesso na 1ª
  tentativa, sucesso após retry, falha definitiva após 3 tentativas.

**Dependências:** QE-01.
**Estimativa:** M

---

## QE-03 — Montagem do prompt com context budget (`services/prompt-builder.ts`)

**Descrição:** Montar o prompt final combinando system prompt
(`/prompts/system-prompt.md`) + chunks recuperados + pergunta, respeitando o
orçamento da ADR-0002 (~4K tokens system + ~8K tokens chunks).

**Critérios de aceite:**
- Função pura `buildPrompt(systemPrompt, chunks, question, history)`.
- Se os chunks excederem o orçamento de ~8K tokens, descarta os de menor
  `score` e **loga o descarte** (nunca trunca silenciosamente).
- Testes cobrem: 1 chunk, 5 chunks dentro do orçamento, chunks que excedem o
  orçamento (verifica que o excedente é descartado e logado, não cortado no
  meio do texto).

**Dependências:** QE-01, QE-02 (formato do chunk).
**Estimativa:** M

---

## QE-04 — Serviço de completion (`services/completion.ts`)

**Descrição:** Chamar o GPT-4o via Azure OpenAI com o prompt montado, com
retry exponencial e timeout configurável.

**Critérios de aceite:**
- Assinatura tipada retornando `{ answer: string, usage: {...} }`.
- Erros de upstream (timeout, 429, 5xx) mapeados para `UpstreamServiceError`
  após esgotar tentativas.
- Testes com mock cobrindo sucesso, sucesso após retry, falha definitiva.

**Dependências:** QE-01, QE-03.
**Estimativa:** M

---

## QE-05 — Validação determinística de guardrails da resposta (`services/response-validator.ts`)

**Descrição:** Antes de devolver a resposta ao atendente, validar de forma
determinística (código, não apenas prompt) que ela cita fonte e não contém
valores numéricos (prazos, multiplicadores, SLAs) ausentes dos chunks
recuperados.

**Critérios de aceite:**
- Função pura `validateResponse(answer, chunks)` retorna resultado aprovado
  ou motivo de bloqueio/aviso de baixa confiança.
- Cobre os 3 incidentes simulados do cenário: (1) prazo/valor numérico
  inventado fora dos chunks, (2) citação de versão desatualizada quando existe
  versão vigente mais recente, (3) falso "não encontrei" quando o chunk
  relevante foi de fato recuperado.
- Testes unitários — um caso por incidente, todos com regressão coberta.

**Dependências:** QE-01.
**Estimativa:** M

---

## QE-06 — Orquestração completa no handler (`functions/query/response-builder.ts` + `handler.ts`)

**Descrição:** Substituir o placeholder de QE-01 pelo fluxo real:
`validator → search → prompt-builder → completion → response-validator →
response-builder`, sempre retornando `source_document`.

**Critérios de aceite:**
- Fluxo ponta a ponta com todos os serviços mockados em teste de integração.
- Nenhuma resposta de sucesso sai sem `source_document` preenchido.
- Falha em qualquer estágio é mapeada para o status HTTP correto (400 input
  inválido, 502/503 falha de upstream, 500 erro inesperado).
- Bloqueio do `response-validator` (QE-05) retorna resposta com aviso de
  baixa confiança + sugestão de escalação (guardrail "quando em dúvida").

**Dependências:** QE-01, QE-02, QE-03, QE-04, QE-05.
**Estimativa:** G

---

## QE-07 — Testes de integração e cobertura do endpoint

**Descrição:** Suite de testes de integração cobrindo os cenários felizes e
de borda do `/api/query`, com todos os serviços externos mockados (`msw` ou
mocks manuais), garantindo a cobertura mínima definida em
`vitest.config.ts` (80% linhas).

**Critérios de aceite:**
- `npm test` passa.
- Cobertura de `src/functions/query` e `src/services` ≥ 80% linhas.
- Inclui teste de regressão para os 3 incidentes simulados (ligados a QE-05).

**Dependências:** QE-06.
**Estimativa:** M

---

## Dependency graph

```
QE-01 ─┬─> QE-02 ─┬─> QE-03 ─> QE-04 ─┐
       ├─> QE-05 ─┘                   ├─> QE-06 ─> QE-07
       └───────────────────────────────┘
```
