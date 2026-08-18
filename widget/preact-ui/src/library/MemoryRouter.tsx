import { isEqual } from "es-toolkit";
import type { ComponentChildren } from "preact";
import { createContext } from "preact";
import { useContext, useState } from "preact/hooks";

import { useLogger } from "../hooks/useEyloAdvanced";

// Route context type definitions
type TRouteParams = Record<string, string | undefined>;

type TRouteContext = {
  currentPath: string;
  params: TRouteParams;
  setParams: (params: TRouteParams) => void;
  navigate: (path: string) => void;
  goBack: () => void;
};

// Create context
const RouterContext = createContext<TRouteContext | null>(null);

// Memory router provider component
interface MemoryRouterProps {
  children: ComponentChildren;
  initialPath?: string;
}

const INITIAL_PATH = "/";

export const MemoryRouter = ({ children, initialPath = INITIAL_PATH }: MemoryRouterProps) => {
  const { debug } = useLogger();
  const [currentPath, setCurrentPath] = useState<string>(initialPath);
  const [pathStack, setPathStack] = useState<string[]>([]);
  const params: TRouteParams = {};

  const setParams = (newParams: TRouteParams) => {
    debug("Setting params:", newParams);
    if (!isEqual(params, newParams)) {
      Object.assign(params, newParams);
    }
  };

  const navigate = (path: string) => {
    if (path !== currentPath) {
      setCurrentPath(path);
      if (path === INITIAL_PATH) {
        setPathStack([]); // Clear stack if navigating to initial path
      } else {
        setPathStack((prevStack) => {
          // Add new path to stack, avoiding duplicates
          if (prevStack[prevStack.length - 1] !== path) {
            return [...prevStack, path];
          }
          return prevStack;
        });
      }
    }
  };

  const goBack = () => {
    const prevPath = pathStack.length > 1 ? pathStack[pathStack.length - 2] : null;
    const popPath = prevPath || INITIAL_PATH; // Fallback to initial path if no previous path
    if (popPath) {
      setCurrentPath(popPath);
      if (popPath === INITIAL_PATH) {
        setPathStack([]);
      } else {
        setPathStack((prevStack) => {
          const newStack = prevStack.slice(0, -1);
          return newStack;
        });
      }
    }
  };

  const contextValue: TRouteContext = {
    currentPath,
    params,
    setParams,
    navigate,
    goBack,
  };
  debug("MemoryRouter context value:", contextValue);
  return <RouterContext.Provider value={contextValue}>{children}</RouterContext.Provider>;
};

// Route component
// Parse route parameters
const _matchRoute = (
  routePath: string,
  currentPath: string
): { matches: boolean; params: TRouteParams } => {
  // Handle exact root path match
  if (routePath === INITIAL_PATH && currentPath === INITIAL_PATH) {
    return { matches: true, params: {} };
  }

  // Handle root path not matching non-root paths
  if (routePath === INITIAL_PATH && currentPath !== INITIAL_PATH) {
    return { matches: false, params: {} };
  }

  const routeParts = routePath.split("/").filter(Boolean);
  const currentParts = currentPath.split("/").filter(Boolean);

  if (routeParts.length !== currentParts.length) {
    return { matches: false, params: {} };
  }

  const params: TRouteParams = {};
  let matches = true;

  for (let i = 0; i < routeParts.length; i++) {
    const routePart = routeParts[i];
    const currentPart = currentParts[i];

    if (routePart.startsWith(":")) {
      // This is a parameter
      const paramName = routePart.slice(1);
      params[paramName] = currentPart;
    } else if (routePart !== currentPart) {
      matches = false;
      break;
    }
  }

  return { matches, params };
};
interface RouteProps {
  path: string;
  component?: () => any;
  children?: ComponentChildren;
}

export const Route = ({ path, component: Component, children }: RouteProps) => {
  const { debug } = useLogger();
  const context = useContext(RouterContext);

  if (!context) {
    throw new Error("Route must be used within a MemoryRouter");
  }

  const { currentPath, setParams } = context;

  const { matches, params } = _matchRoute(path, currentPath);

  if (matches) {
    setParams(params);
  } else {
    return null;
  }
  debug("Rendering route:", path, "with params:", params);
  return Component ? <Component /> : <>{children}</>;
};

// Hook to access router context
export const useMemoryRouter = () => {
  const context = useContext(RouterContext);

  if (!context) {
    throw new Error("useMemoryRouter must be used within a MemoryRouter");
  }

  return context;
};

// Hook to get route parameters
export const useRouteParams = () => {
  const { params } = useMemoryRouter();

  return params;
};

// Hook to get current path
export const useCurrentPath = () => {
  const { currentPath } = useMemoryRouter();
  return currentPath;
};

// Hook for navigation
export const useNavigate = () => {
  const context = useContext(RouterContext);
  if (!context) {
    throw new Error("useNavigate must be used within a MemoryRouter");
  }
  // here we will have two options
  // user can pass params and path
  // in that case we will try to match the path with params
  // and build the path with params
  // or user can just pass path
  const _navigate = (path: string, params?: TRouteParams) => {
    // path here will be the router path ex: "/conversation/:id"
    // and params will be for example { id: "123" }
    if (params) {
      // Build the path with params
      const pathWithParams = Object.keys(params).reduce((acc, key) => {
        return acc.replace(`:${key}`, encodeURIComponent(params[key] || ""));
      }, path);
      context.navigate(pathWithParams);
    } else {
      // Just navigate to the path
      context.navigate(path);
    }
  };
  return _navigate;
};

export const useGoBack = () => {
  const context = useContext(RouterContext);
  if (!context) {
    throw new Error("useGoBack must be used within a MemoryRouter");
  }
  return context.goBack;
};
