// main.tsx
import { Eylo } from "@eylo/sdk";
import { createContext, render } from "preact";
import type { FC } from "preact/compat";
import { useContext, useEffect, useState } from "preact/hooks";
import { merge } from "es-toolkit";

import { App } from "./app.tsx";
import WidgetSamplesScreen from "./components/WidgetSamplesScreen";
import { logger } from "./utils/logging.ts";
import { applyTheme } from "./design-system/theme/apply.ts";
import { presetThemes } from "./design-system/theme/presets.ts";
import type { EyloTheme } from "./design-system/theme/types.ts";
import { registerDynamicWidgetComponents } from "./design-system/compositions/register.ts";
import { useApplySystemTheme } from "./hooks/useSystemTheme.ts";
import {
  resolveWidgetSession,
  WidgetDevelopmentSessionError,
  WidgetInvitationError,
  type WidgetSessionBootstrap,
} from "./invitation-session.ts";

import "./styles.css";

registerDynamicWidgetComponents();

/**
 * Resolve theme configuration
 * Handles string presets, object themes with preset merging, and defaults
 */
function resolveTheme(
  theme?: Partial<EyloTheme> | "minimal" | "rounded" | "bold" | "compact" | "spacious"
): EyloTheme {
  // No theme provided - use default 'minimal'
  if (!theme) {
    return presetThemes.minimal.theme;
  }

  // String preset - apply directly
  if (typeof theme === "string") {
    const presetConfig = presetThemes[theme];
    if (presetConfig) {
      return presetConfig.theme;
    }
    console.warn(`Unknown preset: "${theme}". Falling back to 'minimal'.`);
    return presetThemes.minimal.theme;
  }

  // Object theme with preset - merge preset with overrides
  if (theme.preset) {
    const presetConfig = presetThemes[theme.preset];
    if (presetConfig) {
      return merge(presetConfig.theme, theme) as EyloTheme;
    }
    console.warn(`Unknown preset: "${theme.preset}". Using custom theme only.`);
  }

  // Object theme without preset - use as-is
  return theme as EyloTheme;
}

const isWidgetSamplesMode = (): boolean => {
  if (typeof window === "undefined") {
    return false;
  }

  return new URLSearchParams(window.location.search).get("samples") === "1";
};

type TEyloProviderProps = {
  organizationId: string;
  contactId: string;
  sessionToken: string;
  initialConversationId?: string;
  theme?: Partial<EyloTheme> | "minimal" | "rounded" | "bold" | "compact" | "spacious";
};
declare global {
  interface Window {
    Eylo: Eylo | null; // Global reference to the Eylo SDK instance
    EyloWidget: {
      widget: FC<TEyloProviderProps>;
      initialize: (props: TEyloProviderProps) => void;
      destroy: () => void;
    };
  }
}

// Enhanced context type with all store access
type TEyloContext = {
  eyloSDK: Eylo;
  isConnected: boolean;
  stores: {
    connection: Eylo["store"]["cm"];
    contact: Eylo["store"]["contactStore"];
    conversation: Eylo["store"]["conversationStore"];
    participant: Eylo["store"]["participantStore"];
  };
  services: {
    contact: Eylo["contactService"];
    conversation: Eylo["conversationService"];
    message: Eylo["messageService"];
    participant: Eylo["participantService"];
  };
};

export const EyloSDKContext = createContext<TEyloContext | null>(null);

export const useEyloSDK = (): TEyloContext => {
  const context = useContext(EyloSDKContext);
  if (!context) {
    throw new Error("useEyloSDK must be used within an EyloSDKProvider");
  }
  return context;
};

