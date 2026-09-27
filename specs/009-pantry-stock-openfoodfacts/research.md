# Research & Technical Decisions: Pantry Stock Management, Ingredient Normalization & Open Food Facts Scanner

**Feature**: `009-pantry-stock-openfoodfacts`  
**Date**: 2026-09-15  
**Status**: Completed  

---

## 1. Open Food Facts API Integration & Product Ingestion

### Decision
Implement a dedicated backend service `app/services/openfoodfacts.py` querying the Open Food Facts v2 API (`https://world.openfoodfacts.org/api/v2/product/{barcode}.json`) using `httpx`:
- **HTTP Client**: Use asynchronous / synchronous `httpx` with a compliant User-Agent:
  `User-Agent: AdamHUB/1.0 (https://github.com/adamelhirch/adamHub; contact@adamelhirch.com)`
- **Response Parsing**:
  - `product_name_fr` (fallback `product_name`): raw commercial title
  - `brands` or `brands_tags`: brand / manufacturer
  - `quantity`, `product_quantity`, `product_quantity_unit`: net quantity and measurement unit
  - `categories_tags`: product category classification
  - `image_url` or `image_front_url`: packaging thumbnail
  - `nutriscore_grade`: nutrition rating
- **Caching**:
  Cache responses in a local lightweight key-value / database cache (`OpenFoodFactsCache` or `SupermarketSearchCache`-style cache table) keyed by barcode with a 30-day TTL to minimize external HTTP queries.

### Rationale
- Open Food Facts is open-source, free, and provides extensive coverage of French and European consumer food products.
- Terms of service mandate a distinct User-Agent identifier.
- Fetching product metadata directly via the backend prevents CORS issues and centralizes intelligent cleanup and caching.

### Alternatives Considered
- Direct client-side `fetch` from the browser / mobile app: vulnerable to CORS restrictions, rate limits, and lacks centralized caching across devices.
- Commercial APIs (e.g. UPCitemdb, Barcode Lookup): expensive subscriptions with significantly poorer coverage of French supermarket brands (Carrefour, Intermarché, Leclerc, Monoprix).

---

## 2. Culinary Specificity Normalization Algorithm

### Decision
Create a cleaning function `clean_openfoodfacts_product(raw_product: dict) -> OpenFoodFactsCleaned` in `app/services/openfoodfacts.py` that implements a two-stage transformation:
1. **Brand & Marketing Noise Stripping**:
   - Strip retailer and manufacturer branding (e.g. "Carrefour Extra", "Simpl", "Monoprix Gourmet", "Barilla", "Panzani", "Lustucru", "Fleury Michon") from the main title, moving identified brands to the `brand` attribute.
   - Strip generic marketing fluff (e.g. "qualité supérieure", "format familial", "extra", "recette traditionnelle", "bio", "nutriscore a").
2. **Culinary Variety Preservation**:
   - Extract and preserve the specific culinary subtype (e.g. "Pâtes penne", "Pâtes spaghettoni", "Pâtes trombonnes", "Riz basmati", "Riz thaï", "Lentilles corail", "Farine de blé T55") instead of collapsing everything to a hyper-generic term like "Pâtes".
3. **Quantity & Metric Unit Extraction**:
   - Detect weights and volumes (e.g. "500g", "1 kg", "25 cl", "1L"). Convert to standardized numeric `quantity` (e.g. `500.0`) and standard metric `unit` (`g`, `kg`, `ml`, `cl`, `l`).
4. **Category Mapping**:
   - Map Open Food Facts category tags to AdamHUB's pantry categories: `Épicerie`, `Frais`, `Poisson`, `Viande`, `Produits_laitiers`, `Fruits`, `Légumes`, `Boissons`, `Surgelés`.
5. **Interactive Review Sheet**:
   - Present the cleaned proposal to the user in an intake sheet, flagging missing fields (e.g. expiration date, storage location) for completion before committing to the pantry.

### Rationale
- Aligns strictly with user guidance: distributor branding ("Carrefour") is noise, but culinary variety ("Pâtes penne" vs "Pâtes trombonnes") is essential for cooking and recipe planning.
- Eliminates messy commercial titles in the inventory while preserving necessary cooking distinctions.

### Alternatives Considered
- Direct raw import: results in bloated titles like "Carrefour Extra Penne Rigate Pâtes Alimentaires Qualité Supérieure 500g", ruining pantry readability and search.
- Aggressive collapse to generic base names ("Pâtes"): loses information that the user bought penne rather than spaghetti or lasagna sheets.

---

## 3. Physical Measurability & Disambiguation Rules

### Decision
Enforce two strict domain rules across database models, validation schemas, and AI assistant prompts:
1. **Physical Measurability Rule**:
   - Any food that is measurable in mass or volume (meats, fish, liquids, pasta, grains, flours, grated cheese) MUST use standard metric units: `g`, `kg`, `ml`, `cl`, `l`.
   - The unit `item` is STRICTLY reserved for natural whole-piece foods (e.g. `Avocat`, `Pomme`, `Oeuf`, `Citron`, `Oignon`, `Echalote`).
   - For fish and meats (e.g. salmon steaks), recipes and stock MUST be recorded in grams (e.g. `quantity: 250`, `unit: "g"`). Piece counts or cuts belong exclusively in `note` (e.g. `note: "pavé"` or `note: "2 pavés de 150 g"`).
