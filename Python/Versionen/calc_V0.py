import nidaqmx
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import time

# -----------------------------
# DAQ-Konfiguration
# -----------------------------
CHANNEL = "Dev1/ai0"  # Dein Messkanal
SAMPLE_RATE = 2000     # Hz, Sample Rate
BLOCK_SIZE = 500       # Anzahl Samples pro Lesevorgang

# -----------------------------
# Outlier-Removal (MAD Methode)
# -----------------------------
def remove_outliers(data, k=15, t0=3):
    data = np.array(data)
    mask = np.ones(len(data), dtype=bool)
    for i in range(len(data)):
        left = max(0, i - k)
        right = min(len(data), i + k + 1)
        window = data[left:right]
        med = np.median(window)
        mad = np.median(np.abs(window - med))
        if mad == 0:
            continue
        z = 0.6745 * (data[i] - med) / mad
        if abs(z) > t0:
            mask[i] = False
    return data[mask]

# -----------------------------
# Plot vorbereiten
# -----------------------------
plt.ion()
fig, ax = plt.subplots()
ax.set_title("Live Data (raw) with cleaned Statistics")
ax.set_xlabel("Sample Index")
ax.set_ylabel("Voltage (V)")
line, = ax.plot([], [], lw=1)
text_mean = ax.text(0.7, 0.95, "", transform=ax.transAxes, color='red', fontsize=12, fontweight='bold')
text_std  = ax.text(0.7, 0.9,  "", transform=ax.transAxes, color='red', fontsize=12, fontweight='bold')
text_timer = ax.text(0.02, 0.82, "", transform=ax.transAxes, color='blue', fontsize=12, fontweight='bold')

# -----------------------------
# Variablen
# -----------------------------
V0 = None
is_ref_mode = False
ref_buffer = []
ref_start_time = None

is_recording = False
rec_buffer = []
rec_start_time = None

SAVE_DURATION = 20  # Sekunden Aufnahme für Referenz oder Messung

results = {"mean": [], "std": []}

# -----------------------------
# DAQ-Task erstellen
# -----------------------------
task = nidaqmx.Task()
task.ai_channels.add_ai_voltage_chan(CHANNEL)
task.timing.cfg_samp_clk_timing(rate=SAMPLE_RATE)

# -----------------------------
# Tastatur-Ereignisse
# -----------------------------
def on_key(event):
    global is_ref_mode, ref_buffer, ref_start_time
    global is_recording, rec_buffer, rec_start_time, V0

    if event.key == 'q':
        print("Beenden...")
        plt.close(fig)

    elif event.key == 'p':
        print("Referenzmessung gestartet (V0 bestimmen)...")
        is_ref_mode = True
        ref_buffer = []
        ref_start_time = time.time()
        ax.set_ylabel("Voltage (V)")  # Y-Achse vor Referenzmessung

    elif event.key == 'm':
        if V0 is None:
            print("V0 noch nicht gesetzt! Erst p drücken.")
            return
        print("Messung gestartet...")
        is_recording = True
        rec_buffer = []
        rec_start_time = time.time()

    elif event.key == 's':
        if len(results["mean"]) == 0:
            print("Keine Messdaten zum Speichern.")
            return
        df = pd.DataFrame(results)
        df.to_csv("measurement_results.csv", index=False)
        print("Daten gespeichert in measurement_results.csv")

fig.canvas.mpl_connect('key_press_event', on_key)

# -----------------------------
# Hauptloop
# -----------------------------
try:
    while plt.fignum_exists(fig.number):
        data = task.read(number_of_samples_per_channel=BLOCK_SIZE)
        data = np.array(data)
        clean = remove_outliers(data)
        mean_val = np.mean(clean)
        std_val  = np.std(clean)

        # --- Referenzmodus (p) ---
        if is_ref_mode:
            ref_buffer.extend(clean)
            elapsed = time.time() - ref_start_time
            remaining = max(0, SAVE_DURATION - elapsed)
            text_timer.set_text(f"Referenzmessung: {remaining:.0f}s")
            if elapsed >= SAVE_DURATION:
                V0 = np.mean(ref_buffer)
                print(f"Referenz gesetzt: V0 = {V0:.4f} V")
                is_ref_mode = False
                ax.set_ylabel("Voltage (dB)")  # nach Referenz in dB
                text_timer.set_text("")

        # --- Aufnahmemodus (m) ---
        if is_recording:
            data_db = 20*np.log10(np.maximum(np.abs(clean)/V0, 1e-12))
            rec_buffer.extend(data_db)
            elapsed = time.time() - rec_start_time
            remaining = max(0, SAVE_DURATION - elapsed)
            text_timer.set_text(f"Messung läuft: {remaining:.0f}s")
            if elapsed >= SAVE_DURATION:
                results["mean"].append(np.mean(rec_buffer))
                results["std"].append(np.std(rec_buffer))
                print(f"Messung gespeichert: mean={results['mean'][-1]:.2f} dB, std={results['std'][-1]:.2f} dB")
                is_recording = False
                text_timer.set_text("")

        # --- Plot ---
        display_data = clean if V0 is None else 20*np.log10(np.maximum(np.abs(clean)/V0, 1e-12))
        line.set_xdata(np.arange(len(display_data)))
        line.set_ydata(display_data)
        ax.set_xlim(0, len(display_data))
        ax.set_ylim(min(display_data)-0.5, max(display_data)+0.5)

        # --- Mean/Std Text ---
        text_mean.set_text(f"mean: {mean_val:.4f}" if V0 is None else f"mean(dB): {np.mean(display_data):.2f}")
        text_std.set_text(f"std:  {std_val:.4f}" if V0 is None else f"std(dB):  {np.std(display_data):.2f}")

        fig.canvas.draw_idle()
        plt.pause(0.05)

except KeyboardInterrupt:
    print("Messung manuell abgebrochen.")

finally:
    task.close()
    plt.ioff()
    plt.close(fig)