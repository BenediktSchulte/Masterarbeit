import nidaqmx
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import TextBox
import pandas as pd
from datetime import datetime
import time
from pathlib import Path
import serial

# =================================== #
# ============ Variablen ============ #
# =================================== #
SAVE_DURATION = 10  # Sekunden Aufnahme für Referenz oder Messung

# Zum Referenzwert messen
V0 = None
is_ref_mode = False
ref_buffer = []
ref_start_time = None

# Zum Aufnehmen der Messpunkte
is_recording = False
rec_buffer_db = []
rec_buffer = []
rec_start_time = None
results = {"angle": [], "mean_db": [], "std_db": [], "mean_raw": [], "std_raw": []}

# Zum Finden der maximalen Spannung
max_finder = False
max_buffer = {}
best_angle = None   # Winkel mit der höchsten Spannung
max_angle_start = -40 
max_angle_stop = 40
angle_step = 10
DURATION_FIND_MAXIMUM = 5

# Für den Motor
ser = serial.Serial("COM12", 115200, timeout=1) # Kommunikation
ang = 0 # Aktueller Winkel
measure_start = -60             # Startwinkel für die Messung
measure_stop = 60               # Stoppwinkel für die Messung
step = 0.5

#Für die Kalibrierung
do_calibration = False

# =================================== #
# ======== DAQ-Konfiguration ======== #
# =================================== #
CHANNEL = "Dev1/ai0"    # Dein Messkanal
SAMPLE_RATE = 2000      # Hz, Sample Rate
BLOCK_SIZE = 500        # Anzahl Samples pro Lesevorgang

# =================================== #
# ======= DAQ-Task erstellen ======== #
# =================================== #
task = nidaqmx.Task()
task.ai_channels.add_ai_voltage_chan(CHANNEL)
task.timing.cfg_samp_clk_timing(rate=SAMPLE_RATE)

# =================================== #
# == Outlier-Removal (MAD Methode) == #
# =================================== #
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

# =================================== #
# =========== FUNKTIONEN ============ #
# =================================== #
def send(cmd):
    global ang
    ser.write((cmd + "\r").encode())
    time.sleep(0.1)
    while ser.in_waiting == 0:
        time.sleep(0.1)
    response = ser.read_all().decode().strip()
    if cmd.lower().startswith("move"):
        ang = float(cmd.split()[1])
        text_angle.set_text(f"Winkel: {ang}°")
    return response

def submit_move(text):
    try:
        angle = float(text)
        send(f"move {angle} 5")
        print(f"Motor fährt zu {angle}°")
        time.sleep(5)
        move_box.set_val("")
    except ValueError:
        print("Ungültiger Winkel.")

def save(results=results):
    global measure_start, measure_stop, step, V0
    if len(results["mean_db"]) == 0:
        print("Keine Messdaten zum Speichern.")
        return
    df = pd.DataFrame(results)
    today = datetime.now().strftime("%Y-%m-%d")
    time_stamp = datetime.now().strftime("%Y-%m-%d-T%H-%M-%S")
    Path(today).mkdir(exist_ok=True)
    df.to_csv(f"{today}/data_{time_stamp}_{measure_start}_{measure_stop}_{step}_{V0:.3f}.csv", index=False)
    print("Daten gespeichert in data_{time_stamp}_{measure_start}_{measure_stop}_{step}_{V0}.csv")

# =================================== #
# ======== Plot vorbereiten ========= #
# =================================== #
plt.ion()
fig, ax = plt.subplots()
plt.subplots_adjust(bottom=0.2)

ax.set_title("Live Data (raw) with cleaned Statistics")
ax.set_xlabel("Sample Index")
ax.set_ylabel("Voltage (V)")
line, = ax.plot([], [], lw=1)
text_mean = ax.text(0.7, 0.95, "", transform=ax.transAxes, color='red', fontsize=12, fontweight='bold')
text_std  = ax.text(0.7, 0.9,  "", transform=ax.transAxes, color='red', fontsize=12, fontweight='bold')
text_timer = ax.text(0.02, 0.82, "", transform=ax.transAxes, color='blue', fontsize=12, fontweight='bold')
text_angle = ax.text(0.7, 1.07, "", transform=ax.transAxes, color='green', fontsize=12, fontweight='bold')

