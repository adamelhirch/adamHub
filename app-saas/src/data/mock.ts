export type MockMealPlanDay = {
  day: string;
  date: string;
  meals: { label: string; recipe: string }[];
};

export const mockMealPlan: MockMealPlanDay[] = [
  {
    day: "Lundi",
    date: "12 août",
    meals: [
      { label: "Déjeuner", recipe: "Salade de lentilles au feta" },
      { label: "Dîner", recipe: "Pâtes carbonara" },
    ],
  },
  {
    day: "Mardi",
    date: "13 août",
    meals: [
      { label: "Déjeuner", recipe: "Reste de pâtes carbonara" },
      { label: "Dîner", recipe: "Curry de pois chiches" },
    ],
  },
  {
    day: "Mercredi",
    date: "14 août",
    meals: [{ label: "Dîner", recipe: "Poulet rôti et légumes" }],
  },
];

export type MockGroceryItem = {
  id: string;
  name: string;
  category: string;
  quantity: string;
  checked: boolean;
};

export const mockGroceryList: MockGroceryItem[] = [
  { id: "1", name: "Lentilles vertes", category: "Épicerie", quantity: "500 g", checked: false },
  { id: "2", name: "Feta", category: "Crémerie", quantity: "1", checked: false },
  { id: "3", name: "Spaghetti", category: "Épicerie", quantity: "500 g", checked: true },
  { id: "4", name: "Lardons", category: "Boucherie", quantity: "200 g", checked: false },
  { id: "5", name: "Pois chiches", category: "Épicerie", quantity: "2 boîtes", checked: false },
  { id: "6", name: "Poulet fermier", category: "Boucherie", quantity: "1", checked: false },
];

export type MockPantryItem = {
  id: string;
  name: string;
  category: string;
  quantity: string;
  expiry?: string;
};

export const mockPantry: MockPantryItem[] = [
  { id: "1", name: "Riz basmati", category: "Féculents", quantity: "1 kg" },
  { id: "2", name: "Spaghetti", category: "Féculents", quantity: "500 g" },
  { id: "3", name: "Lait", category: "Crémerie", quantity: "1 L", expiry: "18 août" },
  { id: "4", name: "Œufs", category: "Crémerie", quantity: "6", expiry: "22 août" },
  { id: "5", name: "Tomates pelées", category: "Conserves", quantity: "3 boîtes" },
  { id: "6", name: "Huile d'olive", category: "Épicerie", quantity: "1 L" },
];
