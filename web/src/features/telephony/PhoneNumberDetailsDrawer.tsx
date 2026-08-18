import { ExternalLink, Pencil, Trash2, X } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useState, type ReactNode } from "react";
import { Link } from "react-router";

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
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { Skeleton } from "@/components/ui/skeleton";
import {
  formatTelephonyDate,
  formatTelephonyEnum,
} from "@/features/telephony/telephony-formatters";
import type { PhoneNumber } from "@/features/telephony/telephony.types";

interface PhoneNumberDetailsDrawerProps {
  onClose: () => void;
  organizationId: string;
  phoneNumberId: string | undefined;
}

const PhoneNumberDetailsDrawer = observer(function PhoneNumberDetailsDrawer({
  onClose,
  organizationId,
  phoneNumberId,
}: PhoneNumberDetailsDrawerProps) {
  const { telephony } = useRootStore();
  const store = telephony.numbers;
  const number = store.selectedNumber;
  const [removeOpen, setRemoveOpen] = useState(false);

  async function remove(): Promise<void> {
    if (number === null) return;
    if (await store.remove(number.id)) {
      setRemoveOpen(false);
      onClose();
    }
  }

  return (
    <>
      <Drawer
        open={phoneNumberId !== undefined}
        onOpenChange={(open) => {
          if (!open) onClose();
        }}
        swipeDirection="right"
      >
        <DrawerContent className="[--drawer-content-width:min(100%,48rem)]">
          <DrawerHeader className="border-b p-5 pr-14 pb-5 text-left">
            <DrawerTitle>
              {number?.label || number?.number || "Phone number"}
            </DrawerTitle>
            <DrawerDescription>
              Carrier authority, provisioning state, and exact inbound or
              outbound Agent routing.
            </DrawerDescription>
          </DrawerHeader>
          <Button
            className="absolute top-4 right-4 z-20"
            variant="ghost"
            size="icon"
            aria-label="Close phone number"
            onClick={onClose}
          >
            <X aria-hidden="true" />
          </Button>
          <div className="min-h-0 flex-1 overflow-y-auto p-5">
            {store.isSelectedLoading && number === null ? (
              <DetailsSkeleton />
            ) : store.selectedErrorMessage !== null ? (
              <ErrorBox>{store.selectedErrorMessage}</ErrorBox>
            ) : number === null ? null : (
              <NumberDetails
                number={number}
                organizationId={organizationId}
                agentName={telephony.agentName}
                configName={telephony.configName}
              />
            )}
            {store.actionErrorMessage === null ? null : (
              <div className="mt-4">
                <ErrorBox>{store.actionErrorMessage}</ErrorBox>
              </div>
            )}
          </div>
          {number === null ? null : (
            <DrawerFooter className="flex-row flex-wrap border-t p-4">
              <Button
                nativeButton={false}
                render={
                  <Link
                    to={`/org/${organizationId}/telephony/numbers/${number.id}/edit`}
                  />
                }
              >
                <Pencil aria-hidden="true" />
                Edit
              </Button>
              <Button variant="destructive" onClick={() => setRemoveOpen(true)}>
                <Trash2 aria-hidden="true" />
                Remove from Eylo
              </Button>
            </DrawerFooter>
          )}
        </DrawerContent>
      </Drawer>
      <Dialog
        open={removeOpen}
        onOpenChange={(open) => {
          if (!store.isActing) setRemoveOpen(open);
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader className="pr-8">
            <DialogTitle>Remove this number from Eylo?</DialogTitle>
            <DialogDescription>
              This removes Eylo's number record and routing. It does not release
              or cancel the number at the carrier; manage that contract directly
              with the carrier.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              disabled={store.isActing}
              onClick={() => setRemoveOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={store.isActing}
              onClick={() => void remove()}
            >
              {store.isActing ? "Removing…" : "Remove from Eylo"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
});

function NumberDetails({
  agentName,
  configName,
  number,
  organizationId,
}: {
  agentName: (id: string | null | undefined) => string;
  configName: (id: string) => string;
  number: PhoneNumber;
  organizationId: string;
}) {
  const created = formatTelephonyDate(number.createdAt);
  const updated = formatTelephonyDate(number.updatedAt);
  const danger = number.status === "PROVISIONING_FAILED";
  return (
    <div className="space-y-8">
      <DetailsSection title="Overview">
        <DetailRow label="Number">
          <span className="font-medium">{number.number}</span>
        </DetailRow>
        <DetailRow label="Label">{number.label || "Not set"}</DetailRow>
        <DetailRow label="Status">
          <Badge variant={danger ? "destructive" : "outline"}>
            {formatTelephonyEnum(number.status)}
          </Badge>
        </DetailRow>
        <DetailRow label="Provider">
          <Badge variant="outline">
            {formatTelephonyEnum(number.provider)}
          </Badge>
        </DetailRow>
      </DetailsSection>
      <DetailsSection title="Carrier authority">
        <DetailRow label="Configuration">
          <Link
            className="inline-flex items-center gap-1 underline underline-offset-4"
            to={`/org/${organizationId}/providers/telephony/${number.providerConfigId}`}
          >
            {configName(number.providerConfigId)} · revision{" "}
            {number.providerConfigRevision}
            <ExternalLink className="size-3.5" aria-hidden="true" />
          </Link>
        </DetailRow>
        <DetailRow label="Provider reference">
          <code className="break-all text-xs">
            {number.providerReference ?? "Not recorded"}
          </code>
        </DetailRow>
        <DetailRow label="Provisioning failure">
          {number.provisioningFailureCode ?? "None"}
        </DetailRow>
      </DetailsSection>
      <DetailsSection title="Agent routing">
        <DetailRow label="Inbound Agent">
          {number.inboundAgentId === null ||
          number.inboundAgentId === undefined ? (
            "Not assigned"
          ) : (
            <Link
              className="underline underline-offset-4"
              to={`/org/${organizationId}/agents/${number.inboundAgentId}`}
            >
              {agentName(number.inboundAgentId)}
            </Link>
          )}
        </DetailRow>
        <DetailRow label="Outbound Agent">
          {number.outboundAgentId === null ||
          number.outboundAgentId === undefined ? (
            "Not assigned"
          ) : (
            <Link
              className="underline underline-offset-4"
              to={`/org/${organizationId}/agents/${number.outboundAgentId}`}
            >
              {agentName(number.outboundAgentId)}
            </Link>
          )}
        </DetailRow>
      </DetailsSection>
      <DetailsSection title="Record">
        <DetailRow label="Created">
          {number.createdAt === undefined ? (
            created.label
          ) : (
            <time dateTime={number.createdAt} title={created.title}>
              {created.label}
            </time>
          )}
        </DetailRow>
        <DetailRow label="Updated">
          {number.updatedAt === undefined ? (
            updated.label
          ) : (
            <time dateTime={number.updatedAt} title={updated.title}>
              {updated.label}
            </time>
          )}
        </DetailRow>
        <DetailRow label="ID">
          <code className="break-all text-xs">{number.id}</code>
        </DetailRow>
      </DetailsSection>
    </div>
  );
}

function DetailsSection({
  children,
  title,
}: {
  children: ReactNode;
  title: string;
}) {
  return (
    <section className="space-y-3">
      <h2 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        {title}
      </h2>
      <dl className="divide-y border-y">{children}</dl>
    </section>
  );
}

function DetailRow({
  children,
  label,
}: {
  children: ReactNode;
  label: string;
}) {
  return (
    <div className="grid gap-1 py-3 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-4">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words text-sm">{children}</dd>
    </div>
  );
}

function ErrorBox({ children }: { children: ReactNode }) {
  return (
    <div
      className="border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
      role="alert"
    >
      {children}
    </div>
  );
}

function DetailsSkeleton() {
  return (
    <div className="space-y-5">
      {Array.from({ length: 7 }, (_, index) => (
        <Skeleton className="h-10 w-full" key={index} />
      ))}
    </div>
  );
}

export { PhoneNumberDetailsDrawer };
