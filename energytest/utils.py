import functools
import time
import psutil
import threading
import os
import json
import glob
from .sensors import EnergySensor

energy_sensor_lock = threading.Lock()

class FunctionProfiler:
    """
    Profiles function calls for energy and time.
    This version is process-safe by reading its configuration from an
    environment variable, making it compatible with 'spawn'.
    """
    _records = []

    @staticmethod
    def _get_profile_dir():
        """Reads the profile directory path from an environment variable."""
        return os.environ.get('ENERGYTEST_PROFILE_DIR')

    @classmethod
    def profile(cls, func):
        """Decorator: measures energy + time, writes to a file if configured."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with energy_sensor_lock:
                with EnergySensor(func.__name__) as sensor:
                    start_ns = time.perf_counter_ns()
                    result = func(*args, **kwargs)
                    end_ns = time.perf_counter_ns()
                energy = sensor.results['energy_j']

            record = {
                'func_name': func.__name__,
                'energy_j': energy,
                'elapsed_ns': end_ns - start_ns
            }
            
            profile_dir = cls._get_profile_dir()
            if profile_dir:
                pid = os.getpid()
                ts = f"{time.time():.6f}".replace('.', '')
                fpath = os.path.join(profile_dir, f"prof_{pid}_{ts}.json")
                try:
                    with open(fpath, 'w') as f:
                        json.dump(record, f)
                except IOError as e:
                    print(f"Warning: Could not write profile record to {fpath}: {e}")
            else:
                cls._records.append(record)
            return result
        return wrapper

    @classmethod
    def get_records(cls):
        """Collects records from memory and/or the profile directory."""
        records = list(cls._records)
        profile_dir = cls._get_profile_dir()
        if profile_dir:
            for fpath in glob.glob(os.path.join(profile_dir, "*.json")):
                try:
                    with open(fpath, 'r') as f:
                        records.append(json.load(f))
                except (IOError, json.JSONDecodeError):
                    continue
        return records

    @classmethod
    def clear(cls):
        """Clears records from memory and the profile directory."""
        cls._records.clear()
        profile_dir = cls._get_profile_dir()
        if profile_dir:
            time.sleep(0.01)
            for fpath in glob.glob(os.path.join(profile_dir, "*.json")):
                try:
                    os.remove(fpath)
                except OSError:
                    continue

# Public decorators and functions
energy_profile = FunctionProfiler.profile
get_profiles = FunctionProfiler.get_records
clear_profiles = FunctionProfiler.clear



class DetailedProfiler:
    _records = []
    _lock = threading.Lock()

    @classmethod
    def profile(cls, func):
        """Decorator: includes args & return val."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with energy_sensor_lock:
                with EnergySensor(func.__name__) as sensor:
                    start_ns = time.perf_counter_ns()
                    result = func(*args, **kwargs)
                    end_ns = time.perf_counter_ns()
                energy = sensor.results.get('energy_j', 0.0)

            with cls._lock:
                cls._records.append({
                    'func_name': func.__name__,
                    'args': args,
                    'kwargs': kwargs,
                    'return': result,
                    'energy_j': energy,
                    'elapsed_ns': end_ns - start_ns
                })
            return result
        return wrapper

    @classmethod
    def get_records(cls):
        with cls._lock:
            return list(cls._records)

    @classmethod
    def clear(cls):
        with cls._lock:
            cls._records.clear()

context_profile = DetailedProfiler.profile
get_detailed_profiles = DetailedProfiler.get_records
clear_detailed_profiles = DetailedProfiler.clear