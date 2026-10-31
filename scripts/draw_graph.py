"""Export the LangGraph state machine diagram from the compiled graph.

    python scripts/draw_graph.py   ->  docs/state_machine.mmd, docs/state_machine.png
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matching_agent import build_graph  # noqa: E402

if __name__ == "__main__":
    graph = build_graph().get_graph(xray=1)
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "state_machine.mmd").write_text(graph.draw_mermaid(), encoding="utf-8")
    print("wrote docs/state_machine.mmd")
    try:
        (docs / "state_machine.png").write_bytes(graph.draw_mermaid_png())
        print("wrote docs/state_machine.png")
    except Exception as exc:  # needs internet (mermaid.ink); the .mmd still renders on GitHub
        print(f"PNG export failed ({exc}); paste docs/state_machine.mmd into https://mermaid.live")
