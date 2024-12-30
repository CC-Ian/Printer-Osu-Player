import math
import serial
import time
import pyautogui
from Xlib import X, display
import os
from Xlib.display import Display
from Xlib.ext import xtest
from Xlib import XK

import threading

# Base ~2.4 second delay between when I start the beatmap and when it loads. Can assume it's generally constant.
# Improvement: Base the start time off of ambient desktop audio. When the game menu stops, begin timer till first note.

# I'm also thinking there's a quarter second 250ms delay between start of beatmap and map load. From some rough testing.

BEATMAP = "./BeatMap/Feint & Laura Brehm - Solace (Cut Ver.) (Kujinn) [A r M i N's Expert].osu"

d = display.Display()
_display = Display(os.environ['DISPLAY'])

def acquireSliderMultiplier(filename):
    try:
        with open(filename, 'r') as file:
            SliderMultiplier = None
            lines = file.readlines()
            # print(lines)
            for line in lines:
                if 'SliderMultiplier:' in line:
                    SliderMultiplier = float(line.replace('\n', '').split(':')[1])
                    print(f"Slider Multiplier: {SliderMultiplier}")
                    return SliderMultiplier

    except FileNotFoundError:
        print("Failed to find beatmap")

def acquireHitObjects(filename):
    try:
        with open(filename, 'r') as file:
            lines = file.readlines()
            # print(lines)
            lineIndex = 0
            hitSection = 0
            hitObjects = []
            for line in lines:
                if hitSection == 1:
                    hitObjects.append(line)

                if line == '[HitObjects]\n':
                    hitSection = 1

            return hitObjects

    except FileNotFoundError:
        print("Failed to find beatmap")

def read_lines_between(file_path, start_marker, end_marker):
    with open(file_path, 'r') as file:
        lines = file.readlines()

    result = []
    is_within_section = False

    for line in lines:
        line = line.strip()

        if line == start_marker:
            is_within_section = True
            continue

        if line == end_marker and is_within_section:
            break

        if is_within_section:
            result.append(line)

    return result

def find_index_of_timing_points(number, timingPoints):
    # print(f"number: {number}")
    for index, entry in enumerate(timingPoints):
        # Return last point in the list
        if index + 1 > len(timingPoints)-1:
            return index
        # All other points
        elif number >= entry[0] and number < timingPoints[index + 1][0]:
            # print(f"entry: {entry[0]}")
            return index
    return None  # Handle the case where the number is smaller than the smallest number in the short array

def extractSliders(hitObjectList, compressedTimingPoints, sliderMultiplier):
    '''
    Takes in a list of hit objects in the form [[x, y, absoluteTime], [x, y, absoluteTime], ...]
    Takes in a list of compressed timing points in the form [[absoluteTime, beatLength, uninherited], [absoluteTime, beatLength, uninherited], ...]
    takes in the slider multiplier in the form of a double ex: 1.23'''
    print(compressedTimingPoints)
    result = []

    for hitObject in hitObjectList:
        hitObject = hitObject.replace('\n', '').split(',')
        x = int(hitObject[0])
        y = int(hitObject[1])
        timeABS = int(hitObject[2])

        SVIndex = find_index_of_timing_points(timeABS, compressedTimingPoints)
        # print(f"BeatLengthIndex: {beatlengthIndex}")
        SV = compressedTimingPoints[SVIndex][1]

        beatLength = compressedTimingPoints[0][1]
        # print(beatLength)

        # If the hitobject is a slider
        if "L" in hitObject[5] or "P" in hitObject[5] or "B" in hitObject[5] or "C" in hitObject[5]:
            # Compute time between points. So I need a list of points
            subPoints = [f"{x},{y}"]
            subPoints.extend(hitObject[5].replace("L|", "").replace("B|", "").replace("P|", "").replace("C|", "").replace(":", ",").split("|"))
            sliderDuration = 0
            
            # print(compressedTimingPoints[timingPointIndex][1])
            if SV < 0.00:
                sliderDuration = float(hitObject[7]) / (sliderMultiplier * 100 * (1 / (.01 * abs(SV)))) * beatLength * int(hitObject[6])
            else:
                sliderDuration = float(hitObject[7]) / (sliderMultiplier * 100 * 1) * beatLength * int(hitObject[6])

            sliderPointCopy = subPoints[::-1]

            for i in range(int(hitObject[6]) - 1):
                subPoints.extend(sliderPointCopy)
                sliderPointCopy = sliderPointCopy[::-1]

            numSubPoints = len(subPoints) - 1

            subPointIndex = 0
            for subPoint in subPoints:
                subPoint = subPoint.split(',')
                result.append([int(subPoint[0]), int(subPoint[1]), round(timeABS + subPointIndex*(sliderDuration/numSubPoints), 2), 1])
                subPointIndex += 1
        
        else:
            result.append([x, y, timeABS, 0])
    
    return result

