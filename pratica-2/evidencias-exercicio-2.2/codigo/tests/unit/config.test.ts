import { beforeAll, describe, expect, it } from "vitest";

// NOTE (ver revisão crítica — achado #1): `config.ts` executa
// `loadConfig(process.env)` no top level do módulo (linha 56). Isso obriga
// até este teste, que só quer exercitar `loadConfig` como função pura, a
// garantir um `process.env` "válido" ambiente ANTES do primeiro import do
// módulo — daí o `import()` dinâmico dentro de `beforeAll` em vez de um
// `import` estático no topo do arquivo. Um `import` estático aqui falha o
// arquivo inteiro de teste na coleta, antes mesmo de qualquer `it` rodar
// (reproduzido durante a revisão: ver `npx vitest run tests/unit/config.test.ts`
// antes deste ajuste).
let loadConfig: typeof import("../../src/shared/config.js")["loadConfig"];

const validEnv = {
  AZURE_OPENAI_ENDPOINT: "https://novatech-oai.openai.azure.com",
  AZURE_OPENAI_API_KEY: "test-key",
  AZURE_OPENAI_CHAT_DEPLOYMENT: "gpt-4o",
  AZURE_OPENAI_EMBEDDING_DEPLOYMENT: "text-embedding-3-large",
  AZURE_SEARCH_ENDPOINT: "https://novatech-search.search.windows.net",
  AZURE_SEARCH_API_KEY: "test-key",
  AZURE_SEARCH_INDEX_NAME: "novatech-docs",
};

beforeAll(async () => {
  Object.assign(process.env, validEnv);
  ({ loadConfig } = await import("../../src/shared/config.js"));
});

describe("loadConfig", () => {
  it("carrega e mapeia variáveis de ambiente válidas", () => {
    const config = loadConfig(validEnv);

    expect(config.azureOpenAi.chatDeployment).toBe("gpt-4o");
    expect(config.azureSearch.indexName).toBe("novatech-docs");
    expect(config.logLevel).toBe("info");
  });

  it("lança erro na inicialização quando falta uma variável obrigatória", () => {
    const { AZURE_OPENAI_API_KEY, ...incompleteEnv } = validEnv;

    expect(() => loadConfig(incompleteEnv)).toThrowError(/AZURE_OPENAI_API_KEY/);
  });

  it("rejeita LOG_LEVEL fora do enum esperado", () => {
    expect(() => loadConfig({ ...validEnv, LOG_LEVEL: "verbose" })).toThrowError(/LOG_LEVEL/);
  });
});
