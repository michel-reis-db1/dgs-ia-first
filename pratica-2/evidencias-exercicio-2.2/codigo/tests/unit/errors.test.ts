import { describe, expect, it } from "vitest";
import { UpstreamServiceError, ValidationError, isAppError } from "../../src/shared/errors.js";

describe("errors", () => {
  it("ValidationError carrega statusCode 400 e os detalhes por campo", () => {
    const error = new ValidationError("payload inválido", [{ field: "question", message: "obrigatório" }]);

    expect(error.statusCode).toBe(400);
    expect(error.code).toBe("VALIDATION_ERROR");
    expect(error.details).toEqual([{ field: "question", message: "obrigatório" }]);
    expect(isAppError(error)).toBe(true);
  });

  it("UpstreamServiceError carrega statusCode 502 e o nome do serviço", () => {
    const cause = new Error("timeout");
    const error = new UpstreamServiceError("azure-ai-search", "busca falhou", cause);

    expect(error.statusCode).toBe(502);
    expect(error.code).toBe("UPSTREAM_SERVICE_ERROR");
    expect(error.service).toBe("azure-ai-search");
    expect(error.cause).toBe(cause);
  });

  it("isAppError retorna false para erros genéricos", () => {
    expect(isAppError(new Error("genérico"))).toBe(false);
    expect(isAppError("não é nem um Error")).toBe(false);
  });
});
