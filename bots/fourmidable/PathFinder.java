import java.util.*;

public final class PathFinder
{
  public static final int           NO_PATH = Short.MAX_VALUE;
  private final boolean[][]         passable;
  private final Coord               destination;
  private       LinkedList<Coord>   list;
  private       short[][]           distance;
  private       Map<Coord, Integer> areas;

  /**
   * Constructor.
   * @param ants the game state
   * @param destination the destination tile
   */
  public PathFinder(boolean[][] passable, Coord destination)
  {
    this.passable    = passable;
    this.destination = destination;
    int rows         = Coord.rows;
    int cols         = Coord.cols;
    distance         = new short[rows][cols];
    list             = new LinkedList<Coord>();
    areas            = new HashMap<Coord, Integer>();
    for (int i = 0; i < rows; ++i) for (int j = 0; j < cols; ++j) distance[i][j] = NO_PATH;
    distance[destination.row][destination.col] = 0;
    list.add(destination);
  }

  /**
   * Compute the walking distance, avoiding known obstables, from source to destination.
   * The method can be called multiple times to compute the distance from multiple sources.
   * Re-using the same PathFinder is more efficient as it reuses precomputed results.
   * @param source the origin point
   * @param maxDistance abort if source not found within distance
   * @return the distance in squares, <code>NO_PATH</code> if impassable.
   */
  private int getDistanceInternal(Coord source, int maxDistance)
  {
    if (distance[source.row][source.col] == NO_PATH && !list.isEmpty() && source.getDistanceOrthogonal(destination) <= maxDistance)
    {
      Coord first = list.getFirst();
      if (distance[first.row][first.col] < maxDistance)
      {
        while (!list.isEmpty())
        {
          Coord coord = list.removeFirst();
          if (distance[coord.row][coord.col] >= maxDistance)
          {
            list.addFirst(coord); // Limit reached, put it back
            break;
          }
          if (flood(coord, source)) break;
        }
      }
    }
    return distance[source.row][source.col];
  }

  public int getDistance(Coord source, int maxDistance)
  {
    if (passable[source.row][source.col]) return getDistanceInternal(source, maxDistance);

    // If the source is not reachable, look for adjacent connectivity
    Coord east     = source.getEast();
    Coord north    = source.getNorth();
    Coord west     = source.getWest();
    Coord south    = source.getSouth();
    int   distance = NO_PATH;
    if (passable[east.row][east.col])
    {
      int d = getDistanceInternal(east, maxDistance - 1) + 1;
      if (distance > d) distance = d;
    }
    if (passable[north.row][north.col])
    {
      int d = getDistanceInternal(north, maxDistance - 1) + 1;
      if (distance > d) distance = d;
    }
    if (passable[west.row][west.col])
    {
      int d = getDistanceInternal(west, maxDistance - 1) + 1;
      if (distance > d) distance = d;
    }
    if (passable[south.row][south.col])
    {
      int d = getDistanceInternal(south, maxDistance - 1) + 1;
      if (distance > d) distance = d;
    }
    return distance;
  }

  /**
   * Compute the walking distance, avoiding known obstables, from source to destination.
   * The method can be called multiple times to compute the distance from multiple sources.
   * Re-using the same PathFinder is more efficient as it reuses precomputed results.
   * @param source the origin point
   * @return the distance in squares, <code>NO_PATH</code> if impassable.
   */
  public int getDistance(Coord source)
  {
    return getDistance(source, Integer.MAX_VALUE);
  }

