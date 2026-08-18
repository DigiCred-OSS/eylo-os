import { lazy, Suspense, useState, type ReactNode } from "react";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router";

import { AppShell } from "@/app/AppShell";
import { FullPageStatus } from "@/app/FullPageStatus";
import { NotFoundPage } from "@/app/NotFoundPage";
import { RootStoreProvider } from "@/app/RootStoreProvider";
import { createRootStore } from "@/app/root.store";
import { useRootStore } from "@/app/use-root-store";
import { LoginPage } from "@/features/auth/LoginPage";
import { OrganizationBoundary } from "@/features/auth/OrganizationBoundary";
import { SessionBoundary } from "@/features/auth/SessionBoundary";

const AgentsPage = lazy(() =>
  import("@/features/agents/AgentsPage").then((module) => ({
    default: module.AgentsPage,
  })),
);
const AgentFormPage = lazy(() =>
  import("@/features/agents/AgentFormPage").then((module) => ({
    default: module.AgentFormPage,
  })),
);
const SwarmsPage = lazy(() =>
  import("@/features/swarms/SwarmsPage").then((module) => ({
    default: module.SwarmsPage,
  })),
);
const SwarmFormPage = lazy(() =>
  import("@/features/swarms/SwarmFormPage").then((module) => ({
    default: module.SwarmFormPage,
  })),
);
const ProvidersPage = lazy(() =>
  import("@/features/providers/ProvidersPage").then((module) => ({
    default: module.ProvidersPage,
  })),
);
const ProviderConfigsPage = lazy(() =>
  import("@/features/providers/ProviderConfigsPage").then((module) => ({
    default: module.ProviderConfigsPage,
  })),
);
const ProviderConfigFormPage = lazy(() =>
  import("@/features/providers/ProviderConfigFormPage").then((module) => ({
    default: module.ProviderConfigFormPage,
  })),
);
const KnowledgePage = lazy(() =>
  import("@/features/knowledge/KnowledgePage").then((module) => ({
    default: module.KnowledgePage,
  })),
);
const KnowledgebaseFormPage = lazy(() =>
  import("@/features/knowledge/KnowledgebaseFormPage").then((module) => ({
    default: module.KnowledgebaseFormPage,
  })),
);
const MemoryPage = lazy(() =>
  import("@/features/memory/MemoryPage").then((module) => ({
    default: module.MemoryPage,
  })),
);
const VoiceConfigsPage = lazy(() =>
  import("@/features/voice/VoiceConfigsPage").then((module) => ({
    default: module.VoiceConfigsPage,
  })),
);
const VoiceConfigFormPage = lazy(() =>
  import("@/features/voice/VoiceConfigFormPage").then((module) => ({
    default: module.VoiceConfigFormPage,
  })),
);
const ConversationsPage = lazy(() =>
  import("@/features/conversations/ConversationsPage").then((module) => ({
    default: module.ConversationsPage,
  })),
);
const ContactsPage = lazy(() =>
  import("@/features/contacts/ContactsPage").then((module) => ({
    default: module.ContactsPage,
  })),
);
const ContactFormPage = lazy(() =>
  import("@/features/contacts/ContactFormPage").then((module) => ({
    default: module.ContactFormPage,
  })),
);
const MembersPage = lazy(() =>
  import("@/features/members/MembersPage").then((module) => ({
    default: module.MembersPage,
  })),
);
const ConversationDetailPage = lazy(() =>
  import("@/features/conversations/ConversationDetailPage").then((module) => ({
    default: module.ConversationDetailPage,
  })),
);
const SessionsPage = lazy(() =>
  import("@/features/sessions/SessionsPage").then((module) => ({
    default: module.SessionsPage,
  })),
);
const SessionDetailPage = lazy(() =>
  import("@/features/sessions/SessionDetailPage").then((module) => ({
    default: module.SessionDetailPage,
  })),
);
const IntegrationsPage = lazy(() =>
  import("@/features/integrations/IntegrationsPage").then((module) => ({
    default: module.IntegrationsPage,
  })),
);
const ConfiguredIntegrationsPage = lazy(() =>
  import("@/features/integrations/ConfiguredIntegrationsPage").then(
    (module) => ({ default: module.ConfiguredIntegrationsPage }),
  ),
);
const IntegrationConnectionsPage = lazy(() =>
  import("@/features/integrations/IntegrationConnectionsPage").then(
    (module) => ({ default: module.IntegrationConnectionsPage }),
  ),
);
const IntegrationVendorPage = lazy(() =>
  import("@/features/integrations/IntegrationVendorPage").then((module) => ({
    default: module.IntegrationVendorPage,
  })),
);
const ToolsPage = lazy(() =>
  import("@/features/tools/ToolsPage").then((module) => ({
    default: module.ToolsPage,
  })),
);
const AutomationsPage = lazy(() =>
  import("@/features/automations/AutomationsPage").then((module) => ({
    default: module.AutomationsPage,
  })),
);
const AutomationFormPage = lazy(() =>
  import("@/features/automations/AutomationFormPage").then((module) => ({
    default: module.AutomationFormPage,
  })),
);
const AgentRunsPage = lazy(() =>
  import("@/features/operations/AgentRunsPage").then((module) => ({
    default: module.AgentRunsPage,
  })),
);
const VoiceSessionsPage = lazy(() =>
  import("@/features/operations/VoiceSessionsPage").then((module) => ({
    default: module.VoiceSessionsPage,
  })),
);
const EventHealthPage = lazy(() =>
  import("@/features/operations/EventHealthPage").then((module) => ({
    default: module.EventHealthPage,
  })),
);
const SystemStatusPage = lazy(() =>
  import("@/features/operations/SystemStatusPage").then((module) => ({
    default: module.SystemStatusPage,
  })),
);
const PhoneNumbersPage = lazy(() =>
  import("@/features/telephony/PhoneNumbersPage").then((module) => ({
    default: module.PhoneNumbersPage,
  })),
);
const PhoneNumberFormPage = lazy(() =>
  import("@/features/telephony/PhoneNumberFormPage").then((module) => ({
    default: module.PhoneNumberFormPage,
  })),
);
const CallsPage = lazy(() =>
  import("@/features/telephony/CallsPage").then((module) => ({
    default: module.CallsPage,
  })),
);
const CampaignsPage = lazy(() =>
  import("@/features/campaigns/CampaignsPage").then((module) => ({
    default: module.CampaignsPage,
  })),
);
const CampaignFormPage = lazy(() =>
  import("@/features/campaigns/CampaignFormPage").then((module) => ({
    default: module.CampaignFormPage,
  })),
);
const DocumentationPage = lazy(() =>
  import("@/features/documentation/DocumentationPage").then((module) => ({
    default: module.DocumentationPage,
  })),
);

