# Análise Técnica de Viabilidade — Assistente RAG NovaTech/DB1

---

## Seção 1 — Análise por Tipo de Fonte

### 1.1 PDFs com Tabelas Complexas (15+ colunas)

**Desafio técnico**

Bibliotecas padrão de extração de PDF (PyMuPDF, pdfplumber, Amazon Textract em modo simples) serializam tabelas linha a linha, destruindo o alinhamento colunar. Uma tabela de frete com colunas `[Origem | Destino | Peso_min | Peso_max | Prazo_D+ | Valor_kg | Valor_fixo | Seguro % | ...]` vira uma sequência de tokens sem estrutura relacional. Além disso, tabelas largas que excedem a largura da página frequentemente sofrem quebra de coluna ou mesclagem de células pelo renderizador do PDF.

**Impacto na qualidade sem tratamento**

O LLM receberá texto que parece fragmentos de frases justapostos. Consultas do tipo *"quanto custa o frete de 600 kg para Manaus?"* retornarão valores incorretos ou alucinados porque o modelo não consegue inferir qual valor pertence a qual célula/linha/coluna. Falsos positivos em consultas de SLA e frete têm impacto direto no atendimento ao cliente.

**Estratégia de tratamento**

1. Usar **Azure Document Intelligence** (Form Recognizer) no modo `layout` ou `prebuilt-document`, que retorna tabelas como estrutura JSON com coordenadas de célula (`rowIndex`, `columnIndex`, `content`).
2. Converter cada tabela extraída para **Markdown tabular** (`| col1 | col2 | ...`) antes de indexar — o GPT-4o processa Markdown tabular com fidelidade superior a texto plano serializado.
3. Para tabelas que excedem ~800 tokens em Markdown, aplicar **chunking por faixas de linha** mantendo o cabeçalho completo em cada chunk (ex.: linhas 1–20 com header, linhas 21–40 com header repetido).

---

### 1.2 PDFs Escaneados (~15% do volume = ~120 documentos)

**Desafio técnico**

PDFs escaneados são imagens embutidas — não há camada de texto. OCR precisa ser aplicado antes de qualquer extração. Os desafios compõem-se: (a) qualidade variável da digitalização (resolução, inclinação, manchas), (b) fontes não-padrão em formulários impressos, (c) tabelas em documentos escaneados têm taxa de erro OCR significativamente maior que texto corrido, e (d) o pipeline de ingestão precisa detectar automaticamente se um PDF é escaneado ou nativo.

**Impacto na qualidade sem tratamento**

Documentos escaneados sem OCR aparecem na base como PDFs de tamanho zero (nenhum texto extraível). Se o sistema não falhar explicitamente, esses documentos serão ignorados silenciosamente — o atendente pergunta sobre um processo documentado apenas num formulário escaneado e recebe *"não encontrei informações"*, mesmo o documento existindo na base.

**Estratégia de tratamento**

1. **Detecção automática**: verificar via `pdfminer` ou PyMuPDF se a página tem camada de texto; se `len(texto) < 50 chars/página`, classificar como escaneado.
2. Rotear esses documentos pelo **Azure AI Document Intelligence** com OCR nativo (confiança por caractere disponível na resposta).
3. Descartar chunks onde a confiança OCR média for abaixo de **0,80** — registrar em log de curadoria para revisão humana em vez de indexar lixo.
4. Para os ~120 documentos, estimar custo de processamento OCR via Azure: aproximadamente **USD 0,01/página** × 120 docs × 10 páginas = **USD 12** (custo único de ingestão, negligenciável).

---

### 1.3 Wiki Confluence — Links Internos e Macros Customizadas

**Desafio técnico**

A API REST do Confluence retorna conteúdo em formato **Confluence Storage Format (XML)**, não HTML limpo. Macros como `{status}`, `{jira}`, `{expand}`, `{info}`, `{table-of-contents}` precisam ser interpretadas ou descartadas. Links internos do tipo `[Política de Devolução|pageId:123456]` geram chunks que referenciam conteúdo ausente se a página-alvo não for recuperada no mesmo contexto. O maior risco são as macros `{expand}` (conteúdo colapsado) — se não expandidas, grandes blocos de informação nunca chegam ao índice.

**Impacto na qualidade sem tratamento**

Chunks com markup XML de macros poluem o embedding com tokens irrelevantes (`{warning:title=Atenção}`, `ac:parameter`, etc.), degradando a qualidade vetorial. Páginas que dependem de links internos para completar seu raciocínio produzem respostas parciais e incoerentes.

