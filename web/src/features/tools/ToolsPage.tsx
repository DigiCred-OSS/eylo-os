import { Search } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useMemo, useState } from "react";
import {
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router";

import { useRootStore } from "@/app/use-root-store";
import {
  AppliedFilterBar,
  CollectionToolbar,
  FilterControl,
  SortControl,
} from "@/components/filters";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatProviderIdentifier } from "@/features/providers/provider-formatters";
import { ToolDetailsDrawer } from "@/features/tools/ToolDetailsDrawer";
import { ToolsTable } from "@/features/tools/ToolsTable";
import {
  CATALOG_TOOL_FILTER_SCHEMA,
  CATALOG_TOOL_SORT_OPTIONS,
  TOOL_FILTER_SCHEMA,
  TOOL_SORT_OPTIONS,
} from "@/features/tools/tools-list-controls";
import {
  applyToolsQuery,
  buildToolsSearchParams,
  DEFAULT_TOOLS_QUERY,
  parseToolsQuery,
} from "@/features/tools/tools.query";
import type {
  ToolCapability,
  ToolCollectionQuery,
  ToolSortField,
  ToolSource,
} from "@/features/tools/tools.types";

const CAPABILITIES: readonly ToolCapability[] = [
  "llm",
  "stt",
  "tts",
  "realtime",
  "webrtc",
  "telephony",
  "email",
  "storage",
  "embedding",
  "reranking",
  "memory",
  "sandbox",
];

