# Dev Ex. 3.2 — Revisão crítica: feedback-handler.ts (Copilot)

## Revisão 1

1. **`body = await request.json() as any` sem Zod** — *violação do AGENTS.md*. O cast `any` desativa qualquer checagem de tipo; qualquer payload (campos faltando, tipos errados, `rating: "cinco"`) passa direto para o Cosmos.
2. **`console.log('Feedback recebido:', ...)`** — *violação do AGENTS.md*. Projeto exige pino; `console.log` não tem nível, não é estruturado, não respeita `LOG_LEVEL`.
3. **`const { CosmosClient } = require('@azure/cosmos')` dentro da função** — *violação do AGENTS.md*. Import dinâmico onde o padrão exige imports estáticos no topo. Sem ganho nenhum aqui (não é lazy-load condicional, roda em toda invocação).
4. **`attendantEmail` dentro do objeto logado em `console.log`** — *violação do AGENTS.md* + *problema de segurança*. E-mail é dado pessoal; vai parar em log (Application Insights / stdout), fora do controle de acesso do Cosmos.
5. **`new CosmosClient(...)` instanciado dentro do handler, a cada invocação** — *bug potencial*. Azure Functions reaproveita o processo entre chamadas; recriar o client a cada request esgota conexões/sockets do Cosmos sob carga.
6. **Nenhum `try/catch`** — *bug potencial*. Erro de parse do JSON, campo ausente ou falha do Cosmos sobe como exceção não tratada; runtime devolve 500 genérico sem corpo controlado, sem log de causa.
7. **Nenhuma validação de conteúdo antes de persistir** — *bug potencial*, consequência direta do item 1. `rating` fora de 1–5, `comment` sem limite de tamanho, `queryId`/`attendantEmail` ausentes ou mal formados: tudo é gravado no Cosmos exatamente como veio.

## Revisão 2 (segunda passada)

1. **`app.http` sem `authLevel`** — *problema de segurança*. A doc do SDK (`@azure/functions`, `http.d.ts`) confirma: `authLevel` não especificado default para `'anonymous'`. O endpoint fica público sem function key, e é o mesmo endpoint que recebe e (no original) loga `attendantEmail`.
2. **Resposta de sucesso é string crua (`body: 'OK'`), não JSON** — *bug potencial*. Inconsistente com o resto da API (que responde `jsonBody`); consumidor que espera `{ status: ... }` quebra ao tentar parsear.
3. **Função recebe só `request`, ignora `context: InvocationContext`** — *bug potencial* (observabilidade). Mesmo que o logging fosse trocado para pino, não há como correlacionar logs de uma mesma invocação sem o `invocationId` — o parâmetro nem é capturado.
4. Não achei nada além do que a Revisão 1 já cobriu em: ausência de Zod, `console.log`, `require` dinâmico e log de `attendantEmail` — confirmo esses quatro, sem alterações.

## Comparação

- **Concordância:** as duas passadas convergem no diagnóstico raiz — zero validação de entrada — e nenhuma passada encontrou falso positivo na outra.
- **Só a Revisão 1 encontrou:** client Cosmos recriado por invocação (item 5) e ausência de `try/catch` (item 6) — são problemas de runtime/estrutura, não de payload.
- **Só a Revisão 2 encontrou:** `authLevel` ausente (default anonymous), resposta não-JSON, e falta de `context`/`invocationId` para correlação de log — nenhum desses aparece só de ler o corpo da função superficialmente; exigiram checar o comportamento default do SDK e comparar o contrato de resposta com o resto da API.
- **Falso positivo:** nenhum. Todos os itens das duas listas se sustentam ao reler o código original.

## Verificação da versão final

Cada item foi conferido contra `src/functions/feedback/handler.ts` + `validator.ts` (versão reescrita):

| # | Problema | Resolvido? | Onde |
|---|---|---|---|
| 1 | `any` sem Zod | Sim | `parseFeedbackRequest` + `FeedbackRequestSchema.safeParse` em `validator.ts` |
| 2 | `console.log` | Sim | `logger.child(...)` (pino) — `log.info` / `log.warn` / `log.error` |
| 3 | `require` dinâmico | Sim | `import { CosmosClient } from "@azure/cosmos"` no topo |
| 4 | `attendantEmail` logado | Sim | `log.info` só recebe `{ queryId, rating }`; comentário explícito no código proíbe logar `attendantEmail`/`comment` |
| 5 | Client recriado por invocação | Sim | `cosmosClient`/`feedbackContainer` movidos para escopo de módulo, fora do handler |
| 6 | Sem `try/catch` | Sim | `try/catch` com branch `isAppError` (400 estruturado) e fallback (500 estruturado) |
| 7 | Sem validação de conteúdo | Sim | `rating: z.number().int().min(1).max(5)`, `comment: z.string().max(2000)`, `attendantEmail: z.string().email()` |
| 8 | `authLevel` ausente (anonymous) | Sim | `authLevel: "function"` explícito em `app.http` |
| 9 | Resposta não-JSON | Sim | `jsonBody: { status: "ok" }` (e `jsonBody` também nos dois ramos de erro) |
| 10 | Sem `invocationId` para correlação | Sim | `context: InvocationContext` recebido; `logger.child({ invocationId: context.invocationId })` |

Todos os 10 itens levantados nas duas passadas estão resolvidos na versão final. Não há problema pendente para apontar.

Ponto de atenção que não chega a ser um problema em aberto, mas vale registrar: `FeedbackRequestSchema` não usa `.strict()` (diferente de `StructuredModelOutputSchema` em `types.ts`, que usa `.strict()` de propósito). Não é um bug — o comportamento default do Zod já descarta chaves não reconhecidas do `result.data`, então nenhum campo extra do payload chega a ser persistido no Cosmos —, mas é uma inconsistência de estilo entre os dois schemas do mesmo projeto.
