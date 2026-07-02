### Risco 1 — Exposição de segredos por escopo de filesystem amplo demais

**Descrição:** Se o `filesystem` server receber `"."` (raiz do repositório) como argumento, o agente terá acesso a arquivos como `.env`, `infra/parameters/dev.bicepparam` (que pode conter connection strings) e `.github/workflows/` (que pode conter secrets referenciados). Um agente comprometido ou mal-instruído pode vazar esses valores em logs ou respostas.

**Configuração vulnerável:**
```json
"filesystem": {
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]
}
```

**Mitigação aplicada nesta configuração:**
- O `filesystem` recebe apenas `./src ./specs ./skills ./prompts ./docs/adr` — `infra/` e `.env` ficam fora do escopo.
- Adicionar `.env` ao `.gitignore` e nunca incluir credenciais em arquivos de código.
- Não incluir `./infra/parameters/` no escopo do filesystem — parâmetros de ambiente contêm connection strings.

### Risco 2 — Escrita sem gate de revisão humana

**Descrição:** O `filesystem` server com permissão de escrita permite que o agente modifique arquivos de código (`./src/**`) sem aprovação humana. Em um fluxo AI-first sem validation gate intermediário, o agente pode sobrescrever lógica crítica (ex: `response-validator.ts`) com código que remove guardrails determinísticos.

**Exemplo concreto:** um agente instruído a "otimizar o handler" pode remover a verificação de `source_document` no `response-builder.ts`, violando o guardrail de citação de fonte — e isso só seria detectado em code review (Gate 3, segundo os validation gates do projeto).

**Mitigação:**
1. **Gate 2 (Tasks → Implement):** nenhuma task é executada pelo agente sem aprovação do Tech Lead — o agente não deve ter acesso de escrita a `src/` antes da task ser aprovada.
2. Separar o escopo de escrita do de leitura no AGENTS.md: documentar que o agente usa `filesystem` apenas para leitura de referência durante planejamento; escrita de código via Copilot acontece com o dev no loop.
3. Revisão obrigatória de diff antes de qualquer `write_file` — no Claude Code, isso é feito pela confirmação de permissão antes de edições.