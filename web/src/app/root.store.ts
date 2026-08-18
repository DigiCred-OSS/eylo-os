import { createApiClient, type ApiClient } from "@/api/client";
import { ThemeStore } from "@/app/theme.store";
import { AgentDraftStorage } from "@/features/agents/agent-draft-storage";
import { AgentInstructionDraftStorage } from "@/features/agents/agent-instruction-draft-storage";
import { AgentsStore } from "@/features/agents/agents.store";
import { AuthStore } from "@/features/auth/auth.store";
import { AutomationsService } from "@/features/automations/automations.service";
import { AutomationsStore } from "@/features/automations/automations.store";
import { BrowserTokenStorage } from "@/features/auth/token-storage";
import { CampaignsService } from "@/features/campaigns/campaigns.service";
import { CampaignsStore } from "@/features/campaigns/campaigns.store";
import { ConversationsService } from "@/features/conversations/conversations.service";
import { ConversationsStore } from "@/features/conversations/conversations.store";
import { ContactDraftStorage } from "@/features/contacts/contact-draft-storage";
import { ContactsService } from "@/features/contacts/contacts.service";
import { ContactsStore } from "@/features/contacts/contacts.store";
import { KnowledgeService } from "@/features/knowledge/knowledge.service";
import { KnowledgeContentDraftStorage } from "@/features/knowledge/knowledge-content-draft-storage";
import { KnowledgeDraftStorage } from "@/features/knowledge/knowledge-draft-storage";
import { KnowledgeStore } from "@/features/knowledge/knowledge.store";
import { IntegrationDraftStorage } from "@/features/integrations/integration-draft-storage";
import { IntegrationsService } from "@/features/integrations/integrations.service";
import { IntegrationsStore } from "@/features/integrations/integrations.store";
import { MemoryService } from "@/features/memory/memory.service";
import { MemoryStore } from "@/features/memory/memory.store";
import { MembersService } from "@/features/members/members.service";
import { MembersStore } from "@/features/members/members.store";
import { OperationsService } from "@/features/operations/operations.service";
import { OperationsStore } from "@/features/operations/operations.store";
import { ProviderDraftStorage } from "@/features/providers/provider-draft-storage";
import { ProvidersService } from "@/features/providers/providers.service";
import { ProvidersStore } from "@/features/providers/providers.store";
import { SessionsService } from "@/features/sessions/sessions.service";
import { SessionsStore } from "@/features/sessions/sessions.store";
import { SwarmDraftStorage } from "@/features/swarms/swarm-draft-storage";
import { SwarmsService } from "@/features/swarms/swarms.service";
import { SwarmsStore } from "@/features/swarms/swarms.store";
import { TelephonyService } from "@/features/telephony/telephony.service";
import { TelephonyStore } from "@/features/telephony/telephony.store";
import { ToolsService } from "@/features/tools/tools.service";
import { ToolsStore } from "@/features/tools/tools.store";
import { VoiceConfigDraftStorage } from "@/features/voice/voice-draft-storage";
import { VoiceConfigService } from "@/features/voice/voice.service";
import { VoiceConfigStore } from "@/features/voice/voice.store";

class RootStore {
  readonly api: ApiClient;
  readonly agents: AgentsStore;
  readonly auth: AuthStore;
  readonly automations: AutomationsStore;
  readonly campaigns: CampaignsStore;
  readonly conversations: ConversationsStore;
  readonly contacts: ContactsStore;
  readonly knowledge: KnowledgeStore;
  readonly integrations: IntegrationsStore;
  readonly memory: MemoryStore;
  readonly members: MembersStore;
  readonly operations: OperationsStore;
  readonly providers: ProvidersStore;
  readonly sessions: SessionsStore;
  readonly swarms: SwarmsStore;
  readonly telephony: TelephonyStore;
  readonly theme: ThemeStore;
  readonly tools: ToolsStore;
  readonly voice: VoiceConfigStore;

  constructor(
    api: ApiClient,
    agents: AgentsStore,
    auth: AuthStore,
    automations: AutomationsStore,
    campaigns: CampaignsStore,
    conversations: ConversationsStore,
    contacts: ContactsStore,
    knowledge: KnowledgeStore,
    integrations: IntegrationsStore,
    memory: MemoryStore,
    members: MembersStore,
    operations: OperationsStore,
    providers: ProvidersStore,
    sessions: SessionsStore,
    swarms: SwarmsStore,
    telephony: TelephonyStore,
    theme: ThemeStore,
    tools: ToolsStore,
    voice: VoiceConfigStore,
  ) {
    this.api = api;
    this.agents = agents;
    this.auth = auth;
    this.automations = automations;
    this.campaigns = campaigns;
    this.conversations = conversations;
    this.contacts = contacts;
    this.knowledge = knowledge;
    this.integrations = integrations;
    this.memory = memory;
    this.members = members;
    this.operations = operations;
    this.providers = providers;
    this.sessions = sessions;
    this.swarms = swarms;
    this.telephony = telephony;
    this.theme = theme;
    this.tools = tools;
    this.voice = voice;
  }
}

function createRootStore(): RootStore {
  const authStoreReference: { current: AuthStore | null } = { current: null };
  const api = createApiClient({
    getAccessToken: () => authStoreReference.current?.accessToken ?? null,
    onUnauthorized: () => authStoreReference.current?.expire(),
  });

  const authStore = new AuthStore(
    api,
    new BrowserTokenStorage(window.localStorage, window),
  );
  authStoreReference.current = authStore;

  return new RootStore(
    api,
    new AgentsStore(
      api,
      new AgentDraftStorage(window.localStorage),
      new AgentInstructionDraftStorage(window.localStorage),
    ),
    authStore,
    new AutomationsStore(new AutomationsService(api)),
    new CampaignsStore(new CampaignsService(api)),
    new ConversationsStore(new ConversationsService(api)),
    new ContactsStore(
      new ContactsService(api),
      new ContactDraftStorage(window.localStorage),
    ),
    new KnowledgeStore(
      new KnowledgeService(api),
      new KnowledgeDraftStorage(window.localStorage),
      new KnowledgeContentDraftStorage(window.localStorage),
    ),
    new IntegrationsStore(
      new IntegrationsService(api),
      new IntegrationDraftStorage(window.localStorage),
    ),
    new MemoryStore(new MemoryService(api)),
    new MembersStore(new MembersService(api)),
    new OperationsStore(new OperationsService(api)),
    new ProvidersStore(
      new ProvidersService(api),
      new ProviderDraftStorage(window.localStorage),
    ),
    new SessionsStore(new SessionsService(api)),
    new SwarmsStore(
      new SwarmsService(api),
      new SwarmDraftStorage(window.localStorage),
    ),
    new TelephonyStore(new TelephonyService(api)),
    new ThemeStore(window.localStorage),
    new ToolsStore(new ToolsService(api)),
    new VoiceConfigStore(
      api,
      new VoiceConfigService(api),
      new VoiceConfigDraftStorage(window.localStorage),
    ),
  );
}

export { RootStore, createRootStore };
