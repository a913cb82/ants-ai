import java.io.*;
import java.util.*;

public final class FoodAndHills
{
  private static final int FAR = 1000;

  private final MyBot       bot;
  private final PrintStream debugStream;
  private final Ants        ants;
  private final Overlay     overlay;

  public FoodAndHills(MyBot bot)
  {
    this.bot         = bot;
    this.debugStream = bot.getDebugStream();
    this.ants        = bot.getAnts();
    this.overlay     = bot.getOverlay();
  }

  public void doFoodAndHills() throws TimeRunningOutException
  {
    // Early exit
    if (bot.getFreeAnts().isEmpty()) return;

    // Debug
    if (debugStream != null) debugStream.println("\tdoFoodAndHills time = " + ants.getTurnTimeRemaining() + " free = " + bot.getFreeAnts().size());

    // Collect worthwhile objectives: food and enemy hills
    bot.checkTime();
    ArrayList<Coord> foods      = new ArrayList<Coord>();
    ArrayList<Coord> enemyHills = new ArrayList<Coord>();
    for (int row = 0; row < Coord.rows; ++row) for (int col = 0; col < Coord.cols; ++col)
    {
      Tile tile = ants.getTile(row, col);
      if (tile.hasRecentFood(MyBot.STALE_FOOD)) foods.add(tile.getCoord());
      if (tile.hasEnemyHill()) enemyHills.add(tile.getCoord());
    }
    int objectives = 0;

    // Find all ant/hill pairs
    List<Route> routes = new ArrayList<Route>(bot.getFreeAnts().size()*(foods.size() + enemyHills.size()));
    for (Coord hill : enemyHills)
    {
      bot.checkTime();
      PathFinder path    = new PathFinder(bot.getSniperLand(), hill);

      // Go if at least one ant within SNIPER_RANGE
      boolean    inRange = false;
      for (Coord ant : bot.getFreeAnts())
      {
        int distance = path.getDistance(ant);
        if (distance <= MyBot.SNIPER_RANGE)
        {
          inRange = true;
          break;
        }
      }
      if (inRange)
      {
        ++objectives;
        for (Coord ant : bot.getFreeAnts())
        {
          int distance = path.getDistance(ant);
          if (distance != PathFinder.NO_PATH) routes.add(new Route(ant, hill, distance, path));
        }
      }
    }

    // Optimize start of search
    if (ants.getVisibleEnemyAnts().isEmpty() && routes.isEmpty())
    {
      moreFood(foods);
      return;
    }

    // Find all ant/food pairs
    for (Coord food : foods)
    {
      // Go if
      // 1) Visible food, or
      // 2a) Within STALE_FOOD distance, and
      // 2b) No more than FOOD_HEAD_START behind enemy
      bot.checkTime();
      boolean    inRange = !ants.getTile(food).hasInferredFood(); // Always go for visible food
      PathFinder path    = new PathFinder(bot.getLand(), food);
      if (!inRange)
      {
        int antDistance = PathFinder.NO_PATH;
        for (Coord ant : bot.getFreeAnts())
        {
          int distance = path.getDistance(ant);
          if (antDistance > distance) antDistance = distance;
        }
        if (antDistance <= MyBot.STALE_FOOD)
        {
          inRange = true;
          for (Coord enemy : ants.getVisibleEnemyAnts())
          {
            int distance = path.getDistance(enemy);
            if (antDistance > distance + MyBot.FOOD_HEAD_START)
            {
              inRange = false;
              break;
            }
          }
        }
      }
      if (inRange)
      {
        ++objectives;
        for (Coord ant : bot.getFreeAnts())
        {
          int distance = path.getDistance(ant);
          if (distance != PathFinder.NO_PATH) routes.add(new Route(ant, food, distance, path));
        }
      }
    }

    // Compute maximum ants per target
    if (objectives == 0) return;
    int antsPerTarget = Math.max(1, Math.min(3, (int)Math.floor(MyBot.REENFORCEMENT*bot.getFreeAnts().size()/objectives)));
    if (debugStream != null && antsPerTarget > 1) debugStream.println("\t\tantsPerTarget = " + antsPerTarget);
    MultiSet<Coord> selected = new MultiSet<Coord>();
    for (Coord food : foods     ) selected.add(food, antsPerTarget);
    for (Coord hill : enemyHills) selected.add(hill, antsPerTarget);

    // Select best ant/target pairs based on greedy matching: closest first.
    Collections.sort(routes);
    for (Route route : routes)
    {
      Coord ant = route.getAnt();
      if (!bot.getFreeAnts().contains(ant)) continue;
      Coord target = route.getDestination();
      if (!selected.remove(target)) continue;
      List<Coord> moves = route.getPath().getSortedMoves(bot, ant);
      if (route.getDistance() == 1 && ants.getTile(target).hasVisibleFood())
      {
        moves.remove(moves.size() - 1); // Always self
        moves.add(0, ant);              // Put stay in place first.
      }
      bot.doMoveIntelligently(ant, moves);
      if (overlay != null && overlay.isActive(Overlay.Type.FOOD)) overlay.arrow(ant, target, ants.getTile(target).hasEnemyHill() ? Overlay.LineColor.GREEN : Overlay.LineColor.RED);
    }

    // Debug
    if (debugStream != null) debugStream.println("\t\tfood = " + foods.size() + " hills = " + enemyHills.size() + " objectives = " + objectives);
  }