  /**
   * Get all the directions that results in a shortest path toward destination.
   * Must call {@link PathFinder#getDistance(Coord)} before.
   * @param source the origin square
   * @return the list of equivalent best directions, empty if unreachable
   */
  public List<Coord> getSortedMoves(MyBot bot, final Coord source)
  {
    final Ants                ants      = bot.getAnts();
    final boolean[][]         unblocked = bot.getUnblockedLand();
    List<Coord>               moves     = source.getMovesExcludingSleeping(ants);
    Collections.sort(moves, new Comparator<Coord>()
    {
      @Override
      public int compare(Coord c1, Coord c2)
      {
        // Shortest path first
        int dd = distance[c1.row][c1.col] - distance[c2.row][c2.col];
        if (dd != 0) return dd;

        // Avoid threading on own hill
        boolean hill1 = ants.getMyHills().contains(c1);
        boolean hill2 = ants.getMyHills().contains(c2);
        if (!hill1 && hill2) return -1;
        if (!hill2 && hill1) return  1;

        // Prefer lots of food
        int food = ants.foodCount(c2) - ants.foodCount(c1);
        if (food != 0) return food;

        // Prefer blocked
        if (!unblocked[c1.row][c1.col] && unblocked[c2.row][c2.col]) return -1;
        if (unblocked[c1.row][c1.col] && !unblocked[c2.row][c2.col]) return  1;

        // Prefer fewer beaches
        int beach = ants.beachCount(c1) - ants.beachCount(c2);
        if (beach != 0) return beach;

        // Prefer larger area
        return computeArea(ants, c2) - computeArea(ants, c1);
      }
    });
    moves.add(source); // Always last -- let's keep moving
    return moves;
  }

  /**
   * Starting from 'start' compute the total area that can be used to reach destination using the shortest path.
   * If the path is unique, area is the length of the path. For multiple path, is the the number of squares
   * in the union of all possible paths.
   * @param ants game state
   * @param start starting square
   * @return the area of all equivalent shortest paths
   */
  private int computeArea(Ants ants, Coord start)
  {
    Integer value = areas.get(start);
    if (value != null) return value.intValue();
    int area = 1;
    int d = distance[start.row][start.col];
    Set<Coord> previous = new HashSet<Coord>();
    previous.add(start);
    while (!previous.isEmpty())
    {
      --d;
      Set<Coord> current = new HashSet<Coord>();
      for (Coord coord : previous)
      {
        Coord adj = coord.getEast();
        if (distance[adj.row][adj.col] == d) current.add(adj);
        adj = coord.getNorth();
        if (distance[adj.row][adj.col] == d) current.add(adj);
        adj = coord.getWest();
        if (distance[adj.row][adj.col] == d) current.add(adj);
        adj = coord.getSouth();
        if (distance[adj.row][adj.col] == d) current.add(adj);
      }
      area    += current.size();
      previous = current;
    }
    areas.put(start, Integer.valueOf(area));
    return area;
  }

  /**
   * Utility method that 'paints' the four adjacent squares to the source tile if the shortest path.
   * @param tile the source tile
   * @param source
   * @return if destination was reached
   */
  private boolean flood(Coord tile, Coord source)
  {
    boolean result = false;
    Coord   east   = tile.getEast();
    Coord   west   = tile.getWest();
    Coord   north  = tile.getNorth();
    Coord   south  = tile.getSouth();
    short   d      = (short) (distance[tile.row][tile.col] + 1);

    // 4 neighboors reachable in 'd + 1' if not already better
    if (d < distance[east.row][east.col] && passable[east.row][east.col])
    {
      distance[east.row][east.col] = d;
      list.addLast(east);
      if (source.equals(east)) result = true;
    }
    if (d < distance[south.row][south.col] && passable[south.row][south.col])
    {
      distance[south.row][south.col] = d;
      list.addLast(south);
      if (source.equals(south)) result = true;
    }
    if (d < distance[north.row][north.col] && passable[north.row][north.col])
    {
      distance[north.row][north.col] = d;
      list.addLast(north);
      if (source.equals(north)) result = true;
    }
    if (d < distance[west.row][west.col] && passable[west.row][west.col])
    {
      distance[west.row][west.col] = d;
      list.addLast(west);
      if (source.equals(west)) result = true;
    }
    return result;
  }

  public boolean isPassable(Coord coord)
  {
    return passable[coord.row][coord.col];
  }
}
