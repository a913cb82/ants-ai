using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;

namespace Ants {

	public class Ants {

		private static Ants instance;

		public static readonly Point North = new Point(-1, 0);
		public static readonly Point South = new Point(1, 0);
		public static readonly Point West = new Point(0, -1);
		public static readonly Point East = new Point(0, 1);
		public static readonly Point Stay = new Point(0, 0);

		public static List<Direction> Directions = new List<Direction> {
			Direction.North,
			Direction.South,
			Direction.East,
			Direction.West
		};

		public static List<Move> Moves = new List<Move> {
			Move.North,
			Move.South,
			Move.East,
			Move.West,
			Move.Stay
		};

		public static IDictionary<Direction, Point> Aim = new Dictionary<Direction, Point> {
			{ Direction.North, North},
			{ Direction.South, South},
			{ Direction.East, East},
			{ Direction.West, West}
		};

		public static IDictionary<Move, Point> Aim2 = new Dictionary<Move, Point> {
			{ Move.North, North},
			{ Move.South, South},
			{ Move.East, East},
			{ Move.West, West},
			{ Move.Stay, Stay}
		};

		public static IDictionary<Point, Move> GetAim = new Dictionary<Point, Move> {
			{ North, Move.North},
			{ South, Move.South},
			{ East, Move.East},
			{ West, Move.West},
			{ Stay, Move.Stay}
		};

		private const string READY = "ready";
		private const string GO = "go";
		private const string END = "end";

		private GameState state;
		private Random rand;

		private MyBot bot;

		public static void Log (string str) {
			instance.bot.Log (str);
		}

		public static void LogGlobal (string str) {
			Log (str);
			FileStream fs = Ants.GetStream (Ants.kGlobalLogFile, FileMode.Append, FileAccess.Write);
			StreamWriter writer = new StreamWriter (fs);
			writer.WriteLine (str);
			writer.Close ();
			fs.Close ();
		}


		public void PlayGame (Bot bot, string[] args) {
			instance = this;
			this.bot = bot as MyBot;
			#if DEBUG
			rand = new Random ();
			//string logPath;
			botSlot = 0;
			while (true) {
				try {
					this.bot.fileStream = new FileStream (
						"logs/AntLog_"+DateTime.Now+"-"+botSlot+".txt",
						FileMode.Create, FileAccess.Write, FileShare.None);
					this.bot.writer = new StreamWriter (this.bot.fileStream);
					break;
				}
				catch (Exception e) {
					if (Math.Abs(1) == -1)
						throw e;
					botSlot++;
				}
			}

			Log ("Init Bot Log (slot "+botSlot+")");
			#endif


			List<string> input = new List<string>();

			#if DEBUG
			try {
			#endif
				int turn = 0;
				while (true) {
					string line = System.Console.In.ReadLine().Trim().ToLower();

					if (line.Equals(READY)) {
						ParseSetup(input);
						FinishTurn();
						input.Clear();
						#if DEBUG
						if (args.Length > 0 && args[0] == "fixed")
							FixedParametersSetup ();
						else
							DebugSetup ();
						#else
						FixedParametersSetup ();
						#endif
					} else if (line.Equals(GO)) {
						state.StartNewTurn();
						ParseUpdate(input);
						bot.DoTurn(state);
						FinishTurn();
						input.Clear();
						if (turn%10 == 0)
							GC.Collect ();
						turn++;
					} else if (line.Equals(END)) {
						input.Clear();
						break;
					} else {
						input.Add(line);
					}
				}
			#if DEBUG
			} catch (Exception e) {
				FileStream fs = new FileStream ("debug_"+botSlot+".log", System.IO.FileMode.Create, System.IO.FileAccess.Write);
				StreamWriter writer = new StreamWriter(fs);
				writer.WriteLine(e);
				writer.Close();
				fs.Close();
			}
			#endif

			// End processing

			#if DEBUG
			try {
				while (true) {
					string line = System.Console.In.ReadLine().Trim().ToLower();

					if (line.Equals(GO)) {
						ParseEnd(input);
						input.Clear();
					} else {
						input.Add(line);
					}
				}
			} catch (Exception e) {
				FileStream fs = new FileStream ("debug_"+botSlot+".log", System.IO.FileMode.Create, System.IO.FileAccess.Write);
				StreamWriter writer = new StreamWriter(fs);
				writer.WriteLine(e);
				writer.Close();
				fs.Close();
			}
			#endif

		}

