"""
Live-Messung mit NI-DAQmx, Outlier-Removal, mean/std Anzeige und Aufnahme
- Live-Plot des clean Signals
- Live-mean/std Anzeige (rot, fett)
- 'm': Nächste 20 Sekunden aufnehmen und Mittelwert/std speichern
- 's': Gespeicherte Messungen in CSV speichern
- 'q': Beenden
"""

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import time
import nidaqmx

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
# NI-DAQ Konfiguration
# -----------------------------
CHANNEL = "Dev1/ai0"  # Ändere dies auf deinen Kanal
SAMPLE_RATE = 1000     # Hz
BLOCK_SIZE = 500       # Samples pro Block

task = nidaqmx.Task()
task.ai_channels.add_ai_voltage_chan(CHANNEL)
task.timing.cfg_samp_clk_timing(rate=SAMPLE_RATE)

# -----------------------------
# Aufnahme & Speicherung
# -----------------------------
saved_measurements = []
is_recording = False
record_start_time = None
record_buffer = []
RECORD_DURATION = 20  # Sekunden

def record_start():
    global is_recording, record_start_time, record_buffer
    is_recording = True
    record_start_time = time.time()
    record_buffer = []
    status_text.set_text("Aufnahme läuft...")

def save_to_csv(filename="measurements.csv"):
    if not saved_measurements:
        print("Keine Messungen zum Speichern.")
        return
    df = pd.DataFrame(saved_measurements)
    df.to_csv(filename, index=False)
    print(f"{len(saved_measurements)} Messungen gespeichert in {filename}")

# -----------------------------
# Plot vorbereiten
# -----------------------------
print("=== ADW Live-Viewer gestartet ===")
print("Taste 'q' drücken, um zu beenden.\n")
print("Taste 'k' drücken, um die Referenzmessung erneut durchzuführen. \n")
print("Taste 'm' drücken, um einen Messpunkt aufzunehmen. \n")
print("Taste 's' drücken, um die Messung als .csv abzuspeichern. \n")

plt.ion()
fig, ax = plt.subplots()
ax.set_title("Live clean signal with mean/std")
ax.set_xlabel("Sample Index")
ax.set_ylabel("Amplitude")
line, = ax.plot([], [], lw=1)

text_mean = ax.text(0.5, 1.05, "", transform=ax.transAxes, fontsize=14, color='red', weight='bold', ha='center')
text_std  = ax.text(0.5, 0.98, "", transform=ax.transAxes, fontsize=14, color='red', weight='bold', ha='center')
status_text = ax.text(0.02, 0.9, "", transform=ax.transAxes, fontsize=12, color='blue')

# -----------------------------
# Tastatur-Funktion
# -----------------------------
def on_key(event):
    if event.key == 'm':
        record_start()
    elif event.key == 's':
        save_to_csv()
    elif event.key == 'q':
        plt.close(fig)

fig.canvas.mpl_connect('key_press_event', on_key)

# -----------------------------
# Hauptloop
# -----------------------------
try:
    current_mean = 0
    current_std = 0
    pause_time = 0.05  # Sekunden zwischen Updates

    while plt.fignum_exists(fig.number):
        # --- Messdaten vom NI-DAQ ---
        raw = np.array(task.read(number_of_samples_per_channel=BLOCK_SIZE))
        
        # --- Outlier entfernen ---
        clean = remove_outliers(raw)
        current_mean = np.mean(clean)
        current_std = np.std(clean)

        # --- Plot aktualisieren ---
        line.set_xdata(np.arange(len(clean)))
        line.set_ydata(clean)
        ax.set_xlim(0, len(clean))
        ax.set_ylim(min(clean)-0.5, max(clean)+0.5)

        # --- Text aktualisieren ---
        text_mean.set_text(f"Mean: {current_mean:.4f}")
        text_std.set_text(f"Std:  {current_std:.4f}")

        # --- Aufnahme prüfen ---
        if is_recording:
            record_buffer.extend(clean)
            elapsed = time.time() - record_start_time
            status_text.set_text(f"Aufnahme läuft... {elapsed:.1f}/{RECORD_DURATION} s")
            if elapsed >= RECORD_DURATION:
                m = np.mean(record_buffer)
                s = np.std(record_buffer)
                saved_measurements.append({"mean": m, "std": s})
                print(f"Messung aufgenommen: mean={m:.4f}, std={s:.4f}")
                is_recording = False
                status_text.set_text("Aufnahme beendet.")

        fig.canvas.draw_idle()
        plt.pause(pause_time)

except KeyboardInterrupt:
    print("Messung manuell abgebrochen.")

finally:
    save_to_csv()
    task.close()
    plt.ioff()
    plt.close(fig)