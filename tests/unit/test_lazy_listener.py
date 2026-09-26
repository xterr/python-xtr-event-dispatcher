from __future__ import annotations

from typing import final

import pytest

from tests.support.listeners import DispatcherRecorder
from xtr_event_dispatcher import Event, LazyListener


@final
class _Counting:
    def __init__(self, built: object) -> None:
        self.built = built
        self.calls = 0

    async def __call__(self) -> object:
        self.calls += 1
        return self.built


def test_nothing_is_built_until_asked() -> None:
    factory = _Counting(DispatcherRecorder())

    lazy = LazyListener(factory, "foo")

    assert factory.calls == 0
    assert lazy.resolved is None


@pytest.mark.anyio
async def test_it_binds_the_method_it_names() -> None:
    recorder = DispatcherRecorder()

    listener = await LazyListener(_Counting(recorder), "foo").resolve()

    assert listener == recorder.foo


@pytest.mark.anyio
async def test_without_a_method_it_is_the_built_object() -> None:
    recorder = DispatcherRecorder()

    listener = await LazyListener(_Counting(recorder)).resolve()

    assert listener is recorder


@pytest.mark.anyio
async def test_the_factory_runs_once() -> None:
    factory = _Counting(DispatcherRecorder())
    lazy = LazyListener(factory, "foo")

    _ = await lazy.resolve()
    _ = await lazy.resolve()

    assert factory.calls == 1


@pytest.mark.anyio
async def test_calling_it_calls_the_built_listener_with_what_it_takes() -> None:
    received: list[object] = []
    event = Event()

    async def factory() -> object:
        return received.append

    await LazyListener(factory)(event, "name", object())

    assert received == [event]


def test_its_representation_names_the_factory_and_the_method() -> None:
    async def build_mailer() -> object:
        return object()

    lazy = LazyListener(build_mailer, "on_order_placed")

    assert repr(lazy) == (
        "LazyListener(test_its_representation_names_the_factory_and_the_method.<locals>"
        ".build_mailer, 'on_order_placed')"
    )


def test_it_tells_which_method_it_calls() -> None:
    assert LazyListener(_Counting(object()), "on_foo").method == "on_foo"
    assert LazyListener(_Counting(object())).method == "__call__"
