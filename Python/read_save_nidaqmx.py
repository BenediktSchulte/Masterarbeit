"""
ADW Live Messung & Speicherung
Zweck: Liest analogen Input eines NI-DAQ Geräts (z. B. NI USB-6251),
zeigt ihn live an, und erlaubt gesteuerte Aufzeichnung & Speicherung.
"""

import nidaqmx # type: ignore
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, TextBox, CheckButtons
import keyboard # type: ignore
import time
from datetime import datetime
import numpy as np

# ========================== #
# ==== KONFIGURATION ==== #
# ========================== #
CHANNEL = "Dev1/ai0"        # Dein Messkanal
SAMPLE_RATE = 2000          # Hz - Abtastrate
DISPLAY_WINDOW = 0.5        # Sekunden pro Live-Anzeige
SAVE_FILE = "../data/data.csv"  # Name der Ausgabedatei
SAVE_DURATION = 20          # Sekunden Messzeit bei Speicherung
FILENAME = "Characterisation"

V0 = None
mean_list = []
std_list= []

is_ref_mode = False
ref_start_time = None
ref_buffer = []

is_recording = False
rec_start_time = None
rec_buffer = []
# ========================== #
# ==== INITIALISIERUNG ==== #
# ========================== #
task = nidaqmx.Task()
task.ai_channels.add_ai_voltage_chan(CHANNEL)
task.timing.cfg_samp_clk_timing(rate=SAMPLE_RATE)

plt.ion()  # interaktiver Modus
fig, ax = plt.subplots()
plt.subplots_adjust(bottom=0.4)
line, = ax.plot([], [])
ax.set_title("ADW Live-Messung")
ax.set_xlabel("Time (s)")
#ax.set_ylim(0, 1)
ax.grid(True)

status_text = fig.text(0.5, 0.92, "", ha="center", fontsize=14, color="red")

print("=== ADW Live-Viewer gestartet ===")
print("Taste 'q' drücken, um zu beenden.\n")
print("Taste 'k' drücken, um die Referenzmessung erneut durchzuführen. \n")
print("Taste 'm' drücken, um einen Messpunkt aufzunehmen. \n")
print("Taste 's' drücken, um die Messung als .csv abzuspeichern. \n")

# ========================== #
# ==== FUNKTIONEN ==== #
# ========================== #

def remove_outliers(data, k=15, t0=3):
    """Entfernt Ausreißer aus den Daten"""
    data = np.array(data)
    mask =np.ones(len(data), dtype=bool)
    for i in range(len(data)):
        left = max(0, i-k)
        right = min(len(data), i+k+1)
        window = data[left:right]
        
        med = np.median(window)
        mad = np.median(np.abs(window - med))
        if mad == 0:
            continue
        z = 0.6745 * (data[i] - med) / mad
        if np.abs(z) > t0:
            mask[i] = False
    return data[mask]

def save_to_csv(filename):
    """Speichert Messdaten in CSV."""
    timestamp = datetime.now().strftime("%Y-%m-%d")
    filename = f"{timestamp}-{filename}.csv"
    df = pd.DataFrame({"mean": mean_list, "std": std_list})
    df.to_csv(filename, index=False)
    print(f"Daten gespeichert in: {filename}")

def update_sample_rate(text):
    global SAMPLE_RATE
    try:
        SAMPLE_RATE = float(text)
        task.timing.cfg_samp_clk_timing(rate=SAMPLE_RATE)
        print(f"Neue Sample_Rate: {SAMPLE_RATE} Hz")
    except ValueError:
        print("Ungültige Eingabe für Sample_Rate")

def update_display_window(text):
    global DISPLAY_WINDOW
    try:
        DISPLAY_WINDOW = float(text)
        print(f"Neues Display_Window: {DISPLAY_WINDOW}")
    except ValueError:
        print("Ungültige Eingabe für Display_Window")

def update_yaxis_label():
    """y-Achsenbeschriftung von V in db ändern"""
    if V0 is None:
        ax.set_ylabel("Spannung (V)")
    else:
        ax.set_ylabel("Voltage level (db)")
    fig.canvas.draw_idle() 
    
# ========================== #
# ==== GUI-ELEMENTE ==== #
# ========================== #

mean_text = fig.text(0.15, 0.9, "Mean: ---", fontsize=14, color="blue")
std_text = fig.text(0.15, 0.85, "Std: ---", fontsize=14, color="blue")

# --- Textbox: Sample Rate ---
fig.text(0.175, 0.11, "Sample Rate (Hz)", ha="center", fontsize=10)
ax_rate = plt.axes([0.1, 0.05, 0.15, 0.05])
box_rate = TextBox(ax_rate, "", initial=str(SAMPLE_RATE))
box_rate.on_submit(update_sample_rate)

