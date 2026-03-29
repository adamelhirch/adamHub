import { useState, useEffect, useMemo } from 'react';
import { format, differenceInDays, parseISO } from 'date-fns';
import {
  ShoppingBasket, Package, Plus, Trash2, Check, Search, X, AlertTriangle,
  ChevronDown, ChevronRight, Minus, Loader2, Store,
} from 'lucide-react';
import { useGroceryStore } from '../store/groceryStore';
import type { GroceryItem, PantryItem, SupermarketMapping, SupermarketProduct } from '../store/groceryStore';

// ─── Constants ────────────────────────────────────────────────────────────────
const CATEGORY_COLORS: Record<string, string> = {
  Fruits: '#ef4444', Légumes: '#22c55e', Viande: '#f97316', Poisson: '#06b6d4',
  Produits_laitiers: '#a855f7', Épicerie: '#f59e0b', Boissons: '#3b82f6',
  Surgelés: '#0ea5e9', Hygiène: '#ec4899', Maison: '#78716c', Other: '#94a3b8',
};

function getCategoryColor(cat: string | null): string {
  if (!cat) return '#94a3b8';
  return CATEGORY_COLORS[cat] ?? '#94a3b8';
}

function formatCategoryLabel(category: string | null): string {
  if (!category) return 'Autre';
  const cleaned = category.replace(/_/g, ' ').replace(/\s+/g, ' ').trim();
  if (!cleaned) return 'Autre';
  const isUppercase = cleaned === cleaned.toUpperCase();
  if (!isUppercase) return cleaned;
  return cleaned
    .toLocaleLowerCase('fr-FR')
    .replace(/\b\p{L}/gu, (letter) => letter.toLocaleUpperCase('fr-FR'));
}

function parseGroceryNote(note: string | null): { source: string | null; details: string | null } {
  if (!note) {
    return { source: null, details: null };
  }
  const parts = note.split('·').map((part) => part.trim()).filter(Boolean);
  if (parts.length === 0) {
    return { source: null, details: null };
  }
  if (parts.length === 1) {
    return { source: null, details: parts[0] };
  }
  return {
    source: parts[0],
    details: parts.slice(1).join(' · '),
  };
}

const PRIORITY_LABEL: Record<number, { label: string; color: string }> = {
  1: { label: 'Urgent', color: 'text-red-500 bg-red-50' },
  2: { label: 'Élevée', color: 'text-amber-600 bg-amber-50' },
  3: { label: 'Normale', color: 'text-blue-600 bg-blue-50' },
};

const TAB_LIST = ['Liste de courses', 'Garde-manger'] as const;
type Tab = (typeof TAB_LIST)[number];

// ─── Helper: group items ──────────────────────────────────────────────────────
function groupByCategory<T extends { category: string | null }>(items: T[]): [string, T[]][] {
  const map = new Map<string, T[]>();
  items.forEach((item) => {
    const key = item.category ?? 'Autre';
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(item);
  });
  return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
}

// ─── GroceryRow ───────────────────────────────────────────────────────────────
function GroceryRow({ item, onToggle, onDelete }: {
  item: GroceryItem;
  onToggle: (id: number, checked: boolean) => void;
  onDelete: (id: number) => void;
}) {
  const { source, details } = parseGroceryNote(item.note);
  const quantityLabel = item.quantity !== 1 || item.unit !== 'item' ? `${item.quantity} ${item.unit}` : null;

  return (
    <div className={`group flex items-start gap-3 px-4 py-3.5 transition-colors hover:bg-apple-gray-50 ${item.checked ? 'opacity-60' : ''}`}>
      <button
        onClick={() => onToggle(item.id, !item.checked)}
        className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition-colors ${
          item.checked
            ? 'bg-emerald-500 border-emerald-500 text-white'
            : 'border-apple-gray-300 hover:border-apple-blue'
        }`}
      >
        {item.checked && <Check className="w-3 h-3" />}
      </button>
      {item.image_url ? (
        <img
          src={item.image_url}
          alt={item.name}
          className="h-12 w-12 shrink-0 rounded-xl border border-apple-gray-100 bg-white object-contain p-1"
        />
      ) : (
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-apple-gray-100">
          <ShoppingBasket className="h-5 w-5 text-apple-gray-300" />
        </div>
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <p className={`min-w-0 text-sm font-semibold leading-5 ${item.checked ? 'line-through text-apple-gray-400' : 'text-black'}`}>
            {item.name}
          </p>
          {item.priority < 3 && (
            <span className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-bold uppercase ${PRIORITY_LABEL[item.priority]?.color}`}>
              {PRIORITY_LABEL[item.priority]?.label}
            </span>
          )}
        </div>
        {(quantityLabel || source || details) && (
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className="rounded-full px-2.5 py-1 text-[11px] font-semibold" style={{ backgroundColor: `${getCategoryColor(item.category)}1A`, color: getCategoryColor(item.category) }}>
              {formatCategoryLabel(item.category)}
            </span>
            {quantityLabel && (
              <span className="rounded-full bg-apple-gray-100 px-2.5 py-1 text-[11px] font-semibold text-apple-gray-600">
                {quantityLabel}
              </span>
            )}
            {source && (
              <span className="rounded-full bg-red-50 px-2.5 py-1 text-[11px] font-semibold text-red-600">
                {source}
              </span>
            )}
            {details && (
              <span className="min-w-0 text-[11px] text-apple-gray-500">
                {details}
              </span>
            )}
          </div>
        )}
      </div>
      <button
        onClick={() => onDelete(item.id)}
        className="shrink-0 rounded-lg p-1.5 text-apple-gray-400 opacity-0 transition-all hover:bg-red-50 hover:text-red-500 group-hover:opacity-100"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

