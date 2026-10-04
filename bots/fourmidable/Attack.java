import java.io.*;
import java.util.*;

public final class Attack
{
  private final MyBot        bot;
  private final PrintStream  debugStream;
  private final Ants         ants;
  private final Overlay      overlay;

  private static class TargetInfo
  {
    public final Coord       target;
    public final boolean     visible;
    public final List<Route> indirectRoutes = new ArrayList<Route>();
    public final List<Route> directRoutes   = new ArrayList<Route>();
    public TargetInfo(Coord target, boolean visible) { this.target = target; this.visible = visible; }
  }

  public Attack(MyBot bot)
  {
    this.bot           = bot;
    this.debugStream   = bot.getDebugStream();
    this.ants          = bot.getAnts();
    this.overlay       = bot.getOverlay();
  }

  /**
   * In this method, each ant targets the closest visible, seen or inferred hill.
   * If the hill is visible, and we already have an overwhelming majority, target somewhere else.
   * @throws TimeRunningOutException
   */
  public void doAttackNearest() throws TimeRunningOutException
  {
    // Early exit
    if (bot.getFreeAnts().isEmpty()) return;

    // Debug
    if (debugStream != null) debugStream.println("\tattackNearest time = " + ants.getTurnTimeRemaining() + " free = " + bot.getFreeAnts().size());

    // Find targets
    bot.checkTime();
    boolean[][]           unblockedLand = bot.getUnblockedLand();
    ArrayList<TargetInfo> targets       = new ArrayList<TargetInfo>();
    ArrayList<Route>      directRoutes  = new ArrayList<Route>();
    for (int row = 0; row < Coord.rows; ++row) for (int col = 0; col < Coord.cols; ++col)
    {
      Tile tile = ants.getTile(row, col);
      if (tile.hasEnemyHill())
      {
        bot.checkTime();
        Coord      target       = tile.getCoord();
        TargetInfo info         = new TargetInfo(target, tile.isVisible());
        PathFinder directPath   = new PathFinder(bot.getLand(), target);
        PathFinder indirectPath = new PathFinder(unblockedLand, target);
        for (Coord ant : bot.getFreeAnts())
        {
          int direct = directPath.getDistance(ant);
          if (direct != PathFinder.NO_PATH)
          {
            Route route = new Route(ant, target, direct, directPath);
            info.directRoutes.add(route);
            directRoutes.add(route);
          }
          if (unblockedLand[ant.row][ant.col])
          {
            // If not in the block, compute indirect path.
            int indirect = indirectPath.getDistance(ant);
            if (indirect != PathFinder.NO_PATH) info.indirectRoutes.add(new Route(ant, target, indirect, indirectPath));
          }
        }
        for (Coord enemy : ants.getVisibleEnemyAnts())
        {
          int distance = directPath.getDistance(enemy);
          if (distance != PathFinder.NO_PATH)
          {
            Route route = new Route(enemy, target, distance, directPath);
            info.directRoutes.add(route);
            info.indirectRoutes.add(route);
          }
        }
        Collections.sort(info.directRoutes);
        Collections.sort(info.indirectRoutes);
        targets.add(info);
      }
    }
    if (targets.isEmpty())
    {
      if (debugStream != null) debugStream.println("\t\tNo target, time = " + ants.getTurnTimeRemaining() + " free = " + bot.getFreeAnts().size());
      return;
    }

    // Attack targets in order of preference
    for (;;)
    {
      // Exit conditions.
      bot.checkTime();
      if (bot.getFreeAnts().isEmpty()) break;

      // Select the best remaining target
      TargetInfo bestInfo  = null;
      double     bestScore = Integer.MIN_VALUE;
      for (TargetInfo info : targets)
      {
        double score = getScore(info);
        if (bestScore < score)
        {
          bestScore = score;
          bestInfo  = info;
        }
      }
      if (bestInfo == null) break;
      targets.remove(bestInfo);
      if (overlay != null && overlay.isActive(Overlay.Type.ATTACK)) overlay.star(bestInfo.target, 2, Overlay.LineColor.YELLOW);

      // Process indirect routes for all unblocked ants
      bot.checkTime();
      int balance = bestInfo.visible ? MyBot.ATTACK_MAJORITY : bot.getFreeAnts().size();
      for (Route route : bestInfo.indirectRoutes)
      {
        if (balance <= 0) break;
        Coord ant    = route.getAnt();
        Coord target = route.getDestination();
        if (ants.getTile(ant).hasVisibleEnemyAnt())
        {
          ++balance;
        }
        else if (bot.getFreeAnts().contains(ant))
        {
          --balance;
          List<Coord> moves = route.getPath().getSortedMoves(bot, ant);
          bot.doMoveIntelligently(ant,  moves);
          if (overlay != null && overlay.isActive(Overlay.Type.ATTACK)) overlay.arrow(ant, target, Overlay.LineColor.CYAN);
        }
      }
      if (balance > 0) for (Route route : bestInfo.directRoutes)
      {
        Coord ant    = route.getAnt();
        Coord target = route.getDestination();
        if (bot.getFreeAnts().contains(ant))
        {
          List<Coord> moves = route.getPath().getSortedMoves(bot, ant);
          bot.doMoveIntelligently(ant,  moves);
          if (overlay != null && overlay.isActive(Overlay.Type.ATTACK)) overlay.arrow(ant, target, Overlay.LineColor.MAGENTA);
        }
      }

      // Debug
      if (debugStream != null) debugStream.println("\t\thill = " + bestInfo.target + " score = " + bestScore + " free = " + bot.getFreeAnts().size());
    }

    // Move any remaining ant
    bot.checkTime();
    if (bot.getFreeAnts().size() != 0)
    {
      Collections.sort(directRoutes);
      for (Route route : directRoutes)
      {
        Coord ant    = route.getAnt();
        Coord target = route.getDestination();
        if (bot.getFreeAnts().contains(ant))
        {
          List<Coord> moves = route.getPath().getSortedMoves(bot, ant);
          bot.doMoveIntelligently(ant,  moves);
          if (overlay != null && overlay.isActive(Overlay.Type.ATTACK)) overlay.arrow(ant, target, Overlay.LineColor.MAGENTA);
        }
      }
    }
  }

