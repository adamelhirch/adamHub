import { useState, useEffect, useMemo } from 'react';
import { format, differenceInDays, parseISO } from 'date-fns';
import {
  ShoppingBasket, ShoppingCart, Package, Plus, Trash2, Check, Search, X, AlertTriangle,
  ChevronDown, ChevronRight, Minus, Loader2, Store, Pencil, Lock,
} from 'lucide-react';
import { useGroceryStore, STORE_LABELS, STORE_CAPABILITIES, ACCOUNT_REQUIRED_STORES } from '../store/groceryStore';
import type {
  CartStatus,
  GroceryItem,
  PantryItem,
  SupermarketCartItem,
  SupermarketConnection,
  SupermarketMapping,
  SupermarketProduct,
  SupermarketStoreKey,
} from '../store/groceryStore';

function storeLabelFor(store: string | null | undefined): string {
  if (!store) return 'Magasin';
  return STORE_LABELS[store as SupermarketStoreKey] ?? store;
}

// Client-side geocoding via the French government open API (no key, CORS-enabled).
async function geocodeFrance(zipcode: string, city: string): Promise<{ lat: number; lng: number } | null> {
  try {
    const params = new URLSearchParams();
    if (zipcode.trim()) params.set('postcode', zipcode.trim());
    if (city.trim()) params.set('q', city.trim());
    if (!params.has('q') && !params.has('postcode')) return null;
    params.set('limit', '1');
    const res = await fetch(`https://api-adresse.data.gouv.fr/search/?${params.toString()}`);
    if (!res.ok) return null;
    const data: { features?: Array<{ geometry?: { coordinates?: number[] } }> } = await res.json();
    const coords = data.features?.[0]?.geometry?.coordinates;
    if (!coords || coords.length < 2) return null;
    return { lat: coords[1], lng: coords[0] };
  } catch {
    return null;
  }
}

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

