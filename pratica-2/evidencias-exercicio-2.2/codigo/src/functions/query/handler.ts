// HTTP trigger do query endpoint.
// Padrões (ver AGENTS.md): Azure Functions v4, Zod, pino, sem console.log.
//
// Escopo desta task (QE-01, ver specs/query-endpoint/tasks.md): setup do
// endpoint com validação de input. Busca semântica, prompt-builder,
// completion e guardrails determinísticos entram nas tasks QE-02..QE-06 —
// a resposta de sucesso abaixo é um placeholder explícito.

import { app, type HttpRequest, type HttpResponseInit, type InvocationContext } from "@azure/functions";
import { parseQueryRequest } from "./validator.js";
import { isAppError } from "../../shared/errors.js";
import { logger } from "../../shared/logger.js";
import type { QueryResponse } from "../../shared/types.js";

export async function queryHandler(request: HttpRequest, context: InvocationContext): Promise<HttpResponseInit> {
  const log = logger.child({ invocationId: context.invocationId });

  try {
    const body = await request.json();
    const parsed = parseQueryRequest(body);

    log.info({ questionLength: parsed.question.length }, "query recebida");

    const response: QueryResponse = {
      answer: "TODO: pipeline de busca e completion ainda não implementado (ver QE-02..QE-06).",
      source_document: { documentId: "PENDING" },
      confidence: "low",
    };

    return { status: 200, jsonBody: response };
  } catch (error) {
    if (isAppError(error)) {
      log.warn({ code: error.code, err: error }, "requisição rejeitada");
      return {
        status: error.statusCode,
        jsonBody: {
          code: error.code,
          message: error.message,
          details: "details" in error ? error.details : undefined,
        },
      };
    }

    log.error({ err: error }, "erro inesperado no /api/query");
    return {
      status: 500,
      jsonBody: { code: "INTERNAL_ERROR", message: "Erro interno inesperado." },
    };
  }
}

app.http("query", {
  methods: ["POST"],
  authLevel: "function",
  route: "query",
  handler: queryHandler,
});
