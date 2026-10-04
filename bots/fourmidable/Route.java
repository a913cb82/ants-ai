/**
 * Represents a route from one tile to another.
 */
public final class Route implements Comparable<Route>
{
  private final Coord ant;
  private final Coord destination;
  private final int  distance;
  private final PathFinder path;

  public Route(Coord ant, Coord destination, int distance, PathFinder path)
  {
    this.ant = ant;
    this.destination = destination;
    this.distance = distance;
    this.path = path;
  }

  public Coord getAnt()
  {
    return ant;
  }

  public Coord getDestination()
  {
    return destination;
  }

  public int getDistance()
  {
    return distance;
  }

  public PathFinder getPath()
  {
    return path;
  }

  @Override
  public int compareTo(Route route)
  {
    return distance - route.distance;
  }

  @Override
  public int hashCode()
  {
    return ant.hashCode() * Ants.MAX_MAP_SIZE * Ants.MAX_MAP_SIZE + destination.hashCode();
  }

  @Override
  public boolean equals(Object o)
  {
    return o instanceof Route && ant.equals(((Route) o).ant) && destination.equals(((Route) o).destination);
  }

  @Override
  public String toString()
  {
    return "Route " + ant + " -> " + destination + " (" + distance + ")";
  }
}
