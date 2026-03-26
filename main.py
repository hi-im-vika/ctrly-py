import evdev
from threading import Thread, Lock
import time
import serial
import struct
from serial.tools import list_ports
from cobs import cobs
from dataclasses import dataclass
import dearpygui.dearpygui as dpg
from enum import Enum
import configparser

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

class ConnStatus(Enum):
    CONNECTED = 1
    DISCONNECTED = 2
    RECONNECTING = 3

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

@dataclass
class Calibration:
    is_zoomy = False
    l_dz: int = 5000
    r_dz: int = 5000
    r_dz2: int = 18768
    ax_max: int = 0
    ax_min: int = 0
    use_l_dz: bool = True
    use_r_dz: bool = True
    ly_min_dz: int = 0
    ly_max_dz: int = 0
    rx_min_dz: int = 0
    rx_max_dz: int = 0
    trim: int = 500
    t_factor: int = 0
    use_t_factor: bool = True
    constrain_rx: bool = False
    constrain_mag: int = 5000

@dataclass
class CtrlyState:
    port: str = ''
    connected: ConnStatus = ConnStatus.DISCONNECTED

@dataclass
class Telemetry:
    tx_count: int = 0
    rx_count: int = 0
    fail_count: int = 0
    sd_rx_fail: int = 0

gp_state = GamepadState(0,0,0,0,0)
ctrly_state = CtrlyState()
telemetry = Telemetry()
calib = Calibration()
zoomy_calib = Calibration()

input_mutex = Lock()
tm_mutex = Lock()

calib_defaults = {
    "calibration": {
        "trim": 500
    }
}

def load_config():
    config = configparser.ConfigParser()

    for section, value in calib_defaults.items():
        config[section] = value

    config.read("config.ini")
    return config

config = load_config()

calib.trim = int(config['calibration']['trim'])

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
            ctrly_state.connected = ConnStatus.RECONNECTING
            try:
                ctrly_state.port = find_port()
            except:
                ctrly_state.connected = ConnStatus.DISCONNECTED
                print("No port found. Retrying in 1s")
                time.sleep(1)
        try:
            print(ctrly_state.port.device)
            with serial.Serial(ctrly_state.port.device, baudrate=115200) as ser:
                if not t.is_alive():
                    t.start()
                ctrly_state.connected = ConnStatus.CONNECTED
                while True:
                    with(input_mutex):
                        # put TX/RX stuff here
                        # do deadzone calcs

                        # t-factor to scale steering range based on throttle
                        if (gp_state.ly_filt):
                            if (calib.use_t_factor):
                                calib.t_factor = map_range(abs(abs(abs(gp_state.ly_filt) - 32767) - 32767), calib.l_dz, 32767, 0, calib.r_dz2 - calib.l_dz)
                            else:
                                calib.t_factor = 0
                        if calib.constrain_rx and not calib.use_t_factor:
                            calib.rx_min_dz = calib.ax_min - (-calib.r_dz2) - (-calib.trim)+ calib.constrain_mag
                            calib.rx_max_dz = calib.ax_max - (calib.r_dz2) + (calib.trim) - calib.constrain_mag
                        else:
                            calib.rx_min_dz = calib.ax_min - (-calib.r_dz2) - (-calib.trim) - (-calib.t_factor)
                            calib.rx_max_dz = calib.ax_max - (calib.r_dz2) + (calib.trim) - (calib.t_factor)
                        if calib.is_zoomy:
                                gp_state.lx_filt = gp_state.lx
                                gp_state.ly_filt = gp_state.ly
                                gp_state.rx_filt = gp_state.rx
                                gp_state.ry_filt = gp_state.ry
                        else:
                            if calib.use_l_dz:
                                gp_state.lx_filt = gp_state.lx if abs(gp_state.lx) > calib.l_dz else 0
                                gp_state.ly_filt = gp_state.ly if abs(gp_state.ly) > calib.l_dz else 0
                            else:
                                gp_state.lx_filt = gp_state.lx
                                gp_state.ly_filt = gp_state.ly
                            if calib.use_r_dz:
                                gp_state.rx_filt = map_range(gp_state.rx, calib.ax_min, calib.ax_max, calib.rx_min_dz, calib.rx_max_dz) if abs(gp_state.rx) > calib.r_dz else calib.trim
                                gp_state.ry_filt = map_range(gp_state.ry, calib.ax_min, calib.ax_max, calib.ax_min - (-calib.r_dz2), calib.ax_max - (calib.r_dz2)) if abs(gp_state.ry) > calib.r_dz else 0
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
            ctrly_state.connected = ConnStatus.DISCONNECTED
            ctrly_state.port = ''

