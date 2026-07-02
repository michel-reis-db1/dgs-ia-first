# SKILL.md — TypeScript Conventions (Foundation)

## Quando esta skill se aplica

Ativação: **sempre que um arquivo `.ts` ou `.tsx` for criado ou editado
neste repositório** — endpoint, serviço, componente React, teste, script de
infraestrutura. Esta é a skill Foundation com o escopo mais amplo do
projeto: as skills Domain (`azure-functions-endpoint`, `testing-patterns`,
`react-components`, `azure-ai-search-integration`) e Artifact
(`create-rag-endpoint`, `create-integration-test`, `create-react-card`)
assumem que quem as lê já segue estas regras. Leia esta skill **antes** de
qualquer uma das outras.

## Contexto

O projeto roda em `strict: true` (ver `tsconfig.json`) porque o assistente
lida com dados de logística (prazos, valores de frete, classificação de
carga perigosa) onde um `undefined` não tratado ou um `any` disfarçado é a
diferença entre "não encontrei a informação" (aceitável) e um valor
inventado (guardrail violado — ver ADR-0003 e Product Rules & Guardrails).
Código gerado por IA sem esta skill tende a "escapar" do strict mode com
`any`, cast forçado (`as`) e tipos duplicados manualmente — cada um desses
hábitos reintroduz o risco que o `strict: true` existe para eliminar.

## Regras prescritivas

1. **DEVE** usar `strict: true` como está — nunca adicionar `// @ts-ignore`,
   `// @ts-expect-error` sem justificativa em comentário, nem `as any` para
   silenciar um erro de tipo. Se o tipo está errado, o modelo de dados está
   errado — corrija o tipo, não a checagem.
2. **DEVE** derivar tipos de schemas Zod com `z.infer<typeof Schema>` sempre
   que o dado cruza uma fronteira externa (request HTTP, resposta de
   serviço, config de ambiente). **NÃO DEVE** escrever uma `interface`/`type`
   manual em paralelo a um schema Zod que já existe para o mesmo dado —
   isso cria duas fontes de verdade que divergem silenciosamente.
3. **DEVE** usar imports ESM relativos com extensão `.js` (`import { config }
   from "./config.js"`) — o projeto roda com `"module": "ESNext"` +
   `"moduleResolution": "Bundler"`, e o `.js` no import de um arquivo `.ts` é
   o padrão correto neste setup, não um erro de digitação.
4. **DEVE** respeitar os limites de módulo do Anexo C: código em
   `src/functions/*` (camada HTTP) não importa diretamente de
   `src/pipeline/*` (camada de ingestão) — se um endpoint precisa de algo do
   pipeline, o acesso passa por `src/services/*`. Import cruzando camadas
   sem passar por `services` é sinal de responsabilidade no lugar errado.
5. **DEVE** nomear: `camelCase` para variáveis/funções, `PascalCase` para
   tipos/classes/componentes React, `SCREAMING_SNAKE_CASE` só para variáveis
   de ambiente (nunca para constantes de código). Arquivos: `kebab-case.ts`
   (exceção: componentes React, `PascalCase.tsx`, ex. `App.tsx`).
6. **NÃO DEVE** usar `console.log`/`console.error`/`console.warn` em nenhum
   lugar de `src/` — logging é responsabilidade da skill `error-handling`
   (pino, via `shared/logger.ts`). Um `console.log` esquecido em produção não
   aparece em nenhum pipeline de observabilidade da NovaTech.
7. **NÃO DEVE** usar `export default` fora de `src/web/` (React). No backend
   (Functions, services, pipeline), todo módulo usa **named exports** — torna
   refatoração e busca por uso (`grep`) confiáveis; `export default` permite
   qualquer nome no import, o que já causou inconsistência de nomenclatura
   em outros projetos TS da DB1.
