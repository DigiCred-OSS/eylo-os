"""Register and dispatch typed scheduled actions under explicit contexts."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ActionContext:
    """What a handler is told about the run it is serving.

    Deliberately small. A handler that needs more should take it in its
    payload, where an operator can see it, rather than reaching for platform
    state the schedule never mentioned.
    """

    organization_id: UUID
    schedule_id: UUID
    schedule_revision: int
    run_id: UUID
    agent_id: UUID | None
    agent_revision: int | None
    # The occurrence this run is for — not "now". A handler that reports on
    # "the last hour" must measure from the occurrence, or a run recovered
    # after a crash reports on the wrong hour.
    scheduled_for: datetime
    # How many occurrences were coalesced into this one. A handler that
    # accumulates can use it; most will not.
    misfired_count: int = 0


ActionHandler = Callable[..., Awaitable[dict]]


@dataclass(frozen=True)
class ActionSpec:
    """A handler, and which of its payload keys the platform owns."""

    name: str
    handler: ActionHandler

    # Payload keys the *platform* fills from the caller's context, never the
    # caller. `conversation.reengage` needs a conversation id, and an agent
    # that could name one could name someone else's — the model is the
    # component that reads untrusted text all day, and a scheduled action is a
    # particularly good place to hide an instruction.
    #
    # Same rule as the knowledgebase tools: scope ids never come from the
    # model. A value supplied for one of these is overwritten, not rejected,
    # because the model's choice is simply not consulted.
    context_keys: tuple[str, ...] = ()

    # Whether an agent may schedule this at all. Some actions are operator-only
    # — anything that spends money or reaches outside the organization — and
    # the default is the restrictive one.
    agent_schedulable: bool = False


_HANDLERS: dict[str, ActionSpec] = {}


class UnknownAction(Exception):
    """A schedule names an action nothing has registered.

    Terminal for the run, and deliberately *not* fatal for the schedule. A
    deploy that removed a handler must not silently delete an operator's
    recurring job — the run fails loudly, the schedule survives, and restoring
    the handler resumes it.
    """


def schedulable(
    name: str,
    *,
    context_keys: tuple[str, ...] = (),
    agent_schedulable: bool = False,
) -> Callable[[ActionHandler], ActionHandler]:
    """Register a handler under an action name.

    Names are namespaced by convention — `module.verb` — so a reader of a
    schedule row can tell which module owns it without a lookup.

    `agent_schedulable` defaults to False. An action an agent can reach is one
    a model can be persuaded to reach, so opting in is a decision the module
    author makes rather than one they get by omission.
    """

    def decorator(handler: ActionHandler) -> ActionHandler:
        existing = _HANDLERS.get(name)
        if existing is not None and existing.handler is not handler:
            # Two handlers for one name means a schedule's behaviour depends on
            # import order, which is not a thing anyone can debug.
            raise ValueError(f"Action '{name}' is already registered.")
        _HANDLERS[name] = ActionSpec(
            name=name,
            handler=handler,
            context_keys=context_keys,
            agent_schedulable=agent_schedulable,
        )
        return handler

    return decorator


def registered_actions() -> tuple[str, ...]:
    """Every action name currently registered, sorted."""
    return tuple(sorted(_HANDLERS))


def agent_actions() -> tuple[str, ...]:
    """Actions an agent may schedule."""
    return tuple(sorted(n for n, spec in _HANDLERS.items() if spec.agent_schedulable))


def action_spec(name: str) -> ActionSpec | None:
    return _HANDLERS.get(name)


async def dispatch(action: str, payload: dict, *, context: ActionContext) -> dict:
    """Run the handler for `action`.

    Raises `UnknownAction` when nothing is registered, naming what was asked
    for and what is available — an operator reading that error should not need
    to grep for the answer.
    """
    spec = _HANDLERS.get(action)
    if spec is None:
        raise UnknownAction(
            f"No handler registered for action '{action}'. "
            f"Available: {', '.join(registered_actions()) or 'none'}."
        )
    return await spec.handler(payload, context=context)
