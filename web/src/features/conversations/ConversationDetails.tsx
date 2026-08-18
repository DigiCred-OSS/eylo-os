import { AlertTriangle } from "lucide-react";
import { observer } from "mobx-react-lite";
import type { ReactNode } from "react";

import { useRootStore } from "@/app/use-root-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  formatConversationContact,
  formatConversationDate,
  formatConversationEnum,
  formatDuration,
  formatMilliseconds,
  formatTrackDuration,
} from "@/features/conversations/conversation-formatters";
import type {
  ConversationAggregate,
  ConversationParticipant,
  ConversationRecording,
  ConversationRecordingAudioState,
  ConversationRecordingTrack,
  ConversationVoiceSession,
} from "@/features/conversations/conversations.types";

const ConversationDetails = observer(function ConversationDetails({
  conversation,
  organizationId,
}: {
  conversation: ConversationAggregate;
  organizationId: string;
}) {
  const { conversations } = useRootStore();
  const summaryByParticipantId = new Map(
    (conversation.participants ?? []).map((participant) => [
      participant.id,
      participant,
    ]),
  );

  return (
    <aside className="min-w-0 space-y-6" aria-label="Conversation details">
      <DetailsSection title="Overview">
        <dl>
          <DetailRow label="Status">
            <Badge
              variant={conversation.status === "ACTIVE" ? "default" : "outline"}
            >
              {formatConversationEnum(conversation.status)}
            </Badge>
          </DetailRow>
          <DetailRow label="Channel">
            <Badge variant="outline">
              {formatConversationEnum(conversation.channel)}
            </Badge>
          </DetailRow>
          <DetailRow label="Messages">{conversation.messageCount}</DetailRow>
          <DetailRow label="Started">
            <DateValue value={conversation.createdAt} />
          </DetailRow>
          <DetailRow label="Updated">
            <DateValue value={conversation.updatedAt} />
          </DetailRow>
          <DetailRow label="Ended">
            <DateValue value={conversation.endedAt} />
          </DetailRow>
          <DetailRow label="Duration">
            {formatDuration(conversation.createdAt, conversation.endedAt)}
          </DetailRow>
        </dl>
      </DetailsSection>

      <DetailsSection title="Primary parties">
        <dl>
          <DetailRow label="Agent">
            {conversation.primaryAgent?.name ?? "Not resolved"}
          </DetailRow>
          <DetailRow label="Contact">
            {formatConversationContact(conversation.contact)}
          </DetailRow>
        </dl>
      </DetailsSection>

      {conversations.voiceSession === null &&
      conversations.voiceSessionErrorMessage === null ? null : (
        <DetailsSection title="Voice runtime">
          {conversations.voiceSessionErrorMessage !== null ? (
            <InlineError>
              {conversations.voiceSessionErrorMessage} The conversation remains
              available.
            </InlineError>
          ) : conversations.voiceSession === null ? null : (
            <VoiceSessionDetails session={conversations.voiceSession} />
          )}
        </DetailsSection>
      )}

      <DetailsSection title="Participants and handoffs">
        {conversations.participantsErrorMessage !== null ? (
          <InlineError>{conversations.participantsErrorMessage}</InlineError>
        ) : conversations.participants.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No participant history stored.
          </p>
        ) : (
          <ol className="divide-y border-y">
            {conversations.participants.map((participant) => (
              <ParticipantItem
                key={participant.id}
                participant={participant}
                label={summaryByParticipantId.get(participant.id)?.entityName}
              />
            ))}
          </ol>
        )}
      </DetailsSection>

      <DetailsSection title="Voice recordings">
        {conversations.recordingsErrorMessage !== null ? (
          <InlineError>
            {conversations.recordingsErrorMessage} The transcript remains
            available.
          </InlineError>
        ) : conversations.recordings.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No recording is attached to this conversation.
          </p>
        ) : (
          <div className="space-y-4">
            {conversations.recordings.map((recording) => (
              <RecordingItem
                key={recording.id}
                recording={recording}
                userAudio={conversations.recordingAudioFor(
                  recording.id,
                  "user",
                )}
                agentAudio={conversations.recordingAudioFor(
                  recording.id,
                  "agent",
                )}
                onLoad={(track) =>
                  conversations.loadRecordingTrack(
                    organizationId,
                    conversation.id,
                    recording.id,
                    track,
                  )
                }
              />
            ))}
          </div>
        )}
      </DetailsSection>

      <DetailsSection title="References">
        <dl>
          <DetailRow label="Conversation ID">
            <CodeValue>{conversation.id}</CodeValue>
          </DetailRow>
          <DetailRow label="External ID">
            <CodeValue>{conversation.externalId}</CodeValue>
          </DetailRow>
          <DetailRow label="Swarm ID">
            <CodeValue>{conversation.swarmId}</CodeValue>
          </DetailRow>
          <DetailRow label="Swarm revision">
            {conversation.swarmRevision ?? "Not applicable"}
          </DetailRow>
        </dl>
      </DetailsSection>

      {conversation.meta == null ||
      Object.keys(conversation.meta).length === 0 ? null : (
        <DetailsSection title="Metadata">
          <pre className="min-w-0 break-all border bg-muted/40 p-3 text-xs leading-5 whitespace-pre-wrap">
            {JSON.stringify(conversation.meta, null, 2)}
          </pre>
        </DetailsSection>
      )}
    </aside>
  );
});

