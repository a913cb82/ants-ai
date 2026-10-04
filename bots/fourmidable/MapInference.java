import java.io.*;
import java.util.*;
import java.util.Map.Entry;

public final class MapInference
{
  private static int FINAL_ANALYSIS_TRIGGER = 50;
  private static int factors [][][] =
  {
    null,
    null,
    { {  2 } },
    { {  3 } },
    { {  4 }, { 2, 2 } },
    { {  5 } },
    { {  6 }, { 2, 3 } },
    { {  7 } },
    { {  8 }, { 2, 4 }, { 2, 2, 2 } },
    { {  9 }, { 3, 3 } },
    { { 10 }, { 2, 5 } },
  };

  private final MyBot                             bot;
  private final PrintStream                       debugStream;
  private final Overlay                           overlay;
  private final Ants                              ants;
  private       Map<Transform, Set<TransformSet>> setsPerTransform;
  private       TransformSet                      finalTransformSet;
  private       TransformSet                      bestEffortSet;
  private       int                               evidenceThreshold = MyBot.EVIDENCE_THRESHOLD;

  public MapInference(MyBot bot)
  {
    this.bot         = bot;
    this.debugStream = bot.getDebugStream();
    this.ants        = bot.getAnts();
    this.overlay     = bot.getOverlay();
  }

  public void initialize()
  {
    int cols         = Coord.cols;
    int rows         = Coord.rows;
    int maxType      = (cols == rows ? Transform.MAX_TYPE : Transform.MAX_REGULAR_TYPE);
    setsPerTransform = new TreeMap<Transform, Set<TransformSet>>();

    // Calculate basic transform sets
    for (int row = 0; row < rows; row++)
    {
      for (int col = 0; col < cols; col++)
      {
        for (int type=0; type < maxType; ++type)
        {
          if (type==0 && col==0 && row==0) continue; // skip basic identity transform
          Transform    base = new Transform(type,col,row);
          TransformSet set  = new TransformSet(base);
          Transform    next = base;
          while (set.size() <= Ants.MAX_PLAYERS)
          {
            next = base.multiply(next);
            if (set.contains(next))
            {
              if (set.isClosed())
              {
                for (Transform t : set)
                {
                  if (t.isIdentity()) continue;
                  Set<TransformSet> setOfSets = setsPerTransform.get(t);
                  if (setOfSets == null)
                  {
                    setOfSets = new TreeSet<TransformSet>();
                    setsPerTransform.put(t, setOfSets);
                  }
                  setOfSets.add(set);
                }
              }
              break;
            }
            set.add(next);
          }
        }
      }
    }
    if (debugStream != null) debugStream.println("Starting out with tranforms size=" + setsPerTransform.keySet().size());
  }

  public void doMapInference() throws TimeRunningOutException
  {
    // Debug
    if (debugStream != null)
    {
      debugStream.println("\tmapInference time = " + ants.getTurnTimeRemaining() + " free = " + bot.getFreeAnts().size());
    }

    // Surrounded by water.
    checkReachability();

    // Transformation processing
    bot.checkTime();
    if (finalTransformSet != null)
    {
      incrementalInference();
    }
    else if (setsPerTransform != null)
    {
      analyze();
      TransformSet tranformSet = computeFinalTransformSet();
      if (tranformSet == null)
      {
        TransformSet possibleTransform = bestEffortTransform();
        if (bestEffortSet != null && !bestEffortSet.equals(possibleTransform)) unInferAllIfNeeded();
        if (bestEffortSet == null && possibleTransform != null)
        {
          if (debugStream != null) debugStream.println("\t\tfound best effort transform size = " + possibleTransform.size());
          initialInference(possibleTransform);
          bestEffortSet = possibleTransform;
        }
      }
      else if (!tranformSet.isClosed())
      {
        if (debugStream != null) debugStream.println("\t\tERROR: internal contradiction - no solution");
        unInferAllIfNeeded();
        setsPerTransform = null;
      }
      else
      {
        if (debugStream != null) debugStream.println("\t\tfound final transform size = " + tranformSet.size());
        if (!tranformSet.equals(bestEffortSet))
        {
          unInferAllIfNeeded();
          initialInference(tranformSet);
        }
        finalTransformSet = tranformSet;
        bestEffortSet     = null;
        setsPerTransform  = null;
      }
    }
    if (overlay != null && overlay.isActive(Overlay.Type.INFER))
    {
      for (int r = 0; r < Coord.rows; ++r) for (int c = 0; c < Coord.cols; ++c)
      {
        Tile tile = ants.getTile(r, c);
        Overlay.LineColor lColor = finalTransformSet == null ? Overlay.LineColor.RED : Overlay.LineColor.GREEN;
        if (tile.hasInferredHill()) overlay.star(tile.getCoord(), 2, lColor);
        if (tile.hasRecentInferredFood(MyBot.STALE_FOOD)) overlay.circle(tile.getCoord(), 2, lColor);
      }
    }
  }

