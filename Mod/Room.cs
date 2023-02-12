﻿using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using RandomizerMod.RandomizerData;
using UnityEngine;

namespace TangledMapView {
public class Room {
	public string id;
		//, name;
	// public string area, randomizerArea;
	// public List<string> benches;
	/// <summary>
	/// List of items or "checks" that are in this room,
	/// typically named by what is normally there.
	/// </summary>
	public List<RoomLocation> locations = new List<RoomLocation>();
	/// <summary>
	/// Room can't be fully accessed from any entrance.
	/// List of entrances that can be accessed together.
	/// </summary>
	// public string[][] splitRoom;

	/// <summary>
	/// Transitions leaving this room.
	/// </summary>
	public List<RoomTransition> transitions = new List<RoomTransition>();

	/// <summary>
	/// World-space coordinates for the corners of our thumbnail image.
	/// </summary>
	public float x1, y1, x2, y2;

	static Dictionary<string, Room> rooms;
	static Room() {
		try {
			var assembly = typeof(TangledMapViewMod).Assembly;
			using var resourceStream = assembly.GetManifestResourceStream("TangledMapView.Resources.MapData.json");
			using var sr = new StreamReader(resourceStream);
			var json = sr.ReadToEnd();

			var roomsList = JsonUtil.DeserializeString<List<Room>>(json);
			rooms = roomsList.ToDictionary(x => x.id, x => x);
		} catch (Exception ex) {
			Debug.LogException(ex);
			rooms = new Dictionary<string, Room>();
		}
	}

	public static Room Get(string name) {
		rooms.TryGetValue(name, out var ret);
		return ret;
	}
}


}
