#!/usr/bin/env python3
import os, sys
from concurrent.futures import ThreadPoolExecutor
from energytest.experiment import Experiment, run_experiment
from energytest.utils import energy_profile

class TaskGranularityExperiment(Experiment):
    """
    Quantifies how task size (1e7, 4 x 2500k, 10000 x1k items) influences
    execution time and energy for 1e8 FLOP total on a 4-thread pool.
    """
    def __init__(self, mode: str,
                 total_items: int = 1_000_000_0,
                 work_dir: str = '/tmp',
                 output: str = 'granularity.csv'):
        assert mode in ('sequential', 'coarse', 'fine')
        super().__init__(work_dir=work_dir, output=output)
        self.mode = mode
        self.total_items = total_items

    def setup(self):
        # create output directory if needed
        os.makedirs(self.work_dir, exist_ok=True)

    @energy_profile
    def compute_chunk(self, n_items: int):
        """
        Simulate 100 FLOP per item by doing 50 multiply-add operations.
        This method is profiled per-call for its energy & time.
        """
        total = 0.0
        for i in range(n_items):
            a = float(i)
            for _ in range(50):
                a = a * 1.000001
                a = a + 0.000001
            total += a
        return total

    def _run(self) -> dict:
        """
        Partition work according to mode, dispatch to ThreadPoolExecutor(max_workers=4).
        All compute work goes through compute_chunk(), which is profiled.
        """
        if self.mode == 'sequential':
            task_sizes = [self.total_items]
        elif self.mode == 'coarse':
            task_sizes = [self.total_items // 4] * 4
        else:
            task_sizes = [self.total_items // 1000] * 1000
        with ThreadPoolExecutor(max_workers=4) as executor:
            for _ in executor.map(self.compute_chunk, task_sizes):
                pass
        return {}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        for mode in ('sequential', 'coarse', 'fine'):
            print(f"\n=== Task Granularity experiment: mode={mode} ===")
            exp = TaskGranularityExperiment(
                mode=mode,
                work_dir=f"/tmp/granularity_{mode}",
                output=f"granularity_{mode}.csv"
            )
            run_experiment(exp, runs=3, verbose=True)
    else:
        mode = sys.argv[1]
        print(f"\n=== Task Granularity experiment: mode={mode} ===")
        exp = TaskGranularityExperiment(
                mode=mode,
                work_dir=f"/tmp/granularity_{mode}",
                output=f"granularity_{mode}.csv"
            )
        run_experiment(exp, runs=3, verbose=False)

    
