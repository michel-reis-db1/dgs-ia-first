import { describe, expect, it } from "vitest";
import { parseQueryRequest } from "../../src/functions/query/validator.js";
import { ValidationError } from "../../src/shared/errors.js";

describe("parseQueryRequest", () => {
  it("aceita um payload válido sem histórico", () => {
    const parsed = parseQueryRequest({ question: "Qual o SLA do cliente Gold?" });

    expect(parsed.question).toBe("Qual o SLA do cliente Gold?");
    expect(parsed.conversationHistory).toBeUndefined();
  });

  it("aceita um payload válido com histórico dentro do limite", () => {
    const parsed = parseQueryRequest({
      question: "E para carga perigosa?",
      conversationHistory: [
        { role: "user", content: "Qual o prazo de devolução padrão?" },
        { role: "assistant", content: "7 dias corridos, conforme POL-001." },
      ],
    });

    expect(parsed.conversationHistory).toHaveLength(2);
  });

  it("rejeita payload sem a pergunta", () => {
    expect(() => parseQueryRequest({})).toThrow(ValidationError);
  });

  it("rejeita question vazia", () => {
    try {
      parseQueryRequest({ question: "" });
      expect.unreachable("deveria ter lançado ValidationError");
    } catch (error) {
      expect(error).toBeInstanceOf(ValidationError);
      expect((error as ValidationError).details).toEqual(
        expect.arrayContaining([expect.objectContaining({ field: "question" })]),
      );
    }
  });

  it("rejeita histórico com mais de 3 entradas", () => {
    expect(() =>
      parseQueryRequest({
        question: "pergunta de acompanhamento",
        conversationHistory: [
          { role: "user", content: "1" },
          { role: "assistant", content: "2" },
          { role: "user", content: "3" },
          { role: "assistant", content: "4" },
        ],
      }),
    ).toThrow(ValidationError);
  });
});
