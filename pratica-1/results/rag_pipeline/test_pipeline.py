"""
End-to-end test suite for the NovaTech RAG pipeline.
Run after ingestion: python test_pipeline.py

Each test case:
1. Calls search() with exclude_superseded=True
2. Prints retrieved chunks with scores
3. Computes precision@K (how many expected chunks were recovered)
4. Assembles and prints the full prompt
5. Shows a manual evaluation checklist
"""

from retrieve import search, format_results_table, get_collection_and_model
from assemble import assemble_prompt, print_context_map

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


def _chunk_id_matches(retrieved_id: str, expected_id: str) -> bool:
    """
    Flexible match: expected ids use Anexo-B notation (e.g. "POL-001-3.2")
    while generated ids append chunk_index (e.g. "POL-001-3.2-0").
    A retrieved id matches if it starts with the expected prefix.
    """
    return retrieved_id.startswith(expected_id)


def _precision_at_k(retrieved: list[dict], expected_ids: list[str]) -> tuple[int, int]:
    """Return (hits, total_expected) where hits = expected chunks found in retrieved."""
    hits = 0
    for exp_id in expected_ids:
        for r in retrieved:
            if _chunk_id_matches(r["chunk_id"], exp_id):
                hits += 1
                break
    return hits, len(expected_ids)


def run_test(tc: dict, collection, model) -> dict:
    """Execute one test case and return metrics."""
    print(f"\n{'='*70}")
    print(f"  {tc['id']} — {tc['question']}")
    print(f"{'='*70}")
    print(f"  Expected answer key : {tc['expected_answer_key']}")
    print(f"  Trap to avoid       : {tc['trap']}")

    results = search(
        query=tc["question"],
        collection=collection,
        model=model,
        top_k=5,
        exclude_superseded=True,
        min_score=0.2,
    )

    print(f"\n  --- Retrieved chunks (top {len(results)}) ---")
    print(format_results_table(results))

    print(f"  --- Expected chunks (gabarito) ---")
    for exp in tc["expected_chunks"]:
        found = any(_chunk_id_matches(r["chunk_id"], exp) for r in results)
        status = "✓" if found else "✗ MISSING"
        print(f"    {status}  {exp}")

    hits, total = _precision_at_k(results, tc["expected_chunks"])
    precision = hits / total if total > 0 else 0.0
    print(f"\n  Precision@5: {hits}/{total} = {precision:.0%}")

    # Check for superseded leakage — should never happen with exclude_superseded=True
    leaked = [r for r in results if r.get("is_superseded")]
    superseded_ok = len(leaked) == 0

    print(f"\n  --- Assembled prompt ---")
    print_context_map(tc["question"], results)
    prompt = assemble_prompt(tc["question"], results)
    # Print truncated for readability; full prompt is what the LLM would receive
    preview_lines = prompt.split("\n")[:40]
    print("  (first 40 lines of prompt)\n")
    for line in preview_lines:
        print(f"  {line}")
    if len(prompt.split("\n")) > 40:
        print(f"  ... [{len(prompt.split(chr(10))) - 40} more lines]")

    print(f"\n  --- Checklist de avaliação manual ---")
    print(f"  [ ] Chunks corretos recuperados?           ({hits}/{total} found)")
    print(f"  [ ] Gabarito coberto pelos chunks?         (verifique o texto dos chunks acima)")
    print(f"  [ ] Armadilha evitada?                     ({tc['trap']})")
    print(f"  [ ] Nenhum chunk superseded vazou?         ({'✓ ok' if superseded_ok else '✗ FALHOU — chunks v1 vazaram!'})")

    return {
        "id": tc["id"],
        "question_short": tc["question"][:40],
        "expected_chunks": tc["expected_chunks"],
        "hits": hits,
        "total": total,
        "precision": precision,
        "superseded_leaked": not superseded_ok,
    }


def print_summary_table(metrics: list[dict]) -> None:
    print(f"\n{'='*70}")
    print("  SUMMARY TABLE")
    print(f"{'='*70}")
    header = f"  {'TC':<6} {'Pergunta (curta)':<42} {'Esperados':<12} {'Recuperados ✓':<14} {'Score'}"
    print(header)
    print(f"  {'-'*6} {'-'*42} {'-'*12} {'-'*14} {'-'*6}")
    for m in metrics:
        leaked_tag = " ⚠v1!" if m["superseded_leaked"] else ""
        print(
            f"  {m['id']:<6} {m['question_short']:<42} {str(m['expected_chunks']):<12} "
            f"{m['hits']}/{m['total']}{' '*(12-len(str(m['hits'])+'/'+str(m['total'])))} "
            f"{m['precision']:.0%}{leaked_tag}"
        )
    print()


def problems_found() -> list[dict]:
    """
    Placeholder structure for documenting problems observed during test runs.
    Fill in 'observed' and 'root_cause' after running the pipeline.
    """
    return [
        {
            "id": 1,
            "title": "Split no meio da tabela de multiplicadores do PROC-042",
            "test_case": "TC-04 / TC-05",
            "observed": "[preencher após execução]",
            "expected": "Chunk PROC-042-v2-2.1 deve conter a tabela completa de multiplicadores regionais",
            "root_cause": "[preencher após execução]",
            "impact": "[preencher após execução]",
            "fix": "Garantir que o header '### 2.1.' e seu corpo (incluindo tabela Markdown) permaneçam no mesmo chunk",
            "difficulty": "Baixa",
        },
        {
            "id": 2,
            "title": "Vazamento de chunks v1 se filtro is_superseded falhar",
            "test_case": "TC-04 / TC-05",
            "observed": "[preencher após execução]",
            "expected": "Nenhum chunk do PROC-042 v1 deve aparecer nos resultados",
            "root_cause": "[preencher após execução]",
            "impact": "LLM receberia multiplicador Norte 1.6 (v1) em vez de 1.8 (v2), gerando cotação incorreta",
            "fix": "Verificar que ChromaDB where-filter usa bool False, não string 'False'",
            "difficulty": "Baixa",
        },
    ]


def main():
    print("\n=== NovaTech RAG — Test Pipeline ===")
    print("Loading collection and model...\n")

    collection, model = get_collection_and_model()

    all_metrics = []
    for tc in TEST_CASES:
        metrics = run_test(tc, collection, model)
        all_metrics.append(metrics)

    print_summary_table(all_metrics)

    problems = problems_found()
    print("=== Known / Probable Problems (pre-populated placeholders) ===\n")
    for p in problems:
        print(f"  Problema {p['id']}: {p['title']}")
        print(f"    Test case : {p['test_case']}")
        print(f"    Fix       : {p['fix']}")
        print(f"    Difficulty: {p['difficulty']}\n")


if __name__ == "__main__":
    main()
