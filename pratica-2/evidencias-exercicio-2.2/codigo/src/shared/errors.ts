// Erros tipados do domínio. Toda falha que cruza uma fronteira (HTTP, serviço
// externo) deve ser uma instância destas classes — nunca um Error genérico —
// para que handlers consigam mapear para o status HTTP e o código correto
// sem inspecionar mensagens de texto.

export interface FieldDetail {
  field: string;
  message: string;
}

export abstract class AppError extends Error {
  abstract readonly statusCode: number;
  abstract readonly code: string;

  constructor(message: string, readonly cause?: unknown) {
    super(message);
    this.name = new.target.name;
  }
}

export class ValidationError extends AppError {
  readonly statusCode = 400;
  readonly code = "VALIDATION_ERROR";

  constructor(message: string, readonly details: FieldDetail[] = []) {
    super(message);
  }
}

export class UpstreamServiceError extends AppError {
  readonly statusCode = 502;
  readonly code = "UPSTREAM_SERVICE_ERROR";

  constructor(readonly service: string, message: string, cause?: unknown) {
    super(message, cause);
  }
}

export function isAppError(error: unknown): error is AppError {
  return error instanceof AppError;
}