def convertCoordinates(hitObjectList):
    '''Takes in a list of hitobjects from the osu beatmap file, and converts it to a list of X, Y coordinate pairs for the 3d printer'''
    coordinateList = [[110, 110, 0]]
    # X, Y, DeltaT
    # Start at middle of printer. 110, 110 for ender 3

    lastTime = 0
    # Iterate through each hitObject in the list of hitobjects
    for point in hitObjectList:
        # Split it out into X, Y, Time.
        # Will need to do additional work on this algorithm to handle sliders.
        x = point[0]
        y = point[1]
        time = point[2]

        # Convert to absolute X, Y position on 3d printer bed. Scale factor of 10 to map real world with print bed. I believe these can stay locked together?
        convertedX = round((int(x) - 256) / 22.0, 2)
        convertedY = round((int(y) - 192) / 22.0, 2)

        # Append newly calculated coordinate pair with time difference to array.
        coordinateList.append([110 + convertedX, 110 + convertedY, int(time) - int(lastTime)])
        lastTime = time

    # Returns list of coordinate pairs in the form:
    #  [[110, 110, 0], [100, 102, 480], ...]
    # (Home position), New point (110, 102). Must be there by 480ms in. etc.
    return coordinateList

def createBeatMapGcode(coordinateList):
    gcodeList = []


    for cordIndex in range(1, len(coordinateList)):
        # Current coordinate and previous coordinate.
        # Used to compute the distance of the next move for feedrate.

        coordinateOld = coordinateList[cordIndex-1]
        coordinate = coordinateList[cordIndex]

        # Extract X, Y positions from current and previous coordinate.
        xOld = coordinateOld[0]
        yOld = coordinateOld[1]
        x = coordinate[0]
        y = coordinate[1]
        # print(f"x: {x}, y: {y}")

        if x == xOld and y == yOld:
            x += .01

        timeMS = coordinate[2]

        # Compute triangle legs A and B.
        deltaX = x - xOld
        deltaY = y - yOld

        # Compute triangle hypotnuse C.
        distance = round(math.sqrt((deltaX * deltaX) + (deltaY * deltaY)), 5)

        # Feedrate is speed in (distance / time).
        feedrate = round((distance / timeMS)*1000*60, 5)

        gcodeList.append(f"G1 X{y} Y{x} F10000\n")
    
    # Returns the beatmap gcode as a list.
    return gcodeList

def serialWrite(serial, command):
    serial.write(command.encode('utf-8'))
    while True:
        line = ser.readline()
        if line == b'ok\n':
            break

def compressTimingPoints(timingPoints):
    '''Compresses list of timing points to printer specific requirements.
    Associates beatLength changes to times, ignoring subsequent changes until the next.'''
    result = []
    lastBeatLength = 0

    for point in timingPoints:
        # Split string to 
        point = point.split(',')

        time = int(point[0])
        beatLength = float(point[1])
        uninherited = int(point[6])
        
        if lastBeatLength != beatLength:
            result.append([time, beatLength, uninherited])
        lastBeatLength = beatLength

    return result


