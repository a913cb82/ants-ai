import java.io.*;
import java.util.*;
import java.util.Map.Entry;

public final class MyBot extends Bot
{
  public static final int     MAX_PLAYER           = 10;
  public static final int     OBSERVE_COVER2       = Integer.getInteger("observeCover2",     100);
  public static final int     DEFENSE_RANGE        = Integer.getInteger("defenseRange",       12);
  public static final int     STRONG_DEFENSE_RANGE = Integer.getInteger("strongDefenseRange",  4);
  public static final int     STALE_FOOD           = Integer.getInteger("staleFood",          20);
  public static final int     OBSERVE_RANGE        = Integer.getInteger("observeRange",       70);
  public static final int     SNIPER_RANGE         = Integer.getInteger("sniperRange",        40);
  public static final int     FOOD_HEAD_START      = Integer.getInteger("foodHeadStart",       3);
  public static final int     EVIDENCE_THRESHOLD   = Integer.getInteger("evidenceThreshold",  10);
  public static final int     HUNT_STRENGHT        = Integer.getInteger("huntStrength",        3);
  public static final int     ATTACK_MAJORITY      = Integer.getInteger("attackMajority",      0); // disabled
  public static final int     STILL_THRESHOLD      = Integer.getInteger("stillThreshold",      6);
  public static final int     SAME_DIR_THRESHOLD   = Integer.getInteger("sameDirThreshold",  100); // disabled
  public static final int     TOGGLE_THRESHOLD     = Integer.getInteger("toggleThreshold",   100); // disabled
  public static final double  BOLD_THRESHOLD       = Double.parseDouble(System.getProperty("boldThreshold",    "0.6"));
  public static final double  REENFORCEMENT        = Double.parseDouble(System.getProperty("reenforcement",    "0.2"));
  public static final double  HUNT_RATIO           = Double.parseDouble(System.getProperty("huntRatio",        "0.5"));

  // Persistent info
  private ArrayList<Coord> tilesToExplore;
  private Random           random;
  private Coord            hillToDefend;
  private Coord            defaultTarget;
  private MapInference     mapInference;
  private Overlay          overlay;

  // Per turn info
  private Map<Coord, Coord>      destinationToSource;
  private Map<Coord, BattleMode> battleMode;
  private Map<Coord, Integer>    availableInTheFuture;
  private Set<Coord>             freeAnts;
  private boolean[][]            land;           // Blocked by water
  private boolean[][]            unblockedLand;  // Blocked by water and own ants with two neighbours
  private boolean[][]            safeLand;       // Blocked by water and enemy potential attack range
  private boolean[][]            tradeLand;      // Blocked by water and enemy potential double attack range
  private boolean[][]            sniperLand;
  private byte[][]               influence;
  private double                 totalAntEstimate;

  // Debug
  private PrintStream     echoStream;
  private PrintStream     debugStream;
  private InputStream     inputStream;

  /**
   * Main method executed by the game engine for starting the bot.
   * @param args command line arguments
   * @throws IOException if an I/O error occurs
   */
  public static void main(String[] args) throws IOException
  {
    new MyBot().run();
  }

  /**
   * Constructor.
   */
  private MyBot()
  {
  }

