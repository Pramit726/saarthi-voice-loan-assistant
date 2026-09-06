from saarthi.domain.contracts import ProductFact
from saarthi.services.knowledge_compiler import KnowledgeCompiler


def candidate(identifier: str) -> ProductFact:
    return ProductFact(
        fact_id=identifier,
        product_id="SPL-DEMO-01",
        product_version="1.1",
        fact_set_version="1.1",
        status="draft",
        fact_type="cost",
        topic="fee",
        text="The synthetic processing fee is 2 percent.",
        numeric_values={"processing_fee_percent": 2},
        source_section="Fees",
    )


def test_compiler_output_remains_draft_until_explicit_approval():
    facts = [candidate("FACT-1"), candidate("FACT-2")]
    approved = KnowledgeCompiler.approve(facts, approved_ids={"FACT-1"})
    assert approved[0].status == "approved"
    assert approved[1].status == "draft"


def test_duplicate_fact_ids_are_rejected():
    import pytest

    with pytest.raises(ValueError, match="unique"):
        KnowledgeCompiler.validate_candidates([candidate("FACT-1"), candidate("FACT-1")])
