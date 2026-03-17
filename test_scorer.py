"""
Tests for APEX PriorityScorer
Run with: python -m pytest tests/
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scorer import PriorityScorer


def make_task(name, impact, effort, alignment, has_deps=False):
    return {
        "name": name,
        "user_impact": impact,
        "effort": effort,
        "strategic_alignment": alignment,
        "has_dependencies": has_deps,
        "dependency_note": ""
    }


scorer = PriorityScorer()


def test_max_score():
    """Perfect task: max impact, min effort (1), max alignment, no deps.
    Max = ((10*0.45) + (10*0.30) + (9*0.25)) * 1000 = 9,750
    Note: effort min is 1 (hours), not 0 — so inverted max = 9, not 10.
    """
    task = make_task("Perfect", impact=10, effort=1, alignment=10)
    score = scorer.score(task)
    assert score == 9_750, f"Expected 9750, got {score}"


def test_min_score():
    """Worst task: no impact, max effort, no alignment, blocked."""
    task = make_task("Worst", impact=1, effort=10, alignment=1, has_deps=True)
    score = scorer.score(task)
    assert score < 1_500, f"Expected < 1500, got {score}"


def test_dependency_penalty():
    """Dependency should reduce score by 25%."""
    task_free = make_task("Free", impact=8, effort=4, alignment=8, has_deps=False)
    task_blocked = make_task("Blocked", impact=8, effort=4, alignment=8, has_deps=True)
    score_free = scorer.score(task_free)
    score_blocked = scorer.score(task_blocked)
    assert score_blocked == round(score_free * 0.75), \
        f"Penalty not applied: {score_free} vs {score_blocked}"


def test_effort_inverted():
    """Higher effort = lower score."""
    easy = make_task("Easy", impact=7, effort=2, alignment=7)
    hard = make_task("Hard", impact=7, effort=9, alignment=7)
    assert scorer.score(easy) > scorer.score(hard)


def test_impact_dominates():
    """Impact (45%) should outweigh alignment (30%) and effort (25%)."""
    high_impact = make_task("HighImpact", impact=10, effort=5, alignment=5)
    high_align  = make_task("HighAlign",  impact=5,  effort=5, alignment=10)
    assert scorer.score(high_impact) > scorer.score(high_align)


def test_score_range():
    """All scores should be between 0 and 10,000."""
    import random
    for _ in range(100):
        task = make_task(
            "Random",
            impact=random.randint(1, 10),
            effort=random.randint(1, 10),
            alignment=random.randint(1, 10),
            has_deps=random.choice([True, False])
        )
        score = scorer.score(task)
        assert 0 <= score <= 10_000, f"Score out of range: {score}"


def test_methodology_returned():
    """Scorer must return full methodology dict with correct max score."""
    m = scorer.get_methodology()
    assert "formula" in m
    assert "weights" in m
    assert "penalties" in m
    assert "max_score" in m
    assert m["max_score"] == 9_750, f"Expected max_score=9750, got {m['max_score']}"
    assert "max_score_note" in m  # Must explain why it's not 10,000
