/**
 * shadcn/ui components + DRAMS' `accent`
 *
 * These are stock shadcn/ui components — the same Radix primitives, the same
 * `cva` variants, the same Tailwind classes. DRAMS adds exactly one thing to
 * each: an `accent` boolean that appends the `.accent` class, plus a
 * `data-slot` so the accent layer in globals.css can find the right part.
 *
 * The API matches the CSS system and the Preact adapter:
 *
 *   <Button>Save</Button>          // neutral
 *   <Button accent>Save</Button>   // brand
 */
import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import * as CheckboxPrimitive from '@radix-ui/react-checkbox'
import * as SwitchPrimitive from '@radix-ui/react-switch'
import * as SliderPrimitive from '@radix-ui/react-slider'
import * as RadioPrimitive from '@radix-ui/react-radio-group'
import * as TabsPrimitive from '@radix-ui/react-tabs'
import * as ProgressPrimitive from '@radix-ui/react-progress'
import * as SeparatorPrimitive from '@radix-ui/react-separator'
import * as LabelPrimitive from '@radix-ui/react-label'
import { Check, Circle } from 'lucide-react'
import { cn } from '@/lib/utils'

type Accent = { accent?: boolean }

/* ── Button — stock shadcn cva ────────────────────────────────── */

const buttonVariants = cva(
    'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
    {
        variants: {
            variant: {
                default: 'bg-primary text-primary-foreground hover:bg-primary/90',
                destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
                outline: 'border border-input bg-background hover:bg-accent hover:text-accent-foreground',
                secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80',
                ghost: 'hover:bg-accent hover:text-accent-foreground',
                link: 'text-primary underline-offset-4 hover:underline',
            },
            size: {
                default: 'h-10 px-4 py-2',
                sm: 'h-9 rounded-md px-3',
                lg: 'h-11 rounded-md px-8',
                icon: 'h-10 w-10',
            },
        },
        defaultVariants: { variant: 'default', size: 'default' },
    },
)

export interface ButtonProps
    extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants>, Accent { }

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
    ({ className, variant, size, accent, ...props }, ref) => (
        <button
            ref={ref}
            data-slot="button"
            className={cn(buttonVariants({ variant, size }), accent && 'accent', className)}
            {...props}
        />
    ),
)
Button.displayName = 'Button'

/* ── Input / Textarea ─────────────────────────────────────────── */

export const Input = React.forwardRef<
    HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement> & Accent
>(({ className, accent, ...props }, ref) => (
    <input
        ref={ref}
        className={cn(
            'flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
            accent && 'accent', className,
        )}
        {...props}
    />
))
Input.displayName = 'Input'

export const Textarea = React.forwardRef<
    HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement> & Accent
>(({ className, accent, ...props }, ref) => (
    <textarea
        ref={ref}
        className={cn(
            'flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
            accent && 'accent', className,
        )}
        {...props}
    />
))
Textarea.displayName = 'Textarea'

/* ── Checkbox ─────────────────────────────────────────────────── */

export const Checkbox = React.forwardRef<
    React.ElementRef<typeof CheckboxPrimitive.Root>,
    React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root> & Accent
>(({ className, accent, ...props }, ref) => (
    <CheckboxPrimitive.Root
        ref={ref}
        className={cn(
            'peer h-4 w-4 shrink-0 rounded-sm border border-primary ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground',
            accent && 'accent', className,
        )}
        {...props}
    >
        <CheckboxPrimitive.Indicator className="flex items-center justify-center text-current">
            <Check className="h-4 w-4" />
        </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
))
Checkbox.displayName = 'Checkbox'

/* ── Switch ───────────────────────────────────────────────────── */

export const Switch = React.forwardRef<
    React.ElementRef<typeof SwitchPrimitive.Root>,
    React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root> & Accent
>(({ className, accent, ...props }, ref) => (
    <SwitchPrimitive.Root
        ref={ref}
        className={cn(
            'peer inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=unchecked]:bg-input',
            accent && 'accent', className,
        )}
        {...props}
    >
        <SwitchPrimitive.Thumb className="pointer-events-none block h-5 w-5 rounded-full bg-background shadow-lg ring-0 transition-transform data-[state=checked]:translate-x-5 data-[state=unchecked]:translate-x-0" />
    </SwitchPrimitive.Root>
))
Switch.displayName = 'Switch'

/* ── Slider ───────────────────────────────────────────────────── */

export const Slider = React.forwardRef<
    React.ElementRef<typeof SliderPrimitive.Root>,
    React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root> & Accent
>(({ className, accent, ...props }, ref) => (
    <SliderPrimitive.Root
        ref={ref}
        className={cn('relative flex w-full touch-none select-none items-center', accent && 'accent', className)}
        {...props}
    >
        <SliderPrimitive.Track className="relative h-2 w-full grow overflow-hidden rounded-full bg-secondary">
            <SliderPrimitive.Range data-slot="range" className="absolute h-full bg-primary" />
        </SliderPrimitive.Track>
        <SliderPrimitive.Thumb className="block h-5 w-5 rounded-full border-2 border-primary bg-background ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50" />
    </SliderPrimitive.Root>
))
Slider.displayName = 'Slider'

