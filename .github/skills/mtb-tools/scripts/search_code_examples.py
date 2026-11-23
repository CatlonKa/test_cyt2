#!/usr/bin/env python3
"""Skill: search_code_examples
Calls the Infineon ModusToolbox AI Assistant server command 'search_code_examples' and prints the full result.
The server scores a board's code examples with field-weighted, IDF-weighted lexical matching (token/stem, not
substring) and returns a small, ranked candidate set with a score, matched_tags/matched_terms, and a snippet.

Recommended flow: first run get_code_example_vocabulary.py to expand the user's request into concrete tags, then
pass those here as --tag along with free-text --query-terms and any --role hints. A raw --query alone also works.

Usage:
    python .github/skills/mtb-tools/scripts/search_code_examples.py \
        [--board-id board] [--query "raw text"] [--tag ble --tag gatt] \
        [--query-terms "send sensor data"] [--role server] [--limit 20]
"""

import sys
import os
import argparse

# Get the directory of the current script
current_dir = os.path.dirname(os.path.abspath(__file__))

# Add it to the end of the search path, so we can find the mtbskill.py
sys.path.insert(0, current_dir)

from mtbskill import bootstrap_skill  # type: ignore

parser = argparse.ArgumentParser(description="Search ModusToolbox code examples (ranked)")
parser.add_argument("--board-id", required=False, help="Search examples for a specific board (defaults to the current workspace board)")
parser.add_argument("--query", required=False, help="Raw natural-language query. Used as the free-text terms when --query-terms is omitted.")
parser.add_argument(
    "--tag",
    required=False,
    action="append",
    help="Controlled-vocabulary keyword from get_code_example_vocabulary. Repeat (or comma-separate) for a set. Scored by IDF.",
)
parser.add_argument("--query-terms", required=False, help="Free-text terms; token/stem matched across name, keywords, category, and description.")
parser.add_argument(
    "--role",
    required=False,
    action="append",
    help="Role hint to boost, e.g. server, client, central, peripheral, source, sink. Repeat for several.",
)
parser.add_argument("--limit", required=False, type=int, help="Max ranked results to return (default 20).")
args = parser.parse_args()

try:
    skill = bootstrap_skill(__file__)

    # ── Call the Infineon ModusToolbox AI Assistant server command and print the full result ───────────────────
    params = {}
    if args.board_id:
        params["board_name"] = args.board_id
    if args.query:
        params["query"] = args.query
    tags = []
    for t in args.tag or []:
        tags.extend(p.strip() for p in t.split(",") if p.strip())
    if tags:
        params["selected_tags"] = tags
    if args.query_terms:
        params["query_terms"] = args.query_terms
    roles = []
    for r in args.role or []:
        roles.extend(p.strip() for p in r.split(",") if p.strip())
    if roles:
        params["roles"] = roles
    if args.limit is not None:
        params["limit"] = args.limit

    result = skill.mcp_request("search_code_examples", **params)
    print(skill.mcp_text(result))
except Exception as e:
    error_msg = str(e)
    print("ERROR:", error_msg)
    sys.exit(1)