def click_mouse(clickPrior, clickNow, clickNext):
    print(f"{clickPrior}, {clickNow}, {clickNow}")

    # Button Presses
    if clickPrior == 1 and clickNow == 1:
        print("No Op")
        pass
    elif clickNow == 1 and clickNext == 0:
        xtest.fake_input(d, X.KeyRelease, _display.keysym_to_keycode(XK.string_to_keysym("c")))
        d.sync()
        print("slider end")
    elif clickPrior == 0 and clickNow == 1:
        xtest.fake_input(d, X.KeyPress, _display.keysym_to_keycode(XK.string_to_keysym("c")))
        d.sync()
        print("slider start")
    else:
        # Press the key
        xtest.fake_input(d, X.KeyPress, _display.keysym_to_keycode(XK.string_to_keysym("c")))
        d.sync()  # Ensure the command is sent before we release
        xtest.fake_input(d, X.KeyRelease, _display.keysym_to_keycode(XK.string_to_keysym("c")))
        d.sync()
        print("circle")
    

sliderMultiplier = acquireSliderMultiplier(BEATMAP)

compressedTimingPoints = compressTimingPoints(read_lines_between(BEATMAP, "[TimingPoints]", ""))

hitObjects = acquireHitObjects(BEATMAP)

hitObjects = extractSliders(hitObjects, compressedTimingPoints, sliderMultiplier)
for obj in hitObjects:
    print(obj)
# exit()

printerCoordinates = convertCoordinates(hitObjects)

beatmapGcode = createBeatMapGcode(printerCoordinates)



def handleGcode():
    commandIndex = 0
    for line in beatmapGcode:
        serialWrite(ser, line)
        while ((time.time() * 1000.00) - beatMapStart + 75) < hitObjects[commandIndex][2]:
            continue
        commandIndex += 1

def handleClicks():
    commandIndex = 0
    sliderPrevious = 0
    for hitObject in hitObjects:
        while ((time.time() * 1000.00) - beatMapStart - 20) < hitObjects[commandIndex][2]:
            continue
        commandIndex += 1
        click_mouse(sliderPrevious, hitObjects[commandIndex][3], hitObjects[commandIndex + 1][3])
        sliderPrevious = hitObjects[commandIndex][3]

# print(beatmapGcode)

# exit()

# Define the serial port and baudrate
serial_port = '/dev/ttyUSB1'  # Change this to the correct port for your setup
baud_rate = 115200  # Adjust the baud rate based on your 3D printer's specifications

# Open the serial port
ser = serial.Serial(serial_port, baud_rate, timeout=1)

# Ensure the serial port is open
if ser.is_open:
    print(f"Connected to {serial_port} at {baud_rate} baud.")
else:
    print(f"Failed to open {serial_port}.")
    exit()

time.sleep(5)

try:
    # Home printer and return to centerpoint
    # serialWrite(ser, "G28 X Y\n")
    serialWrite(ser, "M201 X12000 Y12000 Z200 E5000\n")
    serialWrite(ser, "M203 X12000 Y12000 Z20 E60\n")
    serialWrite(ser, "M205 X50.00 Y30.00 Z0.40 E5.00\n")
    serialWrite(ser, "G1 X110 Y110 F 10000\n")
    # serialWrite(ser, "G1 Z8\n")

    time.sleep(2)

    # Start the beatmap
    pyautogui.press('enter')

    # Delay based on precalculated time """constants"""
    time.sleep(2.53)
    beatMapStart = time.time() * 1000.00

    # gcode_thread = threading.Thread(target=handleGcode)
    # click_thread = threading.Thread(target=handleClicks)

    # # Start the threads
    # gcode_thread.start()
    # click_thread.start()

    # # Wait for both threads to finish
    # gcode_thread.join()
    # click_thread.join()

    commandIndex = 0
    for line in beatmapGcode:
        serialWrite(ser, line)
        while ((time.time() * 1000.00) - beatMapStart + 100) < hitObjects[commandIndex][2]:
            continue
        commandIndex += 1
        
    time.sleep(2)
    serialWrite(ser, "G28\n")

except KeyboardInterrupt as e:
    print(f"Process killed by user")
    # gcode_thread.stop()
    # click_thread.stop()
    serialWrite(ser, "G28\n")
    ser.close()
    exit()

except Exception as e:
    print(f"An error occurred: {str(e)}")
    # gcode_thread.stop()
    # click_thread.stop()
    serialWrite(ser, "G28\n")
    ser.close()
    exit()

finally:
    # Close the serial port
    ser.close()
    print("Serial port closed.")
    exit()