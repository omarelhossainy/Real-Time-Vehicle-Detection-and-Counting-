import cv2
import numpy as np
import sys
import os

# Create a window and set a mouse callback
points = []

def mouse_callback(event, x, y, flags, param):
    global points, img_copy
    if event == cv2.EVENT_LBUTTONDOWN:
        if len(points) < 4:
            points.append((x, y))
            cv2.circle(img_copy, (x, y), 5, (0, 0, 255), -1)
            
            if len(points) > 1:
                cv2.line(img_copy, points[-2], points[-1], (0, 255, 0), 2)
            if len(points) == 4:
                cv2.line(img_copy, points[-1], points[0], (0, 255, 0), 2)
                
            cv2.imshow('Coordinate Finder', img_copy)

if len(sys.argv) < 2:
    print("Usage: python coordinate_finder.py <path_to_image>")
    sys.exit(1)

image_path = sys.argv[1]
if not os.path.exists(image_path):
    print(f"Error: File '{image_path}' not found.")
    sys.exit(1)

img = cv2.imread(image_path)
img_copy = img.copy()

cv2.namedWindow('Coordinate Finder')
cv2.setMouseCallback('Coordinate Finder', mouse_callback)

print("--------------------------------------------------")
print("Click 4 points on the image to define your counting box.")
print("Press 'r' to reset points.")
print("Press 'q' or 'ESC' to quit.")
print("--------------------------------------------------")

while True:
    cv2.imshow('Coordinate Finder', img_copy)
    key = cv2.waitKey(1) & 0xFF
    
    if key == ord('r'):
        points = []
        img_copy = img.copy()
        print("Points reset.")
    elif key == ord('q') or key == 27:
        break
    
    if len(points) == 4:
        print("\n\nYOUR NEW POLYGON COORDINATES ARE:")
        print(f"[( {points[0][0]}, {points[0][1]} ), ( {points[1][0]}, {points[1][1]} ), ( {points[2][0]}, {points[2][1]} ), ( {points[3][0]}, {points[3][1]} )]")
        print("\nCopy and paste the array above into config.py!")
        break

cv2.waitKey(0)
cv2.destroyAllWindows()