		// parse initial input and setup starting game state
		private void ParseSetup(List<string> input) {
			int width = 0, height = 0;
			int turntime = 0, loadtime = 0;
			int viewradius2 = 0, attackradius2 = 0, spawnradius2 = 0;

			foreach (string line in input) {
				if (line.Length <= 0) continue;

				string[] tokens = line.Split();
				string key = tokens[0];

				if (key.Equals(@"cols")) {
					width = int.Parse(tokens[1]);
				} else if (key.Equals(@"rows")) {
					height = int.Parse(tokens[1]);
				} else if (key.Equals(@"seed")) {
					;
				} else if (key.Equals(@"turntime")) {
					turntime = int.Parse(tokens[1]);
				} else if (key.Equals(@"loadtime")) {
					loadtime = int.Parse(tokens[1]);
				} else if (key.Equals(@"viewradius2")) {
					viewradius2 = int.Parse(tokens[1]);
				} else if (key.Equals(@"attackradius2")) {
					attackradius2 = int.Parse(tokens[1]);
				} else if (key.Equals(@"spawnradius2")) {
					spawnradius2 = int.Parse(tokens[1]);
				}
			}

			this.state = new GameState(width, height,
			                           turntime, loadtime,
			                           viewradius2, attackradius2, spawnradius2);
		}

		private void FixedParametersSetup () {
			BotInfo info = new BotInfo (-1);
			//info.parameters["DefenceAmount"] = 12; // 25
			//info.parameters["EnemyVisionCost"] = 83; // 50;
			//info.parameters["EnemyAntCost"] = 17; // 50;
			//info.parameters["AllyVisionCost"] = 100; // 0;
			//info.parameters["AllyAntCost"] = 150; // 50;
			//info.parameters["EnemyHeatCost"] = 38; // 38;
			//info.parameters["AllyHeatCost"] = 38; // 30;

			info.parameters["MajorityBonus"] = 287; // 294;
			info.parameters["MajorityThreshold"] = 6; // 5
			info.parameters["BattleGoalCost"] = 42; // 25
			info.parameters["BattleGoalRange"] = 13; // 13
			info.parameters["BattleGoalAmount"] = 20; // 10
			info.parameters["OnlyBullies"] = 0;
			info.parameters["ClearMidway"] = 0;
			info.parameters["TakeRiskAtTie"] = 1;
			bot.SetupParameters (info);
		}

		// parse engine input and update the game state
		private void ParseUpdate(List<string> input) {
			// do some stuff first

			foreach (string line in input) {
				if (line.Length <= 0) continue;

				string[] tokens = line.Split();

				if (tokens.Length >=3) {
					int row = int.Parse(tokens[1]);
					int col = int.Parse(tokens[2]);

					if (tokens[0].Equals("a")) {
						state.AddAnt(row, col, int.Parse(tokens[3]));
					} else if (tokens[0].Equals("f")) {
						state.AddFood(row, col);
					} else if (tokens[0].Equals("r")) {
						state.RemoveFood(row, col);
					} else if (tokens[0].Equals("w")) {
						state.AddWater(row, col);
					} else if (tokens[0].Equals("d")) {
						state.DeadAnt(row, col);
					} else if (tokens[0].Equals("h")) {
						state.AntHill (row, col, int.Parse(tokens[3]));
					}
				}
			}
		}

		private void FinishTurn () {
			System.Console.Out.WriteLine(GO);
		}