  private void run() throws IOException
  {
    // Open files.
    String logFileName = System.getProperty("echo");
    if (logFileName != null) echoStream = new PrintStream(new FileOutputStream(logFileName));
    String debugFilename = System.getProperty("debug");
    if (debugFilename != null) debugStream = new PrintStream(new FileOutputStream(debugFilename));
    String inputFilename = System.getProperty("input");
    if (inputFilename != null) inputStream = new FileInputStream(inputFilename);
    String overlayOptions = System.getProperty("overlay");
    if (overlayOptions != null) overlay = new Overlay(overlayOptions);

    // Print options
    if (debugStream != null)
    {
      debugStream.println("OBSERVE_COVER2       = " + OBSERVE_COVER2);
      debugStream.println("DEFENSE_RANGE        = " + DEFENSE_RANGE);
      debugStream.println("STRONG_DEFENSE_RANGE = " + STRONG_DEFENSE_RANGE);
      debugStream.println("STALE_FOOD           = " + STALE_FOOD);
      debugStream.println("OBSERVE_RANGE        = " + OBSERVE_RANGE);
      debugStream.println("SNIPER_RANGE         = " + SNIPER_RANGE);
      debugStream.println("FOOD_HEAD_START      = " + FOOD_HEAD_START);
      debugStream.println("EVIDENCE_THRESHOLD   = " + EVIDENCE_THRESHOLD);
      debugStream.println("HUNT_STRENGHT        = " + HUNT_STRENGHT);
      debugStream.println("ATTACK_MAJORITY      = " + ATTACK_MAJORITY);
      debugStream.println("STILL_THRESHOLD      = " + STILL_THRESHOLD);
      debugStream.println("SAME_DIR_THRESHOLD   = " + SAME_DIR_THRESHOLD);
      debugStream.println("TOGGLE_THRESHOLD     = " + TOGGLE_THRESHOLD);
      debugStream.println("BOLD_THRESHOLD       = " + BOLD_THRESHOLD);
      debugStream.println("REENFORCEMENT        = " + REENFORCEMENT);
      debugStream.println("HUNT_RATIO           = " + HUNT_RATIO);
    }

    // Invoke base class.
    readSystemInput(inputStream == null ? System.in : inputStream);

    // Close files.
    if (inputStream != null) inputStream.close();
    if (debugStream != null) debugStream.close();
    if (echoStream  != null) echoStream.close();
  }

  @Override
  protected void doProcessLine(String line)
  {
    if (echoStream != null) echoStream.println(line);
  }

  @Override
  protected void doSetup()
  {
    if (debugStream != null)
    {
      debugStream.println("========================================");
    }

    // Build a random generator based on provided seed
    random = new Random(ants.getPlayerSeed());

    // Initialize array of all land tiles
    tilesToExplore = new ArrayList<Coord>(Coord.rows*Coord.cols);
    for (int row = 0; row < Coord.rows; row++)
    {
      for (int col = 0; col < Coord.cols; col++)
      {
        tilesToExplore.add(ants.getTile(row, col).getCoord());
      }
    }
    Collections.shuffle(tilesToExplore, random);

    // Initialize map transformation
    mapInference = new MapInference(this);
    mapInference.initialize();

    // Debug
    if (debugStream != null) debugStream.println("doSetup elapsed = " + (ants.getLoadTime() - ants.getLoadTimeRemaining()));
  }

  @Override
  protected void doTurn()
  {
    try
    {
      // ants.setDebugStream(debugStream);
      if (debugStream != null) debugStream.println("Turn " + Tile.getTurn() + " ants = " + ants.getMyAnts().size() + " hills = " + ants.getMyHills().size());
      if (overlay != null) overlay.init();
      if (overlay != null && overlay.isActive(Overlay.Type.ENEMYANT)) ants.enemyAntOverlay(overlay);
      destinationToSource  = new HashMap<Coord, Coord>();
      battleMode           = new HashMap<Coord, BattleMode>();
      availableInTheFuture = new HashMap<Coord, Integer>();
      freeAnts             = new HashSet<Coord>(ants.getMyAnts());
      land                 = new boolean[Coord.rows][Coord.cols];
      unblockedLand        = new boolean[Coord.rows][Coord.cols];
      safeLand             = new boolean[Coord.rows][Coord.cols];
      tradeLand            = new boolean[Coord.rows][Coord.cols];
      sniperLand           = new boolean[Coord.rows][Coord.cols];
      influence            = new byte[Coord.rows][Coord.cols];
      totalAntEstimate     = estimateTotalAnts();
      selectHillToDefend();
      featureExtraction();
      assignBattleMode();
      new Battle(this).doBattle();
      new FoodAndHills(this).doFoodAndHills();
      new Defense(this).doDefend(hillToDefend);
      new Visitor(this).doVisit();
      new Hunt(this).doHunt(hillToDefend);
      if (ATTACK_MAJORITY == 0)
        new Attack(this).doAttackWeakest();
      else
        new Attack(this).doAttackNearest();
      moveIdleAnts();
      collisionAvoidance();
      mapInference.doMapInference(); // Do map inference last, time permitting. Useful for next turn.
      debug();
      if (debugStream != null) debugStream.println("\tdoTurn elapsed " + ants.getTurnElapsedTime() + " ms");
    }
    catch (RuntimeException e)
    {
      // If debugging, suicide by rethrowing the exception.
      // Otherwise continue on a best effort basis.
      if (debugStream != null)
      {
        e.printStackTrace(debugStream);
      }
      if (inputStream != null)
      {
        throw e;
      }
    }
    catch (TimeRunningOutException e)
    {
      if (debugStream != null)
      {
        e.printStackTrace(debugStream);
      }
      if (inputStream != null)
      {
        throw new RuntimeException(e);
      }
    }
    issueOrders();

    // Cleanup for GC
    destinationToSource  = null;
    battleMode           = null;
    availableInTheFuture = null;
    freeAnts             = null;
    land                 = null;
    unblockedLand        = null;
    safeLand             = null;
    tradeLand            = null;
    influence            = null;
  }