axbox = plt.axes([0.25, 0.05, 0.5, 0.07])
move_box = TextBox(axbox, "Fahre zu Winkel (°): ", initial = "")
move_box.on_submit(submit_move)

# =================================== #
# ======= Tastatur-Ereignisse ======= #
# =================================== #
def on_key(event):
    global is_ref_mode, ref_buffer, ref_start_time
    global is_recording, rec_buffer, rec_start_time, V0
    global results
    global max_buffer, do_calibration
    global max_angle_start, max_angle_stop, angle_step, max_finder

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
        if best_angle == None:
               print("Bester Wert wurde noch nicht gesucht. Führe w aus.")
               return 
        print("Messung gestartet...")
        is_recording = True
        
    elif event.key =="w":
        print("Finde Maximum")
        max_angle_start = -40 
        max_angle_stop = 40
        angle_step = 10
        max_finder = True
        
    elif event.key == "k":
        print("Starte Kalibrierung des Motors")
        do_calibration = True
        
    elif event.key == 's':
        save()

fig.canvas.mpl_connect('key_press_event', on_key)

# =================================== #
# =========== Hauptloop ============= #
# =================================== #
try:
    print(f"""Drücke:
    p zur Messung von V0
    m für eine Messung
    s zum speichern
    w zum finden eines Maximums
    k zur Kalibrierung
    q zum schließen \n""")
    while plt.fignum_exists(fig.number): # Solange das Fenster existiert
        
        # Messpunkt aufnahme -> m drücken
        if is_recording:
            send(f"move {measure_start} 15")
            time.sleep(3)
            angles = np.round(np.arange(measure_start + best_angle, measure_stop + step + best_angle, step), 3)
            for angle in angles:
                send(f"move {angle} 5")
                print(f"Winkel: {angle}° eingestellt. Bedeutung: {angle - best_angle}°")
                time.sleep(2)
                
                rec_buffer_db = []
                rec_buffer = []
                rec_start_time = time.time()
                
                while True: 
                    # Sammle Daten
                    data = task.read(number_of_samples_per_channel=BLOCK_SIZE)
                    data = np.array(data)
                    # Säubere Daten und berechne dB-Skala
                    clean = remove_outliers(data)
                    data_db = 10*np.log10(np.maximum(np.abs(clean)/V0, 1e-12))
                    
                    # Wenn keine sauberen Daten, weiter
                    if len(clean) == 0:
                        plt.pause(0.05)
                        continue
                    
                    # Zeige Mean/Std an
                    text_mean.set_text(f"mean(dB): {np.mean(data_db):.3f}")
                    text_std.set_text(f"std(dB):  {np.std(data_db):.3f}")
                    
                    # Speichere Daten im Puffer
                    rec_buffer_db.extend(data_db)
                    rec_buffer.extend(clean)
                    
                    # Update Timer
                    elapsed = time.time() - rec_start_time
                    remaining = max(0, SAVE_DURATION - elapsed)
                    text_timer.set_text(f"Messung läuft. Dieser Messpunkt noch: {remaining:.0f}s")
                    if elapsed >= SAVE_DURATION:
                        break
                    plt.pause(0.01)
                results["angle"].append(angle-best_angle)
                results["mean_db"].append(np.mean(rec_buffer_db))
                results["std_db"].append(np.std(rec_buffer_db))
                results["mean_raw"].append(np.mean(rec_buffer))
                results["std_raw"].append(np.std(rec_buffer))
                text_timer.set_text("")
                print(f"Messung gespeichert für: Winkel = {angle-best_angle}°, mean={results['mean_db'][-1]:.3f} dB, std={results['std_db'][-1]:.3f} dB")
                #print(f"Werte gespeichert für {angle}°")
            send(f"Move {best_angle} 5")
            save(results=results)
            time.sleep(5)
            is_recording = False
        
        # new maximum finder -> w drücken
        elif max_finder:
            print("Starte Maximums Suche")
            while angle_step >= 0.5: 
                max_buffer = {}
                angles = np.round(np.arange(max_angle_start, max_angle_stop + angle_step, angle_step), 3)
                for angle in angles:
                    send(f"move {angle} 5")
                    print(f"Winkel: {angle}°")
                    time.sleep(2)
                    
                    rec_start_time = time.time()
                    buffer = []
                    while True: 
                        data = task.read(number_of_samples_per_channel=BLOCK_SIZE)
                        data = np.array(data)
                        clean = remove_outliers(data)
                        if len(clean) == 0:
                            continue
                        mean_val = np.mean(clean)
                        buffer.append(mean_val)
                        
                        elapsed = time.time() - rec_start_time
                        if elapsed >= DURATION_FIND_MAXIMUM:
                            break
                    max_buffer[angle] = np.mean(buffer)
                    print(f"Spannung: {np.mean(buffer)}") 
                    time.sleep(0.2)
                best_angle = max(max_buffer, key=max_buffer.get)
                max_angle_start = best_angle - angle_step
                max_angle_stop = best_angle + angle_step
                angle_step = angle_step / 2
                
            best_angle = max(max_buffer, key=max_buffer.get)
            print(f"Höchste Spannung: {best_angle}° mit {max_buffer[best_angle]:.4f}V")
            send(f"Move {best_angle} 15")
            time.sleep(2)
            max_finder = False
            
        # Kalibrierung des Motors -> k drücken
        elif do_calibration:
            send("Move -360 15")
            time.sleep(5)
            print("Starte Calibrierung")
            time.sleep(70)
            print("Ende der Calibrierung")
            send("Move -370 15")
            time.sleep(5)
            send("testcal")
            time.sleep(70)
            print("Ende Test")
            do_calibration = False
            
        else: # Wenn keine Aufnahme stattfindet, kein Maximum gesucht wird und keine Kalibrierung läuft
            # Daten aufnehmen und verarbeiten
            data = task.read(number_of_samples_per_channel=BLOCK_SIZE)
            data = np.array(data)
            clean = remove_outliers(data)
            if len(clean) == 0:
                plt.pause(0.05)
                continue
            mean_val = np.mean(clean)
            std_val  = np.std(clean)

            # Referentwert der Spannung bestimmen -> p drücken
            if is_ref_mode:
                time.sleep(0.5)
                ref_buffer.extend(clean)
                
                elapsed = time.time() - ref_start_time
                remaining = max(0, SAVE_DURATION - elapsed)
                text_timer.set_text(f"Referenzmessung: {remaining:.0f}s")
                if elapsed >= SAVE_DURATION:
                    V0 = np.mean(ref_buffer)
                    print(f"Referenz gesetzt: V0 = {V0:.4f} V")
                    ax.set_ylabel("Voltage (dB)")  # nach Referenz in dB
                    text_timer.set_text("")
                    is_ref_mode = False
                    
            # --- Plot ---
            display_data = clean if V0 is None else 20*np.log10(np.maximum(np.abs(clean)/V0, 1e-12))
            line.set_xdata(np.arange(len(display_data)))
            line.set_ydata(display_data)
            ax.set_xlim(0, BLOCK_SIZE)
            ax.set_ylim(min(display_data)-0.5, max(display_data)+0.5)

            # --- Mean/Std Text ---
            text_mean.set_text(f"mean: {mean_val:.4f}" if V0 is None else f"mean(dB): {np.mean(display_data):.3f}")
            text_std.set_text(f"std:  {std_val:.4f}" if V0 is None else f"std(dB):  {np.std(display_data):.3f}")
            text_angle.set_text(f"Winkel: {ang}°")
            
            fig.canvas.draw_idle()
            plt.pause(0.05)
            
        # --------------
      
except KeyboardInterrupt:
    print("Messung manuell abgebrochen.")

finally:
    task.close()
    plt.ioff()
    plt.close(fig)
    ser.close()


# To-Do
# [?] Kalibrierung verschiebt die x-Achse
# [X] Winkel immer im Plot Updaten
# [ ] Zeit beim Kalibrieren einfügen
#     - geht nicht, da time.sleep() alles pausiert.
# [X] Startposition angucken
# [ ] Motor einstellen Manuelles Feld einfügen.