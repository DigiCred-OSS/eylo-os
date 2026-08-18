import { Plus, Search } from "lucide-react";
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
import { VoiceConfigDeleteDialog } from "@/features/voice/VoiceConfigDeleteDialog";
import { VoiceConfigDetailsDrawer } from "@/features/voice/VoiceConfigDetailsDrawer";
import { VoiceConfigTable } from "@/features/voice/VoiceConfigTable";
import {
  VOICE_FILTER_SCHEMA,
  VOICE_SORT_OPTIONS,
} from "@/features/voice/voice-list-controls";
import {
  applyVoiceCollectionQuery,
  buildVoiceCollectionSearchParams,
  DEFAULT_VOICE_QUERY,
  parseVoiceCollectionQuery,
} from "@/features/voice/voice.query";
import type {
  VoiceCollectionQuery,
  VoiceConfigRecord,
  VoiceSortField,
} from "@/features/voice/voice.types";
import { useAsyncContextGuard } from "@/lib/use-async-context-guard";

const VoiceConfigsPage = observer(function VoiceConfigsPage() {
  const { voice } = useRootStore();
  const { organizationId, voiceConfigId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [voiceConfigToDelete, setVoiceConfigToDelete] =
    useState<VoiceConfigRecord | null>(null);
  const searchParamsKey = searchParams.toString();
  const query = useMemo(
    () => parseVoiceCollectionQuery(new URLSearchParams(searchParamsKey)),
    [searchParamsKey],
  );
  const visibleItems = useMemo(
    () => applyVoiceCollectionQuery(voice.items, query, VOICE_FILTER_SCHEMA),
    [query, voice.items],
  );
  const [searchDraft, setSearchDraft] = useState(query.search);
  const contextKey = `${organizationId ?? "missing"}:${voiceConfigId ?? "collection"}:${searchParamsKey}`;
  const isCurrentContext = useAsyncContextGuard(contextKey);

  useEffect(() => setSearchDraft(query.search), [query.search]);
  useEffect(() => {
    if (organizationId !== undefined) {
      void voice.loadCollection(organizationId);
    }
  }, [organizationId, voice]);
  useEffect(() => {
    if (organizationId !== undefined && voiceConfigId !== undefined) {
      void voice.loadSelected(organizationId, voiceConfigId);
    } else {
      voice.clearSelected();
    }
    return voice.clearSelected;
  }, [organizationId, voice, voiceConfigId]);

  if (organizationId === undefined) {
    return null;
  }
  const activeOrganizationId = organizationId;

  function setQuery(nextQuery: VoiceCollectionQuery): void {
    setSearchParams(buildVoiceCollectionSearchParams(nextQuery));
  }

  function updateQuery(patch: Partial<VoiceCollectionQuery>): void {
    setQuery({ ...query, ...patch });
  }

  function openVoiceConfig(nextVoiceConfigId: string): void {
    void navigate({
      pathname: `/org/${activeOrganizationId}/voice/${nextVoiceConfigId}`,
      search: location.search,
    });
  }

  function closeVoiceConfig(): void {
    void navigate({
      pathname: `/org/${activeOrganizationId}/voice`,
      search: location.search,
    });
  }

  function createVoiceConfig(): void {
    void navigate({
      pathname: `/org/${activeOrganizationId}/voice/new`,
      search: location.search,
    });
  }

  function editVoiceConfig(nextVoiceConfigId: string): void {
    void navigate({
      pathname: `/org/${activeOrganizationId}/voice/${nextVoiceConfigId}/edit`,
      search: location.search,
    });
  }

  function requestDelete(voiceConfig: VoiceConfigRecord): void {
    voice.clearDeleteError();
    setVoiceConfigToDelete(voiceConfig);
  }

  async function confirmDelete(): Promise<boolean> {
    if (voiceConfigToDelete === null) {
      return false;
    }
    const submittedContextKey = contextKey;
    const deleted = await voice.deleteVoiceConfig(
      activeOrganizationId,
      voiceConfigToDelete.id,
    );
    if (!deleted || !isCurrentContext(submittedContextKey)) {
      return false;
    }
    if (voiceConfigId === voiceConfigToDelete.id) {
      closeVoiceConfig();
    }
    setVoiceConfigToDelete(null);
    return true;
  }

  function sortBy(field: VoiceSortField): void {
    const direction =
      query.sortBy === field
        ? query.direction === "asc"
          ? "desc"
          : "asc"
        : field === "updated_at" || field === "revision"
          ? "desc"
          : "asc";
    updateQuery({ direction, sortBy: field });
  }

  return (
    <section className="space-y-6 p-4 sm:p-6" aria-labelledby="voice-title">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1
            id="voice-title"
            className="text-2xl font-semibold tracking-tight"
          >
            Voice
          </h1>
          <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
            Define reusable voice behavior and provider authority, then bind one
            Voice Config to each conversational Agent.
          </p>
        </div>
        <Button onClick={createVoiceConfig}>
          <Plus aria-hidden="true" />
          New Voice Config
        </Button>
      </header>

      {voice.isCollectionStale ? (
        <div className="border bg-muted/30 p-3 text-sm" role="alert">
          Showing the last loaded Voice Configs. {voice.collectionErrorMessage}
        </div>
      ) : null}

      <CollectionToolbar
        listLabel="Voice Configs"
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
              aria-label="Search Voice Configs"
              maxLength={100}
              placeholder="Search Voice Configs"
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
            listLabel="Voice Configs"
            schema={VOICE_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters })}
          />
        }
        sort={
          <SortControl
            direction={query.direction}
            listLabel="Voice Configs"
            options={VOICE_SORT_OPTIONS}
            sort={query.sortBy}
            onDirectionChange={(direction) => updateQuery({ direction })}
            onSortChange={(sortBy) =>
              updateQuery({
                direction:
                  sortBy === "updated_at" || sortBy === "revision"
                    ? "desc"
                    : "asc",
                sortBy,
              })
            }
          />
        }
        appliedFilters={
          <AppliedFilterBar
            filterTree={query.filters}
            listLabel="Voice Configs"
            schema={VOICE_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters })}
          />
        }
      />

      <VoiceConfigTable
        items={visibleItems}
        query={query}
        onClearFilters={() =>
          setQuery({
            ...query,
            filters: DEFAULT_VOICE_QUERY.filters,
            search: "",
          })
        }
        onDelete={requestDelete}
        onEdit={editVoiceConfig}
        onRetry={() => void voice.loadCollection(activeOrganizationId)}
        onSort={sortBy}
        onView={openVoiceConfig}
      />

      <VoiceConfigDetailsDrawer
        voiceConfigId={voiceConfigId}
        onClose={closeVoiceConfig}
        onEdit={editVoiceConfig}
      />
      <VoiceConfigDeleteDialog
        errorMessage={voice.deleteErrorMessage}
        isDeleting={voice.isDeleting}
        open={voiceConfigToDelete !== null}
        voiceConfig={voiceConfigToDelete}
        onOpenChange={(open) => {
          if (!open) {
            setVoiceConfigToDelete(null);
            voice.clearDeleteError();
          }
        }}
        onConfirm={confirmDelete}
      />
    </section>
  );
});

export { VoiceConfigsPage };
