# Exercício 1.3 — Desenvolvedor: Pipeline de RAG com Claude Code

> **Como usar:** Abra o Claude Code no diretório `pratica-1/` e cole o prompt abaixo diretamente no chat. O Claude irá criar todos os arquivos, implementar o código e gerar a documentação. Nenhuma etapa manual de "aceitar completion" é necessária.

---

## Prompt único para Claude Code

```
Implemente um pipeline de RAG completo para a NovaTech Logística. Os documentos-fonte já estão no diretório atual (POL-001-politica-devolucao.md, PROC-042-frete-especial-v1.md, PROC-042-v2-frete-especial-revisado.md, SLA-2024-tabela-sla-clientes.md, FAQ-atendimento.md).

## Stack
- Python 3.11+
- sentence-transformers (all-MiniLM-L6-v2)
- chromadb (cliente local persistente)
- Sem LangChain — cada etapa implementada explicitamente

## Estrutura de arquivos a criar

rag_pipeline/
  __init__.py
  config.py
  ingest.py
  retrieve.py
  assemble.py
  test_pipeline.py
  documents/         ← copie os 5 .md da raiz para cá
requirements.txt

---

## config.py

Constantes:
- CHROMA_PATH = "./chroma_db"
- COLLECTION_NAME = "novatech_docs"
- MODEL_NAME = "all-MiniLM-L6-v2"
- CHUNK_SIZE_TOKENS = 300   # alvo por chunk
- CHUNK_OVERLAP_SENTENCES = 1
- TOP_K = 5

---

## ingest.py

Estratégia de chunking: SEÇÃO-BASED (split em ## e ### headers).

Justificativa embutida nos comentários do código:
- Perguntas NovaTech mapeiam diretamente para seções (ex: "carga perigosa" → POL-001 seção 3.2)
- Tabela de multiplicadores regionais do PROC-042 não pode ser cortada no meio de uma linha
- Chunks curtos e focados (1 seção = 1 tópico) maximizam precisão de retrieval

Overlap: última frase da seção N inserida no início da seção N+1 (preserva contexto cross-section).

Metadados obrigatórios por chunk:
- document_id: str      (ex: "POL-001", "PROC-042", "PROC-042-v2", "SLA-2024", "FAQ")
- version: str          (ex: "3.1", "v2", "2024.1", "informal")
- section: str          (ex: "3.2", "2.1")
- section_title: str    (ex: "Exceções ao prazo geral")
- source_type: str      ("policy" | "procedure" | "sla" | "faq")
- last_updated: str     (data ISO do cabeçalho do documento, ex: "2024-01-15")
- is_superseded: bool   (True para PROC-042 v1)
- chunk_index: int      (posição dentro do documento, base 0)

Mapeamento de documentos para metadados:
- POL-001-politica-devolucao.md       → document_id="POL-001",     source_type="policy",    is_superseded=False
- PROC-042-frete-especial-v1.md       → document_id="PROC-042",    source_type="procedure", is_superseded=True
- PROC-042-v2-frete-especial-revisado.md → document_id="PROC-042-v2", source_type="procedure", is_superseded=False
- SLA-2024-tabela-sla-clientes.md     → document_id="SLA-2024",    source_type="sla",       is_superseded=False
- FAQ-atendimento.md                  → document_id="FAQ",          source_type="faq",       version="informal", is_superseded=False

Funções:
1. load_documents(docs_dir: str) -> list[dict]
   - Lê cada .md, extrai metadados do bloco de cabeçalho via regex (Versão, Última atualização)
   - Retorna lista de {document_id, version, last_updated, source_type, is_superseded, raw_text}

2. split_into_chunks(doc: dict) -> list[dict]
   - Split em ## e ### headers
   - Aplica overlap de 1 frase entre seções adjacentes do mesmo documento
   - chunk_id format: "{document_id}-{section}-{chunk_index}" (ex: "POL-001-3.2-0")
   - Retorna lista de chunk dicts com todos os campos de metadados

3. embed_and_store(chunks: list[dict], collection)
   - Gera embeddings com SentenceTransformer(MODEL_NAME)
   - Armazena no ChromaDB com metadados completos

4. main()
   - Carrega docs → chunka → embute → armazena
   - Imprime resumo: "N documentos → M chunks armazenados"

---

## retrieve.py

def search(
    query: str,
    collection,
    model: SentenceTransformer,
    top_k: int = 5,
    exclude_superseded: bool = True,
    min_score: float = 0.3,
    source_type_filter: list[str] | None = None,
) -> list[dict]:
    """
    Retorna top_k chunks mais similares à query.
    - exclude_superseded=True: filtra is_superseded=True (impede PROC-042 v1 contaminar resultados)
    - min_score: threshold de similaridade cosseno mínima
    - source_type_filter: allowlist opcional de source_type

    ChromaDB retorna distances (menor = mais similar). Converter:
      similarity = 1 - distance
    Filtrar: similarity >= min_score

    Retorno por item: {chunk_id, text, document_id, version, section,
                       section_title, source_type, similarity_score}
    """

def format_results_table(results: list[dict]) -> str:
    """Tabela legível dos resultados para documentação dos testes."""

---

## assemble.py

SYSTEM_PROMPT (string constante) = o texto abaixo, exatamente:

"""
# Identidade
Você é o Assistente de Atendimento NovaTech — um sistema de IA especializado em consultar
e interpretar a documentação oficial da NovaTech Logística para apoiar o time de atendimento
ao cliente. Seu escopo é estritamente a documentação da NovaTech.

# Regras obrigatórias (guardrails)
1. CITE SEMPRE a fonte: informe o document_id e a seção (ex: "POL-001, seção 3.2").
2. NUNCA invente prazos, valores, multiplicadores ou tiers de cliente. Se não estiver
   nos chunks fornecidos, diga que não encontrou.
3. Quando não houver resposta: "Não encontrei essa informação na documentação disponível.
   Recomendo escalar para o supervisor."
4. Responda em português formal e direto.
5. EXCEÇÕES prevalecem sobre regras gerais — leia o chunk completo antes de responder.
6. Se houver chunks de documentos com is_superseded=True entre os resultados, alerte
   o atendente e priorize sempre a versão mais recente.

# Formato obrigatório
**Resposta:** [resposta direta]
**Fonte:** [document_id + seção]
**Observação:** [exceções, alertas de versão, ou conflito entre fontes — se houver]

# Instruções para uso dos chunks
- Use APENAS informações dos chunks abaixo.
- Ausência de informação nos chunks ≠ permissão para inventar.
- Se um chunk citar uma exceção explícita (ex: "NÃO é elegível"), a exceção tem
  prioridade absoluta sobre qualquer regra geral no mesmo ou em outro chunk.
"""

def assemble_prompt(query: str, chunks: list[dict], include_system: bool = True) -> str:
    """
    Monta o prompt completo: sistema + bloco de chunks + query do usuário.
    Orçamento estimado de tokens:
    - System prompt: ~400 tokens (estático)
    - Cada chunk: ~150–300 tokens (dinâmico)
    - Query: ~20–50 tokens (dinâmico)
    - Total com 5 chunks: ~1.400–2.000 tokens (<<< budget de 128K)
    """

def estimate_tokens(text: str) -> int:
    """Estimativa simples: len(text.split()) * 1.33"""

def print_context_map(query: str, chunks: list[dict]) -> None:
    """
    Exibe anatomia do contexto:
    - Qual parte é estática vs dinâmica
    - Tokens estimados por parte
    - Total estimado
    """

---

## test_pipeline.py

5 casos de teste contra o gabarito do Anexo B:

TEST_CASES = [
    {
        "id": "TC-01",
        "question": "Qual o prazo de devolução para carga perigosa?",
        "expected_chunks": ["POL-001-3.2", "POL-001-3.1"],
        "expected_answer_key": "NÃO elegível pelo processo padrão — Gestão de Riscos ramal 4500",
        "trap": "A resposta CORRETA é que NÃO pode devolver pelo processo padrão.",
    },
    {
        "id": "TC-02",
        "question": "Qual o SLA do cliente Gold para chamados gerais?",
        "expected_chunks": ["SLA-2024-2"],
        "expected_answer_key": "Resposta em até 2h úteis, resolução em até 24h úteis",
        "trap": "Não confundir com SLA de incidente crítico (30min / 4h).",
    },
    {
        "id": "TC-03",
        "question": "Qual o SLA do cliente Platinum?",
        "expected_chunks": ["SLA-2024-1"],
        "expected_answer_key": "Tier Platinum NÃO existe — só Gold, Silver e Standard",
        "trap": "Pipeline deve recusar inventar SLAs para tier inexistente.",
    },
    {
        "id": "TC-04",
        "question": "Quanto custa o frete para 600kg para Manaus (região Norte)?",
        "expected_chunks": ["PROC-042-v2-2.1", "PROC-042-v2-2"],
        "expected_answer_key": "Multiplicador Norte 1.8, fator peso 1.0 (500-1000kg). Fórmula: base × 1.8 × 1.0",
        "trap": "PROC-042 v1 tem multiplicador Norte 1.6 — ERRADO. is_superseded filter deve prevenir.",
    },
    {
        "id": "TC-05",
        "question": "Qual o multiplicador regional para o Sudeste no frete especial?",
        "expected_chunks": ["PROC-042-v2-2.1"],
        "expected_answer_key": "1.1 (PROC-042-v2, novembro/2023)",
        "trap": "PROC-042 v1 diz 1.0 (ERRADO). v2 diz 1.1.",
    },
]

Para cada test case, run_test() deve:
1. Chamar search() (top_k=5, exclude_superseded=True)
2. Imprimir: pergunta, chunks recuperados (com scores), chunks esperados (gabarito)
3. Calcular precision@5: quantos chunks esperados foram efetivamente recuperados
4. Montar e imprimir o prompt completo via assemble_prompt()
5. Imprimir checklist de avaliação manual:
   - [ ] Chunks corretos recuperados?
   - [ ] Gabarito coberto pelos chunks?
   - [ ] Armadilha evitada?
   - [ ] Nenhum chunk superseded vazou?

Após os 5 testes, imprimir tabela resumo:
| TC | Pergunta (curta) | Chunks esperados | Recuperados ✓ | Score |

Ao final, incluir função problems_found() com estrutura para documentar 2+ problemas reais
observados durante os testes (pré-preencher com placeholders).

---

## Documentação gerada automaticamente

Após criar todos os arquivos Python, gere também:

### PROBLEMS_FOUND.md

Para cada problema real observado, use a estrutura:

**Problema [N]: [título curto]**
- Pergunta de teste: TC-0X — "[question]"
- Observado: [o que o pipeline retornou]
- Esperado (gabarito Anexo B): [o que deveria retornar]
- Causa raiz: [explicação técnica]
- Impacto na resposta: [o que o LLM diria com os chunks errados]
- Correção proposta: [mudança específica no código]
- Dificuldade de correção: Baixa / Média / Alta

Pré-popule com pelo menos 2 problemas prováveis baseados na arquitetura:
1. Risco de split no meio da tabela de multiplicadores do PROC-042
2. Risco de vazamento de chunks v1 se is_superseded filter falhar

### CHUNKING_JUSTIFICATION.md

Explique:
1. Por que chunking por seção foi escolhido em vez de fixed-token (512)
2. O que quebraria com splits de 512 tokens nos documentos específicos da NovaTech
3. Como o overlap de 1 frase entre seções adjacentes melhora a qualidade de retrieval
4. Como metadado is_superseded previne contaminação v1/v2
5. O risco de "lost in the middle" e como chunks focados por seção mitigam

---

## Requisitos finais

- Gere o requirements.txt com: chromadb, sentence-transformers, torch
- Copie os 5 arquivos .md do diretório pai para rag_pipeline/documents/
- Todo o código deve ser executável com: cd rag_pipeline && python ingest.py && python test_pipeline.py
- Use nomes de variáveis claros, sem abstrações desnecessárias
- Comentários apenas onde o raciocínio não é óbvio (ex: por que is_superseded=False no filtro ChromaDB)
```

