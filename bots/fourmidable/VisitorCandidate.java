public final class VisitorCandidate implements Comparable<VisitorCandidate>
{
  public final Coord      ant;
  public final Coord      target;
  public final int        value;
  public final double     score;
  public final PathFinder path;

  public VisitorCandidate(Coord ant, Coord target, int value, double score, PathFinder path)
  {
    this.ant    = ant;
    this.target = target;
    this.value  = value;
    this.path   = path;
    this.score  = score;
  }

  @Override
  public int compareTo(VisitorCandidate o)
  {
    // Prefer highest score
    if (score > o.score) return -1;
    if (score < o.score) return 1;

    // Prefer smaller value for immediate results.
    if (value < o.value) return -1;
    if (value > o.value) return 1;

    // Equivalent.
    return 0;
  }
}
