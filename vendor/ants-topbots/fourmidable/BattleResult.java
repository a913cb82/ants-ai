import java.util.*;

public final class BattleResult implements Comparable<BattleResult>
{
  public int     worse = Integer.MAX_VALUE;
  public int     best;
  public int     nWorse;
  public int     nBest;
  public Coord[] moves;

  @Override
  public int compareTo(BattleResult other)
  {
    // Return >0 if this is prefered
    if (good() && !other.good()) return  1; // good better than bad
    if (other.good() && !good()) return -1;
    if (best > other.best) return 1; // prefer better best outcome
    if (other.best > best) return -1;
    if (nBest > other.nBest) return 1; // prefer more best instances
    if (other.nBest > nBest) return -1;
    if (worse > other.worse) return 1; // prefer better worse outcome
    if (other.worse > worse) return -1;
    if (other.nWorse > nWorse) return 1; // prefer less worse outcome
    if (nWorse > other.nWorse) return -1;
    return 0;
  }

  /**
   * To be good, the outcome must provide some chance of positive outcome,
   * with no chance of negative outcome. Outcome depends on {@link BattleMode}.
   * @return if acceptable outcome
   */
  public boolean good()
  {
    return best > 0 && worse >= 0;
  }

  public void update(BattleResult other, Coord[] ownDst)
  {
    worse = other.worse;
    best  = other.best;
    nWorse = other.nWorse;
    nBest  = other.nBest;
    moves  = Arrays.copyOf(ownDst, ownDst.length);
  }

  @Override
  public String toString()
  {
    StringBuilder buffer = new StringBuilder();
    buffer.append("good = ").append(good());
    buffer.append(" best = ").append(best).append(" nBest = ").append(nBest);
    buffer.append(" worse = ").append(worse).append(" nWorse = ").append(nWorse);
    buffer.append(" moves = ").append(Arrays.toString(moves));
    return buffer.toString();
  }
}
