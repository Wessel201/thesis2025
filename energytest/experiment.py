import os
import time
import csv
import uuid
from abc import ABC, abstractmethod
import psutil
from .sensors import EnergySensor, read_battery_charge, NVMeSensor
from .utils import get_profiles, clear_profiles

class Experiment(ABC):
    def __init__(self, work_dir: str = '/tmp', output: str = 'results.csv', measure_total_run: bool = True):
        self.work_dir = work_dir
        self.output = output
        self.measure_total_run = measure_total_run

    @abstractmethod
    def setup(self):
        pass

    @abstractmethod
    def _run(self) -> dict:
        pass

    def run(self) -> dict:
        os.makedirs(self.work_dir, exist_ok=True)
        
        profile_dir = os.path.join(self.work_dir, 'profiles')
        os.makedirs(profile_dir, exist_ok=True)
        os.environ['ENERGYTEST_PROFILE_DIR'] = profile_dir

        try:
            clear_profiles()

            # Snapshots before
            proc = psutil.Process()
            charge_before = read_battery_charge()
            cpu_before = psutil.cpu_times()
            mem_before = proc.memory_info().rss
            ctx_before = proc.num_ctx_switches()
            io_before = proc.io_counters()
            nvme_sensor = NVMeSensor()
            nvme_before = nvme_sensor.read_counters()

            run_energy_j = 0.0
            
            if self.measure_total_run:
                with EnergySensor(self.__class__.__name__) as sensor:
                    start_ns = time.perf_counter_ns()
                    self._run()
                    end_ns = time.perf_counter_ns()
                run_energy_j = sensor.results['energy_j']
            else:
                start_ns = time.perf_counter_ns()
                self._run()
                end_ns = time.perf_counter_ns()

            run_elapsed_ns = end_ns - start_ns
            charge_after = read_battery_charge()
            cpu_after = psutil.cpu_times()
            mem_after = proc.memory_info().rss
            ctx_after = proc.num_ctx_switches()
            io_after = proc.io_counters()
            nvme_after = nvme_sensor.read_counters()

            metrics = {'energy_j': run_energy_j, 'elapsed_ns': run_elapsed_ns}
            for f in cpu_before._fields:
                 metrics[f'cpu_{f}'] = getattr(cpu_after, f) - getattr(cpu_before, f)
            metrics['mem_delta_bytes'] = mem_after - mem_before
            metrics['ctx_voluntary'] = ctx_after.voluntary - ctx_before.voluntary
            metrics['ctx_involuntary'] = ctx_after.involuntary - ctx_before.involuntary
            metrics['io_read_calls'] = io_after.read_count - io_before.read_count
            metrics['io_write_calls'] = io_after.write_count - io_before.write_count
            for key, before in nvme_before.items():
                after = nvme_after.get(key)
                if isinstance(before, (int, float)) and isinstance(after, (int, float)):
                    metrics[f'{key}_delta'] = after - before

            profiles = get_profiles()
            metrics['function_profiles'] = profiles
            return metrics

        finally:
            if 'ENERGYTEST_PROFILE_DIR' in os.environ:
                del os.environ['ENERGYTEST_PROFILE_DIR']

def run_experiment(exp: Experiment, runs: int = 1, verbose: bool = False):
    """
    Run an Experiment, and write three CSV files.
    Appends to existing files. Uses a unique UUID for each run.
    """
    exp.setup()
    output_dir = os.path.dirname(exp.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    all_results = []
    for i in range(runs):
        run_data = exp.run()
        run_data['run_uuid'] = str(uuid.uuid4())
        all_results.append(run_data)
        if verbose:
            print_metrics = {k: v for k, v in run_data.items() if k != 'function_profiles'}
            print(f"Run {i+1} metrics:", print_metrics)

    if not all_results:
        print("No experiment runs were performed.")
        return

    metrics_file = exp.output
    base, ext = os.path.splitext(metrics_file)
    profiles_file = f"{base}_profiles{ext}"
    detailed_profiles_file = f"{base}_detailed_profiles{ext}"

    metrics_exists = os.path.exists(metrics_file)
    profiles_exists = os.path.exists(profiles_file)
    detailed_profiles_exists = os.path.exists(detailed_profiles_file)

    m_mode = 'a' if metrics_exists else 'w'
    p_mode = 'a' if profiles_exists else 'w'
    dp_mode = 'a' if detailed_profiles_exists else 'w'
    
    with open(metrics_file, m_mode, newline='') as mf, \
         open(profiles_file, p_mode, newline='') as pf, \
         open(detailed_profiles_file, dp_mode, newline='') as dpf:

        mwriter = csv.writer(mf)
        pwriter = csv.writer(pf)
        dpwriter = csv.writer(dpf)

        metric_keys = list(all_results[0].keys())
        metric_keys.remove('function_profiles')
        metric_keys.remove('run_uuid')
        metric_keys.insert(0, 'run_uuid')

        if not metrics_exists:
            mwriter.writerow(metric_keys)
        
        if not profiles_exists:
            pwriter.writerow(['run_uuid', 'func_name', 'call_count', 'total_energy_j', 'total_elapsed_ns'])
        
        if not detailed_profiles_exists:
            dpwriter.writerow(['run_uuid', 'func_name', 'energy_j', 'elapsed_ns'])

        for result in all_results:
            run_uuid = result.get('run_uuid')
            profiles = result.get('function_profiles', [])
            
            mwriter.writerow([result.get(k) for k in metric_keys])

            agg = {}
            for rec in profiles:
                name = rec['func_name']
                e = rec.get('energy_j', 0.0)
                t = rec.get('elapsed_ns', 0)
                if name not in agg:
                    agg[name] = {'count': 0, 'energy_j': 0, 'elapsed_ns': 0}
                agg[name]['count'] += 1
                agg[name]['energy_j'] += e
                agg[name]['elapsed_ns'] += t
            
            for name, data in agg.items():
                pwriter.writerow([run_uuid, name, data['count'], data['energy_j'], data['elapsed_ns']])
            
            for rec in profiles:
                dpwriter.writerow([run_uuid, rec['func_name'], rec['energy_j'], rec['elapsed_ns']])

            if verbose:
                print(f"Run {result.get('run_uuid')} aggregated function profiles:\n", agg)

    print(f"Results written to {metrics_file}, {profiles_file}, and {detailed_profiles_file}")