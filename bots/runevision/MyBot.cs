using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using Wintellect.PowerCollections;

namespace Ants {

	public class MyBot : Bot {

		static int turn = 0;
		static int Width = 0;
		static int Height = 0;
		static int maxTurnTime = 0;

		public System.IO.FileStream fileStream = null;
		public System.IO.StreamWriter writer = null;
		public DateTime turnStartTime = new DateTime (0);
		public DateTime lastTime = new DateTime (0);

		Random rng;
		public static GameState state;

		Dictionary<Point, AntPlan> allAnts = new Dictionary<Point, AntPlan> ();
		Dictionary<Point, AntPlan> availableAnts = new Dictionary<Point, AntPlan> ();
		//Dictionary<Point, AntPlan> distressedAnts = new Dictionary<Point, AntPlan> ();
		Dictionary<Point, AntPlan> destinations = new Dictionary<Point, AntPlan> ();

		List<Point> enemyHills = new List<Point> ();
		//List<int> enemyHillsHeat = new List<int> ();
		List<Point> foodTiles = new List<Point> ();

		List<Point> bullies = new List<Point> ();

		List<Point> hillOffsets = new List<Point> ();
		List<Point> heatOffsets = new List<Point> ();
		List<int> heatOffsetValues = new List<int> ();
		List<Point> attackOffsets = new List<Point> ();

		int[,] lastSeenMap;

		int heatRadius;
		int[,] enemyHeatMap;
		int[,] myHeatMap;
		private int EnemyHeat (Point p) { return enemyHeatMap[p.x, p.y]; }
		private int MyHeat (Point p) { return myHeatMap[p.x, p.y]; }
		private int EnemyHeatRelative (Point p) { return enemyHeatMap[p.x, p.y] - myHeatMap[p.x, p.y]; }

		int attackRadius;
		int[,] enemyAttackMap;
		List<Point>[,] enemyAttackSources;
		int[,] myAttackMap;
		private int EnemyAttackPotential (Point p) { return enemyAttackMap[p.x, p.y]; }
		private List<Point> EnemyAttackSources (Point p) {
			if (enemyAttackSources[p.x, p.y] == null)
				enemyAttackSources[p.x, p.y] = new List<Point> ();
			return enemyAttackSources[p.x, p.y];
		}
		private int MyAttackPotential (Point p) { return myAttackMap[p.x, p.y]; }

		OrderedBag<GoalPointer> mapQueue = new OrderedBag<GoalPointer> (new PointCostComparer ());

		Direction[] allDirs = new Direction[] {Direction.North, Direction.East, Direction.South, Direction.West};

		private void UpdateLists () {
			bullies.Clear ();
			UpdateList (state.EnemyHills, enemyHills, Tile.Hill);
			UpdateList (state.FoodTiles, foodTiles, Tile.Food);
		}

		public MyBot () {
			rng = new Random (42);
		}

		~ MyBot () {
#if DEBUG
			writer.Close ();
			fileStream.Close ();
#endif
		}

		int defenceAmount;
		int majorityBonus;
		int majorityThreshold;
		int enemyVisionCost;
		int enemyHeatCost;
		int enemyAntCost;
		int allyVisionCost;
		int allyHeatCost;
		int allyAntCost;
		int battleGoalCost;
		int battleGoalRange;
		int battleGoalAmount;
		int onlyBullies;
		int clearMidway;
		int takeRiskAtTie;
		public override void SetupParameters (BotInfo info) {
			defenceAmount = 12;//info.parameters["DefenceAmount"];
			enemyVisionCost = 83;//info.parameters["EnemyVisionCost"];
			enemyHeatCost = 28;//info.parameters["EnemyHeatCost"];
			enemyAntCost = 17;//info.parameters["EnemyAntCost"];
			allyVisionCost = 100;//info.parameters["AllyVisionCost"];
			allyHeatCost = 38;//info.parameters["AllyHeatCost"];
			allyAntCost = 150;//info.parameters["AllyAntCost"];
			onlyBullies = 0;

			majorityBonus = info.parameters["MajorityBonus"];
			majorityThreshold = info.parameters["MajorityThreshold"];
			battleGoalCost = info.parameters["BattleGoalCost"];
			battleGoalRange = info.parameters["BattleGoalRange"];
			battleGoalAmount = info.parameters["BattleGoalAmount"];
			clearMidway = info.parameters["ClearMidway"];
			takeRiskAtTie = info.parameters["TakeRiskAtTie"];
		}

