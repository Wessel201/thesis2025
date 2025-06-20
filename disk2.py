#!/usr/bin/env python3
import os
import time, sys
from energytest.experiment import Experiment, run_experiment
from energytest.utils import energy_profile

class DiskWriteExperiment(Experiment):
    def __init__(self, total_size: int, chunk_size: int,
                 buffered: bool = True, work_dir: str = '/tmp',
                 output: str = 'disk_results.csv'):
        super().__init__(work_dir=work_dir, output=output)
        self.total_size = total_size
        self.chunk_size = chunk_size
        self.buffered = buffered

    def setup(self):
        os.makedirs(self.work_dir, exist_ok=True)

    @energy_profile
    def write_chunk(self, path: str, data: bytes):
        with open(path, 'ab', buffering=self.chunk_size if self.buffered else 0) as f:
            f.write(data)
            if not self.buffered:
                f.flush()
                os.fsync(f.fileno())

    def _run(self) -> dict:
        path = os.path.join(self.work_dir, f"test_{self.chunk_size}.dat")
        open(path, 'wb').close()
        total_written = 0
        while total_written < self.total_size:
            length = min(self.chunk_size, self.total_size - total_written)
            buffer = os.urandom(length)
            self.write_chunk(path, buffer)
            total_written += length

        if self.buffered:
            with open(path, 'r+b') as f:
                f.flush()
                os.fsync(f.fileno())
        os.remove(path)

if __name__ == "__main__":
    mode = sys.argv[1] 
    modes = {'Buffered': True, 'Unbuffered': False}
    cc = int(sys.argv[2])
    chunk_size = cc * 1024

    exp = DiskWriteExperiment(
        total_size= 100 * 1024 * 1024,
        chunk_size=chunk_size,
        buffered=modes[mode],
        work_dir='/tmp',
        output=f'results_{mode}_{cc}kb.csv'
        
    )
    run_experiment(exp, runs=3, verbose=False)