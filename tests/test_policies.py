def test_returns_right_of_withdrawal_section(policy_index):
    results = policy_index.search("quero devolver minha compra")
    assert results
    assert results[0]["section"] == "4.1"


def test_defect_query_hits_defect_and_warranty_sections(policy_index):
    results = policy_index.search("o produto veio com defeito")
    sections = {r["section"] for r in results}
    assert "4.2" in sections


def test_installments_query_hits_section_3_1(policy_index):
    results = policy_index.search("posso parcelar em quantas vezes?")
    assert results[0]["section"] == "3.1"


def test_opening_hours_query_hits_section_2(policy_index):
    results = policy_index.search("que horas vocês abrem?")
    assert results[0]["section"] == "2"


def test_address_query_hits_section_1_2(policy_index):
    results = policy_index.search("qual o endereço da loja?")
    assert results[0]["section"] == "1.2"


def test_strings_query_hits_scope_or_accessories_sections(policy_index):
    results = policy_index.search("vocês vendem corda?")
    sections = {r["section"] for r in results}
    assert sections & {"1", "7.1"}


def test_nonsense_query_returns_empty(policy_index):
    assert policy_index.search("qual a capital da frança?") == []
    assert policy_index.search("receita de bolo de chocolate") == []


def test_chunks_have_editorial_notes_where_expected(policy_index):
    by_section = {c["section"]: c for c in policy_index.chunks}
    assert "note" in by_section["1.2"]
    assert "note" in by_section["3"]
    assert "note" in by_section["4.2"]
    assert "note" in by_section["5.1"]
