"""TalentScout — command-line chat with the LangGraph matching agent.

    python cli.py                      # paste a JD or type a query
    python cli.py --jd data/jds/senior_frontend_engineer.md
"""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from matching_agent import MatchingAgent

console = Console()
HELP = ("Paste a JD (finish with an empty line) or type a query. Try: 'Compare the top 3', "
        "'Why did John rank higher than Jane?', 'Make AWS a must-have', 'Interview questions for #1', 'done'.")


def read_input() -> str:
    first = console.input("[bold cyan]you ›[/] ").strip()
    if len(first) < 120 and not first.startswith("#"):
        return first
    lines = [first]  # multi-line paste: read until an empty line
    while True:
        line = input()
        if not line.strip():
            break
        lines.append(line)
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jd", type=Path, help="Path to a job description to start with")
    args = ap.parse_args()
    agent = MatchingAgent()
    console.print(Panel.fit("🎯 [bold]TalentScout[/] — LangGraph resume matching agent\n" + HELP, border_style="cyan"))

    def on_event(node: str, update: dict) -> None:
        for t in (update.get("trace") or [])[-1:]:
            if t["node"] == node:
                console.print(f"  [dim]▸ {node}:[/] {t['summary']}")

    text = args.jd.read_text() if args.jd else read_input()
    while True:
        if not text:
            text = read_input()
            continue
        with console.status("[cyan]agent reasoning…"):
            replies = agent.send(text, on_event=on_event)
        for r in replies:
            console.print(Panel(Markdown(r), border_style="green", title="TalentScout"))
        if not agent.waiting_for_user:
            break
        text = read_input()


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print("\nbye 👋")
