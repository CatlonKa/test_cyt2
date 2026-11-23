---
name: mtb-list-available-libraries
description: 'Lists ModusToolbox middleware libraries available for this workspace, including category, GitHub URL, latest version, description, and whether already installed.  Also provides the exact command-line workflow to add a library to a project.  USE FOR: answering questions like "what libraries are available?", "which middleware can I add?", "how do I add library X?", "list all available ModusToolbox libraries".  DO NOT USE FOR: listing already-installed libraries (use the deps/ or libs/ folders for that).'
license: "Apache-2.0"
metadata:
  author: "Infineon ModusToolbox Team"
  version: "1.1.0"
---

# Skill: mtb-list-available-libraries

## Purpose

Lists the ModusToolbox middleware libraries available for this workspace as a YAML document:

- **used** libraries, already referenced by a project: `middleware_id`, `category`,
  `remote_uri`, `local_uri`, `used_by_projects`, `version_tags`, `description`
- **unused** libraries, available to add: `middleware_id`, `category`, `remote_uri`,
  `version_tags`, `description`
- a **summary** with counts by category

## When to Invoke

Invoke this skill when the user asks any of:

- "What libraries are available?"
- "List available ModusToolbox middleware"
- "Which middleware can I add to my project?"
- "How do I add library X to my project?"
- "What is the GitHub URL for library X?"
- "What version of library X is available?"

## How to Run

Execute the bundled Python script from the **workspace root** and capture
its output:

```
python .github/skills/mtb-tools/scripts/list_available_libraries.py
```

Outputs the full library catalog as YAML on stdout.

## How to Add a Library to a Project

The catalog output does NOT include this workflow. Use these steps:

1. Determine which `<project>` the library goes into — middleware is added **per project**.
2. Collect `remote_uri`, `middleware_id`, and the first `version_tags` entry — the list is
   sorted newest-first. A trailing `(+N more)` is a count, not a version.
3. Create `<project>/deps/<middleware_id>.mtb` containing:
   ```
   <remote_uri>#<version_tag>#$$ASSET_REPO$$/<middleware_id>/<version_tag>
   ```
4. Add to `<project>/Makefile`:
   ```makefile
   COMPONENTS+=COMPONENT_MW_<MIDDLEWARE_ID_UPPERCASE_UNDERSCORES>
   ```
5. Run both from the **workspace root**, not the project root. Bare `make` is not on PATH on
   Windows, so always go through `run_make.py`:
   ```
   python .github/skills/mtb-tools/scripts/run_make.py --args getlibs
   python .github/skills/mtb-tools/scripts/run_make.py --args build
   ```
   `getlibs` resolves dependencies and updates `<project>/libs/`; sources land in `../mtb_shared/`.

### Example — adding `retarget-io` to a project

1. Catalog gives `remote_uri` = `https://github.com/cypresssemiconductorco/retarget-io`, latest `version_tag` = `release-v1.9.0`
2. Create `<project>/deps/retarget-io.mtb` containing:
   ```
   https://github.com/cypresssemiconductorco/retarget-io#release-v1.9.0#$$ASSET_REPO$$/retarget-io/release-v1.9.0
   ```
3. Add to `<project>/Makefile`: `COMPONENTS+=COMPONENT_MW_RETARGET_IO`
4. From the workspace root:
   ```
   python .github/skills/mtb-tools/scripts/run_make.py --args getlibs
   python .github/skills/mtb-tools/scripts/run_make.py --args build
   ```

## Interpreting the Output

The output is a YAML document with these top-level sections:

### `metadata`

Workspace path, MCU device, BSP name, project names.

### `summary`

Counts of used/unused libraries by category.

### `used_libraries`

Libraries already referenced by a project. Fields:

- `middleware_id` — library identifier
- `category` — e.g. Core, Middleware, Bluetooth®, Wi-Fi, Peripheral, Utilities
- `used_by_projects` — which projects use it
- `remote_uri` — GitHub URL
- `local_uri` — path in `../mtb_shared/`
- `version_tags` — installed version (and how many others are available)
- `description` — what the library does

### `unused_libraries`

Libraries available to download and add. Fields:

- `middleware_id`, `category`, `remote_uri`, `version_tags`, `description`
  (same as above but without `local_uri` / `used_by_projects`)

## Error Handling

If the script exits with a non-zero code or prints an `ERROR:` line, ask the user to select the
`Add AI Enhancements` button from the Application tab of the Infineon ModusToolbox for VS Code
extension, or use `Command Palette > ModusToolbox: Generate AI Instructions`.
