export interface BenchmarkAssertion {
  ingredientName: string;
  expectedKeywords: string[];
  prohibitedKeywords: string[];
  maxExpectedPriceEuros?: number;
  reason?: string;
}

export interface BenchmarkCase {
  id: string;
  recipeName: string;
  store: 'carrefour' | 'intermarche' | 'leclerc' | 'auchan';
  strategy: 'budget' | 'mdd' | 'bio';
  assertions: BenchmarkAssertion[];
}

export const CANONICAL_BENCHMARKS: BenchmarkCase[] = [
  {
    id: 'dahl-lentilles-corail-carrefour-budget',
    recipeName: 'Dahl de lentilles corail (Marmiton)',
    store: 'carrefour',
    strategy: 'budget',
    assertions: [
      {
        ingredientName: 'Lentilles corail',
        expectedKeywords: ['lentille', 'corail'],
        prohibitedKeywords: ['tranches', 'fleury', 'salade', 'houmous', 'veloute', 'soupe', 'terrine'],
        reason: 'Raw lentils required; no processed vegan cold cuts, salads, hummus, or soups',
      },
      {
        ingredientName: 'Lait de coco',
        expectedKeywords: ['coco'],
        prohibitedKeywords: ['vache', 'creme fraiche'],
        reason: 'Coconut milk must contain coconut; no dairy cow milk',
      },
      {
        ingredientName: 'Gousses d\'ail',
        expectedKeywords: ['ail'],
        prohibitedKeywords: ['volaille', 'poulet', 'viande'],
        reason: 'Garlic must not match poultry/chicken broth via substring',
      },
      {
        ingredientName: 'Sel',
        expectedKeywords: ['sel'],
        prohibitedKeywords: ['beurre', 'margarine', 'sucre'],
        reason: 'Table salt must never match butter',
      },
      {
        ingredientName: 'Concentré de tomates',
        expectedKeywords: ['tomate'],
        prohibitedKeywords: ['ketchup', 'veloute'],
        reason: 'Tomato concentrate must match authentic tomato paste',
      },
    ],
  },
  {
    id: 'pates-saumon-carrefour-mdd',
    recipeName: 'Pâtes crémeuses au saumon',
    store: 'carrefour',
    strategy: 'mdd',
    assertions: [
      {
        ingredientName: 'Pavé de saumon',
        expectedKeywords: ['saumon'],
        prohibitedKeywords: ['surimi', 'poulet', 'thon', 'pizza', 'quiche', 'lasagne', 'rillette'],
        reason: 'Salmon must match genuine salmon fillets; no microwave ready-meals or rillettes',
      },
      {
        ingredientName: 'Pâtes penne',
        expectedKeywords: ['penne', 'pate'],
        prohibitedKeywords: ['riz', 'lentille', 'salade', 'box'],
        reason: 'Pasta must match authentic pasta cut; no prepared pasta salads',
      },
      {
        ingredientName: 'Crème fraîche',
        expectedKeywords: ['creme'],
        prohibitedKeywords: ['coco', 'beurre', 'glace', 'dessert'],
        reason: 'Cream must match culinary cooking cream; no desserts or ice cream',
      },
    ],
  },
  {
    id: 'fitness-poulet-brocolis-riz-leclerc-budget',
    recipeName: 'Meal-prep Poulet Brocolis Riz',
    store: 'leclerc',
    strategy: 'budget',
    assertions: [
      {
        ingredientName: 'Filets de poulet',
        expectedKeywords: ['poulet'],
        prohibitedKeywords: ['nugget', 'cordon', 'pane', 'sandwich', 'salade', 'chips'],
        reason: 'Raw chicken fillets required; 0% nuggets, cordons bleus, or processed snacks',
      },
      {
        ingredientName: 'Riz basmati',
        expectedKeywords: ['riz'],
        prohibitedKeywords: ['salade', 'poelee', 'dessert'],
        reason: 'Raw basmati rice required; no prepared rice salads or desserts',
      },
    ],
  },
  {
    id: 'chili-haricots-rouges-carrefour-budget',
    recipeName: 'Chili sin carne',
    store: 'carrefour',
    strategy: 'budget',
    assertions: [
      {
        ingredientName: 'Haricots rouges',
        expectedKeywords: ['haricot'],
        prohibitedKeywords: ['chili con carne', 'traiteur', 'salade', 'barquette'],
        reason: 'Staple kidney beans required; no microwave chili trays',
      },
    ],
  },
  {
    id: 'anti-surcout-beurre-budget',
    recipeName: 'Cuisson au beurre doux',
    store: 'carrefour',
    strategy: 'budget',
    assertions: [
      {
        ingredientName: 'Beurre',
        expectedKeywords: ['beurre'],
        prohibitedKeywords: ['motte gastronomique', 'biscuit', 'croissant', 'pain'],
        maxExpectedPriceEuros: 3.0,
        reason: 'Budget butter must be an economical 250g block (< 3.00 €), never a 5.50 € luxury AOP mound',
      },
    ],
  },
];

