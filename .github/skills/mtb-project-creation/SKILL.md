---
name: mtb-project-creation
description: "Use when the user asks to create a new ModusToolbox project, scaffold a starter application, generate a project from a code example or template, or set up a new embedded project for an Infineon board or MCU."
license: "Apache-2.0"
metadata:
  author: "Infineon ModusToolbox Team"
  version: "1.2.0"
---

# ModusToolbox Project Creation

Create a new ModusToolbox project using the `project-creator-cli` tool via the bundled wrapper script. This skill gathers the required parameters — board, application template, output directory, and project name — then invokes the CLI to scaffold a complete, buildable project.

**Scope:** this is the workspace-mode copy, used when the user is already in a development
workspace and wants to scaffold a *separate* new project. It deliberately does **not** perform the
planning-workspace handoff (`modusToolbox-ai.openWorkspaceAndContinueWork`), because that replaces
the current VS Code window and would abandon the work in progress. Tell the user where the project
was created and let them open it when ready.

## When to Use

- User asks to create a new ModusToolbox project
- User wants to start a project from a code example or application template
- User asks to scaffold a new embedded application for an Infineon board
- User says "create a project for <board>", "new project from <template>", or similar

## Prerequisites

- The Infineon ModusToolbox AI Assistant VS Code extension is active and the server is running
- `CY_TOOLS_PATH` is resolvable from the skill environment (the wrapper reads it; no manual setup needed)
- The wrapper script is available at `.github/skills/mtb-tools/scripts/project_creator_wrapper.py`
- `mtbskill.py` is co-located with the tool scripts in `.github/skills/mtb-tools/scripts/`

## Required Information

Before invoking the project creator, gather all four required parameters:

| Parameter | Flag | Description | How to Resolve |
| --------- | ---- | ----------- | -------------- |
| Board ID | `--board-id` | Target board identifier (e.g., `CY8CPROTO-062-4343W`, `KIT_PSE84_EVAL`) | Ask the user, or run `python .github/skills/mtb-tools/scripts/list_available_boards.py` to list valid boards |
| App/Template ID | `--app-id` | Code example or application template identifier (e.g., `mtb-example-psoc6-hello-world`) | Ask the user, or use the ranked search in step 2 — see [mtb-list-code-examples](../mtb-list-code-examples/SKILL.md) |
| Target Directory | `--target-dir` | Filesystem path where the project will be created | Ask the user, or default to the current workspace directory |
| Project Name | `--user-app-name` | Name for the created project (becomes the project folder name) | Ask the user |

## Step-by-Step Workflow

1. **Identify the board** — If the user specifies a board, use it directly. Otherwise, run `python .github/skills/mtb-tools/scripts/list_available_boards.py` to present available boards and ask the user to choose.

2. **Identify the application template** — If the user names a template, use it directly. Otherwise follow the retrieval flow in [mtb-list-code-examples](../mtb-list-code-examples/SKILL.md): read the board's vocabulary first, then run `search_code_examples.py` with tags drawn from it. Do **not** start with `list_code_examples.py` — the unranked browse path has no relevance signal, and raw user wording rarely matches catalog text.

   ```bash
   python .github/skills/mtb-tools/scripts/get_code_example_vocabulary.py --board-id <board-id>
   python .github/skills/mtb-tools/scripts/search_code_examples.py --board-id <board-id> \
       --tag <tag> --tag <tag> --query-terms "<the user's wording>"
   ```

   Two rules specific to choosing a **template** rather than a reference:

   - ⛔ **Capability, not topical relevance.** The template must actually *provide* the
     infrastructure the application needs (RTOS, connectivity stack, graphics stack). The
     highest-scoring hit is usually the one that matches the *peripheral* — that is a reference to
     read, not a base to build on. For "a FreeRTOS app that drives a PWM LED", the PWM example is
     bare-metal; the correct template is the empty/starter app that already carries FreeRTOS.
   - **Search twice, separately.** One search for the infrastructure/template (tags like `empty`,
     `template`, `starter`, or the stack name), a second for the peripheral references. A single
     union of both tag sets blurs the two and surfaces neither cleanly.

   Confirm the chosen template really has the capability before committing —
   `describe_code_example.py <id>` reports the live `COMPONENTS` and dependencies from the repo.
   Then present the candidates and let the user choose.

3. **Determine the output directory** — Ask the user where the project should be created. If not specified, default to the ModusToolbox project directory (`~/mtb`). **The directory must already exist** — `project-creator-cli` fails with `Directory "<path>" doesn't exist.` rather than creating it. Create it if needed.

4. **Determine the project name** — Ask the user for a project name. If not specified, suggest a sensible default based on the template name.

