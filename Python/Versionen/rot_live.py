# =================================== #
# ============= Packete ============= #
# =================================== #
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
MOTOR_SETTLE_TIME = 7.0
motor_busy = False
motor_read_time = 0.0

# Zum Referenzwert messen
V0 = None # 
ref_buffer = []

# Zum Aufnehmen der Messpunkte
rec_buffer_db = []
rec_buffer = []
results = {"angle": [], "mean_db": [], "std_db": [], "mean_raw": [], "std_raw": []}
SAVE_DURATION = 10  # Sekunden Aufnahme für Referenz oder Messung # 
timer_start = None

# Zum Finden der maximalen Spannung
max_buffer = {}
current_angles = []
angle_index = 0
best_angle = None   # Winkel mit der höchsten Spannung
max_angle_start = -40 
max_angle_stop = 40
angle_step = 10
DURATION_FIND_MAXIMUM = 5 # 

# Für den Motor
ser = serial.Serial("COM12", 115200, timeout=1) # Kommunikation
ang = 0 # Aktueller Winkel  
measure_start = -60             # Startwinkel für die Messung
measure_stop = 60               # Stoppwinkel für die Messung
step = 0.5

#Für die Kalibrierung
do_calibration = False

# ZUSTÄNDE 
STATE_IDLE = "IDLE"
STATE_REF = "REF"
STATE_MEASURE = "MEASURE"
STATE_MEASURE_WAIT = "MEASURE_WAIT"
STATE_FIND_MAX = "FIND_MAX"
STATE_FIND_MAX_WAIT = "FIND_MAX_WAIT"

STATE_CALIBRATE_START = "CALIBRATE_START"
STATE_CALIBRATE_CAL= "CALIBRATE_CAL"
STATE_CALIBRATE_MOVE2 = "CALIBRATE_MOVE2"
STATE_CALIBRATE_TEST= "CALIBRATE_TEST"
STATE_CALIBRATE_DONE = "CALIBRATE_DONE"
CALIBRATE_WAIT = 70 # Sekunden

state = STATE_IDLE

# DAQ-Konfiguration
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
# =========== FUNKTIONEN ============ #
# =================================== #
def remove_outliers(data):
    data = np.asarray(data)
    if len(data) < 10:
        return data

    # global
    med = np.median(data)
    mad = np.median(np.abs(data - med))
    if mad == 0:
        return data

    z = 0.6745 * (data - med) / mad
    data = data[np.abs(z) < 4]

    return data

def send(cmd):
    global ang
    ser.write((cmd + "\r").encode())
    response = ser.read_all().decode(errors="ignore").strip()
    if cmd.lower().startswith("move"):
        ang = float(cmd.split()[1])
        text_angle.set_text(f"Winkel: {ang}°")
    return response

def move_motor(angle, speed=5):
    global motor_busy, motor_read_time
    send(f"Move {angle} {speed}")
    motor_busy = True
    motor_read_time = time.time() + MOTOR_SETTLE_TIME
    
def motor_ready():
    global motor_busy, motor_read_time
    if not motor_busy:
        return True
    if time.time() >= motor_read_time:
        motor_busy = False
        return True
    return False

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
    print(f"Daten gespeichert in data_{time_stamp}_{measure_start}_{measure_stop}_{step}_{V0}.csv")
    
# =================================== #
# ======== Plot vorbereiten ========= #
# =================================== #
plt.ion()
fig, ax = plt.subplots()
plt.subplots_adjust(bottom=0.22)

