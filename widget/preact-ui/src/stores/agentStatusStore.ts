// stores/agentStatusStore.ts
import type { Eylo } from "@eylo/sdk/Eylo";

/**
 * Agent status for a specific conversation
 */
export interface AgentStatus {
  type: "thinking" | "processing" | "tool_executing" | "tool_completed" | "complete" | "error";
  message?: string;
  conversationId: string;
  requestId: string;
  runId: string;
  runStartedAt: string;
  sequence: number;
  terminal: boolean;
  outcome?: "completed" | "failed";
  timestamp: number;
}

/**
 * Global singleton store to track agent status across all conversations
 *
 * Ensures status persists when navigating between views and prevents
 * duplicate event subscriptions
 */
class AgentStatusStore {
  private statuses = new Map<string, AgentStatus>();
  private terminalRuns = new Map<string, Map<string, number>>();
  private listeners = new Set<() => void>();
  private eyloSDK: Eylo | undefined;
  private unsubscribeFromSDK: (() => void) | null = null;

  /**
   * Initialize the store with SDK instance and start listening to status events
   */
  initialize(eyloSDK: Eylo) {
    if (this.eyloSDK === eyloSDK && this.unsubscribeFromSDK) {
      return; // Already initialized with this SDK
    }

    // Clean up previous subscription if any
    if (this.unsubscribeFromSDK) {
      this.unsubscribeFromSDK();
    }

    this.eyloSDK = eyloSDK;

    // @ts-ignore - Subscribe to agent status changes globally
    this.unsubscribeFromSDK = eyloSDK.agentService.onStatusChange((status: any) => {
      if (!status.conversationId) {
        console.warn("[AgentStatusStore] Received status without conversationId:", status);
        return;
      }

      this.updateStatus({
        type: status.type,
        message: status.message,
        conversationId: status.conversationId,
        requestId: status.requestId,
        runId: status.runId,
        runStartedAt: status.runStartedAt,
        sequence: status.sequence,
        terminal: status.terminal,
        outcome: status.outcome,
        timestamp: Date.now(),
      });
    });

    console.log("[AgentStatusStore] Initialized and listening to agent status changes");
  }

  /**
   * Update status for a conversation and notify listeners
   */
  private updateStatus(status: AgentStatus) {
    const conversationId = status.conversationId;
    const previous = this.statuses.get(conversationId);

    if (this.hasTerminalRun(conversationId, status.runId) && !status.terminal) {
      return;
    }

    if (previous && !this.isAtLeastAsRecent(status, previous)) {
      return;
    }

    if (status.terminal) {
      this.recordTerminalRun(conversationId, status.runId);
      if (previous?.runId !== status.runId && previous) {
        return;
      }
      if (status.type === "error") {
        this.statuses.set(conversationId, status);
      } else {
        this.statuses.delete(conversationId);
      }
      this.notifyListeners();
      return;
    }

    this.statuses.set(conversationId, status);
    console.log("[AgentStatusStore] Updated status:", conversationId, status.type);
    this.notifyListeners();
  }

  /**
   * Get current status for a conversation
   */
  getStatus(conversationId: string | undefined): AgentStatus | null {
    if (!conversationId) return null;

    return this.statuses.get(conversationId) || null;
  }

  /**
   * Check if agent is actively working (not complete or error)
   */
  isWorking(conversationId: string | undefined): boolean {
    const status = this.getStatus(conversationId);
    if (!status) return false;

    return (
      status.type === "thinking" ||
      status.type === "processing" ||
      status.type === "tool_executing" ||
      status.type === "tool_completed"
    );
  }

  /**
   * Subscribe to status changes
   */
  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /**
   * Notify all listeners
   */
  private notifyListeners() {
    this.listeners.forEach((listener) => listener());
  }

  private hasTerminalRun(conversationId: string, runId: string): boolean {
    return this.terminalRuns.get(conversationId)?.has(runId) === true;
  }

  private recordTerminalRun(conversationId: string, runId: string): void {
    const runs = this.terminalRuns.get(conversationId) || new Map<string, number>();
    runs.set(runId, Date.now());
    while (runs.size > 32) {
      const oldest = runs.keys().next().value;
      if (!oldest) break;
      runs.delete(oldest);
    }
    this.terminalRuns.set(conversationId, runs);
  }

  private isAtLeastAsRecent(next: AgentStatus, current: AgentStatus): boolean {
    if (next.runId === current.runId) {
      return next.sequence > current.sequence;
    }
    return Date.parse(next.runStartedAt) >= Date.parse(current.runStartedAt);
  }

  /**
   * Get all active statuses (for debugging)
   */
  getAll(): Map<string, AgentStatus> {
    return new Map(this.statuses);
  }

  /**
   * Clean up
   */
  destroy() {
    if (this.unsubscribeFromSDK) {
      this.unsubscribeFromSDK();
      this.unsubscribeFromSDK = null;
    }
    this.statuses.clear();
    this.terminalRuns.clear();
    this.listeners.clear();
    this.eyloSDK = undefined;
    console.log("[AgentStatusStore] Destroyed");
  }
}

// Singleton instance
export const agentStatusStore = new AgentStatusStore();
