#!/usr/bin/env python3
"""Sync generated action documentation against the authoritative ACTION_CATALOG
in app/skill/actions.py.

The script owns several generated blocks, each delimited by HTML-comment
markers, and rewrites them from the catalog on every run:

1. The "## Actions" lists in adamhub-assistant/<domain>/SKILL.md files
   (one block per domain, marker: action-list).
2. The action count + quick action index in the master
   adamhub-assistant/SKILL.md (markers: action-count, action-index).
3. The full action catalog reference at
   adamhub-assistant/references/action-catalog.md (marker: action-catalog).

On first run against a file that has the hand-maintained section but no
markers yet, the script wraps that section in markers (one-time migration)
and fills it with the catalog-derived content.

Usage:
    python scripts/generate_skill_docs.py            # regenerate in place
    python scripts/generate_skill_docs.py --check     # CI mode: exit 1 on drift, no writes
    python scripts/generate_skill_docs.py --diff       # show unified diffs of what would change (no writes)
"""

from __future__ import annotations

import argparse
import ast
import difflib
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ACTIONS_PY = REPO_ROOT / "app" / "skill" / "actions.py"
SKILL_ROOT = REPO_ROOT / "adamhub-assistant"
MASTER_SKILL = SKILL_ROOT / "SKILL.md"
CATALOG_REF = SKILL_ROOT / "references" / "action-catalog.md"

CATALOG_SOURCE = "app/skill/actions.py ACTION_CATALOG"
BEGIN_ACTION_LIST = f"<!-- BEGIN GENERATED: action-list (source: {CATALOG_SOURCE}) -->"
END_ACTION_LIST = "<!-- END GENERATED: action-list -->"
BEGIN_ACTION_COUNT = f"<!-- BEGIN GENERATED: action-count (source: {CATALOG_SOURCE}) -->"
END_ACTION_COUNT = "<!-- END GENERATED: action-count -->"
BEGIN_ACTION_INDEX = f"<!-- BEGIN GENERATED: action-index (source: {CATALOG_SOURCE}) -->"
END_ACTION_INDEX = "<!-- END GENERATED: action-index -->"
BEGIN_ACTION_CATALOG = f"<!-- BEGIN GENERATED: action-catalog (source: {CATALOG_SOURCE}) -->"
END_ACTION_CATALOG = "<!-- END GENERATED: action-catalog -->"

# "As of" date shown next to the action count in the master SKILL.md. Bump
# when the catalog changes and you want the doc to carry a fresh date.
ACTION_COUNT_DATE = "2026-08-14"

# Maps an adamhub-assistant/<domain>/SKILL.md folder to the ACTION_CATALOG
# action-name prefixes it owns. Prefixes with no owning domain folder today
# (calendar, dashboard) are reported but not written anywhere -- see the
# "unassigned" warning in the script output.
DOMAIN_ACTION_PREFIXES = {
    "events": ["event"],
    "finance": ["finance"],
    "fitness": ["fitness"],
    "goals": ["goal"],
    "groceries": ["supermarket", "grocery"],
    "habits": ["habit"],
    "linear": ["linear"],
    "notes": ["note"],
    "pantry": ["pantry"],
    "patrimony": ["patrimony"],
    "recipes": ["recipe", "video", "meal_plan"],
    "subscriptions": ["subscription"],
    "tasks": ["task"],
}

# Section groupings (title, owning prefixes) for the full action catalog
# reference at adamhub-assistant/references/action-catalog.md.
CATALOG_SECTIONS = [
    ("Dashboard", ["dashboard"]),
    ("Tasks", ["task"]),
    ("Finance", ["finance"]),
    ("Fitness", ["fitness"]),
    ("Groceries and supermarket", ["supermarket", "grocery"]),
    ("Video intake", ["video"]),
    ("Recipes", ["recipe"]),
    ("Meal plans", ["meal_plan"]),
    ("Calendar", ["calendar"]),
    ("Habits", ["habit"]),
    ("Goals", ["goal"]),
    ("Events", ["event"]),
    ("Subscriptions", ["subscription"]),
    ("Linear", ["linear"]),
    ("Patrimony", ["patrimony"]),
    ("Pantry", ["pantry"]),
    ("Notes", ["note"]),
]


