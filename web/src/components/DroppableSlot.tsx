import { useDroppable } from '@dnd-kit/core';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface Props {
  id: string;
  children?: React.ReactNode;
  className?: string;
}

export default function DroppableSlot({ id, children, className }: Props) {
  const { isOver, setNodeRef } = useDroppable({
    id: id,
  });

  return (
    <div
      ref={setNodeRef}
      className={twMerge(clsx(className, isOver && id !== 'inbox' ? 'bg-apple-blue/10 rounded-md ring-2 ring-apple-blue/50 inset-1 z-0 relative' : ''))}
    >
      {children}
    </div>
  );
}
