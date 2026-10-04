import java.io.*;
import java.util.*;

public final class Hunt
{
  private final MyBot       bot;
  private final PrintStream debugStream;
  private final Ants        ants;
  private final Overlay     overlay;

  public Hunt(MyBot bot)
  {
    this.bot         = bot;
    this.debugStream = bot.getDebugStream();
    this.ants        = bot.getAnts();
    this.overlay     = bot.getOverlay();
  }

  public void doHunt(Coord hill) throws TimeRunningOutException
  {
    // Early exit
    if (hill == null) return;
    int threshold = (int)Math.ceil((1.0 - MyBot.HUNT_RATIO)*bot.getFreeAnts().size());
    if (bot.getFreeAnts().size() <= threshold) return;

    // Debug
    if (debugStream != null)
    {
      debugStream.println("\tdoHunt time = " + ants.getTurnTimeRemaining() + " free = " + bot.getFreeAnts().size() + " threshold = " + threshold);
    }

    // Select enemy targets
    boolean[][]         land         = bot.getLand();
    boolean[][]         unblocked    = bot.getUnblockedLand();
    PathFinder          hillPath     = new PathFinder(land, hill);
    List<CoordDistance> targetValues = new LinkedList<CoordDistance>();
    for (Coord enemy : ants.getVisibleEnemyAnts())
    {
      int value = hillPath.getDistance(enemy);
      if (value != PathFinder.NO_PATH) targetValues.add(new CoordDistance(enemy, value));
    }

    // Issue orders
    Collections.sort(targetValues);
    for (CoordDistance cd : targetValues)
    {
      bot.checkTime();
      if (bot.getFreeAnts().size() <= threshold) break;
      Coord      target        = cd.coord;
      PathFinder unblockedPath = new PathFinder(unblocked, target);
      PathFinder landPath      = null;
      for (int i = 0; i < MyBot.HUNT_STRENGHT && bot.getFreeAnts().size() > threshold; ++i)
      {
        if (!issueOrder(hill, target, hillPath, unblockedPath))
        {
          if (landPath == null) landPath = new PathFinder(land, target);
          if (!issueOrder(hill, target, hillPath, landPath)) break;
        }
      }
    }
  }

  private boolean issueOrder(Coord hill, Coord target, PathFinder hillpath, PathFinder targetPath)
  {
    Coord      best        = null;
    int        target2hill = hillpath.getDistance(target);
    int        distance    = Integer.MAX_VALUE;
    for (Coord ant : bot.getFreeAnts())
    {
      if (targetPath.isPassable(ant))
      {
        int ant2hill   = hillpath.getDistance(ant);
        int ant2target = targetPath.getDistance(ant);
        if (ant2hill <= target2hill && ant2target <= target2hill && ant2target < distance)
        {
          distance = ant2target;
          best     = ant;
        }
      }
    }
    if (best != null)
    {
      bot.doMoveIntelligently(best, targetPath.getSortedMoves(bot, best));
      if (overlay != null && overlay.isActive(Overlay.Type.HUNT)) overlay.arrow(best, target, Overlay.LineColor.YELLOW);
      return true;
    }
    return false;
  }
}