8. **DEVE** marcar como `readonly` todo campo de classe que não muda depois
   do construtor (ver padrão de `AppError` em `error-handling.md`) — força o
   compilador a pegar mutação acidental de estado que deveria ser imutável.

## Exemplos

### DO — tipo derivado de schema Zod (fonte única de verdade)

```typescript
import { z } from "zod";

export const QueryRequestSchema = z.object({
  question: z.string().min(1, "question não pode ser vazia"),
  conversationHistory: z
    .array(ChatMessageSchema)
    .max(3, "conversationHistory aceita no máximo 3 turnos")
    .optional(),
});

// O tipo vem do schema — se o schema mudar, o tipo acompanha automaticamente.
export type QueryRequest = z.infer<typeof QueryRequestSchema>;
```

### DON'T — tipo manual duplicado, torto de divergir do schema

```typescript
// Duas fontes de verdade: se alguém adicionar um campo ao schema Zod e
// esquecer esta interface (ou vice-versa), o TypeScript não avisa —
// o schema valida um formato, o tipo promete outro.
export interface QueryRequest {
  question: string;
  conversationHistory?: { role: string; content: string }[];
}

const QueryRequestSchema = z.object({
  question: z.string().min(1),
  conversationHistory: z.array(ChatMessageSchema).max(3).optional(),
});
```

### DO — erro tipado, mapeável sem inspecionar string de mensagem

```typescript
export abstract class AppError extends Error {
  abstract readonly statusCode: number;
  abstract readonly code: string;

  constructor(message: string, readonly cause?: unknown) {
    super(message);
    this.name = new.target.name;
  }
}

export class ValidationError extends AppError {
  readonly statusCode = 400;
  readonly code = "VALIDATION_ERROR";
}
```

### DON'T — `any` e `as` para calar o compilador

```typescript
function handleError(error: any) {
  // "any" aqui apaga toda a checagem de tipo do resto da função — o
  // compilador não consegue mais avisar se `error.statusCode` não existir.
  const statusCode = (error as any).statusCode ?? 500;
  return { status: statusCode, body: error.message };
}
```

### DO — import relativo com `.js`, limite de módulo respeitado

```typescript
// src/functions/query/handler.ts
import { logger } from "../../shared/logger.js";
import { searchTopChunks } from "../../services/search.js"; // passa por services, não por pipeline direto
```

### DON'T — import cruzando camada sem passar por `services`

```typescript
// src/functions/query/handler.ts
import { chunkDocument } from "../../pipeline/chunker.js"; // endpoint HTTP não deveria conhecer o pipeline de ingestão
```

## Anti-padrões comuns (o que o Copilot gera sem esta skill)

- **`any` "temporário" que nunca é removido** — Copilot usa `any` para
  destravar rapidamente um erro de tipo e o time humano raramente volta para
  corrigir depois do PR aprovado.
- **Tipo manual ao lado do schema Zod** — muito comum quando o Copilot
  autocompleta uma `interface` por padrão de treinamento, mesmo com um
  schema Zod visível duas linhas acima no mesmo arquivo.
- **`console.log` de debug deixado no código** — aparece sobretudo em
  branches de erro (`catch`) "só para ver o que aconteceu", e sobrevive ao
  code review porque não quebra teste nenhum.
- **`export default` em serviço/handler do backend** — Copilot tende a usar
  `export default` como padrão geral de JS/TS, ignorando que o resto do
  backend deste projeto usa named exports.
- **Import direto do módulo mais "conveniente"** — quando o Copilot precisa
  de uma função de outra camada (ex. pipeline dentro de um handler), ele
  importa do arquivo onde a função está fisicamente, sem considerar o limite
  de camada do Anexo C, porque essa regra não está no código-fonte, só na
  convenção do time.

## Dependências

Nenhuma — esta é a skill base do projeto. É pré-requisito de leitura para:
`error-handling.md`, `project-structure.md` (Foundation), e para todas as
skills Domain e Artifact que geram código TypeScript/TSX.