def serial_rx_thread():
    while True:
        while ctrly_state.connected == ConnStatus.CONNECTED:
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

def change_trim(sender, app_data, user_data):
    calib.trim = app_data
    with open('config.ini', 'w') as cfgfile:
        config["calibration"]["trim"] = str(calib.trim)
        config.write(cfgfile)

def is_zoomy_cb(sender, app_data, user_data):
    calib.is_zoomy = app_data

def use_l_dz_cb(sender, app_data, user_data):
    calib.use_l_dz = app_data

def use_r_dz_cb(sender, app_data, user_data):
    calib.use_r_dz = app_data

def use_t_factor_cb(sender, app_data, user_data):
    calib.use_t_factor = app_data

def constrain_rx_cb(sender, app_data, user_data):
    calib.constrain_rx = app_data

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
    calib.ax_min = ax_info.min if ax_info else -32768
    calib.ax_max = ax_info.max if ax_info else 32767

    thr_input = Thread(target=input_thread, args=(device,), daemon=True)
    thr_serial_rx = Thread(target=serial_rx_thread, daemon=True)
    thr_serial = Thread(target=serial_thread, args=(thr_serial_rx,), daemon=True)
    
    thr_input.start()
    thr_serial.start()

    dpg.create_context()
    dpg.create_viewport(title='Custom Title')

    with dpg.window(label="The Window",tag="Primary Window"):
        conn_status = dpg.add_text(label="")
        with dpg.group():
            with dpg.child_window(height=120,width=-1):
                with dpg.group(horizontal=True):
                    with dpg.group(horizontal=True):
                        throttle_slider = dpg.add_slider_int(min_value = calib.ax_min, max_value=calib.ax_max,vertical=True,height=100,width=100)
                        steering_slider = dpg.add_slider_int(min_value = calib.ax_min, max_value=calib.ax_max,vertical=True,height=100,width=100)
                        with dpg.group():
                            with dpg.table(header_row=False, width=300):
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
                            accel_actual_sent = dpg.add_text("A")
                            steer_actual_sent = dpg.add_text("A")
                        with dpg.group():
                            input_int_trim = dpg.add_input_int(label="change trim", width=100, default_value=calib.trim, callback=change_trim)
                            drag_int_trim = dpg.add_drag_int(label="change trim (faster)", width=100, default_value=calib.trim, min_value=calib.ax_min, max_value=calib.ax_max, callback=change_trim)
                            accel_actual_sent = dpg.add_text("A")
                            steer_actual_sent = dpg.add_text("A")
                        with dpg.group():
                            cb_is_zoomy = dpg.add_checkbox(label="is zoomy", default_value=calib.is_zoomy, callback=is_zoomy_cb)
                            cb_use_l_dz = dpg.add_checkbox(label="use_l_dz", default_value=calib.use_l_dz, callback=use_l_dz_cb)
                            cb_use_r_dz = dpg.add_checkbox(label="use_r_dz", default_value=calib.use_r_dz, callback=use_r_dz_cb)
                            cb_use_t_factor = dpg.add_checkbox(label="use_t_factor", default_value=calib.use_t_factor, callback=use_t_factor_cb)
                            cb_constrain_rx = dpg.add_checkbox(label="constrain_rx", default_value=calib.constrain_rx, callback=constrain_rx_cb)
                        dpg.add_button(label="fullscreen", width=100, height=100, callback=lambda:dpg.toggle_viewport_fullscreen())
                        dpg.add_button(label="exit", width=100, height=100, callback=lambda:exit())
            with dpg.child_window(autosize_y=True):
                with dpg.plot(label="Acceleration Profile", width=-1,no_inputs=True):
                    dpg.add_plot_legend()
                    xaxis = dpg.add_plot_axis(dpg.mvXAxis, label="x")
                    yaxis = dpg.add_plot_axis(dpg.mvYAxis, label="y")
                    dpg.set_axis_limits(xaxis, calib.ax_min, calib.ax_max)
                    dpg.set_axis_limits(yaxis, calib.ax_min, calib.ax_max)

                    raw_accel = dpg.add_drag_line(label="raw_accel", color=[255, 0, 0, 255], no_inputs=True)
                    filt_accel = dpg.add_drag_line(label="filt_accel", color=[255, 255, 0, 255], no_inputs=True)
                    
                    l_dz_rect = dpg.add_drag_rect(label="dz_rect", tag="dz_rect", color=[255, 0, 0, 255], default_value=(-calib.l_dz,calib.ax_min,calib.l_dz,calib.ax_max),no_inputs=True)
                with dpg.plot(label="Steering Profile", width=-1,no_inputs=True):
                    dpg.add_plot_legend()
                    steer_xaxis = dpg.add_plot_axis(dpg.mvXAxis, label="x")
                    steer_yaxis = dpg.add_plot_axis(dpg.mvYAxis, label="y")
                    dpg.set_axis_limits(steer_xaxis, calib.ax_min, calib.ax_max)
                    dpg.set_axis_limits(steer_yaxis, calib.ax_min, calib.ax_max)

                    raw_steer = dpg.add_drag_line(label="raw_steer", color=[255, 0, 0, 255], no_inputs=True)
                    filt_steer = dpg.add_drag_line(label="filt_steer", color=[255, 255, 0, 255], no_inputs=True)

                    r_dz2_rect = dpg.add_drag_rect(label="r_dz2_rect", color=[255, 255, 0, 255], default_value=(calib.rx_min_dz,calib.ax_min,calib.rx_max_dz, calib.ax_max),no_inputs=True)
                    r_dz_rect = dpg.add_drag_rect(label="r_dz_rect", color=[255, 0, 0, 255], default_value=(-calib.r_dz,calib.ax_min,calib.r_dz,calib.ax_max),no_inputs=True)


    dpg.setup_dearpygui()
    dpg.toggle_viewport_fullscreen()
    dpg.show_viewport()
    dpg.set_primary_window("Primary Window", True)
    while dpg.is_dearpygui_running():
        dpg.set_value(raw_accel,gp_state.ly)
        dpg.set_value(filt_accel,gp_state.ly_filt)

        dpg.set_value(raw_steer,gp_state.rx)
        dpg.set_value(filt_steer,gp_state.rx_filt)
        if (ctrly_state.connected == ConnStatus.CONNECTED):
            dpg.set_value(conn_status, f"CONNECTED: {ctrly_state.port}")
            dpg.configure_item(conn_status, color=[0,255,0,255])
        elif (ctrly_state.connected == ConnStatus.RECONNECTING):
            dpg.set_value(conn_status, "RECONNECTING")
            dpg.configure_item(conn_status, color=[255,255,0,255])
        else:
            dpg.set_value(conn_status, "DISCONNECTED")
            dpg.configure_item(conn_status, color=[255,0,0,255])

        dpg.set_value(input_int_trim,calib.trim)
        dpg.set_value(drag_int_trim,calib.trim)

        if (calib.is_zoomy):
            dpg.configure_item(cb_use_l_dz, show=False)
            dpg.configure_item(cb_use_r_dz, show=False)
            dpg.configure_item(cb_use_t_factor, show=False)
            dpg.configure_item(cb_constrain_rx, show=False)
        else:
            dpg.configure_item(cb_use_l_dz, show=True)
            dpg.configure_item(cb_use_r_dz, show=True)
            dpg.configure_item(cb_use_t_factor, show=True)
            dpg.configure_item(cb_constrain_rx, show=True)

        dpg.set_value(r_dz2_rect, (calib.rx_min_dz,calib.ax_min,calib.rx_max_dz, calib.ax_max))

        dpg.set_value(accel_actual_sent, gp_state.ly_filt)
        dpg.set_value(steer_actual_sent, gp_state.rx_filt)

        dpg.set_value(throttle_slider, gp_state.ly)
        dpg.set_value(steering_slider, gp_state.rx)
        dpg.set_value(tx_side_tx, telemetry.tx_count)
        dpg.set_value(tx_side_rx, telemetry.rx_count)
        dpg.set_value(sd_rx_fail, telemetry.sd_rx_fail)
        dpg.render_dearpygui_frame()
    dpg.destroy_context()

if __name__ == "__main__":
    main()