  @Override
  protected void doEnd()
  {
  }

  /**
   * This method estimates the total ant population by extrapolating from the visible area.
   * @return the estimated ant population
   */
  private double estimateTotalAnts()
  {
    // Debug
    if (debugStream != null)
    {
      debugStream.println("\testimateTotalAnts time = " + ants.getTurnTimeRemaining());
    }
    int own = ants.getMyAnts().size();
    if (own == 0) return 0;
    int visibleEnemy = 0;
    int visibleLand  = 0;
    int water        = 0;
    for (int row = 0; row < Coord.rows; ++row)
    {
      for (int col = 0; col < Coord.cols; ++col)
      {
        Tile tile = ants.getTile(row, col);
        if (tile.isVisibleLand()) ++visibleLand;
        if (tile.hasWater()) ++water;
        if (tile.hasVisibleEnemyAnt()) ++visibleEnemy;
      }
    }
    double total = 1.0*(own + visibleEnemy)*(Coord.rows*Coord.cols - water)/visibleLand;
    if (debugStream != null)
    {
      debugStream.println("\t\town = " + own + " enemy = " + visibleEnemy + " total = " + total + " ratio = " + own/total);
    }
    return total;
  }

  private void selectHillToDefend()
  {
    if (debugStream != null)
    {
      debugStream.println("\tselectHillToDefend time = " + ants.getTurnTimeRemaining() + " hillToDefend = " + hillToDefend);
    }
    if (!ants.getMyHills().contains(hillToDefend)) hillToDefend = null;
    if (hillToDefend == null && !ants.getMyHills().isEmpty() && !ants.getVisibleEnemyAnts().isEmpty())
    {
      hillToDefend = ants.getMyHills().get(random.nextInt(ants.getMyHills().size()));
    }
    if (hillToDefend != null && overlay != null && overlay.isActive(Overlay.Type.FEATURES)) overlay.star(hillToDefend, 2, Overlay.LineColor.BLUE);
  }

  private void assignBattleMode()
  {
    double ratio = 1.0*ants.getMyAnts().size()/totalAntEstimate;
    if (debugStream != null)
    {
      debugStream.println("\tassignBattleMode time = " + ants.getTurnTimeRemaining() + " ratio = " + ratio);
    }
    PathFinder hillDistance = null;
    boolean    danger       = false;
    if (hillToDefend != null)
    {
      hillDistance = new PathFinder(land, hillToDefend);
      for (StencilIterator iter = new StencilIterator(hillToDefend, 4, 0); iter.hasNext();)
      {
        if (ants.getTile(iter.next()).hasVisibleEnemyAnt()) danger = true;
      }
    }
    for (Coord ant : ants.getMyAnts())
    {
      if (ants.getMyHills().isEmpty())
      {
        battleMode.put(ant, BattleMode.CAREFUL);
      }
      else if (danger && hillDistance.getDistance(ant) <= STRONG_DEFENSE_RANGE)
      {
        battleMode.put(ant, BattleMode.FEARLESS);
      }
      else if (hillDistance != null && hillDistance.getDistance(ant) <= DEFENSE_RANGE)
      {
        battleMode.put(ant, BattleMode.BOLD);
      }
      else if (ratio < BOLD_THRESHOLD)
      {
        double  x= ratio/BOLD_THRESHOLD;
        battleMode.put(ant, random.nextDouble() < x*x*x ? BattleMode.BOLD : BattleMode.CAREFUL);
      }
      else
      {
        double x = (ratio - BOLD_THRESHOLD)/(1.0 - BOLD_THRESHOLD);
        battleMode.put(ant, random.nextDouble() < x*x*x ? BattleMode.FEARLESS : BattleMode.BOLD);
      }
    }
  }