/* ── Radio group ──────────────────────────────────────────────── */

export const RadioGroup = React.forwardRef<
    React.ElementRef<typeof RadioPrimitive.Root>,
    React.ComponentPropsWithoutRef<typeof RadioPrimitive.Root>
>(({ className, ...props }, ref) => (
    <RadioPrimitive.Root ref={ref} className={cn('grid gap-2', className)} {...props} />
))
RadioGroup.displayName = 'RadioGroup'

export const RadioGroupItem = React.forwardRef<
    React.ElementRef<typeof RadioPrimitive.Item>,
    React.ComponentPropsWithoutRef<typeof RadioPrimitive.Item> & Accent
>(({ className, accent, ...props }, ref) => (
    <RadioPrimitive.Item
        ref={ref}
        className={cn(
            'aspect-square h-4 w-4 rounded-full border border-primary text-primary ring-offset-background focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
            accent && 'accent', className,
        )}
        {...props}
    >
        <RadioPrimitive.Indicator className="flex items-center justify-center">
            <Circle data-slot="indicator" className="h-2.5 w-2.5 fill-current text-current" />
        </RadioPrimitive.Indicator>
    </RadioPrimitive.Item>
))
RadioGroupItem.displayName = 'RadioGroupItem'

/* ── Tabs ─────────────────────────────────────────────────────── */

export const Tabs = TabsPrimitive.Root

export const TabsList = React.forwardRef<
    React.ElementRef<typeof TabsPrimitive.List>,
    React.ComponentPropsWithoutRef<typeof TabsPrimitive.List> & Accent
>(({ className, accent, ...props }, ref) => (
    <TabsPrimitive.List
        ref={ref}
        className={cn(
            'inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground',
            accent && 'accent', className,
        )}
        {...props}
    />
))
TabsList.displayName = 'TabsList'

export const TabsTrigger = React.forwardRef<
    React.ElementRef<typeof TabsPrimitive.Trigger>,
    React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
    <TabsPrimitive.Trigger
        ref={ref}
        className={cn(
            'inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm',
            className,
        )}
        {...props}
    />
))
TabsTrigger.displayName = 'TabsTrigger'

/* ── Progress ─────────────────────────────────────────────────── */

export const Progress = React.forwardRef<
    React.ElementRef<typeof ProgressPrimitive.Root>,
    React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root> & Accent & { value?: number }
>(({ className, value, accent, ...props }, ref) => (
    <ProgressPrimitive.Root
        ref={ref}
        className={cn('relative h-4 w-full overflow-hidden rounded-full bg-secondary', accent && 'accent', className)}
        {...props}
    >
        <ProgressPrimitive.Indicator
            data-slot="indicator"
            className="h-full w-full flex-1 bg-primary transition-all"
            style={{ transform: `translateX(-${100 - (value || 0)}%)` }}
        />
    </ProgressPrimitive.Root>
))
Progress.displayName = 'Progress'

/* ── Misc ─────────────────────────────────────────────────────── */

export const Separator = React.forwardRef<
    React.ElementRef<typeof SeparatorPrimitive.Root>,
    React.ComponentPropsWithoutRef<typeof SeparatorPrimitive.Root>
>(({ className, orientation = 'horizontal', decorative = true, ...props }, ref) => (
    <SeparatorPrimitive.Root
        ref={ref} decorative={decorative} orientation={orientation}
        className={cn('shrink-0 bg-border', orientation === 'horizontal' ? 'h-[1px] w-full' : 'h-full w-[1px]', className)}
        {...props}
    />
))
Separator.displayName = 'Separator'

export const Label = React.forwardRef<
    React.ElementRef<typeof LabelPrimitive.Root>,
    React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>
>(({ className, ...props }, ref) => (
    <LabelPrimitive.Root ref={ref} className={cn('text-sm font-medium leading-none', className)} {...props} />
))
Label.displayName = 'Label'

export const Badge = ({ className, variant = 'default', accent, ...props }:
    React.HTMLAttributes<HTMLDivElement> & Accent & { variant?: 'default' | 'secondary' | 'destructive' | 'outline' }) => {
    const styles = {
        default: 'border-transparent bg-primary text-primary-foreground',
        secondary: 'border-transparent bg-secondary text-secondary-foreground',
        destructive: 'border-transparent bg-destructive text-destructive-foreground',
        outline: 'text-foreground',
    }
    return <div data-slot="badge" className={cn('inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold', styles[variant], accent && 'accent', className)} {...props} />
}

export const Card = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
    <div className={cn('rounded-lg border bg-card text-card-foreground shadow-sm', className)} {...props} />
)

export const Skeleton = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
    <div className={cn('animate-pulse rounded-md bg-muted', className)} {...props} />
)
