# AdamHUB Pantry Skill

Use for inventory management and stock control.

## Actions

<!-- BEGIN GENERATED: action-list (source: app/skill/actions.py ACTION_CATALOG) -->
- `pantry.add_item`
- `pantry.list_items`
- `pantry.update_item`
- `pantry.consume_item`
- `pantry.delete_item`
- `pantry.overview`
- `pantry.lookup_barcode`
<!-- END GENERATED: action-list -->

## Rules

- Use `pantry.overview` before shopping recommendations.
- Never reduce quantities below zero (API already guards this).
- Physical measurability: Any food that can be weighed or measured in mass/volume (meats, fish, liquids, pasta, grains, cheeses) MUST be stored in standard metric units (`g`, `kg`, `ml`, `cl`, `l`). The unit `item` is strictly reserved for natural whole piece foods (`Avocat`, `Pomme`, `Oeuf`, `Citron`, `Oignon`). Fish and meat portions must be stored in grams (e.g. 250 g), with piece counts in notes (e.g. note: "2 pavés"). Never use cuts as units (`pavés`, `morceaux`).
- Culinary disambiguation: Distinguish culinary states in `name` (`Saumon frais` vs `Saumon fumé`, `Thon en boîte` vs `Thon frais`). Physical cuts (e.g. `pavé`, `filet`) belong in `note`.
