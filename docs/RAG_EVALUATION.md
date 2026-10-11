# JANGO Retrieval Evaluation

JANGO now includes small, dependency-free retrieval metrics in
`backend/app/evaluation/retrieval_metrics.py`. They are designed for repeatable
experiments comparing retrieval configurations; they do not measure whether an
LLM's final answer is factually correct.

## Metrics

- **Recall@K**: fraction of known relevant document/chunk IDs present in the top K results.
- **MRR**: reciprocal rank of the first relevant result; rewards relevant passages appearing early.
- **NDCG@K**: normalized discounted cumulative gain with binary relevance labels; rewards relevant results near the top.

## How to use

```python
from backend.app.evaluation.retrieval_metrics import evaluate_retrieval

ranked_chunk_ids = ["chunk-17", "chunk-03", "chunk-21"]
ground_truth_ids = {"chunk-03", "chunk-21"}
metrics = evaluate_retrieval(ranked_chunk_ids, ground_truth_ids, k=3)
print(metrics)
```

Build a small, manually reviewed dataset from representative user questions.
For each question, record the relevant source chunk IDs. Run the same questions
against each retrieval strategy and compare average metrics, latency, and cost.
Do not claim a quality improvement until the benchmark has been run and results
have been recorded. Keep test documents synthetic or permissioned, and avoid
committing private user documents.

## Current scope

These utilities provide metric calculation and tests. They do not automatically
run the production retriever or evaluate answer faithfulness yet; those require
an explicit benchmark dataset and a controlled evaluation runner.
