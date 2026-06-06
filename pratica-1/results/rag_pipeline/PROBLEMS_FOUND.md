# PROBLEMS_FOUND.md — Problemas Identificados no Pipeline de RAG

> Atualizado com resultados reais da execução de `python test_pipeline.py`.

---

**Problema 1: TC-01 — FAQ supera POL-001 no ranking para query sobre "carga perigosa"**

- Pergunta de teste: TC-01 — "Qual o prazo de devolução para carga perigosa?"
- Observado: Os chunks recuperados foram `FAQ-item-3` (score 0.6730), `POL-001-3.5` (0.6388), `FAQ-item-22` (0.6241), `FAQ-item-32` (0.5948). Os chunks esperados `POL-001-3.2` e `POL-001-3.1` **não apareceram no top-5**.
- Esperado (gabarito Anexo B): POL-001-B (seção 3.2) e POL-001-A (seção 3.1) deveriam ser os primeiros resultados, pois são as fontes normativas da política de exceções.
- Causa raiz: O chunk `FAQ-item-3` menciona explicitamente "carga perigosa", "ramal 4500" e "processo padrão" — vocabulário que coincide diretamente com a query. O chunk `POL-001-3.2` usa linguagem formal ("cargas perigosas classificadas nas classes 1 a 6 da ANTT") que o modelo `all-MiniLM-L6-v2` mapeou em embedding ligeiramente diferente da query coloquial. Além disso, o FAQ-item-3 recebeu o overlap da seção anterior (item-22 sobre seguros), o que pode ter inflado seu espaço semântico. Resultado: precisão@5 = **0/2 = 0%** para este caso.
- Impacto na resposta: O LLM receberia o FAQ-item-3 como fonte principal. O FAQ contém a resposta correta ("ramal 4500", "não pode pelo processo padrão"), mas é fonte **informal e não validada por Compliance**. O guardrail de citação de fontes estaria correto (`FAQ, item-3`), mas o atendente poderia ter dúvidas sobre a confiabilidade. O chunk POL-001-3.2 (que lista as classes ANTT específicas, ex: explosivos classe 1, gases classe 2) não estaria disponível para o LLM — perdendo o nível de detalhe normativo.
- Correção proposta: Adicionar re-ranking por `source_type` (bonus de score para `policy` e `sla` vs `faq`) antes de retornar os top-K resultados. Alternativa: adicionar "POL-001, seção 3.2" como campo de metadado no próprio texto do chunk (keyword anchoring), melhorando o recall semântico.
- Dificuldade de correção: **Média** — requer camada de re-ranking pós-retrieval em `retrieve.py`.

---

**Problema 2: Overlap injeta conteúdo irrelevante nos chunks FAQ**

- Pergunta de teste: TC-03 — "Qual o SLA do cliente Platinum?" e TC-01
- Observado: O chunk `FAQ-item-15` começa com: "Na dúvida, use a mais recente (v2), mas se o cliente reclamar do valor, pode ser que o contrato dele ainda esteja na tabela antiga." — esse texto é da última frase do item 8 (sobre frete), não do item 15 (sobre Platinum). O overlap de 1 frase trouxe conteúdo sobre **frete** para dentro de um chunk sobre **tiers de cliente**.
- Esperado: O overlap deveria inserir contexto relevante da seção anterior. No FAQ, itens não têm relação temática entre si — item 8 fala de frete e item 15 fala de tiers. O overlap entre itens não-relacionados polui o chunk.
- Causa raiz: A estratégia de overlap de 1 frase foi projetada para documentos com seções sequencialmente relacionadas (ex: POL-001 onde §3.1 → §3.2 são regra e exceção da mesma política). O FAQ é uma coleção de perguntas independentes — não há relação semântica entre itens adjacentes. O overlap no FAQ é **sempre ruído**.
- Impacto na resposta: Para TC-03, o FAQ-item-15 ficou em rank 1 com score 0.6155, o que é o comportamento correto — mas o texto inicial do chunk ("Na dúvida, use a mais recente (v2)...") poderia confundir o LLM fazendo-o citar frete no contexto de Platinum. Para TC-01, o FAQ-item-3 ficou no rank 1 com score 0.6730 em parte porque o overlap de um item sobre "5 dias em trânsito" acrescentou menção à "rota Norte" que pode ter aumentado levemente o score para a query "carga perigosa Norte".
- Correção proposta: Desabilitar overlap (`CHUNK_OVERLAP_SENTENCES = 0`) para documentos com `source_type = "faq"`. Implementar em `split_into_chunks()` verificando `doc["source_type"] == "faq"` antes de aplicar `prev_last_sentence`.
- Dificuldade de correção: **Baixa** — if de uma linha no loop de chunking.

---

**Problema 3 (potencial, não observado): Vazamento de chunks v1 se filtro is_superseded falhar**

- Pergunta de teste: TC-04 e TC-05
- Observado: **Não ocorreu** — zero chunks v1 vazaram. Todos os 5 resultados de TC-04 e TC-05 são de PROC-042-v2 ou outras fontes. O filtro funcionou corretamente.
- Esperado: Comportamento correto — PROC-042 v1 (Norte=1.6) nunca apareceu; PROC-042-v2 (Norte=1.8) foi corretamente ranqueado como top-2 em TC-04 e top-1 em TC-05.
- Causa raiz do risco (latente): ChromaDB requer que o metadata `is_superseded` seja salvo como `bool` nativo Python, não como `str`. O código em `embed_and_store()` passa o valor diretamente do dict Python — correto. Se alguém modificar o código para serializar metadados como JSON strings antes de salvar (ex: `json.dumps(metadata)`), o filtro `{"is_superseded": {"$eq": False}}` quebraria silenciosamente.
- Impacto se ocorresse: LLM receberia Norte=1.6 (v1) e Norte=1.8 (v2) no mesmo contexto. Cotação ~11% mais barata que o correto.
- Correção proposta: Adicionar assertion no `main()` após ingestão: `assert all(isinstance(c["is_superseded"], bool) for c in all_chunks)`. E teste de sanidade consultando `collection.get(where={"is_superseded": {"$eq": True}})` e verificando que retorna exatamente os 5 chunks do PROC-042 v1.
- Dificuldade de correção: **Baixa**.