		public override void DoTurn (GameState state) {
#if DEBUG
			turnStartTime = DateTime.Now;
			lastTime = DateTime.Now;
#endif
			turn++;
			Log ("----");

			MyBot.state = state;
			Width = state.Width;
			Height = state.Height;

			UpdateLastSeenMap ();
			UpdateLists ();

			if (heatRadius == 0)
				CreateOffsets ();

			if (enemyAttackMap == null)
				enemyHeatMap = new int[Height, Width];
			for (int i=0; i<Height; i++) {
				for (int j=0; j<Width; j++) {
					if (lastSeenMap[i,j] == turn)
						enemyHeatMap[i,j] = 0;
					else
						enemyHeatMap[i,j] = Math.Max (0, enemyHeatMap[i,j]-1);
				}
			}
			UpdateHeatMap (enemyHeatMap, state.EnemyAnts);
			myHeatMap = new int[Height, Width];
			UpdateHeatMap (myHeatMap, state.MyAnts);

			enemyAttackMap = new int[Height, Width];
			enemyAttackSources = new List<Point>[Height, Width];
			UpdateAttackMap (enemyAttackMap, state.EnemyAnts, enemyAttackSources);
			myAttackMap = new int[Height, Width];
			UpdateAttackMap (myAttackMap, state.MyAnts, null);
			LogTime ("UpdateMaps");

			//PrintIntMapDots (myAttackMap);
			LogTime ("PrintMap");

			/*enemyHillsHeat.Clear ();
			foreach (Point p in enemyHills)
				enemyHillsHeat.Add (GetHeatAtTop (p, enemyHeatMap));*/

			// Init plans
			allAnts.Clear ();
			availableAnts.Clear ();
			//distressedAnts.Clear ();
			foreach (Point ant in state.MyAnts) {
				AntPlan plan = new AntPlan (ant);
				HandleCombat (plan);
				allAnts.Add (ant, plan);
				availableAnts.Add (ant, plan);
			}
			LogTime ("HandleCombat");

			// Handle goals
			HandleGoalMaps ();

			if (availableAnts.Count > 0)
				Log ("Ants not assigned: "+availableAnts.Count+"!");

			// Init destinations
			destinations.Clear ();
			// Add dummy dest for hills so we don't block them
			foreach (Point hill in state.MyHills)
				destinations.Add (hill, null);

			allAnts.Shuffle (rng);
			foreach (AntPlan plan in allAnts.Values) {
				if (plan.order == null) {
					Log ("Plan order is null for ant "+plan.here+"!");
					plan.Sort ();
				}
				else {
					HandleOrder (plan);
				}
				TryToGetDestination (plan);
				if (state.TimeRemaining < 100) {
					Log ("Ran out of time B!");
					break;
				}
			}
			LogTime ("HandleOrders");

			foreach (AntPlan plan in allAnts.Values) {
				Log (plan.MovesString ());
				IssueOrder (plan.here, plan.chosenMove.move);
				if (state.TimeRemaining < 50) {
					Log ("Ran out of time C!");
					break;
				}
			}
			LogTime ("IssueOrders");

			maxTurnTime = Math.Max (maxTurnTime, (DateTime.Now - turnStartTime).Milliseconds);
			LogTimeSpan ("Total Time", DateTime.Now - turnStartTime);
			Log ("Max total time: "+maxTurnTime);
		}


		private bool InAttackRange (Point a, Point b) {
			Point v = ShortestDir (b-a);
			return (v.x * v.x + v.y * v.y <= state.AttackRadius2);
		}

		private void HandleCombat (AntPlan plan) {
			Log ("Ant "+plan.here+" combat");
			foreach (Move move in Ants.Moves) {
				// Get my potential position at next turn
				Point myNext = state.GetDestination (plan.here, move);

				// Store potential move
				MoveEvaluation moveEval = new MoveEvaluation (move);


				if (state[myNext] == Tile.Water || state[myNext] == Tile.Food) {
					moveEval.blocked = true;
					plan.moves.Add (moveEval);
					continue;
				}

				bool anyThreatThere = (EnemyAttackPotential (myNext) > 0);

				if (!anyThreatThere) {
					moveEval.strength = Strength.NoThreat;
				}
				else {
					Log (" - Threat at move "+move);
					plan.inBattle = true;

					int enemyAttackPotentialMyNext = EnemyAttackPotential (myNext);
					List<Point> attackSources = EnemyAttackSources (myNext);
					int minAttackPotentialRelative = 100;
					int sumAttackPotentialRelative = 0;
					int countAttackPotentialRelative = 0;
					int lowestMyHeat = 10000;
					int maxAtStakeForMove = 0;
					int risk = 0;
					foreach (Point attackSource in attackSources) {
						int attackPotentialRelative = 100;
						foreach (Move enemyMove in Ants.Moves) {
							Point enemyNext = state.GetDestination (attackSource, enemyMove);
							if (state[enemyNext] == Tile.Water || state[enemyNext] == Tile.Food)
								continue;
							if (InAttackRange (enemyNext, myNext)) {
								int myAttackPotentialEnemyNext = MyAttackPotential (enemyNext);
								int attackPotentialRelativeHere = myAttackPotentialEnemyNext - enemyAttackPotentialMyNext;
								sumAttackPotentialRelative += attackPotentialRelativeHere;
								countAttackPotentialRelative++;

								attackPotentialRelative = Math.Min (attackPotentialRelative, attackPotentialRelativeHere);
								if (enemyAttackPotentialMyNext > 0 && attackPotentialRelativeHere <= 0) {
									risk += (attackPotentialRelative == 0 ? 1 : 2);
								}
								maxAtStakeForMove = Math.Max (maxAtStakeForMove, myAttackPotentialEnemyNext);
							}
						}
						minAttackPotentialRelative = Math.Min (minAttackPotentialRelative, attackPotentialRelative);
						lowestMyHeat = Math.Min (lowestMyHeat, MyHeat (attackSource));
						Log ("    - source "+attackSource+
							" - attackPotentialRelative: "+attackPotentialRelative);
					}

					if (minAttackPotentialRelative >= 0)
						moveEval.score += maxAtStakeForMove * 5;
					if (minAttackPotentialRelative <= 0)
						moveEval.score -= risk * 2;

					int attackPotentialAdjusted = minAttackPotentialRelative;
					if (MyHeat (plan.here) > heatRadius * majorityThreshold) {
						attackPotentialAdjusted += Math.Max (0, (int)(((lowestMyHeat / Math.Max (1, EnemyHeat (plan.here))) - 1) * majorityBonus * 0.01f));
					}

					moveEval.strength = (attackPotentialAdjusted > 0) ? Strength.Stronger : Strength.Weaker;
					if (takeRiskAtTie == 1 && attackPotentialAdjusted == 0 && sumAttackPotentialRelative >= countAttackPotentialRelative)
						moveEval.strength = Strength.Stronger;

					moveEval.score += (((int)moveEval.strength - 1) * 10);

					Log ("   - attackPotentialRelative: "+minAttackPotentialRelative+
						" attackPotentialAdjusted: "+attackPotentialAdjusted+
						" sumAttackPotential: "+sumAttackPotentialRelative+
						" risk: "+risk+
						" maxAtStake: "+maxAtStakeForMove+
						" result: "+moveEval.score
					);
				}

				if (moveEval.strength == Strength.Weaker) {
					plan.inDistress = true;
				}

				plan.moves.Add (moveEval);
			}

			//if (plan.inDistress)
			//	distressedAnts.Add (plan.here, plan);
		}

