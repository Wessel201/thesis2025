#!/usr/bin/env python3
import os
import time
import threading
import asyncio
import queue
import sys
from contextlib import nullcontext
from energytest.experiment import Experiment, run_experiment
from energytest.utils import context_profile, energy_profile

class WaitPatternExperiment(Experiment):
    """
    Compare busy-waiting vs blocking vs async waits in a 100-item producer–consumer.
    """

    def __init__(self, mode: str, work_dir: str = '/tmp', output: str = 'wait_results.csv'):
        assert mode in ('busy', 'blocking', 'async')
        super().__init__(work_dir=work_dir, output=output)
        print(work_dir)
        self.mode = mode
        self.total_items = 100
        self.interval_s = 0.1
    def setup(self):
        os.makedirs(self.work_dir, exist_ok=True)

    @context_profile
    def _consume_spin(self, q: queue.Queue):
        """Busy-wait until an item appears, then pop it."""
        while True:
            try:
                _ = q.get_nowait()
                return
            except queue.Empty:
                continue

    @context_profile
    def _consume_block(self, q: queue.Queue, cond: threading.Condition):
        """Block on a condition variable until an item arrives."""
        with cond:
            while q.empty():
                cond.wait()
            _ = q.get()

    @energy_profile
    async def _consume_async(self, q: asyncio.Queue):
        """Async await until an item appears."""
        _ = await q.get()
        return

    def _run(self) -> dict:
        """
        Single trial: spawn one producer (thread or task), then consume N items
        using the selected wait strategy.
        """
        if self.mode in ('busy', 'blocking'):
            q = queue.Queue()
            cond = threading.Condition()
            ctx_mgr = cond if self.mode == 'blocking' else nullcontext()

            def producer():
                for i in range(self.total_items):
                    with ctx_mgr:
                        q.put(i)
                        if self.mode == 'blocking':
                            cond.notify()
                    time.sleep(self.interval_s)

            prod = threading.Thread(target=producer)
            prod.start()
            for _ in range(self.total_items):
                if self.mode == 'busy':
                    self._consume_spin(q)
                else:
                    self._consume_block(q, cond)

            prod.join()

        else:
            async def producer_async(q: asyncio.Queue):
                for i in range(self.total_items):
                    await q.put(i)
                    await asyncio.sleep(self.interval_s)

            async def runner():
                q_async = asyncio.Queue()
                prod_task = asyncio.create_task(producer_async(q_async))
                for _ in range(self.total_items):
                    await self._consume_async(q_async)
                await prod_task

            asyncio.run(runner())
        return {}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        for mode in ('busy', 'blocking', 'async'):
            print(f"\n=== Running mode: {mode} ===")
            exp = WaitPatternExperiment(
                mode=mode,
                work_dir='./wait_exp',
                output=f'results_{mode}.csv'
            )
            run_experiment(exp, runs=3, verbose=True)
    else:
        mode = sys.argv[1]
        print(f"\n=== Running mode: {mode} ===")
        exp = WaitPatternExperiment(
                mode=mode,
                work_dir='./wait_exp',
                output=f'results_{mode}.csv'
            )
        run_experiment(exp, runs=3, verbose=False)

