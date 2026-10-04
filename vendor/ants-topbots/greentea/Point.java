import java.util.*;

public class Point
{
   private static final int CACHE_SIZE = 500;
   private static Point[][] cache = new Point[CACHE_SIZE][CACHE_SIZE];

   public final int x;
   public final int y;
   public int tag;
   private final int newHashCode;
   private final int hashCode;

   public static Point get(int x, int y)
   {
      Point res = cache[x][y];
      if (res == null)
      {
         res = new Point(x, y);
         cache[x][y] = res;
      }

      return res;
   }

   private Point(int x, int y)
   {
      this.x = x;
      this.y = y;

      this.hashCode = this.x * 65536 + this.y;

      int i = this.x * 599 + this.y;
      this.newHashCode =  i*i;
   }

   public int dX(Point other)
   {
      int dx = Math.abs(x - other.x);
      dx = Math.min(dx, Ants.getColumns() - dx);
      return dx;
   }

   public int dY(Point other)
   {
      int dy = Math.abs(y - other.y);
      dy = Math.min(dy, Ants.getRows() - dy);
      return dy;
   }

   public int distanceInCellsTo(Point other)
   {
      int dx = dX(other);
      int dy = dY(other);

      return dx + dy;
   }

   private int squaredDistanceTo(int dx, int dy)
   {
      return dx*dx + dy*dy;
   }

   public int squaredDistanceTo(Point other)
   {
      int dx = dX(other);
      int dy = dY(other);

      return squaredDistanceTo(dx, dy);
   }

   public boolean isNearToSquaredDist(Point other, int squaredDist)
   {
      boolean res = false;
      for (Direction d : Direction.values)
      {
         Point next = plus(d);
         if (next.squaredDistanceTo(other) <= squaredDist && !next.getType().isWater())
         {
            res = true;
            break;
         }
      }

      return res;
   }

   public List<Point> filterNearToSquaredRangeFromPoints(Collection<Point> points, int squaredDist)
   {
      List<Point> res = new ArrayList<Point>();

      for (Point p : points)
      {
         if (p.isNearToSquaredDist(this, squaredDist))
         {
            res.add(p);
         }
      }

      return res;
   }

   public List<Point> filterNearToSquaredRangeFromAnt(Collection<Point> points, int squaredDist)
   {
      List<Point> res = new ArrayList<Point>();

      for (Point p : points)
      {
         if (isNearToSquaredDist(p, squaredDist))
         {
            res.add(p);
         }
      }

      return res;
   }

   public boolean isNear2ToSquaredRange(Point other, int squaredDist)
   {
      int dx = dX(other);
      int dy = dY(other);

      boolean inaccurateRes = (dx > 1 && squaredDistanceTo(dx - 2, dy) <= squaredDist) ||
            (dx > 0 && dy > 0 && squaredDistanceTo(dx - 1, dy - 1) <= squaredDist) ||
            (dy > 1 && squaredDistanceTo(dx, dy - 2) <= squaredDist);
      if (!inaccurateRes)
      {
         return false;
      }

      List<Point> nextMyPoints = new ArrayList<Point>();
      nextMyPoints.add(this);
      for (Direction d1 : Direction.values)
      {
         nextMyPoints.add(plus(d1));
      }

      for (Point next1 : nextMyPoints)
      {
         if (!next1.getType().isWater())
         {
            if (next1.squaredDistanceTo(other) <= squaredDist)
            {
               return true;
            }

            for (Direction d2 : Direction.values)
            {
               Point next2 = other.plus(d2);
               if (next1.squaredDistanceTo(next2) <= squaredDist && !next2.getType().isWater())
               {
                  return true;
               }
            }
         }
      }

      return false;
   }

   private boolean isSomePointInSquaredDist(Point other, int squaredDist, int[] x, int[] y)
   {
      for (int i = 0; i < x.length; ++i)
      {
         Vector v = new Vector(x[i], y[i]);
         Point newPoint = plus(v);
         if (newPoint.squaredDistanceTo(other) <= squaredDist && !newPoint.getType().isWater())
         {
            return true;
         }
      }

      return false;
   }

   public List<Point> filterNear2ToSquaredRange(Collection<Point> points, int squaredRadius)
   {
      List<Point> res = new ArrayList<Point>();

      for (Point p : points)
      {
         if (isNear2ToSquaredRange(p, squaredRadius))
         {
            res.add(p);
         }
      }

      return res;
   }

