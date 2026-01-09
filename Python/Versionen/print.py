import nidaqmx
import time

CHANNEL = "Dev1/ai0"
SAMPLE_RATE = 2000
BLOCK = 1000

task = nidaqmx.Task()
task.ai_channels.add_ai_voltage_chan(CHANNEL)
task.timing.cfg_samp_clk_timing(rate=SAMPLE_RATE)

print("Live-Werte")
try:
    while True:
        data = task.read(number_of_samples_per_channel=BLOCK)
        value = sum(data) / len(data)
        print(f"Spannung: {value:.6f} V")
        time.sleep(0.1)
except KeyboardInterrupt:
    print("Messung beendet.")
finally:
    task.close()