  private void featureExtraction()
  {
    // Debug
    if (debugStream != null)
    {
      debugStream.println("\tfeatureExtraction time = " + ants.getTurnTimeRemaining());
    }

    byte[][] nearbyWater          = new byte[Coord.rows][Coord.cols];
    byte[][] potentialAttackCount = new byte[Coord.rows][Coord.cols];
    byte[][] ownProximityForBlock = new byte[Coord.rows][Coord.cols];
    byte[][] oppProximityForBlock = new byte[Coord.rows][Coord.cols];
    for (int row = 0; row < Coord.rows; ++row) for (int col = 0; col < Coord.cols; ++col)
    {
      Tile  tile              = ants.getTile(row, col);
      Coord coord             = tile.getCoord();
      unblockedLand[row][col] = !tile.hasWater();
      if (tile.hasWater())
      {
        for (StencilIterator waterIter = new StencilIterator(coord, 1, 0); waterIter.hasNext();) // Basic cross (arbitraty)
        {
          Coord c = waterIter.next();
          ++nearbyWater[c.row][c.col];
        }
      }
      else if (tile.hasVisibleEnemyAnt())
      {
        Coord predicted = ants.getVisibleEnemyAntPrediction(coord);
        int   moves     = 0;
        if (predicted == null)
        {
          predicted = coord;
          moves = 1;
        }
        for (StencilIterator potentialIter = new StencilIterator(predicted, Coord.attackRadius2, moves); potentialIter.hasNext();) // Attack + 1 move (exact)
        {
          Coord c = potentialIter.next();
          ++potentialAttackCount[c.row][c.col];
        }
        for (StencilIterator oppProximityIter = new StencilIterator(coord, Coord.attackRadius2, 3); oppProximityIter.hasNext();) // Attack + 3 moves (arbitraty)
        {
          Coord c = oppProximityIter.next();
          ++oppProximityForBlock[c.row][c.col];
        }
      }
      else if (tile.hasOwnAnt())
      {
        for (StencilIterator ownProximityIter = new StencilIterator(coord, 1, 0); ownProximityIter.hasNext();) // Basic cross
        {
          Coord c = ownProximityIter.next();
          ++ownProximityForBlock[c.row][c.col];
        }
      }
    }
    for (int row = 0; row < Coord.rows; ++row) for (int col = 0; col < Coord.cols; ++col)
    {
      Tile  tile           = ants.getTile(row, col);
      Coord coord          = tile.getCoord();
      land[row][col]       = !tile.hasWater(); // Final answer
      safeLand[row][col]   = !tile.hasWater() && potentialAttackCount[row][col] == 0;
      tradeLand[row][col]  = !tile.hasWater() && potentialAttackCount[row][col] <= 1;
      sniperLand[row][col] = !tile.hasWater();
      if (oppProximityForBlock[row][col] > 0
          && ownProximityForBlock[row][col] >= 2
          && ownProximityForBlock[row][col] + nearbyWater[row][col] >= 3)
      {
        for (StencilIterator blockedIter = new StencilIterator(coord, 2, 0); blockedIter.hasNext();) // Basic square
        {
          Coord c = blockedIter.next();
          unblockedLand[c.row][c.col] = false;
        }
      }
    }
    for (Coord enemy : ants.getVisibleEnemyAnts())
    {
      for (StencilIterator iter = new StencilIterator(enemy, 2, 0); iter.hasNext();)
      {
        Coord c= iter.next();
        sniperLand[c.row][c.col] = false;
      }
    }
    for (Coord hill : ants.getVisibleEnemyHills())
    {
      for (StencilIterator iter = new StencilIterator(hill, Coord.attackRadius2, 0); iter.hasNext();)
      {
        Coord c = iter.next();
        if (land[c.row][c.col]) unblockedLand[c.row][c.col] = true;
      }
    }
    if (overlay != null && overlay.isActive(Overlay.Type.FEATURES))
    {
      for (int row = 0; row < Coord.rows; ++row) for (int col = 0; col < Coord.cols; ++col) if (land[row][col] && !unblockedLand[row][col])
      {
        overlay.highlight(new Coord(row, col), Overlay.FillColor.RED);
      }
      for (Coord enemy : ants.getVisibleEnemyAnts())
      {
        Coord predicted = ants.getVisibleEnemyAntPrediction(enemy);
        if (predicted != null)
        {
          if (!predicted.equals(enemy))
          {
            overlay.arrow(enemy, predicted, Overlay.LineColor.RED);
          }
          else
          {
            overlay.circle(predicted, 1, Overlay.LineColor.RED);
          }
        }
      }
    }
  }