**Estratégia de tratamento**

1. Usar a biblioteca **`atlassian-python-api`** + parser customizado para expandir macros `{expand}`, `{info}`, `{warning}`, `{note}` para seus conteúdos textuais antes do chunking.
2. Para links internos (`[texto|pageId:xxx]`): substituir pelo título da página referenciada + incluir a página referenciada como candidata a co-indexação (grafo de dependências de páginas).
3. Macros sem conteúdo textual relevante (`{jira}`, `{status}`, `{recently-updated}`) → descartar completamente.
4. Adicionar ao metadado do chunk o campo `confluence_page_id` e `parent_page_title` para permitir recuperação contextual por hierarquia de espaço.

---

### 1.4 Planilhas XLSX com Fórmulas Interdependentes

**Desafio técnico**

Fórmulas (`=VLOOKUP(A2,Tabela_SLA!$A:$F,3,FALSE)`) não têm valor semântico para o LLM — o que importa são os **valores calculados**. Planilhas de logística frequentemente têm: abas de parâmetros (tabelas de referência), abas de cálculo (fórmulas), e abas de resultado. O valor em uma célula pode depender de 3–4 abas distintas. Além disso, células numéricas sem contexto de cabeçalho são incompreensíveis (*"1.250"* — é km, R$, kg ou prazo?).

**Impacto na qualidade sem tratamento**

Se indexar o valor da fórmula como string (`=VLOOKUP(...)`), o LLM não entende. Se indexar apenas valores sem cabeçalhos de linha/coluna, os números ficam sem contexto semântico. Consultas sobre frete e SLA (os casos de uso principais) falham completamente.

**Estratégia de tratamento**

1. Carregar a planilha com **`openpyxl`** com `data_only=True` para capturar **valores calculados**, não fórmulas.
2. Para cada aba relevante, extrair como Markdown tabular: cabeçalhos da linha 1 + dados. Linhas/colunas auxiliares (cálculos intermediários, parâmetros ocultos) devem ser incluídas com rótulo explícito.
3. Adicionar **descrição gerada** no início de cada chunk de aba: *"Esta tabela contém os valores de SLA por categoria de cliente (Bronze, Silver, Gold) para as regiões Norte, Nordeste e Sul."* — gerada uma vez via LLM no pipeline de ingestão, não no momento de retrieval.
4. Documentar no metadado a **data de extração dos valores** — planilhas são os documentos com maior taxa de atualização e exigem política de reprocessamento ativo (trigger ou schedule).

---

## Seção 2 — Estimativa de Tamanho da Base em Tokens

### Parâmetros adotados

**PDFs — justificativa do valor de palavras/página:**
Documentos de logística combinam texto corrido (políticas, procedimentos) com tabelas densas e fluxogramas. Uma página A4 com texto corrido tem ~400–500 palavras; com tabelas e imagens, cai para ~150–200 palavras de conteúdo textual por página. Adoto **300 palavras/página** como média ponderada (60% do volume com texto corrido ~400 palavras, 40% com tabelas/imagens ~150 palavras → 0,6×400 + 0,4×150 = 300).

**Planilhas — justificativa:**
Uma planilha de logística típica tem 3–5 abas com tabelas de frete, SLA, e parâmetros. Cada aba tem ~30–80 linhas × 8–15 colunas. O conteúdo textual indexável (cabeçalhos + valores de células + descrição gerada) converge para ~2.000 palavras por arquivo como estimativa conservadora.

### Cálculo passo a passo

```
PDFS:
  800 docs × 10 páginas/doc × 300 palavras/página
  = 800 × 10 × 300
  = 2.400.000 palavras
  ÷ 0,75
  = 3.200.000 tokens  (~3,2M tokens)

WIKI (Confluence):
  400 páginas × 1.500 palavras/página
  = 600.000 palavras
  ÷ 0,75
  = 800.000 tokens  (~800K tokens)

PLANILHAS:
  50 arquivos × 2.000 palavras/arquivo
  = 100.000 palavras
  ÷ 0,75
  = 133.333 tokens  (~133K tokens)

─────────────────────────────────────────
TOTAL DE PALAVRAS:  2.400.000 + 600.000 + 100.000 = 3.100.000 palavras
TOTAL DE TOKENS:    3.200.000 + 800.000 + 133.333 = 4.133.333 tokens ≈ 4,1M tokens
─────────────────────────────────────────
```

