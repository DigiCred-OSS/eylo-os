import { formatAgentDate } from "@/features/agents/agent-formatters";

function AgentDateTime({ value }: { value: string | undefined }) {
  if (value === undefined) {
    return <>Not recorded</>;
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return <>Not recorded</>;
  }

  const exactTimestamp = date.toISOString();
  return (
    <time dateTime={exactTimestamp} title={`${exactTimestamp} (UTC)`}>
      {formatAgentDate(value)}
    </time>
  );
}

export { AgentDateTime };
