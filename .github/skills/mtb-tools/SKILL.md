---
name: mtb-tools
description: Core ModusToolbox build, project creation, and GUI tool launcher scripts. Use this skill when you need to build firmware, run make targets, create projects, list boards/libraries/examples, or launch Device Configurator and other GUI tools.
license: "Apache-2.0"
metadata:
  author: "Infineon ModusToolbox Team"
  version: "1.2.0"
---

# ModusToolbox Tools Skill — Build, Create, Launch

This skill provides Python wrapper scripts that communicate with the ModusToolbox MCP server to build projects, manage libraries, create new projects, and launch GUI tools.

## How to Invoke These Tools

Run all scripts from the workspace root:

```bash
# Build the project:
python .github/skills/mtb-tools/scripts/run_make.py --filter-progress --args build

# Build with environment variables:
python .github/skills/mtb-tools/scripts/run_make.py --filter-progress --args build CONFIG=Debug

# Get libraries (after adding .mtb files):
python .github/skills/mtb-tools/scripts/run_make.py --args getlibs

# Clean:
python .github/skills/mtb-tools/scripts/run_make.py --args clean

# Program the board:
python .github/skills/mtb-tools/scripts/run_make.py --args program

# Build with working directory override:
python .github/skills/mtb-tools/scripts/run_make.py --filter-progress --working-dir proj_cm55 --args build

# Open Device Configurator:
python .github/skills/mtb-tools/scripts/run_tool.py config

# Open Library Manager:
python .github/skills/mtb-tools/scripts/run_tool.py library-manager

# List available boards:
python .github/skills/mtb-tools/scripts/list_available_boards.py

# List code examples for a board:
python .github/skills/mtb-tools/scripts/list_code_examples.py --board-id <board-id>

# List code examples filtered by one or more keywords and/or a category (preferred — keeps output small):
python .github/skills/mtb-tools/scripts/list_code_examples.py --keyword mqtt --keyword wifi --category Wi-Fi --limit 20

# Get the code-example keyword vocabulary for a board (categories, rarest-first keywords, acronym/synonym map):
python .github/skills/mtb-tools/scripts/get_code_example_vocabulary.py --board-id <board-id>

# Search code examples and get a small RANKED set (expand with the vocabulary first, then pass tags + terms):
python .github/skills/mtb-tools/scripts/search_code_examples.py --tag ble --tag gatt --query-terms "send sensor data" --role server

# Describe a code example (fetch metadata from GitHub):
python .github/skills/mtb-tools/scripts/describe_code_example.py <repo-name>

# List available libraries:
python .github/skills/mtb-tools/scripts/list_available_libraries.py --board-id <board-id>

# Find ModusToolbox installation:
python .github/skills/mtb-tools/scripts/list_modustoolbox_location.py

# Create a new project from template:
python .github/skills/mtb-tools/scripts/project_creator_wrapper.py \
    --board-id <board-id> --app-id <template-id> \
    --target-dir <output-dir> --user-app-name <project-name>

# List skills available for a board (JSON output, best for AI; --board-id defaults to the current session board):
python .github/skills/mtb-tools/scripts/list_skills_for_board.py --json --board-id <board-id>
```

**Windows note:** Use `python` (NOT `python3`).

## Available Scripts

### `run_make.py`
Run arbitrary make targets (build, clean, program, getlibs, vscode, etc.) via the MCP server. Handles modus-shell, CY_TOOLS_PATHS, and platform differences automatically.

**Arguments:**
- `--args` (required, remainder): Make target and arguments. Each argument must be a separate token.
- `--working-dir` (optional): Override working directory (for sub-projects)
- `--env-vars` (optional): Key-value pairs for environment variables
- `--filter-progress` (optional): Collapse ninja `[N/M] ...` progress lines to cut output volume. Use it for the `build` target.
- `--heartbeat-secs` (optional): Emit a liveness pulse to stderr after this many seconds with no output, so a silent slow link/codegen phase is not mistaken for a hang. Default 15; `0` disables.

**Important:**
- `--working-dir`, `--env-vars`, `--filter-progress` and `--heartbeat-secs` MUST appear BEFORE `--args`
- Do NOT quote multiple args together: `--args build CONFIG=Debug` (correct), NOT `--args "build CONFIG=Debug"` (wrong)
- Always use `timeout=0` for build, getlibs, and clean commands
- Do NOT invoke modus-shell bash directly — `run_make.py` handles all environment setup

### `run_tool.py`
Launch ModusToolbox GUI configurators (Device Configurator, Library Manager, etc.).

**Arguments:**
- `tool_name` (positional): Tool to launch (e.g., `config`, `library-manager`)

### `list_available_boards.py`
List all boards available for project creation from the ModusToolbox manifest.

### `list_code_examples.py`
List code examples available for a specific board. Prefer filtering over dumping the whole catalog; the response reports `total_unfiltered`, `returned`, `applied_filters`, `truncated`, and a broaden `suggestion` when nothing matches.

