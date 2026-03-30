import { useDraggable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import { BadgeCheck, CalendarClock, Clock3 } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export type CalendarTimelineItem = {
  id: number;
  title: string;
  description: string | null;
  start_at: string;
  end_at: string;
  all_day: boolean;
  category: string;
  source:
    | 'manual'
    | 'task'
    | 'habit'
    | 'event'
    | 'subscription'
    | 'meal_plan'
    | 'fitness_session';
  source_ref_id: number | null;
  generated: boolean;
  completed: boolean;
  notification_enabled: boolean;
  reminder_offsets_min: number[];
  extra_data: Record<string, unknown>;
  last_notified_at: string | null;
  created_at: string;
  updated_at: string;
};

interface Props {
  item: CalendarTimelineItem;
  isOverlay?: boolean;
  compactMobile?: boolean;
}

function getSourceMeta(item: CalendarTimelineItem) {
  switch (item.source) {
    case 'meal_plan':
      return {
        label: 'Repas',
        tone: 'bg-orange-50 text-orange-800 border-orange-200',
        accent: 'bg-orange-500',
      };
    case 'fitness_session':
      return {
        label: 'Fitness',
        tone: 'bg-emerald-50 text-emerald-800 border-emerald-200',
        accent: 'bg-emerald-500',
      };
    case 'subscription':
      return {
        label: 'Abonnement',
        tone: 'bg-violet-50 text-violet-800 border-violet-200',
        accent: 'bg-violet-500',
      };
    case 'event':
      return {
        label: 'Événement',
        tone: 'bg-sky-50 text-sky-800 border-sky-200',
        accent: 'bg-sky-500',
      };
    case 'task':
      return {
        label: 'Tâche',
        tone: 'bg-apple-gray-50 text-black border-apple-gray-200',
        accent: 'bg-apple-gray-500',
      };
    case 'habit':
      return {
        label: 'Routine',
        tone: 'bg-cyan-50 text-cyan-800 border-cyan-200',
        accent: 'bg-cyan-500',
      };
    default:
      return {
        label: 'Manuel',
        tone: 'bg-slate-50 text-slate-800 border-slate-200',
        accent: 'bg-slate-500',
      };
  }
}

export default function DraggableCalendarItem({ item, isOverlay, compactMobile }: Props) {
  const isMovable = item.source !== 'habit';
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `calendar-${item.id}`,
    data: { kind: 'calendar-item' as const, item },
    disabled: !isMovable,
  });

  const style = {
    transform: CSS.Translate.toString(transform),
  };

  const meta = getSourceMeta(item);
  const startAt = new Date(item.start_at);
  const endAt = new Date(item.end_at);
  const durationMinutes = Number.isFinite(startAt.getTime()) && Number.isFinite(endAt.getTime())
    ? Math.max(15, Math.round((endAt.getTime() - startAt.getTime()) / 60000))
    : 30;

  const timeLabel = item.all_day
    ? 'Toute la journée'
    : Number.isFinite(startAt.getTime())
      ? `${item.start_at.substring(11, 16)} · ${durationMinutes}m`
      : `${durationMinutes}m`;

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className={twMerge(
        clsx(
          'flex h-full w-full flex-col overflow-hidden rounded-xl border shadow-xs ring-1 ring-black/5 transition-all backdrop-blur-md touch-none cursor-grab active:cursor-grabbing select-none',
          !isMovable && 'cursor-default active:cursor-default',
          meta.tone,
          isDragging ? 'opacity-40 scale-[0.98]' : 'opacity-100',
          isOverlay ? 'rotate-1 shadow-2xl scale-[1.03] z-50' : '',
          compactMobile ? 'p-2' : 'p-2.5'
        )
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          {item.source === 'habit' ? (
            <div className="flex items-center gap-1.5">
              <span className={`h-2.5 w-2.5 rounded-full ${meta.accent}`} />
              <p
                className={`font-semibold tracking-tight ${compactMobile ? 'text-[11px] leading-tight' : 'text-xs leading-tight'}`}
              >
                {item.title}
              </p>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-1.5">
                <span className={`h-2.5 w-2.5 rounded-full ${meta.accent}`} />
                <span className="text-[9px] font-bold uppercase tracking-[0.24em] opacity-70">{meta.label}</span>
              </div>
              <p className={`mt-1 font-semibold tracking-tight ${compactMobile ? 'text-[11px] leading-tight' : 'text-xs leading-tight'}`}>
                {item.title}
              </p>
            </>
          )}
        </div>
        {item.completed && (
          <BadgeCheck className="h-4 w-4 shrink-0 text-emerald-500" />
        )}
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2 text-[9px] font-semibold opacity-75">
        <span className="inline-flex items-center gap-1 rounded-full bg-white/60 px-2 py-1">
          <Clock3 className="h-3 w-3" />
          {timeLabel}
        </span>
        <span className="inline-flex items-center gap-1 rounded-full bg-white/60 px-2 py-1">
          <CalendarClock className="h-3 w-3" />
          {item.all_day ? 'Journée entière' : item.category}
        </span>
      </div>

      {item.description && compactMobile && (
        <p className="mt-2 max-h-9 overflow-hidden text-[10px] leading-tight opacity-70">
          {item.description}
        </p>
      )}
    </div>
  );
}