		private void HandleOrder (AntPlan plan) {
			Order order = plan.order;
			bool moreImportantThanBattle = false;
			Point dir = ShortestDir (order.next3 - plan.here);

			if (order.task == TaskType.Defend) {
				int toDefenceDist = GetDistance (plan.here, plan.order.goalPos);
				int toHillDist = GetDistance (plan.here, plan.order.goalPos2);
				int hillToDefenceDist = GetDistance (plan.order.goalPos, plan.order.goalPos2);
				if (toHillDist <= hillToDefenceDist || toDefenceDist >= hillToDefenceDist)
					moreImportantThanBattle = true;
			}

			if (order.task == TaskType.EnemyHill) {
				if (order.goalDist <= 2)
					moreImportantThanBattle = true;
			}

			if (order.task == TaskType.Food) {
				if (order.goalDist == 0)
					dir = Point.zero;
				if (order.goalDist <= 1)
					moreImportantThanBattle = true;
			}

			if (order.task == TaskType.Explore) {

			}

			int importance = 1;
			if (moreImportantThanBattle) {
				importance = 3;
				for (int i=0; i<5; i++) {
					MoveEvaluation moveEval = plan.moves[i];
					moveEval.score = 0;
					plan.moves[i] = moveEval;
				}
			}

			if (dir == Point.zero) {
				// Add score to staying
				MoveEvaluation moveEval = plan.moves[4];
				moveEval.score += 4 * importance;
				plan.moves[4] = moveEval;
			}
			else {
				// Add score to directions
				List<Move> moves = GetMoves (plan.here, plan.here + dir, plan.inBattle);
				int score = 4;
				foreach (Direction d in moves) {
					MoveEvaluation moveEval = plan.moves[(int)d];
					moveEval.score += score * importance;
					plan.moves[ (int)d] = moveEval;
					score--;
				}
			}

			plan.Sort ();
		}

		private string ind (int nr) { return nr > 0 ? "   " : ""; }

		private void TryToGetDestination (AntPlan plan) {
			if (plan.moves.Count == 0)
				return;
			for (int depth=0; depth<1000; depth++) {
				int bestScore = -1000;
				int bestMoveIndex = 0;
				bool bestIsOccupied = false;
				Point bestMovePos = plan.here;
				for (int i=0; i<plan.moves.Count; i++) {
					MoveEvaluation moveEval = plan.moves[i];
					if (moveEval.blocked)
						continue;
					Point movePos = state.GetDestination (plan.here, moveEval.move);
					int score;
					bool occupied = destinations.ContainsKey (movePos);
					if (!occupied) {
						score = moveEval.score;
					}
					else {
						AntPlan existing = destinations[movePos];
						if (existing == null)
							continue;
						score = moveEval.score - existing.chosenMove.score;
					}
					if (score > bestScore) {
						bestScore = score;
						bestMoveIndex = i;
						bestIsOccupied = occupied;
						bestMovePos = movePos;
					}
				}
				plan.chosenMoveIndex = bestMoveIndex;
				MoveEvaluation bestMoveEval = plan.chosenMove;
				if (!bestIsOccupied) {
					destinations[bestMovePos] = plan;
					Log (ind (depth)+"Ant "+plan.here+" got dest "+bestMovePos);
					return;
				}
				else {
					AntPlan existing = destinations[bestMovePos];
					Log (ind (depth)+"Ant "+plan.here+" took dest "+bestMovePos+" ("+bestMoveEval.score+") from "+existing.here+" ("+existing.chosenMove.score+") rel:"+bestScore);
					if (bestScore <= 0) {
						for (int i=0; i<plan.moves.Count; i++) {
							MoveEvaluation me = plan.moves[i];
							me.score += -bestScore + 1;
							plan.moves[i] = me;
						}
					}
					destinations[bestMovePos] = plan;
					plan = existing;
				}
			}
			Log ("   TryToGetDestination max depth is exceeded!!");
		}