**Arguments:**
- `--board-id` (optional): Filter examples for a specific board
- `--keyword` (optional, repeatable): Case-insensitive substring matched across name, keywords, category, and description. Repeat the flag (or comma-separate) to pass a set; an example matches if it contains ANY keyword
- `--category` (optional): Case-insensitive category filter. Valid names are board-specific — they are the keys of `counts_by_category` in the response (discover via `--summary-only`)
- `--limit` (optional): Max examples to return. Applies ONLY with `--keyword` (defaults to 20 then); a bare or category-only call returns the full list
- `--summary-only` (optional): Return only `total_unfiltered` + `counts_by_category` (no example list). Cheapest way to discover the valid categories for the current board

### `get_code_example_vocabulary.py`
Return the controlled keyword vocabulary for a board's code examples: keywords grouped by category and **listed rarest (most discriminating) first**, plus an `acronym_map` and `synonym_map`. Map keys share the tag namespace (all lowercase), so a tag can be looked up directly. Use it to map a user's natural-language request onto the specific keywords/categories that exist for the board, then pass those to `search_code_examples.py --tag ...` for a ranked result set (preferred), or to `list_code_examples.py --keyword ...` for an unranked browse.

**Shortcut for the current board.** In a ModusToolbox workspace the extension parks this same YAML at
`<workspace-root>/.modustoolbox/code_example_vocabulary.yaml`, so you can read the file instead of running the script. It is
always the vocabulary for the current workspace board. `board_names` names the manifest boards the keywords were drawn from,
which is **not** always the board you are building for: a custom BSP is not in the manifest, so the vocabulary is drawn from the
kit(s) closest to the project's MCU and your BSP name will not appear there. Do not treat that as a mismatch. The file is
refreshed with the agent instructions and can lag a board change, so re-run the script if the board changed this session.
The file does **not** exist in the project-creation planning workspace (there is no current board there), so always
run the script with an explicit `--board-id` in that flow.

**Arguments:**
- `--board-id` (optional): Build the vocabulary for a specific board (defaults to the current workspace board). The current
  workspace's own BSP is always accepted, including a custom BSP that `list_available_boards.py` does not list

### `search_code_examples.py`
Search a board's code examples and return a small **ranked** candidate set (field-weighted, IDF-weighted lexical scoring; token/stem matching, not substring). This is the preferred retrieval path when relevance ordering matters. Recommended flow: expand the request with `get_code_example_vocabulary.py` first, then pass concrete tags + free-text terms here. Each result carries a `score`, `matched_tags`/`matched_terms`, and a `snippet`; a `suggestion` is returned when nothing scores.

**Arguments:**
- `--board-id` (optional): Search a specific board (defaults to the current workspace board)
- `--query` (optional): Raw natural-language query; used as the free-text terms when `--query-terms` is omitted (Option A fallback)
- `--tag` (optional, repeatable): Controlled-vocabulary keyword from the vocabulary tool. Repeat or comma-separate for a set; scored by IDF (rarer tags count more)
- `--query-terms` (optional): Free-text terms; token/stem matched across name, keywords, category, and description
- `--role` (optional, repeatable): Role hint to boost — e.g. `server`, `client`, `central`, `peripheral`, `source`, `sink`
- `--limit` (optional): Max ranked results (default 20)

### `describe_code_example.py`
Fetch live metadata from Infineon code example repos on GitHub (descriptions, dependencies, COMPONENTS).

**Arguments:**
- Positional repo names (one or more)
- `--source`: List source files in the example
- `--read <path>`: Read specific source files

### `list_available_libraries.py`
List middleware libraries available for a board.

**Arguments:**
- `--board-id` (optional): Filter libraries for a specific board

### `list_modustoolbox_location.py`
Return the installed ModusToolbox tools path.

### `project_creator_wrapper.py`
Create a new project from a template using the project-creator-cli.

**Arguments:**
- `--board-id` (required): Target board identifier
- `--app-id` (required): Template/application identifier
- `--target-dir` (required): Output directory
- `--user-app-name` (required): Project name

### `list_skills_for_board.py`
List the AI skills (name + description) deployed for a board. Run this during PLANNING
to populate the "Required Skill References per Phase" table, and during development to
discover which skills are available for the current target.

Works without a project/workspace context as long as `--board-id` is supplied explicitly.
Queries the extension server directly (not MCP), since manifest/skill resolution lives
in the extension.

**Arguments:**
- `--board-id` (optional): Board to list skills for. Defaults to the current session board. May be exact or partial; it is matched against the manifests' board globs.
- `--json` (optional): Emit the skills as JSON. Prefer this for AI consumption.

## Shared Module: `mtbskill.py`

All scripts depend on `mtbskill.py` (co-located in `scripts/`). This module locates the MCP server session and provides `bootstrap_skill()` for connecting to the running ModusToolbox extension.

## Important Notes

- **Build/getlibs are recursive makes** that build each sub-project and can take several minutes. Wait for the exit code.
- **Do NOT invoke modus-shell bash directly.** The `run_make.py` script handles all environment setup internally.
- **Do NOT construct raw bash commands** — it is error-prone and unnecessary.
- **Always verify build output** (exit_code == 0) before proceeding to program.
