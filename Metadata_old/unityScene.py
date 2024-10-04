import yaml # pip install pyyaml
import io, re

import config

class Loader(yaml.SafeLoader):
	def load104(self, node):
		return self.construct_object(node)

Loader.add_constructor("tag:unity3d.com,2011:104", Loader.load104)
yaml.parser.Parser.DEFAULT_TAGS[u'!u!'] = u'tag:unity3d.com,2011:'

def loadYAML(stringData):
	data = yaml.parse(stringData)
	i = iter(data)
	token = next(i)
	def consume(type = None):
		nonlocal token
		# print("Consume " + repr(token))
		ret = token
		if type is not None and not isinstance(token, type): raise ValueError("Wrong type, wanted " + str(type) + " but got " + str(token))
		token = next(i)
		return ret

	def nextIs(type):
		return isinstance(token, type)

	def burnValue():
		if nextIs(yaml.MappingStartEvent):
			consume()
			while True:
				if nextIs(yaml.MappingStartEvent): burnValue()
				elif nextIs(yaml.MappingEndEvent): break
				else: consume()
			consume(yaml.MappingEndEvent)
		elif nextIs(yaml.SequenceStartEvent):
			consume()
			while True:
				if nextIs(yaml.SequenceStartEvent): burnValue()
				elif nextIs(yaml.SequenceEndEvent): break
				else: consume()
			consume(yaml.SequenceEndEvent)
		else: consume(yaml.ScalarEvent)


	def readObject():
		if nextIs(yaml.ScalarEvent):
			return consume().value
		elif nextIs(yaml.SequenceStartEvent):
			ret = []
			consume(yaml.SequenceStartEvent)
			while not nextIs(yaml.SequenceEndEvent): ret.append(readObject())
			consume(yaml.SequenceEndEvent)
			return ret

		consume(yaml.MappingStartEvent)
		ret = {}
		while nextIs(yaml.ScalarEvent):
			k = consume(yaml.ScalarEvent).value
			v = readObject()
			ret[k] = v

		consume(yaml.MappingEndEvent)
		return ret


	consume(yaml.StreamStartEvent)

	objects = {}

	keyWhitelist = set((
		"m_Component", "m_LocalPosition", "m_Name", "m_Script", "m_GameObject", "m_Father", "m_LocalScale",
		"targetScene", "entryPoint",
	))

	while nextIs(yaml.DocumentStartEvent):
		consume()
		_ = consume(yaml.MappingStartEvent)
		id = _.anchor

		_ = consume(yaml.ScalarEvent)
		type = _.value

		object = {"type": type}

		#props
		consume(yaml.MappingStartEvent)
		while nextIs(yaml.ScalarEvent):
			k = consume(yaml.ScalarEvent).value
			if k in keyWhitelist:
				v = readObject()
			else:
				burnValue()
				continue
			object[k] = v
		consume(yaml.MappingEndEvent) # props

		consume(yaml.MappingEndEvent) # object start

		objects[id] = object

		consume(yaml.DocumentEndEvent)
		# print("---")

	# print(repr(objects))
	return objects