**Observação importante:** este valor é o tamanho da base indexada, não o que cabe numa única query. O Azure AI Search armazena os vetores e o texto bruto externamente; o LLM só vê os K chunks recuperados por query. 4,1M tokens confirmam que toda a base **não cabe** na janela de 128K tokens — retrieval seletivo é obrigatório, não opcional.

---

## Seção 3 — Análise de Orçamento de Contexto por Query

### 3.1 Tokens disponíveis após system prompt

```
Janela total do GPT-4o:        128.000 tokens
(-) System prompt + guardrails:  -2.000 tokens
                               ──────────────
Disponível por query:           126.000 tokens
```

### 3.2 Chunks que cabem por query (com histórico reservado)

```
Disponível por query:          126.000 tokens
(-) Histórico de conversa:      -4.000 tokens  (5 turnos típicos)
                               ──────────────
Orçamento para chunks:         122.000 tokens

122.000 ÷ 500 tokens/chunk = 244 chunks (máximo teórico)
```

**O número teórico de 244 chunks é inútil na prática.** O Azure AI Search retorna chunks ranqueados por relevância — enviar os 244 melhor ranqueados degradaria a qualidade em vez de melhorá-la. O orçamento real deve ser dimensionado pela **qualidade marginal decrescente**: os primeiros 5–8 chunks respondem ~90% das queries; chunks 9–20 raramente acrescentam informação nova; acima de 20, aumenta o risco de chunks irrelevantes que confundem o modelo.

**Recomendação operacional: recuperar 8–12 chunks por query**, reservando ~4.000–6.000 tokens para chunks e mantendo ampla margem de segurança para histórico longo.

### 3.3 Impacto do número de chunks e efeito "lost in the middle"

Com 8–12 chunks no contexto:
- Chunks na **posição 1–2** e **posição final** recebem atenção máxima do modelo (efeito documentado em Liu et al., 2023).
- Chunks nas **posições intermediárias** (3–9 num contexto de 12) têm probabilidade de atenção significativamente reduzida.

**Consequências práticas para NovaTech:**
- Se o chunk com o valor correto de frete estiver na posição 6 de 10, o modelo pode ignorá-lo e gerar uma resposta com base nos chunks 1–2 (menos relevantes mas bem posicionados).
- **Mitigação**: aplicar **Reciprocal Rank Fusion (RRF)** — disponível nativamente no Azure AI Search — combinando busca vetorial + busca lexical (BM25). O chunk mais relevante deve estar garantidamente em posição 1. Alternativamente, usar **reranking** com `cross-encoder` (Azure AI Search tem integração nativa com Cohere Rerank) para reordenar os chunks antes de montar o prompt, colocando o mais relevante primeiro e o segundo mais relevante no final.

### 3.4 Context rot em sessões longas do Teams

```
Modelo de crescimento do histórico:
  Turno médio: ~300 tokens (pergunta) + ~400 tokens (resposta) = ~700 tokens/turno

  Sessão  5 turnos:   5 × 700 = 3.500 tokens  (< 4K reservado → OK)
  Sessão  8 turnos:   8 × 700 = 5.600 tokens  (excede reserva em 1.600 tokens)
  Sessão 10 turnos:  10 × 700 = 7.000 tokens
  Sessão 15 turnos:  15 × 700 = 10.500 tokens
```

**Context rot começa no turno 6–7**, quando o histórico começa a consumir tokens originalmente orçados para chunks. O efeito se manifesta como:

1. **Compressão de chunks**: menos chunks cabem → recall diminui.
2. **Diluição de atenção**: o modelo divide atenção entre histórico antigo (frequentemente irrelevante para a pergunta atual) e chunks novos.
3. **Confusão de referências**: perguntas como *"e para o cliente de que falamos antes?"* dependem de contexto antigo que pode ter sido truncado.

**Mitigações:**
- Implementar **sliding window** no histórico: manter apenas os últimos N turnos (recomendado: últimos 4 turnos = ~2.800 tokens).
- Aplicar **summarization de histórico**: ao atingir turno 6, resumir turnos 1–4 em ~300 tokens antes de passá-los ao contexto.
- Separar por **intenção de sessão**: se a pergunta não referencia explicitamente contexto anterior (sem pronomes anafóricos), enviar histórico = 0 para maximizar chunk budget.

---

## Seção 4 — Recomendação de Estratégia de Chunking