5. **⛔ Check the target folder does not already exist (MANDATORY)** — Before confirming, check whether `<target-dir>/<project-name>` exists. `project-creator-cli` has undefined behaviour when it does, so never let it run blind:
   - If it EXISTS: propose an alternative name (append `_v2`, `_v3`, …) and offer exactly three options — **Overwrite**, **use the proposed alternative**, or **Other** (user supplies a name). Do not overwrite unless the user explicitly chooses it.
   - If it does NOT exist: proceed to confirmation.

6. **Confirm with the user** — Present the full set of parameters and ask for confirmation:
   ```
   I'll create a new ModusToolbox project with these settings:

   - Board: <board-id>
   - Template: <app-id>
   - Directory: <target-dir>
   - Project name: <user-app-name>

   Shall I proceed?
   ```

6. **Run the project creator** — Execute from the workspace root:
   ```
   python .github/skills/mtb-tools/scripts/project_creator_wrapper.py \
       --board-id <board-id> \
       --app-id <template-id> \
       --target-dir <output-dir> \
       --user-app-name <project-name>
   ```

   ⛔ Run this synchronously and wait. First-time creation downloads the BSP and middleware and can
   take several minutes; a multi-core PSOC Edge project builds three sub-projects sequentially.

7. **Verify success** — Check the exit code. On success, confirm the project was created and note the project path. On failure, report the error output to the user.

8. **Generate VS Code configuration** — Run `make vscode` in the new project so the extension does not
   prompt for configuration the first time the project is opened:
   ```
   python .github/skills/mtb-tools/scripts/run_make.py --working-dir <target-dir>/<project-name> --args vscode
   ```
   ⛔ Synchronously, and wait for exit code 0 — on a multi-core project this runs across every
   sub-project and takes 1–2 minutes.

9. **Post-creation guidance** — Report the project path and let the user open it when they choose.
   Do **not** open it automatically: this skill runs inside an active development workspace, and
   switching workspaces would discard the user's current session.

## Parameter Resolution Helpers

### List Available Boards

```
python .github/skills/mtb-tools/scripts/list_available_boards.py
```

Returns the set of boards supported by the current ModusToolbox installation.

### Find Code Examples and Templates

Ranked search — the normal path. Needs tags from the board's vocabulary:

```
python .github/skills/mtb-tools/scripts/get_code_example_vocabulary.py --board-id <board-id>
python .github/skills/mtb-tools/scripts/search_code_examples.py --board-id <board-id> --tag <tag> --query-terms "<wording>"
```

Unranked browse — only for pure discovery ("what ships for this board?") or when a second search
still returns nothing:

```
python .github/skills/mtb-tools/scripts/list_code_examples.py --board-id <board-id> --summary-only
```

Verify a specific example against its live repo before committing to it as a template:

```
python .github/skills/mtb-tools/scripts/describe_code_example.py <example-id>
```

See [mtb-list-code-examples](../mtb-list-code-examples/SKILL.md) for the full flow, including how to
read the vocabulary and why scores are only comparable within a single query.

## Example Intents

- "Create a new project for the CY8CPROTO-062-4343W board"
- "Start a hello-world project for PSoC 6"
- "Scaffold a BLE project for the KIT_PSE84_EVAL"
- "New project from the mtb-example-psoc6-hello-world template"
- "Create a FreeRTOS starter for my board"

## Troubleshooting

| Problem | Resolution |
| ------- | ---------- |
| Wrapper script not found | Ensure the Infineon ModusToolbox AI Assistant extension is active — it deploys the skills on startup |
| Board ID not recognized | Run `list_available_boards.py` to get valid identifiers |
| App ID not found | Run `list_code_examples.py --board-id <board-id>` to get valid template identifiers for the board |
| `Directory "<path>" doesn't exist.` | The target directory must exist before creation — create it, then re-run |
| Permission denied on target directory | Verify the path exists and is writable |
| `CY_TOOLS_PATH` not set | The server must be running — restart VS Code with the Infineon ModusToolbox AI Assistant extension |
| `project-creator-cli` hangs | May be downloading BSP/middleware; allow several minutes for first-time creation |
| `xcrun: unable to load libxcrun` (macOS) | Command Line Tools are missing an x86_64 slice; reinstall with `xcode-select --install`. Check with `arch -x86_64 /usr/bin/git --version` |

## Notes

- The wrapper script uses the `mtbskill` bootstrap to locate `CY_TOOLS_PATH` and the `project-creator-cli` binary automatically.
- Board IDs and app IDs are case-sensitive — always use the exact identifiers from the manifest.
- The created project will include all necessary BSP files, middleware references, and a default `Makefile`.