  private void moreFood(ArrayList<Coord> foods) throws TimeRunningOutException
  {
    if (debugStream != null) debugStream.println("\t\tmoreFood food = " + foods.size() + " free = " + bot.getFreeAnts().size());

    // Get targets adjacent to food
    ArrayList<Route> routes = new ArrayList<Route>();
    Set<Coord> targets = new HashSet<Coord>();
    for (Coord food : foods)
    {
      bot.checkTime();
      for (Coord target : food.getMovesExcludingSleeping(ants))
      {
        if (targets.add(target))
        {
          PathFinder path     = new PathFinder(bot.getLand(), target);
          int        distance = FAR;
          for (Coord otherFood : foods)
          {
            if (!otherFood.equals(food))
            {
              int d = path.getDistance(otherFood);
              if (distance > d) distance = d;
            }
          }
          for (Coord ant : bot.getFreeAnts())
          {
            int d = path.getDistance(ant);
            if (d != PathFinder.NO_PATH)
            {
              d = FAR*d + distance;
              routes.add(new Route(ant, target, d, path));
            }
          }
        }
      }
    }
    Collections.sort(routes);

    // Assign order
    for (Route route : routes)
    {
      bot.checkTime();
      final Coord      ant    = route.getAnt();
      final Coord      target = route.getDestination();
      final PathFinder path   = route.getPath();
      if (bot.getFreeAnts().contains(ant) && removeAdjacent(target, foods) && !reUseAnt(target, path.getDistance(ant), path))
      {
        List<Coord> moves = ant.getMovesIncludingSleeping(ants);
        Collections.sort(moves, new Comparator<Coord>()
        {
          @Override public int compare(Coord c1, Coord c2)
          {
            // Prefer shorter distance
            int dd = path.getDistance(c1) - path.getDistance(c2);
            if (dd != 0) return dd;

            // Avoid threading on own hill
            int hill = 0;
            if (ants.getMyHills().contains(c1)) ++hill;
            if (ants.getMyHills().contains(c2)) --hill;
            if (hill != 0) return hill;

            // Prefer oldest visible range
            int age = 0;
            for (StencilIterator iter = new StencilIterator(c1, Coord.attackRadius2, 0); iter.hasNext();) age -= ants.getTile(iter.next()).getAgeIfLand();
            for (StencilIterator iter = new StencilIterator(c2, Coord.attackRadius2, 0); iter.hasNext();) age += ants.getTile(iter.next()).getAgeIfLand();
            if (age != 0) return age;

            // Prefer lots of food
            int food = ants.foodCount(c2) - ants.foodCount(c1);
            if (food != 0) return food;

            // Prefer fewer beaches
            int beach = ants.beachCount(c1) - ants.beachCount(c2);
            if (beach != 0) return beach;

            // Closest line-of-sight (favors diagonal approach)
            return target.getDistance2(c1) - target.getDistance2(c2);
          }
        });
        bot.doMoveIntelligently(ant, moves);
        bot.addAvailableInTheFuture(target, path.getDistance(ant));
        if (overlay != null && overlay.isActive(Overlay.Type.FOOD)) overlay.arrow(ant, target, Overlay.LineColor.BLUE);
      }
    }
  }

  /**
   * This method evaluates whether we would be better of waiting for an ant enroute
   * before targetting this food/hill.
   * @param target the target tile
   * @param distanceFromFreeAnt the distance from the candidate free ant
   * @param path the path finder
   * @return if we prefer re-using an ant enroute
   */
  private boolean reUseAnt(Coord target, int distanceFromFreeAnt, PathFinder path)
  {
    Coord bestAnt  = null;
    int   distance = distanceFromFreeAnt;
    for (Map.Entry<Coord, Integer> entry : bot.getAvailableInTheFuture().entrySet())
    {
      Coord ant  = entry.getKey();
      int   leg1 = entry.getValue().intValue();
      if (distance > leg1)
      {
        int leg2 = path.getDistance(ant);
        if (leg2 != PathFinder.NO_PATH && distance > leg1 + leg2)
        {
          bestAnt  = ant;
          distance = leg1 + leg2; // New total to beat
        }
      }
    }
    if (bestAnt != null)
    {
      // Place the ant at its new location
      bot.getAvailableInTheFuture().remove(bestAnt);
      bot.addAvailableInTheFuture(target, distance);
    }
    return bestAnt != null;
  }

  private boolean removeAdjacent(Coord target, ArrayList<Coord> foods)
  {
    boolean modified = false;
    for (Iterator<Coord> iter = foods.iterator(); iter.hasNext();)
    {
      Coord food = iter.next();
      if (target.getDistance2(food) <= 1)
      {
        iter.remove();
        modified = true;
      }
    }
    return modified;
  }
}