### 4.1 Estratégia recomendada: Chunking Hierárquico por Seção Semântica

Rejeito chunking por tamanho fixo (*fixed-size*) para este contexto: documentos de logística têm seções coesas (ex.: "Política de Devoluções", "SLA por Categoria") que seriam fragmentadas arbitrariamente, gerando chunks que iniciam no meio de uma regra e terminam antes de sua exceção.

**Estratégia indicada: *Recursive Character Text Splitter* com delimitadores semânticos**, respeitando esta hierarquia de corte:

```
1ª prioridade: quebrar por seção (heading H1/H2 do documento)
2ª prioridade: quebrar por parágrafo duplo (\n\n)
3ª prioridade: quebrar por sentença (ponto final + maiúscula)
4ª prioridade: quebrar por tamanho máximo (fallback)
```

Para tabelas: tratamento separado (ver 4.4).

**Justificativa para o contexto NovaTech:** perguntas como *"qual o prazo de devolução?"* mapeiam diretamente para seções com esse título — o chunking por seção garante que toda a regra (incluindo exceções e condicionais) esteja no mesmo chunk, evitando respostas parciais.

### 4.2 Tamanho e overlap recomendados

| Tipo de documento | Tamanho do chunk | Overlap |
|---|---|---|
| PDFs — texto corrido (políticas, procedimentos) | **500 tokens** | **10% (50 tokens)** |
| PDFs — tabelas (tratamento especial) | **600–800 tokens** (tabela inteira) | **0%** |
| Wiki Confluence | **400 tokens** | **15% (60 tokens)** |
| Planilhas (por aba) | **600 tokens** | **0%** |

**Justificativa do overlap de 10–15%:** o objetivo não é maximizar recall por volume, mas garantir que frases de transição entre seções ("...conforme descrito na tabela anterior, o prazo mínimo é...") não percam contexto. Overlap acima de 20% aumenta tokens de embedding sem ganho proporcional de qualidade.

### 4.3 Metadados obrigatórios por chunk

```json
{
  "chunk_id": "uuid-v4",
  "source_type": "sharepoint_pdf | confluence | xlsx",
  "document_title": "Política de Devoluções - v3.2",
  "document_url": "https://novatech.sharepoint.com/.../doc.pdf",
  "section_heading": "3.2 Prazo para Solicitação de Devolução",
  "page_number": 12,
  "chunk_index": 7,
  "total_chunks_in_doc": 24,
  "last_modified": "2025-11-15",
  "document_category": "devolucoes | frete | sla | procedimentos",
  "confidence_ocr": 0.94,
  "table_id": "table_3_page_12",
  "has_table": true
}
```

O campo `section_heading` é crítico para a resposta com indicação de fonte: permite ao assistente citar *"Seção 3.2 da Política de Devoluções"* em vez de apenas *"documento PDF"*.

O campo `document_category` viabiliza **pre-filtering** no Azure AI Search — antes de busca vetorial, filtrar por categoria reduz o espaço de busca e melhora precisão.

### 4.4 Tratamento de tabelas

**Tabelas devem ser mantidas íntegras num único chunk sempre que possível.**

Justificativa: fragmentar uma tabela de frete por faixa de peso (ex.: chunk 1 = linhas 1–15, chunk 2 = linhas 16–30) significa que uma consulta sobre faixa de 550–650 kg pode recuperar apenas chunk 1 (sem a linha correta) e gerar resposta incorreta.

**Regras práticas:**
- Tabela ≤ 800 tokens → chunk único, com título da tabela e cabeçalho de seção como prefixo.
- Tabela > 800 tokens → dividir por **grupo lógico de linhas** (ex.: por região geográfica, por categoria de cliente), repetindo o **cabeçalho completo em cada chunk** sub-tabular.
- Sempre incluir 1–2 sentenças de contexto antes da tabela no mesmo chunk.

---

## Seção 5 — Riscos Técnicos e Mitigações

### Risco 1 — Drift da Base Documental (Documentos Desatualizados no Índice)

**Descrição:** A base documental da NovaTech é viva — tabelas de frete são renegociadas, SLAs são revisados por contrato, políticas são atualizadas. O pipeline de ingestão inicial indexará uma versão point-in-time; sem sincronização, o assistente responderá com valores antigos enquanto os atendentes já operam com os novos.

**Probabilidade: Alta** — Em empresas de logística, tabelas de frete mudam com frequência sazonal (combustível, impostos). A probabilidade de ao menos 1 documento crítico ficar desatualizado em 30 dias de operação é próxima de 100%.

