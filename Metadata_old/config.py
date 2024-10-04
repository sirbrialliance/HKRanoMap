"""
Grab the things mentioned below and update the paths/data as appropriate.

You may need to `pip install pyyaml`
"""

"""
You'll need the .unity scenes. Use https://github.com/AssetRipper/AssetRipper
	Some outdated docs: https://web.archive.org/web/20210908035016/https://radiance.host/apidocs/EditScene.html
Fill out the path to the .unity scenes below:
"""
scenesPath = "C:/Program Files (x86)/Steam/steamapps/common/Hollow Knight/hollow_knight_ripped_1.5_Data/hollow_knight/ExportedProject/Assets/Scenes"

"""
We need to parse these scenes for data:
	For the scripts in {scenesPath}../../Scripts/Assembly-CSharp/
	Open the .cs.meta file and grab the "guid" field
Note that this is probably different every time you run AssetRipper
"""
# TransitionPoint.cs.meta:
doorTypeGUID = "eedb8600b30f6c446b198071ed76c169"
# RestBench.cs.meta:
benchTypeGUID = "cd5a899bce5670943a0660421ba15c7a"

"""
You'll need the relevant Randomizer sources:
	git clone https://github.com/homothetyhk/RandomizerMod
	git clone https://github.com/homothetyhk/HollowKnight.ItemChanger
"""
randomizerSourcePath = "C:/bin/GameModding/RandomizerMod"
itemRandomizerSourcePath = "C:/bin/GameModding/HollowKnight.ItemChanger"

