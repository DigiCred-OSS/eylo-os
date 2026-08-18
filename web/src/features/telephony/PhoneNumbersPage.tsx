import { Ellipsis, Eye, Pencil, Search, ShoppingCart } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useMemo, useState } from "react";
import {
  Link,
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PhoneNumberDetailsDrawer } from "@/features/telephony/PhoneNumberDetailsDrawer";
import { PurchaseNumberDialog } from "@/features/telephony/PurchaseNumberDialog";
import {
  formatTelephonyDate,
  formatTelephonyEnum,
} from "@/features/telephony/telephony-formatters";
import {
  PHONE_NUMBER_FILTER_SCHEMA,
  PHONE_NUMBER_SORT_OPTIONS,
} from "@/features/telephony/telephony-list-controls";
import {
  applyPhoneNumberQuery,
  buildPhoneNumberSearchParams,
  DEFAULT_PHONE_NUMBER_QUERY,
  hasPhoneNumberFilters,
  parsePhoneNumberQuery,
} from "@/features/telephony/telephony.query";
import type {
  PhoneNumber,
  PhoneNumberCollectionQuery,
  PhoneNumberSortField,
} from "@/features/telephony/telephony.types";

const PhoneNumbersPage = observer(function PhoneNumbersPage() {
  const { telephony } = useRootStore();
  const store = telephony.numbers;
  const { organizationId, phoneNumberId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [purchaseOpen, setPurchaseOpen] = useState(false);
  const searchKey = searchParams.toString();
  const query = useMemo(
    () => parsePhoneNumberQuery(new URLSearchParams(searchKey)),
    [searchKey],
  );
  const [searchDraft, setSearchDraft] = useState(query.search);
  const visible = useMemo(
    () => applyPhoneNumberQuery(store.items, query, PHONE_NUMBER_FILTER_SCHEMA),
    [query, store.items],
  );

  useEffect(() => setSearchDraft(query.search), [query.search]);
  useEffect(() => {
    if (organizationId === undefined) return;
    void store.loadCollection();
    void telephony.loadReferences(organizationId);
  }, [organizationId, store, telephony]);
  useEffect(() => {
    if (phoneNumberId !== undefined) void store.loadSelected(phoneNumberId);
    else store.clearSelected();
    return store.clearSelected;
  }, [phoneNumberId, store]);

  if (organizationId === undefined) return null;
  const basePath = `/org/${organizationId}/telephony/numbers`;

  function setQuery(next: PhoneNumberCollectionQuery): void {
    setSearchParams(buildPhoneNumberSearchParams(next));
  }
  function updateQuery(patch: Partial<PhoneNumberCollectionQuery>): void {
    setQuery({ ...query, ...patch });
  }
  function open(id: string): void {
    void navigate({ pathname: `${basePath}/${id}`, search: location.search });
  }
  function close(): void {
    void navigate({ pathname: basePath, search: location.search });
  }
  function sortBy(field: PhoneNumberSortField): void {
    updateQuery({
      direction:
        query.sortBy === field
          ? query.direction === "asc"
            ? "desc"
            : "asc"
          : "asc",
      sortBy: field,
    });
  }

  return (
    <section
      className="space-y-6 p-4 sm:p-6"
      aria-labelledby="phone-numbers-title"
    >
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1
            id="phone-numbers-title"
            className="text-2xl font-semibold tracking-tight"
          >
            Phone numbers
          </h1>
          <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
            Manage organization-owned carrier numbers and bind exact Agents for
            inbound or outbound routing.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setPurchaseOpen(true)}>
            <ShoppingCart aria-hidden="true" />
            Find numbers
          </Button>
          <Button nativeButton={false} render={<Link to={`${basePath}/new`} />}>
            Register number
          </Button>
        </div>
      </header>
      <CollectionToolbar
        listLabel="Phone numbers"
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
              aria-label="Search phone numbers"
              maxLength={100}
              placeholder="Search number, label, or provider"
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
            listLabel="Phone numbers"
            schema={PHONE_NUMBER_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters })}
          />
        }
        sort={
          <SortControl
            direction={query.direction}
            listLabel="Phone numbers"
            options={PHONE_NUMBER_SORT_OPTIONS}
            sort={query.sortBy}
            onDirectionChange={(direction) => updateQuery({ direction })}
            onSortChange={sortBy}
          />
        }
        appliedFilters={
          <AppliedFilterBar
            filterTree={query.filters}
            listLabel="Phone numbers"
            schema={PHONE_NUMBER_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters })}
          />
        }
      />
      <PhoneNumbersTable
        agentName={telephony.agentName}
        errorMessage={store.collectionErrorMessage}
        hasActiveFilters={hasPhoneNumberFilters(query)}
        isLoading={store.isCollectionLoading}
        items={visible}
        onClear={() =>
          setQuery({
            ...query,
            filters: DEFAULT_PHONE_NUMBER_QUERY.filters,
            search: "",
          })
        }
        onRetry={() => void store.loadCollection()}
        onView={open}
        organizationId={organizationId}
      />
      <PhoneNumberDetailsDrawer
        organizationId={organizationId}
        phoneNumberId={phoneNumberId}
        onClose={close}
      />
      <PurchaseNumberDialog
        open={purchaseOpen}
        onOpenChange={setPurchaseOpen}
        onPurchased={(number) => open(number.id)}
      />
    </section>
  );
});