		GoalPointer[,] InitMap () {
			return new GoalPointer[Height, Width];
		}

		private void HandleGoalMaps () {
			// List of oldest seen points
			List<Point> oldestSeen = new List<Point> ();
			for (int j=0; j<Width; j+=5) {
				for (int i=0; i<Height; i+=5) {
					if (lastSeenMap[i,j] < turn - 10)
						oldestSeen.Add (new Point (i,j));
				}
			}
			oldestSeen.Sort (new LastSeenComparer (lastSeenMap));


			GoalPointer[,] map;
			mapQueue.Clear ();


			// Defend
			map = InitMap ();
			foreach (Point hill in state.MyHills) {
				int assigned = 0;
				int amount = (int)Math.Floor ((defenceAmount * 0.01f * state.MyAnts.Count / state.MyHills.Count));
				Log ("Assign "+amount+" ants to defense of hill "+hill);
				for (int c=0; c<hillOffsets.Count; c++) {
					Point offset = hillOffsets[c];
					if (assigned >= amount)
						break;
					Point p = new Point (Wrapx (hill.x+offset.x), Wrapy (hill.y+offset.y));
					if (state[p] == Tile.Water)
						continue;
					AddGoalInit (p, hill, TaskType.Defend, 1, 0, (100*c)/8, 30, map);
					assigned++;
				}
			}


			// Attack Hills
			if (enemyHills.Count > 0) {
				map = InitMap ();
				int attackPerHill = Math.Max (1, state.MyAnts.Count/3/enemyHills.Count);
				foreach (Point hill in enemyHills) {
					AddGoalInit (hill, hill, TaskType.EnemyHill, attackPerHill, 0, 0, 10000, map);
				}
			}
			// If no known enemy hills, send army to oldest seen point
			else if (turn > 100 && oldestSeen.Count > 0) {
				map = InitMap ();
				int attackPerHill = Math.Max (1, state.MyAnts.Count/3);
				AddGoalInit (oldestSeen[0], oldestSeen[0], TaskType.EnemyHill, attackPerHill, 0, 0, 10000, map);
			}


			// Get food with single gatherers
			if (state.MyHills.Count > 0) {
				map = InitMap ();
				foreach (Point food in foodTiles) {
					AddGoalInit (food, food, TaskType.Food, 1, -1, 100*4, 10000, map);
				}
			}


			if (clearMidway == 1) {
				HandleMap ();
				mapQueue.Clear ();
			}

			// Help distressed ants
			/*map = InitMap ();
			foreach (Point pos in distressedAnts.Keys) {
				AddGoalInit (pos, TaskType.Support, 10, -1, 50, 20, map);
			}*/


			// Explore with single scouts
			map = InitMap ();
			for (int i=0; i < oldestSeen.Count; i++) {
				AddGoalInit (oldestSeen[i], oldestSeen[i], TaskType.Explore, 1, 0, 100*25, 10000, map);
			}


			// Attack Nearby Ants
			map = InitMap ();
			List<Point> enemies = (onlyBullies == 1 ? bullies : state.EnemyAnts);
			foreach (Point enemy in enemies) {
				AddGoalInit (enemy, enemy, TaskType.None, battleGoalAmount, 0, 100*battleGoalCost, battleGoalRange, map);
			}


			HandleMap ();
			mapQueue.Clear ();


			// Attack catch-all to make sure no ants are idle
			if (enemyHills.Count > 0) {
				map = InitMap ();
				foreach (Point hill in enemyHills) {
					AddGoalInit (hill, hill, TaskType.EnemyHill, state.MyAnts.Count, 0, 100*25, 10000, map);
				}
			}
			else if (oldestSeen.Count > 0) {
				map = InitMap ();
				AddGoalInit (oldestSeen[0], oldestSeen[0], TaskType.EnemyHill, state.MyAnts.Count, 100*25, 0, 10000, map);
			}

			HandleMap ();
		}

		void HandleMap () {
			LogTime ("HandleMap Init");
			while (mapQueue.Count > 0 && availableAnts.Count > 0) {
				AddGoalDist (mapQueue.RemoveFirst ());
				if (state.TimeRemaining < 150) {
					Log ("Ran out of time A!");
					break;
				}
			}
			LogTime ("HandleMap Search");
		}

		private void AddGoalInit (Point loc, Point loc2, TaskType type, int nrAnts, int dist, int cost, int maxDist, GoalPointer[,] map) {
			GoalPointer pointer = new GoalPointer (loc, loc, new Goal (loc, loc2, type, nrAnts, maxDist, map), dist, cost);
			map[loc.x, loc.y] = pointer;
			mapQueue.Add (pointer);
		}

