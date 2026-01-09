import serial
import time
import numpy as np
print("start")
ser = serial.Serial("/dev/cu.usbmodem141101", 115200, timeout=1)
time.sleep(1)

def send(cmd):
    ser.write((cmd + "\r").encode())
    time.sleep(0.1)
    response = ser.read_all().decode().strip()
    return response

send("calibrate")
time.sleep(70)
print("calibrierung abgeshclossen")
send("Move -360 15")
time.sleep(7)
send("testcal")
time.sleep(70)
print("Ende Test")
send("Move -360 15")


#for i in range(-5, 6, 1):
#    x = send(f"move {i} 15")
#    print(f"Winkel {i}°")
#    print(x)
#    time.sleep(5)
    

ser.close()