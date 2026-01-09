# ==================== #
# === LOAD PACKAGE === #
# ==================== #
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import os

# ==================== #
# ==== PARAMETERS ==== #
# ==================== #
#PATH_WAY = "data/2025_11_13_Charakterisation.csv" # 13.11.2025 ohne Absorber
#PATH_WAY = "data/2025_11_19_Characterisation.csv" # 19.11.2025 in 31cm Höhe
#PATH_WAY = "data/data_2025_11_21_0_58Degree.csv" # 21.11.2025 in 31cm Höhe von 0 bis 58°
#PATH_WAY = "data/data_2025_11_26_0_50Degree.csv" # 26.11.2025 in 31cm Höhe von 0 bis 50°
#PATH_WAY  = "data/2025-12-18/data_2025-12-18-T13-52-07_-60_60_1_0.19750423164338896.csv" # 18.12.2025
#PATH_WAY  = "data/2025-12-19/data_2025-12-19-T09-22-08_-60_60_0.5_0.20004047407946116.csv" # 19.12.2025
#PATH_WAY  = "data/2025-12-19/data_2025-12-19-T10-56-17_-60_60_0.5_0.196.csv" # 19.12.2025
#PATH_WAY  = "data/2025-12-19/data_2025-12-19-T12-15-31_-60_60_0.5_0.009.csv" # 19.12.2025
#PATH_WAY  = "data/2025-12-19/data_2025-12-19-T13-14-16_-60_60_0.5_0.339.csv" # 19.12.2025
PATH_WAY  = "data/2025-12-19/data_2025-12-19-T14-14-12_-60_60_0.5_0.276.csv" # 19.12.2025

# ==================== #
# ==== Load Data ===== #
# ==================== #
#print("start")
df = pd.read_csv(PATH_WAY, sep=",")
#print(df.info)

# ==================== #
# ==== FUNCTIONS ===== #
# ==================== #
def plot_data(df):
    """ Plotte einen Datensatz mit dem Index 'angle' und den Spalten 'mean' und 'std' als db Voltage Level."""
    required_cols = {"mean_db", "std_db"} # "angle"
    if not required_cols.issubset(df.columns):
        raise ValueError(f"CSV muss die Spalten {required_cols} enthalten")
    #df = df.sort_values(by="angle")
    
    plt.figure(figsize=(10, 6))
    plt.errorbar(df["angle"],df["mean_db"], yerr=df["std_db"], fmt="o-", capsize=4, label="Datapoints with errorbars")
    plt.title("Characterisation of the horn antennas")
    plt.xlabel("Angle (°)")
    plt.ylabel("Voltage Level (db)")
    plt.legend()
    plt.grid()
    plt.tight_layout()
    plt.savefig("Plots/2025_12_19/2025_12_19_Characterisation_Alu_Lensholder.pdf", format="pdf", bbox_inches="tight")
    plt.show()
    
if __name__ == "__main__":
    plot_data(df)
    print("Done")
    