# --- Textbox: Display Window ---
fig.text(0.375, 0.11, "Display Window (s)", ha="center", fontsize=10)
ax_window = plt.axes([0.3, 0.05, 0.15, 0.05])
box_window = TextBox(ax_window, "", initial=str(DISPLAY_WINDOW))
box_window.on_submit(update_display_window)

# ========================== #
# ==== GUI-Tastatur ==== #
# ========================== #
def on_key(event):
    global is_ref_mode, ref_start_time, ref_buffer
    global is_recording, rec_start_time, rec_buffer
    if event.key == 'q':
        print("Beenden durch Benutzer.")
        plt.close(fig)
    elif event.key == 'k':
        print("Referenzwertsetzen durch Benutzer.")
        is_ref_mode = True
        ref_start_time = time.time()
        ref_buffer = []
        status_text.set_text("Keine Live-Daten. Referenzmessung läuft...")
    elif event.key == 'm':
        print("Messpunkt aufnehmen durch Benutzer.")
        is_recording = True
        rec_start_time = time.time()
        rec_buffer = []
        status_text.set_text("Keine Live-Daten. Messung läuft...")
    elif event.key == 's':
        print("Messdaten speichern durch Benutzer.")
        save_to_csv(FILENAME)

fig.canvas.mpl_connect('key_press_event', on_key)

# ========================== #
# ==== HAUPTSCHLEIFE ==== #
# ========================== #
update_yaxis_label()
time_axis = np.linspace(0, DISPLAY_WINDOW)
line.set_xdata(0, DISPLAY_WINDOW)
try:
    while plt.fignum_exists(fig.number):
        data = task.read(number_of_samples_per_channel=int(SAMPLE_RATE*DISPLAY_WINDOW))
        data = np.array(data)
        
        # Referenzmessung
        if is_ref_mode:
            ref_buffer.extend(data)
            elapsed = time.time() - ref_start_time
            status_text.set_text(f"Referenzmessung läuft... {(SAVE_DURATION - elapsed):.0f} s.")
            if elapsed >= SAVE_DURATION:
                V0 = np.mean(ref_buffer)
                print(f"Referenzwert gesetzt: V0 = {V0:.6f} V")
                is_ref_mode = False
                status_text.set_text("")
                update_yaxis_label()
            plt.pause(0.01)
            continue
        
        # Aufnahmemodus
        if is_recording:
            if V0 is None:
                raise ValueError("V0 ist noch nicht gesetzt. Erst Referenzmessung durchführen.")
            data_db = 20 * np.log10(np.maximum(np.abs(np.array(data))/V0, 1e-12))
            rec_buffer.extend(data_db)
            elapsed = time.time() - rec_start_time
            status_text.set_text(f"Messung läuft... {(SAVE_DURATION - elapsed):.0f} s")
            if elapsed >= SAVE_DURATION:
                cleaned_data = remove_outliers(rec_buffer)
                mean_list.append(np.mean(cleaned_data))
                std_list.append(np.std(cleaned_data))
                mean_text.set_text(f"Mean: {np.mean(cleaned_data):.4f} V")
                std_text.set_text(f"Std: {np.std(cleaned_data):.4f} V")
                print("Messpunkte gespeichert")
                is_recording = False
                status_text.set_text("")
            plt.pause(0.01)
            continue
        
        if V0 is None:
            line.set_ydata(data)
            ax.set_ylim(min(data)-0.1, max(data)+0.1)
            time_axis = np.linspace(0, DISPLAY_WINDOW, len(data))
            mean_text.set_text(f"Mean: {np.mean(data):.4f} V")
            std_text.set_text(f"Std: {np.std(data):.4f} V")
        else:
            data_db = 20 * np.log10(np.maximum(np.abs(np.array(data))/V0, 1e-12))
            line.set_ydata(data_db)
            ax.set_ylim(min(data_db)-1, max(data_db)+1)
            time_axis = np.linspace(0, DISPLAY_WINDOW, len(data_db))
            mean_text.set_text(f"Mean: {np.mean(data_db):.4f} V")
            std_text.set_text(f"Std: {np.std(data_db):.4f} V")
        line.set_xdata(time_axis)
        ax.set_xlim(0, DISPLAY_WINDOW)
        fig.canvas.draw_idle()
        
        plt.pause(0.01)

except KeyboardInterrupt:
    print("Messung manuell abgebrochen.")

finally:
    task.close()
    plt.ioff()
    plt.close(fig)
    print("Task beendet, Fenster geschlossen.")