		// parse end score
		private void ParseEnd (List<string> input) {
			int players = 0;
			int score = 0;
			int minScore = 1000;
			int maxScore = 0;

			foreach (string line in input) {
				if (line.Length <= 0) continue;

				string[] tokens = line.Split();
				string key = tokens[0];

				if (key.Equals(@"players")) {
					if (botSlot == 0) {
						players = int.Parse(tokens[1]);
						string str = "Played game with bots ";
						string[] botsInGame = games[0].Split (new char[] {' '}, StringSplitOptions.RemoveEmptyEntries);
						for (int i=0; i<players; i++)
							str += string.Format ("{0,3} ", botsInGame[i]);
						LogGlobal (str);
					}
				} else if (key.Equals(@"score")) {
					score = 0;
					if (!int.TryParse (tokens[1], out score))
						LogGlobal ("Couldn't parse token 1 in end line: "+line);
					for (int i=1; i<tokens.Length; i++) {
						int antScore = 0;
						if (!int.TryParse (tokens[i], out antScore))
							LogGlobal ("Couldn't parse token "+i+" in end line: "+line);
						maxScore = Math.Max (maxScore, antScore);
						minScore = Math.Min (minScore, antScore);
					}
				}
			}
			int percentage;
			if (minScore == maxScore)
				percentage = 50;
			else
				percentage = 100 * (score - minScore) / (maxScore - minScore);

			FileStream fs = GetStream (kResultsFile, FileMode.Append, FileAccess.Write);
			StreamWriter writer = new StreamWriter(fs);
			writer.WriteLine(thisBot.id+":"+percentage);
			writer.Close();
			fs.Close();

			if (botSlot == 0) {
				games.RemoveAt (0);
				WriteScheduledGames ();
			}

			// Rename file
			string name = this.bot.fileStream.Name;
			string newName = name.Substring (0, name.Length-5) + "Bot_" + thisBot.id + " (" + botSlot + ").txt";
			Log ("Renaming "+name+"  to "+newName);
			bot.writer.Close ();
			bot.fileStream.Close ();

			var tries = 0;
			while (true)
			{
				try
				{
					File.Move (name, newName);
					break;
				}
				catch (IOException e)
				{
					if (++tries > kNumberOfTries)
						throw new Exception("The file is locked too long: " + e.Message, e);
					System.Threading.Thread.Sleep (kTimeIntervalBetweenTries);
				}
			}
		}

		public const int kBotsPoolSize = 5;
		public const int kNumLastGamesToEvaluate = 10;

		public const string kParametersFile = "data/parameters.txt";
		public const string kBotsFile = "data/bots.txt";
		public const string kScheduleFile = "data/schedule.txt";
		public const string kResultsFile = "data/results.txt";
		public const string kStatsFile = "data/stats.txt";
		public const string kGlobalLogFile = "data/globallog.txt";

		private int botSlot = -1;
		private BotInfo thisBot;
		private bool isPrimaryBot { get { return botSlot == 0; } }
		List<string> games;

		public void DebugSetup () {

			if (Directory.Exists ("data"))
				Directory.CreateDirectory ("data");

			FileStream fs = GetStream (kParametersFile, FileMode.Open, FileAccess.Read);
			StreamReader reader = new StreamReader (fs);
			List<ParameterInfo> parameters = ReadParameters (reader);
			if (botSlot > 0) {
				reader.Close ();
				fs.Close ();
			}

			games = new List<string> ();

			List<BotInfo> bots = ReadBots (parameters);

			GetScheduledGames (parameters, bots);

			if (botSlot == 0) {
				reader.Close ();
				fs.Close ();
			}

			Log ("Games: "+games.Count+" Bots:"+bots.Count);

			HandleGameStatus (bots);
		}

		private List<ParameterInfo> ReadParameters (StreamReader reader) {
			// Read parameter info
			Log ("Reading parameter info");
			List<ParameterInfo> parameters = new List<ParameterInfo> ();
			while (!reader.EndOfStream)
				parameters.Add (new ParameterInfo (reader.ReadLine ()));
			return parameters;
		}

