import { X } from "lucide-react";
import { observer } from "mobx-react-lite";

import { useRootStore } from "@/app/use-root-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { Skeleton } from "@/components/ui/skeleton";
import {
  formatMemberDate,
  formatMemberStatus,
} from "@/features/members/member-formatters";

const MemberDetailsDrawer = observer(function MemberDetailsDrawer({
  memberId,
  onClose,
}: {
  memberId: string | undefined;
  onClose: () => void;
}) {
  const { members } = useRootStore();
  const member = members.selectedMember;
  return (
    <Drawer
      open={memberId !== undefined}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      swipeDirection="right"
    >
      <DrawerContent className="[--drawer-content-width:min(100%,32rem)]">
        <DrawerHeader className="border-b p-5 pr-14 pb-5 text-left">
          <DrawerTitle className="[overflow-wrap:anywhere]">
            {member?.name ?? "Member details"}
          </DrawerTitle>
          <DrawerDescription>
            Organization membership and activity.
          </DrawerDescription>
        </DrawerHeader>
        <Button
          className="absolute top-4 right-4 z-20"
          variant="ghost"
          size="icon"
          aria-label="Close member details"
          onClick={onClose}
        >
          <X aria-hidden="true" />
        </Button>
        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          {members.isSelectedLoading && member === null ? (
            <div className="space-y-4">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
            </div>
          ) : members.selectedErrorMessage !== null ? (
            <div
              className="border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
              role="alert"
            >
              {members.selectedErrorMessage}
            </div>
          ) : member !== null ? (
            <div className="space-y-8">
              <section className="space-y-3">
                <h3 className="text-sm font-medium">Identity</h3>
                <DetailRow label="Name">{member.name}</DetailRow>
                <DetailRow label="Email">
                  <span className="break-all">{member.email}</span>
                </DetailRow>
                <DetailRow label="Status">
                  <Badge variant="outline">
                    {formatMemberStatus(member.status)}
                  </Badge>
                </DetailRow>
              </section>
              <section className="space-y-3">
                <h3 className="text-sm font-medium">Activity</h3>
                <DetailRow label="Last login">
                  <DateValue value={member.lastLogin} />
                </DetailRow>
                <DetailRow label="Joined">
                  <DateValue value={member.createdAt} />
                </DetailRow>
              </section>
              <section className="space-y-3">
                <h3 className="text-sm font-medium">References</h3>
                <DetailRow label="Member ID">
                  <code className="break-all text-xs">{member.id}</code>
                </DetailRow>
                <DetailRow label="Organization ID">
                  <code className="break-all text-xs">
                    {member.organizationId}
                  </code>
                </DetailRow>
              </section>
            </div>
          ) : null}
        </div>
      </DrawerContent>
    </Drawer>
  );
});

function DetailRow({
  children,
  label,
}: {
  children: React.ReactNode;
  label: string;
}) {
  return (
    <div className="grid gap-1 border-b pb-3 last:border-0 sm:grid-cols-[8rem_minmax(0,1fr)]">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-sm break-words">{children}</dd>
    </div>
  );
}

function DateValue({ value }: { value: string | null | undefined }) {
  const formatted = formatMemberDate(value);
  return formatted.exact === null ? (
    formatted.label
  ) : (
    <time dateTime={formatted.exact}>{formatted.label}</time>
  );
}

export { MemberDetailsDrawer };
