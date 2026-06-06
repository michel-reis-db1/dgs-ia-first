# CHUNKING_JUSTIFICATION.md — Justificativa da Estratégia de Chunking

## 1. Por que chunking por seção em vez de fixed-token (512)?

Chunking por tamanho fixo (ex: 512 tokens) divide o texto em janelas de comprimento constante, sem levar em conta a estrutura lógica do documento. Para documentos técnicos como os da NovaTech, isso cria dois problemas graves:

**a) Quebra de tópicos coerentes.** Uma seção como "3.2. Exceções ao prazo geral" (POL-001) tem ~120 palavras. Com janelas de 512 tokens, ela seria agrupada com o início da seção 3.3 — colocando regras de exceção e procedimento de devolução no mesmo chunk. Uma query sobre "exceções" recuperaria ruído da seção de procedimento, e vice-versa.

**b) Fragmentação de tabelas.** As tabelas de multiplicadores regionais do PROC-042 têm 5 linhas (Sul, Sudeste, Centro-Oeste, Nordeste, Norte). Com fixed-token, dependendo do offset, a tabela pode ser cortada na linha 3 — um chunk conteria "Sul: 1.3, Sudeste: 1.1, Centro-Oeste: 1.4" e o próximo "Nordeste: 1.5, Norte: 1.8". Uma query "multiplicador Norte" recuperaria o segundo chunk, mas sem o contexto completo da tabela seria impossível validar se o valor está correto.

Chunking por seção resolve ambos: cada chunk é delimitado pelo header markdown (`##` ou `###`), garantindo que um tópico = um chunk.

---

## 2. O que quebraria com splits de 512 tokens nos documentos da NovaTech

| Documento | Problema específico com 512 tokens |
|-----------|-------------------------------------|
| POL-001 §3.2 | Exceções ao prazo geral (cargas perigosas, refrigeradas, lacre violado) seriam divididas em 2+ chunks. Query "carga perigosa" recuperaria chunk incompleto — sem o ramal 4500 para tratamento individual. |
| PROC-042-v2 §2.1 | Tabela de multiplicadores regionais (5 regiões × 2 colunas) seria cortada no meio. Dependendo do offset, "Norte: 1.8" poderia ficar em chunk diferente da fórmula de cálculo. |
| SLA-2024 §2 | A tabela de SLAs tem 7 linhas de métricas × 3 tiers. Com 512 tokens, a tabela completa estaria em ~1 chunk — mas a nota crucial "Não existem outros tiers além dos três listados" está na §1 e seria separada da tabela, enfraquecendo o guardrail contra tier Platinum inventado. |
| FAQ-atendimento | O FAQ é uma lista de itens numerados. Com fixed-token, items adjacentes (ex: item 8 sobre frete e item 15 sobre Platinum) seriam agrupados no mesmo chunk, contaminando queries focadas. |

---

## 3. Como o overlap de 1 frase entre seções adjacentes melhora o retrieval

**O problema do "cliff-hanger" de seção.** Às vezes uma seção começa com uma referência implícita ao que veio antes. Exemplo em POL-001:

> §3.1: "O cliente pode solicitar a devolução em até 7 dias úteis..."
> §3.2: "As seguintes categorias NÃO são elegíveis..." ← sem contexto, "elegíveis" para quê?

Se o chunk de §3.2 não tiver referência ao prazo de 7 dias, uma query sobre "prazo de carga perigosa" pode recuperar §3.2 (correto) mas sem o contexto de §3.1, o LLM não saberia que "não elegível" significa "não se aplica o prazo de 7 dias".

**Como o overlap resolve.** A última frase de §3.1 ("A contagem de dias úteis exclui sábados, domingos e feriados nacionais") é inserida no início do chunk de §3.2. Isso ancora o chunk de exceções ao contexto do prazo geral, sem duplicar o chunk inteiro.

**Trade-off.** O overlap de 1 frase introduz ~10-20 tokens extras por chunk (~10% de overhead para chunks de ~150 tokens). Esse custo é trivial frente ao benefício de coerência semântica.

---

## 4. Como o metadado is_superseded previne contaminação v1/v2

**O problema.** PROC-042 v1 e v2 têm conteúdo semanticamente muito similar (mesma fórmula, mesmo domínio, tabelas com mesmo formato). O modelo `all-MiniLM-L6-v2` não tem conhecimento temporal — um embedding de "Norte 1.6" e "Norte 1.8" são quase idênticos em similaridade coseno, já que diferem apenas no valor numérico.

**Por que filtro semântico não resolve.** Não há como distinguir v1 de v2 apenas por similaridade de embedding. Qualquer abordagem baseada só em score de similaridade retornaria chunks de ambas as versões.

**Por que is_superseded resolve.** O filtro é aplicado **antes** do ranking de similaridade, no nível do índice vetorial (ChromaDB where-clause). Chunks com `is_superseded=True` são excluídos do espaço de busca — não são nem ranqueados. É uma garantia estrutural, não probabilística.

**Detalhe de implementação crítico.** O ChromaDB armazena metadados como tipos primitivos. O filtro `{"is_superseded": {"$eq": False}}` só funciona se o valor foi armazenado como bool Python nativo (`False`), não como string `"False"`. O código em `embed_and_store()` passa o valor diretamente do dict Python, garantindo o tipo correto.

---

## 5. O risco de "lost in the middle" e como chunks focados por seção mitigam

**O problema.** Pesquisas sobre comportamento de LLMs com contextos longos (Liu et al., 2023 — "Lost in the Middle") mostram que modelos têm dificuldade em recuperar informações posicionadas no meio de uma janela de contexto longa. Informações no início e no fim do contexto são mais frequentemente utilizadas.

**Cenário concreto na NovaTech.** Se enviássemos o documento POL-001 inteiro como contexto (49 linhas, ~600 palavras), a exceção crítica da §3.2 ("cargas perigosas NÃO são elegíveis") ficaria no meio do documento — entre o Objetivo (§1) e o Procedimento (§3.3). Há risco real de o LLM responder usando a regra geral de 7 dias (§3.1, início do documento) e ignorar a exceção da §3.2.

**Como chunks por seção mitigam.** Quando a query é "prazo de devolução para carga perigosa", o retrieval retorna §3.2 (exceção) e §3.1 (regra geral) como chunks separados, posicionados no início do contexto. A exceção não está "enterrada" — ela é o primeiro ou segundo chunk que o LLM lê. Além disso, o SYSTEM_PROMPT contém a instrução explícita: "EXCEÇÕES prevalecem sobre regras gerais — leia o chunk completo antes de responder."

**Resultado.** Chunks curtos e focados (1 seção = 1 tópico, ~150-300 tokens cada) reduzem o tamanho total do contexto e posicionam as informações mais relevantes no início da janela — o ponto de maior atenção dos modelos transformer.
