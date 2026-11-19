import { cn } from '../../lib/cn';

export function Card({ className, as: Tag = 'section', ...props }) {
  return (
    <Tag
      className={cn('rounded-card border border-line bg-surface p-[18px] shadow-card sm:p-5', className)}
      {...props}
    />
  );
}

/** Title + one line of explanation, the header every card in the app uses. */
export function CardHeader({ title, subtitle, action }) {
  return (
    <div className="mb-4 flex items-start justify-between gap-2">
      <div className="min-w-0">
        <h2 className="text-[19px] font-semibold leading-tight">{title}</h2>
        {subtitle && <p className="mt-1 text-[13px] text-muted">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
