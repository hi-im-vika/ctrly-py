import evdev

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

def main():
    print("Hello from ctrly-py!")


if __name__ == "__main__":
    main()
