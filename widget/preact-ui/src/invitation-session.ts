type WidgetSessionBootstrap = {
  organizationId: string;
  contactId: string;
  initialConversationId?: string;
  sessionToken: string;
  sessionExpiresAt: string;
};

type PendingExchange = {
  tokenDigest: string;
  requestId: string;
};

const INVITATION_QUERY_PARAM = "invitation";
const PENDING_EXCHANGE_KEY = "eylo.widget.pending-exchange.v1";
const SESSION_KEY = "eylo.widget.session.v1";
const INVITATION_UNAVAILABLE = "This chat invitation is unavailable.";

export class WidgetInvitationError extends Error {
  constructor() {
    super(INVITATION_UNAVAILABLE);
    this.name = "WidgetInvitationError";
  }
}

export class WidgetDevelopmentSessionError extends Error {
  constructor() {
    super(
      "Configure WIDGET_DEVELOPMENT_ORGANIZATION_ID and " +
        "WIDGET_DEVELOPMENT_CONTACT_ID on the local server."
    );
    this.name = "WidgetDevelopmentSessionError";
  }
}

export async function resolveWidgetSession(): Promise<WidgetSessionBootstrap | null> {
  const url = new URL(window.location.href);
  const token = url.searchParams.get(INVITATION_QUERY_PARAM);
  if (!token) {
    return readActiveSession() ?? createDevelopmentSession();
  }

  if (token.length < 32 || token.length > 512) {
    clearInvitationFromUrl(url);
    throw new WidgetInvitationError();
  }

  const tokenDigest = await digestToken(token);
  const pendingExchange = readJson<PendingExchange>(PENDING_EXCHANGE_KEY);
  const requestId =
    pendingExchange?.tokenDigest === tokenDigest ? pendingExchange.requestId : crypto.randomUUID();

  writeJson(PENDING_EXCHANGE_KEY, { tokenDigest, requestId });

  let response: Response;
  try {
    response = await fetch("/api/public/widget-invitations/exchange", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, requestId }),
    });
  } catch {
    throw new WidgetInvitationError();
  }

  if (!response.ok) {
    removeStoredValue(PENDING_EXCHANGE_KEY);
    clearInvitationFromUrl(url);
    throw new WidgetInvitationError();
  }

  let session: WidgetSessionBootstrap;
  try {
    const invitation = (await response.json()) as Record<string, unknown>;
    session = parseSession({
      ...invitation,
      initialConversationId: invitation.conversationId,
    });
  } catch {
    removeStoredValue(PENDING_EXCHANGE_KEY);
    clearInvitationFromUrl(url);
    throw new WidgetInvitationError();
  }
  writeJson(SESSION_KEY, session);
  removeStoredValue(PENDING_EXCHANGE_KEY);
  clearInvitationFromUrl(url);
  return session;
}

async function createDevelopmentSession(): Promise<WidgetSessionBootstrap> {
  let response: Response;
  try {
    response = await fetch("/api/public/widget-development/session", {
      method: "POST",
    });
  } catch {
    throw new WidgetDevelopmentSessionError();
  }
  if (!response.ok) {
    throw new WidgetDevelopmentSessionError();
  }
  try {
    const session = parseSession(await response.json());
    writeJson(SESSION_KEY, session);
    return session;
  } catch {
    throw new WidgetDevelopmentSessionError();
  }
}

function readActiveSession(): WidgetSessionBootstrap | null {
  const session = readJson<WidgetSessionBootstrap>(SESSION_KEY);
  if (!session || !isSession(session) || Date.parse(session.sessionExpiresAt) <= Date.now()) {
    removeStoredValue(SESSION_KEY);
    return null;
  }
  return session;
}

function parseSession(value: unknown): WidgetSessionBootstrap {
  if (!isSession(value) || Date.parse(value.sessionExpiresAt) <= Date.now()) {
    throw new WidgetInvitationError();
  }
  return value;
}

function isSession(value: unknown): value is WidgetSessionBootstrap {
  if (!value || typeof value !== "object") {
    return false;
  }
  const session = value as Record<string, unknown>;
  return (
    typeof session.organizationId === "string" &&
    typeof session.contactId === "string" &&
    (session.initialConversationId === undefined ||
      typeof session.initialConversationId === "string") &&
    typeof session.sessionToken === "string" &&
    session.sessionToken.length >= 32 &&
    typeof session.sessionExpiresAt === "string" &&
    Number.isFinite(Date.parse(session.sessionExpiresAt))
  );
}

async function digestToken(token: string): Promise<string> {
  const bytes = new TextEncoder().encode(token);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function readJson<T>(key: string): T | null {
  try {
    const value = sessionStorage.getItem(key);
    return value ? (JSON.parse(value) as T) : null;
  } catch {
    removeStoredValue(key);
    return null;
  }
}

function writeJson(key: string, value: unknown): void {
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    // The live session remains usable when browser storage is unavailable.
  }
}

function removeStoredValue(key: string): void {
  try {
    sessionStorage.removeItem(key);
  } catch {
    // Storage may be unavailable in privacy modes.
  }
}

function clearInvitationFromUrl(url: URL): void {
  url.searchParams.delete(INVITATION_QUERY_PARAM);
  const visibleUrl = `${url.pathname}${url.search}${url.hash}`;
  window.history.replaceState(window.history.state, "", visibleUrl);
}

export type { WidgetSessionBootstrap };