  private void moveIdleAnts() throws TimeRunningOutException
  {
    // Early exit
    if (freeAnts.isEmpty()) return;

    // Debug
    if (debugStream != null)
    {
      debugStream.println("\tmoveIdleAnts time = " + ants.getTurnTimeRemaining() + " default = " + defaultTarget + " free = " + freeAnts.size());
    }

    // Compute default target
    if (defaultTarget == null || !ants.getTile(defaultTarget).hasEnemyHill())
    {
      defaultTarget  = null;
      Coord source   = hillToDefend != null ? hillToDefend : freeAnts.iterator().next();
      int   distance = Integer.MAX_VALUE;
      for (int row = 0; row < Coord.rows; ++row) for (int col = 0; col < Coord.cols; ++col)
      {
        Tile tile = ants.getTile(row, col);
        if (tile.hasEnemyHill())
        {
          int d = tile.getCoord().getDistance2(source);
          if (distance > d)
          {
            distance      = d;
            defaultTarget = tile.getCoord();
          }
        }
      }
    }

    // Compute target
    Coord target = defaultTarget != null ? defaultTarget : tilesToExplore.get(0);
    if (target == null) return; // Shouldn't happen

    // Move ants
    ArrayList<Coord> antList = new ArrayList<Coord>(freeAnts);
    PathFinder       path    = new PathFinder(land, target);
    for (Coord ant : antList)
    {
      checkTime();
      path.getDistance(ant);
      List<Coord> moves = path.getSortedMoves(this, ant);
      doMoveIntelligently(ant,  moves);
      if (overlay != null && overlay.isActive(Overlay.Type.IDLE)) overlay.arrow(ant, target, Overlay.LineColor.GREEN);
    }

    // Logging
    if (debugStream != null)
    {
      debugStream.println("\t\tdetault = " + defaultTarget + " target = " + target + " free = " + freeAnts.size());
    }
  }

  private void collisionAvoidance()
  {
    ArrayList<Coord> stopped = new ArrayList<Coord>(freeAnts);
    for (Coord ant : stopped) trainWreck(ant);
  }

  /**
   * Make analysis for debugging
   * - Check for jammed anthill
   */
  private void debug()
  {
    if (debugStream == null) return;
    Set<Coord> moved = new HashSet<Coord>();
    for (Entry<Coord, Coord> entry : destinationToSource.entrySet())
    {
      Coord destination = entry.getKey();
      Coord source = entry.getValue();
      moved.add(source);
      if (ants.getMyHills().contains(destination))
      {
        debugStream.println("\tBLOCKED HILL: " + source + " -> " + destination);
      }
    }
    for (Coord hill : ants.getMyHills())
    {
      if (ants.getTile(hill).hasOwnAnt() && !moved.contains(hill))
      {
        debugStream.println("\tBLOCKED HILL: " + hill + " -> " + hill);
      }
    }
  }

  private void issueOrders()
  {
    // Debug
    if (debugStream != null)
    {
      debugStream.println("\tissueOrders time = " + ants.getTurnTimeRemaining());
    }

    for (Entry<Coord, Coord> entry : destinationToSource.entrySet())
    {
      Coord destination = entry.getKey();
      Coord source      = entry.getValue();
      if (!source.equals(destination)) issueOrder(source,  source.getDirection(destination));
    }
  }

