using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using ItemChanger;
using Modding;
using Modding.Converters;
using RandomizerMod.RandomizerData;
using UnityEngine;
using UnityEngine.SceneManagement;
using USceneManager = UnityEngine.SceneManagement.SceneManager;

namespace TangledMapView {


/// <summary>
/// Helper camera for rendering out views of scenes for use in maps.
/// </summary>
public class MappingCamera : MonoBehaviour {
	/// <summary>
	/// GameObject layer we use for our purposes.
	/// </summary>
	public const int Layer = 6;
	/// <summary>
	/// How world size is scaled to pixel size in exported tiles.
	/// Bigger numbers=higher resolution tiles.
	/// </summary>
	public const float MapTileScale = 20f;
	public const float LiveViewZoom = 100;

	public static MappingCamera Create(TangledMapViewMod mod) {
		mod.LogDebug("Creating MappingCamera");

		Display.displays[1].Activate();
		Display.displays[1].SetParams(1920, 1080, 0, 0);

		var go = new GameObject("MappingCamera");
		DontDestroyOnLoad(go);
		var ret = go.AddComponent<MappingCamera>();
		ret.mod = mod;
		var cam = ret.camera = go.AddComponent<Camera>();

		cam.targetDisplay = 1;
		cam.clearFlags = CameraClearFlags.Color;
		cam.backgroundColor = new Color(0, 0, 0);
		cam.orthographic = true;
		cam.orthographicSize = LiveViewZoom;
		cam.nearClipPlane = -1;
		cam.farClipPlane = 1000;

		/** HK Layers:
			0 -> Default
			1 -> TransparentFX
			2 -> Ignore Raycast
			4 -> Water
			5 -> UI
			6 -> [Hijacked for this camera]
			8 -> Terrain
			9 -> Player
			10 -> TransitionGates
			11 -> Enemies
			12 -> Projectiles
			13 -> Hero Detector
			14 -> Terrain Detector
			15 -> Enemy Detector
			16 -> Tinker
			17 -> Attack
			18 -> Particle
			19 -> Interactive Object
			20 -> Hero Box
			21 -> Grass
			22 -> Enemy Attack
			23 -> Damage All
			24 -> Bouncer
			25 -> Soft Terrain
			26 -> Corpse
			27 -> uGUI
			28 -> Hero Only
			29 -> ActiveRegion
			30 -> Map Pin
			31 -> Orbit Shield
		*/
		// cam.cullingMask = (1 << 0) | (1 << 4) | (1 << Layer) | (1 << 8) | (1 << 21);
		cam.cullingMask = ~(1 << 9);


		//Make a "backplane" to make it easier to see terrain and stuff
		var back = ret.backplane = GameObject.CreatePrimitive(PrimitiveType.Quad);
		back.name = "Backplane";
		back.transform.SetParent(ret.transform);
		back.transform.localPosition = new Vector3(0, 0, .5f);
		back.transform.localScale = new Vector3(10000, 10000, 10000);
		back.layer = Layer;

		var bren = back.GetComponent<Renderer>();
		bren.material = new Material(Shader.Find("Sprites/Default-ColorFlash"));
		bren.material.color = new Color(.5f, .5f, .5f, .7f);

		if (Camera.main) {
			Camera.main.cullingMask &= ~(1 << Layer);
		}

		return ret;
	}


	public Camera camera;
	private HeroController _hero;
	private List<SpriteRenderer> heroLights = new List<SpriteRenderer>();
	private TangledMapViewMod mod;
	private GameObject backplane;
	private Bounds currentBorders;
	private bool doingGrandTour = false;

	public HeroController Hero {
		get {
			//use FindObjectOfType instead of aHeroController.instance so no logspam when not present
			if (!_hero) _hero = FindObjectOfType<HeroController>();
			return _hero;
		}
	}


	public void OnEnable() {
		// ModHooks.SceneChanged += SceneChanged;//useless, not called
		USceneManager.activeSceneChanged += SceneChanged;
		ModHooks.DrawBlackBordersHook += OnDrawBorders;

		Directory.CreateDirectory(DataExport.OutFolder);
	}


	public void OnDisable() {
		// ModHooks.SceneChanged -= SceneChanged;
		USceneManager.activeSceneChanged -= SceneChanged;
		ModHooks.DrawBlackBordersHook -= OnDrawBorders;
	}

	private void OnDrawBorders(List<GameObject> borders) {
		if (borders.Count == 0) {
			currentBorders = new Bounds();
			return;
		}

		currentBorders = new Bounds(borders[0].transform.position, Vector3.zero);
		foreach (var obj in borders) {
			currentBorders.Encapsulate(obj.transform.position);
		}

		// mod.Log($"New scene borders: {currentBorders}");
	}

	private void SceneChanged(Scene prev, Scene current) {
		if (!doingGrandTour) {
			mod.Log($"Switch from {prev.name} to {current.name}");
			StartCoroutine(SnapScene());
		}
	}

