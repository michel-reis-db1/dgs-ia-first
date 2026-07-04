import { FeedbackRequestSchema, type FeedbackRequest } from "../../shared/types.js";
import { ValidationError, type FieldDetail } from "../../shared/errors.js";

export function parseFeedbackRequest(body: unknown): FeedbackRequest {
  const result = FeedbackRequestSchema.safeParse(body);
  if (!result.success) {
    const details: FieldDetail[] = result.error.issues.map((issue) => ({
      field: issue.path.join(".") || "(root)",
      message: issue.message,
    }));
    throw new ValidationError("Payload de /api/feedback inválido", details);
  }
  return result.data;
}
