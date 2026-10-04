public final class CoordDistance implements Comparable<CoordDistance>
{
  public final Coord coord;
  public final int   distance;

  public CoordDistance(Coord coord, int distance)
  {
    this.coord    = coord;
    this.distance = distance;
  }

  @Override
  public int compareTo(CoordDistance o)
  {
    return distance - o.distance;
  }
}
