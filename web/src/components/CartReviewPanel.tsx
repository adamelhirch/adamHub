import React, { useState } from "react";
import {
  CheckCircle2,
  Edit2,
  Loader2,
  RotateCcw,
  ShoppingCart,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import axios from "axios";
import { api } from "../lib/api";
import type {
  ConfirmPickupResponse,
  GroceryToCartJobRead,
  MatchedCartItemRead,
  SyncJobResponse,
} from "../types/supermarket";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  job: GroceryToCartJobRead | null;
  onUpdateJob: (job: GroceryToCartJobRead) => void;
  onPickupConfirmed?: () => void;
}

export const CartReviewPanel: React.FC<Props> = ({
  isOpen,
  onClose,
  job,
  onUpdateJob,
  onPickupConfirmed,
}) => {
  const [editingItemId, setEditingItemId] = useState<number | null>(null);
  const [customNote, setCustomNote] = useState<string>("");
  const [refining, setRefining] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  if (!isOpen || !job) return null;

  const activeItems = job.items.filter((i) => i.status !== "removed");
  const removedItems = job.items.filter((i) => i.status === "removed");
  const itemsToModify = job.items.filter((i) => i.status === "to_modify");
  const isSynced = job.status === "synced";
  const isCompleted = job.status === "completed";

  const handleUpdateItemStatus = async (
    itemId: number,
    status: "staged" | "to_modify" | "removed",
    note?: string
  ) => {
    try {
      const res = await api.patch<MatchedCartItemRead>(
        `/supermarket/cart/jobs/${job.id}/items/${itemId}`,
        {
          status,
          custom_note: note !== undefined ? note : undefined,
        }
      );

      const updatedItems = job.items.map((it) => (it.id === itemId ? res.data : it));
      const newTotal = updatedItems
        .filter((it) => it.status !== "removed")
        .reduce((acc, it) => acc + it.total_price_cents, 0);

      onUpdateJob({
        ...job,
        items: updatedItems,
        estimated_total_cents: newTotal,
      });
      setEditingItemId(null);
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err) && err.response?.data?.detail
        ? err.response.data.detail
        : "Impossible de modifier cet article.";
      setStatusMessage({ text: msg, type: "error" });
    }
  };

  const handleAcceptSubstitute = async (itemId: number, substituteId: number) => {
    try {
      const res = await api.post<GroceryToCartJobRead>(
        `/supermarket/cart/jobs/${job.id}/refine`,
        {
          adjustments: [
            {
              matched_item_id: itemId,
              action: "accept_substitute",
              substitute_id: substituteId,
            },
          ],
        }
      );
      onUpdateJob(res.data);
      setStatusMessage({ text: "Alternative acceptée.", type: "success" });
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err) && err.response?.data?.detail
        ? err.response.data.detail
        : "Impossible d'appliquer l'alternative.";
      setStatusMessage({ text: msg, type: "error" });
    }
  };

  const handleRefineBatch = async () => {
    setRefining(true);
    setStatusMessage(null);
    try {
      const res = await api.post<GroceryToCartJobRead>(
        `/supermarket/cart/jobs/${job.id}/refine`,
        { adjustments: [] }
      );
      onUpdateJob(res.data);
      setStatusMessage({ text: "Panier réajusté avec succès.", type: "success" });
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err) && err.response?.data?.detail
        ? err.response.data.detail
        : "Erreur lors de la mise à jour.";
      setStatusMessage({ text: msg, type: "error" });
    } finally {
      setRefining(false);
    }
  };

  const handleSyncRemote = async () => {
    setSyncing(true);
    setStatusMessage(null);
    try {
      const res = await api.post<SyncJobResponse>(`/supermarket/cart/jobs/${job.id}/sync`);
      onUpdateJob({
        ...job,
        status: "synced",
        synced_at: res.data.synced_at,
      });
      setStatusMessage({ text: res.data.message, type: "success" });
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err) && err.response?.data?.detail
        ? err.response.data.detail
        : "Erreur lors de la synchronisation vers le Drive.";
      setStatusMessage({ text: msg, type: "error" });
    } finally {
      setSyncing(false);
    }
  };

  const handleConfirmPickup = async () => {
    setConfirming(true);
    setStatusMessage(null);
    try {
      const res = await api.post<ConfirmPickupResponse>(
        `/supermarket/cart/jobs/${job.id}/confirm-pickup`
      );
      onUpdateJob({
        ...job,
        status: "completed",
        completed_at: res.data.completed_at,
      });
      setStatusMessage({ text: res.data.message, type: "success" });
      if (onPickupConfirmed) onPickupConfirmed();
    } catch (err: unknown) {
      const msg = axios.isAxiosError(err) && err.response?.data?.detail
        ? err.response.data.detail
        : "Erreur lors de la confirmation du retrait.";
      setStatusMessage({ text: msg, type: "error" });
    } finally {
      setConfirming(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <div className="flex h-full max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-3xl bg-white shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-slate-900">
                Panier Drive {job.store.toUpperCase()}
              </h2>
              <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-800 uppercase">
                {job.status}
              </span>
            </div>
            <p className="text-xs text-slate-500">
              Point de retrait : {job.external_store_id} • Stratégie : {job.optimization_strategy.toUpperCase()}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Metrics Banner */}
        <div className="grid grid-cols-3 border-b border-slate-100 bg-slate-50/75 px-6 py-3">
          <div>
            <span className="text-[11px] font-medium text-slate-500">Total estimé</span>
            <p className="text-base font-bold text-slate-900">
              {(job.estimated_total_cents / 100).toFixed(2)} €
            </p>
          </div>
          <div>
            <span className="text-[11px] font-medium text-slate-500">Articles actifs</span>
            <p className="text-base font-bold text-slate-900">
              {activeItems.length} / {job.items_count}
            </p>
          </div>
          <div>
            <span className="text-[11px] font-medium text-slate-500">Correspondances</span>
            <p className="text-base font-bold text-slate-900">
              {job.matched_count} SKUs
            </p>
          </div>
        </div>

        {/* Status message */}
        {statusMessage && (
          <div
            className={`mx-6 mt-3 rounded-xl p-3 text-xs font-medium ${
              statusMessage.type === "success"
                ? "bg-emerald-50 text-emerald-700"
                : "bg-red-50 text-red-700"
            }`}
          >
            {statusMessage.text}
          </div>
        )}

        {/* Refine banner if items to modify */}
        {itemsToModify.length > 0 && (
          <div className="mx-6 mt-3 flex items-center justify-between rounded-2xl border border-amber-200 bg-amber-50 p-3.5">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-600" />
              <span className="text-xs font-medium text-amber-800">
                {itemsToModify.length} consigne(s) personnalisée(s) en attente.
              </span>
            </div>
            <button
              onClick={handleRefineBatch}
              disabled={refining}
              className="flex items-center gap-1.5 rounded-xl bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-700 disabled:opacity-50"
            >
              {refining ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
              Réajuster par l'IA
            </button>
          </div>
        )}

        {/* Content list */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
          {activeItems.map((item) => (
            <div
              key={item.id}
              className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-slate-300"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-sm text-slate-900">{item.name}</span>
                    {item.match_type === "substitute" && (
                      <span className="rounded-md bg-purple-100 px-2 py-0.5 text-[10px] font-bold text-purple-700">
                        Substitut
                      </span>
                    )}
                    {item.status === "to_modify" && (
                      <span className="rounded-md bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-800">
                        À modifier
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {item.brand ? `${item.brand} • ` : ""}
                    {item.packaging || ""}
                  </p>

                  {item.custom_note && (
                    <p className="mt-1.5 text-xs italic text-amber-700">
                      Consigne : « {item.custom_note} »
                    </p>
                  )}

                  {/* Proposed substitute */}
                  {item.substitute_proposal && item.substitute_proposal.status === "pending" && (
                    <div className="mt-2.5 rounded-xl border border-purple-200 bg-purple-50/75 p-2.5">
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="text-[11px] font-bold text-purple-900 uppercase">
                            Alternative suggérée :
                          </span>
                          <p className="text-xs font-semibold text-slate-800">
                            {item.substitute_proposal.alternative_name}
                          </p>
                          <p className="text-[11px] text-slate-500">
                            {item.substitute_proposal.reason} ({(item.substitute_proposal.alternative_unit_price_cents / 100).toFixed(2)} €)
                          </p>
                        </div>
                        <button
                          onClick={() => handleAcceptSubstitute(item.id, item.substitute_proposal!.id)}
                          className="rounded-xl bg-purple-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-purple-700"
                        >
                          Accepter
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                <div className="text-right">
                  <span className="text-sm font-bold text-slate-900">
                    {(item.total_price_cents / 100).toFixed(2)} €
                  </span>
                  <p className="text-xs text-slate-400">
                    {item.quantity} × {(item.unit_price_cents / 100).toFixed(2)} €
                  </p>
                  <div className="mt-2 flex items-center justify-end gap-1">
                    <button
                      onClick={() => {
                        setEditingItemId(item.id);
                        setCustomNote(item.custom_note || "");
                      }}
                      title="Modifier la consigne"
                      className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleUpdateItemStatus(item.id, "removed")}
                      title="Retirer du panier"
                      className="rounded-lg p-1 text-slate-400 hover:bg-red-50 hover:text-red-500"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>

              {/* Inline custom note editor */}
              {editingItemId === item.id && (
                <div className="mt-3 border-t border-slate-100 pt-3">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={customNote}
                      onChange={(e) => setCustomNote(e.target.value)}
                      placeholder="Ex : Marque distributeur, bio, moins cher…"
                      className="flex-1 rounded-xl border border-slate-200 px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500"
                    />
                    <button
                      onClick={() => handleUpdateItemStatus(item.id, "to_modify", customNote)}
                      className="rounded-xl bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700"
                    >
                      Enregistrer
                    </button>
                    <button
                      onClick={() => setEditingItemId(null)}
                      className="rounded-xl border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
                    >
                      Annuler
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Removed items section */}
          {removedItems.length > 0 && (
            <div className="mt-6 border-t border-slate-200 pt-4">
              <h3 className="mb-2 text-xs font-bold text-slate-400 uppercase tracking-wider">
                Articles retirés ({removedItems.length})
              </h3>
              <div className="space-y-2">
                {removedItems.map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center justify-between rounded-xl bg-slate-50 p-3 opacity-60"
                  >
                    <div>
                      <span className="text-xs line-through text-slate-600">{item.name}</span>
                      <p className="text-[10px] text-slate-400">
                        {(item.total_price_cents / 100).toFixed(2)} €
                      </p>
                    </div>
                    <button
                      onClick={() => handleUpdateItemStatus(item.id, "staged")}
                      className="flex items-center gap-1 rounded-lg border border-slate-200 px-2 py-1 text-xs text-slate-600 hover:bg-white"
                    >
                      <RotateCcw className="w-3 h-3" />
                      Restaurer
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-slate-100 bg-white p-4">
          {isSynced ? (
            <button
              onClick={handleConfirmPickup}
              disabled={confirming || isCompleted}
              className="flex w-full items-center justify-center gap-2 rounded-2xl bg-blue-600 py-3 text-sm font-bold text-white shadow-md transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {confirming ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <CheckCircle2 className="w-4 h-4" />
              )}
              {isCompleted ? "Retrait déjà confirmé" : "Confirmer le retrait (Garde-manger)"}
            </button>
          ) : (
            <button
              onClick={handleSyncRemote}
              disabled={syncing || activeItems.length === 0}
              className="flex w-full items-center justify-center gap-2 rounded-2xl bg-emerald-600 py-3 text-sm font-bold text-white shadow-md transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {syncing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <ShoppingCart className="w-4 h-4" />
              )}
              Synchroniser vers mon Drive
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
