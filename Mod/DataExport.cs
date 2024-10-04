using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using ItemChanger;
using ItemChanger.Extensions;
using ItemChanger.Locations;
using ItemChanger.Locations.SpecialLocations;
using RandomizerMod.RandomizerData;
using UnityEngine;
using UnityEngine.SceneManagement;
using USceneManager = UnityEngine.SceneManagement.SceneManager;

namespace TangledMapView {
public class DataExport {
	public const string OutFolder = "MappingTiles";

	public static bool WantScene(string name) {
		if (string.IsNullOrEmpty(name)) return false;
		switch (name) {
			case "BetaEnd":
			case "Opening_Sequence":
			case "Beta":
			case "Pre_Menu_Intro":
			case "PermaDeath_Unlock":
			case "Quit_To_Menu":
			case "Dream_Room_Believer_Shrine":
			case "Dream_Backer_Shrine":
			case "PermaDeath":
			case "Menu_Title":
				return false;
			case "GG_Lurker":
			case "GG_Pipeway":
			case "GG_Waterways":
				return true;
		}

		name = name.ToLowerInvariant();
		if (name.StartsWith("_")) return false;
		if (name.StartsWith("cutscene")) return false;
		if (name.StartsWith("cinematic")) return false;
		if (name.StartsWith("end")) return false;
		if (name.StartsWith("menu")) return false;
		if (name.StartsWith("gg_")) return false;
		if (name.EndsWith("_preload")) return false;
		if (name.EndsWith("_boss")) return false;
		if (name.EndsWith("_boss_defeated")) return false;

		return true;
	}

	public static IEnumerable<string> GetAllScenes() {
		//Can't use UnitySceneManager to grab data, unloaded scenes don't have names.
		//Edit, but this method works:
		for (int i = 0; i < USceneManager.sceneCountInBuildSettings; i++) {
			var path = SceneUtility.GetScenePathByBuildIndex(i);
			var name = Path.GetFileNameWithoutExtension(path);
			yield return name;
		}

		//Old way: steal the list from ItemChanger.
		// var consts = typeof(ItemChanger.SceneNames).GetFields(BindingFlags.Public | BindingFlags.Static);
		// foreach (var fieldInfo in consts) {
		// 	if (fieldInfo.FieldType != typeof(string)) continue;
		// 	var name = fieldInfo.GetRawConstantValue() as string;
		// 	if (string.IsNullOrEmpty(name)) continue;
		// 	yield return name;
		// }
	}

	public static IEnumerable<string> GetGameScenes() {
		return GetAllScenes().Where(WantScene);
	}

	public static void ExportData() {
		var allRooms = new List<Room>();

		foreach (var sceneName in GetGameScenes()) {
			var json = File.ReadAllText($"{OutFolder}/{sceneName}.json");
			var roomData = JsonUtil.DeserializeString<Room>(json);
			allRooms.Add(roomData);
		}

		var allData = JsonUtil.Serialize(allRooms);
		File.WriteAllText($"{OutFolder}/MapData.json", allData);
	}


	public static Vector3 ByObject(string objectName) {
		var hasPath = false;
		if (objectName.Contains("\\") || objectName.Contains("/")) {
			objectName = objectName.Replace("\\", "/");
			hasPath = true;
		}

		var obj = GameObject.Find(objectName);
		if (obj) return obj.transform.position;

		//maybe it's disabled?
		if (!hasPath) {
			foreach (var go in GameObject.FindObjectsOfType<GameObject>(true)) {
				if (go.name == objectName) return go.transform.position;
			}
		} else {
			var parts = objectName.Split('/');
			if (parts.Length != 2) throw new ArgumentException("Unsupported path type");
			foreach (var go in GameObject.FindObjectsOfType<GameObject>(true)) {
				if (go.name == parts[1] && go.transform.parent && go.transform.parent.name == parts[0]) {
					return go.transform.position;
				}
			}
		}

		throw new Exception("Failed to find object " + objectName);
	}

	public static Vector3 ByFSM(FsmID id) {
		//this logic don't fully match ItemChanger.Events.FsmHook() (weakID/id/strongID), but should be good enough
		foreach (var fsm in GameObject.FindObjectsOfType<PlayMakerFSM>(true)) {
			if (fsm.FsmName != id.FsmName) continue;

			if (id.ObjectName != null && id.ObjectName.StartsWith("/")) {
				//strict path check
				if ("/" + fsm.transform.GetPathInHierarchy() != id.ObjectName) continue;
			} else if (!string.IsNullOrEmpty(id.ObjectName)) {
				//basic object name check
				if (id.ObjectName != fsm.name) continue;
			}


			return fsm.transform.position;
		}

		Debug.LogWarning("FSM Candidates: " + string.Join(", ", GameObject.FindObjectsOfType<PlayMakerFSM>().Select(x =>
			$"{x.name} -> {x.FsmName}"
		)));

		throw new Exception($"Failed to find anything to match FsmID \"{id}\"");
	}

