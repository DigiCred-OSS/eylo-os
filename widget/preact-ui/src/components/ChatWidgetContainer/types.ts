import type { Feedback } from "../../hooks/useAgentStatus";

export type TChatHeader = {
  title?: string;
  onClose?: () => void;
  onBack?: () => void;
  agentStatus?: Feedback | null;
};
