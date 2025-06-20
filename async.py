#!/usr/bin/env python3
import os
import sys
import time
import asyncio
import threading
import requests
import aiohttp
import aiohttp.web
from multiprocessing import Process
from energytest.experiment import Experiment, run_experiment
from energytest.utils import energy_profile


async def handle(request):
    """Server handler: waits 50ms, returns 1KB of data."""
    await asyncio.sleep(0.05)  # 50ms delay as per spec
    return aiohttp.web.Response(body=b'x' * 1024) # 1KB body

async def init_app():
    """Initializes the aiohttp server application."""
    app = aiohttp.web.Application()
    app.router.add_get('/', handle)
    return app

def run_server(port):
    """Entry point for the server process."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app = loop.run_until_complete(init_app())
    runner = aiohttp.web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    site = aiohttp.web.TCPSite(runner, '127.0.0.1', port)
    loop.run_until_complete(site.start())
    loop.run_forever()

class WebClientExperiment(Experiment):
    """
    Compares energy use of threading vs. asyncio for I/O-bound tasks.
    Implements the experiment described in Section 4.4.
    """
    def __init__(self, total_requests: int, concurrency: int, mode: str, port: int, **kwargs):
        super().__init__(**kwargs)
        if mode not in ['threads', 'async']:
            raise ValueError("Mode must be 'threads' or 'async'")
        self.total_requests = total_requests
        self.concurrency = concurrency
        self.mode = mode
        self.url = f"http://127.0.0.1:{port}"
        self.server_process = None

    def setup(self):
        return

    def _run(self):
        """Dispatches to the correct concurrency model."""
        if self.mode == 'threads':
            self._run_threads()
        else:
            asyncio.run(self._run_async())

    @energy_profile
    def _run_threads(self):
        """Executes requests using a thread-per-task model."""
        threads = []
        # Distribute the total requests across the concurrent threads
        requests_per_thread = self.total_requests // self.concurrency

        def worker():
            for _ in range(requests_per_thread):
                try:
                    requests.get(self.url)
                except requests.exceptions.RequestException as e:
                    pass

        for _ in range(self.concurrency):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

    # --- Model B: Async/Await ---
    @energy_profile
    async def _run_async(self):
        """Executes requests using a single asyncio event loop."""
        tasks = []
        requests_per_coro = self.total_requests // self.concurrency

        async def worker(session):
            for _ in range(requests_per_coro):
                try:
                    async with session.get(self.url) as response:
                        await response.read()
                except aiohttp.ClientError:
                    # Silently ignore errors
                    pass
        async with aiohttp.ClientSession() as session:
            for _ in range(self.concurrency):
                tasks.append(worker(session))
            await asyncio.gather(*tasks)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <threads|async> <concurrency>")
        print("Concurrency levels from paper: 100, 1000, 10000")
        sys.exit(1)

    mode = sys.argv[1]
    concurrency = int(sys.argv[2])
    port = 8080 
    total_requests = 100000

    print(f"Starting experiment: mode={mode}, concurrency={concurrency}, total_requests={total_requests}")

    exp = WebClientExperiment(
        total_requests=total_requests,
        concurrency=concurrency,
        mode=mode,
        port=port,
        work_dir='/tmp/io_experiment',
        output=f'results/io_{mode}_{concurrency}c.csv'
    )
    run_experiment(exp, runs=3, verbose=True)