  private void checkReachability() throws TimeRunningOutException
  {
    // Unreachable squares must be water if all ants are connected
    int rows = Coord.rows;
    int cols = Coord.cols;
    if (!ants.getMyAnts().isEmpty())
    {
      // Flood from the first ant
      bot.checkTime();
      Coord      ant       = ants.getMyAnts().iterator().next();
      PathFinder path      = new PathFinder(bot.getLand(), ant);
      boolean    connected = true;
      int        count     = 0;
      for (Coord coord : ants.getMyAnts()) if (path.getDistance(coord) == PathFinder.NO_PATH) connected = false;
      if (connected) for (int r = 0; r < rows; ++r) for (int c = 0; c < cols; ++c)
      {
        Tile tile = ants.getTile(r, c);
        if (!tile.hasBeenSeen() && path.getDistance(tile.getCoord()) == PathFinder.NO_PATH)
        {
          tile.inferWater();
        }
      }
      if (debugStream != null && count != 0) debugStream.println("\t\tunreachable inferred water count = " + count);
    }
  }

  private void analyze() throws TimeRunningOutException
  {
    if (debugStream != null) debugStream.println("\t\tstarting transform analysis toInspect " + ants.getRecentlyDiscovered().size());

    // Eliminate some transforms
    for (Iterator<Coord> iter = ants.getRecentlyDiscovered().iterator(); iter.hasNext(); )
    {
      Coord          coord    = iter.next();
      iter.remove();
      Tile           tile     = ants.getTile(coord);

      // Apply effort transforms if any
      if (bestEffortSet != null)
      {
        for (Coord otherC : bestEffortSet.apply(coord))
        {
          Tile otherTile = ants.getTile(otherC);
          otherTile.inferFrom(tile);
        }
      }

      // Check for contradiction
      Set<Transform> toRemove = new TreeSet<Transform>();
      for (Transform t : setsPerTransform.keySet())
      {
        Coord   tc          = t.apply(tile.getCoord());
        Tile    transformed = ants.getTile(tc);
        if (transformed.hasBeenSeen())
        {
          if (tile.hasWater() && transformed.hasWater())
          {
            t.confirmWater();
          }
          else if (!tile.hasWater() && !transformed.hasWater())
          {
            t.confirmLand();
          }
          else
          {
            toRemove.add(t);
          }
        }
      }
      for (Transform t1 : toRemove)
      {
        Set<TransformSet> setOfSets = setsPerTransform.remove(t1);
        if (setOfSets != null)
        {
          for (TransformSet s : setOfSets)
          {
            for (Transform t2 : s)
            {
              Set<TransformSet> ss2 = setsPerTransform.get(t2);
              if (ss2 != null)
              {
                ss2.remove(s);
                if (ss2.isEmpty())
                {
                  setsPerTransform.remove(t2);
                }
              }
            }
          }
        }
      }
      bot.checkTime();
    }
  }

  private void initialInference(TransformSet transformSet)
  {
    // Use to find all water
    long timestamp = System.currentTimeMillis();
    for (int r = 0; r < Coord.rows; ++r) for (int c = 0; c < Coord.cols; ++c)
    {
      Tile tile = ants.getTile(r, c);
      if (tile.hasSomethingToInfer())
      {
        for (Coord otherC : transformSet.apply(tile.getCoord()))
        {
          ants.getTile(otherC).inferFrom(tile);
        }
      }
    }
    if (debugStream != null)
    {
      int seen             = 0;
      int transformedWater = 0;
      int possibleHills    = 0;
      int inferredFood     = 0;
      for (int r = 0; r < Coord.rows; ++r) for (int c = 0; c < Coord.cols; ++c)
      {
        Tile tile = ants.getTile(r, c);
        if (tile.hasBeenSeen()) ++seen;
        if (tile.hasInferredHill()) ++possibleHills;
        if (tile.hasInferredWater()) ++transformedWater;
        if (tile.hasRecentInferredFood(MyBot.STALE_FOOD)) ++inferredFood;
      }
      for (Transform t : transformSet) debugStream.println("\t\tevidence = " + t.evidence());
      debugStream.println("\t\tpercentage seen = "+ (100.0*seen/(Coord.rows*Coord.cols)) );
      debugStream.println("\t\ttransformed water = " + transformedWater);
      debugStream.println("\t\tinferred food = " + inferredFood);
      debugStream.println("\t\tpossible hills = " + possibleHills);
      debugStream.println("\t\ttime = " + (System.currentTimeMillis() - timestamp));
    }
  }

  private void incrementalInference()
  {
    // infer new stuff from transform set
    for (Iterator<Coord> iter = ants.getRecentlyDiscovered().iterator(); iter.hasNext();)
    {
      Coord       coord      = iter.next();
      Tile        tile       = ants.getTile(coord);
      List<Coord> otherTiles = finalTransformSet.apply(tile.getCoord());
      iter.remove();
      for (Coord otherC : otherTiles)
      {
        Tile otherTile = ants.getTile(otherC);
        if (tile.contradicts(otherTile))
        {
          if (debugStream != null) debugStream.println("\t\tERROR: found transform contradiction!");
          unInferAllIfNeeded();
          return;
        }
        otherTile.inferFrom(tile);
      }
    }
  }

