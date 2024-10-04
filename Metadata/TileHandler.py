import json

import cv2 as cv # apt install python3-opencv
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

linearLUT = np.asarray([gammaToLinear(v / 255) * 255 for v in range(0, 256)], dtype=np.uint8)
gammaLUT = np.asarray([linearToGamma(v / 255) * 255 for v in range(0, 256)], dtype=np.uint8)

class TileHandler:
	image: np.ndarray
	_debugIdx = 1

	def __init__(self, tileName):
		super().__init__()
		self.tileName = tileName

		self.image = cv.imread(tileName + ".png", cv.IMREAD_UNCHANGED)
		if self.image is None: raise FileNotFoundError(f"Failed to read image {tileName}.png")

		with open(tileName + ".json", "r") as f:
			self.data = json.load(f)

		if DEBUG_IMAGE: pyplot.figure(dpi=240)


	def _debugImage(self, img, text):
		if not DEBUG_IMAGE: return
		pyplot.subplot(1, 5, self._debugIdx)
		self._debugIdx += 1
		pyplot.axis('off')
		pyplot.imshow(img, 'gray')
		pyplot.title(text)

	def process(self):
		print(f"Looking at {self.tileName} image is {self.image.shape}")

		origWidth = self.image.shape[1]
		origHeight = self.image.shape[0]

		# kill any existing alpha
		self.image[:, :, 3] = 255

		grayscale = cv.cvtColor(self.image, cv.COLOR_RGB2GRAY)
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
		self.data["x1"], self.data["x2"] = np.interp(
			(left, right),
			(0, origWidth),
			(self.data["x1"], self.data["x2"]),
		)
		self.data["y1"], self.data["y2"] = np.interp(
			(top, bottom),
			(0, origHeight),
			(self.data["y1"], self.data["y2"]),
		)

		with open(outputFolder + "/" + self.tileName + ".json", "wt") as f:
			json.dump(self.data, f, indent=2)

		if DEBUG_IMAGE: pyplot.show()



