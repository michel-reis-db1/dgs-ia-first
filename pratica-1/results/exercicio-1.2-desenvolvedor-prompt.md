# Exercício 1.2 — Desenvolvedor: Prototipação de Prompt com Engenharia de Contexto

> **Como usar:** Cole o bloco "SYSTEM PROMPT V1" em uma conversa nova no Claude como instrução inicial. Em seguida, no mesmo prompt de abertura, cole os três chunks simulados. Depois faça as 3 perguntas de teste uma por uma, como se fosse o atendente. Documente as respostas e siga o protocolo de análise ao final.

---

## PARTE 1 — System Prompt V1 (cole como instrução inicial)

```
# Identidade

Você é o Assistente de Atendimento NovaTech — um sistema de IA especializado em consultar e interpretar a documentação oficial da NovaTech Logística para apoiar o time de atendimento ao cliente. Você não é um assistente de uso geral; seu escopo é estritamente a documentação da NovaTech.

# Regras obrigatórias (guardrails)

1. CITE SEMPRE a fonte: informe o nome do documento e a seção de onde a informação foi extraída (ex: "POL-001, seção 3.2").
2. NUNCA invente prazos, valores, multiplicadores ou nomes de procedimentos. Se a informação não estiver nos trechos (chunks) fornecidos, diga explicitamente que não encontrou.
3. Quando não houver resposta nos documentos: responda exatamente assim — "Não encontrei essa informação na documentação disponível. Recomendo escalar para o supervisor."
4. Responda em português formal, claro e direto. Evite jargão técnico.
5. Quando um documento contiver uma EXCEÇÃO a uma regra geral, a exceção tem prioridade sobre a regra geral. Aplique a exceção primeiro.
6. Quando houver dois documentos com o mesmo assunto e versões diferentes, priorize o documento com data mais recente. Informe ao atendente que existe uma versão anterior.

# Formato obrigatório de resposta

Estruture toda resposta assim:

**Resposta:** [a resposta direta à pergunta do atendente]
**Fonte:** [nome do documento + seção]
**Observação (se houver):** [alertas, exceções relevantes, ou conflito entre versões]

# Como usar os trechos de documentação (chunks)

- Os trechos fornecidos abaixo são os resultados recuperados pelo sistema de busca para esta consulta específica.
- Use APENAS as informações presentes nesses trechos para gerar sua resposta.
- Se um trecho apresentar regra geral E exceções, leia ambos com atenção antes de responder — não responda baseado apenas na primeira frase.
- Se os trechos forem insuficientes ou contraditórios, declare isso na observação.

# O que você NÃO deve fazer

- Não complete lacunas com conhecimento geral sobre logística ou leis.
- Não afirme que algo é permitido apenas porque não leu a proibição — ausência de informação não é permissão.
- Não invente tiers de cliente, valores de SLA ou multiplicadores de frete.
```

---

## PARTE 2 — Contexto de teste (cole junto com o system prompt na abertura da conversa)

```
--- INÍCIO DOS TRECHOS DE DOCUMENTAÇÃO RECUPERADOS ---

[Chunk A] Fonte: POL-001, seção 3.2 — Exceções ao prazo geral
As seguintes categorias de carga NÃO são elegíveis para devolução pelo processo padrão:
Cargas perigosas classificadas nas classes 1 a 6 da ANTT (Agência Nacional de Transportes Terrestres), conforme Resolução ANTT nº 5.947/2021. Inclui: explosivos (classe 1), gases (classe 2), líquidos inflamáveis (classe 3), sólidos inflamáveis (classe 4), oxidantes e peróxidos (classe 5), substâncias tóxicas e infectantes (classe 6). Para essas categorias, o cliente deve entrar em contato com o setor de Gestão de Riscos (ramal 4500) para tratamento individual.

[Chunk B] Fonte: SLA-2024, seção 2 — Tabela de SLAs (chamados gerais)
SLAs para chamados gerais:
- Gold: resposta em até 2h úteis, resolução em até 24h úteis.
- Silver: resposta em até 4h úteis, resolução em até 48h úteis.
- Standard: resposta em até 8h úteis, resolução em até 72h úteis.

[Chunk C] Fonte: PROC-042-v2, seção 2 — Frete especial (versão revisada, novembro/2023)
Frete especial para cargas acima de 500kg.
Multiplicadores regionais atualizados (novembro/2023):
- Sul: 1.3
- Sudeste: 1.1
- Norte: 1.8
- Nordeste: 1.5
- Centro-Oeste: 1.4
Fórmula: Valor base × Multiplicador regional × Fator de peso.
Fator de peso: 1.0 (500–1.000kg), 1.15 (1.001–3.000kg), 1.4 (acima de 3.000kg).

--- FIM DOS TRECHOS DE DOCUMENTAÇÃO RECUPERADOS ---
```

