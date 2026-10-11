import pytest

from backend.app.evaluation.retrieval_metrics import (
    evaluate_retrieval,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_recall_at_k_counts_relevant_items_in_top_k():
    assert recall_at_k(["a", "b", "c"], {"b", "c", "d"}, k=2) == pytest.approx(1 / 3)


def test_reciprocal_rank_uses_first_relevant_position():
    assert reciprocal_rank(["x", "y", "z"], {"y", "z"}) == 0.5
    assert reciprocal_rank(["x"], {"missing"}) == 0.0


def test_ndcg_is_one_for_ideal_ranking():
    assert ndcg_at_k(["a", "b", "x"], {"a", "b"}, k=3) == pytest.approx(1.0)


def test_empty_relevance_and_nonpositive_k_are_safe():
    assert recall_at_k(["a"], set(), k=5) == 0.0
    assert ndcg_at_k(["a"], {"a"}, k=0) == 0.0


def test_evaluation_returns_expected_metric_names():
    result = evaluate_retrieval(["irrelevant", "answer"], {"answer"}, k=2)
    assert result == {"recall@2": 1.0, "mrr": 0.5, "ndcg@2": pytest.approx(0.63093)}
