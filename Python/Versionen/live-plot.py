import nidaqmx
import numpy as np
import matplotlib.pyplot as plt

CHANNEL = "Dev1/ai0"
SAMPLE_RATE = 2000
DISPLAY_WINDOW = 1.0

task = nidaqmx.Task()
task.ai_channels.add_ai_voltage_chan(CHANNEL)
task.timing.cfg_samp_clk_timing(rate=SAMPLE_RATE)

plt.ion()
fig, ax = plt.subplots()
line, = ax.plot([], [])
ax.set_title("Live Voltage Plot")
ax.set_xlabel("Time (s)")
ax.set_ylabel("Voltage (V)")
ax.grid(True)

try:
    while True:
        data = np.array(task.read(number_of_samples_per_channel=int(SAMPLE_RATE * DISPLAY_WINDOW)))
        t = np.linspace(0, DISPLAY_WINDOW, len(data))
        line.set_xdata(t)
        line.set_ydata(data)
        ax.set_xlim(0,DISPLAY_WINDOW)
        ax.set_ylim(np.min(data)-0.1, np.max(data)+0.1)
        plt.pause(0.1)
except KeyboardInterrupt:
    print("Messung beendet.")
finally:
    task.close()