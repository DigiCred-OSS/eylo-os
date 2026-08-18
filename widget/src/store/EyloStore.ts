import { BaseReactiveStore } from "@eylo/base/BaseReactiveStore";
import { EventEmitter } from "@eylo/events";
import { AgentStore } from "@eylo/modules/agent/store";
import { ContactStore } from "@eylo/modules/contact";
import { ConversationStore } from "@eylo/modules/conversation";
import { ParticipantStore } from "@eylo/modules/participant/store";
import { VoiceStore } from "@eylo/modules/voice/store";
import { ConnectionStore } from "@eylo/net";

export type TEyloAppState = {
  organizationId: string;
  sessionContactId?: string;
  contactStore?: ContactStore;
  conversationStore?: ConversationStore;
  connectionManager?: ConnectionStore;
  participantStore?: ParticipantStore;
  agentStore?: AgentStore;
  voiceStore?: VoiceStore;
  ee: EventEmitter;
};

class EyloStore extends BaseReactiveStore<TEyloAppState> {
  constructor(organizationId: string, eventEmitter: EventEmitter) {
    const initialState = {
      organizationId,
      ee: eventEmitter,
    };
    super(initialState);
    this.__init__();
  }

  private __init__ = (): void => {
    const contactStore = new ContactStore(this);
    const connectionManager = new ConnectionStore(this);
    const conversationStore = new ConversationStore(this);
    const participantStore = new ParticipantStore(this);
    const agentStore = new AgentStore(this);
    const voiceStore = new VoiceStore(this);
    this.set("conversationStore", conversationStore);
    this.set("contactStore", contactStore);
    this.set("connectionManager", connectionManager);
    this.set("participantStore", participantStore);
    this.set("agentStore", agentStore);
    this.set("voiceStore", voiceStore);
  };

  get cm(): ConnectionStore {
    return this.get("connectionManager")!;
  }

  get ee(): EventEmitter {
    return this.get("ee");
  }

  get contactStore(): ContactStore {
    return this.get("contactStore")!;
  }

  get conversationStore(): ConversationStore {
    return this.get("conversationStore")!;
  }

  get participantStore(): ParticipantStore {
    return this.get("participantStore")!;
  }

  get organizationId(): string {
    return this.get("organizationId");
  }

  get sessionContactId(): string | undefined {
    return this.get("sessionContactId");
  }

  setSessionContactId(contactId: string): void {
    this.set("sessionContactId", contactId);
  }

  get agentStore(): AgentStore {
    return this.get("agentStore")!;
  }

  get voiceStore(): VoiceStore {
    return this.get("voiceStore")!;
  }

  get sessionId(): string | null {
    return this.cm.get("sessionId");
  }

  get userSessionId(): string | null {
    return this.cm.get("userSessionId");
  }

  get connectionStateManager() {
    return this.cm.connectionStateManager;
  }

  get store(): TEyloAppState {
    return this.state;
  }
}

export { EyloStore };
