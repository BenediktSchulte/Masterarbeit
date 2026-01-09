"""
Datei 4:
Live-Plot der Rohdaten + Berechnung von mean und std nach Outlier-Removal.
Plot zeigt nur die RAW-Daten.
mean/std beziehen sich auf CLEANED-Daten.

Taste 'q' = Beenden
"""

import numpy as np
import matplotlib.pyplot as plt
import time
import random

# ----------------------------- #
# Outlier-Removal (MAD Methode)
# ----------------------------- #
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

# ----------------------------- #
# Fake-Datenquelle
# (In deinem System später ersetzen durch DAQ)
# ----------------------------- #
def read_data_block(N=500):
    """Simuliert DAQ-Daten mit Ausreißern."""
    base = np.sin(np.linspace(0, 4*np.pi, N)) * 0.5
    noise = np.random.normal(0, 0.05, N)
    raw = base + noise

    if random.random() < 0.5:    # 5% Ausreißer
        idx = random.randint(0, N-1)
        raw[idx] += random.choice([2.0, -2.0])

    return raw

# ----------------------------- #
# Plot vorbereiten
# ----------------------------- #
plt.ion()
fig, ax = plt.subplots()
ax.set_title("Live Data (raw) with cleaned Statistics")
ax.set_xlabel("Sample Index")
ax.set_ylabel("Amplitude")
line, = ax.plot([], [], lw=1)

text_mean = ax.text(0.02, 0.95, "", transform=ax.transAxes)
text_std  = ax.text(0.02, 0.88, "", transform=ax.transAxes)

# ----------------------------- #
# Hauptloop
# ----------------------------- #
try:
    all_data = []

    while plt.fignum_exists(fig.number):

        raw = read_data_block()
        all_data.extend(raw)
        
        # --- CLEAN statistische Daten ---
        clean = remove_outliers(raw)
        m = np.mean(clean)
        s = np.std(clean)

        # --- Plot RAW ---
        line.set_xdata(np.arange(len(clean)))
        line.set_ydata(clean)
        ax.set_xlim(0, len(clean))
        ax.set_ylim(min(clean) - 0.5, max(clean) + 0.5)

        # --- Text aktualisieren ---
        text_mean.set_text(f"mean (clean): {m:.4f}")
        text_std.set_text(f"std (clean):  {s:.4f}")

        fig.canvas.draw_idle()
        plt.pause(0.05)

except KeyboardInterrupt:
    print("Beendet.")

finally:
    plt.ioff()
    plt.close(fig)