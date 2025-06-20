
import time, subprocess, sys
BATTERY_CHARGE_PATH = '/sys/class/power_supply/BAT0/charge_now'

def read_battery_charge():
    try:
        with open(BATTERY_CHARGE_PATH, 'r') as f:
            return int(f.read().strip())
    except:
        return None
    
if __name__ == "__main__":
    before = read_battery_charge()
    t1 = time.perf_counter()
    time.sleep(200)
    cur = read_battery_charge()
    while True: 
        time.sleep(1)
        next = read_battery_charge()
        if next != cur:
            break
    end = time.perf_counter() - t1
    print("time ", end)
    diff = next - before
    print("diff = ", diff)
    print("diff/s = ", diff/end)