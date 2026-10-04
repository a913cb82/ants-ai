using System;
using System.Collections.Generic;

namespace Ants {
	public abstract class Bot {

		public abstract void DoTurn(GameState state);

		protected void IssueOrder(Point loc, Direction direction) {
			System.Console.Out.WriteLine("o {0} {1} {2}", loc.x, loc.y, direction.ToChar());
		}

		protected void IssueOrder(Point loc, Move move) {
			if (move != Move.Stay)
				System.Console.Out.WriteLine("o {0} {1} {2}", loc.x, loc.y, move.ToChar());
		}

		public abstract void SetupParameters (BotInfo info);
	}
}