function normalizeListKey(value: string | null | undefined): string {
  return (value ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^\w\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

function parsePackagingQuantity(packaging: string | null | undefined): { quantity: number; unit: string } | null {
  if (!packaging) return null;
  const match = packaging.match(/(\d+(?:[.,]\d+)?)\s*(kg|g|L|cl|ml|item|items)/i);
  if (!match) return null;
  return {
    quantity: parseFloat(match[1].replace(',', '.')),
    unit: match[2].toLowerCase() === 'l' ? 'L' : match[2].toLowerCase(),
  };
}

const PRIORITY_LABEL: Record<number, { label: string; color: string }> = {
  1: { label: 'Urgent', color: 'text-red-500 bg-red-50' },
  2: { label: 'Élevée', color: 'text-amber-600 bg-amber-50' },
  3: { label: 'Normale', color: 'text-blue-600 bg-blue-50' },
};

const TAB_LIST = ['Liste de courses', 'Garde-manger', 'Panier'] as const;
type Tab = (typeof TAB_LIST)[number];

function formatCartPrice(amount: number | null): string {
  if (amount === null) return '—';
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(amount);
}

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
function GroceryRow({ item, onToggle, onDelete, onUpdate }: {
  item: GroceryItem;
  onToggle: (id: number, checked: boolean) => void;
  onDelete: (id: number) => void;
  onUpdate: (id: number, data: Partial<Pick<GroceryItem, 'name' | 'quantity' | 'unit' | 'category' | 'image_url' | 'store_label' | 'external_id' | 'packaging' | 'price_text' | 'product_url' | 'priority' | 'note' | 'checked'>>) => Promise<void>;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [draftName, setDraftName] = useState(item.name);
  const [draftQuantity, setDraftQuantity] = useState(String(item.quantity));
  const [draftUnit, setDraftUnit] = useState(item.unit);
  const [draftCategory, setDraftCategory] = useState(item.category ?? '');
  const [draftPriority, setDraftPriority] = useState(item.priority);
  const [draftNote, setDraftNote] = useState(item.note ?? '');
  const { source, details } = parseGroceryNote(item.note);
  const quantityLabel = item.quantity !== 1 || item.unit !== 'item' ? `${item.quantity} ${item.unit}` : null;

  useEffect(() => {
    setDraftName(item.name);
    setDraftQuantity(String(item.quantity));
    setDraftUnit(item.unit);
    setDraftCategory(item.category ?? '');
    setDraftPriority(item.priority);
    setDraftNote(item.note ?? '');
  }, [item]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!draftName.trim()) return;
    await onUpdate(item.id, {
      name: draftName.trim(),
      quantity: parseFloat(draftQuantity) || 0,
      unit: draftUnit.trim() || 'item',
      category: draftCategory.trim() || null,
      priority: draftPriority,
      note: draftNote.trim() || null,
    });
    setIsEditing(false);
  };

  return (
    <div className={`group px-4 py-3.5 transition-colors hover:bg-apple-gray-50 ${item.checked ? 'opacity-60' : ''}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
        <div className="flex min-w-0 flex-1 items-start gap-3">
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
            <div className="flex flex-wrap items-start gap-2">
              <p className={`min-w-0 flex-1 text-sm font-semibold leading-5 ${item.checked ? 'line-through text-apple-gray-400' : 'text-black'}`}>
                {item.name}
              </p>
              {item.priority < 3 && (
                <span className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-bold uppercase ${PRIORITY_LABEL[item.priority]?.color}`}>
                  {PRIORITY_LABEL[item.priority]?.label}
                </span>
              )}
            </div>
            {(quantityLabel || item.packaging || item.price_text || source || details || item.store_label) && (
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="rounded-full px-2.5 py-1 text-[11px] font-semibold" style={{ backgroundColor: `${getCategoryColor(item.category)}1A`, color: getCategoryColor(item.category) }}>
                  {formatCategoryLabel(item.category)}
                </span>
                {item.store_label && (
                  <span className="rounded-full bg-red-50 px-2.5 py-1 text-[11px] font-semibold text-red-600">
                    {item.store_label}
                  </span>
                )}
                {quantityLabel && (
                  <span className="rounded-full bg-apple-gray-100 px-2.5 py-1 text-[11px] font-semibold text-apple-gray-600">
                    {quantityLabel}
                  </span>
                )}
                {item.packaging && (
                  <span className="rounded-full bg-apple-gray-100 px-2.5 py-1 text-[11px] font-medium text-apple-gray-500">
                    {item.packaging}
                  </span>
                )}
                {item.price_text && (
                  <span className="rounded-full bg-red-50 px-2.5 py-1 text-[11px] font-semibold text-red-600">
                    {item.price_text}
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
        </div>
        <div className="flex items-center justify-end gap-1 pl-8 sm:pl-0">
          <button
            onClick={() => setIsEditing((value) => !value)}
            className="rounded-lg p-1.5 text-apple-gray-400 opacity-100 transition-all hover:bg-apple-gray-100 hover:text-apple-blue md:opacity-0 md:group-hover:opacity-100"
            title="Modifier"
          >
            <Pencil className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => onDelete(item.id)}
            className="rounded-lg p-1.5 text-apple-gray-400 opacity-100 transition-all hover:bg-red-50 hover:text-red-500 md:opacity-0 md:group-hover:opacity-100"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {isEditing && (
        <form onSubmit={handleSubmit} className="mt-4 rounded-2xl border border-apple-gray-200 bg-white p-4">
          <div className="grid gap-3 md:grid-cols-2">
            <input
              type="text"
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              placeholder="Nom"
              className="rounded-xl border border-apple-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
            />
            <input
              type="text"
              value={draftCategory}
              onChange={(e) => setDraftCategory(e.target.value)}
              placeholder="Catégorie"
              className="rounded-xl border border-apple-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
            />
            <input
              type="number"
              min="0"
              step="0.5"
              value={draftQuantity}
              onChange={(e) => setDraftQuantity(e.target.value)}
              placeholder="Quantité"
              className="rounded-xl border border-apple-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
            />
            <input
              type="text"
              value={draftUnit}
              onChange={(e) => setDraftUnit(e.target.value)}
              placeholder="Unité"
              className="rounded-xl border border-apple-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
            />
            <select
              value={draftPriority}
              onChange={(e) => setDraftPriority(Number(e.target.value))}
              className="rounded-xl border border-apple-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
            >
              <option value={1}>Urgent</option>
              <option value={2}>Élevée</option>
              <option value={3}>Normale</option>
            </select>
            <input
              type="text"
              value={draftNote}
              onChange={(e) => setDraftNote(e.target.value)}
              placeholder="Note"
              className="rounded-xl border border-apple-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
            />
          </div>
          <div className="mt-3 flex gap-2">
            <button
              type="submit"
              className="rounded-xl bg-apple-blue px-4 py-2 text-sm font-semibold text-white hover:bg-blue-600"
            >
              Enregistrer
            </button>
            <button
              type="button"
              onClick={() => {
                setIsEditing(false);
                setDraftName(item.name);
                setDraftQuantity(String(item.quantity));
                setDraftUnit(item.unit);
                setDraftCategory(item.category ?? '');
                setDraftPriority(item.priority);
                setDraftNote(item.note ?? '');
              }}
              className="rounded-xl px-4 py-2 text-sm font-medium text-apple-gray-500 hover:bg-apple-gray-100"
            >
              Annuler
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

// ─── PantryRow ────────────────────────────────────────────────────────────────
function PantryRow({ item, onDelete, onConsume, onUpdate, onMap, onRestock }: {
  item: PantryItem;
  onDelete: (id: number) => void;
  onConsume: (id: number, amount: number) => void;
  onUpdate: (id: number, data: Partial<Pick<PantryItem, 'name' | 'quantity' | 'unit' | 'category' | 'image_url' | 'store_label' | 'external_id' | 'packaging' | 'price_text' | 'product_url' | 'min_quantity' | 'expires_at' | 'location' | 'note'>>) => Promise<void>;
  onMap: (item: PantryItem) => void;
  onRestock: (item: PantryItem) => Promise<void>;
}) {
  const [editingQty, setEditingQty] = useState(false);
  const [qtyValue, setQtyValue] = useState(String(item.quantity));
  const [isEditing, setIsEditing] = useState(false);
  const [draftName, setDraftName] = useState(item.name);
  const [draftQuantity, setDraftQuantity] = useState(String(item.quantity));
  const [draftUnit, setDraftUnit] = useState(item.unit);
  const [draftCategory, setDraftCategory] = useState(item.category ?? '');
  const [draftMinQuantity, setDraftMinQuantity] = useState(String(item.min_quantity));
  const [draftLocation, setDraftLocation] = useState(item.location ?? '');
  const [draftExpiresAt, setDraftExpiresAt] = useState(item.expires_at ?? '');
  const [draftNote, setDraftNote] = useState(item.note ?? '');
  const isLowStock = item.quantity <= item.min_quantity && item.min_quantity > 0;
  const expireSoon = item.expires_at
    ? differenceInDays(parseISO(item.expires_at), new Date())
    : null;
  const isExpireSoon = expireSoon !== null && expireSoon <= 7;

  useEffect(() => {
    setQtyValue(String(item.quantity));
    setDraftName(item.name);
    setDraftQuantity(String(item.quantity));
    setDraftUnit(item.unit);
    setDraftCategory(item.category ?? '');
    setDraftMinQuantity(String(item.min_quantity));
    setDraftLocation(item.location ?? '');
    setDraftExpiresAt(item.expires_at ?? '');
    setDraftNote(item.note ?? '');
  }, [item]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!draftName.trim()) return;
    await onUpdate(item.id, {
      name: draftName.trim(),
      quantity: parseFloat(draftQuantity) || 0,
      unit: draftUnit.trim() || 'item',
      category: draftCategory.trim() || null,
      min_quantity: parseFloat(draftMinQuantity) || 0,
      location: draftLocation.trim() || null,
      expires_at: draftExpiresAt || null,
      note: draftNote.trim() || null,
    });
    setIsEditing(false);
  };

  return (
    <div className={`group px-4 py-3 transition-colors hover:bg-apple-gray-50 ${isLowStock ? 'bg-amber-50/40' : ''}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
        <div className="flex min-w-0 flex-1 items-start gap-3">
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
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="min-w-0 flex-1 text-sm font-semibold leading-5 text-black break-words">{item.name}</p>
              {isLowStock && <AlertTriangle className="w-3 h-3 text-amber-500 shrink-0" />}
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {item.category && (
                <span className="rounded-full px-2.5 py-1 text-[11px] font-semibold" style={{ backgroundColor: `${getCategoryColor(item.category)}1A`, color: getCategoryColor(item.category) }}>
                  {formatCategoryLabel(item.category)}
                </span>
              )}
              {item.store_label && (
                <span className="rounded-full bg-red-50 px-2.5 py-1 text-[11px] font-semibold text-red-600">
                  {item.store_label}
                </span>
              )}
              <span className="rounded-full bg-apple-gray-100 px-2.5 py-1 text-[11px] font-semibold text-apple-gray-600">
                {item.quantity} {item.unit}
              </span>
              {item.packaging && (
                <span className="rounded-full bg-apple-gray-100 px-2.5 py-1 text-[11px] font-medium text-apple-gray-500">
                  {item.packaging}
                </span>
              )}
              {item.price_text && (
                <span className="rounded-full bg-red-50 px-2.5 py-1 text-[11px] font-semibold text-red-600">
                  {item.price_text}
                </span>
              )}
              {item.location && (
                <span className="rounded-full bg-apple-gray-100 px-2.5 py-1 text-[11px] font-medium text-apple-gray-500">
                  {item.location}
                </span>
              )}
              {item.expires_at && (
                <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${isExpireSoon ? 'bg-red-50 text-red-500' : 'bg-apple-gray-100 text-apple-gray-500'}`}>
                  Exp. {format(parseISO(item.expires_at), 'dd/MM/yyyy')}
                  {expireSoon !== null && expireSoon <= 7 && ` · J-${expireSoon}`}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 sm:max-w-[280px] sm:justify-end">
          {!isEditing && (
            <div className="flex items-center gap-1 rounded-full bg-apple-gray-100 px-2 py-1">
              <button
                onClick={() => onConsume(item.id, 1)}
                className="rounded p-1 text-apple-gray-400 transition-all hover:bg-red-50 hover:text-red-500 md:opacity-0 md:group-hover:opacity-100"
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
                      if (!isNaN(v)) {
                        void onUpdate(item.id, { quantity: v });
                      }
                      setEditingQty(false);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        const v = parseFloat(qtyValue);
                        if (!isNaN(v)) {
                          void onUpdate(item.id, { quantity: v });
                        }
                        setEditingQty(false);
                      }
                      if (e.key === 'Escape') setEditingQty(false);
                    }}
                    autoFocus
                    className="w-16 rounded border border-apple-blue px-2 py-1 text-center text-sm focus:outline-none"
                    step="1"
                  />
                </div>
              ) : (
                <button
                  onClick={() => { setEditingQty(true); setQtyValue(String(item.quantity)); }}
                  className={`rounded px-2 py-0.5 text-sm font-bold transition-colors hover:bg-white ${isLowStock ? 'text-amber-600' : 'text-black'}`}
                >
                  {item.quantity}
                </button>
              )}
              <span className="text-xs text-apple-gray-400">{item.unit}</span>
              <button
                onClick={() => void onUpdate(item.id, { quantity: item.quantity + 1 })}
                className="rounded p-1 text-apple-gray-400 transition-all hover:bg-emerald-50 hover:text-emerald-600 md:opacity-0 md:group-hover:opacity-100"
                title="Ajouter 1"
              >
                <Plus className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
          {isLowStock && (
            <button
              onClick={() => void onRestock(item)}
              className="rounded-xl bg-amber-100 px-3 py-2 text-xs font-semibold text-amber-700 transition-colors hover:bg-amber-200"
              title="Ajouter à la liste de courses"
            >
              Ajouter à la liste
            </button>
          )}
          <button
            onClick={() => setIsEditing((value) => !value)}
            className="rounded-lg p-1.5 text-apple-gray-400 opacity-100 transition-all hover:bg-apple-gray-100 hover:text-apple-blue md:opacity-0 md:group-hover:opacity-100"
            title="Modifier"
          >
            <Pencil className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => onMap(item)}
            className="rounded-lg p-1.5 text-apple-gray-400 opacity-100 transition-all hover:bg-red-50 hover:text-red-600 md:opacity-0 md:group-hover:opacity-100"
            title="Lier un produit magasin"
          >
            <Store className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => onDelete(item.id)}
            className="rounded-lg p-1.5 text-apple-gray-400 opacity-100 transition-all hover:bg-red-50 hover:text-red-500 md:opacity-0 md:group-hover:opacity-100"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {isEditing && (
        <form onSubmit={handleSubmit} className="mt-4 rounded-2xl border border-apple-gray-200 bg-white p-4">
          <div className="grid gap-3 md:grid-cols-2">
            <input
              type="text"
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              placeholder="Nom"
              className="rounded-xl border border-apple-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
            />
            <input
              type="text"
              value={draftCategory}
              onChange={(e) => setDraftCategory(e.target.value)}
              placeholder="Catégorie"
              className="rounded-xl border border-apple-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
            />
            <input
              type="number"
              min="0"
              step="0.5"
              value={draftQuantity}
              onChange={(e) => setDraftQuantity(e.target.value)}
              placeholder="Quantité"
              className="rounded-xl border border-apple-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
            />
            <input
              type="text"
              value={draftUnit}
              onChange={(e) => setDraftUnit(e.target.value)}
              placeholder="Unité"
              className="rounded-xl border border-apple-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
            />
            <input
              type="number"
              min="0"
              step="0.5"
              value={draftMinQuantity}
              onChange={(e) => setDraftMinQuantity(e.target.value)}
              placeholder="Seuil stock faible"
              className="rounded-xl border border-apple-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
            />
            <input
              type="text"
              value={draftLocation}
              onChange={(e) => setDraftLocation(e.target.value)}
              placeholder="Emplacement"
              className="rounded-xl border border-apple-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
            />
            <input
              type="date"
              value={draftExpiresAt}
              onChange={(e) => setDraftExpiresAt(e.target.value)}
              className="rounded-xl border border-apple-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
            />
            <input
              type="text"
              value={draftNote}
              onChange={(e) => setDraftNote(e.target.value)}
              placeholder="Note"
              className="rounded-xl border border-apple-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
            />
          </div>
          <div className="mt-3 flex gap-2">
            <button
              type="submit"
              className="rounded-xl bg-apple-blue px-4 py-2 text-sm font-semibold text-white hover:bg-blue-600"
            >
              Enregistrer
            </button>
            <button
              type="button"
              onClick={() => {
                setIsEditing(false);
                setDraftName(item.name);
                setDraftQuantity(String(item.quantity));
                setDraftUnit(item.unit);
                setDraftCategory(item.category ?? '');
                setDraftMinQuantity(String(item.min_quantity));
                setDraftLocation(item.location ?? '');
                setDraftExpiresAt(item.expires_at ?? '');
                setDraftNote(item.note ?? '');
              }}
              className="rounded-xl px-4 py-2 text-sm font-medium text-apple-gray-500 hover:bg-apple-gray-100"
            >
              Annuler
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

function PantryMappingPanel({
  item,
  store,
  searchGateBlocked,
  searchGateMessage,
  mapping,
  query,
  setQuery,
  promotionsOnly,
  setPromotionsOnly,
  supportsPromotions,
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
  store: SupermarketStoreKey;
  searchGateBlocked: boolean;
  searchGateMessage: string;
  mapping: SupermarketMapping | null;
  query: string;
  setQuery: (value: string) => void;
  promotionsOnly: boolean;
  setPromotionsOnly: (value: boolean) => void;
  supportsPromotions: boolean;
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
          <p className="text-xs font-bold uppercase tracking-wider text-red-600">Mapping magasin</p>
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
          <p className="text-sm text-apple-gray-500">Aucun produit magasin lié pour cet article.</p>
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
                  if (!searchGateBlocked) {
                    void onSearch();
                  }
                }
              }}
              placeholder="Rechercher un produit"
              className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-apple-gray-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-red-400/40"
            />
          </div>
          <button
            onClick={() => void onSearch()}
            disabled={searchLoading || !query.trim() || searchGateBlocked}
            className="px-4 py-2.5 bg-red-600 text-white text-sm font-semibold rounded-xl hover:bg-red-700 disabled:opacity-50"
          >
            {searchLoading ? 'Recherche…' : 'Rechercher'}
          </button>
          {canRefresh && (
            <button
              onClick={() => void onRefresh()}
              disabled={searchLoading || !query.trim() || searchGateBlocked}
              className="px-4 py-2.5 border border-red-200 text-red-600 text-sm font-semibold rounded-xl hover:bg-red-50 disabled:opacity-50"
            >
              Actualiser
            </button>
          )}
        </div>

        {store === 'auchan' && <AuchanStorePicker />}

        {supportsPromotions && (
          <label className="flex items-center gap-2 text-sm text-apple-gray-600">
            <input
              type="checkbox"
              checked={promotionsOnly}
              onChange={(e) => setPromotionsOnly(e.target.checked)}
              className="h-4 w-4 rounded border-apple-gray-300 text-red-600 focus:ring-red-400"
            />
            Promotions uniquement
          </label>
        )}

        {searchGateBlocked && (
          <p className="flex items-center gap-1.5 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            <Lock className="w-3 h-3 shrink-0" />
            {searchGateMessage}
          </p>
        )}

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
                <AddToCartButton store={store} product={product} className="px-3 py-2 text-xs shrink-0" />
                <button
                  onClick={() => void onLink(product)}
                  className="px-3 py-2 rounded-xl bg-apple-blue text-white text-sm font-semibold hover:bg-blue-600 shrink-0"
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

// ─── AddToCartButton ─────────────────────────────────────────────────────────
// Quick-add of a search result to the cart of `store` (quantity 1), with a
// transient "Ajouté" confirmation state. Errors surface through the store's
// cartError, displayed in the Panier tab.
function AddToCartButton({ store, product, className }: {
  store: SupermarketStoreKey;
  product: SupermarketProduct;
  className?: string;
}) {
  const addCartItem = useGroceryStore((s) => s.addCartItem);
  const [added, setAdded] = useState<'idle' | 'added' | 'error'>('idle');

  const handleClick = async () => {
    // The store swallows API errors into cartError (surfaced in the Panier
    // tab) rather than rethrowing, so read it back to reflect the outcome.
    await addCartItem(store, { cache_id: product.cache_id, quantity: 1 });
    setAdded(useGroceryStore.getState().cartError ? 'error' : 'added');
    window.setTimeout(() => setAdded('idle'), 1600);
  };

  return (
    <button
      type="button"
      onClick={() => void handleClick()}
      className={`inline-flex items-center justify-center gap-1 rounded-xl text-sm font-semibold transition-colors disabled:opacity-60 ${
        added === 'added'
          ? 'bg-emerald-500 text-white hover:bg-emerald-600'
          : added === 'error'
            ? 'bg-amber-500 text-white hover:bg-amber-600'
            : 'bg-red-600 text-white hover:bg-red-700'
      } ${className ?? ''}`}
      title={
        added === 'added'
          ? 'Ajouté au panier'
          : added === 'error'
            ? `Échec de l'ajout au panier ${STORE_LABELS[store]}`
            : `Ajouter au panier ${STORE_LABELS[store]}`
      }
    >
      {added === 'added' ? (
        <Check className="w-3.5 h-3.5" />
      ) : added === 'error' ? (
        <AlertTriangle className="w-3.5 h-3.5" />
      ) : (
        <Plus className="w-3.5 h-3.5" />
      )}
      {added === 'added' ? 'Ajouté' : added === 'error' ? 'Erreur' : '+ Panier'}
    </button>
  );
}

// ─── CartItemRow ─────────────────────────────────────────────────────────────
function CartItemRow({ item, onUpdateQuantity, onRemove }: {
  item: SupermarketCartItem;
  onUpdateQuantity: (itemId: number, quantity: number) => void;
  onRemove: (itemId: number) => void;
}) {
  const [editingQty, setEditingQty] = useState(false);
  const [qtyValue, setQtyValue] = useState(String(item.quantity));

  useEffect(() => {
    setQtyValue(String(item.quantity));
  }, [item.quantity]);

  const commitQty = () => {
    const value = Math.max(1, Math.round(parseFloat(qtyValue) || 1));
    setQtyValue(String(value));
    if (value !== item.quantity) {
      onUpdateQuantity(item.id, value);
    }
    setEditingQty(false);
  };

  const unitPrice = item.price_text ?? formatCartPrice(item.price_amount);
  const subtotal = item.price_amount === null ? null : item.price_amount * item.quantity;

  return (
    <div className="flex items-center gap-3 px-4 py-3">
      {item.image_url ? (
        <img
          src={item.image_url}
          alt={item.name}
          className="h-12 w-12 shrink-0 rounded-xl border border-apple-gray-100 bg-white object-contain p-1"
        />
      ) : (
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-apple-gray-100">
          <ShoppingCart className="h-5 w-5 text-apple-gray-300" />
        </div>
      )}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold leading-5 text-black">{item.name}</p>
        <p className="mt-0.5 truncate text-[11px] text-apple-gray-500">
          {unitPrice}
          {item.packaging ? ` · ${item.packaging}` : ''}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-1 rounded-full bg-apple-gray-100 px-2 py-1">
        <button
          onClick={() => onUpdateQuantity(item.id, Math.max(1, item.quantity - 1))}
          disabled={item.quantity <= 1}
          className="rounded p-1 text-apple-gray-400 transition-all hover:bg-red-50 hover:text-red-500 disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-apple-gray-400"
          title="Retirer 1"
        >
          <Minus className="w-3.5 h-3.5" />
        </button>
        {editingQty ? (
          <input
            type="number"
            min="1"
            step="1"
            value={qtyValue}
            onChange={(e) => setQtyValue(e.target.value)}
            onBlur={commitQty}
            onKeyDown={(e) => {
              if (e.key === 'Enter') commitQty();
              if (e.key === 'Escape') {
                setQtyValue(String(item.quantity));
                setEditingQty(false);
              }
            }}
            autoFocus
            className="w-12 rounded border border-apple-blue px-1.5 py-0.5 text-center text-sm focus:outline-none"
          />
        ) : (
          <button
            onClick={() => { setEditingQty(true); setQtyValue(String(item.quantity)); }}
            className="rounded px-1.5 py-0.5 text-sm font-bold text-black transition-colors hover:bg-white"
            title="Modifier la quantité"
          >
            {item.quantity}
          </button>
        )}
        <button
          onClick={() => onUpdateQuantity(item.id, item.quantity + 1)}
          className="rounded p-1 text-apple-gray-400 transition-all hover:bg-emerald-50 hover:text-emerald-600"
          title="Ajouter 1"
        >
          <Plus className="w-3.5 h-3.5" />
        </button>
      </div>
      <span className="w-20 shrink-0 text-right text-sm font-bold text-black">
        {formatCartPrice(subtotal)}
      </span>
      <button
        onClick={() => onRemove(item.id)}
        className="shrink-0 rounded-lg p-1.5 text-apple-gray-400 transition-all hover:bg-red-50 hover:text-red-500"
        title="Retirer du panier"
      >
        <Trash2 className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function GroceriesPage() {
  const {
    items, groceryLoading, fetchItems, addItem, updateItem, toggleCheck, deleteItem, clearChecked,
    pantryItems, pantryOverview, pantryLoading, fetchPantry, fetchPantryOverview,
    addPantryItem, updatePantryItem, deletePantryItem, consumePantryItem,
    searchResults, searchLoading, searchError, searchSupermarket, clearSearchResults,
    pantryMappings, fetchPantryMapping, savePantryMapping, deleteMapping, hasCachedProducts,
    selectedStore, setSelectedStore,
    connections, fetchConnections, activateConnection, deleteConnection,
    auchanSelectedStore, fetchSelectedAuchanStore,
    cartsByStore, cartLoading, cartError, fetchCarts, fetchCart,
    updateCartItemQuantity, removeCartItem, clearCart, setCartStatus,
  } = useGroceryStore();

  const currentStoreLabel = STORE_LABELS[selectedStore];
  const selectedCapabilities = STORE_CAPABILITIES[selectedStore];
  const supportsPromotions = selectedCapabilities.supports_promotions;

  // Search gate: block before the POST /search when the store has no usable
  // session — account-less stores (non-Auchan without a connection) and Auchan
  // without a selected store.
  const selectedStoreHasConnection = connections.some((c) => c.store === selectedStore);
  const searchGateBlocked = selectedStore === 'auchan'
    ? !auchanSelectedStore
    : !selectedStoreHasConnection;
  const searchGateMessage = selectedStore === 'auchan'
    ? 'Sélectionne un magasin Auchan avant de lancer une recherche.'
    : `Compte requis : branche une connexion ${currentStoreLabel} via l'extension AdamHUB Connect pour rechercher les prix.`;

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
  const [promotionsOnly, setPromotionsOnly] = useState(false);

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
    fetchConnections();
    fetchSelectedAuchanStore();
    fetchCarts();
  }, []);

  // Keep the current store's cart loaded (tab badge + Panier tab).
  useEffect(() => {
    void fetchCart(selectedStore);
  }, [selectedStore, fetchCart]);

  // Refresh the cart each time the Panier tab is opened.
  useEffect(() => {
    if (activeTab === 'Panier') {
      void fetchCart(selectedStore);
    }
  }, [activeTab, selectedStore, fetchCart]);

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
      cache_id: selectedProduct?.cache_id || undefined,
      store_label: selectedProduct ? storeLabelFor(selectedProduct.store) : undefined,
      external_id: selectedProduct?.external_id || undefined,
      packaging: selectedProduct?.packaging || undefined,
      price_text: selectedProduct?.price_text || undefined,
      product_url: selectedProduct?.product_url || undefined,
      priority: newPriority,
      note: selectedProduct ? `${storeLabelFor(selectedProduct.store)} · ${selectedProduct.price_text ?? ''} · ${selectedProduct.packaging ?? ''}`.trim().replace(/·\s*$/, '') : undefined,
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
      cache_id: selectedPantryProduct?.cache_id || undefined,
      store_label: selectedPantryProduct ? storeLabelFor(selectedPantryProduct.store) : undefined,
      external_id: selectedPantryProduct?.external_id || undefined,
      packaging: selectedPantryProduct?.packaging || undefined,
      price_text: selectedPantryProduct?.price_text || undefined,
      product_url: selectedPantryProduct?.product_url || undefined,
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

  const handleUpdatePantry = async (
    id: number,
    data: Partial<Pick<PantryItem, 'name' | 'quantity' | 'unit' | 'category' | 'image_url' | 'store_label' | 'external_id' | 'packaging' | 'price_text' | 'product_url' | 'min_quantity' | 'expires_at' | 'location' | 'note'>>,
  ) => {
    await updatePantryItem(id, data);
    await fetchPantryOverview();
  };

  const handleConsumePantry = async (id: number, amount: number) => {
    await consumePantryItem(id, amount);
    await fetchPantryOverview();
  };

  const handleDeletePantry = async (id: number) => {
    await deletePantryItem(id);
    await fetchPantryOverview();
  };

  const handleAddLowStockToGroceries = async (item: PantryItem) => {
    const mapping = pantryMappings[item.id] ?? await fetchPantryMapping(item.id);
    const mappedQuantity = parsePackagingQuantity(mapping?.packaging_snapshot);
    const targetQuantity = mappedQuantity?.quantity ?? (
      item.min_quantity > 0
        ? Math.max(item.min_quantity - item.quantity, 1)
        : 1
    );
    const targetUnit = mappedQuantity?.unit ?? item.unit;
    const targetName = mapping?.name_snapshot ?? item.name;
    const targetCategory = mapping?.category_snapshot ?? item.category;
    const targetImage = mapping?.image_url ?? item.image_url;
    const targetNote = [mapping?.store_label, mapping?.price_snapshot, mapping?.packaging_snapshot]
      .filter(Boolean)
      .join(' · ') || item.note || 'Réassort garde-manger';

    const existing = items.find((candidate) => (
      !candidate.checked &&
      normalizeListKey(candidate.name) === normalizeListKey(targetName) &&
      normalizeListKey(candidate.unit) === normalizeListKey(targetUnit)
    ));

    // Store metadata must reference the cache row it came from; when the
    // mapping carries no cache_id we omit those fields rather than
    // re-submitting (the server rejects fabricated store metadata).
    const storeCacheId = mapping?.cache_id ?? undefined;
    const storeMetadata = storeCacheId
      ? {
          cache_id: storeCacheId,
          store_label: mapping?.store_label ?? item.store_label ?? undefined,
          external_id: mapping?.external_id ?? item.external_id ?? undefined,
          price_text: mapping?.price_snapshot ?? item.price_text ?? undefined,
          product_url: mapping?.product_url ?? item.product_url ?? undefined,
        }
      : {};

    if (existing) {
      await updateItem(existing.id, {
        quantity: Number((existing.quantity + targetQuantity).toFixed(2)),
        unit: targetUnit,
        category: existing.category ?? targetCategory,
        image_url: existing.image_url ?? targetImage,
        ...storeMetadata,
        packaging: existing.packaging ?? mapping?.packaging_snapshot ?? item.packaging,
        priority: Math.min(existing.priority, 2),
        note: existing.note ?? targetNote,
      });
      return;
    }

    await addItem({
      name: targetName,
      quantity: targetQuantity,
      unit: targetUnit,
      category: targetCategory ?? undefined,
      image_url: targetImage ?? undefined,
      ...storeMetadata,
      packaging: mapping?.packaging_snapshot ?? item.packaging ?? undefined,
      priority: 2,
      note: targetNote,
    });
  };

  // ── Cart (panier) logic ─────────────────────────────────────────────────
  const currentCart = cartsByStore[selectedStore];
  const cartItems = useMemo(() => currentCart?.items ?? [], [currentCart]);
  const cartItemCount = cartItems.reduce((sum, item) => sum + item.quantity, 0);

  const filteredCartItems = useMemo(() => {
    const q = search.toLowerCase();
    if (!q) return cartItems;
    return cartItems.filter((i) => i.name.toLowerCase().includes(q));
  }, [cartItems, search]);

  const pricedCartItemCount = filteredCartItems.filter((i) => i.price_amount !== null).length;
  const cartTotal = filteredCartItems.reduce(
    (sum, item) => sum + (item.price_amount ?? 0) * item.quantity,
    0,
  );

  const handleClearCart = () => {
    if (cartItems.length === 0) return;
    if (window.confirm(`Vider le panier ${currentStoreLabel} ?`)) {
      void clearCart(selectedStore);
    }
  };

  const handleSetCartStatus = (status: CartStatus) => {
    void setCartStatus(selectedStore, status);
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
    <div className="flex-1 flex flex-col h-full bg-transparent overflow-hidden">
      {/* Header */}
      <div className="sticky top-0 z-10 flex flex-col gap-4 border-b border-white/60 bg-white/75 px-4 py-4 shadow-[0_8px_30px_rgba(15,23,42,0.06)] backdrop-blur-xl sm:flex-row sm:items-center sm:justify-between sm:px-8 sm:py-5">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.28em] text-apple-gray-500">Courses</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-black sm:text-3xl">Groceries</h1>
          <p className="mt-1 text-sm text-apple-gray-500">Liste de courses, garde-manger et panier.</p>
        </div>
        <div className="relative w-full sm:w-auto">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-apple-gray-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={
              activeTab === 'Liste de courses'
                ? 'Rechercher un article…'
                : activeTab === 'Garde-manger'
                  ? 'Rechercher dans le garde-manger…'
                  : 'Rechercher dans le panier…'
            }
            className="w-full rounded-xl border border-apple-gray-200 bg-white py-2 pl-9 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-apple-blue/50 sm:w-64"
          />
          {search && (
            <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-apple-gray-400 hover:text-black">
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-white/60 bg-white/75 px-4 backdrop-blur-xl sm:px-8">
        <div className="flex gap-1 overflow-x-auto">
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
              {tab === 'Liste de courses' ? (
                <ShoppingBasket className="w-4 h-4" />
              ) : tab === 'Garde-manger' ? (
                <Package className="w-4 h-4" />
              ) : (
                <ShoppingCart className="w-4 h-4" />
              )}
              {tab}
              {tab === 'Liste de courses' && uncheckedItems.length > 0 && (
                <span className="bg-apple-blue text-white text-[10px] font-bold rounded-full px-1.5 py-0.5 min-w-[18px] text-center">
                  {uncheckedItems.length}
                </span>
              )}
              {tab === 'Panier' && cartItemCount > 0 && (
                <span className="bg-apple-blue text-white text-[10px] font-bold rounded-full px-1.5 py-0.5 min-w-[18px] text-center">
                  {cartItemCount}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-4 pb-[calc(env(safe-area-inset-bottom)+5.75rem)] sm:px-8 sm:py-6">
        <div className="max-w-2xl mx-auto space-y-4">

          {/* ── GROCERY LIST ─────────────────────────────────────────────── */}
          {activeTab === 'Liste de courses' && (
            <>
              {/* Toolbar */}
              <div className="flex items-center gap-3 flex-wrap">
                <button
                  onClick={handleOpenAddForm}
                  className="flex items-center gap-2 rounded-2xl bg-apple-blue px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-600"
                >
                  {showAddForm ? <X className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
                  {showAddForm ? 'Fermer' : 'Ajouter'}
                </button>
                {checkedItems.length > 0 && (
                <button
                  onClick={clearChecked}
                  className="flex items-center gap-2 rounded-2xl border border-red-200 px-4 py-2.5 text-sm font-medium text-red-500 transition-colors hover:bg-red-50"
                >
                    <Trash2 className="w-4 h-4" />
                    Vider les cochés ({checkedItems.length})
                  </button>
                )}
              </div>

              {/* Add form */}
              {showAddForm && (
                <div className="overflow-hidden rounded-[28px] border border-white/60 bg-white/80 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl">

                  {/* ── Supermarket search ─────────────────────────────── */}
                  <div className="p-5 border-b border-apple-gray-100">
                    <div className="flex items-center justify-between gap-3 mb-3">
                      <div className="flex items-center gap-2">
                        <Store className="w-4 h-4 text-red-600" />
                        <span className="text-xs font-bold text-red-600 uppercase tracking-wider">Rechercher sur {currentStoreLabel}</span>
                      </div>
                      <StoreSelector selected={selectedStore} onChange={setSelectedStore} connections={connections} />
                    </div>
                    <ConnectionStrip
                      store={selectedStore}
                      connections={connections}
                      onActivate={activateConnection}
                      onDelete={deleteConnection}
                    />
                    {selectedStore === 'auchan' && <AuchanStorePicker />}
                    <div className="flex flex-col gap-2 sm:flex-row">
                      <div className="relative flex-1">
                        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-apple-gray-400" />
                        <input
                          type="text"

                          placeholder="Ex: lait, poulet, yaourt…"
                          value={imQuery}
                          onChange={(e) => setImQuery(e.target.value)}
                          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); if (imQuery.trim() && !searchGateBlocked) searchSupermarket(selectedStore, imQuery.trim(), { promotionsOnly }); }}}
                          className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-apple-gray-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-red-400/40"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() => { if (imQuery.trim() && !searchGateBlocked) searchSupermarket(selectedStore, imQuery.trim(), { promotionsOnly }); }}
                        disabled={searchLoading || !imQuery.trim() || searchGateBlocked}
                        className="flex items-center gap-2 px-4 py-2.5 bg-red-600 text-white text-sm font-semibold rounded-xl hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        {searchLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                        {searchLoading ? 'Scraping…' : 'Rechercher'}
                      </button>
                      {imQueryHasCache && (
                        <button
                          type="button"
                          onClick={() => { if (imQuery.trim() && !searchGateBlocked) searchSupermarket(selectedStore, imQuery.trim(), { forceRefresh: true, promotionsOnly }); }}
                          disabled={searchLoading || !imQuery.trim() || searchGateBlocked}
                          className="px-4 py-2.5 border border-red-200 text-red-600 text-sm font-semibold rounded-xl hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          Actualiser
                        </button>
                      )}
                    </div>

                    {searchGateBlocked && (
                      <p className="mt-2 flex items-center gap-1.5 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                        <Lock className="w-3 h-3 shrink-0" />
                        {searchGateMessage}
                      </p>
                    )}
                    {supportsPromotions && (
                      <label className="mt-2 flex items-center gap-2 text-sm text-apple-gray-600">
                        <input
                          type="checkbox"
                          checked={promotionsOnly}
                          onChange={(e) => setPromotionsOnly(e.target.checked)}
                          className="h-4 w-4 rounded border-apple-gray-300 text-red-600 focus:ring-red-400"
                        />
                        Promotions uniquement
                      </label>
                    )}

                    {/* Loading hint */}
                    {searchLoading && (
                      <p className="text-xs text-apple-gray-400 mt-2 animate-pulse">
                        ⏳ Le scraper {currentStoreLabel} est en cours… (~15-30s)
                      </p>
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
                            <div
                              key={p.cache_id}
                              className={`relative flex flex-col flex-shrink-0 w-36 rounded-xl border-2 text-left transition-all hover:shadow-md ${
                                selectedProduct?.cache_id === p.cache_id
                                  ? 'border-red-500 shadow-md bg-red-50'
                                  : 'border-apple-gray-200 bg-white hover:border-red-300'
                              }`}
                            >
                              <button
                                type="button"
                                onClick={() => handleSelectProduct(p)}
                                className="block w-full text-left rounded-t-xl"
                              >
                                {p.image_url ? (
                                  <img src={p.image_url} alt={p.name} className="w-full h-24 object-contain rounded-t-xl bg-white p-2" />
                                ) : (
                                  <div className="w-full h-24 rounded-t-xl bg-apple-gray-100 flex items-center justify-center">
                                    <ShoppingBasket className="w-8 h-8 text-apple-gray-300" />
                                  </div>
                                )}
                                <div className="p-2 pb-1.5">
                                  <p className="text-[11px] font-semibold text-black leading-tight line-clamp-2">{p.name}</p>
                                  {p.category && <p className="text-[10px] text-apple-gray-500 mt-0.5 truncate">{p.category}</p>}
                                  {p.packaging && <p className="text-[10px] text-apple-gray-400 mt-0.5 truncate">{p.packaging}</p>}
                                  {p.price_text && <p className="text-[11px] font-bold text-red-600 mt-1">{p.price_text}</p>}
                                </div>
                              </button>
                              <div className="px-2 pb-2">
                                <AddToCartButton
                                  store={selectedStore}
                                  product={p}
                                  className="w-full px-2 py-1.5 text-[11px]"
                                />
                              </div>
                            </div>
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
                          {storeLabelFor(selectedProduct.store)} sélectionné
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
                    <div className="flex flex-col gap-3 sm:flex-row">
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
                <div className="rounded-[28px] border border-white/60 bg-white/80 py-16 text-center shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl">
                  <ShoppingBasket className="w-12 h-12 text-apple-gray-300 mx-auto mb-3" />
                  <p className="text-apple-gray-500 text-sm">Liste vide</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {/* Unchecked groups */}
                  {uncheckedGroups.map(([category, groupItems]) => (
                    <div key={category} className="overflow-hidden rounded-[28px] border border-white/60 bg-white/80 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl">
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
                            <GroceryRow key={item.id} item={item} onToggle={toggleCheck} onDelete={deleteItem} onUpdate={updateItem} />
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
                            <GroceryRow key={item.id} item={item} onToggle={toggleCheck} onDelete={deleteItem} onUpdate={updateItem} />
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
                  store={selectedStore}
                  searchGateBlocked={searchGateBlocked}
                  searchGateMessage={searchGateMessage}
                  mapping={pantryMappings[mappingTarget.id] ?? null}
                  query={mappingQuery}
                  setQuery={setMappingQuery}
                  promotionsOnly={promotionsOnly}
                  setPromotionsOnly={setPromotionsOnly}
                  supportsPromotions={supportsPromotions}
                  searchResults={searchResults}
                  searchLoading={searchLoading}
                  searchError={searchError}
                  onSearch={async () => {
                    if (mappingQuery.trim()) {
                      await searchSupermarket(selectedStore, mappingQuery.trim(), { promotionsOnly });
                    }
                  }}
                  onClose={() => {
                    setMappingTarget(null);
                    setMappingQuery('');
                    clearSearchResults();
                  }}
                  onLink={async (product) => {
                    await updatePantryItem(mappingTarget.id, {
                      cache_id: product.cache_id,
                      image_url: product.image_url ?? null,
                      store_label: storeLabelFor(product.store),
                      external_id: product.external_id ?? null,
                      packaging: product.packaging ?? null,
                      price_text: product.price_text ?? null,
                      product_url: product.product_url ?? null,
                    });
                    await savePantryMapping(mappingTarget.id, product);
                  }}
                  onUnlink={async (mappingId) => {
                    await deleteMapping(mappingId);
                  }}
                  canRefresh={mappingQueryHasCache}
                  onRefresh={async () => {
                    if (mappingQuery.trim()) {
                      await searchSupermarket(selectedStore, mappingQuery.trim(), { forceRefresh: true, promotionsOnly });
                    }
                  }}
                />
              )}

              {/* Overview stats */}
              {pantryOverview && (
                <div className="grid grid-cols-3 gap-2 sm:gap-3">
                  {[
                    { label: 'Total articles', value: pantryOverview.total_items, color: 'text-black' },
                    { label: 'Stock faible', value: pantryOverview.low_stock_items, color: pantryOverview.low_stock_items > 0 ? 'text-amber-600' : 'text-black' },
                    { label: 'Bientôt périmé', value: pantryOverview.expiring_within_7_days, color: pantryOverview.expiring_within_7_days > 0 ? 'text-red-500' : 'text-black' },
                  ].map(({ label, value, color }) => (
                    <div key={label} className="rounded-[24px] border border-white/60 bg-white/80 p-3 shadow-[0_12px_40px_rgba(15,23,42,0.08)] backdrop-blur-xl sm:p-4">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-apple-gray-500 sm:text-xs sm:tracking-wider">{label}</p>
                      <p className={`mt-1 text-xl font-bold sm:text-2xl ${color}`}>{value}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Toolbar */}
              <div className="flex items-center gap-3">
                <button
                  onClick={handleTogglePantryForm}
                  className="flex items-center gap-2 rounded-2xl bg-apple-blue px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-blue-600"
                >
                  <Plus className="w-4 h-4" />
                  Ajouter
                </button>
              </div>

              {/* Add pantry form */}
              {showPantryForm && (
                <form onSubmit={handleAddPantry} className="rounded-[28px] border border-white/60 bg-white/80 p-5 space-y-4 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl">
                  <div className="space-y-4 border-b border-apple-gray-100 pb-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <Store className="w-4 h-4 text-red-600" />
                        <span className="text-xs font-bold uppercase tracking-wider text-red-600">Choisir un produit sur {currentStoreLabel}</span>
                      </div>
                      <StoreSelector selected={selectedStore} onChange={setSelectedStore} connections={connections} />
                    </div>
                    <ConnectionStrip
                      store={selectedStore}
                      connections={connections}
                      onActivate={activateConnection}
                      onDelete={deleteConnection}
                    />
                    {selectedStore === 'auchan' && <AuchanStorePicker />}
                    <div className="flex flex-col gap-2 sm:flex-row">
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
                              if (pantrySearchQuery.trim() && !searchGateBlocked) {
                                void searchSupermarket(selectedStore, pantrySearchQuery.trim(), { promotionsOnly });
                              }
                            }
                          }}
                          className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-apple-gray-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-red-400/40"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          if (pantrySearchQuery.trim() && !searchGateBlocked) {
                            void searchSupermarket(selectedStore, pantrySearchQuery.trim(), { promotionsOnly });
                          }
                        }}
                        disabled={searchLoading || !pantrySearchQuery.trim() || searchGateBlocked}
                        className="flex items-center gap-2 px-4 py-2.5 bg-red-600 text-white text-sm font-semibold rounded-xl hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        {searchLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                        {searchLoading ? 'Scraping…' : 'Rechercher'}
                      </button>
                      {pantrySearchQueryHasCache && (
                        <button
                          type="button"
                          onClick={() => {
                            if (pantrySearchQuery.trim() && !searchGateBlocked) {
                              void searchSupermarket(selectedStore, pantrySearchQuery.trim(), { forceRefresh: true, promotionsOnly });
                            }
                          }}
                          disabled={searchLoading || !pantrySearchQuery.trim() || searchGateBlocked}
                          className="px-4 py-2.5 border border-red-200 text-red-600 text-sm font-semibold rounded-xl hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          Actualiser
                        </button>
                      )}
                    </div>

                    {searchGateBlocked && (
                      <p className="flex items-center gap-1.5 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                        <Lock className="w-3 h-3 shrink-0" />
                        {searchGateMessage}
                      </p>
                    )}

                    {supportsPromotions && (
                      <label className="flex items-center gap-2 text-sm text-apple-gray-600">
                        <input
                          type="checkbox"
                          checked={promotionsOnly}
                          onChange={(e) => setPromotionsOnly(e.target.checked)}
                          className="h-4 w-4 rounded border-apple-gray-300 text-red-600 focus:ring-red-400"
                        />
                        Promotions uniquement
                      </label>
                    )}

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
                            <div
                              key={product.cache_id}
                              className={`flex flex-col flex-shrink-0 w-40 rounded-xl border-2 text-left transition-all hover:shadow-md ${
                                selectedPantryProduct?.cache_id === product.cache_id
                                  ? 'border-red-500 shadow-md bg-red-50'
                                  : 'border-apple-gray-200 bg-white hover:border-red-300'
                              }`}
                            >
                              <button
                                type="button"
                                onClick={() => handleSelectPantryProduct(product)}
                                className="block w-full text-left rounded-t-xl"
                              >
                                {product.image_url ? (
                                  <img src={product.image_url} alt={product.name} className="w-full h-24 object-contain rounded-t-xl bg-white p-2" />
                                ) : (
                                  <div className="w-full h-24 rounded-t-xl bg-apple-gray-100 flex items-center justify-center">
                                    <Package className="w-8 h-8 text-apple-gray-300" />
                                  </div>
                                )}
                                <div className="p-2 pb-1.5">
                                  <p className="text-[11px] font-semibold text-black leading-tight line-clamp-2">{product.name}</p>
                                  {product.category && <p className="text-[10px] text-apple-gray-500 mt-0.5 truncate">{product.category}</p>}
                                  {product.packaging && <p className="text-[10px] text-apple-gray-400 mt-0.5 truncate">{product.packaging}</p>}
                                  {product.price_text && <p className="text-[11px] font-bold text-red-600 mt-1">{product.price_text}</p>}
                                </div>
                              </button>
                              <div className="px-2 pb-2">
                                <AddToCartButton
                                  store={selectedStore}
                                  product={product}
                                  className="w-full px-2 py-1.5 text-[11px]"
                                />
                              </div>
                            </div>
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
                  <div className="grid gap-3 sm:grid-cols-2">
                    <input type="text" placeholder="Nom" value={pName} onChange={(e) => setPName(e.target.value)} required autoFocus className={`sm:col-span-2 ${inputCls}`} />
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
                  <div className="flex flex-col gap-3 sm:flex-row">
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
                <div className="rounded-[28px] border border-white/60 bg-white/80 py-16 text-center shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl">
                  <Package className="w-12 h-12 text-apple-gray-300 mx-auto mb-3" />
                  <p className="text-apple-gray-500 text-sm">Garde-manger vide</p>
                </div>
              ) : (
                <div className="overflow-hidden rounded-[28px] border border-white/60 bg-white/80 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl">
                  {pantryGroups.map(([category, groupItems]) => (
                    <div key={category} className="border-b border-apple-gray-100 last:border-b-0">
                      <button
                        onClick={() => toggleGroup(`pantry-${category}`)}
                        className="flex w-full items-center gap-3 bg-apple-gray-50 px-4 py-3 text-left transition-colors hover:bg-apple-gray-100"
                      >
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/80">
                          <div className="h-2.5 w-2.5 rounded-full" style={{ background: getCategoryColor(groupItems[0].category) }} />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-apple-gray-400">Rayon</p>
                          <p className="mt-1 text-sm font-semibold leading-5 text-black">{formatCategoryLabel(category)}</p>
                        </div>
                        <span className="shrink-0 rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-apple-gray-500">{groupItems.length}</span>
                        {collapsedGroups.has(`pantry-${category}`) ? <ChevronRight className="w-3.5 h-3.5 text-apple-gray-400" /> : <ChevronDown className="w-3.5 h-3.5 text-apple-gray-400" />}
                      </button>
                      {!collapsedGroups.has(`pantry-${category}`) && (
                        <div className="divide-y divide-apple-gray-50">
                          {groupItems.map((item) => (
                            <PantryRow
                              key={item.id}
                              item={item}
                              onDelete={handleDeletePantry}
                              onConsume={handleConsumePantry}
                              onUpdate={handleUpdatePantry}
                              onRestock={handleAddLowStockToGroceries}
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

          {/* ── CART (PANIER) ───────────────────────────────────────────── */}
          {activeTab === 'Panier' && (
            <>
              {/* Store selector + status badge */}
              <div className="rounded-[28px] border border-white/60 bg-white/80 p-4 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl sm:p-5">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-2">
                    <ShoppingCart className="w-4 h-4 text-red-600" />
                    <span className="text-xs font-bold uppercase tracking-wider text-red-600">Panier {currentStoreLabel}</span>
                  </div>
                  <StoreSelector selected={selectedStore} onChange={setSelectedStore} connections={connections} />
                </div>
                {currentCart && (
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    {currentCart.status === 'validated' ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
                        <Check className="w-3 h-3" />
                        Validé
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] font-semibold text-amber-700">
                        Brouillon
                      </span>
                    )}
                    {currentCart.validated_at && (
                      <span className="text-[11px] text-apple-gray-500">
                        Validé le {format(parseISO(currentCart.validated_at), 'dd/MM/yyyy • HH:mm')}
                      </span>
                    )}
                  </div>
                )}
                {cartError && (
                  <p className="mt-2 text-xs text-red-500">❌ {cartError}</p>
                )}
              </div>

              {/* Cart items */}
              {cartLoading && cartItems.length === 0 ? (
                <div className="flex items-center justify-center py-16">
                  <div className="w-8 h-8 border-2 border-apple-blue/30 border-t-apple-blue rounded-full animate-spin" />
                </div>
              ) : filteredCartItems.length === 0 ? (
                <div className="rounded-[28px] border border-white/60 bg-white/80 py-16 text-center shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl">
                  <ShoppingCart className="w-12 h-12 text-apple-gray-300 mx-auto mb-3" />
                  <p className="text-apple-gray-500 text-sm">
                    {cartItems.length === 0
                      ? `Panier ${currentStoreLabel} vide`
                      : 'Aucun article ne correspond à la recherche'}
                  </p>
                  {cartItems.length === 0 && (
                    <p className="mt-1 text-xs text-apple-gray-400">
                      Ajoute des produits depuis la recherche avec « + Panier ».
                    </p>
                  )}
                </div>
              ) : (
                <>
                  <div className="overflow-hidden rounded-[28px] border border-white/60 bg-white/80 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl">
                    <div className="divide-y divide-apple-gray-50">
                      {filteredCartItems.map((item) => (
                        <CartItemRow
                          key={item.id}
                          item={item}
                          onUpdateQuantity={(itemId, quantity) => void updateCartItemQuantity(selectedStore, itemId, quantity)}
                          onRemove={(itemId) => void removeCartItem(selectedStore, itemId)}
                        />
                      ))}
                    </div>
                  </div>

                  {/* Total */}
                  <div className="flex items-center justify-between rounded-[24px] border border-white/60 bg-white/80 px-5 py-4 shadow-[0_12px_40px_rgba(15,23,42,0.08)] backdrop-blur-xl">
                    <span className="text-sm font-semibold text-apple-gray-500">
                      Total ({filteredCartItems.length} article{filteredCartItems.length > 1 ? 's' : ''})
                    </span>
                    <span className="text-lg font-bold text-black">
                      {pricedCartItemCount > 0 ? formatCartPrice(cartTotal) : '—'}
                    </span>
                  </div>

                  {/* Actions */}
                  <div className="flex flex-col gap-3 sm:flex-row">
                    {currentCart?.status === 'validated' ? (
                      <button
                        onClick={() => handleSetCartStatus('draft')}
                        disabled={cartLoading}
                        className="flex flex-1 items-center justify-center gap-2 rounded-2xl border border-apple-blue/30 bg-apple-blue/10 px-5 py-2.5 text-sm font-semibold text-apple-blue transition-colors hover:bg-apple-blue/20 disabled:opacity-50"
                      >
                        <Pencil className="w-4 h-4" />
                        Repasser en brouillon
                      </button>
                    ) : (
                      <button
                        onClick={() => handleSetCartStatus('validated')}
                        disabled={cartLoading || cartItems.length === 0}
                        className="flex flex-1 items-center justify-center gap-2 rounded-2xl bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <Check className="w-4 h-4" />
                        Valider
                      </button>
                    )}
                    <button
                      onClick={handleClearCart}
                      disabled={cartLoading || cartItems.length === 0}
                      className="flex items-center justify-center gap-2 rounded-2xl border border-red-200 px-5 py-2.5 text-sm font-medium text-red-500 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <Trash2 className="w-4 h-4" />
                      Vider
                    </button>
                  </div>
                </>
              )}
            </>
          )}

        </div>
      </div>
    </div>
  );
}

// ─── Store selector chips ────────────────────────────────────────────────────
const DIRECT_STORE_OPTIONS: { key: SupermarketStoreKey; label: string }[] = [
  { key: 'intermarche', label: 'Intermarché' },
  { key: 'carrefour',   label: 'Carrefour'   },
  { key: 'leclerc',     label: 'Leclerc'     },
  { key: 'auchan',      label: 'Auchan'      },
];

function StoreSelector({
  selected,
  onChange,
  connections,
}: {
  selected: SupermarketStoreKey;
  onChange: (store: SupermarketStoreKey) => void;
  connections: SupermarketConnection[];
}) {
  const requiresStoreSelection = STORE_CAPABILITIES[selected].requires_store_selection;
  const hasConnection = (store: SupermarketStoreKey) => connections.some((c) => c.store === store);
  const accountRequired = (store: SupermarketStoreKey) => ACCOUNT_REQUIRED_STORES.includes(store) && !hasConnection(store);
  return (
    <div className="flex flex-wrap items-center gap-2">
      {DIRECT_STORE_OPTIONS.length > 1 && (
        <div className="inline-flex items-center rounded-full border border-apple-gray-200 bg-white p-0.5">
          {DIRECT_STORE_OPTIONS.map((opt) => (
            <button
              key={opt.key}
              type="button"
              onClick={() => onChange(opt.key)}
              className={`flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold rounded-full transition-colors ${
                selected === opt.key
                  ? 'bg-red-600 text-white'
                  : 'text-apple-gray-500 hover:text-apple-gray-700'
              }`}
            >
              {opt.label}
              {accountRequired(opt.key) && (
                <Lock
                  className={selected === opt.key ? 'w-2.5 h-2.5 text-white/80' : 'w-2.5 h-2.5 text-apple-gray-400'}
                  aria-label={selected === opt.key ? 'Compte requis pour cette enseigne' : 'Compte requis'}
                />
              )}
            </button>
          ))}
        </div>
      )}
      {requiresStoreSelection && (
        <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200 px-2.5 py-1 text-[11px] font-semibold text-amber-700">
          <Store className="w-3 h-3" />
          magasin requis
        </span>
      )}
    </div>
  );
}

// ─── Connections strip (per-store cookie account picker) ───────────────────
function ConnectionStrip({
  store,
  connections,
  onActivate,
  onDelete,
}: {
  store: SupermarketStoreKey;
  connections: SupermarketConnection[];
  onActivate: (id: number) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
}) {
  const storeConnections = connections.filter((c) => c.store === store);
  if (storeConnections.length === 0) {
    return (
      <p className="mb-3 text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
        Aucun compte {STORE_LABELS[store]} branché. Installe l'extension <strong>AdamHUB Connect</strong> et clique sur « Connecter » dans sa popup.
      </p>
    );
  }

  const active = storeConnections.find((c) => c.is_active) ?? storeConnections[0];
  const others = storeConnections.filter((c) => c.id !== active.id);

  return (
    <div className="mb-3 flex flex-wrap items-center gap-2 text-[11px] text-apple-gray-600">
      <span className="font-semibold text-apple-gray-500">Compte :</span>
      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-1 text-emerald-700 font-semibold">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
        {active.label}
      </span>
      {others.map((c) => (
        <button
          key={c.id}
          type="button"
          onClick={() => void onActivate(c.id)}
          title={`Basculer sur ${c.label}`}
          className="inline-flex items-center gap-1 rounded-full bg-white border border-apple-gray-200 px-2.5 py-1 text-apple-gray-600 hover:border-emerald-300 hover:text-emerald-700"
        >
          ↪ {c.label}
        </button>
      ))}
      {storeConnections.length > 0 && (
        <button
          type="button"
          onClick={() => {
            if (window.confirm(`Supprimer la connexion « ${active.label} » ?`)) {
              void onDelete(active.id);
            }
          }}
          className="ml-auto text-apple-gray-400 hover:text-red-500"
          title="Supprimer la connexion active"
        >
          ✕
        </button>
      )}
    </div>
  );
}

// ─── Auchan store picker (no-login store selection flow) ────────────────
// Renders a compact zipcode/ville form once, lists the offering contexts from
// GET /supermarket/auchan/offering-contexts, and POSTs the chosen store.
// When a store is already selected it becomes a badge with a "change store"
// action. Used wherever a search can run on Auchan.
function AuchanStorePicker() {
  const {
    auchanContexts,
    auchanSelectedStore,
    auchanLoading,
    auchanError,
    fetchAuchanOfferingContexts,
    selectAuchanStore,
    clearAuchanStore,
  } = useGroceryStore();

  const [zipcode, setZipcode] = useState('');
  const [city, setCity] = useState('');
  const [manualLat, setManualLat] = useState('');
  const [manualLng, setManualLng] = useState('');
  const [showCoords, setShowCoords] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  if (auchanSelectedStore) {
    return (
      <div className="mb-3 flex flex-wrap items-center gap-2 text-[11px] text-apple-gray-600">
        <span className="font-semibold text-apple-gray-500">Magasin :</span>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-1 text-emerald-700 font-semibold">
          <Store className="w-3 h-3" />
          {auchanSelectedStore.store_label}
        </span>
        {auchanSelectedStore.location_label && (
          <span className="text-apple-gray-500">{auchanSelectedStore.location_label}</span>
        )}
        <button
          type="button"
          onClick={() => clearAuchanStore()}
          className="rounded-full bg-white border border-apple-gray-200 px-2.5 py-1 text-apple-gray-600 hover:border-red-300 hover:text-red-600"
        >
          Changer de magasin
        </button>
      </div>
    );
  }

  const handleLookup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!zipcode.trim() || !city.trim()) {
      setLocalError('Renseigne le code postal et la ville.');
      return;
    }
    setLocalError(null);
    const manualLatValue = parseFloat(manualLat);
    const manualLngValue = parseFloat(manualLng);
    let lat: number | null = null;
    let lng: number | null = null;
    if (manualLat.trim() && manualLng.trim()) {
      lat = Number.isNaN(manualLatValue) ? null : manualLatValue;
      lng = Number.isNaN(manualLngValue) ? null : manualLngValue;
    } else {
      const geocoded = await geocodeFrance(zipcode, city);
      if (geocoded) {
        lat = geocoded.lat;
        lng = geocoded.lng;
      }
    }
    if (lat === null || lng === null) {
      setLocalError('Impossible de géolocaliser ce code postal / ville. Renseigne la latitude et la longitude manuellement.');
      return;
    }
    await fetchAuchanOfferingContexts(zipcode.trim(), city.trim(), lat, lng);
  };

  const selectableContexts = auchanContexts.filter((ctx) => Boolean(ctx.seller_id) && Boolean(ctx.store_reference));

  return (
    <div className="mb-3">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-apple-gray-500">
        Choisir un magasin Auchan
      </p>
      <form onSubmit={(e) => void handleLookup(e)} className="flex flex-col gap-2">
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            type="text"
            value={zipcode}
            onChange={(e) => setZipcode(e.target.value)}
            placeholder="Code postal"
            inputMode="numeric"
            className="w-full rounded-xl border border-apple-gray-200 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-apple-blue/40 sm:w-32"
          />
          <input
            type="text"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            placeholder="Ville"
            className="w-full flex-1 rounded-xl border border-apple-gray-200 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-apple-blue/40"
          />
          <button
            type="submit"
            disabled={auchanLoading || !zipcode.trim() || !city.trim()}
            className="flex items-center justify-center gap-2 rounded-xl bg-apple-blue px-4 py-2 text-sm font-semibold text-white hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {auchanLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Store className="w-3.5 h-3.5" />}
            Choisir un magasin
          </button>
        </div>
        <button
          type="button"
          onClick={() => setShowCoords((value) => !value)}
          className="self-start text-[11px] text-apple-gray-400 hover:text-apple-gray-600"
        >
          {showCoords ? 'Masquer' : 'Afficher'} latitude / longitude (optionnel)
        </button>
        {showCoords && (
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              type="number"
              value={manualLat}
              onChange={(e) => setManualLat(e.target.value)}
              placeholder="Latitude"
              step="any"
              className="w-full rounded-xl border border-apple-gray-200 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-apple-blue/40 sm:w-1/2"
            />
            <input
              type="number"
              value={manualLng}
              onChange={(e) => setManualLng(e.target.value)}
              placeholder="Longitude"
              step="any"
              className="w-full rounded-xl border border-apple-gray-200 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-apple-blue/40 sm:w-1/2"
            />
          </div>
        )}
      </form>

      {localError && <p className="mt-2 text-xs text-red-500">❌ {localError}</p>}
      {auchanError && <p className="mt-2 text-xs text-red-500">❌ {auchanError}</p>}

      {!auchanLoading && selectableContexts.length > 0 && (
        <div className="mt-3">
          <p className="mb-2 text-xs text-apple-gray-400">{selectableContexts.length} magasin(s) — clique pour sélectionner</p>
          <div className="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1">
            {selectableContexts.map((ctx) => (
              <button
                key={ctx.seller_id}
                type="button"
                onClick={() => void selectAuchanStore({
                  seller_id: ctx.seller_id,
                  store_reference: ctx.store_reference ?? '',
                  channel: ctx.channel ?? 'PICK_UP',
                  store_label: ctx.name ?? ctx.seller_id,
                  location_label: [ctx.name, ctx.address].filter(Boolean).join(' — ') || null,
                  zipcode: zipcode.trim() || null,
                  city: city.trim() || null,
                  country: 'France',
                  latitude: manualLat.trim() ? parseFloat(manualLat) : null,
                  longitude: manualLng.trim() ? parseFloat(manualLng) : null,
                })}
                disabled={auchanLoading}
                className="flex-shrink-0 w-52 rounded-xl border border-apple-gray-200 bg-white p-3 text-left transition-colors hover:border-emerald-300 disabled:opacity-50"
              >
                <p className="text-[11px] font-semibold text-black">{ctx.name ?? ctx.seller_id}</p>
                {ctx.address && <p className="mt-0.5 text-[10px] text-apple-gray-500">{ctx.address}</p>}
                {ctx.distance && <p className="mt-0.5 text-[10px] font-semibold text-emerald-600">{ctx.distance}</p>}
              </button>
            ))}
          </div>
        </div>
      )}

      {!auchanLoading && !auchanError && auchanContexts.length > 0 && selectableContexts.length === 0 && (
        <p className="mt-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          Aucun magasin sélectionnable pour cette adresse.
        </p>
      )}
    </div>
  );
}