		private void AddGoalDist (GoalPointer newGoal) {
			Point p = newGoal.here;
			GoalPointer[,] map = newGoal.goal.map;
			if (newGoal.goal.covered)
				return;

			if (state[p] == Tile.Ant && availableAnts.ContainsKey (p)) {
				bool assign = true;
				AntPlan taker = availableAnts[p];
				/*if (newGoal.goal.task == TaskType.Support) {
					if (newGoal.goal.position == p)
						assign = false;
					if (distressedAnts.ContainsKey (p))
						assign = false;
				}*/
				if (assign) {
					newGoal.goal.assigned++;
					taker.order = new Order (newGoal);
					availableAnts.Remove (p);
				}
			}

			if (newGoal.dist < newGoal.goal.maxDist) {
				allDirs.Shuffle (rng);
				foreach (Direction dir in allDirs) {
					Point n = state.GetDestination (p, dir);

					int cost = 100;
					int enemyHeat = enemyHeatMap[p.x, p.y];
					int myHeat = myHeatMap[p.x, p.y];
					cost += enemyVisionCost * (enemyHeat > 0 ? 1 : 0);
					cost += enemyHeatCost * enemyHeat / heatRadius;
					cost += allyVisionCost * (myHeat > 0 ? 1 : 0);
					cost += allyHeatCost * myHeat / heatRadius;
					if (state[n] == Tile.Ant) {
						cost += (allAnts.ContainsKey (n) ? allyAntCost : enemyAntCost);
					}
					cost = newGoal.cost + Math.Max (1, cost);

					GoalPointer potential = new GoalPointer (n, p, newGoal.goal, newGoal.dist+1, cost);
					GoalPointer existing = map[n.x, n.y];
					if (IsBetterGoal (existing, potential))
					{
						map[n.x, n.y] = potential;
						mapQueue.Add (potential);
					}
				}
			}
		}

		private bool IsBetterGoal (GoalPointer o, GoalPointer n) {
			return (o.goal == null || o.goal.covered || n.cost < o.cost) && state.GetIsPassable (n.here);
		}

		/*private Point GetHeatVector (Point loc, int[,] map) {
			Point v = new Point (0,0);
			int heatHere = map[loc.x, loc.y];
			foreach (Direction dir in allDirs) {
				Point delta = Ants.Aim[dir];
				Point n = state.GetDestination (loc, dir);
				int heatThere = map[n.x, n.y];
				v += delta * (heatThere - heatHere);
			}
			int div = Math.Max (1, Math.Max (Math.Abs (v.x), Math.Abs (v.y)) / 3);
			v.x /= div;
			v.y /= div;
			return v;
		}*/

		/*private int GetHeatAtTop (Point loc, int[,] map) {
			int heatHere = map[loc.x, loc.y];
			for (int i=0; i<100; i++) {
				int highestHeat = 0;
				Point highestHeatLoc = loc;
				foreach (Direction dir in allDirs) {
					Point n = state.GetDestination (loc, dir);
					int heatThere = map[n.x, n.y];
					if (heatThere > highestHeat) {
						highestHeat = heatThere;
						highestHeatLoc = n;
					}
				}
				if (highestHeat <= heatHere)
					return heatHere;
				heatHere = highestHeat;
				loc = highestHeatLoc;
			}
			return heatHere;
		}*/

		private void UpdateHeatMap (int[,] map, List<Point> locations) {
			bool[,] marked = new bool[heatRadius*2+1, heatRadius*2+1];
			foreach (Point ant in locations)
			{
				for (int i=0; i<heatOffsets.Count; i++) {
					if (state[Wrap (ant+heatOffsets[i])] == Tile.Water)
						continue;

					bool markedNeighbor = i == 0;
					foreach (Direction dir in allDirs) {
						if (markedNeighbor)
							break;
						Point neighbor = heatOffsets[i] + Ants.Aim[dir];
						if (Math.Abs (neighbor.x) > heatRadius || Math.Abs (neighbor.y) > heatRadius)
							continue;
						if (marked[neighbor.x+heatRadius, neighbor.y+heatRadius])
							markedNeighbor = true;
					}
					if (markedNeighbor) {
						map[Wrapx (ant.x + heatOffsets[i].x), Wrapy (ant.y + heatOffsets[i].y)] += heatOffsetValues[i];
						marked[heatOffsets[i].x+heatRadius, heatOffsets[i].y+heatRadius] = true;
					}
				}
			}
		}

		private Point GetCloserToCenterPoint (Point p) {
			if (p == Point.zero)
				return p;
			int i = p.x; int j = p.y;
			if (Math.Abs (i) > Math.Abs (j))
				i = i - Math.Sign (i);
			else
				j = j - Math.Sign (j);
			return new Point (i,j);
		}

