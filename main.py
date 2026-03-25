import evdev
from threading import Thread, Lock
import time
import serial
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
    lx_filt: int = 0
    ly_filt: int = 0
    rx_filt: int = 0
    ry_filt: int = 0
    buttons: int = 0
    inv_ls: bool = True
    inv_rs: bool = True
    l_dz: int = 5000
    r_dz: int = 5000
    ax_max: int = 0
    ax_min: int = 0
    use_l_dz: bool = True
    use_r_dz: bool = False

@dataclass
class CtrlyState:
    port: str = ''
    connected: bool = False

@dataclass
class Telemetry:
    tx_count: int = 0
    rx_count: int = 0
    fail_count: int = 0
    sd_rx_fail: int = 0

gp_state = GamepadState(0,0,0,0,0)
ctrly_state = CtrlyState()
telemetry = Telemetry()

input_mutex = Lock()
tm_mutex = Lock()

# Source - https://stackoverflow.com/a/34837691
# Posted by Delgan, modified by community. See post 'Timeline' for change history
# Retrieved 2026-03-25, License - CC BY-SA 3.0

def constrain(val, min_val, max_val):
    return min(max_val, max(min_val, val))

# Source - https://stackoverflow.com/a/70659904
# Posted by CrazyChucky, modified by community. See post 'Timeline' for change history
# Retrieved 2026-03-25, License - CC BY-SA 4.0

def map_range(x, in_min, in_max, out_min, out_max):
  return (x - in_min) * (out_max - out_min) // (in_max - in_min) + out_min

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

def serial_thread(t):
    while True:
        while not ctrly_state.port:
            try:
                ctrly_state.port = find_port()
            except:
                print("No port found. Retrying in 1s")
                time.sleep(1)
        try:
            print(ctrly_state.port.device)
            with serial.Serial(ctrly_state.port.device, baudrate=115200) as ser:
                if not t.is_alive():
                    t.start()
                ctrly_state.connected = True
                while True:
                    with(input_mutex):
                        # put TX/RX stuff here
                        # do deadzone calcs
                        if gp_state.use_l_dz:
                            gp_state.lx_filt = gp_state.lx if abs(gp_state.lx) > gp_state.l_dz else 0
                            gp_state.ly_filt = gp_state.ly if abs(gp_state.ly) > gp_state.l_dz else 0
                        else:
                            gp_state.lx_filt = gp_state.lx
                            gp_state.ly_filt = gp_state.ly
                        if gp_state.use_r_dz:
                            gp_state.rx_filt = gp_state.rx if abs(gp_state.rx) > gp_state.r_dz else 0
                            gp_state.ry_filt = gp_state.ry if abs(gp_state.ry) > gp_state.r_dz else 0
                        else:
                            gp_state.rx_filt = gp_state.rx
                            gp_state.ry_filt = gp_state.ry
                        frame = struct.pack("<4hH", gp_state.lx_filt, gp_state.ly_filt, gp_state.rx_filt, gp_state.ry_filt, gp_state.buttons)
                        # print(f"{gp_state.lx} {gp_state.ly} {gp_state.rx} {gp_state.ry}")
                        encoded = cobs.encode(frame) + b'\x00'
                        ser.write(encoded)
                        # print(f"{len(encoded)} bytes written: {frame.hex()} to {encoded.hex()}")
                    time.sleep(0.001)
        except Exception as e:
            print(e)
            ctrly_state.connected = False
            ctrly_state.port = ''

def serial_rx_thread():
    while True:
        while ctrly_state.connected:
            try:
                with serial.Serial(ctrly_state.port.device, baudrate=115200) as ser:
                    encoded = ser.read_until(b'\x00')[:-1]
                    with tm_mutex:
                        try:
                            decoded = cobs.decode(encoded)
                            frame = struct.unpack("<3L",decoded)
                            telemetry.tx_count = frame[0]
                            telemetry.rx_count = frame[1]
                            telemetry.fail_count = frame[2]
                        except:
                            telemetry.sd_rx_fail += 1
            except Exception as e:
                print(e)

