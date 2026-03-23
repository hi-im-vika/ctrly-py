import serial, re
import threading
from serial.tools import list_ports

def find_port():
    ports = list_ports.grep(r'^\/dev\/ttyACM[1-9]+')    # ignore ttyACM0
    try:
        port = next(ports)
        return port
    except StopIteration:
        raise Exception("No ports found")

def serial_thread():
    port = ''
    while True:
        while not port:
            try:
                port = find_port()
            except:
                print("No port found. Retrying in 1s")
                time.sleep(1)
        try:
            print(port.device)
            with serial.Serial(port.device, baudrate=115200) as ser:
                while True:
                    # put TX/RX stuff here
                    print(f"Serial port found ({port.device})")
                    ser.write(b'hello')
                    time.sleep(1)
        except Exception as e:
            print(e)
            print("Serial port error. Disconnecting and retrying")
            ser.close()
            port = ''
            time.sleep(1)     

def main():
    print("Hello from ctrly-py!")
    
    thr_serial = threading.Thread(target=serial_thread, daemon=True)
    thr_serial.start()

    try:
        while True:
            print("Hi from main thread")
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting")

if __name__ == "__main__":
    main()
