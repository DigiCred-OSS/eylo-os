import { createContext } from "react";

import type { RootStore } from "@/app/root.store";

const RootStoreContext = createContext<RootStore | null>(null);

export { RootStoreContext };
