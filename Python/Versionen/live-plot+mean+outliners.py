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

text_mean = fig.text(0.15, 0.9, "---")
text_std = fig.text(0.15, 0.85, "---")

def remove_outliers(data, k=20, t0=3):
    mask = np.ones(len(data), dtype=bool)
    for i in range(len(data)):
        start = max(0, i-k)
        end =min(len(data), i+k)
        window = data[start:end]
        
        med = np.median(window)
        mad = np.median(np.abs(window - med))
        if mad == 0:
            continue
        z_score = 0.6745 * (data[i] - med) / mad
        if np.abs(z_score) > t0:
            mask[i] = False
        return data[mask]

try:
    while True:
        data_raw = np.array(task.read(number_of_samples_per_channel=int(SAMPLE_RATE * DISPLAY_WINDOW)))
        data_clean = remove_outliers(data_raw)
        t = np.linspace(0, DISPLAY_WINDOW, len(data_raw))
        line.set_xdata(t)
        line.set_ydata(data_raw)
        ax.set_xlim(0,DISPLAY_WINDOW)
        ax.set_ylim(np.min(data_raw)-0.1, np.max(data_raw)+0.1)
        
        text_mean.set_text(f"Mean: {np.mean(data_clean):.4f} V")
        text_std.set_text(f"Std: {np.std(data_clean):.4f} V")
        
        plt.pause(0.1)
except KeyboardInterrupt:
    print("Messung beendet.")
finally:
    task.close()