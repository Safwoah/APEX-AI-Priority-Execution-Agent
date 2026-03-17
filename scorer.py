"""
APEX Priority Scorer
Converts task attributes into a 1–9,750 priority score.

Scoring Philosophy:
  The score answers: "If you could only build ONE thing, what creates the most value fastest?"
  It penalizes high-effort tasks, rewards high-impact + strategic ones,
  and applies a dependency penalty since blocked tasks can't ship first.
"""


class PriorityScorer:
    """
    Score Formula (max = 9,750):

    BASE_SCORE = (
        (user_impact         * WEIGHT_IMPACT)     # How much users feel this
      + (strategic_alignment * WEIGHT_ALIGN)      # Does this unlock future features?
      + ((10 - effort)       * WEIGHT_EFFORT)     # Inverted: lower effort = higher score
    ) * SCALE

    Why max is 9,750 and not 10,000:
      The effort component is (10 - effort). Minimum meaningful effort is 1 (hours),
      not 0, so the inverted max is (10-1)=9, contributing 9*0.25=2.25, not 2.50.
      Max base = (10*0.45) + (10*0.30) + (9*0.25) = 4.5 + 3.0 + 2.25 = 9.75
      9.75 * 1,000 = 9,750

    PENALTIES:
      - has_dependencies: multiply by DEPENDENCY_PENALTY (0.75)
        Rationale: a blocked task is not truly #1 until its blocker ships

    SCALE brings max score to 9,750:
      scale = 1,000 maps weighted sum to 0–9,750 range
    """

    WEIGHT_IMPACT      = 0.45   # User impact is the dominant factor
    WEIGHT_ALIGN       = 0.30   # Strategic alignment second
    WEIGHT_EFFORT      = 0.25   # Effort (inverted) third
    SCALE              = 1_000  # Maps weighted sum to 0–9,750 range
    DEPENDENCY_PENALTY = 0.75   # 25% penalty for tasks with unresolved dependencies
    MAX_SCORE          = 9_750  # Theoretical maximum (impact=10, effort=1, alignment=10, no deps)

    def score(self, task: dict) -> int:
        impact    = task["user_impact"]           # 1–10
        effort    = task["effort"]                # 1–10 (10 = hardest)
        alignment = task["strategic_alignment"]   # 1–10
        blocked   = task.get("has_dependencies", False)

        base = (
            (impact    * self.WEIGHT_IMPACT) +
            (alignment * self.WEIGHT_ALIGN)  +
            ((10 - effort) * self.WEIGHT_EFFORT)
        ) * self.SCALE

        if blocked:
            base *= self.DEPENDENCY_PENALTY

        return round(base)

    def get_methodology(self) -> dict:
        return {
            "formula": "score = ((impact*0.45) + (alignment*0.30) + ((10-effort)*0.25)) * 1000",
            "max_score": self.MAX_SCORE,
            "max_score_note": "9,750 not 10,000 — effort minimum is 1 (hours), so inverted max = 9*0.25 = 2.25, not 2.50",
            "weights": {
                "user_impact": "45% — dominant factor, we build for users first",
                "strategic_alignment": "30% — foundational tasks unlock more value over time",
                "effort_inverted": "25% — lower effort = higher score (ship fast, validate fast)"
            },
            "penalties": {
                "has_dependencies": "25% reduction — a blocked task cannot be true #1 priority"
            },
            "scale": "x1000 to map weighted sum to 0–9,750 range",
            "example": {
                "task": "Binance API sync",
                "impact": 9, "effort": 5, "alignment": 10,
                "no_dependency": True,
                "calculation": "((9*0.45) + (10*0.30) + (5*0.25)) * 1000 = 8,300"
            }
        }

    def explain(self, task: dict) -> str:
        """Human-readable score explanation for a task."""
        score = self.score(task)
        lines = [
            f"Task: {task['name']}",
            f"  User Impact:          {task['user_impact']}/10  × 0.45 = {task['user_impact'] * 0.45:.2f}",
            f"  Strategic Alignment:  {task['strategic_alignment']}/10  × 0.30 = {task['strategic_alignment'] * 0.30:.2f}",
            f"  Effort (inverted):    {10 - task['effort']}/10  × 0.25 = {(10 - task['effort']) * 0.25:.2f}",
        ]
        if task.get("has_dependencies"):
            lines.append(f"  Dependency penalty:   × 0.75")
        lines.append(f"  ➜ APEX Score: {score:,} / {self.MAX_SCORE:,}")
        return "\n".join(lines)
