# Feature Specification: Pantry Stock Management, Ingredient Normalization & Open Food Facts Scanner

**Feature Branch**: `009-pantry-stock-openfoodfacts`

**Created**: 2026-09-15

**Status**: Ready for Planning

**Input**: User description: "Dans cet utilisateur, je me retrouve avec une recette de pâtes au saumon, donc dedans il y a saumon et l'unité c'est en pavés. Je me retrouve ensuite avec une autre recette, saumon teriyaki avec riz, et là dedans c'est du saumon et l'unité c'est les pavés. Et en stock, j'ai du saumon. Là j'ai du saumon et il y a marqué que c'est c'est du poisson et j'ai 250 g de saumon. On ne sait pas si c'est du saumon fumé, du saumon, tu vois. Il faudrait que tu corriges ces deux recettes ainsi que ce qui est écrit dans mon garde-manger et que tu revois les garde-fous et les directives pour que l'IA ne fasse plus ça. J'aimerais bien aussi que l'agent ne fasse plus ça et permettre à l'utilisateur de modifier le stock. Intégrer aussi le fait de ajouter des items venant de Open Food Facts. La pipeline serait scanner le code-barres, s'il est reconnu qu'il se trouve dans la base de données de Open Food Facts, l'ajouter au stock, mais avant de l'ajouter au stock, faire cette conversion de les pâtes Carrefour Extra, je sais pas quoi, à pâtes trombonnes 250 g, un truc du genre. Et s'il manque des informations venant de Open Food Facts, pourquoi pas proposer à l'utilisateur la possibilité de modifier ou de compléter le produit."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - User Pantry Stock Modification & Full Editing (Priority: P1)

As a user managing my household pantry, I want to edit any item in my stock directly (updating exact quantity via numerical keyboard input, changing unit, modifying name, category, storage location, and expiration date) so that my inventory accurately reflects what is physically in my kitchen.

**Why this priority**: Currently, pantry items can only be incremented or decremented by 1 unit via +/- buttons. When an item is measured in grams (e.g. 250 g of salmon), adjusting quantities is impossible without entering exact numbers. Direct stock modification is fundamental to inventory trust and usability.

**Independent Test**: Can be tested independently by navigating to the pantry screen, opening an existing item (e.g. "Saumon frais"), directly typing a new quantity (e.g. 300 g), changing its category or expiration date, saving, and verifying the updated values persist immediately.

**Acceptance Scenarios**:

1. **Given** an existing pantry item "Saumon frais" with quantity `250` and unit `g`, **When** the user taps on the item to edit, changes the quantity to `300` and sets an expiration date, **Then** the updated values are saved and displayed correctly in the pantry list.
2. **Given** a user viewing their pantry list, **When** they open the item editor, **Then** they can directly type the exact amount using a numeric keyboard rather than clicking a +/- button repeatedly.
3. **Given** an item with an inaccurate name or category, **When** the user edits the item name to "Saumon frais" and unit to "g", **Then** the pantry item is updated cleanly without creating duplicate records or breaking grocery-pantry sync links.

---

### User Story 2 - Correction and Disambiguation of Existing Recipes & Pantry Items (Priority: P1)

As a home cook, I want my existing recipes ("Pâtes au saumon", "Saumon teriyaki avec riz") and pantry items ("Saumon") to have precise, disambiguated product names (distinguishing culinary state, e.g. "Saumon frais" vs "Saumon fumé") and measurable metric units (weight in `g` for fish/meat portions), with piece mentions relegated to notes, so that recipes clearly indicate the exact food required and cook deductions match inventory seamlessly.

**Why this priority**: Ambiguous ingredient names ("Saumon") prevent the user and the system from knowing whether an ingredient refers to fresh salmon fillets or smoked salmon. Furthermore, using "pavés" as a unit violates standard metric conventions and breaks automatic cook deductions against a pantry stocked in grams.

