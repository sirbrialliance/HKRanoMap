import json

import cv2 as cv # apt install python3-opencv
import numpy
import numpy as np
from matplotlib import pyplot

from processData import outputFolder

DEBUG_IMAGE = False

def gammaToLinear(v):
	if v >= 0.04045: return pow(((v + 0.055)/(1 + 0.055)), 2.4)
	else: return v / 12.92

def linearToGamma(v):
	if v >= 0.0031308: return 1.055 * pow(v, (1.0/2.4)) - 0.055
	else: return 12.92 * v

def lerp(v, aMin, aMax, bMin, bMax):
	return ((bMax - bMin) * v + aMax * bMin - aMin * bMax) / (aMax - aMin)

linearLUT = np.asarray([gammaToLinear(v / 255) * 255 for v in range(0, 256)], dtype=np.uint8)
gammaLUT = np.asarray([linearToGamma(v / 255) * 255 for v in range(0, 256)], dtype=np.uint8)

class TileHandler:
	image: np.ndarray
	_debugIdx = 1
	logicalImageSize: (int, int) # size to use for pixel<->world conversions

	def __init__(self, tileName):
		super().__init__()
		self.tileName = tileName

		self.image = cv.imread(tileName + ".png", cv.IMREAD_UNCHANGED)
		if self.image is None: raise FileNotFoundError(f"Failed to read image {tileName}.png")

		self.logicalImageSize = (self.image.shape[1], self.image.shape[0])

		with open(tileName + ".json", "r") as f:
			self.data = json.load(f)

		if DEBUG_IMAGE:
			pyplot.figure(dpi=240, figsize=(4, 6))
			pyplot.tight_layout()

	def pixelToWorld(self, x, y):
		# (minus one to w/h because the rightmost pixel should be inclusive of the right edge)
		rx = lerp(x,0, self.logicalImageSize[0] - 1,self.data["x1"], self.data["x2"])
		ry = lerp(y,0, self.logicalImageSize[1] - 1,self.data["y2"], self.data["y1"])
		# print(f"px({x},{y})->wr({rx},{ry})")
		return (rx, ry)

	def worldToPixel(self, x, y):
		rx = lerp(x, self.data["x1"], self.data["x2"], 0, self.logicalImageSize[0] - 1)
		ry = lerp(y, self.data["y2"], self.data["y1"], 0, self.logicalImageSize[1] - 1)
		# print(f"wr({x},{y})->px({rx},{ry})")
		return (round(rx), round(ry))

	def _debugImage(self, img, text):
		if not DEBUG_IMAGE: return
		pyplot.subplot(5, 2, self._debugIdx)
		self._debugIdx += 1
		pyplot.axis('off')
		pyplot.imshow(img, 'gray')
		pyplot.title(text)

	def _pickBGColor(self, grayscale, colorImage):
		fallbackColor = (127, 127, 127, 255)

		brighterBits = colorImage[grayscale > 127]
		if len(brighterBits):
			color = np.median(brighterBits, axis=0)
		else:
			color = fallbackColor

		# This shouldn't be needed but I guess it is:
		color = (int(color[0]), int(color[1]), int(color[2]), int(color[3]))

		if sum(color[0:3]) < 127 * 3: color = fallbackColor

		return color

	def _paintTransitions(self):
		"""Paints color on the non-door transitions to help with visuals"""

		# self.pixelToWorld(0, 0)
		# self.pixelToWorld(self.logicalImageSize[0] - 1, self.logicalImageSize[1] - 1)
		# self.worldToPixel(self.data["x1"], self.data["y2"])
		# self.worldToPixel(self.data["x2"], self.data["y1"])

		for transition in self.data["transitions"]:
			x, y, w, h = transition["x"], transition["y"], transition["w"], transition["h"]
			if w * h <= 0: continue
			dir = transition["id"][:-1].split("[")[1][:-1] # "left" from "Crossroads_10[left1]"
			if dir not in ("top", "bottom", "left", "right"): continue

			x1, y1 = self.worldToPixel(x - w / 2, y + h / 2)
			x2, y2 = self.worldToPixel(x + w / 2, y - h / 2)

			match dir:
				case "top": y1 = 0
				case "bottom": y2 = self.image.shape[0] - 1
				case "left": x1 = 0
				case "right": x2 =  self.image.shape[1] - 1

			# try to find a good color
			color = self._pickBGColor(self.grayscale[y1:y2, x1:x2], self.image[y1:y2, x1:x2])

			# print(f"{transition['id']} going {dir} at {x, y, w, h} to paint in {x1, y1, x2, y2} with {color} maybe from {maxLoc}={maxVal}")
			cv.rectangle(self.image, (x1, y1), (x2, y2), color=color, thickness=cv.FILLED)


	def process(self):
		print(f"Looking at {self.tileName} image is {self.image.shape[1]}x{self.image.shape[0]}")

		# kill any existing alpha
		self.image[:, :, 3] = 255

		grayscale = self.grayscale = cv.cvtColor(self.image, cv.COLOR_RGB2GRAY)
		self._debugImage(grayscale, "grayscale")


		mask = cv.threshold(grayscale, 1, 255, cv.THRESH_BINARY)[1]
		self._debugImage(mask, "mask")

		# Figure out what parts we want to keep
		edgeKernel = np.ones((10, 10), np.uint8)
		mask = cv.dilate(mask, edgeKernel, iterations=20)

		contours, _ = cv.findContours(mask, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)

		# Fill gaps
		cv.fillPoly(mask, contours, (127,))
		# cv.drawContours(mask, contours, -1, (127,), cv.FILLED)

		self._debugImage(mask, "borders")

		# With the mask calculated, make some last-minute visual changes
		self._paintTransitions()
		self._debugImage(self.image, "postPaint")


		# Clear everything we're not keeping
		self.image[mask == 0] = (0, 0, 0, 0)

		# Debug show contours
		# cv.drawContours(self.image, contours, -1, (255, 0, 0, 255), 7)

		# Get bounding box
		# https://stackoverflow.com/a/53459825/710714
		bbs = []
		for cnt in contours:
			x, y, w, h = cv.boundingRect(cnt)
			bbs.append([x, y, x + w, y + h])
		if not len(bbs): bbs.append([0, 0, self.image.shape[1], self.image.shape[0]])
		bbs = np.asarray(bbs)
		left, top = np.min(bbs, axis=0)[:2]
		right, bottom = np.max(bbs, axis=0)[2:]
		# cv.rectangle(self.image, (left, top), (right, bottom), (0, 255, 0, 255), 2)

		# Crop and scale image
		print(f"Will crop from (0, 0):({self.image.shape[1]}, {self.image.shape[0]}) to ({left}, {top}):({right}, {bottom})")
		self.image = self.image[top:bottom, left:right]

		# Color space conversion (e.g. gamma sRGB <-> linear sRGB) in OpenCV is kinda a mess

		linear = cv.LUT(self.image, linearLUT)
		self._debugImage(linear, "linear")
		linear = cv.resize(
			linear,
			(self.image.shape[1] // 6, self.image.shape[0] // 6),
			interpolation=cv.INTER_AREA
		)

		self.image = cv.LUT(linear, gammaLUT)

		cv.imwrite(outputFolder + "/"  + self.tileName + ".webp", self.image)
		self._debugImage(self.image, "final")

		# Update image -> world mapping in metadata
		newCorners = (
			self.pixelToWorld(left, top),
			self.pixelToWorld(right, bottom),
		)
		((self.data["x1"], self.data["y2"]), (self.data["x2"], self.data["y1"])) = newCorners
		self.logicalImageSize = (self.image.shape[1], self.image.shape[0])

		with open(outputFolder + "/" + self.tileName + ".json", "wt") as f:
			json.dump(self.data, f, indent=2)

		if DEBUG_IMAGE:
			pyplot.show()