		private void UpdateAttackMap (int[,] map, List<Point> locations, List<Point>[,] sourceMap) {
			bool[,] marked = new bool[attackRadius*2+1, attackRadius*2+1];
			foreach (Point ant in locations)
			{
				for (int o=0; o<attackOffsets.Count; o++) {
					if (state[Wrap (ant+attackOffsets[o])] == Tile.Water)
						continue;

					/*bool markedNeighbor = o == 0;
					if (!markedNeighbor) {
						Point neighbor = GetCloserToCenterPoint (attackOffsets[o]);
						if (marked[neighbor.x+attackRadius, neighbor.y+attackRadius])
							markedNeighbor = true;
					}
					if (markedNeighbor) {*/
						int i = Wrapx (ant.x + attackOffsets[o].x);
						int j = Wrapy (ant.y + attackOffsets[o].y);
						map[i, j] += 1;
						marked[attackOffsets[o].x+attackRadius, attackOffsets[o].y+attackRadius] = true;
						if (sourceMap != null) {
							if (sourceMap[i, j] == null)
								sourceMap[i, j] = new List<Point> ();
							sourceMap[i, j].Add (ant);
						}
					//}
				}
			}
		}

		[Conditional ("DEBUG")]
		private void PrintIntMapNr (int[,] map) {
			string str;
			for (int i=0; i<map.GetLength (0); i++) {
				str = string.Empty;
				for (int j=0; j<map.GetLength (1); j++) {
					if (map[i,j] == 0)
						str += " ";
					else
						str += Math.Min (9,map[i,j]);
				}
				Log (str);
			}
		}

		[Conditional ("DEBUG")]
		private void PrintIntMapDots (int[,] map) {

			string str1 = "    ";
			string str2 = "    ";
			string str3 = "    ";
			string str4 = "    ";
			for (int j=0; j<map.GetLength (1); j++) {
				string nr = j.ToString ("D3");
				str1 += nr.Substring (0, 1) + " ";
				str2 += nr.Substring (1, 1) + " ";
				str3 += nr.Substring (2, 1) + " ";
				str4 += "  ";
			}
			Log (str1);
			Log (str2);
			Log (str3);
			Log (str4);
			string str;
			for (int i=0; i<map.GetLength (0); i++) {
				str = i.ToString ("D3") + " ";
				for (int j=0; j<map.GetLength (1); j++) {
					Point p = new Point (i,j);
					Tile tile = state[p];
					if (tile == Tile.Hill)
						str += "@ ";
					else if (tile == Tile.Water)
						str += "# ";
					else if (tile == Tile.Ant) {
						if (state.MyAnts.Contains (p))
							str += "O ";
						else
							str += "X ";
					}
					else if (map[i,j] > 0)
						str += "` ";
					else if (lastSeenMap[i,j] < 0)
						str += "/ ";
					else if (lastSeenMap[i,j] < turn)
						str += ". ";
					else
						str += "  ";
				}
				Log (str);
			}
		}

		Point Wrap (Point p) { return new Point (Wrapx (p.x), Wrapy (p.y)); }
		int Wrapy (int col) { return (col + Width) % Width; }
		int Wrapx (int row) { return (row + Height) % Height; }

		private void UpdateLastSeenMap () {
			if (lastSeenMap == null) {
				lastSeenMap = new int[Height, Width];
				for (int i=0; i<Height; i++) {
					for (int j=0; j<Width; j++) {
						lastSeenMap[i,j] = -1000 - rng.Next (1000);
					}
				}
			}
			List<Point> offsets = new List<Point> ();
			int squares = (int)Math.Floor (Math.Sqrt (state.ViewRadius2));
			for (int r = -1 * squares; r <= squares; ++r)
			{
				for (int c = -1 * squares; c <= squares; ++c)
				{
					int square = r * r + c * c;
					if (square < state.ViewRadius2)
						offsets.Add (new Point (r, c));
				}
			}
			foreach (Point ant in state.MyAnts)
			{
				foreach (Point offset in offsets)
					lastSeenMap[Wrapx (ant.x + offset.x), Wrapy (ant.y + offset.y)] = turn;
			}
		}

		private void UpdateList (List<Point> serverList, List<Point> localList, Tile tileType) {
			for (int i=localList.Count-1; i>=0; i--) {
				if (IsVisible (localList[i]) && !serverList.Contains (localList[i]))
					localList.RemoveAt (i);
			}
			foreach (Point loc in serverList) {
				if (!localList.Contains (loc))
					localList.Add (loc);
			}
		}

		private bool IsVisible (Point p) {
			return lastSeenMap[p.x, p.y] == turn;
		}

		public int GetDistance (Point a, Point b) {
			return state.GetDistance (a, b);
		}

		[Conditional ("DEBUG")]
		public void Log (string str) {
			if (state != null)
				writer.WriteLine (state.TimeRemaining.ToString ("D5") + "  " + str);
			else
				writer.WriteLine (str);
			writer.Flush ();
		}

		[Conditional ("DEBUG")]
		public void LogTime (string header) {
			LogTimeSpan (header, DateTime.Now - lastTime);
			lastTime = DateTime.Now;
		}

		[Conditional ("DEBUG")]
		public void LogTimeSpan (string header, TimeSpan span)
		{
			Log (String.Format ("Turn {0,5} {1,25} {2,5}", turn, header+" time:", span.Milliseconds));
		}