**Independent Test**: Can be tested independently by inspecting the user's database: verifying that "Pâtes au saumon" and "Saumon teriyaki avec riz" use canonical ingredient names ("Saumon frais") with metric weight units (`g`), that cuts/pieces are in notes ("pavé", "2 pavés"), and that the pantry salmon item explicitly specifies "Saumon frais" (250 g, Poisson).

**Acceptance Scenarios**:

1. **Given** the recipe "Saumon teriyaki avec riz", **When** viewing its ingredient list, **Then** the salmon ingredient is specified as `name: "Saumon frais"`, `quantity: 300.0`, `unit: "g"`, and `note: "2 pavés de 150 g"`, and the prohibited unit "pavés" is eliminated.
2. **Given** the recipe "Pâtes au saumon", **When** viewing its ingredient list, **Then** the salmon ingredient is explicitly qualified as `name: "Saumon frais"`, `quantity: 250.0`, `unit: "g"`, and `note: "pavé"`.
3. **Given** the user's pantry item currently named generic "Saumon" (250 g, Poisson), **When** updated, **Then** its name is corrected to "Saumon frais" (250 g, Poisson), perfectly aligning with recipes that consume it.

---

### User Story 3 - AI Directives & Guardrails for Physical Measurability and Disambiguation (Priority: P2)

As a system user chatting with the AI assistant or generating recipes and shopping lists, I want the AI assistant to strictly enforce physical measurability (metric units `g`/`kg`/`ml`/`l` for measurable foods; `item` strictly reserved for natural piece units like eggs and avocados) and culinary disambiguation (e.g. `Saumon frais` vs `Saumon fumé`) so that it never generates recipes or pantry entries with cut-as-unit (e.g. "pavés") or ambiguous generic names.

**Why this priority**: Without strict assistant guardrails and prompt enforcement, the AI will continue generating ambiguous ingredients and invalid units in new recipes, meal plans, or pantry restocks, recreating the exact same inconsistencies.

**Independent Test**: Can be tested independently by prompting the AI assistant to create a recipe containing salmon steaks and avocado, and asserting that the assistant generates measurable foods in grams (`g`) with cuts in notes (`note: "pavés"`), natural whole foods in pieces (`item`), and distinguishes culinary nature (`Saumon frais`).

**Acceptance Scenarios**:

1. **Given** a user asking the AI assistant to create a recipe with salmon steaks, **When** the assistant outputs the recipe ingredients, **Then** the ingredient name is disambiguated (`name: "Saumon frais"`), the unit is metric (`g`), and the cut is in the note (`note: "2 pavés"`).
2. **Given** an AI assistant generating an ingredient that is a whole natural piece (e.g. avocado, egg, onion), **When** specifying the ingredient, **Then** the assistant uses `unit: "item"`, reserving `item` exclusively for natural piece foods.
3. **Given** an AI assistant tool call (`recipe__add`, `recipe__update`, `pantry__add_item`, `grocery__add_item`), **When** validated against the system guardrails, **Then** non-standard units such as "pavés", "morceaux", or "tranches" are rejected or automatically converted to metric units with note annotations.

---

### User Story 4 - Barcode Scanning & Open Food Facts Ingestion with Culinary Specificity (Priority: P2)

As a user restocking my kitchen, I want to scan a product barcode with my device camera or enter an EAN code, retrieve its product information from Open Food Facts, have brand noise (e.g. "Carrefour Extra") stripped while preserving specific culinary variety (e.g. "Pâtes penne", "Pâtes trombonnes"), and review/complete missing data (such as expiration date and storage location) in an interactive sheet before saving to pantry stock.

**Why this priority**: Scanning barcodes via Open Food Facts dramatically accelerates pantry intake. However, raw commercial product titles are polluted with marketing and supermarket branding, while sometimes lacking essential pantry metadata like expiration dates. Cleaning the name while preserving culinary specificity (e.g. knowing they are penne or trombonnes pasta, not just generic pasta) maintains pantry precision.

