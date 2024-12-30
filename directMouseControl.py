import math
import serial
import time
import pyautogui
from Xlib import X, display
from Xlib.ext import xtest

# Base ~2.4 second delay between when I start the beatmap and when it loads. Can assume it's generally constant.
# Improvement: Base the start time off of ambient desktop audio. When the game menu stops, begin timer till first note.

# I'm also thinking there's a quarter second 250ms delay between start of beatmap and map load. From some rough testing.



BEATMAP = "./BeatMap/DragonForce - Through the Fire and Flames (Ponoyoshi) [Myth].osu"
# BEATMAP = "./BeatMap/Feint - We Won't Be Alone (feat. Laura Brehm) (FCL) [MKL's Insane].osu"

d = display.Display()

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

def convertCoordinates(hitObjectList):
    '''Takes in a list of hitobjects from the osu beatmap file, and converts it to a list of X, Y coordinate pairs for the 3d printer'''
    coordinateList = []
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
        convertedX = (int(x) - 256) * 3
        convertedY = (int(y) - 192) * 3

        # Append newly calculated coordinate pair with time difference to array.
        coordinateList.append([convertedX,convertedY, int(time)])
        lastTime = time

    # for item in coordinateList:
    #     print(item)

    # Returns list of coordinate pairs in the form:
    #  [[110, 110, 0], [100, 102, 480], ...]
    # (Home position), New point (110, 102). Must be there by 480ms in. etc.
    return coordinateList

def createControlPoints(scaledCoords):
    controlPoints = []

    lastTime = 0
    for coordinate in scaledCoords:
        x = coordinate[0]
        y = coordinate[1]
        time = coordinate[2]

        controlPoints.append([2560 + 1280 + x, 720 + y, (time - lastTime) / 1000])
        lastTime = time

    # for item in controlPoints:
    #     print(item)
    
    return controlPoints

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
                sliderDuration = float(hitObject[7]) / (sliderMultiplier * 100 * (1 / (.01 * abs(SV)))) * beatLength
                # print(hitObject)
                print(f"SV: {1 / (.01 * abs(SV))}, sliderDuration: {sliderDuration}")
                # print(beatLength)
            else:
                sliderDuration = float(hitObject[7]) / (sliderMultiplier * 100 * 1) * beatLength
                print(f"SV: 1, sliderDuration: {sliderDuration}")


            sliderPointCopy = subPoints[::-1]

            for i in range(int(hitObject[6]) - 1):
                subPoints.extend(sliderPointCopy)
                sliderPointCopy = sliderPointCopy[::-1]

            numSubPoints = len(subPoints) - 1

            visibility = []

            sliderDuration *= int(hitObject[6])

            subPointIndex = 0
            for subPoint in subPoints:
                subPoint = subPoint.split(',')
                result.append([int(subPoint[0]), int(subPoint[1]), timeABS + subPointIndex*(sliderDuration/numSubPoints)])
                subPointIndex += 1
        
        else:
            result.append([x, y, timeABS])
    
    return result

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

def move_mouse(x, y):
    root = d.screen().root
    root.warp_pointer(x, y)
    d.sync()

def click_mouse():
    # Press the mouse button
    xtest.fake_input(d, X.ButtonPress, 1)
    d.sync()  # Ensure the command is sent before we release

    # Release the mouse button
    xtest.fake_input(d, X.ButtonRelease, 1)
    d.sync()

sliderMultiplier = acquireSliderMultiplier(BEATMAP)

compressedTimingPoints = compressTimingPoints(read_lines_between(BEATMAP, "[TimingPoints]", ""))

hitObjects = acquireHitObjects(BEATMAP)

hitObjects = extractSliders(hitObjects, compressedTimingPoints, sliderMultiplier)

scaledCoords = convertCoordinates(hitObjects)
controlPoints = createControlPoints(scaledCoords)

# exit()

time.sleep(5)

try:
    # Start the beatmap
    pyautogui.press('enter')

    # Delay based on precalculated time """constants"""
    time.sleep(2.540) # Needs to be about 3 for the printer.
    beatMapStart = time.time() * 1000.00

    # Send the beatmap move commands!
    commandIndex = 0
    for point in controlPoints:
        move_mouse(point[0], point[1])
        while ((time.time() * 1000.00) - beatMapStart) < hitObjects[commandIndex][2]:
            continue
        # click_mouse()
        commandIndex += 1
    # serialWrite(ser, "G1 Z18\n")


except Exception as e:
    print(f"An error occurred: {str(e)}")

# finally:
#     # Close the serial port
#     ser.close()``
#     print("Serial port closed.")  
d.close()