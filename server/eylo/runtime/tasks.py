"""Background task registration for the `runtime` platform."""

import asyncio
import logging
from typing import Any, Callable, Coroutine, Mapping

logger = logging.getLogger(__name__)

# A frozenset is immutable; attempts to add restart conditions raise AttributeError.


def _eval_restart_conditions(restart_conditions: set[Callable[[], bool]]) -> bool:
    _should_restart = True
    for condition in restart_conditions:
        if isinstance(condition, Callable):
            try:
                if condition():
                    _should_restart &= True
            except Exception as error:
                logger.error(
                    "Restart condition failed error_type=%s",
                    type(error).__name__,
                )
        elif isinstance(condition, bool):
            _should_restart &= condition
        else:
            logger.error(
                f"Invalid restart condition type: {type(condition)}. Expected Callable or bool."
            )
            _should_restart &= False
    return _should_restart


async def monitor_long_running_tasks(
    task_definitions: Mapping[str, Callable[..., Coroutine[Any, Any, None]]],
    active_tasks: dict[str, asyncio.Task],
    task_params: Mapping[str, tuple[tuple[Any, ...], dict[str, Any]]] = {},
    exceptions_to_ignore: set[type[BaseException]] = frozenset(),  # type: ignore
    exceptions_to_restart: set[type[BaseException]] = frozenset(),  # type: ignore
    restart_conditions: set[Callable[[], bool]] = frozenset(),  # type: ignore
) -> None:
    """Monitor and manage the lifecycle of tasks.

    This function checks the status of each task in the active_tasks dictionary.
    If a task has completed (either successfully or with an exception), it will
    be restarted if the connection is still active.

    Args:
        task_definitions (dict): A dictionary mapping task names to their
            corresponding coroutine functions.
        active_tasks (dict): A dictionary mapping task names to their
            corresponding asyncio.Task objects.

    """
    # Check each task for failures
    for name, task in list(active_tasks.items()):
        if task.done():
            # Task has stopped - check if it failed with an exception
            exception = task.exception()

            # Handle task completion based on how it ended
            if exception is None:
                # Task completed normally (unexpected for continuous tasks)
                logger.warning(
                    f"Task '{name}' ended unexpectedly by returning normally"
                )
            else:
                # Task ended with an exception
                if isinstance(exception, asyncio.CancelledError):
                    # Task was explicitly cancelled (normal during shutdown)
                    logger.debug(f"Task '{name}' was cancelled")
                    continue  # Don't restart cancelled tasks
                else:
                    if isinstance(exception, tuple(exceptions_to_ignore)):
                        # Ignore specific exceptions
                        logger.debug(
                            "Task '%s' stopped with ignored error_type=%s",
                            name,
                            type(exception).__name__,
                        )
                        continue
                    elif isinstance(exception, tuple(exceptions_to_restart)):
                        # Restart task on specific exceptions
                        logger.info(
                            "Task '%s' stopped with restartable error_type=%s",
                            name,
                            type(exception).__name__,
                        )
                        # Always restart the task if we're still connected

                        if name in task_definitions and _eval_restart_conditions(
                            restart_conditions
                        ):
                            logger.info(f"Restarting task '{name}'")
                            if name in task_params:
                                args, kwargs = task_params[name]
                                active_tasks[name] = asyncio.create_task(
                                    task_definitions[name](*args, **kwargs)
                                )
                            else:
                                active_tasks[name] = asyncio.create_task(
                                    task_definitions[name]()
                                )


async def teardown_long_running_tasks(
    active_tasks: dict[str, asyncio.Task],
) -> None:
    """Cancel all long-running tasks.

    This function cancels all tasks in the active_tasks dictionary and waits
    for them to finish.

    Args:
        active_tasks (dict): A dictionary mapping task names to their
            corresponding asyncio.Task objects.

    """
    current_task = asyncio.current_task()
    for name, task in active_tasks.items():
        if task is current_task:
            logger.debug(f"Skipping current task '{name}' during teardown")
            continue
        if not task.done():
            logger.debug(f"Cancelling task '{name}'")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.debug(f"Task '{name}' cancelled successfully")
            except Exception as error:
                logger.error(
                    "Task cancellation failed task=%s error_type=%s",
                    name,
                    type(error).__name__,
                )
            finally:
                logger.debug(f"Task '{name}' removed from active tasks")
    pending_tasks = [
        task
        for task in active_tasks.values()
        if not task.done() and task is not current_task
    ]
    if pending_tasks:
        try:
            await asyncio.gather(*pending_tasks, return_exceptions=True)
        except Exception as error:
            logger.error(
                "Waiting for task cancellation failed error_type=%s",
                type(error).__name__,
            )


async def teardown_queues(
    queues: list[asyncio.Queue],
    join_timeout: int = 1,
):
    for queue in queues:
        await _teardown_queue(queue, join_timeout)


async def _teardown_queue(
    queue: asyncio.Queue,
    join_timeout: int = 1,
):
    try:
        await asyncio.wait_for(queue.join(), timeout=join_timeout)
    except asyncio.TimeoutError:
        logger.warning(
            "Timeout waiting for request queue to drain. "
            f"{queue.qsize()} items might be unprocessed."
        )
    except Exception as error:
        logger.error(
            "Queue drain failed error_type=%s",
            type(error).__name__,
        )
