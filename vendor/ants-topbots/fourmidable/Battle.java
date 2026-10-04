import java.io.*;
import java.util.*;

public final class Battle
{
  private final MyBot       bot;
  private final PrintStream debugStream;
  private final Ants        ants;
  private final Overlay     overlay;

  public Battle(MyBot bot)
  {
    this.bot         = bot;
    this.debugStream = bot.getDebugStream();
    this.ants        = bot.getAnts();
    this.overlay     = bot.getOverlay();
  }

  public void doBattle() throws TimeRunningOutException
  {
    // Early exit
    Set<Coord> freeAnts = bot.getFreeAnts();
    if (freeAnts.isEmpty()) return;

    // Debug
    if (debugStream != null)
    {
      debugStream.println("\tdoBattle time = " + ants.getTurnTimeRemaining() + " free = " + freeAnts.size());
    }

    // For each visible enemy, find distance to closest of ours
    ArrayList<CoordDistance> sortedEnemies = sortEnemies();

    // Process each enemy ant
    for (CoordDistance cd : sortedEnemies)
    {
      bot.checkTime();
      Coord   enemy1 = cd.coord;
      Coord[] ownSrc = selectAttackingAnts(enemy1, 4);
      if (ownSrc != null)
      {
        Coord   enemy2 = selectDefending(enemy1, ownSrc);
        Coord[] oppSrc = enemy2 == null ? new Coord[]{enemy1} : new Coord[]{enemy1, enemy2};
        // Coord[] oppSrc = selectDefendingAnts(enemy1, ownSrc, 3);
        BattleMode   mode   = bot.getBattleMode(ownSrc[bot.getRandom().nextInt(ownSrc.length)]);
        if (debugStream != null) debugStream.println("\t\tdoBattle: mode = " + mode + " ownSrc = " + Arrays.toString(ownSrc) + " oppSrc = " + Arrays.toString(oppSrc));
        BattleResult result = new BattleResult();
        simulateOwn(ownSrc.length, ownSrc, oppSrc, new Coord[ownSrc.length], new Coord[oppSrc.length], new boolean[ownSrc.length], mode, result);
        if (result.good())
        {
          if (debugStream != null) debugStream.println("\t\tdoBattle: Result " + result);
          if (overlay != null && overlay.isActive(Overlay.Type.BATTLE)) for (int i = 0; i < ownSrc.length; ++i) if (result.moves[i] != null) for (Coord opp : oppSrc) overlay.line(ownSrc[i],  opp, Overlay.LineColor.WHITE);
          for (int i = 0; i < ownSrc.length; ++i) if (result.moves[i] != null) bot.doMove(ownSrc[i], result.moves[i]);
        }
      }
    }
  }

  private void simulateOwn(int m, Coord[] ownSrc, Coord[] oppSrc, Coord[] ownDst, Coord[] oppDst, boolean[] ownDanger, BattleMode mode, BattleResult result)
  {
    if (--m >= 0)
    {
      ownDst[m]    = null;
      ownDanger[m] = false;
      simulateOwn(m, ownSrc, oppSrc, ownDst, oppDst, ownDanger, mode, result);
      for (Coord dst : ownSrc[m].getMovesIncludingSleeping(ants))
      {
        if (!bot.isOccupied(dst) && !coordArrayContains(ownDst, m + 1, ownDst.length, dst))
        {
          ownDst[m]       = dst;
          ownDanger[m]    = false;
          boolean inRange = false; // Check if targetted ant in range
          for (StencilIterator iter = new StencilIterator(dst, Coord.attackRadius2, 1); iter.hasNext();)
          {
            Coord c = iter.next();
            if (ants.getTile(c).hasVisibleEnemyAnt())
            {
              if (coordArrayContains(oppSrc, 0, oppSrc.length, c))
              {
                inRange = true;
              }
              else
              {
                Coord predicted = ants.getVisibleEnemyAntPrediction(c);
                if (predicted == null || predicted.getDistance2(dst) <= Coord.attackRadius2)
                {
                  ownDanger[m] = true;
                }
                else
                {
                  if (overlay != null) overlay.circle(c, 1, Overlay.LineColor.RED);
                }
              }
            }
          }

          // Try this move only if in range of at least one enemy.
          if (inRange) simulateOwn(m, ownSrc, oppSrc, ownDst, oppDst, ownDanger, mode, result);
        }
      }
    }
    else
    {
      BattleResult r = new BattleResult();
      simulateOpp(oppSrc.length, oppSrc, ownDst, oppDst, ownDanger, mode, r);
      if (r.compareTo(result) > 0)
      {
        result.update(r, ownDst);
      }
    }
  }