   public Point getNearest(Collection<Point> points, boolean includeThis)
   {
      int minDist = Integer.MAX_VALUE;
      Point nearestPoint = null;
      for (Point target : points)
      {
         int distance = distanceInCellsTo(target);
         if (distance < minDist && (includeThis || distance > 0))
         {
            minDist = distance;
            nearestPoint = target;
         }
      }

      return nearestPoint;
   }

   public int getMinDist(Collection<Point> points)
   {
      int minDist = Integer.MAX_VALUE;
      for (Point target : points)
      {
         int distance = distanceInCellsTo(target);
         if (distance < minDist)
         {
            minDist = distance;
         }
      }

      return minDist;
   }

   public int getMinSquaredDist(Collection<Point> points)
   {
      int minDist = Integer.MAX_VALUE;
      for (Point target : points)
      {
         int distance = squaredDistanceTo(target);
         if (distance < minDist)
         {
            minDist = distance;
         }
      }

      return minDist;
   }

   public Point getNearestHalfX(Collection<Point> points, boolean includeThis)
   {
      return getNearestX(getNearest(points, 3, includeThis), includeThis);
   }

   public Point getNearestX(Collection<Point> points, boolean includeThis)
   {
      int minDist = Integer.MAX_VALUE;
      Point nearestPoint = null;
      for (Point target : points)
      {
         int distance = findShortestPathLen(target, 25);
         if (distance < minDist && (includeThis || distance > 0))
         {
            minDist = distance;
            nearestPoint = target;
         }
      }

      return nearestPoint;
   }

   public List<Point> getMultipleNearestHalfX(Collection<Point> points, boolean includeThis)
   {
      return getMultipleNearestX(getNearest(points, 5, includeThis), includeThis);
   }

   public List<Point> getMultipleNearestX(Collection<Point> points, boolean includeThis)
   {
      int minDist = Integer.MAX_VALUE;
      List<Point> nearestPoints = new ArrayList<Point>();
      for (Point target : points)
      {
         int distance = findShortestPathLen(target, 25);
         if (includeThis || distance > 0)
         {
            if (distance < minDist)
            {
               nearestPoints.clear();
            }
            if (distance <= minDist)
            {
               minDist = distance;
               nearestPoints.add(target);
            }
         }
      }

      return nearestPoints;
   }

   public List<Point> getNearest(Collection<Point> pointsCollection, int count, boolean includeThis)
   {
      List<Point> points = new ArrayList<Point>(pointsCollection);
      List<Point> res = new ArrayList<Point>(count);

      for (int k = 0; k < points.size(); ++k)
      {
         int minDist = Integer.MAX_VALUE;
         int nearestIndex = -1;
         Point nearest = null;
         for (int i = 0; i < points.size(); ++i)
         {
            Point p = points.get(i);
            if (p != null)
            {
               int dist = distanceInCellsTo(p);
               if (dist < minDist  && (includeThis || dist > 0))
               {
                  minDist = dist;
                  nearest = p;
                  nearestIndex = i;
               }
            }
         }

         if (nearest != null)
         {
            res.add(nearest);
            points.set(nearestIndex, null);

            if (res.size() == count)
            {
               break;
            }
         }
      }

      return res;
   }

   public List<Direction> findShortestPath(Point p2)
   {
      return PathFinding.findShortestPath(Ants.getInstance().getMap(), this, p2);
   }

   public int findShortestPathLen(Point p2)
   {
      return PathFinding.findShortestPathLen(Ants.getInstance().getMap(), this, p2);
   }

   public List<Direction> findShortestPath(Point p2, int maxSearchDepth)
   {
      return PathFinding.findShortestPath(Ants.getInstance().getMap(), this, p2, maxSearchDepth);
   }

   public int findShortestPathLen(Point p2, int maxSearchDept)
   {
      return PathFinding.findShortestPathLen(Ants.getInstance().getMap(), this, p2, maxSearchDept);
   }

   public int sumSquaredDistance(Collection<Point> points)
   {
      int res = 0;
      for (Point p : points)
      {
         res += squaredDistanceTo(p);
      }

      return res;
   }

   public int sumDistance(Collection<Point> points)
   {
      int res = 0;
      for (Point p : points)
      {
         res += distanceInCellsTo(p);
      }

      return res;
   }

