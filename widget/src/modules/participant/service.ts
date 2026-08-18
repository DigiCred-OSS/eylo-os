import { EYLO_EVENTS } from "@eylo/events";
import { WS_ACTIONS, type TWsMessage } from "@eylo/net";
import type { EyloStore } from "@eylo/store";
import { logger } from "@eylo/utils";

import { AgentService, type TAgent } from "../agent";
import { ContactService, type ContactStore, type TContact } from "../contact";
import { Participant } from "./model";
import type { ParticipantStore } from "./store";
import type { TParticipant, TParticipantKind } from "./types";

class ParticipantService {
  private static _instance: ParticipantService | null = null;
  // @ts-ignore [TS2564] - TS does not recognize the store as a class property
  private _eyloStore: EyloStore;
  // @ts-ignore [TS2564] - TS does not recognize the store as a class property
  private _participantStore: ParticipantStore;
  // @ts-ignore [TS2564] - TS does not recognize the store as a class property
  private _contactStore: ContactStore;
  constructor(eyloStore: EyloStore) {
    if (ParticipantService._instance) {
      return ParticipantService._instance;
    }
    this._eyloStore = eyloStore;
    this._contactStore = this._eyloStore.contactStore;
    this._participantStore = this._eyloStore.participantStore;
    this._installHandlers();
    ParticipantService._instance = this;
  }

  private _messageParticipantHandler = () => {
    this._eyloStore.cm.registerMessageHandler(WS_ACTIONS.PARTICIPANT_CREATED, (participant) => {
      if (participant.data) {
        const newParticipant = new Participant(participant.data);
        this._participantStore.add_(newParticipant);
        this._eyloStore.ee.emit(EYLO_EVENTS.PARTICIPANT_CREATED, newParticipant);
      } else {
        logger.warn("Received participant created without data.");
      }
    });
  };

  private _participantQueryHandler = () => {
    const _handler = (message: TWsMessage) => {
      if (message.data) {
        message.data.forEach((m: TParticipant) => {
          const participant = new Participant(m);
          this._participantStore.add_(participant);
          this._eyloStore.ee.emit(EYLO_EVENTS.PARTICIPANT_CREATED, participant);
        });
      } else {
        logger.warn("Received participant query message without data.");
      }
    };
    this._eyloStore.cm.registerMessageHandler(WS_ACTIONS.PARTICIPANT_QUERY, _handler);
  };

  private _installHandlers = (): void => {
    this._messageParticipantHandler();
    this._participantQueryHandler();
  };

  public resolveParticipant_byID(participantId: string): TContact | TAgent | undefined {
    const participant = this._participantStore.get_(participantId);
    if (!participant) {
      this._eyloStore.cm.send({
        kind: WS_ACTIONS.PARTICIPANT_QUERY,
        data: {
          filters: {
            participantIds: [participantId],
          },
        },
        requestId: participantId,
      } as TWsMessage);
      return;
    }
    // TODO: add support for "AGENT", "MEMBER", etc.
    if (!["CONTACT", "AGENT"].includes(participant.entityKind as TParticipantKind)) {
      return;
    }
    if (participant.entityKind === "AGENT") {
      const agent = new AgentService(this._eyloStore).resolveAgent_byID(participant.entityId);
      if (!agent) {
        return;
      }
      return agent;
    }
    if (participant.entityKind === "CONTACT") {
      const contact = new ContactService(this._eyloStore).resolveContact_byID(participant.entityId);
      if (!contact) {
        return;
      }
      return contact;
    }
  }
}

export { ParticipantService };
