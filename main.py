import serial, re
from serial.tools import list_ports

def find_port():
    ports = list_ports.grep(r'^\/dev\/ttyACM[1-9]+')    # ignore ttyACM0
    try:
        port = next(ports)
        return port
    except StopIteration:
        raise Exception("No ports found")   

def main():
    print("Hello from ctrly-py!")
    
    port = find_port()
    print(port.device)

if __name__ == "__main__":
    main()
