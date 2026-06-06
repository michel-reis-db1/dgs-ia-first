# Revisão Crítica da Análise Técnica — NovaTech RAG

> Papel: engenheiro sênior crítico revisando a análise de viabilidade.
> Objetivo: identificar pontos fracos, não defender o que foi escrito.

---

## 1. Estimativas Otimistas Demais

### 1.1 O número de 4,1M tokens ignora o overhead de ingestão

O cálculo estimou o tamanho do conteúdo bruto, não o que efetivamente fica indexado. Há três fontes de inchaço não contabilizadas:

**Overhead de metadados por chunk:** Cada chunk carrega um bloco de metadados JSON (~150–200 tokens). Com ~8.200 chunks estimados (4,1M ÷ 500), isso soma **~1,4M tokens adicionais** que nunca aparecem nas buscas mas consomem espaço de armazenamento e custo de embedding.

**Overhead de overlap:** Com 10–15% de overlap nos chunks de texto corrido, o volume efetivo de tokens indexados cresce ~8–12% sobre o volume bruto.

**Descrições geradas para planilhas:** As descrições geradas via LLM recomendadas para cada aba (~100 tokens/chunk) não foram incluídas no cálculo.

**Correção:** O volume real indexado está provavelmente entre **5,5M e 6M tokens**, não 4,1M. Isso impacta o custo de embedding inicial e recorrente.

---

### 1.2 A estimativa de 300 palavras/página esconde uma variância perigosa

O valor médio pode estar certo para o conjunto inteiro, mas a variância é o problema real. Documentos de logística têm distribuição bimodal:

- Formulários e tabelas de frete: **80–150 palavras/página** (a maior parte é número e célula vazia)
- Procedimentos operacionais com texto corrido: **400–500 palavras/página**

Usar a média numa base bimodal produz chunks de tamanho 500 tokens com conteúdo semântico muito diferente: alguns terão uma tabela inteira com pouco texto, outros terão metade de uma seção de procedimento. A estratégia de retrieval precisa ser calibrada para essa variância, não para a média.

---

### 1.3 O orçamento de contexto de 2K tokens para system prompt é otimista

O sistema descrito exige, no system prompt:
- Persona e tom em português
- Instrução de citar fontes com formato específico
- Guardrails de hallucination (instrução explícita sobre números)
- Instrução de não responder fora do escopo
- Formato de saída estruturada (se houver)
- Instrução de comportamento para perguntas ambíguas

Em produção, system prompts deste tipo chegam facilmente a **3.500–5.000 tokens**. Com 5K de system prompt em vez de 2K, o orçamento disponível cai de 126K para 123K — não catastrófico, mas o cálculo deveria partir do pior caso, não do otimista.

---

### 1.4 O crescimento do histórico foi subestimado para o Teams

O documento adotou 700 tokens/turno (300 pergunta + 400 resposta). Dois problemas:

**Respostas com tabelas valem muito mais:** Se o assistente responde com uma tabela Markdown de 8 linhas × 4 colunas, isso são ~300 tokens só de tabela. Respostas ricas chegam facilmente a **800–1.200 tokens**.

**O Teams incentiva perguntas longas com contexto colado:** Atendentes frequentemente colam trechos de e-mail do cliente na pergunta. Uma pergunta dessas vale **500–700 tokens**, não 300.

**Cálculo revisado com pior caso realista:**
```
Turno médio real: ~500 tokens (pergunta) + ~700 tokens (resposta) = 1.200 tokens/turno
5 turnos:   6.000 tokens  (50% acima da reserva de 4K)
8 turnos:   9.600 tokens
10 turnos: 12.000 tokens
```

O "context rot" que a análise situou no turno 6–7 começa na prática no **turno 4–5**. Isso muda a urgência da estratégia de sliding window./

---

## 2. Riscos Omitidos

### 2.1 Documentos contraditórios no índice (risco omitido completamente)

