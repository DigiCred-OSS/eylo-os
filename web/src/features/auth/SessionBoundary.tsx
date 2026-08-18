import { useEffect } from "react";
import { observer } from "mobx-react-lite";
import { Navigate, Outlet, useLocation } from "react-router";

import { FullPageStatus } from "@/app/FullPageStatus";
import { useRootStore } from "@/app/use-root-store";
import { SessionUnavailable } from "@/features/auth/SessionUnavailable";

const SessionBoundary = observer(function SessionBoundary() {
  const { auth } = useRootStore();
  const location = useLocation();

  useEffect(() => {
    void auth.hydrate();
  }, [auth]);

  if (auth.status === "checking") {
    return <FullPageStatus message="Verifying session…" />;
  }

  if (auth.status === "unavailable") {
    return <SessionUnavailable />;
  }

  if (auth.status === "anonymous") {
    return (
      <Navigate
        replace
        to="/login"
        state={{ returnTo: `${location.pathname}${location.search}` }}
      />
    );
  }

  return <Outlet />;
});

export { SessionBoundary };