		private List<BotInfo> ReadBots (List<ParameterInfo> parameters) {
			// Read existing bots
			List<BotInfo> bots = new List<BotInfo> ();

			Log ("Reading existing bots");
			while (bots.Count == 0) {
				// Read bots
				FileStream fs = GetStream (kBotsFile, FileMode.OpenOrCreate, FileAccess.Read);
				StreamReader reader = new StreamReader (fs);
				while (!reader.EndOfStream) {
					string str = reader.ReadLine ();
					Log ("   Reading: "+str);
					bots.Add (new BotInfo (str, parameters));
				}
				reader.Close ();
				fs.Close ();

				// If no bots, create initial random bots
				if (bots.Count == 0) {
					if (botSlot == 0) {
						LogGlobal ("Creating initial random bots");
						for (int i=0; i<kBotsPoolSize; i++) {
							bots.Add (BotInfo.RandomBot (i, parameters, rand));
							bots[i].WriteToFile ();
						}

						// Schedule initial games
						fs = GetStream (kScheduleFile, FileMode.OpenOrCreate, FileAccess.Write);
						StreamWriter writer = new StreamWriter (fs);
						for (int i=0; i<kBotsPoolSize; i++) {
							string gameLine = i+" "+((i+1) % kBotsPoolSize)+" ";
							for (int j=0; j<8; j++)
								gameLine += rand.Next (kBotsPoolSize) + " ";
							games.Add (gameLine);
							writer.WriteLine (gameLine);
						}
						writer.Close ();
						fs.Close ();
					}
					else {
						System.Threading.Thread.Sleep (kTimeIntervalBetweenTries);
					}
				}
			}

			return bots;
		}

		private void GetScheduledGames (List<ParameterInfo> parameters, List<BotInfo> bots) {
			Log ("Getting scheduled games");
			while (games.Count == 0) {
				ReadScheduledGames ();
				if (games.Count == 0) {
					if (botSlot == 0)
						BreedNewBotAndScheduleGames (bots, parameters);
					else
						System.Threading.Thread.Sleep (kTimeIntervalBetweenTries);
				}
			}
		}

		private void ReadScheduledGames () {
			// Read scheduled games
			FileStream fs = GetStream (kScheduleFile, FileMode.OpenOrCreate, FileAccess.Read);
			StreamReader reader = new StreamReader (fs);
			while (!reader.EndOfStream)
				games.Add (reader.ReadLine ());
			reader.Close ();
			fs.Close ();
		}

		private void WriteScheduledGames () {
			// Write scheduled games
			Log ("Writing scheduled games");
			FileStream fs = GetStream (kScheduleFile, FileMode.Create, FileAccess.Write);
			StreamWriter writer = new StreamWriter (fs);
			foreach (string game in games)
				writer.WriteLine (game);
			writer.Close ();
			fs.Close ();
		}

		private void BreedNewBotAndScheduleGames (List<BotInfo> bots, List<ParameterInfo> parameters) {
			// Evaluate best bots
			Log ("Evaluating best bots");
			List<BotResults> botScores = GetBestBotIds (bots, parameters);
			List<BotResults> botPriorities = new List<BotResults> (botScores);
			botPriorities.Sort (new BotPriorityComparer ());

			// Create new bot from best bots
			if (botPriorities[0].games > 5 && botPriorities[1].games > 5) {
				LogGlobal ("Breeding new bot from bot "+botScores[0].id+" and "+botScores[1].id);
				BotInfo newBot = BreedNewBotFromParents (bots.Count, bots, botScores[0].id, botScores[1].id, parameters);
				bots.Add (newBot);
				newBot.WriteToFile ();
				BotResults newBotScore = new BotResults ();
				newBotScore.id = newBot.id;
				newBotScore.games = 0;
				newBotScore.avgAllTime = 0;
				newBotScore.avgLastN = 0;
				botPriorities.Insert (0, newBotScore);
			}

			Log ("Scheduling games");
			FileStream fs = GetStream (kScheduleFile, FileMode.OpenOrCreate, FileAccess.Write);
			StreamWriter writer = new StreamWriter (fs);
			string gameLine = "";
			if (rand.Next (4) > 0) {
				// Go against best other bots using recent games rankings
				for (int j=0; j<10; j++)
					gameLine += botPriorities[j % botPriorities.Count].id + " ";
			}
			else {
				// Go against best other bots using all-time games rankings
				List<BotResults> botAllTimeScores = new List<BotResults> (botPriorities);
				botAllTimeScores.Sort (new BotScoreAllTimeComparer ());
				gameLine += botPriorities[0].id + " ";
				int added = 0;
				int j = 0;
				while (added < 9) {
					BotResults r = botAllTimeScores[j % botAllTimeScores.Count];
					if (r.id != botPriorities[0].id) {
						gameLine += r.id + " ";
						added++;
					}
					j++;
				}
			}
			games.Add (gameLine);
			writer.WriteLine (gameLine);
			writer.Close ();
			fs.Close ();
		}