		public static Point ShortestDir (Point v) {
			if (v.y > Width/2)
				v.y -= Width;
			else if (v.y < -Width/2)
				v.y += Width;
			if (v.x > Height/2)
				v.x -= Height;
			else if (v.x < -Height/2)
				v.x += Height;
			return new Point (v.x, v.y);
		}

		public Move GetClosestMove (Point a, Point b) {
			if (a == b)
				return Move.Stay;
			Point v = ShortestDir (b - a);
			if (Math.Abs (v.y) > Math.Abs (v.x))
				return (v.y > 0 ? Move.East : Move.West);
			else
				return (v.x > 0 ? Move.South : Move.North);
		}

		public List<Move> GetMoves (Point a, Point b, bool steady) {
			List<Move> moves = new List<Move> ();
			if (a == b) {
				moves.Add (Move.Stay);
				allDirs.Shuffle (rng);
				foreach (Direction d in allDirs)
					moves.Add ((Move)((int)d));
				return moves;
			}
			Point v = ShortestDir (b - a);

			bool vertical = (Math.Abs (v.x) == Math.Abs(v.y)) ?
				rng.Next (2) == 0 :
				Math.Abs (v.x) > Math.Abs (v.y);
			if (!vertical) {
				moves.Add (v.y > 0 ? Move.East : Move.West);
				if (v.x != 0)
					moves.Add (v.x > 0 ? Move.South : Move.North);
				else
					moves.Add (rng.Next (2) == 0 ? Move.South : Move.North);
			}
			else {
				moves.Add (v.x > 0 ? Move.South : Move.North);
				if (v.y != 0)
					moves.Add (v.y > 0 ? Move.East : Move.West);
				else
					moves.Add (rng.Next (2) == 0 ? Move.West : Move.East);
			}

			int dir = (int)moves[1];
			moves.Add ((Move) ((dir/2)*2 + 1- (dir%2)));
			dir = (int)moves[0];
			moves.Add ((Move) ((dir/2)*2 + 1- (dir%2)));

			if (!steady)
				moves.Add (Move.Stay);
			else if (v.x == 0 || v.y == 0)
				moves.Insert (1, Move.Stay);
			else
				moves.Insert (2, Move.Stay);

			return moves;
		}

		public void CreateOffsets () {
			// Heat offsets
			heatRadius = (int)Math.Floor (Math.Sqrt (state.ViewRadius2));
			for (int r = -1 * heatRadius; r <= heatRadius; ++r)
			{
				for (int c = -1 * heatRadius; c <= heatRadius; ++c)
				{
					int square = r * r + c * c;
					if (square <= heatRadius*heatRadius)
						heatOffsets.Add (new Point (r, c));
				}
			}
			heatOffsets.Sort (new PointDistFromCenterComparer ());
			for (int i=0; i<heatOffsets.Count; i++)
			{
				int square = heatOffsets[i].x * heatOffsets[i].x + heatOffsets[i].y * heatOffsets[i].y;
				heatOffsetValues.Add (heatRadius - (int)Math.Floor (Math.Sqrt (square)));
			}

			// Attack offsets
			attackRadius = (int)Math.Floor (Math.Sqrt (state.AttackRadius2))+1;
			for (int r = -1 * attackRadius; r <= attackRadius; ++r)
			{
				for (int c = -1 * attackRadius; c <= attackRadius; ++c)
				{
					Point p = new Point (r, c);
					int square = r * r + c * c;
					if (square <= state.AttackRadius2)
						attackOffsets.Add (p);
					else {
						Point q = GetCloserToCenterPoint (p);
						square = q.x * q.x + q.y * q.y;
						if (square <= state.AttackRadius2)
							attackOffsets.Add (p);
					}
				}
			}

			// Hill offsets
			const int radius = 30;
			List<Point> quaterOffsets = new List<Point> ();
			for (int i=0; i<=radius; i+=1) {
				for (int j=1; j<=radius; j+=1) {
					if (i*i+j*j <= radius*radius)
						quaterOffsets.Add (new Point (i,j));
				}
			}
			quaterOffsets.Sort (new PointDistFromCenterComparer ());
			hillOffsets = new List<Point> ();
			foreach (Point p in quaterOffsets) {
				hillOffsets.Add (new Point (p.x, p.y));
				hillOffsets.Add (new Point (-p.x, -p.y));
				hillOffsets.Add (new Point (p.y, -p.x));
				hillOffsets.Add (new Point (-p.y, p.x));
			}
			/*hillOffsets = new List<Point> ();
			{
				int i = 0;
				while (hillOffsets0.Count > 0) {
					int j = i<2 ? 0 : (i) % 6;
					int c = hillOffsets.Count / 4 * j * j;
					c = c % hillOffsets0.Count;
					Point p = hillOffsets0[c];
					hillOffsets0.RemoveAt (c);
					hillOffsets.Add (new Point (p.x, p.y));
					hillOffsets.Add (new Point (-p.x, -p.y));
					hillOffsets.Add (new Point (p.y, -p.x));
					hillOffsets.Add (new Point (-p.y, p.x));
					i++;
				}
			}*/
		}

		public static void Main (string[] args) {
			new Ants ().PlayGame (new MyBot (), args);
		}
	}