def input_thread(dev):
    for evt in dev.read_loop():
        with input_mutex:
            if evt.type == evdev.ecodes.EV_ABS:
                if evt.code == AX_LX:
                    gp_state.lx = -evt.value if gp_state.inv_ls else evt.value
                elif evt.code == AX_LY:
                    gp_state.ly = -evt.value if gp_state.inv_ls else evt.value
                elif evt.code == AX_RX:
                    gp_state.rx = -evt.value if gp_state.inv_rs else evt.value
                elif evt.code == AX_RY:
                    gp_state.ry = -evt.value if gp_state.inv_rs else evt.value
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

    abs_info = dict(device.capabilities().get(evdev.ecodes.EV_ABS, []))
    ax_info = abs_info.get(evdev.ecodes.ABS_X)
    gp_state.ax_min = ax_info.min if ax_info else -32768
    gp_state.ax_max = ax_info.max if ax_info else 32767

    thr_input = Thread(target=input_thread, args=(device,), daemon=True)
    thr_serial_rx = Thread(target=serial_rx_thread, daemon=True)
    thr_serial = Thread(target=serial_thread, args=(thr_serial_rx,), daemon=True)
    
    thr_input.start()
    thr_serial.start()

    dpg.create_context()
    dpg.create_viewport(title='Custom Title')

    with dpg.window(label="The Window",tag="Primary Window"):
        with dpg.child_window():
            with dpg.child_window(autosize_x=True, height=95):
                with dpg.group(horizontal=True):
                    axis_text = dpg.add_text()
                    with dpg.table(header_row=False):
                        dpg.add_table_column()
                        dpg.add_table_column()
                        with dpg.table_row():
                            dpg.add_text(f"TX side TX count")
                            tx_side_tx = dpg.add_text(f"0.1 ms")
                        with dpg.table_row():
                            dpg.add_text(f"TX side RX count")
                            tx_side_rx = dpg.add_text(f"9000 hz")
                        with dpg.table_row():
                            dpg.add_text(f"SD UART RX fails")
                            sd_rx_fail = dpg.add_text(f"0.1 ms")
            with dpg.child_window(autosize_x=True, autosize_y=True):
                with dpg.group(horizontal=True, width=0):
                    with dpg.child_window(width=102, autosize_y=True):
                        with dpg.group():
                            throttle_knob = dpg.add_knob_float(min_value = gp_state.ax_min, max_value=gp_state.ax_max)
                            steering_knob = dpg.add_knob_float(min_value = gp_state.ax_min, max_value=gp_state.ax_max)
                    with dpg.child_window(autosize_y=True):
                        with dpg.plot(label="Acceleration Profile", height=400, width=-1,no_inputs=True):
                            dpg.add_plot_legend()
                            xaxis = dpg.add_plot_axis(dpg.mvXAxis, label="x")
                            yaxis = dpg.add_plot_axis(dpg.mvYAxis, label="y")
                            dpg.set_axis_limits(xaxis, gp_state.ax_min, gp_state.ax_max)
                            dpg.set_axis_limits(yaxis, gp_state.ax_min, gp_state.ax_max)

                            raw_accel = dpg.add_drag_line(label="raw_accel", color=[255, 0, 0, 255], no_inputs=True)
                            filt_accel = dpg.add_drag_line(label="filt_accel", color=[255, 255, 0, 255], no_inputs=True)
                            dpg.add_drag_rect(label="dz_rect", tag="dz_rect", color=[255, 0, 0, 255], default_value=(-gp_state.l_dz,gp_state.ax_min,gp_state.l_dz,gp_state.ax_max),no_inputs=True)

    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("Primary Window", True)
    while dpg.is_dearpygui_running():
        dpg.set_value(raw_accel,gp_state.ly)
        dpg.set_value(filt_accel,gp_state.ly_filt)

        dpg.set_value(axis_text, f"{gp_state.ly:10} {gp_state.rx:10}")
        dpg.set_value(throttle_knob, gp_state.ly)
        dpg.set_value(steering_knob, gp_state.rx)
        dpg.set_value(tx_side_tx, telemetry.tx_count)
        dpg.set_value(tx_side_rx, telemetry.rx_count)
        dpg.set_value(sd_rx_fail, telemetry.sd_rx_fail)
        dpg.render_dearpygui_frame()
    dpg.destroy_context()

if __name__ == "__main__":
    main()