import { useCallback, useLayoutEffect, useRef } from "react";

function useAsyncContextGuard(
  contextKey: string,
): (expectedContextKey: string) => boolean {
  const mounted = useRef(false);
  const currentContextKey = useRef(contextKey);

  useLayoutEffect(() => {
    mounted.current = true;
    currentContextKey.current = contextKey;
    return () => {
      mounted.current = false;
    };
  }, [contextKey]);

  return useCallback(
    (expectedContextKey: string) =>
      mounted.current && currentContextKey.current === expectedContextKey,
    [],
  );
}

export { useAsyncContextGuard };
