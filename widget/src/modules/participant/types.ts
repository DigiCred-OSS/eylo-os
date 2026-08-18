export type TParticipantKind = "AGENT" | "CONTACT" | "MEMBER";
export const ParticipantKind: Record<TParticipantKind, TParticipantKind> = {
  AGENT: "AGENT",
  CONTACT: "CONTACT",
  MEMBER: "MEMBER",
};

export type TParticipant = {
  id: string;
  entityKind: TParticipantKind;
  entityId: string;
  hasInitiated: boolean;
  addedByKind?: TParticipantKind | null;
  addedById?: string | null;
  joinedAt: Date;
  isActive: boolean;
  removedByKind?: TParticipantKind | null;
  removedById?: string | null;
  leftAt?: Date | null;
  conversationId: string;
};
