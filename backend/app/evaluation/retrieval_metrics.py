"""Small, dependency-free metrics for evaluating ranked retrieval results.

Expected inputs are chunk/document IDs in ranked order and a set of relevant IDs
for a query. These metrics evaluate retrieval, not the factual quality of the
LLM's final answer.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


def recall_at_k(ranked_ids: Sequence[str], relevant_ids: Iterable[str], k: int = 5) -> float:
    """Fraction of known relevant IDs retrieved in the first k results."""
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    if k <= 0:
        return 0.0
    return len(set(ranked_ids[:k]) & relevant) / len(relevant)


def reciprocal_rank(ranked_ids: Sequence[str], relevant_ids: Iterable[str]) -> float:
    """Reciprocal rank of the first relevant result, or zero if absent."""
    relevant = set(relevant_ids)
    for rank, item_id in enumerate(ranked_ids, start=1):
        if item_id in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(ranked_ids: Sequence[str], relevant_ids: Iterable[str], k: int = 5) -> float:
    """Binary-relevance NDCG@k; useful when relevance labels are yes/no."""
    relevant = set(relevant_ids)
    if k <= 0 or not relevant:
        return 0.0

    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, item_id in enumerate(ranked_ids[:k], start=1)
        if item_id in relevant
    )
    ideal_hits = min(len(relevant), k)
    ideal_dcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / ideal_dcg if ideal_dcg else 0.0


def evaluate_retrieval(
    ranked_ids: Sequence[str], relevant_ids: Iterable[str], k: int = 5
) -> dict[str, float]:
    """Return a stable metric dictionary for a single query."""
    relevant = list(set(relevant_ids))
    return {
        f"recall@{k}": round(recall_at_k(ranked_ids, relevant, k), 6),
        "mrr": round(reciprocal_rank(ranked_ids, relevant), 6),
        f"ndcg@{k}": round(ndcg_at_k(ranked_ids, relevant, k), 6),
    }
