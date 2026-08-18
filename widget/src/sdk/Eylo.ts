import { EventEmitter } from "@eylo/events";
import { AgentService } from "@eylo/modules/agent";
import { ContactService } from "@eylo/modules/contact";
import { ConversationService, type TConversationCreate } from "@eylo/modules/conversation";
import { MessageService } from "@eylo/modules/message/service";
import type { TMessageCreate, TWidgetResponseMessageCreate } from "@eylo/modules/message/types";
import { KnowledgeService } from "@eylo/modules/knowledge";
import { ParticipantService } from "@eylo/modules/participant/service";
import { VoiceService } from "@eylo/modules/voice/service";
import { EyloStore } from "@eylo/store";

class Eylo {
  private static _instance: Eylo | null = null;
  // @ts-ignore || __init__ will set these
  private _ee: EventEmitter;
  // @ts-ignore || __init__ will set these
  private _store: EyloStore;
  // @ts-ignore || __init__ will set these
  private _contactService: ContactService;
  // @ts-ignore || __init__ will set these
  private _conversationService: ConversationService;
  // @ts-ignore || __init__ will set these
  private _messageService: MessageService;
  // @ts-ignore || __init__ will set these
  private _participantService: ParticipantService;
  // @ts-ignore || __init__ will set these
  private _agentService: AgentService;
  // @ts-ignore || __init__ will set these
  private _voiceService: VoiceService;
  // @ts-ignore || __init__ will set this
  private _knowledgeService: KnowledgeService;

  constructor(organizationId: string) {
    if (Eylo._instance) {
      return Eylo._instance;
    }

    this.__init__(organizationId);
    Eylo._instance = this;
  }

  private __init__ = (organizationId: string): void => {
    this._ee = new EventEmitter();
    this._store = new EyloStore(organizationId, this._ee);
    this._contactService = new ContactService(this._store);
    this._conversationService = new ConversationService(this._store);
    this._messageService = new MessageService(this._store);
    this._participantService = new ParticipantService(this._store);
    this._agentService = new AgentService(this._store);
    this._voiceService = new VoiceService(this._store);
    this._knowledgeService = new KnowledgeService(this._store);
  };

  get ee(): EventEmitter {
    return this._ee;
  }
  get store(): EyloStore {
    return this._store;
  }
  get contactService(): ContactService {
    return this._contactService;
  }
  get conversationService(): ConversationService {
    return this._conversationService;
  }
  get messageService(): MessageService {
    return this._messageService;
  }
  get participantService(): ParticipantService {
    return this._participantService;
  }
  get agentService(): AgentService {
    return this._agentService;
  }
  get voiceService(): VoiceService {
    return this._voiceService;
  }
  get knowledgeService(): KnowledgeService {
    return this._knowledgeService;
  }
  // figure out a better way to expose the underlying methods
  public initialize = async (sessionToken: string, contactId?: string): Promise<void> => {
    if (contactId) {
      this._store.setSessionContactId(contactId);
    }
    await this._store.cm.connectWithSession(sessionToken, contactId);
  };
  public terminate = () => {
    this._store.cm.disconnect();
  };
  public suspend = () => {
    this._store.cm.disconnect(1000, "widget_unmounted", false);
  };
  public startConversation = (
    conversationRequest: TConversationCreate,
    requestId: string
  ): void => {
    this._conversationService.startConversation(conversationRequest, requestId);
  };
  public sendMessage = (request: TMessageCreate, requestId: string): boolean => {
    return this._messageService.sendMessage(request, requestId);
  };
  public sendWidgetResponse = (
    request: TWidgetResponseMessageCreate,
    requestId: string
  ): boolean => {
    return this._messageService.sendWidgetResponse(request, requestId);
  };
  public sendFeedback = (
    conversationId: string,
    requestId: string,
    feedback: "positive" | "negative"
  ): boolean => {
    return this._messageService.sendFeedback(conversationId, requestId, feedback);
  };
  public startVoiceSession = (conversationId: string): Promise<void> => {
    return this._voiceService.startVoiceSession(conversationId);
  };
  public stopVoiceSession = (): Promise<void> => {
    return this._voiceService.endVoiceCall();
  };
}

export { Eylo };
