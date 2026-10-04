
namespace Ants {

public struct Point {
	public int x, y;

	public Point (int x, int y) {
		this.x = x;
		this.y = y;
	}

	public int this[int index] {
		get {
			switch (index) {
				case 0: return x;
				case 1: return y;
				default: throw new System.IndexOutOfRangeException();
			}
		}
		set {
			switch (index) {
				case 0: x = value; break;
				case 1: y = value; break;
				default: throw new System.IndexOutOfRangeException();
			}
		}
	}

	public static Point zero = new Point(0, 0);
	public static Point right = new Point(1, 0);
	public static Point up = new Point(0, 1);

	// User-defined conversion from Point to Vector2
	/*public static implicit operator Vector2 (Point p) {
		return new Vector2(p.x, p.y);
	}
	//  User-defined conversion from Vector2 to Point
	public static explicit operator Point (Vector2 p) {
		return new Point(Mathf.FloorToInt(p.x), Mathf.FloorToInt(p.y));
	}*/

	public static Point operator + (Point a, Point b) {
		return new Point(a.x + b.x, a.y + b.y);
	}

	public static Point operator - (Point a, Point b) {
		return new Point(a.x - b.x, a.y - b.y);
	}

	public static Point operator - (Point a) {
		return new Point(-a.x, -a.y);
	}

	public static Point operator * (Point a, int f) {
		return new Point(a.x * f, a.y * f);
	}

	public static Point operator / (Point a, int f) {
		return new Point(a.x / f, a.y / f);
	}

	public static Point operator * (Point a, Point b) {
		return new Point(a.x * b.x, a.y * b.y);
	}

	public static bool operator == (Point a, Point b) {
		return a.Equals(b);
	}

	public static bool operator != (Point a, Point b) {
		return !a.Equals(b);
	}

	public override bool Equals (System.Object obj) {
		//Check for null and compare run-time types.
		if (obj == null || GetType() != obj.GetType()) return false;
		Point p = (Point)obj;
		return (x == p.x) && (y == p.y);
	}

	public override string ToString() {
		return "("+x+","+y+")";
	}

	public override int GetHashCode() {
		return x*10000 + y;
	}
}

public struct Pointf {
	public float x, y;

	public Pointf (float x, float y) {
		this.x = x;
		this.y = y;
	}

	public float this[int index] {
		get {
			switch (index) {
				case 0: return x;
				case 1: return y;
				default: throw new System.IndexOutOfRangeException();
			}
		}
		set {
			switch (index) {
				case 0: x = value; break;
				case 1: y = value; break;
				default: throw new System.IndexOutOfRangeException();
			}
		}
	}

	public static Pointf zero = new Pointf(0, 0);
	public static Pointf right = new Pointf(1, 0);
	public static Pointf up = new Pointf(0, 1);

	// User-defined conversion from Point to Pointf
	public static implicit operator Pointf (Point p) {
		return new Pointf(p.x, p.y);
	}
	//  User-defined conversion from Pointf to Point
	public static explicit operator Point (Pointf p) {
		return new Point((int)System.Math.Round(p.x), (int)System.Math.Round(p.y));
	}

	public static Pointf operator + (Pointf a, Pointf b) {
		return new Pointf(a.x + b.x, a.y + b.y);
	}

	public static Pointf operator - (Pointf a, Pointf b) {
		return new Pointf(a.x - b.x, a.y - b.y);
	}

	public static Pointf operator - (Pointf a) {
		return new Pointf(-a.x, -a.y);
	}

	public static Pointf operator * (Pointf a, float f) {
		return new Pointf(a.x * f, a.y * f);
	}

	public static Pointf operator / (Pointf a, float f) {
		return new Pointf(a.x / f, a.y / f);
	}

	public static Pointf operator * (Pointf a, Pointf b) {
		return new Pointf(a.x * b.x, a.y * b.y);
	}

	/*public static bool operator == (Pointf a, Pointf b) {
		return a.Equals(b);
	}

	public static bool operator != (Pointf a, Pointf b) {
		return !a.Equals(b);
	}

	public override bool Equals (System.Object obj) {
		//Check for null and compare run-time types.
		if (obj == null || GetType() != obj.GetType()) return false;
		Pointf p = (Pointf)obj;
		return (x == p.x) && (y == p.y);
	}*/

	public static bool operator == (Pointf a, Pointf b) {
		return a.Equals(b);
	}

	public static bool operator != (Pointf a, Pointf b) {
		return !a.Equals(b);
	}

	public override bool Equals (System.Object obj) {
		//Check for null and compare run-time types.
		if (obj == null || GetType() != obj.GetType()) return false;
		Point p = (Point)obj;
		return (x == p.x) && (y == p.y);
	}

	public override string ToString() {
		return "("+x+","+y+")";
	}

	public override int GetHashCode() {
		return (int)(x*10000 + y);
	}

	public Pointf normalized { get {
		return this / (float)System.Math.Sqrt(x*x+y*y);
	} }
}

}
