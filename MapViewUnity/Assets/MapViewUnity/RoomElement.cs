using Newtonsoft.Json;
using UnityEngine;

namespace TangledMapView {

/// <summary>
/// Something that's located in a room and has a position.
/// </summary>
public class RoomElement {
	public string id;

	/// <summary>
	/// Position in room.
	/// </summary>
	public float x, y, z;
	/// <summary>
	/// Bounding box width/height/depth for item.
	/// May be zero.
	/// </summary>
	public float w, h, d;

	[JsonIgnore]
	public Vector3 Position {
		get => new Vector3(x, y, z);
		set {
			x = value.x;
			y = value.y;
			z = value.z;
		}
	}

	[JsonIgnore]
	public Vector3 Size {
		get => new Vector3(w, h, d);
		set {
			w = value.x;
			h = value.y;
			d = value.z;
		}
	}
}

}
