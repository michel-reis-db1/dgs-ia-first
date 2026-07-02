import { beforeAll, describe, expect, it } from "vitest";
import type { HttpRequest, InvocationContext } from "@azure/functions";

// NOTE (ver revisão crítica — achado #1): `handler.ts` importa `logger.ts`,
// que importa `config.ts`. Como `config.ts` roda `loadConfig(process.env)`
// no top level, o `import()` precisa ser dinâmico e feito só depois de
// popular `process.env` — mesmo este teste não fazendo nenhuma chamada real
// a Azure OpenAI/Search.
let queryHandler: typeof import("../../src/functions/query/handler.js")["queryHandler"];

beforeAll(async () => {
  Object.assign(process.env, {
    AZURE_OPENAI_ENDPOINT: "https://novatech-oai.openai.azure.com",
    AZURE_OPENAI_API_KEY: "test-key",
    AZURE_OPENAI_CHAT_DEPLOYMENT: "gpt-4o",
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: "text-embedding-3-large",
    AZURE_SEARCH_ENDPOINT: "https://novatech-search.search.windows.net",
    AZURE_SEARCH_API_KEY: "test-key",
    AZURE_SEARCH_INDEX_NAME: "novatech-docs",
  });
  ({ queryHandler } = await import("../../src/functions/query/handler.js"));
});

function fakeRequest(body: unknown): HttpRequest {
  return { json: async () => body } as unknown as HttpRequest;
}

function fakeContext(): InvocationContext {
  return { invocationId: "test-invocation-id" } as unknown as InvocationContext;
}

describe("queryHandler", () => {
  it("retorna 200 com payload placeholder para input válido", async () => {
    const response = await queryHandler(fakeRequest({ question: "Qual o SLA do cliente Gold?" }), fakeContext());

    expect(response.status).toBe(200);
    expect(response.jsonBody).toMatchObject({
      source_document: { documentId: "PENDING" },
      confidence: "low",
    });
  });

  it("retorna 400 com detalhes por campo para input inválido", async () => {
    const response = await queryHandler(fakeRequest({}), fakeContext());

    expect(response.status).toBe(400);
    expect(response.jsonBody).toMatchObject({ code: "VALIDATION_ERROR" });
    expect((response.jsonBody as { details: unknown[] }).details.length).toBeGreaterThan(0);
  });

  it("retorna 500 sem vazar stack trace para erro inesperado", async () => {
    const brokenRequest = {
      json: async () => {
        throw new Error("falha de parsing simulada, não relacionada à validação");
      },
    } as unknown as HttpRequest;

    const response = await queryHandler(brokenRequest, fakeContext());

    expect(response.status).toBe(500);
    expect(JSON.stringify(response.jsonBody)).not.toContain("falha de parsing simulada");
  });
});
