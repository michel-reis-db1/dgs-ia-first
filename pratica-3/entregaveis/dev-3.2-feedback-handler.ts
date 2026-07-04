// HTTP trigger do feedback endpoint.
// Padrões (ver AGENTS.md): Azure Functions v4, Zod, pino, sem console.log,
// imports estáticos, nunca logar dados pessoais (e-mail, nome).
// Reescrito na revisão crítica do cenário 3 (Dev Ex. 3.2) — ver
// docs/revisao-critica/dev-3.2-feedback-handler.md para o antes/depois.

import { app, type HttpRequest, type HttpResponseInit, type InvocationContext } from "@azure/functions";
import { CosmosClient } from "@azure/cosmos";
import { parseFeedbackRequest } from "./validator.js";
import { isAppError } from "../../shared/errors.js";
import { logger } from "../../shared/logger.js";
import { config } from "../../shared/config.js";

// Client criado uma vez no escopo do módulo — Azure Functions reaproveita o
// processo entre invocações; recriar o client a cada request (como no
// código original do Copilot) esgota conexões do Cosmos sob carga.
const cosmosClient = new CosmosClient(config.cosmos.connectionString);
const feedbackContainer = cosmosClient.database("novatech").container("feedbacks");

export async function feedbackHandler(request: HttpRequest, context: InvocationContext): Promise<HttpResponseInit> {
  const log = logger.child({ invocationId: context.invocationId });

  try {
    const body = await request.json();
    const parsed = parseFeedbackRequest(body);

    const record = {
      ...parsed,
      timestamp: new Date().toISOString(),
    };

    // Nunca logar attendantEmail/comment (dados pessoais) — só identificadores não sensíveis.
    log.info({ queryId: record.queryId, rating: record.rating }, "feedback recebido");

    await feedbackContainer.items.create(record);

    return { status: 200, jsonBody: { status: "ok" } };
  } catch (error) {
    if (isAppError(error)) {
      log.warn({ code: error.code, err: error }, "feedback rejeitado");
      return {
        status: error.statusCode,
        jsonBody: {
          code: error.code,
          message: error.message,
          details: "details" in error ? error.details : undefined,
        },
      };
    }

    log.error({ err: error }, "erro inesperado no /api/feedback");
    return {
      status: 500,
      jsonBody: { code: "INTERNAL_ERROR", message: "Erro interno inesperado." },
    };
  }
}

app.http("feedback", {
  methods: ["POST"],
  authLevel: "function",
  route: "feedback",
  handler: feedbackHandler,
});