function VoiceSessionDetails({
  session,
}: {
  session: ConversationVoiceSession;
}) {
  const providers = [
    formatProvider(session.realtimeVendor, session.realtimeModel),
    formatProvider(session.sttVendor, session.sttModel),
    formatProvider(session.ttsVendor, session.ttsModel),
    formatProvider(session.telephonyProvider),
  ].filter((value): value is string => value !== null);
  return (
    <dl>
      <DetailRow label="Status">
        <Badge
          variant={session.status === "failed" ? "destructive" : "outline"}
        >
          {formatConversationEnum(session.status)}
        </Badge>
      </DetailRow>
      <DetailRow label="End reason">
        {session.endedReason == null
          ? "Not ended"
          : formatConversationEnum(session.endedReason)}
      </DetailRow>
      <DetailRow label="Runtime">
        <span className="flex min-w-0 flex-wrap gap-2">
          <Badge variant="outline">
            {formatConversationEnum(session.runtimeMode)}
          </Badge>
          <Badge variant="outline">
            {formatConversationEnum(session.transport)}
          </Badge>
        </span>
      </DetailRow>
      <DetailRow label="Providers">
        {providers.length === 0 ? "Not recorded" : providers.join(" · ")}
      </DetailRow>
      <DetailRow label="Started">
        <DateValue value={session.startedAt} />
      </DetailRow>
      <DetailRow label="Ended">
        <DateValue value={session.endedAt} />
      </DetailRow>
      <DetailRow label="Duration">
        {formatMilliseconds(session.durationMs)}
      </DetailRow>
      <DetailRow label="Canonical state">
        <Badge variant="outline">
          {formatConversationEnum(session.canonicalState)}
        </Badge>
      </DetailRow>
      <DetailRow label="Canonical messages">
        {session.canonicalMessageCount}
      </DetailRow>
      <DetailRow label="Segments">{session.segmentCount}</DetailRow>
      {session.canonicalFailureCode == null ? null : (
        <DetailRow label="Projection failure">
          <CodeValue>{session.canonicalFailureCode}</CodeValue>
        </DetailRow>
      )}
      <DetailRow label="Voice session ID">
        <CodeValue>{session.id}</CodeValue>
      </DetailRow>
    </dl>
  );
}

function formatProvider(
  provider: string | null | undefined,
  model?: string | null,
): string | null {
  if (provider == null || provider === "") {
    return null;
  }
  return model == null || model === "" ? provider : `${provider} · ${model}`;
}

function ParticipantItem({
  label,
  participant,
}: {
  label: string | null | undefined;
  participant: ConversationParticipant;
}) {
  return (
    <li className="min-w-0 space-y-2 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="break-words text-sm font-medium">
          {label?.trim() || formatConversationEnum(participant.entityKind)}
        </span>
        <Badge variant="outline">
          {formatConversationEnum(participant.entityKind)}
        </Badge>
        {participant.isPrimary ? <Badge>Primary</Badge> : null}
        <Badge variant={participant.isActive ? "outline" : "secondary"}>
          {participant.isActive ? "Active" : "Left"}
        </Badge>
      </div>
      <dl>
        <DetailRow label="Entity ID">
          <CodeValue>{participant.entityId}</CodeValue>
        </DetailRow>
        <DetailRow label="Agent revision">
          {participant.agentRevision ?? "Not applicable"}
        </DetailRow>
        <DetailRow label="Joined">
          <DateValue value={participant.joinedAt} />
        </DetailRow>
        <DetailRow label="Left">
          <DateValue value={participant.leftAt} />
        </DetailRow>
        <DetailRow label="Added by">
          {participant.addedByKind == null ? (
            "Initial participant"
          ) : (
            <span className="flex min-w-0 flex-wrap items-center gap-2">
              <Badge variant="outline">
                {formatConversationEnum(participant.addedByKind)}
              </Badge>
              <CodeValue>{participant.addedById}</CodeValue>
            </span>
          )}
        </DetailRow>
        <DetailRow label="Removed by">
          {participant.removedByKind == null ? (
            "Not removed"
          ) : (
            <span className="flex min-w-0 flex-wrap items-center gap-2">
              <Badge variant="outline">
                {formatConversationEnum(participant.removedByKind)}
              </Badge>
              <CodeValue>{participant.removedById}</CodeValue>
            </span>
          )}
        </DetailRow>
      </dl>
    </li>
  );
}

