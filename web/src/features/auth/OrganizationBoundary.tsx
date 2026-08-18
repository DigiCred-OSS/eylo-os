import { observer } from "mobx-react-lite";
import { Outlet, useParams } from "react-router";

import { NotFoundPage } from "@/app/NotFoundPage";
import { useRootStore } from "@/app/use-root-store";

const OrganizationBoundary = observer(function OrganizationBoundary() {
  const { auth } = useRootStore();
  const { organizationId } = useParams();

  if (
    organizationId === undefined ||
    auth.organizationId === null ||
    organizationId !== auth.organizationId
  ) {
    return <NotFoundPage />;
  }

  return <Outlet />;
});

export { OrganizationBoundary };
