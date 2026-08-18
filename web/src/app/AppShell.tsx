import { LogOut, Menu } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useState } from "react";
import { NavLink, Outlet } from "react-router";

import { OrganizationNavigation } from "@/app/OrganizationNavigation";
import { ThemeToggle } from "@/app/ThemeToggle";
import { useRootStore } from "@/app/use-root-store";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from "@/components/ui/drawer";
import { Separator } from "@/components/ui/separator";

const AppShell = observer(function AppShell() {
  const { auth } = useRootStore();
  const member = auth.member;
  const [isMobileNavigationOpen, setMobileNavigationOpen] = useState(false);

  if (member === null) {
    return null;
  }

  return (
    <div className="min-h-svh bg-background md:grid md:grid-cols-[15rem_minmax(0,1fr)]">
      <a
        href="#main-content"
        className="sr-only z-50 rounded-md bg-background px-3 py-2 text-sm font-medium focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        Skip to content
      </a>

      <aside className="hidden overflow-hidden border-r bg-sidebar md:sticky md:top-0 md:flex md:h-svh md:flex-col">
        <div className="flex h-14 items-center px-4 text-sm font-semibold tracking-tight">
          Eylo
        </div>
        <Separator />
        <div className="min-h-0 flex-1 overflow-y-auto p-2 py-4">
          <OrganizationNavigation organizationId={member.organizationId} />
        </div>
        <Separator />
        <div className="space-y-3 p-4">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{member.name}</p>
            <p className="truncate text-xs text-muted-foreground">
              {member.email}
            </p>
          </div>
          <Button
            className="w-full justify-start"
            variant="ghost"
            onClick={() => void auth.logout()}
          >
            <LogOut aria-hidden="true" />
            Sign out
          </Button>
        </div>
      </aside>

      <div className="min-w-0 w-full max-w-full overflow-x-hidden">
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b bg-background/95 px-4 backdrop-blur sm:px-6">
          <div className="flex min-w-0 items-center gap-1 md:hidden">
            <Drawer
              open={isMobileNavigationOpen}
              swipeDirection="left"
              onOpenChange={setMobileNavigationOpen}
            >
              <DrawerTrigger
                render={
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Open navigation"
                    title="Open navigation"
                  />
                }
              >
                <Menu aria-hidden="true" />
              </DrawerTrigger>
              <DrawerContent>
                <DrawerHeader className="border-b pb-4 text-left">
                  <DrawerTitle>Eylo</DrawerTitle>
                  <DrawerDescription>Organization navigation</DrawerDescription>
                </DrawerHeader>
                <div className="min-h-0 flex-1 overflow-y-auto p-2 py-4">
                  <OrganizationNavigation
                    organizationId={member.organizationId}
                    onNavigate={() => setMobileNavigationOpen(false)}
                  />
                </div>
              </DrawerContent>
            </Drawer>
            <NavLink
              to={`/org/${member.organizationId}/agents`}
              className="truncate text-sm font-semibold tracking-tight"
            >
              Eylo
            </NavLink>
          </div>
          <div className="hidden min-w-0 md:block">
            <p className="truncate text-sm font-medium">{member.name}</p>
          </div>
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <Button
              className="md:hidden"
              variant="ghost"
              size="icon"
              aria-label="Sign out"
              title="Sign out"
              onClick={() => void auth.logout()}
            >
              <LogOut aria-hidden="true" />
            </Button>
          </div>
        </header>

        <main id="main-content" className="min-w-0 w-full max-w-full">
          <Outlet />
        </main>
      </div>
    </div>
  );
});

export { AppShell };