  private void simulateOpp(int n, Coord[] oppSrc, Coord[] ownDst, Coord[] oppDst, boolean[] ownDanger, BattleMode mode, BattleResult result)
  {
    if (--n >= 0)
    {
      // Move opp ant.
      for (Coord dst : getPredictedEnemyMoves(oppSrc[n]))
      {
        if (!coordArrayContains(oppDst, n + 1, oppDst.length, dst))
        {
          oppDst[n] = dst;
          simulateOpp(n, oppSrc, ownDst, oppDst, ownDanger, mode, result);
        }
      }
    }
    else
    {
      resolve(ownDst, oppDst, ownDanger, mode, result);
    }
  }

  private List<Coord> getPredictedEnemyMoves(Coord enemy)
  {
    Coord predicted = ants.getVisibleEnemyAntPrediction(enemy);
    if (predicted != null)
    {
      if (overlay != null && overlay.isActive(Overlay.Type.BATTLE)) overlay.circle(predicted, 1, Overlay.LineColor.GREEN);
      return Arrays.asList( predicted );
    }
    return enemy.getMovesIncludingSleeping(ants);
  }

  private void resolve(Coord[] ownDst, Coord[] oppDst, boolean[] ownDanger, BattleMode mode, BattleResult result)
  {
    // Count number of threats for each ant
    // Enemy threatened by moves already made and attacking ants
    // Attacking ants threatened by defending ants and potential attacks
    int[] ownCount = new int[ownDst.length];
    int[] oppCount = new int[oppDst.length];
    for (int j = 0; j < oppCount.length; ++j)
    {
      oppCount[j] = bot.getInfluence(oppDst[j].row, oppDst[j].col);
      for (int i = 0; i < ownCount.length; ++i)
      {
        if (ownDst[i] != null && ownDst[i].getDistance2(oppDst[j]) <= Coord.attackRadius2)
        {
          ++ownCount[i];
          ++oppCount[j];
        }
      }
    }

    // Compare each threat level to max of opponent threat in range.
    int ownDead   = 0;
    int oppKilled = 0;
    for (int i = 0; i < ownCount.length; ++i)
    {
      if (ownDst[i] == null)
      {
        // Ignore
      }
      else if (ownDanger[i])
      {
        ++ownDead;
      }
      else for (int j = 0; j < oppCount.length; ++j)
      {
        if (oppCount[j] <= ownCount[i] && ownDst[i].getDistance2(oppDst[j]) <= Coord.attackRadius2)
        {
          ++ownDead;
          break;
        }
      }
    }
    for (int j = 0; j < oppCount.length; ++j)
    {
      for (int i = 0; i < ownCount.length; ++i)
      {
        if (ownDst[i] != null && ownCount[i] <= oppCount[j] && ownDst[i].getDistance2(oppDst[j]) <= Coord.attackRadius2)
        {
          ++oppKilled;
          break;
        }
      }
    }

    // Remember the best outcome and the worse outcome.
    int score = mode.getScore(ownDead, oppKilled);
    if (result.best < score)
    {
      result.best  = score;
      result.nBest = 1;
    }
    else if (result.best == score)
    {
      ++result.nBest;
    }
    if (result.worse > score)
    {
      result.worse  = score;
      result.nWorse = 1;
    }
    else if (result.worse == score)
    {
      ++result.nWorse;
    }
  }

  private boolean coordArrayContains(Coord[] coordArray, int start, int end, Coord c)
  {
    for (int i = start; i < end; ++i) if (c.equals(coordArray[i])) return true;
    return false;
  }

  private Coord selectDefending(Coord enemy, Coord[] attackingAnts)
  {
    Coord selected = null;
    int   distance = Integer.MAX_VALUE;
    for (StencilIterator iter = new StencilIterator(enemy, Coord.attackRadius2, 2); iter.hasNext();)
    {
      Coord c = iter.next();
      if (ants.getTile(c).hasVisibleEnemyAnt() && !c.equals(enemy))
      {
        int d = c.getDistance2(enemy);
        for (Coord ant : attackingAnts) d += c.getDistance2(ant);
        if (distance > d)
        {
          distance = d;
          selected = c;
        }
      }
    }
    if (selected != null)
    {
      StencilIterator iter2 = new StencilIterator(selected, Coord.attackRadius2, 2);
      for (Coord ant : attackingAnts) if (iter2.contains(ant)) return selected;
    }
    return null;
  }

