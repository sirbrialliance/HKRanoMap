import glob
import os
import sys
from os.path import exists

import TileHandler

outputFolder = os.path.dirname(os.path.dirname(os.path.realpath(__file__))) + "/Mod/Resources/MapTiles"


def processData(tile: str):
	handler = TileHandler.TileHandler(tile)
	handler.process()

def getTileNames():
	# TileHandler.DEBUG_IMAGE = True
	# yield "Hive_04"
	# yield "Hive_05"
	# return


	for file in glob.glob("*.json"):
		tileName = file[:-5]

		if tileName == "MapData": continue
		if exists(outputFolder + "/" + tileName + ".webp"):
			continue

		yield tileName

if __name__ == "__main__":
	if len(sys.argv) <= 1:
		print("Usage: processData.py PATH_TO_DATA")
		sys.exit(1)

	os.chdir(sys.argv[1])

	for tile in sorted(getTileNames()):
		processData(tile)

