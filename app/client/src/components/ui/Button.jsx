import { cn } from '../../lib/cn';

const VARIANTS = {
  default: 'border-line bg-surface hover:border-accent hover:text-accent',
  primary:
    'border-accent bg-accent text-accent-fg hover:brightness-110 hover:shadow-[0_6px_20px_-6px_var(--accent)]',
  ghost: 'border-transparent bg-transparent hover:bg-surface-2',
  danger: 'border-line bg-surface text-bad hover:border-bad'
};

const SIZES = {
  sm: 'px-2.5 py-1 text-xs',
  md: 'px-3.5 py-2 text-sm'
};

/** Renders a <button>, or an <a> when `href` is given. */
export function Button({ as, href, variant = 'default', size = 'md', className, ...props }) {
  const Tag = as || (href ? 'a' : 'button');
  return (
    <Tag
      href={href}
      {...(Tag === 'button' ? { type: props.type || 'button' } : null)}
      className={cn(
        'inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border font-medium no-underline',
        'transition-[color,background-color,border-color,box-shadow,transform,filter] duration-200',
        'enabled:active:translate-y-px disabled:cursor-not-allowed disabled:opacity-50',
        VARIANTS[variant],
        SIZES[size],
        className
      )}
      {...props}
    />
  );
}