class SceneHandler:
	def __init__(self):
		self.roomId = None

	def loadFile(self, name, path):
		# print("Read " + name)

		idMatch = re.compile(b"^\d+\s+&(\d+)")
		nameMatch = re.compile(b"^\s+m_Name: (.*)$", re.M)

		self.roomId = name
		with open(path, "rb") as f:
			self.rawSceneData = f.read()

		scriptGUIDs = (
			config.doorTypeGUID.encode(),
			config.benchTypeGUID.encode(),
		)

		# instead of parsing the whole YAML document (really slow with our parser)
		# do some string manipulation to get the individual sections and note things for later
		# We'll parse things when we actually need the real data.
		self.objects = {}
		self.sceneObjectStrings = {}
		self.namesToObjectIds = {}
		self.interestingObjectIds = set()
		for segment in self.rawSceneData.split(b"--- !u!")[1:]:
			objId = idMatch.match(segment).group(1).decode()
			self.sceneObjectStrings[objId] = segment

			if segment.startswith(b"1 "): # GameObject
				match = nameMatch.search(segment)
				if match is None:
					print("No name match on", segment.decode('utf-8'))
				name = match.group(1).decode()

				idsWithName = self.namesToObjectIds.setdefault(name, [])
				idsWithName.append(objId)

			if segment.startswith(b"114 "): # MonoBehaviour
				for guid in scriptGUIDs:
					if guid in segment:
							self.interestingObjectIds.add(objId)

		# print("FYI, scene names->ids: " + repr(self.namesToObjectIds))


	def getObject(self, id):
		if id in self.objects: return self.objects[id]

		data = loadYAML(b"--- !u!" + self.sceneObjectStrings[id])
		# unwrap
		ret = self.objects[id] = data[id]
		return ret

	def getGameObject(self, component):
		return self.getObject(component["m_GameObject"]["fileID"])

	def getComponent(self, gameObject, type):
		for comp in gameObject["m_Component"]:
			compObj = self.getObject(comp["component"]["fileID"])
			if compObj["type"] == type: return compObj
		raise ValueError("Found no " + type + " on " + str(gameObject))

	def getTransformParent(self, transform):
		father = transform["m_Father"]["fileID"]
		if father != '0': return self.getObject(father)
		else: return None

	def getGOParent(self, go):
		transform = self.getComponent(go, "Transform")
		parent = self.getTransformParent(transform)
		if parent: return self.getGameObject(parent)
		else: return None

	def getPosition(self, gameObject):
		if not gameObject: raise ValueError("missing GameObject")
		transform = self.getComponent(gameObject, "Transform")

		# print("Pos is " + repr(transform["m_LocalPosition"]))
		x = float(transform["m_LocalPosition"]["x"])
		y = float(transform["m_LocalPosition"]["y"])
		parent = self.getTransformParent(transform)
		while parent:
			# print("has a parent! " + repr(transform["m_LocalPosition"]) + " scale " + repr(transform["m_LocalScale"]))
			x *= float(parent["m_LocalScale"]["x"])
			y *= float(parent["m_LocalScale"]["y"])
			x += float(parent["m_LocalPosition"]["x"])
			y += float(parent["m_LocalPosition"]["y"])
			parent = self.getTransformParent(parent)

		return (x, y)

	def _addDoors(self, roomData):
		doors = roomData["transitions"]
		for id in self.interestingObjectIds:
			object = self.getObject(id)
			# print("obj is", repr(object))
			if object["type"] != "MonoBehaviour": continue
			if object["m_Script"]["guid"] != config.doorTypeGUID: continue
			# print("Found a door on " + id)

			go = self.getGameObject(object)


			doorSide = go["m_Name"]
			targetRoomId = object['targetScene']
			targetSide = object['entryPoint']

			if doorSide in doors: continue # custom changes in roomMeta.yaml

			if doorSide == "left1 extra": continue #oddball door we don't want (it's a copy anyway)
			if " (" in doorSide: continue # "left1 (1)", etc
			if targetRoomId == "bot1" and targetSide == "Town": continue # go home Crossroads_01, you're drunk

			# probably all the non-case mismatches are unused and could be deleted:
			if targetRoomId == "Deepnest_east_07": targetRoomId = "Deepnest_East_07"
			if targetRoomId == "Room_Fung_Shaman": targetRoomId = "Room_Fungus_Shaman"
			if targetRoomId == "Room_Final_Boss_atrium": targetRoomId = "Room_Final_Boss_Atrium"
			if targetRoomId == "Room_nailmsith": targetRoomId = "Room_nailsmith"
			if targetRoomId == "Grimm_Tent": targetRoomId = "Grimm_Main_Tent"


			if not targetRoomId or not targetSide or targetRoomId == "0.":
				targetDoorId = None
			else:
				targetDoorId = f"{targetRoomId}[{targetSide}]"

			x, y = self.getPosition(go)
			doors[doorSide] = {"x": x, "y": y, "to": targetDoorId}

	def _addItems(self, roomData):
		for itemId, item in roomData["items"].items():
			if 'x' in item: continue

			if "objectName" not in item or not item['objectName']:
				print(f"{itemId} has no object location - {repr(item)}")
				continue

			# try to find the object's position
			nameParts = item['objectName'].split("\\")
			objName = nameParts[-1]

			if objName not in self.namesToObjectIds:
				print(f"There's no {objName} in {self.roomId} - location {itemId} - {repr(item)}")
				continue
				# raise Exception(f"There's no {objName} in {self.roomId} - location {itemId} - {repr(item)}")

			possibleIds = self.namesToObjectIds[objName]

			if itemId == "Charm_Notch-Shrumal_Ogres":
				# There's two objects that match we'll...umm...just pick the first one
				go = self.getObject(possibleIds[0])
			elif len(possibleIds) > 1:
				# Find based on parent's name too
				parentName = nameParts[-2] if len(nameParts) >= 2 else None
				# print("Object " + itemId + " targets " + item['objectName'] + " and could be", repr(possibleIds), "parent name is", parentName)

				go = None
				for id in possibleIds:
					if go: break

					candidate = self.getObject(id)
					candidateParent = self.getGOParent(candidate)

					# print("Candidate parent is", repr(candidateParent))

					if candidateParent is None and parentName is None:
						go = candidate
						break
					elif candidateParent:
						if candidateParent['m_Name'] == parentName:
							go = candidate
							break
				if not go: raise ValueError("Could not determine which object to use")
			else:
				go = self.getObject(possibleIds[0])

			# print("Using this for object:", repr(go))

			x, y = self.getPosition(go)
			item["x"] = x
			item["y"] = y
			del item['objectName']

	def _addBenches(self, roomData):
		benches = roomData["benches"]
		for id in self.interestingObjectIds:
			object = self.getObject(id)
			if object["type"] != "MonoBehaviour": continue
			if object["m_Script"]["guid"] != config.benchTypeGUID: continue

			go = self.getGameObject(object)

			x, y = self.getPosition(go)
			benches.append({"x": x, "y": y})


	def addInfo(self, roomData):
		self._addDoors(roomData)
		self._addItems(roomData)
		self._addBenches(roomData)



		# if len(doors):
		# 	print("  Doors: " + repr(doors))

		# print(sceneData.entries)
		# print(sceneData.dump_yaml())
		# doors = sceneData.filter(class_names=("MonoBehaviour",), attributes=("isADoor",))
		# print(repr(sceneData))

		# doors = []
		# for doc in sceneData:
		# 	print(repr(doc.value))
		# 	if "MonoBehaviour" not in doc.value: continue
		# 	if "isADoor" not in doc['MonoBehaviour']: continue
		# 	doors.append(doc)
		# if not len(doors): return

		# print("Has " + str(len(doors)) + " doors")


