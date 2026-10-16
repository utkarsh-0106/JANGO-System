"""Small, isolated benchmark for Ollama embedding models on multilingual queries.

This evaluates synthetic labeled examples only. It does not read or modify the
production Chroma collection. Pull candidate models with Ollama before running.
"""
import argparse
from collections import defaultdict

from langchain_ollama import OllamaEmbeddings

CASES = [
    {
        "id": "leave_policy",
        "passage": "Employees receive 18 days of paid annual leave each calendar year.",
        "queries": ["How many paid leave days do employees get?", "Employees ko saal mein kitni paid chhutti milti hai?", "कर्मचारियों को साल में कितनी सवैतनिक छुट्टियाँ मिलती हैं?"],
    },
    {
        "id": "security_policy",
        "passage": "All accounts must enable multi-factor authentication before accessing company systems.",
        "queries": ["What authentication is required for system access?", "System access ke liye kaunsi authentication zaroori hai?", "सिस्टम इस्तेमाल करने के लिए कौन-सा प्रमाणीकरण आवश्यक है?"],
    },
    {
        "id": "refund_policy",
        "passage": "Eligible purchases can be refunded within 30 days with proof of purchase.",
        "queries": ["When can an eligible purchase be refunded?", "Eligible purchase ka refund kitne din mein mil sakta hai?", "पात्र खरीदारी का रिफंड कितने दिनों में मिल सकता है?"],
    },
]


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def evaluate(model_name, base_url):
    embeddings = OllamaEmbeddings(model=model_name, base_url=base_url)
    passages = [(case["id"], case["passage"]) for case in CASES]
    passage_vectors = embeddings.embed_documents([text for _, text in passages])
    total = 0
    correct = 0
    by_language = defaultdict(lambda: [0, 0])
    for case in CASES:
        for language_index, query in enumerate(case["queries"]):
            vector = embeddings.embed_query(query)
            ranked = sorted(
                zip((item[0] for item in passages), passage_vectors),
                key=lambda item: cosine(vector, item[1]),
                reverse=True,
            )
            passed = ranked[0][0] == case["id"]
            total += 1
            correct += int(passed)
            by_language[("English", "Hinglish", "Hindi")[language_index]][0] += int(passed)
            by_language[("English", "Hinglish", "Hindi")[language_index]][1] += 1
    print(f"Model: {model_name}")
    print(f"Top-1 accuracy: {correct}/{total} = {correct / total:.1%}")
    for language, (hits, count) in by_language.items():
        print(f"  {language}: {hits}/{count} = {hits / count:.1%}")
    print("Note: synthetic pilot set only; benchmark real, manually labeled JANGO queries before selecting a model.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="nomic-embed-text,qwen3-embedding:0.6b")
    parser.add_argument("--base-url", default="http://localhost:11434")
    args = parser.parse_args()
    for model in [item.strip() for item in args.models.split(",") if item.strip()]:
        try:
            evaluate(model, args.base_url)
        except Exception as exc:
            print(f"Model {model} could not be evaluated: {exc}\n")
