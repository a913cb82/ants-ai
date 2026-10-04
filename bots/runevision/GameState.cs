using System;
using System.Collections.Generic;

namespace Ants {

	public class GameState : IGameState {

		public int Width { get; private set; }
		public int Height { get; private set; }

		public int LoadTime { get; private set; }
		public int TurnTime { get; private set; }

		private DateTime turnStart;
		public int TimeRemaining {
			get {
				TimeSpan timeSpent = DateTime.Now - turnStart;
				return TurnTime - timeSpent.Milliseconds;
			}
		}

		public int ViewRadius2 { get; private set; }
		public int AttackRadius2 { get; private set; }
		public int SpawnRadius2 { get; private set; }

		public List<Point> MyAnts { get; private set; }
		public List<Point> MyHills { get; private set; }
		public List<Point> EnemyAnts { get; private set; }
		public List<Point> EnemyHills { get; private set; }
		public List<Point> DeadTiles { get; private set; }
		public List<Point> FoodTiles { get; private set; }

		public Tile this[Point location] {
			get { return this.map[location.x, location.y]; }
		}

		public Tile this[int row, int col] {
			get { return this.map[row, col]; }
		}

		private Tile[,] map;

		public GameState (int width, int height,
		                  int turntime, int loadtime,
		                  int viewradius2, int attackradius2, int spawnradius2) {

			Width = width;
			Height = height;

			LoadTime = loadtime;
			TurnTime = turntime;

			ViewRadius2 = viewradius2;
			AttackRadius2 = attackradius2;
			SpawnRadius2 = spawnradius2;

			MyAnts = new List<Point>();
			MyHills = new List<Point>();
			EnemyAnts = new List<Point>();
			EnemyHills = new List<Point>();
			DeadTiles = new List<Point>();
			FoodTiles = new List<Point>();

			map = new Tile[height, width];
			for (int row = 0; row < height; row++) {
				for (int col = 0; col < width; col++) {
					map[row, col] = Tile.Land;
				}
			}
		}

		#region State mutators
		public void StartNewTurn () {
			// start timer
			turnStart = DateTime.Now;

			// clear ant data
			foreach (Point loc in MyAnts) map[loc.x, loc.y] = Tile.Land;
			foreach (Point loc in MyHills) map[loc.x, loc.y] = Tile.Land;
			foreach (Point loc in EnemyAnts) map[loc.x, loc.y] = Tile.Land;
			foreach (Point loc in EnemyHills) map[loc.x, loc.y] = Tile.Land;
			foreach (Point loc in DeadTiles) map[loc.x, loc.y] = Tile.Land;

			MyHills.Clear();
			MyAnts.Clear();
			EnemyHills.Clear();
			EnemyAnts.Clear();
			DeadTiles.Clear();

			// set all known food to unseen
			foreach (Point loc in FoodTiles) map[loc.x, loc.y] = Tile.Land;
			FoodTiles.Clear();
		}

		public void AddAnt (int row, int col, int team) {
			map[row, col] = Tile.Ant;

			Point ant = new Point(row, col);
			if (team == 0) {
				MyAnts.Add(ant);
			} else {
				EnemyAnts.Add(ant);
			}
		}

		public void AddFood (int row, int col) {
			map[row, col] = Tile.Food;
			FoodTiles.Add(new Point(row, col));
		}

		public void RemoveFood (int row, int col) {
			// an ant could move into a spot where a food just was
			// don't overwrite the space unless it is food
			if (map[row, col] == Tile.Food) {
				map[row, col] = Tile.Land;
			}
			FoodTiles.Remove(new Point(row, col));
		}

		public void AddWater (int row, int col) {
			map[row, col] = Tile.Water;
		}

		public void DeadAnt (int row, int col) {
			// food could spawn on a spot where an ant just died
			// don't overwrite the space unless it is land
			if (map[row, col] == Tile.Land) {
				map[row, col] = Tile.Dead;
			}

			// but always add to the dead list
			DeadTiles.Add(new Point(row, col));
		}

		public void AntHill (int row, int col, int team) {

			if (map[row, col] == Tile.Land) {
				map[row, col] = Tile.Hill;
			}

			Point hill = new Point (row, col);
			if (team == 0)
				MyHills.Add (hill);
			else
				EnemyHills.Add (hill);
		}
		#endregion