---

## PARTE 3 — Perguntas de teste (faça uma por uma após abrir a conversa)

Execute cada pergunta abaixo em sequência, como se fosse um atendente consultando o assistente durante um chamado real.

**Pergunta 1:**
```
Qual o prazo de devolução para carga perigosa?
```

**Pergunta 2:**
```
Meu cliente é Gold, qual o SLA de resolução?
```

**Pergunta 3:**
```
Quanto custa o frete para 600kg para Manaus?
```

---

## PARTE 4 — Protocolo de análise das respostas

Após obter as 3 respostas, analise cada uma com a tabela abaixo:

| Critério | Pergunta 1 | Pergunta 2 | Pergunta 3 |
|----------|------------|------------|------------|
| Resposta factualmente correta? |         |         |         |
| Citou a fonte correta? |         |         |         |
| Respeitou o formato (Resposta / Fonte / Observação)? |         |         |         |
| Aplicou corretamente exceções ou regras de prioridade? |         |         |         |
| Falhou em algum guardrail? Qual? |         |         |         |

**Gabarito esperado por pergunta:**

- **Pergunta 1 (carga perigosa):** A resposta CORRETA é que carga perigosa NÃO é elegível para devolução pelo processo padrão (POL-001, seção 3.2). O assistente deve mencionar o ramal 4500. Se disser "sim, pode devolver" ou omitir a exceção — isso é uma falha crítica de interpretação.
- **Pergunta 2 (SLA Gold):** Resposta correta é "resolução em até 24h úteis" (SLA-2024, seção 2). Atenção: não confundir com incidente crítico (4h) — os chunks fornecidos não incluem a seção de incidentes críticos, então o assistente não deve mencionar esse dado.
- **Pergunta 3 (frete 600kg Manaus):** Manaus fica na Região Norte, multiplicador 1.8. A carga é 600kg, portanto fator de peso 1.0. Fórmula: valor base × 1.8 × 1.0. O assistente não deve inventar o valor base (não está no chunk), apenas apresentar a fórmula e o multiplicador.

---

## PARTE 5 — Mapeamento estático/dinâmico (documente no seu entregável)

Use a tabela abaixo para documentar a estrutura de contexto:

| Parte do contexto | Estático ou Dinâmico | Estimativa de tokens | Observação |
|-------------------|---------------------|----------------------|------------|
| System prompt (identidade, regras, formato, instruções de chunk) | Estático | ~400–500 tokens | Vai em toda query |
| Chunks recuperados (A, B, C neste teste) | Dinâmico | ~200–300 tokens por chunk | Muda por query com base na busca semântica |
| Pergunta do atendente | Dinâmico | ~15–30 tokens | Muda a cada interação |
| Histórico de conversa (em sessões longas no Teams) | Dinâmico, crescente | Cresce com cada turno | Risco de context rot — monitorar |
| **Total estimado por query (3 chunks)** | | ~1.200–1.500 tokens | Bem dentro do budget de 128K; mas escala com chunks adicionais |

---

## PARTE 6 — Iteração V1 → V2

Após a análise, identifique os pontos do system prompt v1 que precisam de ajuste. Reescreva apenas as seções problemáticas e documente:

1. O que a resposta v1 gerou de incorreto ou incompleto.
2. Qual instrução do system prompt causou (ou não impediu) o problema.
3. O que você adicionou/mudou no v2 e por que.

Depois teste novamente com a(s) pergunta(s) que falharam e compare os resultados.

---

## Referência rápida: o que constitui cada nível de entrega

| Score | Indicadores |
|-------|-------------|
| **3 (excelente)** | System prompt tem identidade + regras + formato + instruções de chunk bem definidas; mapeamento estático/dinâmico com estimativa de tokens; 3 perguntas testadas com respostas reais documentadas; v1 → v2 com melhoria concreta e verificável; a armadilha da carga perigosa foi identificada como falha (ou o v1 já a tratou corretamente). |
| **2 (suficiente)** | System prompt funcional mas genérico em algum aspecto; mapeamento feito mas sem estimativa de tokens; testes realizados mas análise superficial. |
| **1 (insuficiente)** | System prompt genérico ("você é um assistente útil"); sem mapeamento; respostas não testadas de verdade no Claude; falha na carga perigosa não identificada. |
