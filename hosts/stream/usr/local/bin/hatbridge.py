#!/usr/bin/env python3
"""Turn the Sunshine virtual pad into keys for SuperTuxKart.

The overlay's button labels do not match the kernel codes: pressing the button labelled
A sends BTN_SOUTH, B sends BTN_NORTH, X sends BTN_WEST and Y sends BTN_EAST. STK reads
keys reliably, so this translates the codes we actually observed.

A emits both Return and Up: Return confirms in menus, Up is the accelerator in a race.
"""
import glob, os, struct, subprocess, time

SIZE = struct.calcsize("llHHi")
HAT = {-1: "Left", 1: "Right"}
BTN = {
    304: ["Return", "Up"],   # the button labelled A
    305: ["Down"],           # labelled Y
    307: ["space"],          # labelled B
    308: ["Return"],         # labelled X
}
held = {}


def key(action, name):
    if action == "down":
        if name not in held:
            subprocess.run(["xdotool", "keydown", name], check=False)
            held[name] = True
    elif name in held:
        subprocess.run(["xdotool", "keyup", name], check=False)
        del held[name]


def release_all():
    for name in list(held):
        key("up", name)


def find_device():
    for event in sorted(glob.glob("/sys/class/input/event*")):
        try:
            with open(os.path.join(event, "device/name")) as fh:
                if "Sunshine" in fh.read():
                    return "/dev/input/" + os.path.basename(event)
        except OSError:
            continue
    return None


while True:
    device = find_device()
    if not device:
        release_all()
        time.sleep(1)
        continue
    try:
        with open(device, "rb") as dev:
            while True:
                data = dev.read(SIZE)
                if len(data) < SIZE:
                    break
                _, _, etype, code, value = struct.unpack("llHHi", data)
                if etype == 1 and code in BTN:
                    for name in BTN[code]:
                        key("down" if value else "up", name)
                elif etype == 3 and code == 16:
                    if value in HAT:
                        key("down", HAT[value])
                    else:
                        key("up", "Left")
                        key("up", "Right")
                elif etype == 3 and code == 17 and value == 0:
                    key("up", "Up")
                    key("up", "Down")
    except OSError:
        pass
    release_all()
    time.sleep(1)
