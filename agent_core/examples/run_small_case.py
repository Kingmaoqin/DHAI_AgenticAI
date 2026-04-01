from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from agent_core import build_default_runner


def main() -> None:
    runner = build_default_runner()
    query = (
        "Based on the office handbook, what is the lunch reimbursement limit, "
        "and what is 18 + 24? Return a short report with evidence."
    )
    output_dir = Path("/home/xqin5/agenticAI/runs")
    run_state = runner.run(query=query, output_dir=output_dir)

    print("Small case completed.")
    print(json.dumps(asdict(run_state.final_response), indent=2, ensure_ascii=True))
    print(f"Artifacts: {len(run_state.artifacts)}")
    print(f"Trace events: {len(run_state.trace)}")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
