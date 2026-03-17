"""
APEX - AI Priority Execution Agent
Turns vague product goals into ranked, executable task lists.
Then auto-scaffolds the #1 priority for Cursor.
"""

import os
import json
import anthropic
from scorer import PriorityScorer
from typing import Optional

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are APEX, an elite AI product strategist and senior engineer.
Your job is to take a product goal or feature list and:
1. Break it into discrete, buildable tasks
2. Analyze each task for: user impact, technical effort, strategic alignment, dependencies
3. Return ONLY valid JSON — no prose, no markdown fences

Output format:
{
  "goal_summary": "one sentence summary of the overall goal",
  "tasks": [
    {
      "id": 1,
      "name": "short task name",
      "description": "what exactly needs to be built",
      "user_impact": 1-10,
      "effort": 1-10,
      "strategic_alignment": 1-10,
      "has_dependencies": true/false,
      "dependency_note": "what it depends on or empty string",
      "cursor_scaffold": "the exact first file or function to create in Cursor"
    }
  ]
}

Rules:
- user_impact: how much users feel this (10 = critical, 1 = invisible)
- effort: how hard to build (10 = months, 1 = hours) — LOWER is better for ranking
- strategic_alignment: does this unlock future features? (10 = foundational)
- has_dependencies: true if this task needs another task done first
- cursor_scaffold: one concrete starting point (e.g. "Create binance_client.py with connect() function")
- Be ruthlessly honest. Not everything is high priority.
"""

def parse_goal(goal: str, context: Optional[str] = None) -> dict:
    """Send goal to Claude, get structured task breakdown."""
    user_message = f"Product goal: {goal}"
    if context:
        user_message += f"\n\nAdditional context: {context}"

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )

    raw = response.content[0].text.strip()
    # Strip markdown fences if model slips
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def generate_cursor_plan(top_task: dict, goal_summary: str) -> str:
    """Generate a detailed Cursor implementation plan for the #1 priority task."""
    prompt = f"""
You are a senior engineer writing a Cursor AI implementation plan.
Goal: {goal_summary}
Task to implement: {top_task['name']} — {top_task['description']}
Starting point: {top_task['cursor_scaffold']}

Write a step-by-step Cursor implementation plan. Be specific and technical.
Format as numbered steps. Max 10 steps. Each step should be a concrete action.
Start with: "Open Cursor and begin:"
"""
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


def run(goal: str, context: Optional[str] = None, verbose: bool = True) -> dict:
    """Main APEX pipeline."""
    if verbose:
        print("\n🔍 APEX — AI Priority Execution Agent")
        print("=" * 50)
        print(f"📋 Goal: {goal}\n")
        print("⚙️  Analyzing tasks...\n")

    # Step 1: Parse goal into tasks
    data = parse_goal(goal, context)
    tasks = data["tasks"]
    goal_summary = data["goal_summary"]

    # Step 2: Score each task
    scorer = PriorityScorer()
    scored_tasks = []
    for task in tasks:
        score = scorer.score(task)
        task["apex_score"] = score
        scored_tasks.append(task)

    # Step 3: Sort by score descending
    scored_tasks.sort(key=lambda x: x["apex_score"], reverse=True)

    # Step 4: Display results
    if verbose:
        print(f"🎯 Goal Summary: {goal_summary}\n")
        print(f"{'SCORE':>10}  {'TASK':<30}  {'IMPACT':>6}  {'EFFORT':>6}  {'ALIGN':>5}")
        print("-" * 70)
        for task in scored_tasks:
            dep_flag = " ⚠️" if task["has_dependencies"] else ""
            print(
                f"{task['apex_score']:>10,}  "
                f"{task['name']:<30}  "
                f"{task['user_impact']:>6}  "
                f"{task['effort']:>6}  "
                f"{task['strategic_alignment']:>5}"
                f"{dep_flag}"
            )
        print()
        print("⚠️  = has dependencies (may not be true #1 to implement)")

    # Step 5: Pick #1 and generate Cursor plan
    top_task = scored_tasks[0]
    if verbose:
        print(f"\n✅ #1 PRIORITY: {top_task['name']}")
        print(f"   Score: {top_task['apex_score']:,} / 10,000")
        print(f"   Why: Impact={top_task['user_impact']}/10, Effort={top_task['effort']}/10, Alignment={top_task['strategic_alignment']}/10")
        if top_task["dependency_note"]:
            print(f"   Depends on: {top_task['dependency_note']}")
        print(f"\n📁 Generating Cursor implementation plan for: {top_task['name']}...\n")

    cursor_plan = generate_cursor_plan(top_task, goal_summary)

    if verbose:
        print(cursor_plan)
        print("\n" + "=" * 50)
        print("🚀 APEX complete. Open Cursor and follow the plan above.")

    return {
        "goal_summary": goal_summary,
        "ranked_tasks": scored_tasks,
        "top_priority": top_task,
        "cursor_plan": cursor_plan,
        "scorer_methodology": scorer.get_methodology()
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        # Demo mode
        demo_goal = (
            "Build a crypto portfolio tracker with: Binance API sync, "
            "real-time price alerts, portfolio charts, user auth, "
            "and social sharing of portfolio performance"
        )
        run(demo_goal)
    else:
        goal = " ".join(sys.argv[1:])
        run(goal)