const ToolsPage = observer(function ToolsPage() {
  const { tools } = useRootStore();
  const { organizationId, toolId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const searchParamsKey = searchParams.toString();
  const query = useMemo(
    () => parseToolsQuery(new URLSearchParams(searchParamsKey)),
    [searchParamsKey],
  );
  const [searchDraft, setSearchDraft] = useState(query.search);
  const activeFilterSchema =
    query.source === "managed"
      ? TOOL_FILTER_SCHEMA
      : CATALOG_TOOL_FILTER_SCHEMA;
  const activeSortOptions =
    query.source === "managed" ? TOOL_SORT_OPTIONS : CATALOG_TOOL_SORT_OPTIONS;
  const visibleItems = useMemo(
    () => applyToolsQuery(tools.items, query, activeFilterSchema),
    [activeFilterSchema, query, tools.items],
  );

  useEffect(() => setSearchDraft(query.search), [query.search]);
  useEffect(() => {
    if (organizationId !== undefined) {
      void tools.loadCollection(organizationId, query.source, query.capability);
    }
  }, [organizationId, query.capability, query.source, tools]);
  useEffect(() => {
    if (
      organizationId !== undefined &&
      toolId !== undefined &&
      (query.source === "managed" || !tools.isCollectionLoading)
    ) {
      void tools.select(organizationId, toolId, query.source);
    } else if (toolId === undefined) {
      tools.clearSelected();
    }
  }, [
    organizationId,
    query.source,
    toolId,
    tools,
    tools.isCollectionLoading,
    tools.items,
  ]);

  if (organizationId === undefined) return null;
  const activeOrganizationId = organizationId;

  function setQuery(next: ToolCollectionQuery): void {
    setSearchParams(buildToolsSearchParams(next));
  }

  function updateQuery(patch: Partial<ToolCollectionQuery>): void {
    setQuery({ ...query, ...patch });
  }

  function changeSource(source: ToolSource): void {
    setQuery({
      ...query,
      filters: DEFAULT_TOOLS_QUERY.filters,
      sortBy:
        source === "managed" ||
        (query.sortBy !== "lifecycle" && query.sortBy !== "updated_at")
          ? query.sortBy
          : "display_name",
      source,
    });
  }

  function openTool(nextToolId: string): void {
    void navigate({
      pathname: `/org/${activeOrganizationId}/tools/${nextToolId}`,
      search: location.search,
    });
  }

  function closeTool(): void {
    void navigate({
      pathname: `/org/${activeOrganizationId}/tools`,
      search: location.search,
    });
  }

  function sortBy(field: ToolSortField): void {
    updateQuery({
      direction:
        query.sortBy === field
          ? query.direction === "asc"
            ? "desc"
            : "asc"
          : field === "updated_at"
            ? "desc"
            : "asc",
      sortBy: field,
    });
  }

  return (
    <section className="space-y-6 p-4 sm:p-6" aria-labelledby="tools-title">
      <header className="space-y-1">
        <h1 id="tools-title" className="text-2xl font-semibold tracking-tight">
          Tools
        </h1>
        <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
          Inspect the exact contracts Agents can call. Agent-to-tool assignment
          remains explicit in each Agent configuration.
        </p>
      </header>

      <div className="space-y-4 border-y py-4">
        <div
          className="flex flex-wrap gap-2"
          role="group"
          aria-label="Tool source"
        >
          <SourceButton
            active={query.source === "system"}
            onClick={() => changeSource("system")}
          >
            System catalog
          </SourceButton>
          <SourceButton
            active={query.source === "provider"}
            onClick={() => changeSource("provider")}
          >
            Provider tools
          </SourceButton>
          <SourceButton
            active={query.source === "managed"}
            onClick={() => changeSource("managed")}
          >
            Managed definitions
          </SourceButton>
        </div>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <p className="max-w-2xl text-sm text-muted-foreground">
            {sourceDescription(query.source)}
          </p>
          {query.source === "provider" ? (
            <div className="w-full space-y-2 sm:w-64">
              <Label htmlFor="tool-capability">Provider capability</Label>
              <Select
                value={query.capability}
                onValueChange={(value) => {
                  if (value !== null)
                    updateQuery({ capability: value as ToolCapability });
                }}
              >
                <SelectTrigger id="tool-capability" className="w-full">
                  <SelectValue>
                    {formatProviderIdentifier(query.capability)}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {CAPABILITIES.map((capability) => (
                    <SelectItem key={capability} value={capability}>
                      {formatProviderIdentifier(capability)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}
        </div>
      </div>

      <CollectionToolbar
        listLabel="Tools"
        search={
          <form
            className="relative w-full sm:max-w-sm"
            role="search"
            onSubmit={(event) => {
              event.preventDefault();
              updateQuery({ search: searchDraft.trim().slice(0, 100) });
            }}
          >
            <Search
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              className="pr-20 pl-9"
              aria-label="Search tools"
              maxLength={100}
              placeholder="Search tools"
              value={searchDraft}
              onChange={(event) => setSearchDraft(event.target.value)}
            />
            <Button
              className="absolute top-0 right-0 rounded-l-none"
              variant="ghost"
              type="submit"
            >
              Search
            </Button>
          </form>
        }
        filter={
          <FilterControl
            filterTree={query.filters}
            listLabel="Tools"
            schema={activeFilterSchema}
            onChange={(filters) => updateQuery({ filters })}
          />
        }
        sort={
          <SortControl
            direction={query.direction}
            listLabel="Tools"
            options={activeSortOptions}
            sort={query.sortBy}
            onDirectionChange={(direction) => updateQuery({ direction })}
            onSortChange={sortBy}
          />
        }
        appliedFilters={
          <AppliedFilterBar
            filterTree={query.filters}
            listLabel="Tools"
            schema={activeFilterSchema}
            onChange={(filters) => updateQuery({ filters })}
          />
        }
      />

      <ToolsTable
        errorMessage={tools.collectionErrorMessage}
        isLoading={tools.isCollectionLoading}
        items={visibleItems}
        query={query}
        source={query.source}
        onClearFilters={() =>
          setQuery({
            ...query,
            filters: DEFAULT_TOOLS_QUERY.filters,
            search: "",
          })
        }
        onRetry={() =>
          void tools.loadCollection(
            activeOrganizationId,
            query.source,
            query.capability,
          )
        }
        onView={openTool}
      />

      <ToolDetailsDrawer
        organizationId={activeOrganizationId}
        source={query.source}
        toolId={toolId}
        onClose={closeTool}
      />
    </section>
  );
});

function SourceButton({
  active,
  children,
  onClick,
}: {
  active: boolean;
  children: string;
  onClick: () => void;
}) {
  return (
    <Button
      variant={active ? "secondary" : "ghost"}
      aria-pressed={active}
      onClick={onClick}
    >
      {children}
    </Button>
  );
}

function sourceDescription(source: ToolSource): string {
  if (source === "provider") {
    return "Tools unlocked by a provider capability. Readiness still depends on an enabled provider config and Agent mapping.";
  }
  if (source === "managed") {
    return "Organization-owned MCP or registered local definitions with explicit revision lifecycle.";
  }
  return "Platform-owned tools available to this organization after capability requirements are evaluated.";
}

export { ToolsPage };
