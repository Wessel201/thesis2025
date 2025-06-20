
import time, subprocess, sys
BATTERY_CHARGE_PATH = '/sys/class/power_supply/BAT0/charge_now'

def read_battery_charge():
    try:
        with open(BATTERY_CHARGE_PATH, 'r') as f:
            return int(f.read().strip())
    except:
        return None

def wait_for_update(initial_value, poll_interval=0.1):
    while True:
        time.sleep(poll_interval)
        current = read_battery_charge()
        if current is None:
            continue
        if current != initial_value:
            return current


def main(blocks):
    if len(sys.argv) < 2:
        print("Usage: python measure_energy.py <script> [args...]")
        sys.exit(1)

    cmd = sys.argv[1:]
    initial = read_battery_charge()
    if initial is None:
        sys.exit(1)
    updated = wait_for_update(initial)
    start_time = time.perf_counter()
    start_charge = updated
    runs = 0
    try:
        while True:
            subprocess.run(cmd)
            runs += 1
            elapsed = time.perf_counter() - start_time
            print(elapsed % 23, read_battery_charge())
            if elapsed % 23.0 < 3 and runs > 9:
                if read_battery_charge() != initial:
                    break
    except:
        pass
    end_time = time.perf_counter()
    end_charge = read_battery_charge()
    if end_charge is None:
        sys.exit(1)
    total_energy = start_charge - end_charge
    measured_per_run = total_energy / runs if runs > 0 else float('nan')
    elapsed_seconds = end_time - start_time
    measrued_rate_uAh_per_sec = total_energy / elapsed_seconds if elapsed_seconds > 0 else float('nan')
    avg_run_duration = elapsed_seconds / runs
    extra_time = elapsed_seconds % 23
    real_time = (elapsed_seconds // 23) * 23
    real_rate = total_energy/real_time
    extra_polated = real_rate * avg_run_duration
        
    

    print(f"Total time: {elapsed_seconds}")
    # print(f"diff measured vs real time {elapsed_seconds - real_time}")
    # print(f"Runs executed: {runs}")
    # print(f"Measured energy per run: {measured_per_run:.2f} uAh")
    print(f"{cmd}, energy per trial: {(extra_polated/3):.2f} uAh")


if __name__ == "__main__":
    main(1)