import { Search, ShoppingCart } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useState } from "react";

import { useRootStore } from "@/app/use-root-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { formatTelephonyEnum } from "@/features/telephony/telephony-formatters";
import type {
  AvailableNumber,
  NumberType,
  PhoneNumber,
} from "@/features/telephony/telephony.types";

interface PurchaseNumberDialogProps {
  onOpenChange: (open: boolean) => void;
  onPurchased: (number: PhoneNumber) => void;
  open: boolean;
}

const NUMBER_TYPES: readonly NumberType[] = ["Local", "TollFree", "Mobile"];

const PurchaseNumberDialog = observer(function PurchaseNumberDialog({
  onOpenChange,
  onPurchased,
  open,
}: PurchaseNumberDialogProps) {
  const { telephony } = useRootStore();
  const store = telephony.numbers;
  const [configId, setConfigId] = useState("");
  const [country, setCountry] = useState("");
  const [numberType, setNumberType] = useState<NumberType | "">("");
  const [areaCode, setAreaCode] = useState("");
  const [contains, setContains] = useState("");
  const [selected, setSelected] = useState<AvailableNumber | null>(null);
  const [label, setLabel] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [idempotencyKey, setIdempotencyKey] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const configs = telephony.configs.filter(
    (config) =>
      config.ready &&
      config.operations.search_numbers === true &&
      config.operations.purchase_number === true,
  );

  useEffect(() => {
    if (open) return;
    store.clearSearch();
    setConfigId("");
    setCountry("");
    setNumberType("");
    setAreaCode("");
    setContains("");
    setSelected(null);
    setLabel("");
    setConfirmOpen(false);
    setIdempotencyKey("");
    setValidationError(null);
  }, [open, store]);

  async function search(): Promise<void> {
    const normalizedCountry = country.trim().toUpperCase();
    if (configId === "")
      return setValidationError("Select a carrier configuration.");
    if (!/^[A-Z]{2}$/.test(normalizedCountry))
      return setValidationError(
        "Country must be a two-letter ISO code, such as US or IN.",
      );
    if (numberType === "") return setValidationError("Select a number type.");
    setValidationError(null);
    setSelected(null);
    await store.search(configId, {
      areaCode: areaCode.trim() || undefined,
      contains: contains.trim() || undefined,
      country: normalizedCountry,
      limit: 20,
      numberType,
    });
  }

  function choose(number: AvailableNumber): void {
    setSelected(number);
    setIdempotencyKey(crypto.randomUUID());
    setValidationError(null);
  }

  async function purchase(): Promise<void> {
    if (selected === null || configId === "" || idempotencyKey === "") return;
    const purchased = await store.purchase(
      configId,
      {
        countryCode: selected.country ?? country.trim().toUpperCase(),
        label: label.trim() || null,
        phoneNumber: selected.phoneNumber,
      },
      idempotencyKey,
    );
    if (purchased !== null) {
      setConfirmOpen(false);
      onOpenChange(false);
      onPurchased(purchased);
    }
  }

  return (
    <>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          if (!store.isActing) onOpenChange(next);
        }}
      >
        <DialogContent className="max-h-[92svh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader className="pr-8">
            <DialogTitle>Find a carrier number</DialogTitle>
            <DialogDescription>
              Search one explicit ready carrier account. Purchasing may incur
              carrier charges and is never run during QA without approval.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="number-search-config" label="Carrier configuration">
              <Select
                value={configId || null}
                onValueChange={(value) => setConfigId(value ?? "")}
              >
                <SelectTrigger id="number-search-config" className="w-full">
                  <SelectValue placeholder="Select configuration" />
                </SelectTrigger>
                <SelectContent>
                  {configs.map((config) => (
                    <SelectItem value={config.id} key={config.id}>
                      {config.name} · {config.provider}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field id="number-search-country" label="Country code">
              <Input
                id="number-search-country"
                maxLength={2}
                placeholder="US"
                value={country}
                onChange={(event) =>
                  setCountry(event.target.value.toUpperCase())
                }
              />
            </Field>
            <Field id="number-search-type" label="Number type">
              <Select
                value={numberType || null}
                onValueChange={(value) =>
                  setNumberType(
                    NUMBER_TYPES.includes(value as NumberType)
                      ? (value as NumberType)
                      : "",
                  )
                }
              >
                <SelectTrigger id="number-search-type" className="w-full">
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  {NUMBER_TYPES.map((type) => (
                    <SelectItem key={type} value={type}>
                      {formatTelephonyEnum(type)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field id="number-search-area" label="Area code" optional>
              <Input
                id="number-search-area"
                maxLength={12}
                value={areaCode}
                onChange={(event) => setAreaCode(event.target.value)}
              />
            </Field>
            <Field id="number-search-contains" label="Contains" optional>
              <Input
                id="number-search-contains"
                maxLength={20}
                value={contains}
                onChange={(event) => setContains(event.target.value)}
              />
            </Field>
          </div>
          {validationError === null &&
          store.searchErrorMessage === null ? null : (
            <ErrorBox>{validationError ?? store.searchErrorMessage}</ErrorBox>
          )}
          <div className="flex justify-end">
            <Button
              disabled={store.isSearching || configs.length === 0}
              onClick={() => void search()}
            >
              <Search aria-hidden="true" />
              {store.isSearching ? "Searching…" : "Search carrier"}
            </Button>
          </div>
          {configs.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No ready telephony configuration supports both number search and
              purchase.
            </p>
          ) : null}
          {store.isSearching ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }, (_, index) => (
                <Skeleton className="h-16 w-full" key={index} />
              ))}
            </div>
          ) : store.availableNumbers.length === 0 ? null : (
            <div
              className="divide-y border"
              role="list"
              aria-label="Available phone numbers"
            >
              {store.availableNumbers.map((number) => (
                <button
                  className={
                    selected?.phoneNumber === number.phoneNumber
                      ? "flex w-full items-center justify-between gap-4 bg-muted p-3 text-left"
                      : "flex w-full items-center justify-between gap-4 p-3 text-left hover:bg-muted/60"
                  }
                  key={number.phoneNumber}
                  type="button"
                  onClick={() => choose(number)}
                >
                  <span className="min-w-0">
                    <span className="block font-medium">
                      {number.friendlyName || number.phoneNumber}
                    </span>
                    <span className="block break-words text-xs text-muted-foreground">
                      {[number.locality, number.region, number.country]
                        .filter(Boolean)
                        .join(" · ") || "Location not supplied"}
                    </span>
                  </span>
                  <span className="flex flex-wrap justify-end gap-1">
                    {Object.entries(number.capabilities ?? {})
                      .filter(([, enabled]) => enabled === true)
                      .map(([capability]) => (
                        <Badge variant="outline" key={capability}>
                          {formatTelephonyEnum(capability)}
                        </Badge>
                      ))}
                  </span>
                </button>
              ))}
            </div>
          )}
          {selected === null ? null : (
            <Field
              id="number-purchase-label"
              label={`Label for ${selected.phoneNumber}`}
              optional
            >
              <Input
                id="number-purchase-label"
                maxLength={255}
                value={label}
                onChange={(event) => setLabel(event.target.value)}
              />
            </Field>
          )}
          {store.actionErrorMessage === null ? null : (
            <ErrorBox>{store.actionErrorMessage}</ErrorBox>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              disabled={store.isActing}
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              disabled={selected === null || store.isActing}
              onClick={() => setConfirmOpen(true)}
            >
              <ShoppingCart aria-hidden="true" />
              Review purchase
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog
        open={confirmOpen}
        onOpenChange={(next) => {
          if (!store.isActing) setConfirmOpen(next);
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader className="pr-8">
            <DialogTitle>Purchase {selected?.phoneNumber}?</DialogTitle>
            <DialogDescription>
              This sends one charged request to the selected carrier. Eylo uses
              the same idempotency key if you retry this confirmation after an
              uncertain response.
            </DialogDescription>
          </DialogHeader>
          <div className="border p-3 text-sm">
            <p className="font-medium">Carrier contract applies</p>
            <p className="mt-1 text-muted-foreground">
              Pricing, availability, regulatory requirements, and cancellation
              remain between your organization and the carrier.
            </p>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              disabled={store.isActing}
              onClick={() => setConfirmOpen(false)}
            >
              Go back
            </Button>
            <Button disabled={store.isActing} onClick={() => void purchase()}>
              {store.isActing ? "Purchasing…" : "Purchase number"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
});

function Field({
  children,
  id,
  label,
  optional = false,
}: {
  children: React.ReactNode;
  id: string;
  label: string;
  optional?: boolean;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <Label htmlFor={id}>{label}</Label>
        {optional ? (
          <span className="text-xs text-muted-foreground">Optional</span>
        ) : null}
      </div>
      {children}
    </div>
  );
}

function ErrorBox({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
      role="alert"
    >
      {children}
    </div>
  );
}

export { PurchaseNumberDialog };
