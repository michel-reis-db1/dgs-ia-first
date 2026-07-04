# Dev Ex. 3.1 — Entregável 1: Schema Zod do structured output

Código: `pratica-3/novatech-assistant/src/shared/types.ts`.

```ts
export const StructuredModelOutputSchema = z
  .object({
    answer: z.string().min(1),
    source_document: z.string().min(1),
    confidence_score: z.number().min(0).max(1),
  })
  .strict();
export type StructuredModelOutput = z.infer<typeof StructuredModelOutputSchema>;
```

## Decisões de projeto

- `source_document` é `string` (o identificador curto do documento — `POL-001`, `SLA-2024` — igual ao que o Tech Lead usa no Ex. 3.1 dele para checar contra a lista de documentos válidos), não o objeto `{ documentId, section }` do `QueryResponseSchema` já existente no projeto. São dois contratos diferentes: este é o output bruto do modelo antes do harness; o outro é a resposta final do endpoint.
- `confidence_score` é `number` entre 0 e 1, não o enum categórico (`"high"/"low"`) já usado em `QueryResponseSchema`. O enunciado nomeia o campo como "score", o que sugere um valor contínuo — isso é uma decisão que merece registro no `prompt-changelog.md` do projeto real, porque cria dois vocabulários de confiança coexistindo (`confidence` categórico no endpoint, `confidence_score` numérico no output bruto do modelo). Ambíguo o suficiente para gerar confusão entre times se não for documentado.
- `.strict()` — rejeita campos extras que o modelo eventualmente inclua fora do contrato (ver achado #1 em `dev-3.1-code-review.md`).
