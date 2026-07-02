import { z } from "zod";

export const ChatMessageSchema = z.object({
  role: z.enum(["user", "assistant"]),
  content: z.string().min(1),
});
export type ChatMessage = z.infer<typeof ChatMessageSchema>;

// ADR-0002: histórico limitado a 3 turnos de conversa.
export const QueryRequestSchema = z.object({
  question: z.string().min(1, "question não pode ser vazia"),
  conversationHistory: z.array(ChatMessageSchema).max(3, "conversationHistory aceita no máximo 3 turnos").optional(),
});
export type QueryRequest = z.infer<typeof QueryRequestSchema>;

export const SourceDocumentSchema = z.object({
  documentId: z.string().min(1),
  section: z.string().optional(),
});
export type SourceDocument = z.infer<typeof SourceDocumentSchema>;

// source_document nunca é opcional: guardrail do cenário — mesmo respostas de
// baixa confiança devem indicar de onde a tentativa de resposta veio.
export const QueryResponseSchema = z.object({
  answer: z.string(),
  source_document: SourceDocumentSchema,
  confidence: z.enum(["high", "low"]),
});
export type QueryResponse = z.infer<typeof QueryResponseSchema>;
