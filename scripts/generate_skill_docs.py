#!/usr/bin/env python3
"""Sync the "## Actions" lists in adamhub-assistant/<domain>/SKILL.md files
against the authoritative ACTION_CATALOG in app/skill/actions.py.

Each SKILL.md action list is hand-maintained prose today, so this script
only owns the block between two HTML-comment markers:

    <!-- BEGIN GENERATED: action-list (source: app/skill/actions.py ACTION_CATALOG) -->
    - `action.name`
    ...
    <!-- END GENERATED: action-list -->

On first run against a file that has a "## Actions" section but no markers
yet, the script wraps that section's bullet list in markers (one-time
migration) and fills it with the catalog-derived content.

Usage:
    python scripts/generate_skill_docs.py            # regenerate in place
    python scripts/generate_skill_docs.py --check     # CI mode: exit 1 on drift, no writes
    python scripts/generate_skill_docs.py --diff       # show unified diffs of what would change
"""

from __future__ import annotations

import argparse
import ast
import difflib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ACTIONS_PY = REPO_ROOT / "app" / "skill" / "actions.py"
SKILL_ROOT = REPO_ROOT / "adamhub-assistant"

BEGIN_MARKER = "<!-- BEGIN GENERATED: action-list (source: app/skill/actions.py ACTION_CATALOG) -->"
END_MARKER = "<!-- END GENERATED: action-list -->"

# Maps an adamhub-assistant/<domain>/SKILL.md folder to the ACTION_CATALOG
# action-name prefixes it owns. Prefixes with no owning domain folder today
# (calendar, dashboard, linear, ubereats) are reported but not written
# anywhere -- see the "unassigned" warning in the script output.
DOMAIN_ACTION_PREFIXES = {
    "events": ["event"],
    "finance": ["finance"],
    "fitness": ["fitness"],
    "goals": ["goal"],
    "groceries": ["supermarket", "grocery"],
    "habits": ["habit"],
    "notes": ["note"],
    "pantry": ["pantry"],
    "patrimony": ["patrimony"],
    "recipes": ["recipe", "video", "meal_plan"],
    "subscriptions": ["subscription"],
    "tasks": ["task"],
}


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


def actions_for_prefixes(catalog: list[dict], prefixes: list[str]) -> list[str]:
    prefix_set = set(prefixes)
    return [
        entry["action"]
        for entry in catalog
        if entry["action"].split(".", 1)[0] in prefix_set
    ]


def render_block(actions: list[str]) -> str:
    lines = [BEGIN_MARKER]
    lines.extend(f"- `{action}`" for action in actions)
    lines.append(END_MARKER)
    return "\n".join(lines)


def splice_markers(text: str, block: str) -> str | None:
    begin_idx = text.find(BEGIN_MARKER)
    end_idx = text.find(END_MARKER)
    if begin_idx != -1 and end_idx != -1:
        end_idx += len(END_MARKER)
        return text[:begin_idx] + block + text[end_idx:]
    return None


def splice_actions_heading(text: str, block: str) -> str | None:
    """One-time migration: find '## Actions' and the bullet list right
    after it, and wrap that bullet list in markers."""
    heading = "## Actions"
    heading_idx = text.find(heading)
    if heading_idx == -1:
        return None
    after_heading = heading_idx + len(heading)
    rest = text[after_heading:]
    lines = rest.splitlines(keepends=True)

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

    prefix = text[: after_heading] + "".join(lines[:bullets_start])
    suffix = "".join(lines[bullets_end:])
    return prefix + block + "\n" + suffix


def regenerate_file(path: Path, actions: list[str]) -> tuple[str, str] | None:
    """Returns (old_text, new_text) if the file has a generated section,
    else None if the domain has no Actions section to manage."""
    old_text = path.read_text()
    block = render_block(actions)

    new_text = splice_markers(old_text, block)
    if new_text is None:
        new_text = splice_actions_heading(old_text, block)
    if new_text is None:
        return None
    return old_text, new_text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any SKILL.md action list is out of sync (no writes). Suitable for CI.",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Print unified diffs of what would change.",
    )
    args = parser.parse_args()

    catalog = load_action_catalog()
    catalog_prefixes = {entry["action"].split(".", 1)[0] for entry in catalog}
    mapped_prefixes = {p for prefixes in DOMAIN_ACTION_PREFIXES.values() for p in prefixes}
    unassigned = sorted(catalog_prefixes - mapped_prefixes)

    drifted: list[str] = []
    missing_section: list[str] = []
    updated: list[str] = []

    for domain, prefixes in sorted(DOMAIN_ACTION_PREFIXES.items()):
        skill_path = SKILL_ROOT / domain / "SKILL.md"
        if not skill_path.exists():
            print(f"warning: no SKILL.md for domain '{domain}' at {skill_path}", file=sys.stderr)
            continue

        actions = actions_for_prefixes(catalog, prefixes)
        result = regenerate_file(skill_path, actions)
        if result is None:
            missing_section.append(domain)
            continue
        old_text, new_text = result

        if old_text == new_text:
            continue

        drifted.append(domain)
        rel = skill_path.relative_to(REPO_ROOT)

        if args.diff or args.check:
            diff = difflib.unified_diff(
                old_text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
            )
            sys.stdout.writelines(diff)

        if not args.check:
            skill_path.write_text(new_text)
            updated.append(domain)

    if unassigned:
        print(
            "warning: ACTION_CATALOG prefixes with no owning adamhub-assistant/<domain>/SKILL.md: "
            + ", ".join(unassigned),
            file=sys.stderr,
        )
    if missing_section:
        print(
            "note: domains with no '## Actions' section / markers to manage: "
            + ", ".join(missing_section),
            file=sys.stderr,
        )

    if args.check:
        if drifted:
            print(f"\nDRIFT: {len(drifted)} SKILL.md file(s) out of sync: {', '.join(drifted)}", file=sys.stderr)
            return 1
        print("OK: all SKILL.md action lists match ACTION_CATALOG.")
        return 0

    if updated:
        print(f"Updated {len(updated)} SKILL.md file(s): {', '.join(updated)}")
    else:
        print("No changes needed; all SKILL.md action lists already match ACTION_CATALOG.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
