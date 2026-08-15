from __future__ import annotations

import asyncio

import pytest

from app.controller import ApplicationController


@pytest.mark.asyncio
async def test_request_shutdown_keeps_single_task_alive() -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    class ControllerStub:
        _closing = False
        _shutdown_task = None

        async def shutdown(self) -> None:
            started.set()
            await release.wait()

    controller = ControllerStub()

    ApplicationController.request_shutdown(controller)
    first_task = controller._shutdown_task
    ApplicationController.request_shutdown(controller)

    assert first_task is not None
    assert controller._shutdown_task is first_task
    await started.wait()
    release.set()
    await first_task