	public static Vector3 ResolveLocation(AbstractLocation icLocation) {
		//Ugly "data fix" hacks:
		switch (icLocation.name) {
			case "Sly_(Key)": return ByObject("Sly Shop");
			case "Leg_Eater": return ByObject("Leg Eater");
		}


		//A million ways to grab data:
		if (icLocation is ObjectLocation ol) {
			return ByObject(ol.objectName);
		} else if (icLocation is CoordinateLocation cl) {
			return new Vector3(cl.x, cl.y, 0);
		} else if (icLocation is DualLocation dl) {
			return ResolveLocation(dl.trueLocation);
		} else if (icLocation is ExistingFsmContainerLocation efcl) {
			return ByFSM(new FsmID(efcl.objectName, efcl.fsmName));
		} else if (icLocation is ShopLocation sl) {
			return ByFSM(new FsmID(sl.objectName, sl.fsmName));
		} else if (icLocation is BossEssenceLocation bel) {
			return ByFSM(new FsmID(bel.objName, bel.fsmName));
		} else if (icLocation is EggShopLocation esl) {
			return ResolveLocation(esl.location);
		} else if (icLocation is WhisperingRootLocation wrl) {
			return GameObject.FindObjectOfType<DreamPlant>().transform.position;
		} else if (icLocation is CorniferLocation corn) {
			try {
				return ByObject(corn.objectName);
			} catch {
				return ByFSM(new FsmID("Cornifer Card", "FSM"));
			}
		} else if (icLocation is CostChestLocation ccl) {
			return ResolveLocation(ccl.chestLocation);
		}

		switch (icLocation.GetType().Name) {
			// case "ShadeSoulLocation": return ByFSM(new FsmID("Ruins Shaman", "Ruins Shaman"));
			// case "GrimmkinLocation": return ByObject("Flamebearer Spawn");//return ByFSM(new FsmID("Flamebearer Spawn", "Spawn Control"));

			case "DescendingDarkLocation":
			case "DivineLocation":
			case "NailmasterLocation":
			case "EnemyLocation":
			case "SealOfBindingLocation": {
				//has an "objectName" property
				var objNameField = icLocation.GetType().GetField("objectName", BindingFlags.Public | BindingFlags.Instance);
				return ByObject((string)objNameField.GetValue(icLocation));
			}
			case "AbyssShriekLocation": return ByFSM(new FsmID("Scream 2 Get", "Scream Get"));
			case "BrummFlameLocation": return ByFSM(new FsmID("Brumm Torch NPC", "Conversation Control"));
			case "GrimmkinLocation": return ByFSM(new FsmID("Flamebearer Spawn", "Spawn Control"));
			case "GruzMotherDropLocation": return ByObject("Corpse Big Fly Burster");
			case "NailmastersGloryLocation": return ByFSM(new FsmID("Sly Basement NPC", "Conversation Control"));
			case "ShadeCloakLocation": return ByFSM(new FsmID("Dish Plat", "Get Shadow Dash"));
			case "ShadeSoulLocation": return ByFSM(new FsmID("Ruins Shaman", "Ruins Shaman"));
			case "TukDefendersCrestLocation": return ByObject("Alive_Tuk");
			case "VoidHeartLocation": return ByFSM(new FsmID("End Cutscene", "Control"));
		}

		throw new Exception($"Don't know how to find location of type {icLocation.GetType().FullName} for {icLocation.name}");
	}



	/// <summary>
	/// Given that the location's scene is loaded, fills our fields with the appropriate
	/// info.
	/// </summary>
	public static RoomItemLocation RoomFrom(AbstractLocation icLocation) {
		try {
			var ret = new RoomItemLocation {id = icLocation.name};
			ret.Position = ResolveLocation(icLocation);
			//make sure everything is on the z plane:
			ret.z = 0;

			return ret;
		} catch (Exception ex) {
			Debug.LogException(ex);
			Debug.LogError($"Failed to locate {icLocation.name} in {icLocation.sceneName} ({icLocation.GetType().FullName})");
			var ret = new RoomItemLocation {id = icLocation.name};
			ret.Position = new Vector3(-100, -100, -100);
			return ret;
		}
	}
}
}