	private IEnumerator CleanupView() {
		if (!Hero) yield break;

		// mod.Log($"CleanupView state: {Hero.transitionState} and isT {Hero.cState.transitioning}");

		while (Hero.cState.transitioning) {
			yield return null;
		}

		yield return null;
		yield return null;
		yield return null;

		//Thanks to DebugMod for showing us what needs to happen.
		Hero.vignette.enabled = false;

		heroLights.Clear();
		heroLights.Add(Hero.transform.Find("HeroLight").GetComponent<SpriteRenderer>());
		heroLights.Add(Hero.transform.Find("white_light_donut").GetComponent<SpriteRenderer>());

		//deactivate visual masks
		foreach (var renderer in FindObjectsOfType<Renderer>()) {
			var name = renderer.gameObject.name;
			if (
				name.StartsWith("msk_") || name.StartsWith("Tut_msk") ||
				name.StartsWith("black_solid") ||
				name.ToLower().Contains("vignette")
			) {
				renderer.enabled = false;
			}
		}

		foreach (var fsm in FindObjectsOfType<PlayMakerFSM>()) {
			if (fsm.FsmName == "unmasker" || fsm.FsmName == "remasker_inverse" || fsm.FsmName == "remasker") {
				foreach (var renderer in fsm.gameObject.GetComponentsInChildren<Renderer>()) {
					renderer.enabled = false;
				}
			}
		}
	}

	private string SceneName => USceneManager.GetActiveScene().name;

	private IEnumerator SnapScene() {
		yield return StartCoroutine(CleanupView());

		var aspect = currentBorders.size.x / currentBorders.size.y;
		var width = Mathf.RoundToInt(currentBorders.size.x * MapTileScale);
		var height = Mathf.RoundToInt(currentBorders.size.y * MapTileScale);

		if (width <= 0 || height <= 0) {
			mod.LogError($"Current scene has no size");
			yield break;
		}

		//Camera setup
		//Doing the extra RT dance is annoying, but it does let us render things larger than the screen when needed.
		var buf = new RenderTexture(width, height, 24);
		buf.antiAliasing = 16;
		camera.transform.position = currentBorders.center;
		//"orthographicSize is half the size of the vertical viewing volume"
		camera.orthographicSize = currentBorders.size.y / 2f;


		//Render to buffer, pull image
		var tex = new Texture2D(width, height, TextureFormat.RGBA32, false);
		camera.targetTexture = buf;
		RenderTexture.active = buf;

		camera.Render();
		tex.ReadPixels(new Rect(0, 0, width, height), 0, 0, true);
		tex.Apply();

		//Encode
		var data = tex.EncodeToPNG();

		//Cleanup
		camera.targetTexture = null;
		RenderTexture.active = null;
		Destroy(tex);
		Destroy(buf);
		camera.orthographicSize = LiveViewZoom;

		var roomData = GetRoomData();
		var dataFileName = $"{DataExport.OutFolder}/{SceneName}.json";
		File.WriteAllText(dataFileName, JsonUtil.Serialize(roomData));

		//Write
		var imgFileName = $"{DataExport.OutFolder}/{SceneName}.png";
		File.WriteAllBytes(imgFileName, data);
		mod.Log($"Wrote {imgFileName}");
	}

	private Room GetRoomData() {
		var sceneName = SceneName;
		var ret = new Room {
			id = sceneName,
			x1 = currentBorders.min.x,
			y1 = currentBorders.min.y,
			x2 = currentBorders.max.x,
			y2 = currentBorders.max.y,
		};

		var placements = Finder.GetFullLocationList().Where(kvp => kvp.Value.sceneName == sceneName);
		foreach (var kvp in placements) {
			ret.locations.Add(DataExport.RoomFrom(kvp.Value));
		}

		var transitions = Data.Transitions.Where(kvp => kvp.Value.SceneName == sceneName);
		var tObjects = FindObjectsOfType<TransitionPoint>(true);
		foreach (var kvp in transitions) {
			var randoTransition = kvp.Value;
			var sceneObject = tObjects
				.FirstOrDefault(x => x.name == randoTransition.DoorName)
			;

			if (!sceneObject) {
				Debug.LogWarning("Doors we have: " + string.Join(", ", tObjects.Select(x =>
					$"{x.name} - {x.entryPoint} - {x.targetScene}"
				)));
				Debug.LogWarning($"Objects w/ name? {GameObject.Find(randoTransition.Name)}");
				throw new Exception($"Can't find door for {randoTransition.Name}");
			}

			ret.transitions.Add(new RoomTransition {
				id = randoTransition.Name,
				srcDoor = randoTransition.DoorName,
				Position = sceneObject.transform.position,
				destDoor = randoTransition.VanillaTarget,
			});
		}

		return ret;
	}

	public void LateUpdate() {
		if (!Hero) return;

		transform.position = Hero.transform.position;

		foreach (var light in heroLights) {
			if (light) light.color = new Color(1, 1, 1, 0);
		}

		if (Input.GetKeyDown(KeyCode.F11) && Input.GetKey(KeyCode.LeftControl) && Input.GetKey(KeyCode.LeftShift)) {
			StartCoroutine(DoGrandTour());
		}

		if (Input.GetKeyDown(KeyCode.F9)) {
			foreach (var renderer in Hero.GetComponentsInChildren<Renderer>()) {
				var path = "";
				var p = renderer.transform;
				while (p != Hero.transform) {
					path += p.name + "<-";
					p = p.parent;
				}
				Debug.Log($"Renderer: {path} it's a {renderer.GetType().FullName}");
			}
		}
	}


	private IEnumerator DoGrandTour() {
		doingGrandTour = true;

		foreach (var name in DataExport.GetGameScenes()) {
			if (File.Exists($"{DataExport.OutFolder}/{name}.png")) continue;

			mod.Log($"Load scene for image grab: {name}");
			USceneManager.LoadScene(name, LoadSceneMode.Single);

			yield return StartCoroutine(SnapScene());
			yield return new WaitForSeconds(.1f);

			if (Input.anyKey) break;
		}

		mod.Log("Ended the grand tour!");

		DataExport.ExportData();

		mod.Log("Exported data");
		doingGrandTour = false;
	}

}
}