Este é provavelmente o risco mais grave para um sistema de atendimento. Situações comuns em logística:

- "Política de Devoluções v2.1" (2023) e "Política de Devoluções v3.0" (2024) **ambas indexadas**
- Tabela de frete desatualizada em pasta de rede + versão atual no SharePoint
- Procedimento no Confluence que contradiz o PDF oficial porque a wiki não foi atualizada após revisão

O que acontece no RAG: ambos os documentos retornam chunks com alta relevância para a mesma query. O LLM recebe informações contraditórias e tem três comportamentos possíveis — todos ruins: (a) escolhe o mais recente sem indicar a contradição, (b) média os valores, (c) alerta que há conflito sem indicar qual está correto.

**Correção:** O pipeline de ingestão precisa de uma etapa de **deduplicação semântica** — detectar pares de documentos com similaridade de embedding acima de 0,92 e encaminhar para revisão humana antes de indexar. Adicionar campo `status: [vigente | obsoleto | em_revisão]` nos metadados, coletado via atributo do SharePoint ou campo do Confluence.

---

### 2.2 Latência de ponta a ponta não foi analisada

O documento calculou tokens e custos, mas não tocou em latência. O pipeline completo para uma query:

```
Query preprocessing + query expansion:  ~200ms
Azure AI Search (vector + BM25 + RRF):  ~300–800ms
Reranking (Cohere Rerank, se usado):    ~400–800ms
GPT-4o inference (6K tokens input):     ~3.000–8.000ms
────────────────────────────────────────────────────────
Total realista:                          ~4s – 10s por query
```

Para um atendente ao telefone com um cliente, 8–10 segundos é um silêncio constrangedor. O SLA padrão de chatbots de atendimento é 3 segundos.

**Correção:** Definir SLA de latência como requisito não-funcional antes do início (sugestão: P95 < 5 segundos). Planejar: cache semântico para queries frequentes (ex.: "qual o SLA do cliente Gold?" — provavelmente perguntada dezenas de vezes por dia), streaming de resposta para feedback visual imediato, benchmark de latência como critério de aceite.

---

### 2.3 Custo recorrente de re-embedding foi mencionado mas não calculado corretamente

O custo financeiro de embedding é irrelevante (text-embedding-3-large custa $0,13/1M tokens → re-indexação mensal de 20% do conteúdo ≈ $0,11/mês). O custo real omitido é **operacional e de engenharia**:

- Detectar quais chunks específicos mudaram dentro de um documento alterado (um documento de 20 chunks com 1 parágrafo alterado: re-processar todos os 20 ou detectar mudança granular?)
- Gerenciar estado de transição onde metade dos chunks do documento é da versão nova e metade da versão antiga durante o reprocessamento
- Garantir que deleção de chunks antigos ocorre atomicamente com inserção dos novos

**Correção:** Estimar **3–4 sprints de desenvolvimento** apenas para o pipeline de sincronização incremental robusto, ou recomendar solução gerenciada (Azure Logic Apps + Azure AI Search indexer com change detection nativo do SharePoint).

---

### 2.4 Controle de acesso e vazamento de informação confidencial

Completamente ausente da análise. Questões não feitas:

- Todos os 45 atendentes têm o mesmo nível de acesso no SharePoint atual?
- Existem contratos de clientes específicos com condições comerciais confidenciais indexadas?
- Tabelas de frete negociadas individualmente por cliente deveriam ser visíveis a todos?

Se o SharePoint tem ACLs por pasta e essas não forem mapeadas para filtros no Azure AI Search, o assistente pode responder com informações de contratos confidenciais para atendentes sem permissão de acesso.

**Correção:** Mapear permissões atuais do SharePoint antes de iniciar o projeto. Decidir entre: (a) indexar apenas documentos com permissão universal, (b) implementar security trimming no Azure AI Search usando grupos do Azure AD, ou (c) segmentar índices por nível de acesso.