  /**
   * If no hill avoid any trade.
   * If near last hill, move avoiding death or move ignoring enemy according to distance
   * If winning move ignoring enemies
   * Normally move avoiding trade or avoiding death randomly.
   * @param source ant location
   * @param moves sorted ant destinations
   */
  public Coord doMoveIntelligently(Coord source, List<Coord> moves)
  {
    return getBattleMode(source).move(this, source, moves);
  }

  /**
   * Move an ant avoiding any trade.
   * @param source ant location
   * @param moves sorted ant destinations
   */
  public Coord doMoveCarefully(Coord source, List<Coord> moves)
  {
    // Find a safe move
    for (Coord move : moves)
    {
      if (!isOccupied(move) && !ants.getTile(move).isBlocked() && safeLand[move.row][move.col])
      {
        doMove(source, move);
        return move;
      }
    }
    return doMoveBoldly(source, moves);
  }

  /**
   * Move an ant avoiding 2 vs 1 death.
   * @param source ant location
   * @param moves sorted ant destinations
   */
  public Coord doMoveBoldly(Coord source, List<Coord> moves)
  {
    // Try a non suicidable move
    for (Coord move : moves)
    {
      if (!isOccupied(move) && !ants.getTile(move).isBlocked() && tradeLand[move.row][move.col])
      {
        doMove(source, move);
        return move;
      }
    }
    return doMoveFearlessly(source, moves);
  }

  /**
   * Move an ant disregarding enemies.
   * @param source ant location
   * @param moves sorted ant destinations
   */
  public Coord doMoveFearlessly(Coord source, List<Coord> moves)
  {
    // Try anything
    for (Coord move : moves)
    {
      if (!isOccupied(move) && !ants.getTile(move).isBlocked())
      {
        doMove(source, move);
        return move;
      }
    }

    // No valid move!
    trainWreck(source);
    return source;
  }

  private void updateInfluence(Coord ant)
  {
    for (StencilIterator iter = new StencilIterator(ant, Coord.attackRadius2, 0); iter.hasNext();)
    {
      Coord c = iter.next();
      ++influence[c.row][c.col];
    }
  }

  public void doMove(Coord source, Coord destination)
  {
    freeAnts.remove(source);
    destinationToSource.put(destination, source);
    updateInfluence(destination);
  }

  /**
   * If is possible that there is no left move for an ant, not even staying it place if
   * another ant as already decided to take our place. Stop this other ant, which
   * may require stopping another that was expecting to move in, etc.
   * Stop the whole thing.
   * @param ant Ant with no move
   */
  private void trainWreck(Coord ant)
  {
  if (destinationToSource.containsValue(ant)) throw new RuntimeException("Duplicate source " + ant);
    freeAnts.remove(ant);
    for (; ant != null; ant = destinationToSource.put(ant, ant)) updateInfluence(ant);
  }

  public void checkTime() throws TimeRunningOutException
  {
    if (inputStream == null && Tile.getTurn() >= 0 && ants.isTurnTimeCritical()) throw new TimeRunningOutException();
  }

  public BattleMode getBattleMode(Coord ant)
  {
    BattleMode mode = battleMode.get(ant);
    return mode == null ? BattleMode.BOLD : mode;
  }

  public void addAvailableInTheFuture(Coord ant, int turn)
  {
    availableInTheFuture.put(ant, Integer.valueOf(turn));
  }

  public Map<Coord, Integer> getAvailableInTheFuture()      { return availableInTheFuture; }
  public PrintStream         getDebugStream()               { return debugStream; }
  public Overlay             getOverlay()                   { return overlay; }
  public Ants                getAnts()                      { return ants; }
  public Set<Coord>          getFreeAnts()                  { return freeAnts; }
  public Random              getRandom()                    { return random; }
  public int                 getInfluence(int row, int col) { return influence[row][col]; }
  public boolean             isOccupied(Coord destination)  { return destinationToSource.containsKey(destination); }
  public List<Coord>         getTilesToExplore()            { return tilesToExplore; }
  public boolean[][]         getUnblockedLand()             { return unblockedLand; }
  public boolean[][]         getLand()                      { return land; }
  public boolean[][]         getSniperLand()                { return sniperLand; }
}
