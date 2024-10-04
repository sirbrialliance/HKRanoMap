import math
import json
import yaml # pip install pyyaml

import config

# See roomMeta.yaml
metaData = None
roomData = None

def getRoom(roomId):
	if roomId not in roomData or roomData[roomId] is None:
		data = roomData[roomId] = {}
	else:
		data = roomData[roomId]

	if "items" not in data: data["items"] = {}
	if "transitions" not in data: data["transitions"] = {}
	if "area" not in data:
		# usually the name before the first underscore, unless the area has an underscore in it or has none
		if roomId.startswith("White_Palace"): data["area"] = "White_Palace"
		elif roomId.startswith("Deepnest_East"): data["area"] = "Deepnest_East"
		elif roomId == "Town": data["area"] = "Town"
		else: data["area"] = roomId.split("_")[0]
	if "benches" not in data: data["benches"] = []

	return data


def loadData():
	global metaData, roomData
	with open("roomMeta.yaml", "rb") as f:
		metaData = yaml.load(f, yaml.SafeLoader)

	roomData = metaData['rooms']

	# print(repr(roomData))

	# for roomId, data in roomData.items():
	# 	if data is None: roomData[roomId] = data = {}
	# 	if "items" not in data: data["items"] = []
	# 	if "transitions" not in data: data["transitions"] = {}

	loadRandomizerData()
	print("Loaded room info")
	# print(repr(roomData["Room_Bretta"]))
	# print(repr(metaData))


randomizerData = {}

def loadRandomizerData():
	dataPath = config.randomizerSourcePath + "/RandomizerMod/Resources/Data/"

	global randomizerData

	for id in ['rooms', 'transitions', 'locations']:
		with open(dataPath + id + ".json", "rt") as f:
			randomizerData[id] = json.load(f)

	with open(config.itemRandomizerSourcePath + "/ItemChanger/Resources/locations.json", "rt") as f:
		randomizerData["sceneLocations"] = json.load(f)


	# Note what area the randomizer considers each room to be in.
	for roomId, data in randomizerData['rooms'].items():
		room = getRoom(roomId)
		room["randomizerArea"] = data["MapArea"]
		room["randomizerTitleArea"] = data["TitledArea"]

	# note what items/checks are in each room and info about them
	# If we have to look up the location of an object in the scene we'll do that later.
	for locId, data in randomizerData['locations'].items():
		if locId == "Start": continue
		if locId == "Salubra_(Requires_Charms)": continue # same place as normal Salubra

		# These don't have actual locations in a scene (do they?)
		if locId in ["Leftslash", "Rightslash", "Upslash", ]: continue

		try:
			roomId = data['SceneName']
			items = getRoom(roomId)["items"]

			locData = randomizerData["sceneLocations"][locId]

			itemInfo = {'id': locId}

			# Dig into relevant detail for certain item types:
			if "chestLocation" in locData: locData = locData["chestLocation"]
			elif "location" in locData: locData = locData["location"]
			elif "trueLocation" in locData: locData = locData["trueLocation"]

			if "objectName" in locData:
				itemInfo['objectName'] = locData['objectName']
			elif "objName" in locData:
				itemInfo['objectName'] = locData['objName']
			elif "x" in locData:
				itemInfo = {
					'x': float(locData['x']),
					'y': float(locData['y']),
				}
			elif locData["$type"] == "ItemChanger.Locations.SpecialLocations.WhisperingRootLocation, ItemChanger":
				itemInfo['objectName'] = "__whisperingRoot__"
			elif locData["$type"] == "ItemChanger.Locations.SpecialLocations.GrimmkinLocation, ItemChanger":
				itemInfo['objectName'] = "__grimmkin__"
			# Special items without embedded hints. To get info, you Look up the
			# class (e.g. ShadeCloakLocation) and find the object named.
			elif locId == "Shade_Cloak": itemInfo['objectName'] = "Dish Plat"
			elif locId == "Shade_Soul": itemInfo['objectName'] = "Ruins Shaman"
			elif locId == "Abyss_Shriek": itemInfo['objectName'] = "Scream 2 Get"
			elif locId == "Nailmaster's_Glory": itemInfo['objectName'] = "Sly Basement NPC"
			elif locId == "Void_Heart": itemInfo['objectName'] = "__todo__" # put the location on the black sphere you hit
			elif locId == "Rancid_Egg-Tuk_Defender's_Crest": itemInfo['objectName'] = "Tuk NPC"
			elif locId == "Grimmkin_Flame-Brumm": itemInfo['objectName'] = "Brumm Torch NPC"
			else:
				raise Exception("No scene location data")

			# itemInfo['randType'] = prop(item, "type")
			# itemInfo['randAction'] = prop(item, "action")
			# itemInfo['randPool'] = prop(item, "pool")
			items[locId] = itemInfo
		except:
			print(f"Issue handling {locId}\n{repr(data)}\n{repr(locData)}")
			raise

def finishData():
	buildStagTransitions()

	# merge items from certain rooms to other rooms
	for roomId, room in roomData.copy().items():
		targetRoomId = None
		if roomId.endswith("_boss"): targetRoomId = roomId[:-5]
		if roomId.endswith("_boss_defeated"): targetRoomId = roomId[:-14]
		if roomId == "Dream_Nailcollection": targetRoomId = "__orphans__"

		if not targetRoomId: continue


		# merge to new room
		targetRoom = getRoom(targetRoomId)
		if "items" not in room: continue
		if "items" not in targetRoom: continue

		print("Forward data from", roomId, "to", targetRoomId)
		# print("----", roomId, "going to", targetRoomId)
		# print(repr(room), repr(targetRoom))

		targetRoom["items"].update(room["items"])

		del roomData[roomId]


def buildStagTransitions():
	stagHub = getRoom("Cinematic_Stag_travel")
	stagRooms = []
	for roomId, room in roomData.items():
		if "stag" not in room: continue
		stagRooms.append(roomId)

	stagRooms.sort()

	radius = 15
	for i in range(len(stagRooms)):
		angle = i / len(stagRooms) * 2 * math.pi
		roomId = stagRooms[i]
		room = getRoom(roomId)

		doorName = "stag_" + room["stag"]

		if "door_stagExit" not in room["transitions"]:
			print(f"Missing door_stagExit in {roomId}", repr(room["transitions"]))
			continue

		stagDoor = room["transitions"]["door_stagExit"]
		stagDoor["to"] = "Cinematic_Stag_travel[" + doorName + "]"

		stagHub["transitions"][doorName] = {
			"x": math.cos(angle) * radius,
			"y": math.sin(angle) * radius,
			"to": roomId + "[door_stagExit]",
		}


def markOneWayDoors():
	for id, data in randomizerData['transitions'].items():
		if data['Sides'] == "Both": continue # not one-way

		roomId = data['SceneName']
		doorName = data['DoorName']

		room = getRoom(roomId)
		if doorName not in room["transitions"]:
			print("One-way: No " + doorName + " on " + roomId)
			return
		room["transitions"][doorName]["to"] = None