	public class PointDistFromCenterComparer : IComparer<Point> {
		public int Compare (Point x, Point y)
		{
			int radX = x.x*x.x + x.y*x.y;
			int radY = y.x*y.x + y.y*y.y;
			if (radX != radY)
				return radX.CompareTo (radY);
			if (Octant (x) != Octant (y))
				return Octant (x).CompareTo (Octant (y));
			return Quadrant (x).CompareTo (Quadrant (y));
		}
		private int Octant (Point p) {
			return Math.Sign (p.x*p.y) * Math.Sign (Math.Abs (p.x) - Math.Abs (p.y));
		}
		private int Quadrant (Point p) {
			return Math.Sign (p.x*p.y);
		}
	}

	public class LastSeenComparer : IComparer<Point> {
		int[,] map;
		public LastSeenComparer (int[,] map) {
			this.map = map;
		}
		public int Compare (Point x, Point y)
		{
			return map[x.x, x.y].CompareTo (map[y.x, y.y]);
		}
	}

	public enum TaskType {
		Food,
		Explore,
		EnemyHill,
		Defend,
		Support,
		None
	}

	public struct GoalPointer {
		public Point here;
		public Point next;
		public Goal goal;
		public int dist;
		public int cost;
		public GoalPointer (Point here, Point next, Goal goal, int dist, int cost) {
			this.here = here;
			this.next = next;
			this.goal = goal;
			this.dist = dist;
			this.cost = cost;
		}
	}

	public class PointCostComparer : IComparer<GoalPointer> {
		public int Compare (GoalPointer a, GoalPointer b) {
			return a.cost.CompareTo (b.cost);
		}
	}

	public class Order {
		public TaskType task;
		public Point goalPos;
		public Point goalPos2;
		public Point next;
		public Point next3;
		public int goalDist;
		public Order (GoalPointer pointer) {
			task = pointer.goal.task;
			goalPos = pointer.goal.position;
			goalPos2 = pointer.goal.position2;
			next = pointer.next;
			next3 = pointer.goal.map[next.x, next.y].next;
			next3 = pointer.goal.map[next.x, next.y].next;
			goalDist = pointer.dist;
		}
	}

	public enum CombatState {
		None,
		Attack,
		Flee
	}

	public enum Strength {
		Weaker = 0,
		NoThreat = 1,
		Stronger = 2
	}

	public class AntPlan {
		public Point here;
		public int chosenMoveIndex;
		public List<MoveEvaluation> moves;
		public Order order;
		public bool inBattle;
		public bool inDistress;
		public AntPlan (Point here) {
			this.here = here;
			chosenMoveIndex = 0;
			moves = new List<MoveEvaluation> ();
			order = null;
		}
		public void Sort () {
			moves.Sort ();
		}
		public MoveEvaluation chosenMove { get { return moves[chosenMoveIndex]; } }
		public Point chosenMovePos { get { return MyBot.state.GetDestination (here, chosenMove.move); } }
		public string MovesString () {
			return String.Format ("Ant "+here+" move {0,18} of {1,18} {2,18} {3,18} {4,18} {5,18}", moves[chosenMoveIndex], moves[0], moves[1], moves[2], moves[3], moves[4]);
		}
	}

	public struct MoveEvaluation : IComparable {
		public Move move;
		public bool blocked;
		public Strength strength;
		public int score;
		public MoveEvaluation (Move move) {
			this.move = move;
			blocked = false;
			strength = Strength.NoThreat;
			score = 0;
		}
		public int CompareTo (object obj) {
			MoveEvaluation o = (MoveEvaluation)obj;
			if (blocked != o.blocked)
				return blocked ? 1 : -1;
			return o.score.CompareTo (score);

		}
		public override string ToString () {
			if (blocked)
				return move+" ("+score+" blocked)";
			return move+" ("+score+" "+strength+") ";
		}
	}

	public class Goal {
		public Point position;
		public Point position2;
		public TaskType task;
		public int assigned;
		public int targetCount;
		public int maxDist;
		public GoalPointer[,] map;
		public Goal (Point position, Point position2, TaskType task, int targetCount, int maxDist, GoalPointer[,] map) {
			this.position = position;
			this.position2 = position2;
			this.task = task;
			this.targetCount = targetCount;
			this.maxDist = maxDist;
			assigned = 0;
			this.map = map;
		}
		public bool covered { get {
			return assigned >= targetCount;
		} }
	}

	public static class Extensions {
		// Fisher-Yates shuffle courtesy of StackOverflow
		public static IEnumerable<T> Shuffle<T> (this IEnumerable<T> source, Random rng) {
			T[] elements = source.ToArray ();
			// Note i > 0 to avoid final pointless iteration
			for (int i = elements.Length-1; i > 0; i--) {
				// Swap element "i" with a random earlier element it (or itself)
				int swapIndex = rng.Next (i + 1);
				T tmp = elements[i];
				elements[i] = elements[swapIndex];
				elements[swapIndex] = tmp;
			}
			// Lazily yield (avoiding aliasing issues etc)
			foreach (T element in elements) {
				yield return element;
			}
		}
	}

}
