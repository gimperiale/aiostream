from asyncio import iscoroutinefunction

import math
import anyio
from anyio import sleep, fail_after, create_task_group, create_semaphore

__all__ = ['iscoroutinefunction', 'time', 'sleep_forever', 'open_channel',
           'sleep', 'fail_after', 'create_task_group', 'create_semaphore']


async def sleep_forever():
    while True:
        # Sleep for a day
        await anyio.sleep(60 * 60 * 24)


async def time():
    asynclib = anyio._detect_running_asynclib()
    if asynclib == 'asyncio':
        import asyncio
        return asyncio.get_running_loop().time()
    if asynclib == 'trio':
        import trio
        return trio.current_time()
    if asynclib == 'curio':
        import curio
        return await curio.clock()
    raise RuntimeError("Asynclib detection failed")


def open_channel(capacity=0):
    asynclib = anyio._detect_running_asynclib()
    if asynclib == 'trio':
        import trio
        return trio.open_memory_channel(capacity)

    class ClosedResourceError(IOError):
        pass

    senders = set()
    sentinel = object()
    send_queue = anyio.create_queue(1)
    maxsize = 0 if capacity == math.inf else 1 if capacity == 0 else capacity
    receive_queue = anyio.create_queue(maxsize)

    class ReceiveChannel:

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return await self.receive()
            except ClosedResourceError:
                raise StopAsyncIteration

        async def receive(self):
            item = sentinel
            while item == sentinel:
                if not senders and receive_queue.empty():
                    raise ClosedResourceError
                item = await receive_queue.get()
            if capacity == 0:
                await send_queue.put(None)
            return item

        @classmethod
        def clone(cls):
            return cls()

    class SendChannel:

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            senders.remove(self)
            if not receive_queue.full():
                await receive_queue.put(sentinel)

        async def send(self, item):
            await receive_queue.put(item)
            if capacity == 0:
                await send_queue.get()

        @classmethod
        def clone(cls):
            instance = cls()
            senders.add(instance)
            return instance

    return SendChannel.clone(), ReceiveChannel.clone()