		/// <summary>
		/// Gets whether <paramref name="location"/> is passable or not.
		/// </summary>
		/// <param name="location">The location to check.</param>
		/// <returns><c>true</c> if the location is not water, <c>false</c> otherwise.</returns>
		/// <seealso cref="GetIsUnoccupied"/>
		public bool GetIsPassable (Point location) {
			return map[location.x, location.y] != Tile.Water;
		}

		/// <summary>
		/// Gets whether <paramref name="location"/> is occupied or not.
		/// </summary>
		/// <param name="location">The location to check.</param>
		/// <returns><c>true</c> if the location is passable and does not contain an ant, <c>false</c> otherwise.</returns>
		public bool GetIsUnoccupied (Point location) {
			return GetIsPassable(location) && map[location.x, location.y] != Tile.Ant;
		}

		/// <summary>
		/// Gets the destination if an ant at <paramref name="location"/> goes in <paramref name="direction"/>, accounting for wrap around.
		/// </summary>
		/// <param name="location">The starting location.</param>
		/// <param name="direction">The direction to move.</param>
		/// <returns>The new location, accounting for wrap around.</returns>
		public Point GetDestination (Point location, Direction direction) {
			Point delta = Ants.Aim[direction];

			int row = (location.x + delta.x + Height) % Height;

			int col = (location.y + delta.y + Width) % Width;

			return new Point(row, col);
		}

		public Point GetDestination (Point location, Move move) {
			Point delta = Ants.Aim2[move];

			int row = (location.x + delta.x + Height) % Height;

			int col = (location.y + delta.y + Width) % Width;

			return new Point(row, col);
		}

		/// <summary>
		/// Gets the distance between <paramref name="loc1"/> and <paramref name="loc2"/>.
		/// </summary>
		/// <param name="loc1">The first location to measure with.</param>
		/// <param name="loc2">The second location to measure with.</param>
		/// <returns>The distance between <paramref name="loc1"/> and <paramref name="loc2"/></returns>
		public int GetDistance (Point loc1, Point loc2) {
			int d_row = Math.Abs(loc1.x - loc2.x);
			d_row = Math.Min(d_row, Height - d_row);

			int d_col = Math.Abs(loc1.y - loc2.y);
			d_col = Math.Min(d_col, Width - d_col);

			return d_row + d_col;
		}

		/// <summary>
		/// Gets the closest directions to get from <paramref name="loc1"/> to <paramref name="loc2"/>.
		/// </summary>
		/// <param name="loc1">The location to start from.</param>
		/// <param name="loc2">The location to determine directions towards.</param>
		/// <returns>The 1 or 2 closest directions from <paramref name="loc1"/> to <paramref name="loc2"/></returns>
		public ICollection<Direction> GetDirections (Point loc1, Point loc2) {
			List<Direction> directions = new List<Direction>();

			if (loc1.x < loc2.x) {
				if (loc2.x - loc1.x >= Height / 2)
					directions.Add(Direction.North);
				if (loc2.x - loc1.x <= Height / 2)
					directions.Add(Direction.South);
			}
			if (loc2.x < loc1.x) {
				if (loc1.x - loc2.x >= Height / 2)
					directions.Add(Direction.South);
				if (loc1.x - loc2.x <= Height / 2)
					directions.Add(Direction.North);
			}

			if (loc1.y < loc2.y) {
				if (loc2.y - loc1.y >= Width / 2)
					directions.Add(Direction.West);
				if (loc2.y - loc1.y <= Width / 2)
					directions.Add(Direction.East);
			}
			if (loc2.y < loc1.y) {
				if (loc1.y - loc2.y >= Width / 2)
					directions.Add(Direction.East);
				if (loc1.y - loc2.y <= Width / 2)
					directions.Add(Direction.West);
			}

			return directions;
		}

		public bool GetIsVisible(Point loc)
		{
			List<Point> offsets = new List<Point>();
			int squares = (int)Math.Floor(Math.Sqrt(this.ViewRadius2));
			for (int r = -1 * squares; r <= squares; ++r)
			{
				for (int c = -1 * squares; c <= squares; ++c)
				{
					int square = r * r + c * c;
					if (square < this.ViewRadius2)
					{
						offsets.Add(new Point(r, c));
					}
				}
			}
			foreach (Point ant in this.MyAnts)
			{
				foreach (Point offset in offsets)
				{
					if ((ant.y + offset.y) == loc.y &&
						(ant.x + offset.x) == loc.x)
					{
								 return true;
					}
				}
			}
			return false;
		}

	}
}
