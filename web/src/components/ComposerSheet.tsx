import { type ReactNode } from "react";
import { X } from "lucide-react";

type ComposerSheetProps = {
  open: boolean;
  title: string;
  subtitle?: string;
  eyebrow?: string;
  onClose: () => void;
  children: ReactNode;
  panelClassName?: string;
};

export default function ComposerSheet({
  open,
  title,
  subtitle,
  eyebrow,
  onClose,
  children,
  panelClassName = "",
}: ComposerSheetProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center bg-black/40 p-0 backdrop-blur-sm md:items-center md:p-4">
      <div
        className={`flex max-h-[92vh] w-full flex-col overflow-hidden bg-white shadow-2xl md:rounded-[32px] md:max-w-5xl ${panelClassName}`}
      >
        <div className="flex shrink-0 items-start justify-between gap-3 border-b border-apple-gray-200 bg-white/95 px-4 py-4 backdrop-blur md:px-6 md:py-5">
          <div className="min-w-0">
            {eyebrow && (
              <p className="text-[10px] font-bold uppercase tracking-[0.28em] text-apple-gray-500">
                {eyebrow}
              </p>
            )}
            <h2 className="mt-1 text-lg font-semibold tracking-tight text-black md:text-xl">
              {title}
            </h2>
            {subtitle && (
              <p className="mt-1 text-sm text-apple-gray-500">{subtitle}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-2 text-apple-gray-500 transition-colors hover:bg-apple-gray-100 hover:text-black"
            aria-label="Fermer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 pb-[calc(env(safe-area-inset-bottom)+6.5rem)] md:pb-6 md:px-6 md:py-6">
          {children}
        </div>
      </div>
    </div>
  );
}
