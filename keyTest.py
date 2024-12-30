# import pyautogui
import time
from Xlib import X, display
from Xlib.ext import xtest
# 1534x1150 for my display
# maps to 512x384
# at a scale factor of: 2.999 so 3.

# Dead center of my display is:
# (1280, 720). Corresponding to (256, 192)

# Center of that is...

# n = 5

# sliderPoints = [[1,2], [2,3]]
# sliderPointCopy = sliderPoints[::-1]

# for i in range(n):
#     sliderPoints.extend(sliderPointCopy)
#     sliderPointCopy = sliderPointCopy[::-1]

# for point in sliderPoints:
#     print(point)


# def click_mouse():
#     # Press the mouse button
#     xtest.fake_input(d, X.ButtonPress, 1)
#     d.sync()  # Ensure the command is sent before we release

#     # Release the mouse button
#     xtest.fake_input(d, X.ButtonRelease, 1)
#     d.sync()


array = [[1, 2, 3], [8, 7, 6], [[1, 2], [3,4], [5,6], 56]]
print(array)
for element in array:
    print(element)

# pyautogui.moveTo(100, 100, 1)
# pyautogui.moveTo(mapped_coordinate)
# pyautogui.moveTo(2560 + 100, 100)