---

## Gabarito de referência (Anexo B)

| Pergunta | Chunks esperados | Armadilha |
|----------|-----------------|-----------|
| TC-01: prazo carga perigosa | POL-001 seções 3.2 e 3.1 | Exceção "NÃO elegível" deve prevalecer sobre regra geral |
| TC-02: SLA Gold chamados gerais | SLA-2024 seção 2 | Não confundir com incidente crítico (30min/4h) |
| TC-03: SLA Platinum | SLA-2024 seção 1 ("não existem outros tiers") | Tier inexistente → recusa informada, não invenção |
| TC-04: frete 600kg Manaus | PROC-042-v2 seções 2.1 e 2 | v1 tem Norte=1.6 (ERRADO), v2 tem Norte=1.8 |
| TC-05: multiplicador Sudeste | PROC-042-v2 seção 2.1 | v1=1.0 vs v2=1.1 — contradição entre versões |

---

## Mapa de tokens do contexto

| Parte do contexto | Tipo | Tokens estimados |
|-------------------|------|-----------------|
| System prompt | Estático | ~400 tokens |
| 5 chunks (~200 tokens cada) | Dinâmico | ~1.000 tokens |
| Pergunta do atendente | Dinâmico | ~20–50 tokens |
| **Total estimado** | | **~1.500 tokens** |

**Nota:** Com budget de ~126K tokens úteis, cabem ~250 chunks de 500 tokens por query. Na prática, 5–10 chunks é o ideal — mais chunks dilui a atenção do modelo e aumenta o risco de trazer versões conflitantes.