**Independent Test**: Can be tested independently by scanning or submitting a barcode for branded pasta (e.g. Carrefour Extra Penne 500g), observing that the intake pipeline proposes "Pâtes penne", 500 g, category "Épicerie", and allowing the user to add an expiration date and confirm addition to the pantry.

**Acceptance Scenarios**:

1. **Given** a user scanning a product barcode recognized by Open Food Facts (e.g. "Carrefour Extra Penne Rigate 500g"), **When** product data is fetched, **Then** the system presents a review sheet pre-filled with the culinary-specific name (`Pâtes penne`), net quantity (`500`), unit (`g`), category (`Épicerie`), and brand recorded in the brand/note field.
2. **Given** an Open Food Facts product missing an expiration date or storage location, **When** presented in the review sheet, **Then** these fields are highlighted for completion and the user can easily select them before confirming.
3. **Given** a barcode not found in Open Food Facts, **When** scanned, **Then** the system notifies the user gracefully and opens a manual creation form with the scanned barcode already attached.

---

### Edge Cases

- What happens if an Open Food Facts product has multiple package sizes or ambiguous quantities (e.g. "6x100g")? The system extracts total net weight when available, formats it as quantity and unit (e.g. 600 g), and lets the user edit or confirm in the review sheet.
- What happens when a user scans a barcode for an item already present in the pantry? The system detects the matching existing item and offers to either increment the existing stock quantity or create a separate lot with a different expiration date.
- What happens if the device is offline or the Open Food Facts API is unreachable/slow? The scanner shows a friendly error message with an instant fallback to manual entry so the user is never blocked.
- What happens if an ingredient could be either piece or weight (e.g. fresh mozzarella ball)? If standard commercial packaging is by weight (e.g. 125 g), the system records weight in `g` and piece details in `note` ("1 boule").
- What happens if an ingredient is entered with a deprecated unit like "pavés"? The backend normalization layer maps it to `unit: "g"` (using standard portion defaults, e.g. 1 pavé = 125-150 g) and places "pavé" into the `note` attribute.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow users to view and directly edit all fields of any existing pantry item (name, quantity, unit, category, storage location, min_quantity, expiration date) through both the mobile application and the web interface.
- **FR-002**: Pantry quantity editing MUST support direct numerical keyboard input in addition to quick increment/decrement controls.
- **FR-003**: Existing user recipes ("Pâtes au saumon" and "Saumon teriyaki avec riz") and the user's pantry item ("Saumon") MUST be corrected to replace non-standard units (such as "pavés") with valid standardized metric units (`g`) and accurate portion notes.
- **FR-004**: System MUST distinguish distinct culinary states and preparations of ingredients in canonical names (e.g. `Saumon frais`, `Saumon fumé`, `Thon en boîte`) so that recipes and inventory do not ambiguously conflate incompatible foods. Physical cuts and preparations (e.g. `pavé`, `filet`, `émincé`, `tranches`) MUST remain strictly in the `note` attribute.
- **FR-005**: AI Assistant system directives (`context_builder.py`, skill definitions, and prompt templates) MUST be updated with explicit guardrails enforcing culinary disambiguation (e.g. `Saumon frais` vs `Saumon fumé`) and physical measurability.
- **FR-006**: Backend validation and normalization MUST reject or normalize non-standard ingredient and pantry units, strictly enforcing the allowed unit vocabulary (`g`, `kg`, `ml`, `cl`, `l`, `c. à soupe`, `c. à café`, `pincée`, `item`).
- **FR-007**: When cuts (such as "pavé", "filet", "gousse") are specified, they MUST be stored exclusively in the `note` attribute, never in the `unit` or `name` attributes.
- **FR-008**: System MUST enforce physical measurability: any ingredient that can be weighed or measured in mass/volume (meats, fish, liquids, pasta, grains, cheeses) MUST be expressed in standard metric units (`g`, `kg`, `ml`, `cl`, `l`). The unit `item` is strictly reserved for naturally countable, whole-piece items (e.g. `Avocat`, `Pomme`, `Oeuf`, `Citron`, `Oignon`). For fish and meat portions (e.g. salmon steaks), recipes and pantry stock MUST be specified in grams (e.g. 250 g), with piece counts or cuts recorded in notes (e.g. note: "2 pavés").
- **FR-009**: System MUST provide an Open Food Facts integration service that queries product details by barcode (EAN-13, EAN-8, UPC) over HTTPS.
- **FR-010**: System MUST support barcode scanning via device camera in the mobile application, as well as manual barcode entry on both web and mobile surfaces.
- **FR-011**: Open Food Facts intake pipeline MUST transform raw commercial product titles by stripping retailer branding (e.g. "Carrefour Extra") while preserving specific culinary varieties (e.g. "Pâtes penne", "Pâtes trombonnes", "Riz basmati").
- **FR-012**: System MUST display an interactive review and completion dialog before saving scanned products to the pantry, allowing the user to validate the proposed culinary name, adjust quantities, and supply missing attributes (expiration date, storage location).
- **FR-013**: If Open Food Facts does not contain the scanned barcode, the system MUST allow the user to manually create the product and associate the barcode with it for future recognition.
- **FR-014**: All pantry updates, creations, and deletions MUST remain strictly scoped to the authenticated tenant/user in compliance with Constitution Principle I.
- **FR-015**: Barcode lookups SHOULD cache Open Food Facts responses locally to reduce external network calls and enable rapid subsequent scans.