  @SuppressWarnings("unused")
  private Coord[] selectDefendingAnts(final Coord enemy, final Coord[] attackingAnts, int n)
  {
    ArrayList<Coord> neighbours = new ArrayList<Coord>(n);
    for (StencilIterator iter = new StencilIterator(enemy, Coord.attackRadius2, 2); iter.hasNext();)
    {
      Coord c = iter.next();
      if (ants.getTile(c).hasVisibleEnemyAnt() && !c.equals(enemy))
      {
        StencilIterator iter2 = new StencilIterator(c, Coord.attackRadius2, 2);
        for (Coord ant : attackingAnts) if (iter2.contains(ant))
        {
          neighbours.add(c);
          break;
        }
      }
    }
    Collections.sort(neighbours, new Comparator<Coord>()
    {
      @Override public int compare(Coord c1, Coord c2)
      {
        int d = c1.getDistance2(enemy) - c2.getDistance2(enemy);
        for (Coord c : attackingAnts) d += c1.getDistance2(c) - c2.getDistance2(c);
        return d;
      }
    });
    int size = Math.min(n, 1 + neighbours.size());
    Coord[] result = new Coord[size];
    result[0] = enemy;
    for (int i = 1; i < size; ++i) result[i] = neighbours.get(i - 1);
    return result;
  }

  private Coord[] selectAttackingAnts(final Coord enemy, int n)
  {
    // Find all our ants that could possible get into attack range.
    Set<Coord>  freeAnts = bot.getFreeAnts();
    List<Coord> ownAnts  = new ArrayList<Coord>(n + 1);
    for (StencilIterator iter = new StencilIterator(enemy, Coord.attackRadius2, 2); iter.hasNext();)
    {
      Coord ant = iter.next();
      if (ants.getTile(ant).hasOwnAnt() && freeAnts.contains(ant)) ownAnts.add(ant);
    }
    int size = ownAnts.size();
    if (size <  2) return null;
    if (size <= n) return ownAnts.toArray(new Coord[size]);

    // We have too many ants, use heuristic to pick some:
    // 1) For each possible own leader ant
    // 2) Find 'n - 1' sidekicks closest to both leader and enemy
    // 3) Remember the group with the smallest total distance
    Coord[] sortedAnts    = ownAnts.toArray(new Coord[size]);
    int     bestDistance  = Integer.MAX_VALUE;
    Coord[] bestAttacking = null;
    for (final Coord leader : ownAnts)
    {
      Arrays.sort(sortedAnts, new Comparator<Coord>()
      {
        @Override public int compare(Coord o1, Coord o2)
        {
          if (leader.equals(o1)) return  1;
          if (leader.equals(o2)) return -1;
          return (o1.getDistance2(leader) + o1.getDistance2(enemy)) - (o2.getDistance2(leader) + o2.getDistance2(enemy));
        }
      });
      if (!leader.equals(sortedAnts[size - 1])) throw new RuntimeException("internal error");
      swap(sortedAnts, n - 1, size - 1);
      int d = 0;
      for (int i = 0; i < n; ++i) d += sortedAnts[i].getDistance2(leader) + sortedAnts[i].getDistance2(enemy);
      if (bestDistance > d)
      {
        bestDistance  = d;
        bestAttacking = Arrays.copyOfRange(sortedAnts, 0, n);
      }
    }
    return bestAttacking;
  }

  private static void swap(Object[] x, int a, int b)
  {
    Object t = x[a];
    x[a] = x[b];
    x[b] = t;
  }

  private ArrayList<CoordDistance> sortEnemies()
  {
    Collection<Coord> freeAnts  = bot.getFreeAnts();
    Collection<Coord> enemyAnts = ants.getVisibleEnemyAnts();
    ArrayList<CoordDistance> enemyList = new ArrayList<CoordDistance>(enemyAnts.size());
    for (Coord enemy : enemyAnts)
    {
      int distance = Integer.MAX_VALUE;
      for (Coord ant : freeAnts)
      {
        int d = enemy.getDistance2(ant);
        if (distance > d) distance = d;
      }
      enemyList.add(new CoordDistance(enemy, distance));
    }
    Collections.shuffle(enemyList, bot.getRandom());
    Collections.sort(enemyList);
    return enemyList;
  }

}
