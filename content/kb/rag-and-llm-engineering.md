---
title: RAG pipelines and LLM engineering essentials
categories: [rag, llms, vector-databases, ai-agents, llmops]
license: CC-BY-4.0
attribution: CareerPilot AI contributors
---
# A retrieval-augmented generation pipeline

1. **Ingest**: clean documents, split them into chunks (often a few hundred tokens, split on headings, with
   a little overlap), and keep metadata such as the title, URL, licence and access rights.
2. **Index**: store embeddings in a vector index (pgvector, Qdrant, FAISS…) and keep a keyword index too.
3. **Retrieve**: hybrid search (keyword + vector) catches both exact terms (error codes, names) and
   paraphrases. Fuse the rankings (for example reciprocal rank fusion) and optionally rerank the top results.
4. **Generate**: give the model the passages with identifiers and ask it to cite them. Reject citations that
   do not point to a retrieved passage.
5. **Evaluate**: measure retrieval recall@k on labelled queries and answer quality on a fixed dataset;
   compare versions over enough cases and repeated runs before concluding.

# Generation parameters

**Temperature** controls how random token sampling is: low values are more deterministic, high values more
varied and more error-prone. Structured outputs (JSON schema) make model responses easy to validate.

# Agents and tools

Give agents narrow, typed tools with limits (for example `refund(order_id, amount <= 100)`) rather than
generic ones (`run_sql`). Treat retrieved text and user content as untrusted data: it can contain injected
instructions. Make side-effecting tools idempotent, so a retry after a timeout cannot repeat an action, and
require human approval for high-impact actions.