def load_action_catalog() -> list[dict]:
    """Parse ACTION_CATALOG out of app/skill/actions.py via AST, without
    importing the module (which would pull in DB/settings dependencies).

    The catalog entries carry a dispatch-only `handler` key holding a
    function reference, which is not a literal; those keys are skipped so
    the metadata fields (action/description/input_schema) stay parseable.
    """
    source = ACTIONS_PY.read_text()
    tree = ast.parse(source, filename=str(ACTIONS_PY))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "ACTION_CATALOG" for t in node.targets
        ):
            catalog = []
            for entry in node.value.elts:
                item: dict = {}
                for key_node, value_node in zip(entry.keys, entry.values):
                    if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
                        continue
                    if key_node.value == "handler":
                        continue
                    item[key_node.value] = ast.literal_eval(value_node)
                catalog.append(item)
            return catalog
    raise SystemExit(f"ACTION_CATALOG assignment not found in {ACTIONS_PY}")


def action_prefix(action: str) -> str:
    return action.split(".", 1)[0]


def actions_for_prefixes(catalog: list[dict], prefixes: list[str]) -> list[str]:
    prefix_set = set(prefixes)
    return [entry["action"] for entry in catalog if action_prefix(entry["action"]) in prefix_set]


def render_action_list(actions: list[str]) -> str:
    lines = [BEGIN_ACTION_LIST]
    lines.extend(f"- `{action}`" for action in actions)
    lines.append(END_ACTION_LIST)
    return "\n".join(lines)


def render_action_count(catalog: list[dict]) -> str:
    return "\n".join(
        [
            BEGIN_ACTION_COUNT,
            f"As of `{ACTION_COUNT_DATE}`, the skill surface exposes `{len(catalog)}` actions.",
            END_ACTION_COUNT,
        ]
    )


def render_action_index(catalog: list[dict]) -> str:
    groups: dict[str, list[str]] = {}
    for entry in catalog:
        groups.setdefault(action_prefix(entry["action"]), []).append(entry["action"])
    lines = [BEGIN_ACTION_INDEX]
    lines.extend(f"- `{'|'.join(actions)}`" for actions in groups.values())
    lines.append(END_ACTION_INDEX)
    return "\n".join(lines)


def render_catalog_ref(catalog: list[dict]) -> str:
    lines = [BEGIN_ACTION_CATALOG]
    for title, prefixes in CATALOG_SECTIONS:
        selected = [entry for entry in catalog if action_prefix(entry["action"]) in prefixes]
        if not selected:
            continue
        lines.append(f"## {title}")
        lines.append("")
        for entry in selected:
            lines.append(f"- `{entry['action']}` — {entry.get('description', '')}")
            schema = entry.get("input_schema", {})
            if schema:
                fields = ", ".join(f"`{key}`: {value}" for key, value in schema.items())
                lines.append(f"  - `input_schema`: {fields}")
            else:
                lines.append("  - `input_schema`: (none)")
            lines.append("")
    lines.append(END_ACTION_CATALOG)
    return "\n".join(lines)


def splice_block(text: str, begin: str, end: str, block: str) -> str | None:
    begin_idx = text.find(begin)
    end_idx = text.find(end)
    if begin_idx != -1 and end_idx != -1 and end_idx >= begin_idx:
        end_idx += len(end)
        return text[:begin_idx] + block + text[end_idx:]
    return None


def splice_heading_block(text: str, heading: str, block: str) -> str | None:
    """One-time migration: find a heading and the bullet list right after it,
    and wrap that bullet list in markers."""
    heading_idx = text.find(heading)
    if heading_idx == -1:
        return None
    after_heading = heading_idx + len(heading)
    lines = text[after_heading:].splitlines(keepends=True)

    i = 0
    # skip blank lines right after the heading
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    bullets_start = i
    while i < len(lines) and lines[i].lstrip().startswith("- "):
        i += 1
    bullets_end = i

    if bullets_start == bullets_end:
        return None

    prefix = text[:after_heading] + "".join(lines[:bullets_start])
    suffix = "".join(lines[bullets_end:])
    return prefix + block + "\n" + suffix


def splice_count_line(text: str, block: str) -> str | None:
    """One-time migration: replace the single 'As of ..., exposes N actions.'
    sentence in the master SKILL.md with the generated count block."""
    pattern = re.compile(r"As of `[^`]+`, the skill surface exposes `\d+` actions\.\n?")
    match = pattern.search(text)
    if match is None:
        return None
    return text[: match.start()] + block + "\n" + text[match.end() :]


def splice_catalog_ref(text: str, block: str) -> str | None:
    """One-time migration: wrap the hand-maintained catalog sections (between
    '## Dashboard' and '## Field highlights') in markers."""
    start = text.find("## Dashboard")
    end = text.find("## Field highlights")
    if start == -1 or end == -1 or end < start:
        return None
    return text[:start] + block + "\n\n" + text[end:]


