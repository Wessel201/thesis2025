import os
import glob
import subprocess
import json
import psutil
import pyRAPL
import warnings

# Initialize RAPL sensor
pyRAPL.setup()

BATTERY_CHARGE_PATH = '/sys/class/power_supply/BAT0/charge_now'

def read_battery_charge():
    """Read the current battery charge in microampere-hours (uAh)."""
    try:
        with open(BATTERY_CHARGE_PATH, 'r') as f:
            return int(f.read().strip())
    except Exception:
        return None


def detect_powercap_zones():
    zones = []
    for path in glob.glob('/sys/class/powercap/*/energy_uj'):
        zones.append(path)
    return zones

def read_powercap():
    metrics = {}
    for uj_path in detect_powercap_zones():
        name = os.path.basename(os.path.dirname(uj_path))
        try:
            uj = int(open(uj_path).read().strip())
            metrics[f'{name}_energy_uj'] = uj
        except:
            continue
    return metrics

def detect_hwmon_sensors():
    base = '/sys/class/hwmon'
    sensors = []
    for hw in glob.glob(f'{base}/hwmon*'):
        label_file = os.path.join(hw, 'name')
        name = open(label_file).read().strip() if os.path.exists(label_file) else os.path.basename(hw)
        for file in glob.glob(f'{hw}/in*_input') + glob.glob(f'{hw}/curr*_input') + glob.glob(f'{hw}/power*_input') + glob.glob(f'{hw}/temp*_input'):
            label = os.path.basename(file).replace('_input','')
            sensors.append((name, label, file))
    return sensors

def read_hwmon():
    metrics = {}
    for name, label, path in detect_hwmon_sensors():
        try:
            val = int(open(path).read().strip())
            metrics[f'{name}_{label}'] = val
        except:
            continue
    return metrics

    
def detect_nvme_devices():
    """Detect NVMe block device namespaces, return list of /dev paths."""
    nvme_devs = []
    # NVMe controllers listed under /sys/class/nvme/nvme*
    for ctrl_path in glob.glob('/sys/class/nvme/nvme*'):
        ctrl_name = os.path.basename(ctrl_path)
        # namespaces under each controller: nvme0n1, nvme0n2, etc.
        for ns_path in glob.glob(os.path.join(ctrl_path, f'{ctrl_name}n*')):
            dev = f"/dev/{os.path.basename(ns_path)}"
            if os.path.exists(dev):
                nvme_devs.append(dev)
    return nvme_devs

class NVMeSensor:
    """Sensor abstraction for NVMe SMART log counters."""
    def __init__(self):
        self.devices = detect_nvme_devices()

    def read_counters(self):
        """Return dict of NVMe SMART counters for each device."""
        metrics = {}
        for dev in self.devices:
            try:
                output = subprocess.check_output(
                    ['nvme', 'smart-log', '--output-format=json', dev],
                    stderr=subprocess.DEVNULL
                ).decode('utf-8')
                data = json.loads(output)
                dur = data.get('data_units_read', None)
                duw = data.get('data_units_written', None)
                metrics[f'nvme_{os.path.basename(dev)}_data_units_read'] = dur
                metrics[f'nvme_{os.path.basename(dev)}_data_units_written'] = duw
            except Exception:
                continue
        return metrics

class EnergySensor:
    """Context manager for RAPL energy measurements."""
    def __init__(self, name: str):
        self._meas = pyRAPL.Measurement(name)
        self._energy_j = 0.0

    def __enter__(self):
        self._meas.begin()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._meas.end()
        
        total_uj = 0.0
        if hasattr(self._meas, 'result') and self._meas.result is not None:
            pkg_uj = getattr(self._meas.result, 'pkg', []) or []
            dram_uj = getattr(self._meas.result, 'dram', []) or []
            try:
                total_uj = sum(pkg_uj) + sum(dram_uj)
            except TypeError:
                total_uj = 0.0
        if total_uj == 0.0:
            warnings.warn(
                f"Energy measurement for '{self._meas.label}' was 0.0 Joules. ",
                UserWarning
            )
        self._energy_j = total_uj / 1e6

    @property
    def results(self) -> dict:
        """Returns a dictionary with the energy consumption in Joules."""
        return {'energy_j': self._energy_j}