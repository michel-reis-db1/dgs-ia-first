import { QueryRequestSchema, type QueryRequest } from "../../shared/types.js";
import { ValidationError, type FieldDetail } from "../../shared/errors.js";

export function parseQueryRequest(body: unknown): QueryRequest {
  const result = QueryRequestSchema.safeParse(body);
  if (!result.success) {
    const details: FieldDetail[] = result.error.issues.map((issue) => ({
      field: issue.path.join(".") || "(root)",
      message: issue.message,
    }));
    throw new ValidationError("Payload de /api/query inválido", details);
  }
  return result.data;
}