		private void HandleGameStatus (List<BotInfo> bots) {
			// Read scheduled game and assume bot parameters
			Log ("Handling game status");
			Log ("   Game: "+games[0]);
			string[] botsInGame = games[0].Split (new char[] {' '}, StringSplitOptions.RemoveEmptyEntries);
			Log ("   Bots in this game: "+botsInGame.Length);
			int thisBotId = Int32.Parse (botsInGame[botSlot]);
			Log ("   This bot id: "+thisBotId);
			thisBot = bots[thisBotId];
			bot.SetupParameters (thisBot);
		}

		private bool BotsAreDifferent (BotInfo a, BotInfo b, List<ParameterInfo> parameters) {
			bool anyDifferent = false;
			foreach (ParameterInfo p in parameters) {
				if (p.boolean) {
					if (a.parameters[p.name] != b.parameters[p.name])
						return true;
				}
				else {
					if (a.parameters[p.name] != b.parameters[p.name] &&
						Math.Abs (a.parameters[p.name] - b.parameters[p.name]) > ((p.max-p.min)/20))
						return true;
				}
			}
			return false;
		}

		private bool BotIsDifferentFromRest (BotInfo n, List<BotInfo> bots, List<ParameterInfo> parameters) {
			foreach (BotInfo existing in bots) {
				if (!BotsAreDifferent (n, existing, parameters))
					return false;
			}
			return true;
		}

		private BotInfo BreedNewBotFromParents (int id, List<BotInfo> bots, int idA, int idB, List<ParameterInfo> parameters) {
			BotInfo n = new BotInfo (id);
			BotInfo a = bots[idA];
			BotInfo b = bots[idB];
			bool different = false;
			bool allClose = true;
			for (int tries=0; tries<3; tries++) {
				allClose = true;
				foreach (ParameterInfo p in parameters) {
					int valA = a.parameters[p.name];
					int valB = b.parameters[p.name];
					int min = Math.Min (valA, valB);
					int max = Math.Max (valA, valB);
					int diff = (max-min);
					int val;
					if (p.boolean || Math.Abs (valA - valB) <= 1)
						val = ((rand.Next (2) == 0) ? valA : valB);
					else
						val = rand.Next (min+1, max-1 + 1);
					//int val = (min + max) / 2;
					val = Math.Min (val, p.max);
					val = Math.Max (val, p.min);
					n.parameters[p.name] = val;

					if (diff > 1 && (diff * 100 / (p.max - p.min)) >= 3)
						allClose = false;
					if (p.boolean && diff > 0)
						allClose = false;
				}
				if (BotIsDifferentFromRest (n, bots, parameters)) {
					different = true;
					break;
				}
			}
			if (allClose)
				LogGlobal ("   All parameters are close in parents");
			if (allClose || different == false || rand.Next (3) == 0) {
				while (true) {
					// Use first parent
					foreach (ParameterInfo p in parameters) {
						int valA = a.parameters[p.name];
						n.parameters[p.name] = valA;
					}
					// Make a random of the parameters have a random value
					ParameterInfo pa = parameters[0];
					int val = 0;
					int c = 0;
					while (c<50) {
						int i = rand.Next (parameters.Count);
						pa = parameters[i];
						int valA = a.parameters[pa.name];
						int valB = b.parameters[pa.name];
						int min = Math.Min (valA, valB);
						int max = Math.Max (valA, valB);
						int diff = (max-min);
						val = rand.Next (pa.min, pa.max);
						if (val < min - diff/10 || val > max + diff/10)
							break;
						if (pa.boolean && valA == valB) {
							val = 1 - valA;
							break;
						}
						c++;
					}
					n.parameters[pa.name] = val;

					// Check if bot is identical to existing bot
					if (BotIsDifferentFromRest (n, bots, parameters)) {
						LogGlobal ("   Giving parameter "+pa.name+" random value of "+val);
						break;
					}
				}
			}
			return n;
		}