---

## 3. Pontos Fracos na Estratégia de Chunking

### 3.1 A estratégia hierárquica falha silenciosamente em PDFs sem estrutura de heading

O documento assumiu que PDFs têm hierarquia de headings (H1/H2). PDFs corporativos gerados a partir do Word frequentemente têm **zero marcação semântica** — todo o texto está em estilo "Normal", com seções demarcadas apenas por linhas em negrito ou tamanho de fonte ligeiramente maior. Nenhuma biblioteca de parsing reconhece isso como heading.

Resultado: a 1ª prioridade da estratégia (cortar por seção) falha imediatamente e toda a lógica cai para o fallback de parágrafo/sentença — que para documentos de procedimento logístico longo produz chunks sem coesão semântica.

**Correção:** Auditar 20–30 PDFs representativos para determinar que porcentagem tem estrutura de heading detectável. Se for abaixo de 60%, a estratégia primária deve ser parágrafo duplo (`\n\n`), com detecção heurística de "pseudo-headings" (linha curta + negrito + ≤ 10 palavras).

---

### 3.2 Overlap em chunks tabulares cria ambiguidade garantida

Ao dividir uma tabela grande por faixas de linhas com repetição de cabeçalho, as linhas de fronteira aparecem em dois chunks — isso **é** overlap de conteúdo tabular. O problema: se as linhas 18–22 aparecem no chunk A (linhas 1–22) e no chunk B (linhas 20–40), ambos com o mesmo cabeçalho, o retrieval pode retornar os dois chunks para a mesma query, e o LLM receberá a linha 20 duplicada em dois contextos diferentes.

**Correção:** Para tabelas divididas, usar **particionamento sem sobreposição de linhas** com numeração explícita de parte no metadado (`table_part: 1/3`, `table_part: 2/3`), e adicionar instrução no system prompt para, em caso de múltiplos chunks da mesma tabela, referenciar o conjunto completo.

---

### 3.3 A estratégia não endereça dependências cross-documento

Um chunk da "Política de Devoluções" pode conter: *"O prazo de 7 dias não se aplica a clientes com contrato especial conforme Adendo Comercial vigente."* O Adendo Comercial é outro documento. O chunking isola o primeiro documento corretamente, mas a resposta incompleta ("prazo de 7 dias") sem recuperar o adendo é **tecnicamente correta e operacionalmente errada**.

**Correção:** O metadado de cada chunk deve incluir `references_documents: [lista de títulos/IDs de documentos referenciados explicitamente no texto]`, extraído no pipeline de ingestão. O módulo de retrieval deve implementar **follow-up retrieval**: se o chunk top-1 contém referência a outro documento, buscar chunks desse documento como candidatos de segunda passagem.

---

### 3.4 Fallback por sentença falha em texto com abreviações logísticas

A estratégia usa ponto final como delimitador de sentença. Abreviações comuns em logística — *"prazo de entrega é de 2 d.u. após confirmação"*, *"peso máx. 30kg"*, *"cf. tabela anexa"* — acionam falsos positivos no detector de sentença, gerando chunks com corte no meio de uma regra.

**Correção:** Implementar tokenizador de sentenças com lista de abreviações do domínio (`d.u.`, `máx.`, `mín.`, `cf.`, `p.ex.`) para evitar cortes incorretos.

---

## 4. O Que Não Foi Dito Sobre "Lost in the Middle"

### 4.1 O efeito é composto em queries multi-domínio — e isso não foi dito claramente

A análise tratou "lost in the middle" como um problema de posicionamento dentro de um único conjunto de chunks relevantes. Para o caso de uso específico — *"qual o SLA, prazo de devolução e custo de frete para 300kg para Manaus para um cliente Gold?"* — o problema é fundamentalmente diferente e mais grave.

O retrieval retorna chunks de **três domínios distintos** simultaneamente. Com 10–12 chunks no contexto, a distribuição típica é:

