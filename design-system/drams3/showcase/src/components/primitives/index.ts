/**
 * DRAMS3 Primitive Components
 *
 * PRIMARY PRIMITIVES — Components that introduce invariants.
 *
 * Categories:
 * - Structural: Page, Section, Article, Header, Footer, Nav, Aside
 * - Layout: Box, Flex, Grid, Stack, ScrollArea
 * - Typography: Heading, Text, Caption, Code
 * - Form: Form, FormField, FormDescription, FormMessage, Fieldset, Legend
 * - Form Controls: Button, Input, Checkbox, Radio, Select, Switch, Slider, Toggle
 * - Display: Avatar, Image, Badge, Kbd, Progress, Separator, Skeleton, Spinner
 *
 * API follows shadcn/ui conventions for drop-in compatibility.
 */

/* ═══════════════════════════════════════════════════════════════
   STRUCTURAL PRIMITIVES (HTML semantic replacements)
   ═══════════════════════════════════════════════════════════════ */

export {
   Article, Aside, Footer, Header, Nav, Page, Section, type ArticleProps, type AsideProps, type FooterProps, type HeaderProps, type NavProps, type PageProps, type SectionProps
} from './Layout'

/* ═══════════════════════════════════════════════════════════════
   LAYOUT PRIMITIVES
   ═══════════════════════════════════════════════════════════════ */

export {
   Box, Flex, Grid, Stack, type BoxProps, type FlexProps, type GridProps, type StackProps
} from './Layout'

export { ScrollArea, ScrollBar, type ScrollAreaProps, type ScrollBarProps } from './ScrollArea'

/* ═══════════════════════════════════════════════════════════════
   TYPOGRAPHY PRIMITIVES
   ═══════════════════════════════════════════════════════════════ */

export {
   Caption, Code, Heading, Text, type CaptionProps, type CodeProps, type HeadingProps, type TextProps
} from './Typography'

/* ═══════════════════════════════════════════════════════════════
   FORM PRIMITIVES
   ═══════════════════════════════════════════════════════════════ */

export {
   Fieldset, Form,
   FormDescription, FormField, FormMessage, Legend, type FieldsetProps, type FormDescriptionProps, type FormFieldProps, type FormMessageProps,
   type FormProps, type LegendProps
} from './Form'

/* ═══════════════════════════════════════════════════════════════
   FORM CONTROL PRIMITIVES
   ═══════════════════════════════════════════════════════════════ */

export { Button, type ButtonProps } from './Button'
export { Checkbox, type CheckboxProps } from './Checkbox'
export { Input, Textarea } from './Input'
export { Label } from './Label'
export { RadioGroup, RadioGroupItem } from './Radio'
export {
   Select,
   SelectContent,
   SelectGroup,
   SelectItem,
   SelectLabel,
   SelectScrollDownButton,
   SelectScrollUpButton,
   SelectSeparator,
   SelectTrigger,
   SelectValue,
   type SelectContentProps,
   type SelectItemProps,
   type SelectTriggerProps
} from './Select'
export { Slider, type SliderProps } from './Slider'
export { Switch } from './Switch'
export { Toggle, type ToggleProps } from './Toggle'

/* ═══════════════════════════════════════════════════════════════
   DISPLAY PRIMITIVES
   ═══════════════════════════════════════════════════════════════ */

export {
   Alert,
   AlertAction,
   AlertDescription,
   AlertTitle,
   type AlertProps
} from './Alert'
export {
   AlertDialog,
   AlertDialogAction,
   AlertDialogCancel,
   AlertDialogContent,
   AlertDialogDescription,
   AlertDialogFooter,
   AlertDialogHeader,
   AlertDialogOverlay,
   AlertDialogPortal,
   AlertDialogTitle,
   AlertDialogTrigger
} from './AlertDialog'
export {
   Avatar,
   AvatarBadge,
   AvatarFallback,
   AvatarGroup,
   AvatarGroupCount,
   AvatarImage,
   type AvatarBadgeProps,
   type AvatarGroupCountProps,
   type AvatarGroupProps,
   type AvatarProps
} from './Avatar'
export {
   Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader,
   CardTitle, type CardProps
} from './Card'
export {
   Dialog,
   DialogClose,
   DialogContent,
   DialogDescription,
   DialogFooter,
   DialogHeader,
   DialogOverlay,
   DialogPortal,
   DialogTitle,
   DialogTrigger,
   type DialogContentProps
} from './Dialog'
export {
   DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuPortal, DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuSeparator,
   DropdownMenuShortcut, DropdownMenuSub,
   DropdownMenuSubContent,
   DropdownMenuSubTrigger, DropdownMenuTrigger, type DropdownMenuContentProps,
   type DropdownMenuItemProps,
   type DropdownMenuLabelProps,
   type DropdownMenuSubTriggerProps
} from './DropdownMenu'
export { AspectRatio, Image, type AspectRatioProps, type ImageProps } from './Image'
export { Kbd, KbdGroup, type KbdGroupProps, type KbdProps } from './Kbd'
export {
   Popover,
   PopoverAnchor,
   PopoverClose,
   PopoverContent,
   PopoverPortal,
   PopoverTrigger,
   type PopoverContentProps
} from './Popover'
export { Progress, type ProgressProps } from './Progress'
export { Separator, type SeparatorProps } from './Separator'
export { Skeleton, type SkeletonProps } from './Skeleton'
export { Toaster, toast, type ToasterProps } from './Sonner'
export { Spinner, type SpinnerProps } from './Spinner'
export {
   BreadcrumbTabsList,
   BreadcrumbTabsSeparator,
   BreadcrumbTabsTrigger,
   Tabs,
   TabsContent,
   TabsList,
   TabsTrigger,
   type BreadcrumbTabsListProps,
   type BreadcrumbTabsSeparatorProps,
   type BreadcrumbTabsTriggerProps,
   type TabsContentProps,
   type TabsListProps,
   type TabsProps,
   type TabsTriggerProps
} from './Tabs'
export {
   Tooltip,
   TooltipContent,
   TooltipProvider,
   TooltipTrigger,
   type TooltipContentProps
} from './Tooltip'
