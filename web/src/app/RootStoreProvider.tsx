import type { PropsWithChildren } from "react";

import { RootStoreContext } from "@/app/root-store-context";
import type { RootStore } from "@/app/root.store";

interface RootStoreProviderProps extends PropsWithChildren {
  store: RootStore;
}

function RootStoreProvider({ children, store }: RootStoreProviderProps) {
  return (
    <RootStoreContext.Provider value={store}>
      {children}
    </RootStoreContext.Provider>
  );
}

export { RootStoreProvider };
