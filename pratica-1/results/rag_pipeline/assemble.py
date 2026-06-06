"""
Prompt assembly: combines system prompt + retrieved chunks + user query.
"""

SYSTEM_PROMPT = """
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
""".strip()


def estimate_tokens(text: str) -> int:
    """Simple estimate: word count × 1.33 (accounts for subword tokenization overhead)."""
    return int(len(text.split()) * 1.33)


def assemble_prompt(query: str, chunks: list[dict], include_system: bool = True) -> str:
    """
    Build the full prompt: [system] + [retrieved chunks block] + [user query].

    Token budget (approximate):
    - System prompt : ~400 tokens  (static)
    - Each chunk    : ~150-300 tokens (dynamic, depends on section length)
    - Query         : ~20-50 tokens  (dynamic)
    - Total (5 chunks): ~1,400-2,000 tokens  (well within 128K context)
    """
    parts = []

    if include_system:
        parts.append(f"<system>\n{SYSTEM_PROMPT}\n</system>")

    if chunks:
        chunk_lines = ["<context>"]
        for i, c in enumerate(chunks, 1):
            superseded_warning = ""
            if c.get("is_superseded"):
                superseded_warning = "\n⚠ ATENÇÃO: Este chunk é de documento SUPERSEDED (versão antiga)."

            chunk_lines.append(
                f"\n--- Chunk {i} ---\n"
                f"document_id: {c.get('document_id')} | version: {c.get('version')} | "
                f"section: {c.get('section')} | source_type: {c.get('source_type')}\n"
                f"section_title: {c.get('section_title')}"
                f"{superseded_warning}\n\n"
                f"{c.get('text', '')}"
            )
        chunk_lines.append("\n</context>")
        parts.append("\n".join(chunk_lines))

    parts.append(f"<user_query>\n{query}\n</user_query>")

    return "\n\n".join(parts)


def print_context_map(query: str, chunks: list[dict]) -> None:
    """Print anatomy of the assembled context with token estimates per part."""
    system_tokens = estimate_tokens(SYSTEM_PROMPT)
    query_tokens = estimate_tokens(query)

    print("\n=== Context Map ===")
    print(f"  [STATIC]  System prompt   : ~{system_tokens} tokens")
    print(f"  [DYNAMIC] User query      : ~{query_tokens} tokens")

    total_chunk_tokens = 0
    for i, c in enumerate(chunks, 1):
        t = estimate_tokens(c.get("text", ""))
        total_chunk_tokens += t
        superseded_tag = " ⚠ SUPERSEDED" if c.get("is_superseded") else ""
        print(
            f"  [DYNAMIC] Chunk {i} ({c.get('document_id')}-{c.get('section')})"
            f"{superseded_tag}: ~{t} tokens"
        )

    total = system_tokens + query_tokens + total_chunk_tokens
    print(f"  {'─'*40}")
    print(f"  TOTAL ESTIMATED           : ~{total} tokens")
    print(f"  (128K context budget used : {total/128000*100:.2f}%)\n")
