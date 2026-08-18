/**
 * DRAMS3 React Components
 *
 * Two categories:
 *
 * 1. PRIMITIVES — Components that introduce invariants.
 *    These are the foundational building blocks.
 *
 * 2. COMPOSITIONS — Documented patterns using primitives.
 *    These introduce NO new invariants.
 *
 * API follows shadcn/ui conventions where applicable.
 */

/* ═══════════════════════════════════════════════════════════════
   PRIMITIVES
   Structural, layout, typography, form, and control elements.
   ═══════════════════════════════════════════════════════════════ */

export {
    // Alert
    Alert, AlertAction, AlertDescription,
    // AlertDialog
    AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogOverlay, AlertDialogPortal, AlertDialogTitle, AlertDialogTrigger, AlertTitle,
    // Structural (HTML semantic replacements)
    Article, Aside, AspectRatio,
    // Display
    Avatar, AvatarBadge, AvatarFallback, AvatarGroup, AvatarGroupCount, AvatarImage,
    // Layout
    Box,
    // Tabs
    BreadcrumbTabsList, BreadcrumbTabsSeparator, BreadcrumbTabsTrigger,
    // Form Controls
    Button,
    // Typography
    Caption,
    // Card
    Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle, Checkbox, Code,
    // Dialog
    Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogOverlay, DialogPortal, DialogTitle, DialogTrigger,
    // Dropdown Menu
    DropdownMenu, DropdownMenuCheckboxItem, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuPortal, DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuSeparator, DropdownMenuShortcut, DropdownMenuSub, DropdownMenuSubContent,
    DropdownMenuSubTrigger, DropdownMenuTrigger,
    // Form structure
    Fieldset, Flex, Footer, Form, FormDescription, FormField, FormMessage, Grid, Header, Heading, Image, Input, Kbd, KbdGroup, Label, Legend, Nav, Page,
    // Popover
    Popover, PopoverAnchor, PopoverClose, PopoverContent, PopoverPortal, PopoverTrigger, Progress, RadioGroup, RadioGroupItem, ScrollArea, ScrollBar, Section, Select, SelectContent, SelectGroup, SelectItem, SelectLabel,
    SelectScrollDownButton, SelectScrollUpButton, SelectSeparator, SelectTrigger, SelectValue, Separator,
    // Display continued
    Skeleton, Slider, Spinner, Stack, Switch, Tabs, TabsContent, TabsList, TabsTrigger, Text, Textarea, Toaster, Toggle,
    // Tooltip
    Tooltip, TooltipContent, TooltipProvider, TooltipTrigger, toast,
    // Types
    type AlertProps,
    type ArticleProps, type AsideProps, type AspectRatioProps,
    type AvatarBadgeProps, type AvatarGroupCountProps, type AvatarGroupProps, type AvatarProps,
    type BoxProps, type BreadcrumbTabsListProps, type BreadcrumbTabsSeparatorProps, type BreadcrumbTabsTriggerProps, type ButtonProps, type CaptionProps, type CardProps, type CheckboxProps, type CodeProps, type DialogContentProps, type DropdownMenuContentProps, type DropdownMenuItemProps, type DropdownMenuLabelProps,
    type DropdownMenuSubTriggerProps,
    type FieldsetProps, type FlexProps, type FooterProps,
    type FormDescriptionProps, type FormFieldProps, type FormMessageProps, type FormProps,
    type GridProps, type HeaderProps, type HeadingProps, type ImageProps,
    type KbdGroupProps, type KbdProps, type LegendProps, type NavProps, type PageProps, type PopoverContentProps, type ProgressProps, type ScrollAreaProps, type ScrollBarProps, type SectionProps,
    type SelectContentProps, type SelectItemProps, type SelectTriggerProps,
    type SeparatorProps, type SkeletonProps, type SliderProps, type SpinnerProps, type StackProps, type TabsContentProps, type TabsListProps, type TabsProps, type TabsTriggerProps, type TextProps, type ToasterProps, type ToggleProps, type TooltipContentProps
} from './primitives'

/* ═══════════════════════════════════════════════════════════════
   COMPOSITIONS
   Documented patterns using primitives. No new invariants.
   ═══════════════════════════════════════════════════════════════ */

export {
    Badge,
    ButtonGroup,
    ButtonGroupSeparator,
    ButtonGroupText,
    EmptyState,
    // Sheet (Dialog variant that slides from edges)
    Sheet, SheetClose, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetOverlay, SheetPortal, SheetTitle, SheetTrigger,
    // Types
    type BadgeProps, type ButtonGroupProps,
    type ButtonGroupSeparatorProps,
    type ButtonGroupTextProps,
    type EmptyStateProps,
    type SheetContentProps
} from './compositions'