  private TransformSet computeFinalTransformSet() throws TimeRunningOutException
  {
    int minNumPlayers = ants.getMinNumPlayers();
    int numTransforms = setsPerTransform.keySet().size();

    if (numTransforms < minNumPlayers)
    {
      // Simple find only this set is possible
      TransformSet ts = new TransformSet();
      for(Transform t : setsPerTransform.keySet()) ts.add(t);
      return ts;
    }

    if (numTransforms <= FINAL_ANALYSIS_TRIGGER)
    {
      if (debugStream != null)
      {
        debugStream.println("\t\tnumber of transform left = " + numTransforms);
        debugStream.println("\t\tmin number of players = " + minNumPlayers);
      }

      Set<Integer> possibleNumPlayers = new HashSet<Integer>();
      Map<Integer, TreeSet<TransformSet>> setsPerSize = new HashMap<Integer, TreeSet<TransformSet>>();

      // Build sets per size
      for(Transform t : setsPerTransform.keySet())
      {
        Set<TransformSet> setOfSets = setsPerTransform.get(t);
        for(TransformSet set : setOfSets)
        {
          int size = set.size();
          // Fill up setsPerSize
          TreeSet<TransformSet> sizeSet = setsPerSize.get(size);
          if(sizeSet == null)
          {
            sizeSet = new TreeSet<TransformSet>();
            setsPerSize.put(size, sizeSet);
          }
          sizeSet.add(set);

        }
      }

      // Compute potential number of players
      for(int p = minNumPlayers; p <= Ants.MAX_PLAYERS; ++p)
      {
        int factor[][] = factors[p];
        for(int f[] : factor)
        {
          boolean found = true;
          for (int fac : f)
          {
            if (!setsPerSize.containsKey(fac))
            {
              found = false;
              break;
            }
          }
          if (found)
          {
            possibleNumPlayers.add(p);
            break;
          }
        }
      }
      if (debugStream != null) debugStream.println("\t\tstill potential players = " + possibleNumPlayers.size());

      // Compute all complete sets
      TreeSet<TransformSet> sets = new TreeSet<TransformSet>();
      for (int players : possibleNumPlayers)
      {
        int factor[][] = factors[players];
        for(int f[] : factor)
        {
          mergeAndAddNext(setsPerSize, f, 0, null, sets, players);
          bot.checkTime();
        }
      }

      if (debugStream != null) debugStream.println("\t\tnumber of valid sets left = " + sets.size());

      if (sets.size() == 1)
      {
        return sets.first();
      }
    }
    return null;
  }

  private void mergeAndAddNext(Map<Integer, TreeSet<TransformSet>> setsPerSize, int factors[], int curFactor, TransformSet curSet, TreeSet<TransformSet> outSets, int numPlayers) throws TimeRunningOutException
  {
    if (curFactor == factors.length)
    {
      if (curSet.size() == numPlayers && curSet.isClosed())
      {
        outSets.add(curSet);
      }
      return;
    }

    TreeSet<TransformSet> set = setsPerSize.get(factors[curFactor]);
    if (set == null) return;
    Iterator<TransformSet> it = set.descendingIterator();
    while (it.hasNext())
    {
      TransformSet setToMerge = curSet == null ? it.next() : curSet.merge(it.next());
      mergeAndAddNext(setsPerSize, factors, curFactor + 1, setToMerge, outSets, numPlayers);
      bot.checkTime();
    }
  }

  private TransformSet bestEffortTransform() throws TimeRunningOutException
  {
    TransformSet transformSet = null;

    // Raise the evidence threshold until fewer transformed are selected.
    for (;; ++evidenceThreshold)
    {
      bot.checkTime();
      transformSet = new TransformSet();
      for (Entry<Transform, Set<TransformSet>> entry : setsPerTransform.entrySet())
      {
        Transform t = entry.getKey();
        if (t.evidence() >= evidenceThreshold) transformSet.add(t);
        if (transformSet.size() > MyBot.MAX_PLAYER) break;
      }
      for (int size = transformSet.size(); size <= MyBot.MAX_PLAYER; size = transformSet.size())
      {
        transformSet = transformSet.merge(transformSet);
        if (transformSet.size() == size) break;
      }
      if (transformSet.size() <= MyBot.MAX_PLAYER) break;
      if (debugStream != null) debugStream.println("\t\tincreasing evidence threshold to " + (evidenceThreshold + 1));
    }
    return transformSet.size() < 2 && MyBot.MAX_PLAYER < transformSet.size() ? null : transformSet;
  }

  private void unInferAllIfNeeded()
  {
    if (finalTransformSet != null || bestEffortSet != null)
    {
      if (debugStream != null) debugStream.println("\t\tremoving all inferred data due to mismatch");
      finalTransformSet = null;
      bestEffortSet     = null;
      for (int r = 0; r < Coord.rows; ++r) for (int c = 0; c < Coord.cols; ++c) ants.getTile(r, c).unInfer();
    }
  }
}
