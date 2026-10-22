from graphmind.extract import extract_all, parse_json_object
from graphmind.graph import build_graph, entity_key
from graphmind.pdf import Page, chunk_pages, read_pages
from graphmind.retrieve import GraphRetriever

from conftest import PAGES, FakeLLM, ent


def build(pdf_bytes, fake_llm, chunk_chars=120):
    pages, _ = read_pages(pdf_bytes, max_pages=50)
    chunks = chunk_pages(pages, chunk_chars)
    return build_graph(extract_all(fake_llm, chunks, workers=2), pages), chunks


def test_reads_every_page(pdf_bytes):
    pages, total = read_pages(pdf_bytes, max_pages=50)
    assert total == 3
    assert [p.number for p in pages] == [1, 2, 3]
    assert "Lehman Brothers filed for bankruptcy" in pages[1].text


def test_max_pages_limits_reading(pdf_bytes):
    pages, total = read_pages(pdf_bytes, max_pages=2)
    assert total == 3 and len(pages) == 2


def test_rejects_non_pdf():
    import pytest

    from graphmind.pdf import PDFError

    with pytest.raises(PDFError):
        read_pages(b"hello", 10)


def test_chunks_cover_whole_document_with_page_spans():
    pages = [Page(i, f"page {i} " + "x" * 900) for i in range(1, 11)]
    chunks = chunk_pages(pages, chunk_chars=2000)
    assert len(chunks) > 1
    covered = [n for c in chunks for n in range(c.first_page, c.last_page + 1)]
    assert sorted(set(covered)) == list(range(1, 11))
    assert all(f"[Page {c.first_page}]" in c.text for c in chunks)


def test_oversized_page_is_split_not_truncated():
    big = "\n\n".join(f"paragraph {i} " + "y" * 400 for i in range(20))
    chunks = chunk_pages([Page(7, big)], chunk_chars=1000)
    assert len(chunks) > 1
    assert all(c.first_page == c.last_page == 7 for c in chunks)
    assert "paragraph 19" in chunks[-1].text


def test_each_chunk_is_sent_to_the_llm(pdf_bytes, fake_llm):
    _, chunks = build(pdf_bytes, fake_llm)
    assert len(chunks) == 3
    assert len(fake_llm.calls) == 3


def test_entities_merge_across_chunks_via_aliases(pdf_bytes, fake_llm):
    kg, _ = build(pdf_bytes, fake_llm)
    # "Federal Reserve" (alias "Fed") and "The Fed" from another chunk become one node.
    fed = [n for n in kg.nodes.values() if entity_key(n.id) in ("federal reserve", "fed")]
    assert len(fed) == 1
    assert fed[0].mentions == 2
    lehman = kg.nodes["Lehman Brothers"]
    assert lehman.mentions == 2
    assert lehman.description == "An investment bank."


def test_generic_alias_does_not_merge_distinct_entities():
    llm = FakeLLM({"x": {"entities": [ent("Bank of America", aliases=["bank"]), ent("Bank of England", aliases=["bank"])]}})
    pages = [Page(1, "x Bank of America and Bank of England")]
    kg = build_graph(extract_all(llm, chunk_pages(pages, 1000), 1), pages)
    assert {"Bank of America", "Bank of England"} <= set(kg.nodes)


def test_pages_come_from_the_text_not_the_model(pdf_bytes, fake_llm):
    kg, _ = build(pdf_bytes, fake_llm)
    assert kg.nodes["Lehman Brothers"].pages == [1, 2]
    assert kg.nodes["AIG"].pages == [3]


def test_evidence_quotes_are_verified_against_the_source(pdf_bytes, fake_llm):
    kg, _ = build(pdf_bytes, fake_llm)
    by_rel = {e.relation: e for e in kg.edges}
    regulates = by_rel["regulates"].evidence[0]
    assert regulates.verified and regulates.page == 1
    invented = by_rel["rescued"].evidence[0]
    assert not invented.verified and invented.page is None


def test_relation_to_unlisted_entity_keeps_the_fact():
    llm = FakeLLM({"x": {"entities": [ent("Alpha")], "relations": [{"source": "Alpha", "target": "Beta", "relation": "owns", "evidence": ""}]}})
    pages = [Page(1, "x Alpha owns Beta")]
    kg = build_graph(extract_all(llm, chunk_pages(pages, 1000), 1), pages)
    assert "Beta" in kg.nodes and kg.edges[0].target == "Beta"


def test_retriever_ranks_by_meaning_not_first_substring(pdf_bytes, fake_llm):
    kg, _ = build(pdf_bytes, fake_llm)
    r = GraphRetriever(kg)
    assert r.find_nodes("Who sold credit default swaps?")[0] == "AIG"
    assert r.find_pages("when did lehman go bankrupt", k=1) == [2]


def test_parse_json_handles_fences_think_tags_and_truncation():
    assert parse_json_object('<think>hmm</think>```json\n{"a": [1, 2,]}\n```') == {"a": [1, 2]}
    assert parse_json_object('{"entities": [{"name": "A"}, {"name": "B') == {"entities": [{"name": "A"}, {"name": "B"}]}
    assert parse_json_object("no json here") is None


def test_failed_chunk_is_reported_not_fatal():
    class Flaky(FakeLLM):
        def complete(self, system, user, **kw):
            return "garbage" if "page two" in user else super().complete(system, user, **kw)

    llm = Flaky({"page one": {"entities": [ent("One")]}})
    chunks = chunk_pages([Page(1, "page one"), Page(2, "page two")], chunk_chars=10)
    results = extract_all(llm, chunks, 2)
    assert [r.error is None for r in results] == [True, False]


def test_page_text_fixture_is_consistent():
    assert len(PAGES) == 3
