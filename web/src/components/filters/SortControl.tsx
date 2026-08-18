import { ArrowDown, ArrowUp, type LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface SortOption<Sort extends string> {
  icon: LucideIcon;
  label: string;
  value: Sort;
}

interface SortControlProps<Sort extends string> {
  direction: "asc" | "desc";
  listLabel: string;
  onDirectionChange: (direction: "asc" | "desc") => void;
  onSortChange: (sort: Sort) => void;
  options: readonly SortOption<Sort>[];
  sort: Sort;
}

function SortControl<Sort extends string>({
  direction,
  listLabel,
  onDirectionChange,
  onSortChange,
  options,
  sort,
}: SortControlProps<Sort>) {
  const selected = options.find((option) => option.value === sort);
  if (selected === undefined) {
    return null;
  }

  const SelectedIcon = selected.icon;
  const DirectionIcon = direction === "asc" ? ArrowUp : ArrowDown;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            aria-label={`Sort ${listLabel} by ${selected.label}, ${direction === "asc" ? "ascending" : "descending"}`}
            size="sm"
            variant="outline"
          />
        }
      >
        <SelectedIcon aria-hidden="true" />
        <span className="hidden sm:inline">{selected.label}</span>
        <DirectionIcon className="text-muted-foreground" aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuRadioGroup
          value={sort}
          onValueChange={(value) => onSortChange(value as Sort)}
        >
          <DropdownMenuLabel>Sort by</DropdownMenuLabel>
          {options.map((option) => {
            const Icon = option.icon;
            return (
              <DropdownMenuRadioItem key={option.value} value={option.value}>
                <Icon className="text-muted-foreground" aria-hidden="true" />
                {option.label}
              </DropdownMenuRadioItem>
            );
          })}
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <DropdownMenuRadioGroup
          value={direction}
          onValueChange={(value) =>
            onDirectionChange(value === "asc" ? "asc" : "desc")
          }
        >
          <DropdownMenuLabel>Direction</DropdownMenuLabel>
          <DropdownMenuRadioItem value="asc">
            <ArrowUp className="text-muted-foreground" aria-hidden="true" />
            Ascending
          </DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="desc">
            <ArrowDown className="text-muted-foreground" aria-hidden="true" />
            Descending
          </DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export { SortControl };
export type { SortOption };