function RecordingItem({
  agentAudio,
  onLoad,
  recording,
  userAudio,
}: {
  agentAudio: ConversationRecordingAudioState;
  onLoad: (track: ConversationRecordingTrack) => Promise<void>;
  recording: ConversationRecording;
  userAudio: ConversationRecordingAudioState;
}) {
  return (
    <article className="min-w-0 space-y-3 border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="break-all font-mono text-xs">
          {recording.session_id}
        </span>
        <Badge
          variant={
            recording.upload_state === "SUCCEEDED" ? "outline" : "secondary"
          }
        >
          {formatConversationEnum(recording.upload_state)}
        </Badge>
      </div>
      {recording.upload_error == null ? null : (
        <p className="break-words text-xs text-destructive">
          {recording.upload_error}
        </p>
      )}
      <RecordingTrack
        audio={userAudio}
        available={recording.user_audio_url != null}
        label="User track"
        duration={recording.user_duration_seconds}
        onLoad={() => void onLoad("user")}
      />
      <RecordingTrack
        audio={agentAudio}
        available={recording.agent_audio_url != null}
        label="Agent track"
        duration={recording.agent_duration_seconds}
        onLoad={() => void onLoad("agent")}
      />
      <p className="text-xs text-muted-foreground">
        Recorded {formatConversationDate(recording.created_at).label}
      </p>
    </article>
  );
}

function RecordingTrack({
  audio,
  available,
  duration,
  label,
  onLoad,
}: {
  audio: ConversationRecordingAudioState;
  available: boolean;
  duration: number | null | undefined;
  label: string;
  onLoad: () => void;
}) {
  return (
    <div className="min-w-0 space-y-1">
      <p className="text-xs font-medium">
        {label} · {formatTrackDuration(duration)}
      </p>
      {!available ? (
        <p className="text-xs text-muted-foreground">
          Audio track unavailable.
        </p>
      ) : audio.status === "ready" && audio.objectUrl !== null ? (
        <audio
          className="h-9 w-full max-w-full"
          controls
          preload="metadata"
          src={audio.objectUrl}
        >
          Your browser does not support audio playback.
        </audio>
      ) : (
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <Button
            size="xs"
            variant="outline"
            disabled={audio.status === "loading"}
            onClick={onLoad}
            aria-label={`${audio.status === "error" ? "Retry" : "Load"} ${label.toLowerCase()}`}
          >
            {audio.status === "loading"
              ? "Loading audio…"
              : audio.status === "error"
                ? "Retry audio"
                : "Load audio"}
          </Button>
          {audio.errorMessage === null ? null : (
            <span className="break-words text-xs text-destructive" role="alert">
              {audio.errorMessage}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function DetailsSection({
  children,
  title,
}: {
  children: ReactNode;
  title: string;
}) {
  return (
    <section className="min-w-0 border">
      <h2 className="border-b px-4 py-3 text-sm font-medium">{title}</h2>
      <div className="min-w-0 p-4">{children}</div>
    </section>
  );
}

function DetailRow({
  children,
  label,
}: {
  children: ReactNode;
  label: string;
}) {
  return (
    <div className="grid min-w-0 gap-1 border-b py-2 last:border-b-0 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-3">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words text-sm">{children}</dd>
    </div>
  );
}

function DateValue({ value }: { value: string | null | undefined }) {
  const formatted = formatConversationDate(value);
  return value == null ? (
    formatted.label
  ) : (
    <time dateTime={value} title={formatted.title}>
      {formatted.label}
    </time>
  );
}

function CodeValue({ children }: { children: string | null | undefined }) {
  return (
    <code className="break-all text-xs">{children ?? "Not recorded"}</code>
  );
}

function InlineError({ children }: { children: ReactNode }) {
  return (
    <div
      className="flex items-start gap-2 border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
      role="alert"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <p className="break-words">{children}</p>
    </div>
  );
}

export { ConversationDetails };