   public List<Point> sortByDistance(Collection<Point> points)
   {
      List<Point> sorted = new ArrayList<Point>(points);
      Collections.sort(sorted, new Comparator<Point>() {
         public int compare(Point p1, Point p2)
         {
            Integer dist1 = distanceInCellsTo(p1);
            Integer dist2 = distanceInCellsTo(p2);

            return dist1.compareTo(dist2);
         }
      });

      return sorted;
   }

   public PointType getType(Ants ants)
   {
      return ants.getPointType(this);
   }

   public PointType getType()
   {
      return Ants.getInstance().getPointType(this);
   }

   public List<Point> inRange(Collection<Point> points, int minDist, int maxDist)
   {
      List<Point> res = new ArrayList<Point>();
      for (Point p : points)
      {
         int dist = distanceInCellsTo(p);
         if (dist >= minDist && dist <= maxDist)
         {
            res.add(p);
         }
      }

      return res;
   }

   public List<Point> inRange(Collection<Point> points, int maxRange)
   {
      return inRange(points, 0, maxRange);
   }

   public Set<Point> inRangeSet(Collection<Point> points, int minDist, int maxDist)
   {
      Set<Point> res = new HashSet<Point>();
      for (Point p : points)
      {
         int dist = distanceInCellsTo(p);
         if (dist >= minDist && dist <= maxDist)
         {
            res.add(p);
         }
      }

      return res;
   }

   public Set<Point> inRangeSet(Collection<Point> points, int maxRange)
   {
      return inRangeSet(points, 0, maxRange);
   }

   public List<Point> inSquaredDistance(Collection<Point> points, int minDist, int maxDist)
   {
      List<Point> res = new ArrayList<Point>();
      for (Point p : points)
      {
         int dist = squaredDistanceTo(p);
         if (dist >= minDist && dist <= maxDist)
         {
            res.add(p);
         }
      }

      return res;
   }

   public List<Point> inSquaredDistance(List<Point> points, int maxDist)
   {
      return inSquaredDistance(points, 0, maxDist);
   }

   public List<Point> inSquaredDistance(List<Point> points, int minDist, int maxDist)
   {
      List<Point> res = new ArrayList<Point>();
      for (int i = 0; i < points.size(); ++i)
      {
         Point p = points.get(i);
         int dist = squaredDistanceTo(p);
         if (dist >= minDist && dist <= maxDist)
         {
            res.add(p);
         }
      }

      return res;
   }

   public List<Point> inSquaredDistance(Collection<Point> points, int maxDist)
   {
      return inSquaredDistance(points, 0, maxDist);
   }


   public Point getNearestWithoutOtherMyAnt(Collection<Point> points)
   {
      int minDist = Integer.MAX_VALUE;
      Point nearestPoint = null;
      for (Point target : points)
      {
         if (equals(target) || target.getType() != PointType.MY_ANT)
         {
            int distance = distanceInCellsTo(target);
            if (distance < minDist)
            {
               minDist = distance;
               nearestPoint = target;
            }
         }
      }

      return nearestPoint;
   }

   public Point getNearestWithoutOtherMyAntX(Collection<Point> points)
   {
      int minDist = Integer.MAX_VALUE;
      Point nearestPoint = null;
      for (Point target : points)
      {
         if (equals(target) || target.getType() != PointType.MY_ANT)
         {
            int distance = findShortestPathLen(target);
            if (distance < minDist)
            {
               minDist = distance;
               nearestPoint = target;
            }
         }
      }

      return nearestPoint;
   }

   public Point plus(int dx, int dy)
   {
      int nRow = (y + dy) % Ants.getRows();
      if (nRow < 0)
      {
         nRow += Ants.getRows();
      }
      int nCol = (x + dx) % Ants.getColumns();
      if (nCol < 0)
      {
         nCol += Ants.getColumns();
      }
      return new Point(nCol, nRow);
   }


   public Point plus(Direction direction)
   {
      return plus(direction.dx, direction.dy);
   }

   public Point plus(Vector vector)
   {
      return plus(vector.dx, vector.dy);
   }

   public int hashCode()
   {
      return hashCode;
   }

   public int newHashCode()
   {
      return newHashCode;
   }

   public boolean equals(Object o)
   {
      if (o != null && o.getClass() == Point.class)
      {
         return this.x == ((Point) o).x && this.y == ((Point) o).y;
      }
      else
      {
         return false;
      }
   }

   public String toString()
   {
      return "(" + this.x + "," + this.y + ")";
   }
}
