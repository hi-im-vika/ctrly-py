import evdev
import threading

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

def main():
    print("Hello from ctrly-py!")
    try:
        device = find_gamepad()
    except:
        print("No gamepad found")
        exit()
    
    print(device)


if __name__ == "__main__":
    main()