def regenerate_action_list(path: Path, catalog: list[dict], prefixes: list[str]) -> tuple[str, str] | None:
    old_text = path.read_text()
    block = render_action_list(actions_for_prefixes(catalog, prefixes))

    new_text = splice_block(old_text, BEGIN_ACTION_LIST, END_ACTION_LIST, block)
    if new_text is None:
        new_text = splice_heading_block(old_text, "## Actions", block)
    if new_text is None:
        return None
    return old_text, new_text


def regenerate_master_skill(catalog: list[dict]) -> tuple[str, str] | None:
    old_text = MASTER_SKILL.read_text()
    text = old_text

    count_block = render_action_count(catalog)
    before_count = text
    new_text = splice_block(text, BEGIN_ACTION_COUNT, END_ACTION_COUNT, count_block)
    if new_text is None:
        new_text = splice_count_line(text, count_block)
    if new_text is None:
        return None
    text = new_text

    index_block = render_action_index(catalog)
    before_index = text
    new_text = splice_block(text, BEGIN_ACTION_INDEX, END_ACTION_INDEX, index_block)
    if new_text is None:
        new_text = splice_heading_block(text, "## 14) Quick action index", index_block)
    if new_text is None:
        return None
    text = new_text

    if text == before_count and text == before_index and text == old_text:
        return old_text, old_text
    return old_text, text


def regenerate_catalog_ref(catalog: list[dict]) -> tuple[str, str] | None:
    old_text = CATALOG_REF.read_text()
    block = render_catalog_ref(catalog)

    new_text = splice_block(old_text, BEGIN_ACTION_CATALOG, END_ACTION_CATALOG, block)
    if new_text is None:
        new_text = splice_catalog_ref(old_text, block)
    if new_text is None:
        return None
    return old_text, new_text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any generated action doc is out of sync (no writes). Suitable for CI.",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Print unified diffs of what would change (no writes).",
    )
    args = parser.parse_args()

    catalog = load_action_catalog()
    catalog_prefixes = {action_prefix(entry["action"]) for entry in catalog}
    mapped_prefixes = {p for prefixes in DOMAIN_ACTION_PREFIXES.values() for p in prefixes}
    unassigned = sorted(catalog_prefixes - mapped_prefixes)

    covered = set()
    for _, prefixes in CATALOG_SECTIONS:
        covered.update(e["action"] for e in catalog if action_prefix(e["action"]) in prefixes)
    uncovered = sorted({entry["action"] for entry in catalog} - covered)

    targets: list[tuple[str, Path, callable]] = []
    for domain, prefixes in sorted(DOMAIN_ACTION_PREFIXES.items()):
        skill_path = SKILL_ROOT / domain / "SKILL.md"
        if not skill_path.exists():
            print(f"warning: no SKILL.md for domain '{domain}' at {skill_path}", file=sys.stderr)
            continue
        targets.append((domain, skill_path, lambda c, p=prefixes, sp=skill_path: regenerate_action_list(sp, c, p)))
    targets.append(("SKILL.md (master)", MASTER_SKILL, lambda c: regenerate_master_skill(c)))
    targets.append(("references/action-catalog.md", CATALOG_REF, lambda c: regenerate_catalog_ref(c)))

    drifted: list[str] = []
    missing_section: list[str] = []
    updated: list[str] = []

    for label, path, regenerate in targets:
        if not path.exists():
            print(f"warning: missing {path}", file=sys.stderr)
            continue
        result = regenerate(catalog)
        if result is None:
            missing_section.append(label)
            continue
        old_text, new_text = result

        if old_text == new_text:
            continue

        drifted.append(label)
        rel = path.relative_to(REPO_ROOT)

        if args.diff or args.check:
            diff = difflib.unified_diff(
                old_text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
            )
            sys.stdout.writelines(diff)

        if not args.check and not args.diff:
            path.write_text(new_text)
            updated.append(label)

    if unassigned:
        print(
            "warning: ACTION_CATALOG prefixes with no owning adamhub-assistant/<domain>/SKILL.md: "
            + ", ".join(unassigned),
            file=sys.stderr,
        )
    if uncovered:
        print(
            "warning: ACTION_CATALOG actions with no section in references/action-catalog.md: "
            + ", ".join(uncovered),
            file=sys.stderr,
        )
    if missing_section:
        print(
            "note: targets with no generated section / markers to manage: "
            + ", ".join(missing_section),
            file=sys.stderr,
        )

    if args.check:
        if drifted:
            print(
                f"\nDRIFT: {len(drifted)} generated action doc(s) out of sync: {', '.join(drifted)}",
                file=sys.stderr,
            )
            return 1
        print("OK: all generated action docs match ACTION_CATALOG.")
        return 0

    if updated:
        print(f"Updated {len(updated)} file(s): {', '.join(updated)}")
    else:
        print("No changes needed; all generated action docs already match ACTION_CATALOG.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
