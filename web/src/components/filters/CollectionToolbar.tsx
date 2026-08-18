import type { ReactNode } from "react";

interface CollectionToolbarProps {
  appliedFilters: ReactNode;
  filter: ReactNode;
  listLabel: string;
  search: ReactNode;
  sort: ReactNode;
}

function CollectionToolbar({
  appliedFilters,
  filter,
  listLabel,
  search,
  sort,
}: CollectionToolbarProps) {
  return (
    <div className="min-w-0 space-y-2">
      <div
        aria-label={`${listLabel} list controls`}
        className="flex min-w-0 items-center gap-2"
        role="group"
      >
        <div className="min-w-0 flex-1">{search}</div>
        <div className="flex shrink-0 items-center gap-2">
          {filter}
          {sort}
        </div>
      </div>
      {appliedFilters}
    </div>
  );
}

export { CollectionToolbar };
