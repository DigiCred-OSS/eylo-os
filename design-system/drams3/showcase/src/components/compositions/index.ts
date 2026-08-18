/**
 * DRAMS3 Composition Components
 *
 * COMPOSITIONS — Documented patterns using primitives.
 * These introduce NO new invariants.
 *
 * Compositions are:
 * - Badge: Box + Typography for status indicators
 * - ButtonGroup: Flex + Button for grouped actions
 * - Sheet: Dialog variant that slides from screen edges
 *
 * API follows shadcn/ui conventions for drop-in compatibility.
 */

export { Badge, type BadgeProps } from './Badge'
export {
    ButtonGroup,
    ButtonGroupSeparator,
    ButtonGroupText,
    type ButtonGroupProps,
    type ButtonGroupSeparatorProps,
    type ButtonGroupTextProps
} from './ButtonGroup'
export { EmptyState, type EmptyStateProps } from './EmptyState'
export {
    Sheet,
    SheetClose,
    SheetContent,
    SheetDescription,
    SheetFooter,
    SheetHeader,
    SheetOverlay,
    SheetPortal,
    SheetTitle,
    SheetTrigger,
    type SheetContentProps
} from './Sheet'