```
Posição 1–2:   SLA Gold           (alta atenção ✓)
Posição 3–5:   Frete Manaus 300kg (atenção degradada ✗)
Posição 6–8:   Devolução          (baixa atenção ✗✗)
Posição 9–10:  SLA Gold           (duplicata)
Posição 11–12: Frete Manaus 300kg (alta atenção por recency ✓)
```

O resultado provável: o LLM responde SLA corretamente (posição 1–2), frete corretamente (posição 11–12, efeito "recency"), e **devolução incorretamente ou omitida** (posições intermediárias). O atendente recebe uma resposta aparentemente completa, mas com a sub-resposta do meio errada — e não tem como detectar isso sem verificação manual.

---

### 4.2 A solução proposta (reranking) não resolve o problema multi-domínio

Reranking resolve *qual* chunk é mais relevante para a query inteira, mas não resolve *como distribuir a atenção entre subproblemas de domínios diferentes*. O reranker vai colocar no topo o chunk mais relevante para a query como um todo — que provavelmente é do domínio mais "denso" na query (frete, por ter mais especificidade numérica). Os chunks de SLA e devolução continuam no meio.

**A solução correta não mencionada: decomposição de query (query decomposition).**

Para queries multi-domínio detectadas (heurística: recuperação de chunks de 3+ `document_category` distintos), o sistema deve:

1. Decompor a query em sub-queries: `["SLA cliente Gold", "prazo devolução cliente Gold", "frete 300kg Manaus"]`
2. Executar retrieval independente para cada sub-query (3–4 chunks cada)
3. Montar o contexto com os resultados separados por seção explícita no prompt:
   ```
   ## Informações sobre SLA
   [chunks de SLA]
   ## Informações sobre Devolução
   [chunks de devolução]
   ## Informações sobre Frete
   [chunks de frete]
   ```
4. Garantir que cada subtópico tenha posição de destaque (início de bloco), não posição aleatória num único fluxo

**Correção a incorporar:** A Seção 3 e a Seção 4 deveriam incluir uma subseção sobre detecção de queries multi-domínio e o padrão de query decomposition como **requisito de arquitetura**, não como otimização futura. Para atendimento logístico onde SLA + frete + devolução cruzam na mesma pergunta com frequência, isso é o caminho crítico.

---

### 4.3 Nenhum critério de avaliação foi proposto

O documento discutiu o efeito mas não propôs como medir se ele está ocorrendo em produção. Sem métrica, o problema pode existir silenciosamente por meses.

**Correção:** Incluir como critério de aceite um conjunto de **golden queries multi-domínio** (ex.: 20 perguntas que cruzam SLA + frete + devolução com respostas conhecidas e verificadas), executadas contra o sistema com logging de qual posição o chunk correto ocupou no contexto. Se a taxa de acerto para chunks em posição 4–8 for mais de 15% abaixo da taxa para posição 1–2, o problema está ativo e precisa de intervenção antes do go-live.

---

## Síntese dos Problemas por Severidade

| Problema | Severidade | Impacto se ignorado |
|---|---|---|
| Documentos contraditórios no índice | Crítica | Respostas erradas desde a semana 1 de operação |
| Latência não analisada | Alta | Adoção do sistema fracassa por UX |
| Queries multi-domínio sem decomposição | Alta | Sub-respostas erradas em 30–40% das queries complexas |
| Controle de acesso não mapeado | Alta | Vazamento de informação confidencial |
| Context rot mais cedo que estimado | Média | Degradação de qualidade em sessões longas não detectada |
| PDFs sem estrutura de heading | Média | Chunking incoerente em parcela significativa dos documentos |
| Volume real 35% maior que estimado | Baixa | Impacto menor em custo, não em qualidade |

---

> O documento original é um bom ponto de partida para uma proposta comercial. Não é suficiente como especificação técnica para início de desenvolvimento.
