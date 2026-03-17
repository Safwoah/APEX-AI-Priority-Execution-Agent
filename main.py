
"""
APEX CLI — run from terminal or Cursor terminal
Usage:
  python main.py "your product goal here"
  python main.py --benchmark "your product goal here"
  python main.py --demo
  python main.py --json "your product goal here"
"""

import sys
import os
import argparse


def main():
    parser = argparse.ArgumentParser(
        prog="apex",
        description="APEX — AI Priority Execution Agent. Turns product goals into ranked, Cursor-ready tasks."
    )
    parser.add_argument("goal", nargs="*", help="Your product goal (in quotes)")
    parser.add_argument("--benchmark", action="store_true", help="Run APEX vs Cursor-simulated Claude comparison")
    parser.add_argument("--demo", action="store_true", help="Run with built-in demo goal")
    parser.add_argument("--json", action="store_true", help="Output raw JSON result")
    parser.add_argument("--context", type=str, help="Optional: extra context about your project")

    args = parser.parse_args()

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ Error: ANTHROPIC_API_KEY not set.")
        print("   Copy .env.example to .env and add your key.")
        print("   Then run: export ANTHROPIC_API_KEY=your_key_here")
        sys.exit(1)

    demo_goal = (
        "Build a crypto portfolio tracker with: Binance API sync, "
        "real-time price alerts, portfolio performance charts, "
        "user authentication, and social sharing of gains/losses"
    )

    goal = demo_goal if args.demo else " ".join(args.goal)

    if not goal:
        parser.print_help()
        sys.exit(0)

    if args.benchmark:
        from benchmark import run_benchmark
        run_benchmark(goal, context=args.context)
    else:
        from agent import run
        result = run(goal, context=args.context, verbose=not args.json)
        if args.json:
            import json
            print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
