---
name: mtb-list-code-examples
description: "Find and summarize the ModusToolbox code examples most relevant to the current board, MCU family or requested feature. Use it when the user asks for sample projects, starter apps or reference implementations for a peripheral, connectivity, ML or FreeRTOS use case."
license: "Apache-2.0"
metadata:
  author: "Infineon ModusToolbox Team"
  version: "1.2.0"
---

# ModusToolbox Code Examples

This skill helps an agent find and summarize the most relevant ModusToolbox code examples for the current target, board, MCU family, or requested feature.

## When to use

Use this skill when the user asks for:

- code examples or sample projects
- starter apps or reference implementations
- examples for a specific peripheral or middleware feature
- examples for a board or MCU family
- a good repo to clone as a starting point

Once the board to use is resolved, run the scripts below from the workspace root. **Always prefer manifest data over defaults.**

## How to find examples

Both retrieval paths need real keywords, and the only source of real keywords is the board's
vocabulary — so **step 1 is not optional**. Every script call returns in well under 100 ms, so
the extra call costs nothing.

**Exception — pure discovery.** If the user only wants to know what exists ("what examples ship
for this board?"), go straight to `list_code_examples.py --summary-only`. It needs no keywords
and returns the valid category names itself.

### 1. Get the board's vocabulary

Read `<workspace-root>/.modustoolbox/code_example_vocabulary.yaml`. The server writes it
unconditionally at startup, so a missing file means the server is not running — and
`get_code_example_vocabulary.py` would fail for the same reason rather than rescue it. For a
board other than the current one, call that script with `--board-id <board-id>`.

It gives you the board's keywords grouped by `category`, **listed rarest (most
discriminating) first**, with a per-category `count`, plus an `acronym_map` and `synonym_map`.
All keys are lowercase and share the tag namespace, so a tag can be looked up directly.

This is what turns the user's wording into terms that exist for **this** board. "keyword
spotter" matches nothing in the catalog; the vocabulary shows `deepcraft` and `ml`, which find
the voice-assistant examples.

### 2. Search

Expand the request against the vocabulary, then search:

```bash
python .github/skills/mtb-tools/scripts/search_code_examples.py \
    --tag <tag> --tag <tag> --query-terms "<the user's wording>" --role <role>
```

- `--tag` — **only tags present in the vocabulary**, 5–8 at most. Prefer tags listed earlier in a
  category; they are rarer and discriminate better. A tag that is not in the vocabulary scores
  nothing. Never invent one.
- `--query-terms` — the user's own wording, as free text. Token/stem matched across name,
  keywords, category, and description. This is where words like "breathing" or "fade" belong:
  they will never be tags, but they do match descriptions.
- `--role` — when the request implies one: `server`, `client`, `central`, `peripheral`, `source`,
  `sink`.

Results come back highest score first, each with a `score`, `matched_tags`, `matched_terms`, and
a `snippet`. `applied` echoes what was actually scored — check it when the ranking surprises you.
`--limit` defaults to 20.

### 3. Judge the results

Read the top hits' `snippet` and `matched_terms`, keep the 3–8 that genuinely fit, and say why
each is relevant.

**Do not use an absolute score threshold.** Scores are IDF sums over whichever terms you passed,
so they are comparable only *within* a single query — a correct top hit scored 16.4 on one
request and 65.6 on another. Judge by whether the hits matched what was asked, not by the number.

### 4. Fall back only when the search was inconclusive

| Situation | Do this |
| --- | --- |
| `returned: 0` | **Re-search first.** Follow the response's `suggestion`: swap in vocabulary tags, bridge wording through `synonym_map`/`acronym_map`, generalize `--query-terms`, or drop `--role`. Browsing with the same unusable words fails the same way. Browse only if a second search still returns 0. |
| Top hits' `matched_tags`/`matched_terms` miss the request's main concept | Browse the neighbourhood with `--keyword` / `--category`. |
| The user wants completeness — "all", "what else", "the full list" | Browse. |

**`--tag` and `--keyword` are different namespaces.** `--tag` (search) must come from the
vocabulary or it scores nothing. `--keyword` (browse) is a plain substring match across fields,
so any term works — but vocabulary tags are still the reliable ones.

## Browse path — `list_code_examples.py`

The listing tool supports server-side filtering so you don't have to pull the whole catalog into context:

- `--keyword <term>` — case-insensitive substring matched across name, keywords, category, and description. **Repeat the flag (or comma-separate) to pass a set**; an example matches if it contains **any** of the keywords (a wide candidate net).
- `--category <cat>` — case-insensitive **substring** match on the example's category. **Valid category names are board-specific and self-describing:** they are exactly the keys of `counts_by_category` in any response (from the manifest, not a fixed list — some device families lack e.g. Wi-Fi or Graphics). Commonly seen: `Audio`, `Bluetooth`, `Getting Started`, `Graphics`, `Machine Learning`, `Peripherals`, `Security`, `Sensing`, `Wi-Fi` — but confirm against `counts_by_category` for the current board.
- `--summary-only` — return **only** `total_unfiltered` + `counts_by_category` (+ notes), no example list. The cheapest way to **discover the valid categories** and the distribution for this board before drilling in.
- `--limit <N>` — max results. **Applies only when you pass `--keyword`** (defaults to 20 then). A bare or **category-only** call returns the **full** list, since there is no relevance signal to justify capping an unranked browse.

The response is self-describing: it reports `total_unfiltered`, `returned`, the `applied_filters`, a `truncated` flag when more matched than the limit, `notes` (e.g. when the limit was ignored), and a `suggestion` to broaden when nothing matched. `counts_by_category` reflects the **full match distribution before the limit**, and results are **not ranked** — order is stable, not by relevance — so you do the final relevance judgement yourself.

1. **Discover scope cheaply first** when you don't know the board's capabilities: `list_code_examples.py --summary-only`. Its `counts_by_category` keys are the exact, valid category names for this board, and the counts show where the examples are.
2. Prefer a **filtered** query over dumping everything, e.g.:
   - "BLE examples" → `--keyword ble` (or `--category Bluetooth`)
   - "Wi-Fi MQTT" → `--keyword mqtt --category Wi-Fi`
   - "wireless sensor options" → `--keyword ble --keyword wifi --keyword sensor` (any-match widens the net)
   ```bash
   python .github/skills/mtb-tools/scripts/list_code_examples.py --keyword <term> --keyword <term> --category <cat>
   ```
3. If `returned` is 0, follow the `suggestion`: broaden or drop a keyword, drop the category, or try more general terms.
4. If `truncated` is true, add a more specific keyword or category rather than raising the limit blindly.
5. Identify examples that best match the user's requested feature, board, or device family.
6. Summarize the top 3–8 matches in a compact list and explain why each is relevant.
7. If there is no exact match, suggest the closest alternatives and say why.

## Output guidelines

- Prefer the most relevant 3-8 examples instead of dumping everything.
- Group results by feature area when helpful, such as connectivity, RTOS, AI/ML, sensors, or peripheral drivers.
- Mention board or device compatibility when known.
- Do not invent repository names, features, or support claims.
- Be clear when an example is adjacent rather than an exact match.

## Suggested response structure

Include:

- a brief one-line summary
- a short bullet list of recommended examples
- the main feature or use case for each example
- a note on which one is the best starting point

## Example intent

- "Show me UART examples for this board"
- "Find a FreeRTOS sample I can adapt"
- "What code examples exist for BLE or Wi-Fi?"
- "Give me a good ModusToolbox starter project"

## Notes

This skill is especially useful before generating new code, because a real example project often reveals the correct middleware, initialization order, build settings, and board-specific patterns.
