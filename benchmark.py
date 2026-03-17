"""
APEX Benchmark: APEX vs Cursor-Simulated Claude
Compares prioritization quality between APEX and a context-aware Claude prompt
that simulates how Cursor's Claude operates in a real development environment.

Benchmark design notes:
  - "Default Cursor Claude" is not directly callable via API. Cursor injects your
    open files, project structure, and recent edits as context automatically.
  - We simulate this honestly by constructing the same kind of context-rich system
    prompt Cursor would use: project files, goal, and codebase awareness.
  - This makes the comparison HARDER for APEX (stronger baseline), not easier.
  - An independent Claude judge instance scores both outputs blind on three criteria.
  - See README.md "Benchmark Methodology" section for full transparency note.

Evaluation criteria (scored 1-10 by independent judge):
  1. Specificity    — concrete and unambiguous guidance
  2. Actionability  — developer can act immediately without clarification
  3. Reproducibility — two people get the same priority order
"""

import os
import json
import anthropic
from typing import Optional

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# ─────────────────────────────────────────────────────────────
# Cursor-simulated system prompt (Option A)
# Mirrors what Cursor injects: project context, open files,
# codebase awareness, and the developer's current task.
# This is a STRONGER baseline than a blank Claude prompt.
# ─────────────────────────────────────────────────────────────
CURSOR_SIMULATED_PROMPT = """You are Claude, an AI assistant embedded inside the Cursor IDE.
You have full awareness of the developer's current project. Here is the project context:

PROJECT: crypto portfolio tracker (early stage, no code written yet)
STACK: Python, Binance API, likely Flask or FastAPI for backend
TEAM SIZE: 1-2 developers
TIMELINE: 2-week MVP target
OPEN FILES: none yet — developer is planning what to build first
RECENT ACTIVITY: developer just described the product goal below

Your job: given this product goal, list what the developer should build in priority order.
Be specific to this project and stack. Think like a senior engineer who knows this codebase.
Provide clear reasoning for your ordering."""

# ─────────────────────────────────────────────────────────────
# Independent judge system prompt
# ─────────────────────────────────────────────────────────────
JUDGE_SYSTEM_PROMPT = """You are an impartial evaluator assessing the quality of AI prioritization outputs.
Score each output on three criteria from 1-10:

1. Specificity: Does it give concrete, unambiguous guidance? (10 = laser-specific, 1 = vague platitudes)
2. Actionability: Can a developer act on this immediately without clarification? (10 = open editor and go, 1 = still unclear)
3. Reproducibility: Would two different people get the same priority order from this? (10 = deterministic, 1 = varies each run)

Return ONLY valid JSON, no prose, no markdown fences:
{
  "output_a": {
    "specificity": <1-10>,
    "actionability": <1-10>,
    "reproducibility": <1-10>,
    "total": <sum>,
    "verdict": "<one sentence>"
  },
  "output_b": {
    "specificity": <1-10>,
    "actionability": <1-10>,
    "reproducibility": <1-10>,
    "total": <sum>,
    "verdict": "<one sentence>"
  },
  "winner": "output_a or output_b or tie",
  "reasoning": "<two sentences explaining the winner>"
}"""


def get_cursor_simulated_ranking(goal: str) -> str:
    """
    Get priority ranking from a Cursor-simulated Claude.

    Cursor's Claude is not directly callable via API — it uses an internal
    context injection system that includes open files, project tree, and
    editor state. We simulate this with a context-rich system prompt that
    provides the same kind of project awareness Cursor would inject.

    This intentionally makes the baseline STRONGER than a blank Claude call.
    """
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=800,
        system=CURSOR_SIMULATED_PROMPT,
        messages=[{"role": "user", "content": f"Product goal: {goal}"}]
    )
    return response.content[0].text.strip()


def get_apex_ranking(goal: str, context: Optional[str] = None) -> dict:
    """Get APEX ranked output."""
    from agent import run
    return run(goal, context=context, verbose=False)


def format_apex_for_judge(apex_result: dict) -> str:
    """Convert APEX structured output to readable text for the judge."""
    lines = [f"Goal summary: {apex_result['goal_summary']}\n"]
    lines.append("Priority ranking (scored 1-9,750):")
    for task in apex_result["ranked_tasks"]:
        dep = " [BLOCKED - has dependencies]" if task["has_dependencies"] else ""
        lines.append(
            f"  #{task['id']} {task['name']} - Score: {task['apex_score']:,}"
            f" (Impact={task['user_impact']}/10, Effort={task['effort']}/10, "
            f"Alignment={task['strategic_alignment']}/10){dep}"
        )
    top = apex_result["top_priority"]
    lines.append(f"\n#1 Priority: {top['name']}")
    lines.append(f"Cursor starting point: {top['cursor_scaffold']}")
    lines.append(f"\nImplementation plan:\n{apex_result['cursor_plan']}")
    return "\n".join(lines)


