import { z } from "zod";

// Falha rápido e alto na inicialização se uma variável obrigatória faltar —
// nunca em runtime no meio de uma requisição do atendente.
const envSchema = z.object({
  AZURE_OPENAI_ENDPOINT: z.string().url(),
  AZURE_OPENAI_API_KEY: z.string().min(1),
  AZURE_OPENAI_CHAT_DEPLOYMENT: z.string().min(1),
  AZURE_OPENAI_EMBEDDING_DEPLOYMENT: z.string().min(1),
  AZURE_SEARCH_ENDPOINT: z.string().url(),
  AZURE_SEARCH_API_KEY: z.string().min(1),
  AZURE_SEARCH_INDEX_NAME: z.string().min(1),
  LOG_LEVEL: z.enum(["debug", "info", "warn", "error"]).default("info"),
});

export type Config = {
  azureOpenAi: {
    endpoint: string;
    apiKey: string;
    chatDeployment: string;
    embeddingDeployment: string;
  };
  azureSearch: {
    endpoint: string;
    apiKey: string;
    indexName: string;
  };
  logLevel: "debug" | "info" | "warn" | "error";
};

function loadConfig(env: NodeJS.ProcessEnv): Config {
  const parsed = envSchema.safeParse(env);
  if (!parsed.success) {
    const missing = parsed.error.issues.map((issue) => issue.path.join(".")).join(", ");
    throw new Error(`Configuração inválida — variáveis de ambiente ausentes/inválidas: ${missing}`);
  }

  const env_ = parsed.data;
  return {
    azureOpenAi: {
      endpoint: env_.AZURE_OPENAI_ENDPOINT,
      apiKey: env_.AZURE_OPENAI_API_KEY,
      chatDeployment: env_.AZURE_OPENAI_CHAT_DEPLOYMENT,
      embeddingDeployment: env_.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
    },
    azureSearch: {
      endpoint: env_.AZURE_SEARCH_ENDPOINT,
      apiKey: env_.AZURE_SEARCH_API_KEY,
      indexName: env_.AZURE_SEARCH_INDEX_NAME,
    },
    logLevel: env_.LOG_LEVEL,
  };
}

export { loadConfig };
export const config = loadConfig(process.env);
