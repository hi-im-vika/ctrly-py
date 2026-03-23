import evdev
import threading
import time
from dataclasses import dataclass

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

gp_state = GamepadState()

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

    thr_input = threading.Thread(target=input_thread, args=(device,), daemon=True)
    thr_input.start()

    try:
        while True:
            print(f"{gp_state.ly:10} {gp_state.rx:10}\r", end="")
            time.sleep(0.001)
    except KeyboardInterrupt:
        print("Bye bye")

if __name__ == "__main__":
    main()