// ─── PantryRow ────────────────────────────────────────────────────────────────
function PantryRow({ item, onDelete, onConsume, onUpdate, onMap }: {
  item: PantryItem;
  onDelete: (id: number) => void;
  onConsume: (id: number, amount: number) => void;
  onUpdate: (id: number, data: Partial<PantryItem>) => void;
  onMap: (item: PantryItem) => void;
}) {
  const [editingQty, setEditingQty] = useState(false);
  const [qtyValue, setQtyValue] = useState(String(item.quantity));
  const isLowStock = item.quantity <= item.min_quantity && item.min_quantity > 0;
  const expireSoon = item.expires_at
    ? differenceInDays(parseISO(item.expires_at), new Date())
    : null;
  const isExpireSoon = expireSoon !== null && expireSoon <= 7;

  return (
    <div className={`flex items-center gap-3 px-4 py-3 hover:bg-apple-gray-50 transition-colors group ${isLowStock ? 'bg-amber-50/40' : ''}`}>
      {item.image_url ? (
        <img
          src={item.image_url}
          alt={item.name}
          className="h-12 w-12 shrink-0 rounded-xl border border-apple-gray-100 bg-white object-contain p-1"
        />
      ) : (
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-apple-gray-100">
          <Package className="h-5 w-5 text-apple-gray-300" />
        </div>
      )}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-sm font-semibold text-black truncate">{item.name}</p>
          {isLowStock && <AlertTriangle className="w-3 h-3 text-amber-500 shrink-0" />}
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          {item.category && (
            <span className="rounded-full px-2.5 py-1 text-[11px] font-semibold" style={{ backgroundColor: `${getCategoryColor(item.category)}1A`, color: getCategoryColor(item.category) }}>
              {formatCategoryLabel(item.category)}
            </span>
          )}
          {item.location && <span className="text-xs text-apple-gray-400">· {item.location}</span>}
          {item.expires_at && (
            <span className={`text-xs font-medium ${isExpireSoon ? 'text-red-500' : 'text-apple-gray-400'}`}>
              · Exp: {format(parseISO(item.expires_at), 'dd/MM/yyyy')}
              {expireSoon !== null && expireSoon <= 7 && ` (J-${expireSoon})`}
            </span>
          )}
        </div>
      </div>

      {/* Quantity */}
      <div className="flex items-center gap-1 shrink-0">
        <button
          onClick={() => onConsume(item.id, 1)}
          className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-50 text-apple-gray-400 hover:text-red-500 transition-all"
          title="Consommer 1"
        >
          <Minus className="w-3.5 h-3.5" />
        </button>
        {editingQty ? (
          <div className="flex items-center gap-1">
            <input
              type="number"
              value={qtyValue}
              onChange={(e) => setQtyValue(e.target.value)}
              onBlur={() => {
                const v = parseFloat(qtyValue);
                if (!isNaN(v)) onUpdate(item.id, { quantity: v });
                setEditingQty(false);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  const v = parseFloat(qtyValue);
                  if (!isNaN(v)) onUpdate(item.id, { quantity: v });
                  setEditingQty(false);
                }
                if (e.key === 'Escape') setEditingQty(false);
              }}
              autoFocus
              className="w-16 px-2 py-1 text-sm text-center rounded border border-apple-blue focus:outline-none"
              step="1"
            />
          </div>
        ) : (
          <button
            onClick={() => { setEditingQty(true); setQtyValue(String(item.quantity)); }}
            className={`text-sm font-bold px-2 py-0.5 rounded hover:bg-apple-gray-100 transition-colors ${isLowStock ? 'text-amber-600' : 'text-black'}`}
          >
            {item.quantity}
          </button>
        )}
        <span className="text-xs text-apple-gray-400">{item.unit}</span>
        <button
          onClick={() => onUpdate(item.id, { quantity: item.quantity + 1 })}
          className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-emerald-50 text-apple-gray-400 hover:text-emerald-600 transition-all"
          title="Ajouter 1"
        >
          <Plus className="w-3.5 h-3.5" />
        </button>
      </div>

      <button
        onClick={() => onMap(item)}
        className="opacity-0 group-hover:opacity-100 p-1.5 text-apple-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all shrink-0"
        title="Lier Intermarché"
      >
        <Store className="w-3.5 h-3.5" />
      </button>

      <button
        onClick={() => onDelete(item.id)}
        className="opacity-0 group-hover:opacity-100 p-1.5 text-apple-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all shrink-0"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

function PantryMappingPanel({
  item,
  mapping,
  query,
  setQuery,
  searchResults,
  searchLoading,
  searchError,
  onSearch,
  canRefresh,
  onRefresh,
  onClose,
  onLink,
  onUnlink,
}: {
  item: PantryItem;
  mapping: SupermarketMapping | null;
  query: string;
  setQuery: (value: string) => void;
  searchResults: SupermarketProduct[];
  searchLoading: boolean;
  searchError: string | null;
  onSearch: () => Promise<void>;
  canRefresh: boolean;
  onRefresh: () => Promise<void>;
  onClose: () => void;
  onLink: (product: SupermarketProduct) => Promise<void>;
  onUnlink: (mappingId: number) => Promise<void>;
}) {
  return (
    <div className="bg-white rounded-2xl border border-red-200 shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-red-100 bg-red-50/60">
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-red-600">Mapping Intermarché</p>
          <h3 className="text-sm font-semibold text-black mt-1">{item.name}</h3>
        </div>
        <button onClick={onClose} className="p-2 rounded-lg hover:bg-white/80 text-apple-gray-500">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="p-5 space-y-4">
        {mapping ? (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-emerald-700">{mapping.store_label}</p>
              <p className="text-sm font-semibold text-black">{mapping.name_snapshot}</p>
              <p className="text-xs text-apple-gray-500">
                {[mapping.category_snapshot, mapping.packaging_snapshot, mapping.price_snapshot].filter(Boolean).join(' · ') || 'Produit lié'}
              </p>
            </div>
            <button
              onClick={() => onUnlink(mapping.id)}
              className="px-3 py-2 rounded-xl text-sm font-medium text-red-600 hover:bg-red-50"
            >
              Retirer
            </button>
          </div>
        ) : (
          <p className="text-sm text-apple-gray-500">Aucun produit Intermarché lié pour cet article.</p>
        )}

        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-apple-gray-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  void onSearch();
                }
              }}
              placeholder="Rechercher chez Intermarché"
              className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-apple-gray-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-red-400/40"
            />
          </div>
          <button
            onClick={() => void onSearch()}
            disabled={searchLoading || !query.trim()}
            className="px-4 py-2.5 bg-red-600 text-white text-sm font-semibold rounded-xl hover:bg-red-700 disabled:opacity-50"
          >
            {searchLoading ? 'Recherche…' : 'Rechercher'}
          </button>
          {canRefresh && (
            <button
              onClick={() => void onRefresh()}
              disabled={searchLoading || !query.trim()}
              className="px-4 py-2.5 border border-red-200 text-red-600 text-sm font-semibold rounded-xl hover:bg-red-50 disabled:opacity-50"
            >
              Actualiser
            </button>
          )}
        </div>

        {searchError && <p className="text-xs text-red-500">{searchError}</p>}

        {searchResults.length > 0 && (
          <div className="space-y-2">
            {searchResults.map((product) => (
              <div key={product.cache_id} className="rounded-xl border border-apple-gray-200 p-3 flex items-center gap-3">
                {product.image_url ? (
                  <img src={product.image_url} alt={product.name} className="w-14 h-14 rounded-lg object-contain bg-white p-1 border border-apple-gray-100" />
                ) : (
                  <div className="w-14 h-14 rounded-lg bg-apple-gray-100 flex items-center justify-center">
                    <Package className="w-5 h-5 text-apple-gray-300" />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-black truncate">{product.name}</p>
                  <p className="text-xs text-apple-gray-500">
                    {[product.category, product.packaging, product.price_text].filter(Boolean).join(' · ') || 'Aucun détail'}
                  </p>
                </div>
                <button
                  onClick={() => void onLink(product)}
                  className="px-3 py-2 rounded-xl bg-apple-blue text-white text-sm font-semibold hover:bg-blue-600"
                >
                  Lier
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function GroceriesPage() {
  const {
    items, groceryLoading, fetchItems, addItem, toggleCheck, deleteItem, clearChecked,
    pantryItems, pantryOverview, pantryLoading, fetchPantry, fetchPantryOverview,
    addPantryItem, updatePantryItem, deletePantryItem, consumePantryItem,
    searchResults, searchLoading, searchError, searchIntermarche, clearSearchResults,
    pantryMappings, fetchPantryMapping, savePantryMapping, deleteMapping, hasCachedProducts,
  } = useGroceryStore();

  const [activeTab, setActiveTab] = useState<Tab>('Liste de courses');
  const [search, setSearch] = useState('');

  // Grocery form
  const [showAddForm, setShowAddForm] = useState(false);
  const [newName, setNewName] = useState('');
  const [newQty, setNewQty] = useState('1');
  const [newUnit, setNewUnit] = useState('item');
  const [newCategory, setNewCategory] = useState('');
  const [newPriority, setNewPriority] = useState(3);
  // Intermarché search state
  const [imQuery, setImQuery] = useState('');
  const [selectedProduct, setSelectedProduct] = useState<SupermarketProduct | null>(null);
  const [pantrySearchQuery, setPantrySearchQuery] = useState('');
  const [selectedPantryProduct, setSelectedPantryProduct] = useState<SupermarketProduct | null>(null);
  const [mappingTarget, setMappingTarget] = useState<PantryItem | null>(null);
  const [mappingQuery, setMappingQuery] = useState('');
  const [imQueryHasCache, setImQueryHasCache] = useState(false);
  const [pantrySearchQueryHasCache, setPantrySearchQueryHasCache] = useState(false);
  const [mappingQueryHasCache, setMappingQueryHasCache] = useState(false);

  const handleSelectProduct = (p: SupermarketProduct) => {
    setSelectedProduct(p);
    setNewName(p.name);
    setNewCategory(p.category ?? '');
    // Try to extract unit from packaging (e.g. '1 L', '500 g', '6x1 kg')
    if (p.packaging) {
      const match = p.packaging.match(/(\d+(?:[.,]\d+)?)\s*(kg|g|L|cl|ml)/i);
      if (match) {
        setNewQty(match[1].replace(',', '.'));
        setNewUnit(match[2].toLowerCase() === 'l' ? 'L' : match[2].toLowerCase());
      }
    }
  };

  const handleOpenAddForm = () => {
    setShowAddForm(!showAddForm);
    if (showAddForm) {
      clearSearchResults();
      setSelectedProduct(null);
      setImQuery('');
    }
  };

  // Pantry form
  const [showPantryForm, setShowPantryForm] = useState(false);
  const [pName, setPName] = useState('');
  const [pQty, setPQty] = useState('1');
  const [pUnit, setPUnit] = useState('item');
  const [pCategory, setPCategory] = useState('');
  const [pMinQty, setPMinQty] = useState('0');
  const [pExpires, setPExpires] = useState('');
  const [pLocation, setPLocation] = useState('');

  const handleSelectPantryProduct = (product: SupermarketProduct) => {
    setSelectedPantryProduct(product);
    setPName(product.name);
    setPCategory(product.category ?? '');
    if (product.packaging) {
      const match = product.packaging.match(/(\d+(?:[.,]\d+)?)\s*(kg|g|L|cl|ml)/i);
      if (match) {
        setPQty(match[1].replace(',', '.'));
        setPUnit(match[2].toLowerCase() === 'l' ? 'L' : match[2].toLowerCase());
      }
    }
  };

  const handleTogglePantryForm = () => {
    setShowPantryForm(!showPantryForm);
    if (showPantryForm) {
      clearSearchResults();
      setSelectedPantryProduct(null);
      setPantrySearchQuery('');
    }
  };

  // Collapsed category groups
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchItems();
    fetchPantry();
    fetchPantryOverview();
  }, []);

  useEffect(() => {
    const value = imQuery.trim();
    if (!value) {
      setImQueryHasCache(false);
      return;
    }
    const timer = window.setTimeout(() => {
      void hasCachedProducts(value)
        .then(setImQueryHasCache)
        .catch(() => setImQueryHasCache(false));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [imQuery, hasCachedProducts]);

  useEffect(() => {
    const value = mappingQuery.trim();
    if (!value) {
      setMappingQueryHasCache(false);
      return;
    }
    const timer = window.setTimeout(() => {
      void hasCachedProducts(value)
        .then(setMappingQueryHasCache)
        .catch(() => setMappingQueryHasCache(false));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [mappingQuery, hasCachedProducts]);

  useEffect(() => {
    const value = pantrySearchQuery.trim();
    if (!value) {
      setPantrySearchQueryHasCache(false);
      return;
    }
    const timer = window.setTimeout(() => {
      void hasCachedProducts(value)
        .then(setPantrySearchQueryHasCache)
        .catch(() => setPantrySearchQueryHasCache(false));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [pantrySearchQuery, hasCachedProducts]);

  // ── Grocery list logic ────────────────────────────────────────────────────
  const filteredItems = useMemo(() => {
    const q = search.toLowerCase();
    if (!q) return items;
    return items.filter((i) => i.name.toLowerCase().includes(q));
  }, [items, search]);

  const uncheckedItems = filteredItems.filter((i) => !i.checked);
  const checkedItems = filteredItems.filter((i) => i.checked);
  const uncheckedGroups = groupByCategory(uncheckedItems);

  const handleAddGrocery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    await addItem({
      name: newName.trim(),
      quantity: parseFloat(newQty) || 1,
      unit: newUnit || 'item',
      category: newCategory || undefined,
      image_url: selectedProduct?.image_url || undefined,
      priority: newPriority,
      note: selectedProduct ? `Intermarché · ${selectedProduct.price_text ?? ''} · ${selectedProduct.packaging ?? ''}`.trim().replace(/·\s*$/, '') : undefined,
    });
    setNewName(''); setNewQty('1'); setNewUnit('item'); setNewCategory(''); setNewPriority(3);
    setSelectedProduct(null); clearSearchResults(); setImQuery('');
    setShowAddForm(false);
  };

  // ── Pantry logic ──────────────────────────────────────────────────────────
  const filteredPantry = useMemo(() => {
    const q = search.toLowerCase();
    if (!q) return pantryItems;
    return pantryItems.filter((i) => i.name.toLowerCase().includes(q));
  }, [pantryItems, search]);

  const pantryGroups = groupByCategory(filteredPantry);

  const handleAddPantry = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pName.trim()) return;
    const created = await addPantryItem({
      name: pName.trim(),
      quantity: parseFloat(pQty) || 0,
      unit: pUnit || 'item',
      category: pCategory || undefined,
      image_url: selectedPantryProduct?.image_url || undefined,
      min_quantity: parseFloat(pMinQty) || 0,
      expires_at: pExpires || undefined,
      location: pLocation || undefined,
    });
    if (selectedPantryProduct) {
      await savePantryMapping(created.id, selectedPantryProduct);
    }
    setPName(''); setPQty('1'); setPUnit('item'); setPCategory(''); setPMinQty('0'); setPExpires(''); setPLocation('');
    setSelectedPantryProduct(null); setPantrySearchQuery(''); clearSearchResults();
    setShowPantryForm(false);
    fetchPantryOverview();
  };

  const toggleGroup = (group: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(group)) next.delete(group);
      else next.add(group);
      return next;
    });
  };

  const inputCls = 'px-3 py-2 rounded-xl border border-apple-gray-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-apple-blue/50';

  return (
    <div className="flex-1 flex flex-col h-full bg-apple-gray-50 overflow-hidden">
      {/* Header */}
      <div className="px-8 py-5 border-b border-apple-gray-200 bg-white shadow-sm z-10 flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-black">Groceries</h1>
          <p className="text-apple-gray-500 mt-0.5 text-sm">Liste de courses &amp; garde-manger</p>
        </div>
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-apple-gray-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={activeTab === 'Liste de courses' ? 'Rechercher un article…' : 'Rechercher dans le garde-manger…'}
            className="pl-9 pr-4 py-2 rounded-xl border border-apple-gray-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-apple-blue/50 w-64"
          />
          {search && (
            <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-apple-gray-400 hover:text-black">
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-apple-gray-200 bg-white px-8">
        <div className="flex gap-1">
          {TAB_LIST.map((tab) => (
            <button
              key={tab}
              onClick={() => { setActiveTab(tab); setSearch(''); }}
              className={`px-5 py-3 text-sm font-semibold border-b-2 transition-colors flex items-center gap-2 ${
                activeTab === tab
                  ? 'border-apple-blue text-apple-blue'
                  : 'border-transparent text-apple-gray-500 hover:text-black'
              }`}
            >
              {tab === 'Liste de courses' ? <ShoppingBasket className="w-4 h-4" /> : <Package className="w-4 h-4" />}
              {tab}
              {tab === 'Liste de courses' && uncheckedItems.length > 0 && (
                <span className="bg-apple-blue text-white text-[10px] font-bold rounded-full px-1.5 py-0.5 min-w-[18px] text-center">
                  {uncheckedItems.length}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto space-y-4">

          {/* ── GROCERY LIST ─────────────────────────────────────────────── */}
          {activeTab === 'Liste de courses' && (
            <>
              {/* Toolbar */}
              <div className="flex items-center gap-3 flex-wrap">
                <button
                  onClick={handleOpenAddForm}
                  className="flex items-center gap-2 px-5 py-2.5 bg-apple-blue text-white text-sm font-semibold rounded-xl hover:bg-blue-600 transition-colors shadow-sm"
                >
                  {showAddForm ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
                  {showAddForm ? 'Fermer' : 'Ajouter'}
                </button>
                {checkedItems.length > 0 && (
                  <button
                    onClick={clearChecked}
                    className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-red-500 border border-red-200 rounded-xl hover:bg-red-50 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                    Vider les cochés ({checkedItems.length})
                  </button>
                )}
              </div>

              {/* Add form */}
              {showAddForm && (
                <div className="bg-white rounded-2xl border border-apple-gray-200 shadow-sm overflow-hidden">

                  {/* ── Intermarché search ─────────────────────────────── */}
                  <div className="p-5 border-b border-apple-gray-100">
                    <div className="flex items-center gap-2 mb-3">
                      <Store className="w-4 h-4 text-red-600" />
                      <span className="text-xs font-bold text-red-600 uppercase tracking-wider">Rechercher sur Intermarché</span>
                    </div>
                    <div className="flex gap-2">
                      <div className="relative flex-1">
                        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-apple-gray-400" />
                        <input
                          type="text"
                          placeholder="Ex: lait, poulet, yaourt…"
                          value={imQuery}
                          onChange={(e) => setImQuery(e.target.value)}
                          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); if (imQuery.trim()) searchIntermarche(imQuery.trim()); }}}
                          className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-apple-gray-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-red-400/40"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() => { if (imQuery.trim()) searchIntermarche(imQuery.trim()); }}
                        disabled={searchLoading || !imQuery.trim()}
                        className="flex items-center gap-2 px-4 py-2.5 bg-red-600 text-white text-sm font-semibold rounded-xl hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        {searchLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                        {searchLoading ? 'Scraping…' : 'Rechercher'}
                      </button>
                      {imQueryHasCache && (
                        <button
                          type="button"
                          onClick={() => { if (imQuery.trim()) searchIntermarche(imQuery.trim(), true); }}
                          disabled={searchLoading || !imQuery.trim()}
                          className="px-4 py-2.5 border border-red-200 text-red-600 text-sm font-semibold rounded-xl hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          Actualiser
                        </button>
                      )}
                    </div>

                    {/* Loading hint */}
                    {searchLoading && (
                      <p className="text-xs text-apple-gray-400 mt-2 animate-pulse">⏳ Le scraper Intermarché est en cours… (~15-30s)</p>
                    )}

                    {/* Error */}
                    {searchError && (
                      <p className="text-xs text-red-500 mt-2">❌ {searchError}</p>
                    )}

                    {/* Product results */}
                    {searchResults.length > 0 && !searchLoading && (
                      <div className="mt-3">
                        <p className="text-xs text-apple-gray-400 mb-2">{searchResults.length} résultat(s) — cliquez pour pré-remplir</p>
                        <div className="flex gap-3 overflow-x-auto pb-2 -mx-1 px-1">
                          {searchResults.map((p) => (
                            <button
                              key={p.cache_id}
                              type="button"
                              onClick={() => handleSelectProduct(p)}
                              className={`flex-shrink-0 w-36 rounded-xl border-2 text-left transition-all hover:shadow-md ${
                                selectedProduct?.cache_id === p.cache_id
                                  ? 'border-red-500 shadow-md bg-red-50'
                                  : 'border-apple-gray-200 bg-white hover:border-red-300'
                              }`}
                            >
                              {p.image_url ? (
                                <img src={p.image_url} alt={p.name} className="w-full h-24 object-contain rounded-t-xl bg-white p-2" />
                              ) : (
                                <div className="w-full h-24 rounded-t-xl bg-apple-gray-100 flex items-center justify-center">
                                  <ShoppingBasket className="w-8 h-8 text-apple-gray-300" />
                                </div>
                              )}
                              <div className="p-2">
                                <p className="text-[11px] font-semibold text-black leading-tight line-clamp-2">{p.name}</p>
                                {p.category && <p className="text-[10px] text-apple-gray-500 mt-0.5 truncate">{p.category}</p>}
                                {p.packaging && <p className="text-[10px] text-apple-gray-400 mt-0.5 truncate">{p.packaging}</p>}
                                {p.price_text && <p className="text-[11px] font-bold text-red-600 mt-1">{p.price_text}</p>}
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* ── Add form ───────────────────────────────────────── */}
                  <form onSubmit={handleAddGrocery} className="p-5 space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-black">Détails de l'article</h3>
                      {selectedProduct && (
                        <div className="flex items-center gap-1.5 text-xs font-semibold text-red-600 bg-red-50 border border-red-200 rounded-full px-2.5 py-1">
                          <Store className="w-3 h-3" />
                          Intermarché sélectionné
                          <button type="button" onClick={() => { setSelectedProduct(null); setNewName(''); setNewQty('1'); setNewUnit('item'); setNewCategory(''); }} className="ml-1 hover:text-red-800">
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-3">
                      <input
                        type="text" placeholder="Nom de l'article" value={newName}
                        onChange={(e) => setNewName(e.target.value)} required
                        autoFocus={!selectedProduct}
                        className={`flex-1 min-w-[180px] ${inputCls}`}
                      />
                      <input
                        type="number" placeholder="Qté" value={newQty}
                        onChange={(e) => setNewQty(e.target.value)} min="0" step="0.5"
                        className={`w-20 ${inputCls}`}
                      />
                      <input
                        type="text" placeholder="Unité" value={newUnit}
                        onChange={(e) => setNewUnit(e.target.value)}
                        className={`w-24 ${inputCls}`}
                      />
                      <input
                        type="text" placeholder="Catégorie" value={newCategory}
                        onChange={(e) => setNewCategory(e.target.value)}
                        className={`flex-1 min-w-[120px] ${inputCls}`}
                      />
                      <select
                        value={newPriority} onChange={(e) => setNewPriority(Number(e.target.value))}
                        className={inputCls}
                      >
                        <option value={1}>🔴 Urgent</option>
                        <option value={2}>🟡 Élevée</option>
                        <option value={3}>🔵 Normale</option>
                      </select>
                    </div>
                    <div className="flex gap-3">
                      <button type="submit" className="px-5 py-2.5 bg-apple-blue text-white text-sm font-semibold rounded-xl hover:bg-blue-600 transition-colors">Ajouter à la liste</button>
                      <button type="button" onClick={handleOpenAddForm} className="px-5 py-2.5 text-sm font-medium text-apple-gray-500 hover:bg-apple-gray-100 rounded-xl transition-colors">Annuler</button>
                    </div>
                  </form>
                </div>
              )}

              {/* List */}
              {groceryLoading ? (
                <div className="flex items-center justify-center py-16">
                  <div className="w-8 h-8 border-2 border-apple-blue/30 border-t-apple-blue rounded-full animate-spin" />
                </div>
              ) : filteredItems.length === 0 ? (
                <div className="bg-white rounded-2xl border border-apple-gray-200 shadow-sm py-16 text-center">
                  <ShoppingBasket className="w-12 h-12 text-apple-gray-300 mx-auto mb-3" />
                  <p className="text-apple-gray-500 text-sm">Liste vide</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {/* Unchecked groups */}
                  {uncheckedGroups.map(([category, groupItems]) => (
                    <div key={category} className="overflow-hidden rounded-2xl border border-apple-gray-200 bg-white shadow-sm">
                      <button
                        onClick={() => toggleGroup(category)}
                        className="flex w-full items-center gap-3 border-b border-apple-gray-100 bg-white px-4 py-3 text-left transition-colors hover:bg-apple-gray-50"
                      >
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-apple-gray-50">
                          <div className="h-2.5 w-2.5 rounded-full" style={{ background: getCategoryColor(groupItems[0].category) }} />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-apple-gray-400">Rayon</p>
                          <p className="mt-1 text-sm font-semibold leading-5 text-black">{formatCategoryLabel(category)}</p>
                        </div>
                        <span className="shrink-0 rounded-full bg-apple-gray-100 px-2.5 py-1 text-xs font-semibold text-apple-gray-500">
                          {groupItems.length}
                        </span>
                        {collapsedGroups.has(category) ? <ChevronRight className="h-4 w-4 text-apple-gray-400" /> : <ChevronDown className="h-4 w-4 text-apple-gray-400" />}
                      </button>
                      {!collapsedGroups.has(category) && (
                        <div className="divide-y divide-apple-gray-50">
                          {groupItems.map((item) => (
                            <GroceryRow key={item.id} item={item} onToggle={toggleCheck} onDelete={deleteItem} />
                          ))}
                        </div>
                      )}
                    </div>
                  ))}

                  {/* Checked items */}
                  {checkedItems.length > 0 && (
                    <div className="overflow-hidden rounded-2xl border border-emerald-200 bg-white shadow-sm">
                      <button
                        onClick={() => toggleGroup('__checked__')}
                        className="flex w-full items-center gap-3 border-b border-emerald-100 bg-emerald-50/80 px-4 py-3 text-left transition-colors hover:bg-emerald-50"
                      >
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/80">
                          <Check className="h-4 w-4 text-emerald-500" />
                        </div>
                        <div className="flex-1">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-500">Terminés</p>
                          <p className="mt-1 text-sm font-semibold text-emerald-800">Articles cochés</p>
                        </div>
                        <span className="shrink-0 rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-emerald-600">
                          {checkedItems.length}
                        </span>
                        {collapsedGroups.has('__checked__') ? <ChevronRight className="h-4 w-4 text-emerald-400" /> : <ChevronDown className="h-4 w-4 text-emerald-400" />}
                      </button>
                      {!collapsedGroups.has('__checked__') && (
                        <div className="divide-y divide-apple-gray-50">
                          {checkedItems.map((item) => (
                            <GroceryRow key={item.id} item={item} onToggle={toggleCheck} onDelete={deleteItem} />
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {/* ── PANTRY ───────────────────────────────────────────────────── */}
          {activeTab === 'Garde-manger' && (
            <>
              {mappingTarget && (
                <PantryMappingPanel
                  item={mappingTarget}
                  mapping={pantryMappings[mappingTarget.id] ?? null}
                  query={mappingQuery}
                  setQuery={setMappingQuery}
                  searchResults={searchResults}
                  searchLoading={searchLoading}
                  searchError={searchError}
                  onSearch={async () => {
                    if (mappingQuery.trim()) {
                      await searchIntermarche(mappingQuery.trim());
                    }
                  }}
                  onClose={() => {
                    setMappingTarget(null);
                    setMappingQuery('');
                    clearSearchResults();
                  }}
                  onLink={async (product) => {
                    await updatePantryItem(mappingTarget.id, { image_url: product.image_url ?? null });
                    await savePantryMapping(mappingTarget.id, product);
                  }}
                  onUnlink={async (mappingId) => {
                    await deleteMapping(mappingId);
                  }}
                  canRefresh={mappingQueryHasCache}
                  onRefresh={async () => {
                    if (mappingQuery.trim()) {
                      await searchIntermarche(mappingQuery.trim(), true);
                    }
                  }}
                />
              )}

              {/* Overview stats */}
              {pantryOverview && (
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { label: 'Total articles', value: pantryOverview.total_items, color: 'text-black' },
                    { label: 'Stock faible', value: pantryOverview.low_stock_items, color: pantryOverview.low_stock_items > 0 ? 'text-amber-600' : 'text-black' },
                    { label: 'Bientôt périmé', value: pantryOverview.expiring_within_7_days, color: pantryOverview.expiring_within_7_days > 0 ? 'text-red-500' : 'text-black' },
                  ].map(({ label, value, color }) => (
                    <div key={label} className="bg-white rounded-2xl border border-apple-gray-200 shadow-sm p-4">
                      <p className="text-xs font-semibold text-apple-gray-500 uppercase tracking-wider">{label}</p>
                      <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Toolbar */}
              <div className="flex items-center gap-3">
                <button
                  onClick={handleTogglePantryForm}
                  className="flex items-center gap-2 px-5 py-2.5 bg-apple-blue text-white text-sm font-semibold rounded-xl hover:bg-blue-600 transition-colors shadow-sm"
                >
                  <Plus className="w-4 h-4" />
                  Ajouter
                </button>
              </div>

              {/* Add pantry form */}
              {showPantryForm && (
                <form onSubmit={handleAddPantry} className="bg-white rounded-2xl border border-apple-gray-200 shadow-sm p-5 space-y-4">
                  <div className="space-y-4 border-b border-apple-gray-100 pb-4">
                    <div className="flex items-center gap-2">
                      <Store className="w-4 h-4 text-red-600" />
                      <span className="text-xs font-bold uppercase tracking-wider text-red-600">Choisir un produit magasin</span>
                    </div>
                    <div className="flex gap-2">
                      <div className="relative flex-1">
                        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-apple-gray-400" />
                        <input
                          type="text"
                          placeholder="Ex: lait, pain, yaourt…"
                          value={pantrySearchQuery}
                          onChange={(e) => setPantrySearchQuery(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              e.preventDefault();
                              if (pantrySearchQuery.trim()) {
                                void searchIntermarche(pantrySearchQuery.trim());
                              }
                            }
                          }}
                          className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-apple-gray-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-red-400/40"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          if (pantrySearchQuery.trim()) {
                            void searchIntermarche(pantrySearchQuery.trim());
                          }
                        }}
                        disabled={searchLoading || !pantrySearchQuery.trim()}
                        className="flex items-center gap-2 px-4 py-2.5 bg-red-600 text-white text-sm font-semibold rounded-xl hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        {searchLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                        {searchLoading ? 'Scraping…' : 'Rechercher'}
                      </button>
                      {pantrySearchQueryHasCache && (
                        <button
                          type="button"
                          onClick={() => {
                            if (pantrySearchQuery.trim()) {
                              void searchIntermarche(pantrySearchQuery.trim(), true);
                            }
                          }}
                          disabled={searchLoading || !pantrySearchQuery.trim()}
                          className="px-4 py-2.5 border border-red-200 text-red-600 text-sm font-semibold rounded-xl hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          Actualiser
                        </button>
                      )}
                    </div>

                    {searchLoading && (
                      <p className="text-xs text-apple-gray-400 animate-pulse">⏳ Recherche du produit magasin…</p>
                    )}

                    {searchError && (
                      <p className="text-xs text-red-500">❌ {searchError}</p>
                    )}

                    {searchResults.length > 0 && !searchLoading && (
                      <div className="space-y-2">
                        <p className="text-xs text-apple-gray-400">{searchResults.length} résultat(s) — clique pour créer le produit pantry depuis le magasin</p>
                        <div className="flex gap-3 overflow-x-auto pb-2 -mx-1 px-1">
                          {searchResults.map((product) => (
                            <button
                              key={product.cache_id}
                              type="button"
                              onClick={() => handleSelectPantryProduct(product)}
                              className={`flex-shrink-0 w-40 rounded-xl border-2 text-left transition-all hover:shadow-md ${
                                selectedPantryProduct?.cache_id === product.cache_id
                                  ? 'border-red-500 shadow-md bg-red-50'
                                  : 'border-apple-gray-200 bg-white hover:border-red-300'
                              }`}
                            >
                              {product.image_url ? (
                                <img src={product.image_url} alt={product.name} className="w-full h-24 object-contain rounded-t-xl bg-white p-2" />
                              ) : (
                                <div className="w-full h-24 rounded-t-xl bg-apple-gray-100 flex items-center justify-center">
                                  <Package className="w-8 h-8 text-apple-gray-300" />
                                </div>
                              )}
                              <div className="p-2">
                                <p className="text-[11px] font-semibold text-black leading-tight line-clamp-2">{product.name}</p>
                                {product.category && <p className="text-[10px] text-apple-gray-500 mt-0.5 truncate">{product.category}</p>}
                                {product.packaging && <p className="text-[10px] text-apple-gray-400 mt-0.5 truncate">{product.packaging}</p>}
                                {product.price_text && <p className="text-[11px] font-bold text-red-600 mt-1">{product.price_text}</p>}
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-black">Ajouter au garde-manger</h3>
                    {selectedPantryProduct && (
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-red-600 bg-red-50 border border-red-200 rounded-full px-2.5 py-1">
                        <Store className="w-3 h-3" />
                        Produit magasin sélectionné
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedPantryProduct(null);
                            setPName('');
                            setPQty('1');
                            setPUnit('item');
                            setPCategory('');
                          }}
                          className="ml-1 hover:text-red-800"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <input type="text" placeholder="Nom" value={pName} onChange={(e) => setPName(e.target.value)} required autoFocus className={`col-span-2 ${inputCls}`} />
                    <div className="relative">
                      <input type="number" placeholder="Quantité" value={pQty} onChange={(e) => setPQty(e.target.value)} min="0" step="0.5" className={`w-full ${inputCls}`} />
                    </div>
                    <input type="text" placeholder="Unité (item, g, L…)" value={pUnit} onChange={(e) => setPUnit(e.target.value)} className={inputCls} />
                    <input type="text" placeholder="Catégorie" value={pCategory} onChange={(e) => setPCategory(e.target.value)} className={inputCls} />
                    <input type="number" placeholder="Qté min (alerte stock)" value={pMinQty} onChange={(e) => setPMinQty(e.target.value)} min="0" step="0.5" className={inputCls} />
                    <div>
                      <label className="block text-xs text-apple-gray-500 mb-1">Date de péremption</label>
                      <input type="date" value={pExpires} onChange={(e) => setPExpires(e.target.value)} className={`w-full ${inputCls}`} />
                    </div>
                    <input type="text" placeholder="Emplacement (frigo, placard…)" value={pLocation} onChange={(e) => setPLocation(e.target.value)} className={inputCls} />
                  </div>
                  <div className="flex gap-3">
                    <button type="submit" className="px-5 py-2.5 bg-apple-blue text-white text-sm font-semibold rounded-xl hover:bg-blue-600 transition-colors">Ajouter</button>
                    <button type="button" onClick={handleTogglePantryForm} className="px-5 py-2.5 text-sm font-medium text-apple-gray-500 hover:bg-apple-gray-100 rounded-xl transition-colors">Annuler</button>
                  </div>
                </form>
              )}

              {/* Pantry list */}
              {pantryLoading ? (
                <div className="flex items-center justify-center py-16">
                  <div className="w-8 h-8 border-2 border-apple-blue/30 border-t-apple-blue rounded-full animate-spin" />
                </div>
              ) : filteredPantry.length === 0 ? (
                <div className="bg-white rounded-2xl border border-apple-gray-200 shadow-sm py-16 text-center">
                  <Package className="w-12 h-12 text-apple-gray-300 mx-auto mb-3" />
                  <p className="text-apple-gray-500 text-sm">Garde-manger vide</p>
                </div>
              ) : (
                <div className="bg-white rounded-2xl border border-apple-gray-200 shadow-sm overflow-hidden">
                  {pantryGroups.map(([category, groupItems]) => (
                    <div key={category} className="border-b border-apple-gray-100 last:border-b-0">
                      <button
                        onClick={() => toggleGroup(`pantry-${category}`)}
                        className="w-full flex items-center gap-2 px-4 py-2 bg-apple-gray-50 hover:bg-apple-gray-100 transition-colors"
                      >
                        <div className="w-2 h-2 rounded-full shrink-0" style={{ background: getCategoryColor(groupItems[0].category) }} />
                        <span className="text-xs font-semibold text-apple-gray-600 uppercase tracking-wider flex-1 text-left">{category}</span>
                        <span className="text-xs text-apple-gray-400">{groupItems.length}</span>
                        {collapsedGroups.has(`pantry-${category}`) ? <ChevronRight className="w-3.5 h-3.5 text-apple-gray-400" /> : <ChevronDown className="w-3.5 h-3.5 text-apple-gray-400" />}
                      </button>
                      {!collapsedGroups.has(`pantry-${category}`) && (
                        <div className="divide-y divide-apple-gray-50">
                          {groupItems.map((item) => (
                            <PantryRow
                              key={item.id}
                              item={item}
                              onDelete={deletePantryItem}
                              onConsume={consumePantryItem}
                              onUpdate={updatePantryItem}
                              onMap={async (target) => {
                                setMappingTarget(target);
                                setMappingQuery(target.name);
                                clearSearchResults();
                                await fetchPantryMapping(target.id);
                              }}
                            />
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

        </div>
      </div>
    </div>
  );
}