**Impacto:** Qualidade e reputação. Atendentes que confiam no assistente podem passar informações erradas a clientes finais, gerando litígios sobre cobranças.

**Mitigação:**
- Implementar webhook/delta-sync com SharePoint Graph API (suporte nativo a `$deltaToken`).
- Para Confluence: varredura diária por `lastModified > T-1d`.
- **TTL de index por categoria**: documentos de frete reindexados a cada 24h; políticas semanalmente.
- Exibir ao atendente a **data de última atualização** do chunk fonte junto à resposta.

---

### Risco 2 — Alucinação em Consultas Numéricas Precisas

**Descrição:** Consultas sobre frete, SLA e prazos exigem precisão absoluta. GPT-4o, mesmo com grounding em chunks relevantes, pode "suavizar" valores numéricos, especialmente quando o chunk contém múltiplos números similares.

**Probabilidade: Média**

**Impacto:** Alto em operações críticas. Um valor de frete errado em R$ 0,50/kg para um cliente enviando 10 toneladas representa R$ 5.000 de diferença.

**Mitigação:**
- Instrução explícita no system prompt para reproduzir valores numéricos exatamente como no documento.
- **Guardrail pós-geração**: regex para detectar números na resposta e verificar se aparecem verbatim em algum chunk retornado.
- Incluir no output o trecho exato do documento fonte (quote), não apenas a resposta parafraseada.

---

### Risco 3 — Qualidade do Embedding para Termos de Domínio Logístico

**Descrição:** Modelos de embedding padrão têm representações vetoriais fracas para termos como *"CIF"*, *"FOB"*, *"GRIS"*, *"ad valorem"*, *"romaneio"*, *"CTe"*. Uma busca por *"qual a alíquota de seguro?"* pode falhar em recuperar o chunk correto se o documento usar *"ad valorem"* como sinônimo.

**Probabilidade: Média**

**Impacto:** Degradação silenciosa de recall — o sistema responde *"não encontrei"* quando a informação existe.

**Mitigação:**
- Construir glossário de termos logísticos com sinônimos para expansão de query.
- **Busca híbrida obrigatória**: vetorial (semântica) + BM25 (lexical), com fusão por RRF.
- Avaliar fine-tuning do modelo de embedding após 30 dias de uso.

---

### Risco 4 — Escalabilidade do Pipeline de Ingestão para Documentos Dinâmicos

**Descrição:** O pipeline precisa gerenciar re-parse, re-chunk, re-embed e re-index de documentos alterados, com gestão de versões (chunks v2 coexistindo com chunks v1 durante a transição).

**Probabilidade: Alta** — Todo sistema RAG em produção enfrenta este problema.

**Impacto:** Prazo (2–3 semanas de desenvolvimento não planejado se descoberto após go-live) e qualidade (chunks de versões antigas contaminando respostas).

**Mitigação:**
- Projetar com **document_id + version_hash** desde o início: ao reindexar, deletar todos os chunks da versão anterior antes de inserir os novos.
- Usar **Azure Data Factory** ou **Logic Apps** para orquestrar sincronização incremental.
- Implementar dashboard de monitoramento de ingestão antes do go-live.

---

## Conclusão

O projeto é **tecnicamente viável** dentro de um cronograma de 3 meses, desde que o escopo seja realista: as seções de complexidade alta (OCR com validação de qualidade, extração fiel de tabelas multi-coluna, pipeline de sincronização incremental) representam trabalho de engenharia substantivo, não configuração de produto. A stack Azure OpenAI + Azure AI Search é adequada e madura para este caso de uso, com integração nativa entre os componentes.

A **principal incógnita técnica que precisa ser validada antes de confirmar o cronograma** é a qualidade de extração das tabelas complexas dos PDFs do SharePoint via Azure Document Intelligence: é necessário executar um **proof-of-concept de ingestão** com 20–30 PDFs representativos (incluindo tabelas de frete com 15+ colunas e documentos escaneados de baixa qualidade) e medir o *round-trip accuracy* — ou seja, fazer queries sobre valores específicos dessas tabelas e verificar se o sistema recupera os valores corretos com precisão ≥ 90%. Se essa validação revelar taxa de extração abaixo deste threshold, o pipeline precisará de uma camada de normalização manual ou semi-automática que impacta diretamente prazo e custo, e esse risco precisa estar precificado no contrato antes do início da execução.
