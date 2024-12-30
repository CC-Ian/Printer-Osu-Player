import math
import serial
import time
import pyautogui

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
        rawData = point.split(',')
        x = rawData[0]
        y = rawData[1]
        time = rawData[2]

        # Convert to absolute X, Y position on 3d printer bed. Scale factor of 10 to map real world with print bed. I believe these can stay locked together?
        convertedX = (int(x) - 256) / 22.0
        convertedY = (int(y) - 192) / 22.0

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

        gcodeList.append(f"G1 X{y} Y{x} F{feedrate}\n")
    
    # Returns the beatmap gcode as a list.
    return gcodeList

def serialWrite(serial, command):
    serial.write(command.encode('utf-8'))
    while True:
        line = ser.readline()
        if line == b'ok\n':
            break


beatmapCoords = ['0, 0, 500', '250, 0, 1000', '512, 0, 1500', '512, 192, 2000', '512, 384, 2500', '256, 384, 3000', '0, 384, 3500', '0, 192, 4000', '0, 0, 4500', '256, 192, 5000']
# beatmapCoords = ['256, 192, 600']
# beatmapCoords = ['512, 384, 700']
# beatmapCoords = []

printercoords = convertCoordinates(beatmapCoords)

gcode = createBeatMapGcode(printercoords)

print(gcode)


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

# time.sleep(5)

try:
    # Home printer and return to centerpoint
    # serialWrite(ser, "G28 X Y\n")
    serialWrite(ser, "M201 X15000 Y15000 Z100 E5000\n")
    serialWrite(ser, "M203 X15000 Y15000 Z10 E60\n")
    serialWrite(ser, "M205 X100.00 Y100.00 Z0.40 E5.00\n")
    serialWrite(ser, "G1 X110 Y110 F 10000\n")
    # serialWrite(ser, "G1 Z8\n")

    time.sleep(2)

    # Start the beatmap
    # pyautogui.press('enter')

    # Delay based on precalculated time """constants"""
    time.sleep(0.25)

    # Send the beatmap move commands!
    for command in gcode:
        serialWrite(ser, command)
    
    time.sleep(2)

    # serialWrite(ser, "G1 Z18\n")



except Exception as e:
    print(f"An error occurred: {str(e)}")

finally:
    # Close the serial port
    ser.close()
    print("Serial port closed.")