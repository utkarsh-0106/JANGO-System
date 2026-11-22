from types import SimpleNamespace

import pytest

from backend.app.services import lexical_search


def make_chunk(content, user_id=7, document_id=101, **metadata):
    return SimpleNamespace(
        page_content=content,
        metadata={
            "user_id": user_id,
            "document_id": document_id,
            "filename": "policy.pdf",
            "page_number": 3,
            **metadata,
        },
    )


def test_index_and_search_preserve_source_metadata(tmp_path):
    path = tmp_path / "lexical.sqlite3"
    chunks = [
        make_chunk("Employees receive annual paid leave."),
        make_chunk("Annual leave requests require manager approval."),
    ]

    count = lexical_search.replace_document_chunks(101, 7, chunks, path)
    results = lexical_search.keyword_search("annual leave", 7, path=path)

    assert count == 2
    assert len(results) == 2
    assert results[0]["metadata"]["filename"] == "policy.pdf"
    assert results[0]["metadata"]["page_number"] == 3
    assert results[0]["document_id"] == 101


def test_search_enforces_user_isolation(tmp_path):
    path = tmp_path / "lexical.sqlite3"

    lexical_search.replace_document_chunks(
        101, 7, [make_chunk("Confidential payroll information", 7)], path
    )
    lexical_search.replace_document_chunks(
        202, 8, [make_chunk("Confidential payroll information", 8, 202)], path
    )

    user_seven = lexical_search.keyword_search("payroll", 7, path=path)
    user_eight = lexical_search.keyword_search("payroll", 8, path=path)

    assert {row["document_id"] for row in user_seven} == {101}
    assert {row["document_id"] for row in user_eight} == {202}


def test_search_can_be_scoped_to_document_ids(tmp_path):
    path = tmp_path / "lexical.sqlite3"

    lexical_search.replace_document_chunks(
        101, 7, [make_chunk("Company security policy", 7, 101)], path
    )
    lexical_search.replace_document_chunks(
        102, 7, [make_chunk("Company security policy", 7, 102)], path
    )

    results = lexical_search.keyword_search(
        "security policy", 7, document_ids=[102], path=path
    )

    assert {row["document_id"] for row in results} == {102}


def test_replacing_document_chunks_removes_old_content(tmp_path):
    path = tmp_path / "lexical.sqlite3"

    lexical_search.replace_document_chunks(
        101, 7, [make_chunk("Old document retention policy")], path
    )
    lexical_search.replace_document_chunks(
        101, 7, [make_chunk("New employee onboarding policy")], path
    )

    assert lexical_search.keyword_search("retention", 7, path=path) == []
    assert len(lexical_search.keyword_search("onboarding", 7, path=path)) == 1


def test_delete_document_chunks_is_tenant_scoped(tmp_path):
    path = tmp_path / "lexical.sqlite3"

    lexical_search.replace_document_chunks(
        101, 7, [make_chunk("Quarterly finance report", 7)], path
    )
    lexical_search.replace_document_chunks(
        101, 8, [make_chunk("Quarterly finance report", 8)], path
    )

    deleted = lexical_search.delete_document_chunks(101, 7, path)

    assert deleted == 1
    assert lexical_search.keyword_search("finance", 7, path=path) == []
    assert len(lexical_search.keyword_search("finance", 8, path=path)) == 1


def test_invalid_chunk_ownership_is_rejected(tmp_path):
    path = tmp_path / "lexical.sqlite3"

    with pytest.raises(ValueError, match="ownership mismatch"):
        lexical_search.replace_document_chunks(
            101, 7, [make_chunk("Private text", user_id=8)], path
        )


def test_empty_and_punctuation_only_queries_return_no_results(tmp_path):
    path = tmp_path / "lexical.sqlite3"

    assert lexical_search.keyword_search("", 7, path=path) == []
    assert lexical_search.keyword_search("!!! ???", 7, path=path) == []


def test_result_limit_is_bounded(tmp_path):
    path = tmp_path / "lexical.sqlite3"
    chunks = [
        make_chunk(f"Annual leave policy section {number}")
        for number in range(5)
    ]
    lexical_search.replace_document_chunks(101, 7, chunks, path)

    results = lexical_search.keyword_search("annual leave", 7, k=10000, path=path)

    assert len(results) == 5
