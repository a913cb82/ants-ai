import java.util.*;
import java.util.Map.Entry;

/**
 * Holds all game data and current game state.
 */
public final class Ants
{
  /** Maximum map size. */
  public  static final int MAX_MAP_SIZE     = 256;
  public  static final int MAX_PLAYERS      = 10;
  private static final int TURN_TIME_SAFETY = 4; // Larger => less safe
  private static final int LOAD_TIME_SAFETY  = 2;

  private final int               loadTime;
  private final int               turnTime;
  private final int               turns;
  private final long              playerSeed;
  private final Tile[][]          map;
  private final Collection<Coord> myAnts             = new ArrayList<Coord>();
  private final List<Coord>       myHills            = new ArrayList<Coord>();
  private final List<Coord>       recentlyDiscovered = new LinkedList<Coord>();
  private       long              turnStartTime;
  private final long              loadStartTime;

  private final Collection<Coord>    visibleEnemyAnts           = new ArrayList<Coord>();
  private final Map<Coord, Coord>    visibleEnemyAntPredictions = new HashMap<Coord, Coord>();
  private       Map<Coord, EnemyAnt> visibleEnemyAntHistory     = new HashMap<Coord, EnemyAnt>();
  private final Collection<Coord>    visibleEnemyHills          = new ArrayList<Coord>();
  private       int                  minNumberOfPlayers         = 2;

  /**
   * Creates new {@link Ants} object.
   * @param loadTime timeout for initializing and setting up the bot on turn 0
   * @param turnTime timeout for a single game turn, starting with turn 1
   * @param rows game map height
   * @param cols game map width
   * @param turns maximum number of turns the game will be played
   * @param viewRadius2 squared view radius of each ant
   * @param attackRadius2 squared attack radius of each ant
   * @param spawnRadius2 squared spawn radius of each ant
   * @param playerSeed
   */
  public Ants(long gameStartTime, int loadTime, int turnTime, int turns, long playerSeed)
  {
    this.loadStartTime  = gameStartTime;
    this.loadTime       = loadTime;
    this.turnTime       = turnTime;
    this.turns          = turns;
    this.playerSeed     = playerSeed;
    this.map            = new Tile[Coord.rows][Coord.cols];
    for (int r = 0; r < Coord.rows; ++r) for (int c = 0; c < Coord.cols; ++c) map[r][c] = new Tile(r, c);
  }

  /**
   * Initialize for the start time.
   * @param turnStartTime turn start time
   */
  public void preUpdate()
  {
    turnStartTime = System.currentTimeMillis();
    Tile.incrementTurn();
    myAnts.clear();
    myHills.clear();
    visibleEnemyAnts.clear();
    visibleEnemyHills.clear();
  }

  private void setVisible(Tile tile)
  {
    if (!tile.hasBeenSeen()) recentlyDiscovered.add(tile.getCoord());
    tile.setVisible();
  }

  public void observeWater(int row, int col)
  {
    Tile tile = map[row][col];
    setVisible(tile);
    tile.setWater();
  }

  public void observeFood(int row, int col)
  {
    Tile tile = map[row][col];
    if (tile.neverSeenFood() && tile.hasBeenSeen()) recentlyDiscovered.add(tile.getCoord());
    setVisible(tile);
    tile.setFood();
  }

  public void observeAnt(int row, int col, int owner)
  {
    Tile tile   = map[row][col];
    Coord coord = tile.getCoord();
    setVisible(tile);
    tile.setAnt(owner);
    if (owner == 1)
    {
      myAnts.add(coord);
    }
    else
    {
      visibleEnemyAnts.add(coord);
    }
    if (owner > minNumberOfPlayers)
    {
      minNumberOfPlayers = owner;
    }
  }