ax.set_title("Live Data")
ax.set_xlabel("Sample")
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
    global state, timer_start, ref_buffer, current_angles, angle_index
    global max_buffer, angle_step, max_angle_start, max_angle_stop

    if event.key == 'q':
        print("Beenden...")
        plt.close(fig)

    elif event.key == 'p':
        print("Referenzmessung gestartet (V0 bestimmen)...")
        ref_buffer = []
        timer_start = time.time()
        ax.set_ylabel("Voltage (V)")  # Y-Achse vor Referenzmessung
        state = STATE_REF

    elif event.key == 'm':
        if V0 is None or best_angle is None:
            print("V0 oder best_angle noch nicht gesetzt! Erst p oder w drücken.")
            return
        results = {k: [] for k in results}
        print("Messung gestartet...")
        current_angles = np.round(
            np.arange(measure_start, measure_stop + step, step) + best_angle, 3)
        angle_index = 0
        state = STATE_MEASURE
        
    elif event.key =="w":
        print("Finde Maximum")
        max_angle_start = -40 
        max_angle_stop = 40
        angle_step = 10
        state = STATE_FIND_MAX
        
    elif event.key == "k":
        print("Starte Kalibrierung des Motors")
        state = STATE_CALIBRATE_START
        
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
        
        # Auf den Motor warten
        if not motor_ready():
            plt.pause(0.1)
            continue
        
        # Live Daten
        data = np.array(task.read(number_of_samples_per_channel=BLOCK_SIZE))
        clean = remove_outliers(data)
        
        if len(clean):
            display_data = clean if V0 is None else 10*np.log10(np.maximum(np.abs(clean)/V0, 1e-12))
            line.set_xdata(np.arange(len(display_data)))
            line.set_ydata(display_data)
            ax.set_xlim(0, BLOCK_SIZE)
            ax.set_ylim(min(display_data)-0.5, max(display_data)+0.5)
            
            # --- Mean/Std Text ---
            text_mean.set_text(f"mean: {np.mean(display_data):.4f}")
            text_std.set_text(f"std:  {np.std(display_data):.4f}")
            text_angle.set_text(f"Winkel: {ang:.2f}°")
            
        # STATES:  
        if state == STATE_CALIBRATE_START:
            move_motor(-360, speed=15)
            timer_start = time.time()
            state = STATE_CALIBRATE_CAL
        elif state == STATE_CALIBRATE_CAL:
            if motor_ready():
                print("Starte Kalibrierung... ")
                send("calibrate")
                motor_busy = True
                motor_read_time = time.time() + CALIBRATE_WAIT
                state = STATE_CALIBRATE_MOVE2
        elif state == STATE_CALIBRATE_MOVE2:
            if motor_ready():
                move_motor(-360, speed=15)
                timer_start = time.time()
                state = STATE_CALIBRATE_TEST
        elif state == STATE_CALIBRATE_TEST:
            if motor_ready():
                print("Kalibrierung Testen ...")
                send("testcal")
                motor_busy = True
                motor_read_time = time.time() + CALIBRATE_WAIT
                state = STATE_CALIBRATE_DONE
        elif state == STATE_CALIBRATE_DONE:
            if motor_ready():
                print("Testen der Kalibrierung abgeschlossen.")
                state = STATE_IDLE
          
        if state == STATE_REF:
            ref_buffer.extend(clean)
            if time.time() - timer_start >= SAVE_DURATION:
                V0 = np.mean(ref_buffer)
                print(f"V0 = {V0:.4f} V")
                state = STATE_IDLE
                
        elif state == STATE_FIND_MAX:
            if not max_buffer:
                current_angles = np.arange(max_angle_start, max_angle_stop + angle_step, angle_step)
                angle_index = 0
                
            if angle_index < len(current_angles):
                move_motor(current_angles[angle_index])
                rec_buffer = []
                timer_start = time.time()
                state = STATE_FIND_MAX_WAIT
            
            else:
                best_angle = max(max_buffer, key=max_buffer.get)
                max_angle_start = best_angle - angle_step
                max_angle_stop = best_angle + angle_step
                angle_step /= 2 
                max_buffer = {}
                if angle_step < 0.5:
                    print(f"Bester Winkel: {best_angle}° mit Spannung {max_buffer[best_angle]:.4f}V")
                    state = STATE_IDLE
                    
        elif state == STATE_FIND_MAX_WAIT:
            rec_buffer.extend(clean)
            if time.time() - timer_start >= DURATION_FIND_MAXIMUM:
                max_buffer[current_angles[angle_index]] = np.mean(rec_buffer)
                angle_index +=1
                state = STATE_FIND_MAX
    
        elif state == STATE_MEASURE:
            if angle_index < len(current_angles):
                move_motor(current_angles[angle_index])
                timer_start = time.time()
                rec_buffer = []
                rec_buffer_db = []
                state = STATE_MEASURE_WAIT
            else:
                print("Messung abgeschlossen")
                save(results)
                move_motor(best_angle)
                state = STATE_IDLE
                
        elif state == STATE_MEASURE_WAIT:
            rec_buffer.extend(clean)
            rec_buffer_db.extend(10*np.log10(np.maximum(np.abs(clean)/V0, 1e-12)))
            if time.time() - timer_start >= SAVE_DURATION:
                angle = current_angles[angle_index]
                results["angle"].append(angle-best_angle)
                results["mean_db"].append(np.mean(rec_buffer_db))
                results["std_db"].append(np.std(rec_buffer_db))
                results["mean_raw"].append(np.mean(rec_buffer))
                results["std_raw"].append(np.std(rec_buffer))
                angle_index += 1
                state = STATE_MEASURE
        
        fig.canvas.draw_idle()
        plt.pause(0.01)
except KeyboardInterrupt:
    print("Messung manuell abgebrochen.")

finally:
    task.close()
    plt.ioff()
    plt.close(fig)
    ser.close()
    