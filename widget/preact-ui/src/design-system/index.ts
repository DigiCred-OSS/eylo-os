/**
 * Eylo Widget Design System
 *
 * A comprehensive, production-ready component library built with Preact
 * Inspired by shadcn/ui with semantic design tokens and HSL color system
 */

// Utilities
export { cm, cn } from "./utils";
export type { ClassValue } from "./utils";

// Theme System
export * from "./theme";

// Primitives not yet rendered by product screens remain staged for planned widget rework.
// Core Components
export { Button } from "./components/Button";
export type { ButtonProps } from "./components/Button";

export { Input } from "./components/Input";
export type { InputProps } from "./components/Input";

export { Textarea } from "./components/Textarea";
export type { TextareaProps } from "./components/Textarea";

export { Label } from "./components/Label";
export type { LabelProps } from "./components/Label";

export { Badge } from "./components/Badge";
export type { BadgeProps } from "./components/Badge";

export { Separator } from "./components/Separator";
export type { SeparatorProps } from "./components/Separator";

// Layout Components
export {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "./components/Card";
export type { CardProps } from "./components/Card";

export { ScrollArea } from "./components/ScrollArea";
export type { ScrollAreaProps } from "./components/ScrollArea";

export { List, ListDivider, ListItem } from "./components/List";
export type { ListItemProps, ListProps } from "./components/List";

export { Flex } from "./components/Flex";
export type { FlexProps } from "./components/Flex";

export { Stack } from "./components/Stack";
export type { StackProps } from "./components/Stack";

// Feedback Components
export { Alert, AlertDescription, AlertTitle } from "./components/Alert";
export type { AlertProps } from "./components/Alert";

export { Progress } from "./components/Progress";
export type { ProgressProps } from "./components/Progress";

export { Skeleton } from "./components/Skeleton";
export type { SkeletonProps } from "./components/Skeleton";

export { Empty } from "./components/Empty";
export type { EmptyProps } from "./components/Empty";

export { Avatar } from "./components/Avatar";
export type { AvatarProps } from "./components/Avatar";

// Form Components
export { Switch } from "./components/Switch";
export type { SwitchProps } from "./components/Switch";

export { Checkbox } from "./components/Checkbox";
export type { CheckboxProps } from "./components/Checkbox";

export { RadioGroup, RadioGroupItem } from "./components/RadioGroup";
export type { RadioGroupItemProps, RadioGroupProps } from "./components/RadioGroup";

export {
  Select,
  SelectContent,
  SelectEmpty,
  SelectGroup,
  SelectGroupLabel,
  SelectItem,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "./components/Select";
export type {
  SelectContentProps,
  SelectItemProps,
  SelectProps,
  SelectTriggerProps,
} from "./components/Select";

export { Field } from "./components/Field";
export type { FieldProps } from "./components/Field";

// Dialog & Overlay Components
export {
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "./components/Dialog";
export type { DialogCloseProps, DialogContentProps, DialogProps } from "./components/Dialog";

export {
  Sheet,
  SheetBody,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "./components/Sheet";
export type { SheetCloseProps, SheetContentProps, SheetProps } from "./components/Sheet";

export { Tooltip } from "./components/Tooltip";
export type { TooltipProps } from "./components/Tooltip";

export { Popover, PopoverClose, PopoverContent, PopoverTrigger } from "./components/Popover";
export type { PopoverContentProps, PopoverProps, PopoverTriggerProps } from "./components/Popover";

export {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./components/DropdownMenu";
export type {
  DropdownMenuCheckboxItemProps,
  DropdownMenuContentProps,
  DropdownMenuItemProps,
  DropdownMenuProps,
  DropdownMenuTriggerProps,
} from "./components/DropdownMenu";

// Typography Components
export { Code, Heading, Text, Label as TypographyLabel } from "./components/Typography";
export type {
  CodeProps,
  HeadingProps,
  TextProps,
  LabelProps as TypographyLabelProps,
} from "./components/Typography";

export { Link } from "./components/Link";
export type { LinkProps } from "./components/Link";

// Composition Components
export {
  WidgetButtonGroup,
  WidgetCardList,
  WidgetDatePicker,
  WidgetDivider,
  WidgetForm,
  WidgetImage,
  WidgetProgress,
  WidgetRow,
  WidgetSection,
  WidgetStack,
  WidgetTable,
  WidgetText,
} from "./compositions";
