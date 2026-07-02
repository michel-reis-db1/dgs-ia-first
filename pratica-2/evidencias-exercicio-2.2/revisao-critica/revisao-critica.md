# Revisão crítica — QE-01 (setup do endpoint com validação de input)

> Código gerado com apoio do Copilot/Claude Code para a task **QE-01** de
> `specs/query-endpoint/tasks.md`. Esta revisão foi feita rodando de verdade
> `npx vitest run` e `npx tsc -p . --noEmit` sobre o código entregue — os dois
> primeiros achados abaixo foram **reproduzidos**, não apenas inferidos por
> leitura.

Arquivos revisados: `src/shared/config.ts`, `src/shared/logger.ts`,
`src/shared/errors.ts`, `src/shared/types.ts`,
`src/functions/query/validator.ts`, `src/functions/query/handler.ts`.

---

## Achado 1 — `config.ts` valida o ambiente no *top level* do módulo (acoplamento de teste)

**Onde:** `src/shared/config.ts`, última linha:
```ts
export const config = loadConfig(process.env);
```

**Problema:** qualquer módulo que importe `config.ts` — direta ou
transitivamente — dispara o `parse` do Zod e, se faltar uma variável, um
`throw` **na avaliação do import**, antes de qualquer teste rodar. Isso
significa que `logger.ts` (que importa `config` só para ler `logLevel`) e,
por consequência, `handler.ts`, arrastam essa dependência de ambiente para
qualquer teste que só queira exercitar a validação HTTP — sem nenhuma
chamada real a Azure OpenAI/Search.

**Reproduzido:** rodando `npx vitest run tests/unit/config.test.ts` com um
`import` estático no topo do arquivo de teste, a suíte falhava **antes de
qualquer `it` executar**:
```
Error: Configuração inválida — variáveis de ambiente ausentes/inválidas:
AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_CHAT_DEPLOYMENT, ...
 ❯ loadConfig src/shared/config.ts:35:11
```
O contorno usado nos testes entregues (`tests/unit/config.test.ts` e
`tests/integration/query-handler.test.ts`) foi popular `process.env` dentro
de `beforeAll` e só então fazer `import()` dinâmico do módulo. Funciona, mas
é sintoma do problema: um teste que testa *lógica de validação de request
HTTP* não deveria precisar simular 7 variáveis de segredo Azure.

**Ajuste proposto:** trocar o singleton eager por um lazy singleton
(`getConfig()` com cache no primeiro acesso, chamado só onde a config é
realmente usada) ou por injeção explícita de config nos serviços que
precisam dela (search/completion), mantendo `handler.ts`/`validator.ts` sem
essa dependência transitiva. `loadConfig` (a função pura) já está correta e
testável — o problema é só a linha de execução eager no módulo.

**Severidade:** Média — não quebra produção (o Function App real sempre tem
as env vars configuradas), mas degrada a testabilidade e vai se agravar
conforme mais módulos importarem `logger`/`config`.

---

## Achado 2 — corpo JSON malformado cai no branch de erro 500, não 400

**Onde:** `src/functions/query/handler.ts`, bloco `try/catch`:
```ts
const body = await request.json();      // pode lançar SyntaxError
const parsed = parseQueryRequest(body);
...
} catch (error) {
  if (isAppError(error)) { ... }         // SyntaxError não é AppError
  ...
  return { status: 500, ... };           // cai aqui
}
```

**Problema:** o critério de aceite da QE-01 é explícito — "body inválido
retorna 400". Um body com JSON sintaticamente quebrado (por exemplo, um
integrador do painel web ou do bot do Teams enviando um payload truncado) é
claramente um erro do cliente, não uma falha interna do servidor. Como
`request.json()` lança antes de chegar em `parseQueryRequest`, o erro nunca
vira `ValidationError` e o handler responde 500 — o que é semanticamente
errado (o cliente vai tratar como "tente de novo mais tarde" quando deveria
corrigir o payload) e também polui os logs de erro 500 com algo que não é
um bug do sistema.

**Reproduzido:** o teste de integração `retorna 500 sem vazar stack trace
para erro inesperado` (`tests/integration/query-handler.test.ts`) usa
exatamente esse cenário (falha dentro de `request.json()`) para validar que
não há vazamento de stack trace — e confirma que a resposta é 500, não 400.

**Ajuste proposto:** envolver especificamente a chamada a `request.json()`
em seu próprio `try/catch` e converter qualquer falha de parsing em
`ValidationError("Corpo da requisição não é um JSON válido")` antes de
seguir para `parseQueryRequest`.

**Severidade:** Média-alta — é uma violação direta de um critério de aceite
já escrito na spec, não uma melhoria hipotética.

---

## Achado 3 — "3 turnos" (ADR-0002) implementado como "3 mensagens"

**Onde:** `src/shared/types.ts`:
```ts
conversationHistory: z.array(ChatMessageSchema).max(3, "...")
```

**Problema:** a ADR-0002 (citada em `plan.md`) fala em histórico limitado a
"3 turnos" de conversa. Se um turno é o par pergunta+resposta (o padrão mais
comum em chat), o limite deveria ser de **6 mensagens** (3 pares
`user`+`assistant`), não 3 mensagens soltas. Como o schema atual conta
mensagens e não turnos, o atendente perde metade do histórico esperado (1,5
turno em vez de 3) — de forma **silenciosa**: não é erro, só corta a
janela de contexto pela metade sem avisar ninguém.

**Reproduzido:** `tests/unit/validator.test.ts` — "rejeita histórico com mais
de 3 entradas" usa 4 mensagens (2 turnos completos) como caso inválido, o
que só está correto se a intenção real for "3 mensagens". Ou seja: o próprio
teste que valida o comportamento atual é evidência de que a interpretação
precisa ser confirmada com quem escreveu a ADR-0002, porque hoje o código
formaliza uma leitura que pode não ser a pretendida.

**Ajuste proposto:** confirmar com Tech Lead/Product Specialist o que conta
como "turno". Se for par pergunta+resposta, mudar o schema para modelar o
histórico como uma lista de pares (`{ question, answer }`) com `.max(3)` —
isso remove a ambiguidade estruturalmente, em vez de depender de um
comentário. Se a intenção sempre foi "3 mensagens", basta documentar isso
explicitamente no schema para não reabrir a dúvida no próximo code review.

**Severidade:** Baixa-média — não quebra nada tecnicamente, mas é uma
divergência silenciosa entre a spec (ADR-0002) e o código, do tipo que só
aparece quando um atendente reclama que "o assistente esqueceu o que eu
perguntei há 2 mensagens".

---

## O que **não** foi considerado problema

- Uso de classes (`AppError`/subclasses) em vez de union types para erros —
  estilo aceitável dado que `instanceof` é usado de forma consistente
  (`isAppError`) e o projeto já assume TypeScript com classes em outros
  pontos do Anexo C.
- `authLevel: "function"` no registro do endpoint — não é um bug, mas fica
  em aberto até o plan.md ou uma ADR definirem o modelo de autenticação
  entre bot do Teams / painel web e a Function App; não há critério de
  aceite da QE-01 sobre isso.