function App() {
  const [store] = useState(createRootStore);

  return (
    <RootStoreProvider store={store}>
      <BrowserRouter>
        <Routes>
          <Route path="login" element={<LoginPage />} />
          <Route element={<SessionBoundary />}>
            <Route index element={<AuthenticatedHome />} />
            <Route
              path="org/:organizationId"
              element={<OrganizationBoundary />}
            >
              <Route element={<AppShell />}>
                <Route index element={<Navigate replace to="agents" />} />
                <Route
                  path="agents"
                  element={
                    <LazyRoute>
                      <AgentsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="agents/new"
                  element={
                    <LazyRoute>
                      <AgentFormPage mode="create" />
                    </LazyRoute>
                  }
                />
                <Route
                  path="agents/:agentId/edit"
                  element={
                    <LazyRoute>
                      <AgentFormPage mode="edit" />
                    </LazyRoute>
                  }
                />
                <Route
                  path="agents/:agentId"
                  element={
                    <LazyRoute>
                      <AgentsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="swarms"
                  element={
                    <LazyRoute>
                      <SwarmsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="swarms/new"
                  element={
                    <LazyRoute>
                      <SwarmFormPage mode="create" />
                    </LazyRoute>
                  }
                />
                <Route
                  path="swarms/:swarmId/edit"
                  element={
                    <LazyRoute>
                      <SwarmFormPage mode="edit" />
                    </LazyRoute>
                  }
                />
                <Route
                  path="swarms/:swarmId"
                  element={
                    <LazyRoute>
                      <SwarmsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="knowledge/new"
                  element={
                    <LazyRoute>
                      <KnowledgebaseFormPage mode="create" />
                    </LazyRoute>
                  }
                />
                <Route
                  path="knowledge/:knowledgebaseId/edit"
                  element={
                    <LazyRoute>
                      <KnowledgebaseFormPage mode="edit" />
                    </LazyRoute>
                  }
                />
                <Route
                  path="knowledge/:knowledgebaseId/content"
                  element={
                    <LazyRoute>
                      <KnowledgePage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="knowledge/:knowledgebaseId"
                  element={
                    <LazyRoute>
                      <KnowledgePage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="knowledge"
                  element={
                    <LazyRoute>
                      <KnowledgePage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="contacts/new"
                  element={
                    <LazyRoute>
                      <ContactFormPage mode="create" />
                    </LazyRoute>
                  }
                />
                <Route
                  path="contacts/:contactId/edit"
                  element={
                    <LazyRoute>
                      <ContactFormPage mode="edit" />
                    </LazyRoute>
                  }
                />
                <Route
                  path="contacts/:contactId"
                  element={
                    <LazyRoute>
                      <ContactsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="contacts"
                  element={
                    <LazyRoute>
                      <ContactsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="members/:memberId"
                  element={
                    <LazyRoute>
                      <MembersPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="members"
                  element={
                    <LazyRoute>
                      <MembersPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="memory/:memoryId"
                  element={
                    <LazyRoute>
                      <MemoryPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="memory"
                  element={
                    <LazyRoute>
                      <MemoryPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="voice/new"
                  element={
                    <LazyRoute>
                      <VoiceConfigFormPage mode="create" />
                    </LazyRoute>
                  }
                />
                <Route
                  path="voice/:voiceConfigId/edit"
                  element={
                    <LazyRoute>
                      <VoiceConfigFormPage mode="edit" />
                    </LazyRoute>
                  }
                />
                <Route
                  path="voice/:voiceConfigId"
                  element={
                    <LazyRoute>
                      <VoiceConfigsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="automations"
                  element={
                    <LazyRoute>
                      <AutomationsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="automations/new"
                  element={
                    <LazyRoute>
                      <AutomationFormPage mode="create" />
                    </LazyRoute>
                  }
                />
                <Route
                  path="automations/:scheduleId/edit"
                  element={
                    <LazyRoute>
                      <AutomationFormPage mode="edit" />
                    </LazyRoute>
                  }
                />
                <Route
                  path="automations/:scheduleId"
                  element={
                    <LazyRoute>
                      <AutomationsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="voice"
                  element={
                    <LazyRoute>
                      <VoiceConfigsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="conversations/:conversationId"
                  element={
                    <LazyRoute>
                      <ConversationDetailPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="conversations"
                  element={
                    <LazyRoute>
                      <ConversationsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="sessions/:userSessionId"
                  element={
                    <LazyRoute>
                      <SessionDetailPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="sessions"
                  element={
                    <LazyRoute>
                      <SessionsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="agent-runs/:runId"
                  element={
                    <LazyRoute>
                      <AgentRunsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="agent-runs"
                  element={
                    <LazyRoute>
                      <AgentRunsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="voice-sessions/:voiceSessionId"
                  element={
                    <LazyRoute>
                      <VoiceSessionsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="voice-sessions"
                  element={
                    <LazyRoute>
                      <VoiceSessionsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="events"
                  element={
                    <LazyRoute>
                      <EventHealthPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="system-status"
                  element={
                    <LazyRoute>
                      <SystemStatusPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="telephony"
                  element={<Navigate replace to="numbers" />}
                />
                <Route
                  path="telephony/numbers/new"
                  element={
                    <LazyRoute>
                      <PhoneNumberFormPage mode="create" />
                    </LazyRoute>
                  }
                />
                <Route
                  path="telephony/numbers/:phoneNumberId/edit"
                  element={
                    <LazyRoute>
                      <PhoneNumberFormPage mode="edit" />
                    </LazyRoute>
                  }
                />
                <Route
                  path="telephony/numbers/:phoneNumberId"
                  element={
                    <LazyRoute>
                      <PhoneNumbersPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="telephony/numbers"
                  element={
                    <LazyRoute>
                      <PhoneNumbersPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="telephony/calls/:callId"
                  element={
                    <LazyRoute>
                      <CallsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="telephony/calls"
                  element={
                    <LazyRoute>
                      <CallsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="outbound"
                  element={<Navigate replace to="campaigns" />}
                />
                <Route
                  path="outbound/campaigns/new"
                  element={
                    <LazyRoute>
                      <CampaignFormPage mode="create" />
                    </LazyRoute>
                  }
                />
                <Route
                  path="outbound/campaigns/:campaignId/edit"
                  element={
                    <LazyRoute>
                      <CampaignFormPage mode="edit" />
                    </LazyRoute>
                  }
                />
                <Route
                  path="outbound/campaigns/:campaignId"
                  element={
                    <LazyRoute>
                      <CampaignsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="outbound/campaigns"
                  element={
                    <LazyRoute>
                      <CampaignsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="tools"
                  element={
                    <LazyRoute>
                      <ToolsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="tools/:toolId"
                  element={
                    <LazyRoute>
                      <ToolsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="integrations/configured"
                  element={
                    <LazyRoute>
                      <ConfiguredIntegrationsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="integrations/connections"
                  element={
                    <LazyRoute>
                      <IntegrationConnectionsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="integrations/:vendor"
                  element={
                    <LazyRoute>
                      <IntegrationVendorPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="integrations"
                  element={
                    <LazyRoute>
                      <IntegrationsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="providers"
                  element={
                    <LazyRoute>
                      <ProvidersPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="providers/:capability/new"
                  element={
                    <LazyRoute>
                      <ProviderConfigFormPage mode="create" />
                    </LazyRoute>
                  }
                />
                <Route
                  path="providers/:capability/:configId/edit"
                  element={
                    <LazyRoute>
                      <ProviderConfigFormPage mode="edit" />
                    </LazyRoute>
                  }
                />
                <Route
                  path="providers/:capability/:configId"
                  element={
                    <LazyRoute>
                      <ProviderConfigsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="providers/:capability"
                  element={
                    <LazyRoute>
                      <ProviderConfigsPage />
                    </LazyRoute>
                  }
                />
                <Route
                  path="documentation/*"
                  element={
                    <LazyRoute>
                      <DocumentationPage />
                    </LazyRoute>
                  }
                />
              </Route>
            </Route>
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
    </RootStoreProvider>
  );
}

function LazyRoute({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<FullPageStatus message="Loading console…" />}>
      {children}
    </Suspense>
  );
}

function AuthenticatedHome() {
  const { auth } = useRootStore();

  return auth.organizationId === null ? (
    <Outlet />
  ) : (
    <Navigate replace to={`/org/${auth.organizationId}/agents`} />
  );
}

export { App };