		private List<BotResults> GetBestBotIds (List<BotInfo> bots, List<ParameterInfo> parameters) {
			StreamReader reader;
			FileStream fs;

			// Initialize dictionaries
			Dictionary<int, List<int>> botsResults = new Dictionary<int, List<int>> ();
			foreach (BotInfo botInfo in bots)
				botsResults[botInfo.id] = new List<int> ();

			/*Dictionary<string, Dictionary<int, Point>> parameterValueResults =
				new Dictionary<string, Dictionary<int, Point>> ();
			foreach (ParameterInfo par in parameters) {
				parameterValueResults[par.name] = new Dictionary<int, Point> ();
			}*/

			// Get bot results of previous games
			fs = GetStream (kResultsFile, FileMode.OpenOrCreate, FileAccess.Read);
			reader = new StreamReader (fs);
			while (!reader.EndOfStream) {
				string line = reader.ReadLine ();
				Log ("Reading: "+line);
				string[] str = line.Split (':');
				int botId = Int32.Parse (str[0]);
				int result = Int32.Parse (str[1]);
				botsResults[botId].Add (result);

				// Record parameter stats
				/*foreach (ParameterInfo param in parameters) {
					int val = bots[botId].parameters[param.name];
					if (!parameterValueResults[param.name].ContainsKey (val))
						parameterValueResults[param.name][val] = new Point (0, 0);
					Point p = parameterValueResults[param.name][val];
					p.x = p.x + 1;
					p.y = p.y + result;
					parameterValueResults[param.name][bots[botId].parameters[param.name]] = p;
				}*/
			}

			reader.Close ();
			fs.Close ();

			// Record average result of up to kNumLastGamesToEvaluate last games
			List<BotResults> botScores = new List<BotResults> ();
			foreach (KeyValuePair<int, List<int>> kvp in botsResults) {
				BotResults r = new BotResults ();
				r.id = kvp.Key;
				int sum = 0;
				int sumAll = 0;
				int c = 0;
				for (int i=kvp.Value.Count-1; i >= 0; i--) {
					if (c < kNumLastGamesToEvaluate)
						sum += kvp.Value[i];
					sumAll += kvp.Value[i];
					c++;
				}
				r.games = kvp.Value.Count;
				r.avgLastN = sum / Math.Max (1, Math.Min (kNumLastGamesToEvaluate, kvp.Value.Count));
				r.avgAllTime = sumAll / Math.Max (1, kvp.Value.Count);
				botScores.Add (r);
			}
			botScores.Sort (new BotScoreComparer ());

			// Return list with ids of best bots
			fs = GetStream (kStatsFile, FileMode.Create, FileAccess.Write);
			StreamWriter writer = new StreamWriter (fs);
			foreach (BotResults r in botScores) {
				Log ("   Adding: "+r);
				writer.WriteLine (r+"  |  "+bots[r.id]);
			}

			writer.Close ();
			fs.Close ();

			Log ("   Done");
			return botScores;
		}

		private const int kNumberOfTries = 20;
		private const int kTimeIntervalBetweenTries = 5;

		public static FileStream GetStream (string fileName, FileMode fileMode, FileAccess fileAccess)
		{
			var tries = 0;
			while (true)
			{
				try
				{
					return File.Open (fileName, fileMode, fileAccess, FileShare.None);
				}
				catch (IOException e)
				{
					if (!IsFileLocked (e))
						throw;
					if (++tries > kNumberOfTries)
						throw new Exception("The file is locked too long: " + e.Message, e);
					System.Threading.Thread.Sleep (kTimeIntervalBetweenTries);
				}
			}
		}