  private void computeAllEnemyAntMovement()
  {
    Map<Coord, EnemyAnt> newEnemyAnts = new HashMap<Coord, EnemyAnt>();
    Set<Coord> enemyAntsToMove = new HashSet<Coord>(visibleEnemyAnts);
    int previousSize = -1;
    //if(debugStream != null) debugStream.println("\tStarting enemy tracking size="+enemyAntsToMove.size());
    while(!enemyAntsToMove.isEmpty() && enemyAntsToMove.size()!=previousSize)
    {
      previousSize = enemyAntsToMove.size();
      Set<Coord> toRemove = new HashSet<Coord>();
      for(Coord coord : enemyAntsToMove)
      {
        Tile tile = getTile(coord);
        int owner = tile.getAnt();
        //if(debugStream != null) debugStream.println("\t\tFinding movement for ant c="+coord+" o="+owner);

        // Who could've moved here?
        List<EnemyAnt> potentialAnts = new ArrayList<EnemyAnt>(5);
        boolean couldAlsoBeNew = false;
        for (StencilIterator iter = new StencilIterator(coord, 1, 0); iter.hasNext();)
        {
          Coord source = iter.next();
          Tile otherTile = getTile(source);
          EnemyAnt ant = visibleEnemyAntHistory.get(source);
          if(ant != null)
          {
            if(ant.getOwner() == owner)
            {
              potentialAnts.add(ant);
              //if(debugStream != null) debugStream.println("\t\t\tPotential: c="+ant.getPos()+" o="+ant.getOwner());
            }
          }
          else if(otherTile.getAge() > 1)
          {
            couldAlsoBeNew = true;
          }
        }

        // No one, assume it's a new ant. This should only occur on hill?
        if(potentialAnts.isEmpty())
        {
          //if(debugStream != null) debugStream.println("\t\tNew ant c="+coord+" o="+owner);
          newEnemyAnts.put(coord, new EnemyAnt(owner, coord));
          toRemove.add(coord);
        }
        // Only one possibility, assume it's that one
        else if(potentialAnts.size() == 1 && !couldAlsoBeNew)
        {
          EnemyAnt ant = potentialAnts.get(0);
          visibleEnemyAntHistory.remove(ant.getPos());
          //if(debugStream != null) debugStream.println("\t\tAnt from="+ant.getPos()+" to="+coord+" o="+owner);
          ant.move(coord);
          newEnemyAnts.put(coord, ant);
          toRemove.add(coord);
        }
      }
      enemyAntsToMove.removeAll(toRemove);
    }
    // Assume the rest are "deadlock" and everyone has simply stayed put (if possible)
    for(Coord coord : enemyAntsToMove)
    {
      Tile tile = getTile(coord);
      int owner = tile.getAnt();
      EnemyAnt ant = visibleEnemyAntHistory.remove(coord);
      if(ant != null)
      {
        //if(debugStream != null) debugStream.println("\t\tKeeping ant at="+coord+" o="+ant.getOwner());
        ant.move(coord);
        newEnemyAnts.put(coord, ant);
      }
      else
      {
        // Find potential again, but this time, prefer moving
        List<EnemyAnt> potentialAnts = new ArrayList<EnemyAnt>(5);
        for (StencilIterator iter = new StencilIterator(coord, 1, 0); iter.hasNext();)
        {
          Coord source = iter.next();
          ant = visibleEnemyAntHistory.get(source);
          if(ant != null)
          {
            if(ant.getOwner() == owner)
            {
              potentialAnts.add(ant);
            }
          }
        }
        if(potentialAnts.size() == 1)
        {
          ant = potentialAnts.get(0);
          visibleEnemyAntHistory.remove(ant.getPos());
          //if(debugStream != null) debugStream.println("\t\tAnt from="+ant.getPos()+" to="+coord+" o="+owner);
          ant.move(coord);
          newEnemyAnts.put(coord, ant);
        }
        else
        {
          // Assume new ant
          // Oh oh! what happened here!
          //if(debugStream != null) debugStream.println("\t\tWeird case, assuming new ant at="+coord);
          newEnemyAnts.put(coord, new EnemyAnt(owner, coord));
        }
      }
    }
    visibleEnemyAntHistory = newEnemyAnts;
  }

  public void observeHill(int row, int col, int owner)
  {
    Tile tile = map[row][col];
    setVisible(tile);
    tile.setHill(owner);
    if (owner == 1)
    {
      myHills.add(tile.getCoord());
    }
    else
    {
      visibleEnemyHills.add(tile.getCoord());
    }
  }

  public void observeDead(int row, int col, int owner)
  {
    // Ignore for now
  }

  public void postUpdate()
  {
    for (Coord ant : myAnts)
    {
      for (StencilIterator iter = new StencilIterator(ant, Coord.viewRadius2, 0); iter.hasNext();)
      {
        Coord coord = iter.next();
        setVisible(map[coord.row][coord.col]);
      }
    }
    computeAllEnemyAntMovement();
    visibleEnemyAntPredictions.clear();
    for (Entry<Coord, EnemyAnt> entry : visibleEnemyAntHistory.entrySet())
    {
      visibleEnemyAntPredictions.put(entry.getKey(), entry.getValue().getPredictedMove(this));
    }
  }

