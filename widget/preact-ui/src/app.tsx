import styles from "./App.module.css";
import AgentList from "./components/AgentList";
import ChatWidgetContainer from "./components/ChatWidgetContainer";
import ConversationCreate from "./components/ConversationCreate";
import ConversationDetails from "./components/ConversationDetails";
import ConversationList from "./components/ConversationList";
import ErrorBoundary from "./components/ErrorBoundary";
import { MemoryRouter, Route } from "./library/MemoryRouter";

export const PATHS = {
  CONVERSATION_LIST: "/",
  CONVERSATION_CREATE: "/conversation/create",
  CONVERSATION_DETAILS: "/conversation/detail/:id",
  CONVERSATION_WITH_AGENT: "/conversation/agent/:id",
  AGENT_LIST: "/agent/list",
};

type AppProps = {
  initialConversationId?: string;
};

const App = ({ initialConversationId }: AppProps) => {
  const initialPath = initialConversationId
    ? PATHS.CONVERSATION_DETAILS.replace(":id", encodeURIComponent(initialConversationId))
    : PATHS.CONVERSATION_LIST;

  return (
    <MemoryRouter initialPath={initialPath}>
      <div className={styles.appContainer}>
        <ChatWidgetContainer>
          <ErrorBoundary>
            <Route path={PATHS.CONVERSATION_CREATE}>
              <ConversationCreate />
            </Route>
            <Route path={PATHS.CONVERSATION_DETAILS}>
              <ConversationDetails />
            </Route>
            <Route path={PATHS.CONVERSATION_LIST}>
              <ConversationList />
            </Route>
            <Route path={PATHS.AGENT_LIST}>
              <AgentList />
            </Route>
            <Route path={PATHS.CONVERSATION_WITH_AGENT}>
              <ConversationCreate />
            </Route>
          </ErrorBoundary>
        </ChatWidgetContainer>
      </div>
    </MemoryRouter>
  );
};

export { App };
