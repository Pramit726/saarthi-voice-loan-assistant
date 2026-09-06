from decimal import Decimal

from saarthi.domain.contracts import FinancialProjection
from saarthi.domain.policies import ResponseGuard
from saarthi.services.renderer import ListenerRenderer


def projection() -> FinancialProjection:
    return FinancialProjection(
        source_application_revision=2,
        product_id="SPL-DEMO-01",
        product_version="1.1",
        fact_set_version="1.1",
        calculator_version="test",
        requested_amount=Decimal("100000.00"),
        annual_interest_rate_percent=Decimal("12.50"),
        tenure_months=12,
        processing_fee=Decimal("2000.00"),
        tax_on_processing_fee=Decimal("360.00"),
        total_deduction=Decimal("2360.00"),
        net_disbursal=Decimal("97640.00"),
        emi=Decimal("8908.29"),
        total_repayment=Decimal("106899.44"),
        total_interest=Decimal("6899.44"),
    )


def test_written_and_spoken_plans_share_projection_values():
    renderer = ListenerRenderer()
    item = projection()
    plan = renderer.projection_plan(item)
    plan = ResponseGuard().evaluate(plan, financial_response=True)
    segments = renderer.render(plan, generation_id=7)
    written = renderer.written_projection(item)
    assert segments
    assert plan.labelled_values["emi"] == written["emi"]
    assert plan.labelled_values["net_disbursal"] == written["net_disbursal"]
    assert all(segment.generation_id == 7 for segment in segments)


def test_listener_renderer_splits_dense_summary_into_short_segments():
    renderer = ListenerRenderer()
    plan = ResponseGuard().evaluate(
        renderer.projection_plan(projection()), financial_response=True
    )
    segments = renderer.render(plan, generation_id=1)
    assert len(segments) >= 8
    assert max(len(segment.text.split()) for segment in segments) < 25


def test_financial_plan_contains_draft_disclosure():
    plan = ListenerRenderer().projection_plan(projection())
    assert any("not been submitted" in segment for segment in plan.message_segments)
