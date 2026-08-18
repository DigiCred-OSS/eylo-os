import { useContext } from "react";

import { RootStoreContext } from "@/app/root-store-context";

function useRootStore() {
  const store = useContext(RootStoreContext);

  if (store === null) {
    throw new Error("useRootStore must be used inside RootStoreProvider");
  }

  return store;
}

export { useRootStore };