		private static bool IsFileLocked (IOException exception)
		{
			return true;
			//int errorCode = Marshal.GetHRForException(exception) & ((1 << 16) - 1);
			//return errorCode == 32 || errorCode == 33;
		}

	}

	public class BotScoreComparer : IComparer<BotResults> {
		public int Compare (BotResults x, BotResults y)
		{
			return y.avgLastN.CompareTo (x.avgLastN);
		}
	}

	public class BotScoreAllTimeComparer : IComparer<BotResults> {
		public int Compare (BotResults x, BotResults y)
		{
			return y.avgAllTime.CompareTo (x.avgAllTime);
		}
	}

	public class BotPriorityComparer : IComparer<BotResults> {
		public int Compare (BotResults x, BotResults y)
		{
			return y.priority.CompareTo (x.priority);
		}
	}

	public struct BotResults {
		public int id;
		public int games;
		public int avgLastN;
		public int avgAllTime;
		public int priority { get {
			if (games >= Ants.kNumLastGamesToEvaluate)
				return avgLastN;
			// Pretend one full score to boost bots with few played games
			int pretendGames = (Ants.kNumLastGamesToEvaluate - games) / 2 + 1;
			return (avgLastN * games + 100*pretendGames) / (games + pretendGames);
		} }
		public override string ToString ()
		{
			return string.Format ("Bot {0,3}  games: {1,3}  avg-all: {2,3}  avg-last-{3}: {4,3}  priority: {5,3}",
				id, games, avgAllTime, Ants.kNumLastGamesToEvaluate, avgLastN, priority);
		}
	}

	public class BotInfo {
		public int id;
		public Dictionary<string, int> parameters = new Dictionary<string, int> ();
		public BotInfo (int id) {
			this.id = id;
		}
		public BotInfo (string info, List<ParameterInfo> paramInfos) {
			string[] parts = info.Split (':');
			id = Int32.Parse (parts[0]);
			string[] prms = parts[1].Split (new char[] {' '}, StringSplitOptions.RemoveEmptyEntries);
			foreach (string parameter in prms) {
				string[] keyval = parameter.Split ('=');
				parameters[keyval[0]] = Int32.Parse (keyval[1]);
			}
			foreach (ParameterInfo param in paramInfos) {
				if (!parameters.ContainsKey (param.name))
					parameters[param.name] = param.def;
			}
		}
		public static BotInfo RandomBot (int id, List<ParameterInfo> parameterInfo, Random rand) {
			BotInfo bot = new BotInfo (id);
			foreach (ParameterInfo pi in parameterInfo)
				bot.parameters[pi.name] = rand.Next (pi.min, pi.max + 1);
			return bot;
		}
		public void WriteToFile () {
			FileStream fs = Ants.GetStream (Ants.kBotsFile, FileMode.Append, FileAccess.Write);
			string str = this.ToString ();
			StreamWriter writer = new StreamWriter (fs);
			Ants.LogGlobal ("   Writing: "+str);
			writer.WriteLine (str);
			writer.Close ();
			fs.Close ();
		}
		public override string ToString ()
		{
			string str = string.Format ("{0, 3}:  ", id);
			foreach (KeyValuePair<string, int> kvp in parameters)
				str += string.Format ("{0}={1,-4}  ", kvp.Key, kvp.Value);
			return str;
		}
	}

	public class ParameterInfo {
		public string name;
		public int min;
		public int max;
		public int def;
		public bool boolean { get { return (max-min == 1); } }
		public ParameterInfo (string info) {
			string[] inf = info.Split (new char[] {' '}, StringSplitOptions.RemoveEmptyEntries);
			name = inf[0];
			min = Int32.Parse(inf[1]);
			max = Int32.Parse(inf[2]);
			if (inf.Length > 3)
				def = Int32.Parse(inf[3]);
		}
	}
}
