import java.io.*;
import java.util.*;

public final class Defense
{
  private final MyBot       bot;
  private final PrintStream debugStream;
  private final Ants        ants;

  public Defense(MyBot bot)
  {
    this.bot           = bot;
    this.debugStream   = bot.getDebugStream();
    this.ants          = bot.getAnts();
  }

  /**
   * This method defends our last anthill.
   * It finds all ants within DEFENSE_RANGE of our hill.
   * The objective is to have a strict majority of ants at all distances.
   * If not, for N enemy in range we move N + 1 ants toward our hill.
   * Also, if no enemy, we still keep one ant close to provide vision.
   * Initially disabled to avoid impeding the initial growth phase.
   * @throws TimeRunningOutException
   */
  public void doDefend(Coord hillToDefend) throws TimeRunningOutException
  {
    // Defend if only one hill
    Set<Coord> freeAnts = bot.getFreeAnts();
    if (hillToDefend == null || freeAnts.isEmpty()) return;

    // Debug
    if (debugStream != null)
    {
      debugStream.println("\tdefend time = " + ants.getTurnTimeRemaining()  + " free = " + freeAnts.size());
    }

    // Find destinations close to hill.
    List<Coord> corners = new ArrayList<Coord>(4);
    Coord corner = hillToDefend.getEast().getNorth();
    if (!ants.getTile(corner).hasWater()) corners.add(corner);
    corner = hillToDefend.getWest().getNorth();
    if (!ants.getTile(corner).hasWater()) corners.add(corner);
    corner = hillToDefend.getWest().getSouth();
    if (!ants.getTile(corner).hasWater()) corners.add(corner);
    corner = hillToDefend.getEast().getSouth();
    if (!ants.getTile(corner).hasWater()) corners.add(corner);
    if (corners.isEmpty()) corners.add(hillToDefend);
    Collections.shuffle(corners, bot.getRandom());

    // Locate enemies and defenders
    boolean[][] land = bot.getLand();
    PathFinder  hillPath    = new PathFinder(land, hillToDefend);
    List<Route> localForces = new ArrayList<Route>(ants.getVisibleEnemyAnts().size());
    int         enemyCount = 0;
    for (Coord enemy : ants.getVisibleEnemyAnts())
    {
      int d = hillPath.getDistance(enemy);
      if (d <= MyBot.DEFENSE_RANGE)
      {
        ++enemyCount;
        localForces.add(new Route(enemy, hillToDefend, d, hillPath));
      }
    }
    for (Coord ant : freeAnts)
    {
      int d = hillPath.getDistance(ant);
      if (d <= MyBot.DEFENSE_RANGE)
      {
        localForces.add(new Route(ant, hillToDefend, d, hillPath));
      }
    }

    // Sort ants according to distance, keep majority by one at all range
    Collections.sort(localForces);
    Collections.reverse(localForces);
    int balance = 0;
    int minimum = 1;
    for (Route route : localForces)
    {
      Tile tile = ants.getTile(route.getAnt());
      if (tile.hasOwnAnt())
      {
        ++balance;
      }
      else
      {
        --balance;
      }
      if (minimum < balance) minimum = balance;
    }

    // If we have a majority and one idling ant: done
    if (minimum >= 1 && !localForces.isEmpty() && localForces.iterator().next().getAnt().getDistance2(hillToDefend) <= 2) return;

    // Enemy is in majority, or no idling ant: move enemyCount + 1 own ants toward my hill
    List<Route> routes   = new ArrayList<Route>(freeAnts.size()*corners.size());

    // Find all ant/corner pair
    for (Coord destination : corners)
    {
      bot.checkTime();
      PathFinder path = new PathFinder(land, destination);
      for (Coord ant : freeAnts)
      {
        int distance = path.getDistance(ant);
        if (distance != PathFinder.NO_PATH) routes.add(new Route(ant, destination, distance, path));
      }
    }

    // Select best ant/target pairs based on greedy matching: closest first.
    Collections.sort(routes);
    int defender = 0;
    for (Route route : routes)
    {
      if (defender > enemyCount) break; // Moved enough ants to the rescue
      Coord ant    = route.getAnt();
      Coord target = route.getDestination();
      if (freeAnts.contains(ant))
      {
        List<Coord> moves = route.getPath().getSortedMoves(bot, ant);
        if (route.getDistance() == 1 && ants.getTile(target).hasVisibleFood())
        {
          moves.remove(moves.size() - 1); // Always self
          moves.add(0, ant); // Put stay in place first.
        }
        bot.doMoveIntelligently(ant, moves);
        ++defender;
      }
    }

    // Logs
    if (debugStream != null)
    {
      debugStream.println("\t\tbalance = " + balance + " enemyCount = " + enemyCount + " defender = " + defender);
    }

  }
}