function PhoneNumbersTable({
  agentName,
  errorMessage,
  hasActiveFilters,
  isLoading,
  items,
  onClear,
  onRetry,
  onView,
  organizationId,
}: {
  agentName: (id: string | null | undefined) => string;
  errorMessage: string | null;
  hasActiveFilters: boolean;
  isLoading: boolean;
  items: readonly PhoneNumber[];
  onClear: () => void;
  onRetry: () => void;
  onView: (id: string) => void;
  organizationId: string;
}) {
  if (errorMessage !== null)
    return (
      <Empty
        action="Try again"
        description={errorMessage}
        onAction={onRetry}
        title="Phone numbers are unavailable"
      />
    );
  if (!isLoading && items.length === 0)
    return (
      <Empty
        action={hasActiveFilters ? "Clear filters" : undefined}
        description={
          hasActiveFilters
            ? "Change or clear the filters to inspect other numbers."
            : "Register a number you already own, or search a configured carrier for a new number."
        }
        onAction={onClear}
        title={
          hasActiveFilters
            ? "No phone numbers match these filters"
            : "No phone numbers yet"
        }
      />
    );
  return (
    <div className="border">
      <div
        className="divide-y sm:hidden"
        role="list"
        aria-label="Phone numbers"
      >
        {isLoading
          ? Array.from({ length: 5 }, (_, index) => <LoadingCard key={index} />)
          : items.map((number) => (
              <NumberCard
                agentName={agentName}
                key={number.id}
                number={number}
                onView={onView}
                organizationId={organizationId}
              />
            ))}
      </div>
      <Table className="hidden table-fixed sm:table" aria-label="Phone numbers">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-[25%]">Number</TableHead>
            <TableHead className="w-32">Status</TableHead>
            <TableHead className="hidden w-32 md:table-cell">
              Provider
            </TableHead>
            <TableHead className="hidden w-[22%] lg:table-cell">
              Inbound Agent
            </TableHead>
            <TableHead className="hidden w-[22%] xl:table-cell">
              Outbound Agent
            </TableHead>
            <TableHead className="w-12 text-right">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading
            ? Array.from({ length: 6 }, (_, index) => (
                <LoadingRow key={index} />
              ))
            : items.map((number) => (
                <NumberRow
                  agentName={agentName}
                  key={number.id}
                  number={number}
                  onView={onView}
                  organizationId={organizationId}
                />
              ))}
        </TableBody>
      </Table>
      <div className="border-t px-3 py-3 text-xs text-muted-foreground">
        {isLoading
          ? "Loading phone numbers…"
          : `${items.length} phone number${items.length === 1 ? "" : "s"} · first 100`}
      </div>
    </div>
  );
}

