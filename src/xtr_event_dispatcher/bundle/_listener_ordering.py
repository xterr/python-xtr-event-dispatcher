"""Putting each event's listeners in the order they run, ``before``/``after`` included.

A dispatcher runs listeners by priority, then in the order they were added.
So ``before``/``after`` constraints are turned into that order here, while
the container is built: a declared priority is never changed, and a listener
without one takes the priority its place needs.
"""

from __future__ import annotations

from xtr_dependency_injection.compiler.before_after_sorter import sort_with_priorities
from xtr_dependency_injection.exception import ServiceOrderError

from xtr_event_dispatcher.exception import InvalidListenerError

from ._declared_listeners import DeclaredListener
from ._listener_reference import ListenerReference

__all__ = ["ordered"]


def ordered(
    event_name: str, group: list[DeclaredListener]
) -> tuple[tuple[int, ListenerReference], ...]:
    """Return one event's listeners on one dispatcher as ``(priority, listener)`` in running order.

    Raises:
        InvalidListenerError: When the constraints form a cycle, contradict a
            declared priority, or name a method that does not listen to the
            event.
    """
    if not any(listener.before or listener.after for listener in group):
        return tuple((listener.priority or 0, listener.reference) for listener in group)

    keys: dict[str, DeclaredListener] = {}
    aliases: dict[str, list[str]] = {}
    for listener in group:
        key = listener.label
        repeat = 1
        while key in keys:
            key = f"{listener.label}#{repeat}"
            repeat += 1
        keys[key] = listener
        for name in listener.names:
            aliases.setdefault(name, []).append(key)

    constraints = {
        key: {"before": list(listener.before), "after": list(listener.after)}
        for key, listener in keys.items()
        if listener.before or listener.after
    }
    _check_targets(event_name, keys, aliases)

    try:
        resolved = sort_with_priorities(
            {key: listener.priority for key, listener in keys.items()},
            constraints,
            aliases,
        )
    except ServiceOrderError as error:
        first = next(iter(constraints))
        raise InvalidListenerError(
            keys[first].label,
            f'the "before"/"after" constraints of the event "{event_name}" cannot be met: '
            f"{error.reason}",
        ) from error

    return tuple((priority, keys[key].reference) for key, priority in resolved.items())


def _check_targets(
    event_name: str,
    keys: dict[str, DeclaredListener],
    aliases: dict[str, list[str]],
) -> None:
    """Refuse ``Class.method`` naming a class that listens here, through another method.

    A target naming nothing that listens is ignored — its package may not be
    installed — but one whose class does listen names a method that does not,
    and the constraint would silently do nothing.
    """
    for listener in keys.values():
        for target in (*listener.before, *listener.after):
            owner, _, method = target.rpartition(".")
            if target in aliases or not owner or ":" not in owner or owner not in aliases:
                continue
            raise InvalidListenerError(
                listener.label,
                f"it is ordered against {target}, but {owner} does not listen to the event "
                f'"{event_name}" with {method!r}',
            )
