#!/usr/bin/env python3
import os
import sys
import psutil
import multiprocessing as mp
import numpy as np
from concurrent.futures import ProcessPoolExecutor
from energytest.experiment import Experiment, run_experiment
from energytest.utils import energy_profile


if __name__ == "__main__":
    mp.set_start_method('spawn', force=True)

class CPUConcurrencyExperiment(Experiment):
    """
    Quantify energy & time vs. process concurrency for:
      - Segmented sieve of Eratosthenes up to 1e7
      - Dense double-precision matmul of size 4096x4096
    """
    def __init__(self, kernel: str, num_workers: int,
                 work_dir: str = '/tmp', output: str = 'cpu_results.csv'):
        assert kernel in ('sieve', 'matmul'), "kernel must be 'sieve' or 'matmul'"
        super().__init__(work_dir=work_dir, output=output)
        self.kernel = kernel
        self.num_workers = num_workers
        self.sieve_n = 10**7
        self.matmul_n = 4096

    def setup(self):
        os.makedirs(self.work_dir, exist_ok=True)

    @energy_profile
    def sieve_task(self, start: int, end: int):
        """Segmented sieve"""
        size = end - start
        sieve = bytearray(b'\x01') * size
        limit = int(end**0.5) + 1
        for p in range(2, limit):
            first = ((start + p - 1) // p) * p
            for m in range(first, end, p):
                sieve[m - start] = 0
        _ = sum(sieve)

    @energy_profile
    def matmul_task(self, rows: slice):
        """ matmul for rows of A."""
        N = self.matmul_n
        A = np.random.rand(rows.stop - rows.start, N)
        B = np.random.rand(N, N)
        _ = A.dot(B)

    def _run(self) -> dict:
        ctx = mp.get_context('spawn')
        if self.kernel == 'sieve':
            N = self.sieve_n
            per = N // self.num_workers
            segments = [
                (i*per, (i+1)*per if i < self.num_workers - 1 else N)
                for i in range(self.num_workers)
            ]
            starts, ends = zip(*segments)
            map_args = (starts, ends)
            task_fn = self.sieve_task

        else:
            N = self.matmul_n
            per = N // self.num_workers
            segments = [
                slice(i*per, (i+1)*per if i < self.num_workers - 1 else N)
                for i in range(self.num_workers)
            ]
            map_args = (segments,)
            task_fn = self.matmul_task
        with ProcessPoolExecutor(
            max_workers=self.num_workers,
            mp_context=ctx
        ) as executor:
            list(executor.map(task_fn, *map_args))
        return {}

if __name__ == "__main__":
    phys = psutil.cpu_count(logical=False) or 1
    configs = sorted({1, 2, 4, 5, phys, phys * 2})
    kernels = sys.argv[1:] or ['sieve']
    for kernel in kernels:
        for w in [5]:
            print(f"\n=== Kernel={kernel}, workeras={w} ===")
            out_prefix = f"cpu_{kernel}_{w}"
            exp = CPUConcurrencyExperiment(
                kernel=kernel,
                num_workers=w,
                work_dir=f"/tmp/cpu_{kernel}_{w}",
                output=f"{kernel}_{out_prefix}.csv",
            )
            run_experiment(exp, runs=3, verbose=True)
