import { logger } from "@eylo/utils";
import type { TVoiceConnectionState, VoiceVendorServiceState } from "./types";

/**
 * Valid state transitions for WebRTC voice connection
 * Key: Current state
 * Value: Array of valid next states
 */
const STATE_TRANSITIONS: Record<TVoiceConnectionState, TVoiceConnectionState[]> = {
  DISCONNECTED: ["CONNECTING", "ERROR"],

  CONNECTING: ["NEGOTIATING", "ERROR", "DISCONNECTED"],

  NEGOTIATING: ["ICE_CHECKING", "ERROR", "FAILED", "DISCONNECTED"],

  ICE_CHECKING: ["CONNECTED", "FAILED", "RECONNECTING", "ERROR", "DISCONNECTED"],

  CONNECTED: ["RECONNECTING", "FAILED", "DISCONNECTED"],

  RECONNECTING: ["CONNECTED", "FAILED", "DISCONNECTED"],

  FAILED: ["DISCONNECTED", "CONNECTING"],

  ERROR: ["DISCONNECTED", "CONNECTING"],
};

/**
 * Descriptions for each state (useful for logging and debugging)
 */
export const STATE_DESCRIPTIONS: Record<TVoiceConnectionState, string> = {
  DISCONNECTED: "No active connection",
  CONNECTING: "Getting microphone access and setting up connection",
  NEGOTIATING: "WebRTC offer/answer exchange in progress",
  ICE_CHECKING: "Finding best connection path (STUN/TURN)",
  CONNECTED: "Fully connected, audio flowing, ready to speak",
  RECONNECTING: "Connection lost, attempting to reconnect",
  FAILED: "Connection failed",
  ERROR: "Error occurred during setup",
};

/**
 * Voice Connection State Machine
 * Manages state transitions with validation and logging
 */
export class VoiceConnectionStateMachine {
  private _currentState: TVoiceConnectionState = "DISCONNECTED";
  private _stateHistory: Array<{ state: TVoiceConnectionState; timestamp: Date; reason?: string }> =
    [];

  /**
   * Get the current connection state
   */
  get currentState(): TVoiceConnectionState {
    return this._currentState;
  }

  /**
   * Get the state transition history (useful for debugging)
   */
  get stateHistory() {
    return [...this._stateHistory];
  }

  /**
   * Check if a state transition is valid
   */
  canTransitionTo(nextState: TVoiceConnectionState): boolean {
    const allowedTransitions = STATE_TRANSITIONS[this._currentState];
    return allowedTransitions.includes(nextState);
  }

  /**
   * Get all valid next states from current state
   */
  getValidNextStates(): TVoiceConnectionState[] {
    return [...STATE_TRANSITIONS[this._currentState]];
  }

  /**
   * Transition to a new state with validation
   * @param nextState - The state to transition to
   * @param reason - Optional reason for the transition (for logging)
   * @param force - Force transition even if invalid (use sparingly)
   * @returns true if transition was successful
   */
  transition(nextState: TVoiceConnectionState, reason?: string, force: boolean = false): boolean {
    // Check if transition is valid
    if (!force && !this.canTransitionTo(nextState)) {
      logger.warn(
        `[VoiceStateMachine] Invalid transition: ${this._currentState} → ${nextState}` +
        `\nAllowed transitions from ${this._currentState}: ${this.getValidNextStates().join(", ")}` +
        (reason ? `\nReason: ${reason}` : "")
      );
      return false;
    }

    const previousState = this._currentState;
    this._currentState = nextState;

    // Record state change in history
    this._stateHistory.push({
      state: nextState,
      timestamp: new Date(),
      reason,
    });

    // Keep history size manageable (last 50 transitions)
    if (this._stateHistory.length > 50) {
      this._stateHistory.shift();
    }

    // Log the transition
    const transitionLog =
      `[VoiceStateMachine] ${previousState} → ${nextState}` +
      (reason ? ` (${reason})` : "") +
      `\n  ${STATE_DESCRIPTIONS[nextState]}`;

    logger.debug(transitionLog);

    return true;
  }

  /**
   * Reset state machine to initial state
   */
  reset(): void {
    this.transition("DISCONNECTED", "State machine reset", true);
  }

  /**
   * Get a formatted string of the state transition history
   */
  getHistoryLog(): string {
    return this._stateHistory
      .map((entry, index) => {
        const time = entry.timestamp.toISOString().split("T")[1].split(".")[0];
        const reason = entry.reason ? ` - ${entry.reason}` : "";
        return `${index + 1}. [${time}] ${entry.state}${reason}`;
      })
      .join("\n");
  }

  /**
   * Check if currently in a "connected" family of states
   * (states where user can interact with the system)
   */
  isConnectedState(): boolean {
    return ["CONNECTED", "RECONNECTING"].includes(this._currentState);
  }

  /**
   * Check if currently in a "connecting" family of states
   * (states during connection establishment)
   */
  isConnectingState(): boolean {
    return ["CONNECTING", "NEGOTIATING", "ICE_CHECKING"].includes(this._currentState);
  }

  /**
   * Check if currently in an error/failed state
   */
  isErrorState(): boolean {
    return ["ERROR", "FAILED"].includes(this._currentState);
  }

  /**
   * Check if connection is active (any state except DISCONNECTED)
   */
  isActive(): boolean {
    return this._currentState !== "DISCONNECTED";
  }
}

type VoiceVendorTransitionResult = {
  changed: boolean;
  state: VoiceVendorServiceState | null;
};

const VENDOR_STARTUP_STATES: VoiceVendorServiceState[] = ["connecting", "connected"];

const VENDOR_STATE_TRANSITIONS: Record<VoiceVendorServiceState, VoiceVendorServiceState[]> = {
  connecting: ["connected", "ready", "disconnected", "error"],
  connected: ["ready", "disconnected", "error"],
  ready: ["disconnected", "error"],
  disconnected: ["connecting", "connected", "ready", "error"],
  error: ["connecting", "connected", "ready", "disconnected"],
};

export class VoiceVendorStateMachine {
  private _currentState: VoiceVendorServiceState | null = null;
  private readonly _label: string;

  constructor(label: string) {
    this._label = label;
  }

  get currentState(): VoiceVendorServiceState | null {
    return this._currentState;
  }

  transition(nextState: VoiceVendorServiceState): VoiceVendorTransitionResult {
    if (this._currentState === nextState) {
      return { changed: false, state: this._currentState };
    }

    if (!this.canTransitionTo(nextState)) {
      logger.debug(
        `[VoiceVendorStateMachine:${this._label}] Ignoring stale transition: ${this._currentState} → ${nextState}`
      );
      return { changed: false, state: this._currentState };
    }

    const previousState = this._currentState;
    this._currentState = nextState;
    logger.debug(
      `[VoiceVendorStateMachine:${this._label}] ${previousState ?? "idle"} → ${nextState}`
    );
    return { changed: true, state: this._currentState };
  }

  reset(): void {
    this._currentState = null;
  }

  private canTransitionTo(nextState: VoiceVendorServiceState): boolean {
    if (!this._currentState) {
      return true;
    }

    if (this._currentState === "ready" && VENDOR_STARTUP_STATES.includes(nextState)) {
      return false;
    }

    return VENDOR_STATE_TRANSITIONS[this._currentState].includes(nextState);
  }
}