### Key Entities *(include if feature involves data)*

- **PantryItem**: Represents physical food items currently in the household stock. Attributes: `id`, `user_id`, `name` (culinary name, e.g. "Saumon frais", "Pâtes penne"), `quantity` (numeric), `unit` (`g`, `kg`, `ml`, `cl`, `l`, `item`), `category`, `storage_location` (e.g. Réfrigérateur, Placard, Congélateur), `min_quantity`, `expires_at`, `barcode`, `brand`, `note` (e.g. "2 pavés").
- **RecipeIngredient**: Ingredient requirement belonging to a recipe. Attributes: `id`, `recipe_id`, `name` (canonical base name distinguishing culinary nature, e.g. "Saumon frais"), `quantity` (numeric), `unit` (standardized metric or piece unit), `note` (cuts, preparation details, piece counts).
- **OpenFoodFactsProductDraft**: Ephemeral representation of a product scanned from Open Food Facts prior to user confirmation. Attributes: `barcode`, `raw_name`, `brand`, `suggested_name` (cleaned culinary name), `quantity`, `unit`, `category`, `image_url`, `nutriscore`, `missing_fields`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the user's existing recipes and pantry items have valid, standardized metric units (`g`, `kg`, etc.) or natural piece units (`item`) with zero instances of cut-based units like "pavés".
- **SC-002**: Users can edit an existing pantry item's quantity, unit, or metadata in under 5 seconds using direct numerical keyboard input.
- **SC-003**: Barcode lookups against Open Food Facts return product information and pre-fill the confirmation sheet with a cleaned culinary name in under 2 seconds on standard mobile connectivity.
- **SC-004**: 0% of AI-generated recipes or pantry suggestions introduce prohibited units or conflate ambiguous product forms after guardrail updates.
- **SC-005**: 100% of scanned products allow user inspection and field correction before committing inventory changes to the database.

## Assumptions

- Open Food Facts API is freely accessible over HTTPS without requiring commercial API keys for standard read queries (using a compliant User-Agent as per Open Food Facts policy).
- Mobile device has camera hardware and permissions for barcode scanning (using Expo Camera / BarcodeScanner or equivalent native scanner).
- The user's current database is accessible for data migration and correction of the two specific recipes ("Pâtes au saumon", "Saumon teriyaki avec riz") and the pantry stock item.
- Existing database schema can support optional barcode and brand fields on `PantryItem` without breaking backwards compatibility.