def run_judge(cursor_output: str, apex_output: str) -> dict:
    """Ask an independent Claude instance to score both outputs blind."""
    judge_prompt = f"""Score these two prioritization outputs for the same product goal.

Output A:
{cursor_output}

---

Output B:
{apex_output}

Score both on Specificity, Actionability, and Reproducibility (1-10 each).
Return only valid JSON."""

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=800,
        system=JUDGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": judge_prompt}]
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def run_benchmark(goal: str, context: Optional[str] = None) -> dict:
    """Run side-by-side comparison with independent LLM judge."""
    print("\n" + "=" * 65)
    print("APEX BENCHMARK: APEX vs Cursor-Simulated Claude")
    print("Evaluated by: independent Claude judge instance (blind)")
    print("=" * 65)
    print(f"\nGoal: {goal}\n")

    # Transparency notice up front
    print("[ BENCHMARK METHODOLOGY NOTE ]")
    print("Cursor's Claude is not directly callable via API. It works by")
    print("injecting your open files, project tree, and editor state as")
    print("context automatically. We simulate this with a context-rich")
    print("system prompt that provides equivalent project awareness.")
    print("This makes the baseline STRONGER than a blank Claude call.")
    print("The judge sees only 'Output A' and 'Output B' — no labels.\n")

    # Cursor-simulated Claude
    print("-" * 65)
    print("OUTPUT A: Cursor-Simulated Claude (context-aware baseline):")
    print("-" * 65)
    cursor_output = get_cursor_simulated_ranking(goal)
    print(cursor_output)

    # APEX
    print("\n" + "-" * 65)
    print("OUTPUT B: APEX Agent:")
    print("-" * 65)
    apex_result = get_apex_ranking(goal, context)
    apex_formatted = format_apex_for_judge(apex_result)

    print(f"\n{'SCORE':>10}  {'TASK':<35}")
    print("-" * 50)
    for task in apex_result["ranked_tasks"]:
        dep = " (blocked)" if task["has_dependencies"] else ""
        print(f"{task['apex_score']:>10,}  {task['name']:<35}{dep}")
    print(f"\nAPEX #1 Priority: {apex_result['top_priority']['name']}")

    # Independent Judge
    print("\n" + "-" * 65)
    print("INDEPENDENT JUDGE (separate Claude instance, no labels shown):")
    print("Criteria: Specificity | Actionability | Reproducibility")
    print("-" * 65)

    scores = run_judge(cursor_output, apex_formatted)

    a = scores["output_a"]  # Cursor-simulated
    b = scores["output_b"]  # APEX

    print(f"\n{'CRITERION':<20}  {'CURSOR CLAUDE':>13}  {'APEX':>6}")
    print("-" * 45)
    print(f"{'Specificity':<20}  {a['specificity']:>13}/10  {b['specificity']:>4}/10")
    print(f"{'Actionability':<20}  {a['actionability']:>13}/10  {b['actionability']:>4}/10")
    print(f"{'Reproducibility':<20}  {a['reproducibility']:>13}/10  {b['reproducibility']:>4}/10")
    print(f"{'TOTAL':<20}  {a['total']:>13}/30  {b['total']:>4}/30")

    print(f"\nCursor Claude: {a['verdict']}")
    print(f"APEX:          {b['verdict']}")

    winner_label = (
        "CURSOR CLAUDE" if scores["winner"] == "output_a"
        else "APEX" if scores["winner"] == "output_b"
        else "TIE"
    )
    print(f"\nWinner: {winner_label}")
    print(f"{scores['reasoning']}")

    print("\n[ LIMITATION ]")
    print("This benchmark cannot fully replicate Cursor's live file injection.")
    print("A production benchmark would diff outputs across 20+ diverse goals")
    print("and average judge scores. This is a representative single-run sample.")

    return {
        "goal": goal,
        "baseline": "cursor_simulated",
        "cursor_output": cursor_output,
        "apex_result": apex_result,
        "judge_scores": scores,
        "methodology_note": (
            "Cursor Claude simulated via context-rich system prompt. "
            "True Cursor API is not publicly accessible. "
            "Baseline intentionally strengthened to avoid easy wins."
        )
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        goal = (
            "Build a crypto portfolio tracker with Binance API sync, "
            "real-time price alerts, portfolio charts, user auth, "
            "and social sharing"
        )
    else:
        goal = " ".join(sys.argv[1:])

    run_benchmark(goal)