const EyloProvider: FC<TEyloProviderProps> = ({
  organizationId,
  contactId,
  sessionToken,
  initialConversationId,
  theme,
}) => {
  const [eyloSDK, setEyloSDK] = useState<Eylo | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [isInitializing, setIsInitializing] = useState(true);
  const [isInitialized, setIsInitialized] = useState<boolean>(false);
  const [hasUserSession, setHasUserSession] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Apply system theme automatically
  useApplySystemTheme();

  // Apply theme with preset merging support
  useEffect(() => {
    const widgetRoot = document.getElementById("eylo-widget");
    const targetElement = widgetRoot || document.documentElement;

    const resolvedTheme = resolveTheme(theme);
    applyTheme(targetElement, resolvedTheme);
  }, [theme]);

  useEffect(() => {
    let sdk: Eylo;
    try {
      // Step 1: Instantiate SDK. This is the critical part.
      sdk = new Eylo(organizationId);
      setEyloSDK(sdk);
      setHasUserSession(Boolean(sdk.store.cm.get("userSessionId")));
    } catch (e: any) {
      setError(e.message || "An unknown error occurred during instantiation.");
      return; // Stop execution
    } finally {
      setIsInitializing(false);
    }

    // If instantiation succeeded, proceed with initialization and listeners.
    const handleConnected = () => {
      setIsConnected(true);
    };
    const handleDisconnected = () => setIsConnected(false);
    sdk.ee.on("eylo:net:connected", handleConnected);
    sdk.ee.on("eylo:net:disconnected", handleDisconnected);

    const unsubscribeConnection = sdk.store.cm.subscribe("isConnected", (detail) => {
      setIsConnected(detail.value || false);
    });
    const unsubscribeUserSession = sdk.store.cm.subscribe("userSessionId", (detail) => {
      setHasUserSession(Boolean(detail.value));
    });

    window.Eylo = sdk;

    sdk
      .initialize(sessionToken, contactId)
      .then(() => {
        setIsInitialized(true);
      })
      .catch((e: any) => {
        setError(e.message || "An unknown error occurred during initialization.");
      })
      .finally(() => {
        setIsInitializing(false);
      });

    // Cleanup
    return () => {
      unsubscribeConnection();
      unsubscribeUserSession();
      sdk.ee.off("eylo:net:connected", handleConnected);
      sdk.ee.off("eylo:net:disconnected", handleDisconnected);
      sdk.suspend();
      window.Eylo = null;
    };
  }, [contactId, organizationId, sessionToken]);

  if (isInitializing) {
    return <div>Initializing Session...</div>;
  }

  if (error) {
    return <div>Error: {error}</div>;
  }

  if (!eyloSDK) {
    // This case should ideally not be reached if logic is correct, but it's a safeguard.
    return <div>Error: Eylo SDK could not be loaded.</div>;
  }

  const contextValue: TEyloContext = {
    eyloSDK,
    isConnected,
    stores: {
      connection: eyloSDK.store.cm,
      contact: eyloSDK.store.contactStore,
      conversation: eyloSDK.store.conversationStore,
      participant: eyloSDK.store.participantStore,
    },
    services: {
      contact: eyloSDK.contactService,
      conversation: eyloSDK.conversationService,
      message: eyloSDK.messageService,
      participant: eyloSDK.participantService,
    },
  };

  return (
    <EyloSDKContext.Provider value={contextValue}>
      {isInitialized && isConnected && hasUserSession && (
        <App initialConversationId={initialConversationId} />
      )}
    </EyloSDKContext.Provider>
  );
};

if (isWidgetSamplesMode()) {
  const rootElement = document.getElementById("eylo-widget");

  if (rootElement) {
    render(<WidgetSamplesScreen />, rootElement);
  }
} else {
  window.EyloWidget = {
    widget: EyloProvider,
    initialize: (props: TEyloProviderProps) => {
      logger.debug("Initializing EyloWidget.");
      let rootElement = document.getElementById("eylo-widget");
      if (!rootElement) {
        rootElement = document.createElement("div");
        rootElement.id = "eylo-widget";
        document.body.appendChild(rootElement);
      }
      logger.debug("Rendering EyloProvider.");
      render(<EyloProvider {...props} />, rootElement);
    },
    destroy: () => {
      if (window.Eylo) {
        window.Eylo.terminate();
      }
      const rootElement = document.getElementById("eylo-widget");
      if (rootElement) {
        render(null, rootElement);
        rootElement.remove();
      }
      window.Eylo = null;
    },
  };

  void initializeStandaloneWidget();
}

async function initializeStandaloneWidget(): Promise<void> {
  try {
    const session = await resolveWidgetSession();
    if (session) {
      initializeSession(session);
      return;
    }
  } catch (error) {
    renderInvitationError(error);
  }
}

function initializeSession(session: WidgetSessionBootstrap): void {
  window.EyloWidget.initialize({
    organizationId: session.organizationId,
    contactId: session.contactId,
    sessionToken: session.sessionToken,
    initialConversationId: session.initialConversationId,
  });
}

function renderInvitationError(error: unknown): void {
  const rootElement = document.getElementById("eylo-widget");
  if (!rootElement) {
    return;
  }
  const message =
    error instanceof WidgetInvitationError || error instanceof WidgetDevelopmentSessionError
      ? error.message
      : "The chat could not be started.";
  render(<div role="alert">{message}</div>, rootElement);
}

// Export individual store hooks for convenience
export const useEyloStores = () => {
  const { stores } = useEyloSDK();
  return stores;
};

export const useEyloServices = () => {
  const { services } = useEyloSDK();
  return services;
};
