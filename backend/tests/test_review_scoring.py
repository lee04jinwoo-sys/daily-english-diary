"""Band helpers kept for reviews stored before 2026-11-26 (new reviews have no band scores;
see test_grammar_metrics.py). Overall band = mean of the criteria, rounded the IELTS way."""
from app.services.gemini_service import ielts_overall


def test_ielts_overall_rounding():
    assert ielts_overall([6.5, 6.0, 6.5, 6.0]) == 6.5    # 6.25 -> 6.5
    assert ielts_overall([7.0, 6.5, 6.5, 6.5]) == 6.5    # 6.625 -> 6.5
    assert ielts_overall([7.0, 7.0, 6.5, 6.5]) == 7.0    # 6.75 -> 7.0
    assert ielts_overall([6.0, 6.0, 6.0, 6.5]) == 6.0    # 6.125 -> 6.0