  private double getScore(TargetInfo info)
  {
    int    limit  = Math.min(MyBot.ATTACK_MAJORITY, (bot.getFreeAnts().size() + 1)/2);
    double own    = 0.0;
    int[]  opp    = new int[MyBot.MAX_PLAYER];
    int    maxOpp = 0;
    for (Route route : info.directRoutes)
    {
      Tile tile = ants.getTile(route.getAnt());
      if (tile.hasOwnAnt())
      {
        own += 2000.0/(20.0 + route.getDistance());
        if (--limit <= 0) break;
      }
      else
      {
        int player = tile.getAnt() - 1;
        if (maxOpp < ++opp[player]) maxOpp = opp[player];
      }
    }
    double score = own - maxOpp;
    if (debugStream != null) debugStream.println("\t\ttarget = " + info.target + " own = " + own + " opp = " + maxOpp + " score = " + score);
    return score;
  }

  public void doAttackWeakest() throws TimeRunningOutException
  {
    // Early exit
    if (bot.getFreeAnts().isEmpty()) return;

    // Debug
    if (debugStream != null)
    {
      debugStream.println("\tattackWeakest time = " + ants.getTurnTimeRemaining() + " free = " + bot.getFreeAnts().size());
    }

    // Find weakest
    bot.checkTime();
    int   rows         = Coord.rows;
    int   cols         = Coord.cols;
    int[] antCount     = new int[MyBot.MAX_PLAYER + 1];
    int[] visibleCount = new int[MyBot.MAX_PLAYER + 1];
    int[] hillCount    = new int[MyBot.MAX_PLAYER + 1];
    for (int row = 0; row < rows; ++row) for (int col = 0; col < cols; ++col)
    {
      Tile tile = ants.getTile(row, col);
      ++antCount[tile.getAnt()]; // TODO_MPIOTTE check visible?
      ++hillCount[tile.getHill()];
      if (tile.isVisible()) ++visibleCount[tile.getAnt()];
    }
    int weakest = 0;
    for (int player = 2; player < antCount.length; ++player)
    {
      if (hillCount[player] > 0 && (weakest == 0 || antCount[player] < antCount[weakest])) weakest = player;
    }

    // Attack!
    if (weakest != 0)
    {
      // Find hills.
      ArrayList<Coord> hills = new ArrayList<Coord>();
      for (int row = 0; row < rows; ++row) for (int col = 0; col < cols; ++col)
      {
        Tile tile = ants.getTile(row, col);
        if (tile.getHill() == weakest) hills.add(tile.getCoord());
      }

      // Build routes.
      List<Route> directRoutes   = new ArrayList<Route>(bot.getFreeAnts().size()*hills.size());
      List<Route> indirectRoutes = new ArrayList<Route>(bot.getFreeAnts().size()*hills.size());
      boolean[][] unblockedLand  = bot.getUnblockedLand();
      boolean[][] land           = bot.getLand();
      for (Coord destination : hills)
      {
        bot.checkTime();
        PathFinder directPath   = new PathFinder(land, destination);
        PathFinder indirectPath = new PathFinder(unblockedLand, destination);
        for (Coord ant : bot.getFreeAnts())
        {
          int direct = directPath.getDistance(ant);
          if (direct != PathFinder.NO_PATH) directRoutes.add(new Route(ant, destination, direct, directPath));
          if (unblockedLand[ant.row][ant.col])
          {
            // If not in the block, compute indirect path.
            int indirect = indirectPath.getDistance(ant);
            if (indirect != PathFinder.NO_PATH) indirectRoutes.add(new Route(ant, destination, indirect, indirectPath));
          }
        }
      }
      Collections.sort(directRoutes);
      Collections.sort(indirectRoutes);

      // Process direct route of all blocked ants
      bot.checkTime();
      for (Route route : directRoutes)
      {
        Coord ant = route.getAnt();
        if (!unblockedLand[ant.row][ant.col] && bot.getFreeAnts().contains(ant))
        {
          List<Coord> moves = route.getPath().getSortedMoves(bot, ant);
          bot.doMoveIntelligently(ant,  moves);
          if (overlay != null && overlay.isActive(Overlay.Type.ATTACK)) overlay.arrow(ant,  route.getDestination(), Overlay.LineColor.MAGENTA);
        }
      }

      // Process indirect route for all unblocked ants
      bot.checkTime();
      for (Route route : indirectRoutes)
      {
        Coord ant = route.getAnt();
        if (bot.getFreeAnts().contains(ant))
        {
          List<Coord> moves = route.getPath().getSortedMoves(bot, ant);
          bot.doMoveIntelligently(ant,  moves);
          if (overlay != null && overlay.isActive(Overlay.Type.ATTACK)) overlay.arrow(ant,  route.getDestination(), Overlay.LineColor.CYAN);
        }
      }

      // Re-process direct routes for ants not indirectly routable.
      bot.checkTime();
      for (Route route : directRoutes)
      {
        Coord ant = route.getAnt();
        if (bot.getFreeAnts().contains(ant))
        {
          List<Coord> moves = route.getPath().getSortedMoves(bot, ant);
          bot.doMoveIntelligently(ant,  moves);
          if (overlay != null && overlay.isActive(Overlay.Type.ATTACK)) overlay.arrow(ant,  route.getDestination(), Overlay.LineColor.MAGENTA);
        }
      }

      if (debugStream != null)
      {
        debugStream.print("\t\tweakest = " + weakest + " visible = " + visibleCount[weakest] + " all = " + antCount[weakest] + " hills =");
        for (Coord hill : hills) debugStream.print(" (" + hill + ")");
        debugStream.println(" free = " + bot.getFreeAnts().size());
      }
    }
    else if (debugStream != null)
    {
      debugStream.println("\t\tNo enemy hill visible");
    }
  }
}
