from __future__ import annotations

import functools

import pytest

from xtr_event_dispatcher import ListenerSignatureError
from xtr_event_dispatcher._listener_call import call_listener, positional_arity


def _none() -> None: ...


def _event(_event: object) -> None: ...


def _named(_event: object, _name: str) -> None: ...


def _all(_event: object, _name: str, _dispatcher: object) -> None: ...


def _variadic(*_arguments: object) -> None: ...


def _optional_fourth(_event: object, _name: str, _dispatcher: object, _extra: int = 0) -> None: ...


def _options(_event: object, **_options: object) -> None: ...


def _four(event: object, name: str, dispatcher: object, extra: object) -> None:
    del event, name, dispatcher, extra


def _keyword(_event: object, *, _required: object) -> None: ...


class _Callable:
    def __call__(self, _event: object, _name: str) -> None: ...


@pytest.mark.parametrize(
    ("listener", "arity"),
    [
        (_none, 0),
        (_event, 1),
        (_named, 2),
        (_all, 3),
        (_variadic, 3),
        (_optional_fourth, 3),
        (_options, 1),
        (_Callable(), 2),
        (functools.partial(_named, object()), 1),
    ],
)
def test_a_listener_is_given_as_many_arguments_as_it_takes(listener: object, arity: int) -> None:
    assert callable(listener)
    assert positional_arity(listener) == arity


def test_a_callable_without_a_signature_is_given_every_argument() -> None:
    assert positional_arity(dict) == 3


def test_requiring_a_fourth_positional_argument_is_refused() -> None:
    with pytest.raises(ListenerSignatureError) as raised:
        _ = positional_arity(_four)

    assert raised.value.listener == f"{__name__}._four"
    assert raised.value.signature == "(event, name, dispatcher, extra)"


def test_requiring_a_keyword_argument_is_refused() -> None:
    with pytest.raises(ListenerSignatureError):
        _ = positional_arity(_keyword)


@pytest.mark.anyio
async def test_an_awaitable_result_is_awaited() -> None:
    awaited: list[str] = []

    async def listener(name: object) -> None:
        awaited.append(str(name))

    await call_listener(listener, 1, ("event", "name", "dispatcher"))

    assert awaited == ["event"]