  /**
   * Returns timeout for initializing and setting up the bot on turn 0.
   * @return timeout for initializing and setting up the bot on turn 0
   */
  public int getLoadTime()
  {
    return loadTime;
  }

  /**
   * Returns timeout for a single game turn, starting with turn 1.
   * @return timeout for a single game turn, starting with turn 1
   */
  public int getTurnTime()
  {
    return turnTime;
  }

  /**
   * Returns maximum number of turns the game will be played.
   * @return maximum number of turns the game will be played
   */
  public int getTurns()
  {
    return turns;
  }

  public long getPlayerSeed()
  {
    return playerSeed;
  }

  public int getMinNumPlayers()
  {
    return minNumberOfPlayers;
  }

  /**
   * Returns how much time the bot has still has to take its turn before timing out.
   * @return how much time the bot has still has to take its turn before timing out
   */
  public int getTurnTimeRemaining()
  {
    return turnTime - getTurnElapsedTime();
  }

  public int getTurnElapsedTime()
  {
    return (int) (System.currentTimeMillis() - turnStartTime);
  }

  public boolean isTurnTimeCritical()
  {
    return getTurnTimeRemaining()*TURN_TIME_SAFETY <= turnTime;
  }

  public int getLoadTimeRemaining()
  {
    return loadTime - getLoadElapsedTime();
  }

  public int getLoadElapsedTime()
  {
    return (int) (System.currentTimeMillis() - loadStartTime);
  }

  public boolean isLoadTimeCritical()
  {
    return getLoadTimeRemaining()*LOAD_TIME_SAFETY <= loadTime;
  }

  public Tile getTile(Coord coord)
  {
    return map[coord.row][coord.col];
  }

  public Tile getTile(int row, int col)
  {
    return map[row][col];
  }

  public List<Coord> getRecentlyDiscovered()
  {
    return recentlyDiscovered;
  }

  /**
   * Returns a set containing all my ants locations.
   * @return a set containing all my ants locations
   */
  public Collection<Coord> getMyAnts()
  {
    return myAnts;
  }

  /**
   * Returns a set containing all my hills locations.
   * @return a set containing all my hills locations
   */
  public List<Coord> getMyHills()
  {
    return myHills;
  }

  public Collection<Coord> getVisibleEnemyAnts()
  {
    return visibleEnemyAnts;
  }

  public Collection<Coord> getVisibleEnemyAntHistoryKeys()
  {
    return visibleEnemyAntHistory.keySet();
  }

  public Coord getVisibleEnemyAntPrediction(Coord enemy)
  {
    return visibleEnemyAntPredictions.get(enemy);
  }

  public Collection<Coord> getVisibleEnemyHills()
  {
    return visibleEnemyHills;
  }

  public int beachCount(Coord coord)
  {
    int water = 0;
    for (StencilIterator iter = new StencilIterator(coord, 1, 0); iter.hasNext();) if (getTile(iter.next()).hasWater()) ++water;
    return water;
  }

  public int foodCount(Coord coord)
  {
    int food = 0;
    for (StencilIterator iter = new StencilIterator(coord, 1, 0); iter.hasNext();) if (getTile(iter.next()).hasVisibleFood()) ++food;
    return food;
  }

  public void enemyAntOverlay(Overlay overlay)
  {
    for (Entry<Coord, EnemyAnt> entry : visibleEnemyAntHistory.entrySet())
    {
      Coord    c   = entry.getKey();
      EnemyAnt ant = entry.getValue();
      Coord    c1  = null;
      for(Coord c2 : ant.getPrevPosList())
      {
        if(c1 != null)
        {
          if(c1.equals(c2))
          {
            overlay.star(c2, 1, Overlay.LineColor.RED);
          }
          else
          {
            overlay.arrow(c1, c2, Overlay.LineColor.RED);
          }
        }
        c1 = c2;
      }
      if(c1 != null)
      {
        if(c1.equals(c))
        {
          overlay.star(c, 1, Overlay.LineColor.RED);
        }
        else
        {
          overlay.arrow(c1, c, Overlay.LineColor.RED);
        }
      }
    }
  }
}
