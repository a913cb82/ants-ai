import java.io.*;
import java.util.*;


/**
 * This class is the main exploration engine for the games.
 * Given a random order of the tiles, it selects a set of tile that creates
 * a partially overlapping fied of vision. It then assigns ants to visit
 * based on best age/distance ratio.
 * Once an ant is simulated to reach its destination, it can be re-used
 * to visit the next one. A maximum distance is imposed to accelerate computation
 * and prevent impossible assignments.
 */
public final class Visitor
{
  private final MyBot       bot;
  private final PrintStream debugStream;
  private final Ants        ants;
  private final Overlay     overlay;

  public Visitor(MyBot bot)
  {
    this.bot           = bot;
    this.debugStream   = bot.getDebugStream();
    this.ants          = bot.getAnts();
    this.overlay       = bot.getOverlay();
  }

  public void doVisit() throws TimeRunningOutException
  {
    // Early exit
    if (bot.getFreeAnts().isEmpty()) return;

    // Debug
    if (debugStream != null) debugStream.println("\tdoVisit time = " + ants.getTurnTimeRemaining() + " free = " + bot.getFreeAnts().size());

    // Sort tiles by land/age
    bot.checkTime();
    List<Coord> tilesToExplore = bot.getTilesToExplore();
    Collections.sort(tilesToExplore, new Comparator<Coord>()
    {
      // Land first
      // Oldest second
      @Override
      public int compare(Coord c1, Coord c2)
      {
        // Prefer dry land
        Tile t1 = ants.getTile(c1);
        Tile t2 = ants.getTile(c2);
        if (!t1.hasWater() && t2.hasWater()) return -1;
        if (!t2.hasWater() && t1.hasWater()) return  1;

        // Prefer oldest
        if (t1.getAge() > t2.getAge()) return -1;
        if (t2.getAge() > t1.getAge()) return  1;

        // Equivalent
        return 0;
      }
    });

    // Select targets
    bot.checkTime();
    boolean[][] covered = new boolean[Coord.rows][Coord.cols];
    boolean[][] land    = bot.getLand();
    for (int row = 0; row < Coord.rows; ++row) for (int col = 0; col < Coord.cols; ++col) covered[row][col] = !land[row][col];
    List<CoordDistance> targetValues = new LinkedList<CoordDistance>();
    for (Coord target : tilesToExplore)
    {
      Tile tile = ants.getTile(target);
      if (tile.isVisible() || tile.hasWater()) break;
      if (!covered[target.row][target.col])
      {
        int  value = 0;
        for (StencilIterator iter = new StencilIterator(target, MyBot.OBSERVE_COVER2, 0); iter.hasNext();)
        {
          Coord c               = iter.next();
          Tile  t               = ants.getTile(c);
          covered[c.row][c.col] = true;
          if (!t.hasWater()) value += t.getAge();
        }
        targetValues.add(new CoordDistance(target, value));
      }
    }

    // Move through unblocked land first
    assignOrders(bot.getUnblockedLand(), targetValues);
    assignOrders(bot.getLand(), targetValues);
  }

  private void assignOrders(boolean[][] passable, List<CoordDistance> targetValues) throws TimeRunningOutException
  {
    // Make heap of unblocked visits, as well as blocked visits if no unblocked
    Heap<VisitorCandidate> heap = new Heap<VisitorCandidate>();
    for (Iterator<CoordDistance> iter = targetValues.iterator(); iter.hasNext();)
    {
      bot.checkTime();
      CoordDistance targetValue = iter.next();
      Coord         target      = targetValue.coord;
      if (passable[target.row][target.col])
      {
        PathFinder path         = new PathFinder(passable, target);
        Coord      bestAnt      = null;
        int        bestDistance = PathFinder.NO_PATH;
        for (Coord ant : bot.getFreeAnts())
        {
          if (passable[ant.row][ant.col])
          {
            int d = path.getDistance(ant, MyBot.OBSERVE_RANGE);
            if (bestDistance > d)
            {
              bestDistance = d;
              bestAnt      = ant;
            }
          }
        }
        if (bestAnt != null)
        {
          iter.remove();
          VisitorCandidate vc = new VisitorCandidate(bestAnt, target, targetValue.distance, 1.0*targetValue.distance/(bestDistance + 1), path);
          heap.add(vc);
        }
      }
    }

    // Assign movement
    while (!heap.isEmpty())
    {
      bot.checkTime();
      VisitorCandidate vc = heap.removeFirst();
      bot.doMoveIntelligently(vc.ant, vc.path.getSortedMoves(bot, vc.ant));
      if (overlay != null && overlay.isActive(Overlay.Type.VISIT)) overlay.arrow(vc.ant, vc.target, Overlay.LineColor.WHITE);

      // Remove any matching obsoleted.
      ArrayList<VisitorCandidate> obsoletes = new ArrayList<VisitorCandidate>();
      for (Iterator<VisitorCandidate> iter = heap.iterator(); iter.hasNext(); )
      {
        VisitorCandidate obsolete = iter.next();
        if (obsolete.ant.equals(vc.ant))
        {
          iter.remove();
          obsoletes.add(obsolete);
        }
      }

      // Build new matchings
      for (VisitorCandidate obsolete : obsoletes)
      {
        Coord bestAnt      = null;
        int   bestDistance = PathFinder.NO_PATH;
        for (Coord ant : bot.getFreeAnts())
        {
          if (passable[ant.row][ant.col])
          {
            int d = obsolete.path.getDistance(ant, MyBot.OBSERVE_RANGE);
            if (bestDistance > d)
            {
              bestDistance = d;
              bestAnt      = ant;
            }
          }
        }
        if (bestAnt != null)
        {
          vc = new VisitorCandidate(bestAnt, obsolete.target, obsolete.value, 1.0*obsolete.value/(bestDistance + 1), obsolete.path);
          heap.add(vc);
        }
      }
    }
  }
}
