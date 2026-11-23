#!/usr/bin/env python3
"""Skill: get_code_example_vocabulary
Calls the Infineon ModusToolbox AI Assistant server command 'get_code_example_vocabulary' and prints the full
result. The vocabulary is the controlled keyword set for a board's code examples: keywords grouped by category,
listed rarest (most discriminating) first, plus a lowercase acronym/synonym map. Use it to expand a user's
request into a small set of relevant keywords before calling search_code_examples.

Usage:
    python .github/skills/mtb-tools/scripts/get_code_example_vocabulary.py [--board-id board]
"""

import sys
import os
import argparse

# Get the directory of the current script
current_dir = os.path.dirname(os.path.abspath(__file__))

# Add it to the end of the search path, so we can find the mtbskill.py
sys.path.insert(0, current_dir)

from mtbskill import bootstrap_skill  # type: ignore

parser = argparse.ArgumentParser(description="Get the ModusToolbox code-example keyword vocabulary for a board")
parser.add_argument("--board-id", required=False, help="Build the vocabulary for a specific board (defaults to the current workspace board)")
args = parser.parse_args()

try:
    skill = bootstrap_skill(__file__)

    # ── Call the Infineon ModusToolbox AI Assistant server command and print the full result ───────────────────
    params = {}
    if args.board_id:
        params["board_name"] = args.board_id

    result = skill.mcp_request("get_code_example_vocabulary", **params)
    print(skill.mcp_text(result))
except Exception as e:
    error_msg = str(e)
    print("ERROR:", error_msg)
    sys.exit(1)