2. **Culinary Disambiguation Rule**:
   - Incompatible culinary states MUST be distinguished in the canonical `name` (e.g. `Saumon frais`, `Saumon fumé`, `Thon en boîte`), preventing accidental substitution or incorrect stock deductions.
   - Physical cuts and preparations (`pavé`, `filet`, `émincé`, `tranches`, `dés`) remain in `note`.
3. **Unit Whitelist Enforcement**:
   - Allowed units: `["g", "kg", "ml", "cl", "l", "c. à soupe", "c. à café", "pincée", "item"]`.
   - Prohibited cut-units ("pavés", "morceaux", "tranches", "gousses", "boîtes") are intercepted by `canonical_ingredient()` in `app/services/units.py`, converted to the appropriate metric unit (or `item` for natural pieces), and the cut name is moved to `note`.

### Rationale
- Solves the exact user problem where one recipe had `2 item` (pavés), another had `250 g` (pavé), and stock had generic `250 g Saumon` (uncertain whether fresh or smoked).
- Guarantees arithmetic precision when deducting stock on recipe cooking.

---

## 4. Mobile & Web UX for Barcode Scanning & Direct Stock Editing

### Decision
1. **Direct Stock Editing**:
   - **Mobile (`app-saas`)**: Replace the restrictive +/- 1 buttons on `pantry.tsx` with a tap-to-open Edit Sheet / Modal allowing direct keypad numeric entry for `quantity`, selection of `unit`, editing of `name`, `category`, `storage_location` (`Réfrigérateur`, `Placard`, `Congélateur`), `expires_at` (native date picker / formatted text), and `min_quantity`. Quick +/- 1 buttons remain available for piece items.
   - **Web (`web`)**: Add an edit button / modal on pantry cards in `GroceriesPage.tsx` to update quantities, units, and details.
2. **Barcode Scanner**:
   - **Mobile (`app-saas`)**: Integrate camera barcode scanning via `expo-camera` (using `CameraView` with `barcodeScannerSettings={{ barcodeTypes: ['ean13', 'ean8', 'upc_a', 'upc_e'] }}`), plus a manual numeric EAN input toggle.
   - **Web (`web`)**: Add a manual EAN input dialog with instant Open Food Facts lookup.
3. **Pre-fill & Review Flow**:
   - Scanning a barcode triggers `GET /api/v1/pantry/barcode/{barcode}`.
   - A bottom sheet modal opens displaying:
     - Scanned barcode and product thumbnail
     - Cleaned culinary name (editable)
     - Net quantity and unit (editable)
     - Detected category (editable)
     - Storage location (selectable: Placard, Réfrigérateur, Congélateur)
     - Expiration date picker
   - User taps "Ajouter au garde-manger" to commit (`POST /api/v1/pantry/items`).

### Rationale
- Directly answers the user request: "permettre à l'utilisateur de modifier le stock" and "proposer à l'utilisateur la possibilité de modifier ou de compléter le produit".
- Dual entry (camera scan + manual barcode digits) ensures usability even under poor lighting, damaged barcodes, or simulator testing.

---

## 5. Migration & Data Correction for Existing User Records

### Decision
Create and run a targeted database migration script `scripts/fix_user_recipes_and_pantry_saumon.py`:
1. **Recipe 1 (`Saumon teriyaki avec riz`)**:
   - Update ingredient "Saumon":
     - `name`: `"Saumon frais"`
     - `quantity`: `300.0`
     - `unit`: `"g"`
     - `note`: `"2 pavés de 150 g"`
2. **Recipe 12 (`Pâtes crémeuses au saumon`)**:
   - Update ingredient "Saumon":
     - `name`: `"Saumon frais"`
     - `quantity`: `250.0`
     - `unit`: `"g"`
     - `note`: `"pavé"`
3. **Pantry Item 7 (`Saumon`)**:
   - Update:
     - `name`: `"Saumon frais"`
     - `quantity`: `250.0`
     - `unit`: `"g"`
     - `category`: `"Poisson"`
     - `location`: `"Réfrigérateur"`
     - `note`: `"2 pavés"`

### Rationale
- Fixes the user's live database state immediately, eliminating the existing unit discrepancy between the recipes and the pantry.

---

## 6. AI Assistant Guardrails & Synchronous Contract Updates

### Decision
In accordance with Constitution Principle V (Contract Synchronization):
1. **Assistant System Prompt (`app/services/assistant/context_builder.py`)**:
   - Update Section 8 to strictly enforce:
     - Physical measurability: meats and fish in `g`/`kg`, `item` only for natural whole pieces (avocat, œuf, citron).
     - Culinary disambiguation: distinct states in `name` (`Saumon frais`, `Saumon fumé`, `Thon en boîte`).
     - Zero tolerance for cuts as units: "pavé", "filet", "tranche" are prohibited as units and must be in `note`.
2. **Skill Documentation (`adamhub-assistant/recipes/SKILL.md` & `pantry/SKILL.md`)**:
   - Document new rules, actions, and validation constraints.
3. **Action Catalog (`app/skill/actions.py`) & Handlers**:
   - Register `pantry.lookup_barcode` in `ACTION_CATALOG`.
   - Update `pantry.update_item` and `pantry.add_item` handlers to support full stock editing and barcode metadata.
