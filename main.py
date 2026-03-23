import evdev
import threading
import time
import serial
import re
import struct
from serial.tools import list_ports
from cobs import cobs
from dataclasses import dataclass
import dearpygui.dearpygui as dpg

# evdev axis codes
AX_LX = evdev.ecodes.ABS_X
AX_LY = evdev.ecodes.ABS_Y
AX_RX = evdev.ecodes.ABS_RX
AX_RY = evdev.ecodes.ABS_RY

# Button bit positions
BTN_MAP = {
    evdev.ecodes.BTN_SOUTH:  0,   # A
    evdev.ecodes.BTN_EAST:   1,   # B
    evdev.ecodes.BTN_NORTH:  2,   # Y
    evdev.ecodes.BTN_WEST:   3,   # X
    evdev.ecodes.BTN_TL:     4,   # L1
    evdev.ecodes.BTN_TR:     5,   # R1
    evdev.ecodes.BTN_SELECT: 6,   # Select
    evdev.ecodes.BTN_START:  7,   # Start
    evdev.ecodes.BTN_THUMBL: 8,   # L3
    evdev.ecodes.BTN_THUMBR: 9,   # R3
}

@dataclass
class GamepadState:
    lx: int = 0
    ly: int = 0
    rx: int = 0
    ry: int = 0
    buttons: int = 0

gp_state = GamepadState(0,0,0,0,0)

def find_gamepad():
    stick_ecodes = {AX_LX, AX_LY, AX_RX, AX_RY}
    name_kws = {'microsoft', 'wireless'}
    for path in evdev.list_devices():
        device = evdev.InputDevice(path)
        d_name = device.name
        d_caps = device.capabilities()
        has_key = evdev.ecodes.EV_KEY in d_caps
        has_sticks = any(x in d_caps for x in stick_ecodes)
        match_name = any(x in d_name.lower() for x in name_kws)
        if has_key and has_sticks and match_name:
            return device
    raise Exception("No gamepads found")

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

def input_thread(dev):
    for evt in dev.read_loop():
        if evt.type == evdev.ecodes.EV_ABS:
            if evt.code == AX_LX:
                gp_state.lx = evt.value
            elif evt.code == AX_LY:
                gp_state.ly = evt.value
            elif evt.code == AX_RX:
                gp_state.rx = evt.value
            elif evt.code == AX_RY:
                gp_state.ry = evt.value
        elif evt.type == evdev.ecodes.EV_KEY:
            bit = BTN_MAP.get(evt.code)
            if bit is not None:
                if evt.value:
                    gp_state.buttons |= (1 << bit)
                else:
                    gp_state.buttons &= ~(1 << bit)

def main():
    print("Hello from ctrly-py!")

    try:
        device = find_gamepad()
    except:
        print("No gamepad found")
        exit()

    print(device)

    dpg.create_context()
    dpg.create_viewport(title='Custom Title')

    thr_input = threading.Thread(target=input_thread, args=(device,), daemon=True)
    thr_input.start()

    thr_serial = threading.Thread(target=serial_thread, daemon=True)
    thr_serial.start()

    with dpg.window(label="The Window",tag="Primary Window"):
        axis_text = dpg.add_text()
        throttle_slider = dpg.add_slider_int(label="Throttle", vertical=True, max_value=65535, height=160)
        steering_slider = dpg.add_slider_int(label="Steering", vertical=True, max_value=65535, height=160)
        with dpg.table(header_row=False):

            # use add_table_column to add columns to the table,
            # table columns use slot 0
            dpg.add_table_column()
            dpg.add_table_column()

            with dpg.table_row():
                dpg.add_text(f"Refresh rate")
                dpg.add_text(f"9000 hz")
            with dpg.table_row():
                dpg.add_text(f"Response time")
                dpg.add_text(f"0.1 ms")

    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("Primary Window", True)
    while dpg.is_dearpygui_running():
        dpg.set_value(axis_text, f"{gp_state.ly:10} {gp_state.rx:10}")
        dpg.set_value(throttle_slider, gp_state.ly + 32767)
        dpg.set_value(steering_slider, gp_state.rx + 32767)
        dpg.render_dearpygui_frame()
    dpg.destroy_context()

if __name__ == "__main__":
    main()