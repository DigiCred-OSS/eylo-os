import { useEffect, useState } from "react";

import type { FilterDefinition, FilterOption } from "@/lib/filters";

interface LoadedOptions {
  error: string | null;
  options: readonly FilterOption[];
  property: string | null;
  query: string | null;
}

function useFilterOptions<Item, Property extends string, Icon>(
  definition: FilterDefinition<Item, Property, Icon>,
  query: string,
  enabled = true,
) {
  const [loaded, setLoaded] = useState<LoadedOptions>({
    error: null,
    options: [],
    property: null,
    query: null,
  });
  const loadOptions = definition.loadOptions;

  useEffect(() => {
    if (!enabled || loadOptions === undefined) {
      return;
    }

    let current = true;
    void loadOptions(query)
      .then((options) => {
        if (current) {
          setLoaded({
            error: null,
            options,
            property: definition.property,
            query,
          });
        }
      })
      .catch(() => {
        if (current) {
          setLoaded({
            error: "Values could not be loaded.",
            options: [],
            property: definition.property,
            query,
          });
        }
      });

    return () => {
      current = false;
    };
  }, [definition.property, enabled, loadOptions, query]);

  if (loadOptions === undefined) {
    return {
      error: null,
      isLoading: false,
      options: definition.options ?? [],
    };
  }

  const isCurrent =
    loaded.property === definition.property && loaded.query === query;
  return {
    error: isCurrent ? loaded.error : null,
    isLoading: enabled && !isCurrent,
    options: isCurrent ? loaded.options : [],
  };
}

export { useFilterOptions };
