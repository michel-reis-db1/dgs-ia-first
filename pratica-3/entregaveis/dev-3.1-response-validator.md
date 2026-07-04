# Dev Ex. 3.1 — Entregável 2: response-validator.ts (os 2 guardrails)

Código: `pratica-3/novatech-assistant/src/services/response-validator.ts`.
Testes: `pratica-3/novatech-assistant/tests/unit/response-validator.test.ts` (7 testes, todos verdes).
Schema usado: ver `dev-3.1-schema-zod.md`.

**Guardrail 1 (fonte obrigatória):** não é um `if` separado — é o próprio schema. `source_document: z.string().min(1)` já rejeita ausência ou string vazia no `safeParse`. Isso é intencional: a estrutura obrigatória *é* o guardrail 1, não algo adicional a ela.

**Guardrail 2 (carga perigosa + devolução):** roda depois do parse, sobre o campo já validado e tipado (`parsed.data.answer`, não o `raw` bruto):

```ts
const DANGEROUS_CARGO_PATTERN = /\bcargas?\s+perigosas?\b|\bclasses?\s+[1-6]\s+(da\s+)?antt\b/i;
const RETURN_PATTERN = /\bdevolu[çc][ãa]o\b|\bdevolv(er|ida|idas)\b/i;
const NEGATION_PATTERN = /\bn[ãa]o\b|\bimposs[ií]vel\b|\bvedad[ao]\b/i;
```

Em qualquer falha (schema ou guardrail 2), a função loga o motivo via `pino` (`logger.warn`) e retorna `SAFE_FALLBACK_RESPONSE` — nunca deixa a resposta seguir sem verificação, e nunca lança exceção para quem chama (o caller decide o que fazer com `{ ok: false, reason, fallback }`).

## Como isso conecta com o harness maior

- **Structured outputs** (camada Guardrails do framework de 5 camadas) = o schema (entregável 1).
- **Verification loop** = `validateModelOutput` sendo chamado antes de qualquer resposta chegar ao atendente.
- **HITL** = o ponto de escalação sugerido no risco residual do code review (`dev-3.1-code-review.md`) — não implementado neste módulo (é decisão de produto/orquestração), mas o `reason` retornado já dá o gancho para o caller decidir rotear para revisão humana em vez de só devolver o fallback genérico.