function NumberRow({
  agentName,
  number,
  onView,
  organizationId,
}: {
  agentName: (id: string | null | undefined) => string;
  number: PhoneNumber;
  onView: (id: string) => void;
  organizationId: string;
}) {
  const danger = number.status === "PROVISIONING_FAILED";
  return (
    <TableRow>
      <TableCell className="whitespace-normal">
        <button
          className="text-left font-medium underline-offset-4 hover:underline"
          type="button"
          onClick={() => onView(number.id)}
        >
          {number.number}
        </button>
        <p className="mt-0.5 break-words text-xs text-muted-foreground">
          {number.label || "No label"}
        </p>
      </TableCell>
      <TableCell>
        <Badge variant={danger ? "destructive" : "outline"}>
          {formatTelephonyEnum(number.status)}
        </Badge>
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Badge variant="outline">{formatTelephonyEnum(number.provider)}</Badge>
      </TableCell>
      <TableCell className="hidden whitespace-normal lg:table-cell">
        {agentName(number.inboundAgentId)}
      </TableCell>
      <TableCell className="hidden whitespace-normal xl:table-cell">
        {agentName(number.outboundAgentId)}
      </TableCell>
      <TableCell className="text-right">
        <NumberMenu
          id={number.id}
          label={number.number}
          onView={onView}
          organizationId={organizationId}
        />
      </TableCell>
    </TableRow>
  );
}

function NumberCard({
  agentName,
  number,
  onView,
  organizationId,
}: {
  agentName: (id: string | null | undefined) => string;
  number: PhoneNumber;
  onView: (id: string) => void;
  organizationId: string;
}) {
  const updated = formatTelephonyDate(number.updatedAt);
  return (
    <article className="space-y-3 p-4" role="listitem">
      <div className="flex items-start justify-between gap-3">
        <button
          className="text-left font-medium underline-offset-4 hover:underline"
          type="button"
          onClick={() => onView(number.id)}
        >
          {number.number}
          <span className="block text-xs font-normal text-muted-foreground">
            {number.label || "No label"}
          </span>
        </button>
        <NumberMenu
          id={number.id}
          label={number.number}
          onView={onView}
          organizationId={organizationId}
        />
      </div>
      <div className="flex flex-wrap gap-2">
        <Badge
          variant={
            number.status === "PROVISIONING_FAILED" ? "destructive" : "outline"
          }
        >
          {formatTelephonyEnum(number.status)}
        </Badge>
        <Badge variant="outline">{formatTelephonyEnum(number.provider)}</Badge>
      </div>
      <p className="text-xs text-muted-foreground">
        Inbound: {agentName(number.inboundAgentId)} · Updated {updated.label}
      </p>
    </article>
  );
}

function NumberMenu({
  id,
  label,
  onView,
  organizationId,
}: {
  id: string;
  label: string;
  onView: (id: string) => void;
  organizationId: string;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Actions for ${label}`}
          />
        }
      >
        <Ellipsis aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => onView(id)}>
          <Eye aria-hidden="true" />
          View
        </DropdownMenuItem>
        <DropdownMenuItem
          render={
            <Link to={`/org/${organizationId}/telephony/numbers/${id}/edit`} />
          }
        >
          <Pencil aria-hidden="true" />
          Edit
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function LoadingRow() {
  return (
    <TableRow>
      <TableCell>
        <Skeleton className="h-4 w-28" />
        <Skeleton className="mt-2 h-3 w-20" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-5 w-24" />
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Skeleton className="h-5 w-20" />
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Skeleton className="h-4 w-28" />
      </TableCell>
      <TableCell className="hidden xl:table-cell">
        <Skeleton className="h-4 w-28" />
      </TableCell>
      <TableCell>
        <Skeleton className="ml-auto size-8" />
      </TableCell>
    </TableRow>
  );
}
function LoadingCard() {
  return (
    <div className="space-y-3 p-4">
      <Skeleton className="h-4 w-36" />
      <Skeleton className="h-5 w-40" />
      <Skeleton className="h-3 w-52" />
    </div>
  );
}
function Empty({
  action,
  description,
  onAction,
  title,
}: {
  action?: string;
  description: string;
  onAction: () => void;
  title: string;
}) {
  return (
    <div className="border py-16 text-center">
      <p className="text-sm font-medium">{title}</p>
      <p className="mx-auto mt-1 max-w-lg text-sm text-muted-foreground">
        {description}
      </p>
      {action === undefined ? null : (
        <Button className="mt-4" variant="outline" onClick={onAction}>
          {action}
        </Button>
      )}
    </div>
  );
}

export { PhoneNumbersPage };
