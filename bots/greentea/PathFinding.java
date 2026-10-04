import java.util.*;

/**
 * Created by IntelliJ IDEA. User: GreenTea Date: 29.05.11 Time: 17:54 To change this template use
 * File | Settings | File Templates.
 */
public class PathFinding
{
   public static final int DEFAULT_MAX_SEARCH_DEPTH = 100;
   private static final double MAZE2_EXPLORATION_THRESHOLD = 0.7;
   private static final double MAZE1_EXPLORATION_THRESHOLD = 0.9;
   private static final int FINISH_TAKING_STATISTICS_TURN = 750;

   public static List<Direction> lastCalculatedShortestPath;

   private static double minNearToMinFactor = 1;
   private static double nearToMinFactor = 1;
   private static int calculationsCount = 0;

   public static boolean isMaze2()
   {
      return minNearToMinFactor <= MAZE2_EXPLORATION_THRESHOLD;
   }

   public static boolean isMaze1()
   {
      return minNearToMinFactor > MAZE2_EXPLORATION_THRESHOLD &&
             minNearToMinFactor <= MAZE1_EXPLORATION_THRESHOLD;

   }

   public static boolean isOpenMap()
   {
//      if (Ants.getInstance().getTurn() > 145)
//      {
//         throw new RuntimeException("" + nearToMinFactor);
//      }

      return minNearToMinFactor > MAZE1_EXPLORATION_THRESHOLD;
   }

   private static int maxX;
   private static int maxY;

   public static Point plus(Point pos, Direction direction)
   {
      int nRow = (pos.y + direction.dy) % maxY;
      if (nRow < 0)
      {
         nRow += maxY;
      }
      int nCol = (pos.x + direction.dx) % maxX;
      if (nCol < 0)
      {
         nCol += maxX;
      }
      return Point.get(nCol, nRow);
   }

   public static List<Direction> findShortestPath(PointType[][] map, Point start, Point end,
                                                  int maxSearchDepth)
   {
      maxY = map.length;
      maxX = map[0].length;

      List<Direction> res = null;
      if (start.distanceInCellsTo(end) < maxSearchDepth)
      {
         PathFinding finder = new PathFinding(map, start, end, maxSearchDepth);
         res = finder.search();
      }
      lastCalculatedShortestPath = res;

      if (Ants.getInstance().getTurn() < FINISH_TAKING_STATISTICS_TURN)
      {
         saveStatistics(start, end, res);
      }

      return res;
   }

   private static void saveStatistics(Point start, Point end, List<Direction> shortestPath)
   {
      int minPathLen = start.distanceInCellsTo(end);
      int shortestPathLen = shortestPath != null ? shortestPath.size() : Integer.MAX_VALUE;

      double factor = 0;
      if (minPathLen == 0 && shortestPathLen == 0)
      {
         factor = 1;
      }
      else
      {
         factor = minPathLen / (double)shortestPathLen;
      }

      double totalFactor = minNearToMinFactor * calculationsCount + factor;
      calculationsCount++;
      nearToMinFactor = totalFactor / calculationsCount;
      if (nearToMinFactor < minNearToMinFactor)
      {
         minNearToMinFactor = nearToMinFactor;
      }
   }

   public static void clearStatistics()
   {
      nearToMinFactor = 1;
      minNearToMinFactor = 1;
      calculationsCount = 0;
   }

   public static int findShortestPathLen(PointType[][] map, Point start, Point end,
                                         int maxSearchDepth)
   {
      int simpleDist = start.distanceInCellsTo(end);

      int res = Integer.MAX_VALUE;
      if (simpleDist < maxSearchDepth)
      {
         List<Direction> shortestPath = findShortestPath(map, start, end, maxSearchDepth);
         if (shortestPath != null)
         {
            res = shortestPath.size();
         }
      }

      return res;
   }

   public static List<Direction> findShortestPath(PointType[][] map, Point start, Point end)
   {
      return findShortestPath(map, start, end, DEFAULT_MAX_SEARCH_DEPTH);
   }

   public static int findShortestPathLen(PointType[][] map, Point start, Point end)
   {
      return findShortestPathLen(map, start, end, DEFAULT_MAX_SEARCH_DEPTH);
   }

   private static Point findObject(PointType[][] map, int object)
   {
      Point res = null;
      for (int i = 0; i < map.length; ++i)
      {
         for (int j = 0; j < map[i].length; ++j)
         {
            if (map[i][j].id == object)
            {
               res = Point.get(j, i);
               break;
            }
         }
      }
      return res;
   }

   private static void drawPath(PointType[][] map, Point start, List<Direction> path)
   {
      Point currentPos = start;
      for (Direction d : path)
      {
         currentPos = plus(currentPos, d);
         map[currentPos.y][currentPos.x] = PointType.PATH;
      }
   }

   public static void main(String[] args)
   {
      String[] mapStr = new String[]
              {". . . . . . . . . .",
               ". . % . . . . % . .",
               ". % . . . . . * % .",
               "% % % % % % % % . .",
               "% . . . . . . . . .",
               "% . . . . . . . . .",
               "% . . . . . . . . .",
               "% . . . . . . . . .",
               "% . . . . . . . . .",
               "% A . . . . . . . .",
               "% % % % % % % % % %",};

      PointType[][] map = Utils.parseMap(mapStr);
      Ants ants = new Ants(map);
      Ants.pushAnts(ants);

      Point start = findObject(map, PointType.MY_ANT.id);
      Point end = findObject(map, PointType.FOOD.id);

      List<Direction> shortestPath = null;
      Date startTime = new Date();
      int count = 10000;
      for (int i = 0; i < count; ++i)
      {
         shortestPath = findShortestPath(map, start, end);
      }
      long time = new Date().getTime() - startTime.getTime();

      if (shortestPath != null)
      {
         drawPath(map, start, shortestPath);
      }

      Utils.printMap(map);
      System.out.println("Time of " + count + " executions: " + time);
   }

   private PointType[][] map;
   private Point start;
   private Point end;
   private List<Point> whiteListPoints = new ArrayList<Point>();
   private List<Point> forbiddenPoints = new ArrayList<Point>();
//   private CellInfo[][] cellInfos;
   private CellInfo[] cellInfos;
//   private Map<Point, CellInfo> cellInfos = new HashMap<Point, CellInfo>();
   private int maxSearchDepth;

   List<Direction> shortestPath;

   int currentCellInfoNumber = 0;
   TreeSet<CellInfo> cellsPool = new TreeSet<CellInfo>();
//   CellsPool cellsPool = new CellsPool();

   int counter = 0;

   private PathFinding(PointType[][] map, Point start, Point end,
                       int maxSearchDepth)
   {
      this.map = map;
      this.start = start;
      this.end = end;
      this.maxSearchDepth = maxSearchDepth;

      for (Direction d : Direction.values)
      {
         Point near = start.plus(d);

         if (MyBot.isPointFreeForMove(near))
         {
            whiteListPoints.add(near);
         }
         else
         {
            forbiddenPoints.add(near);
         }
      }

      //cellInfos = new CellInfo[maxY][maxX];
      cellInfos = new CellInfo[maxY*maxX];
   }

   private CellInfo getNearestCellFromPool()
   {
      return cellsPool.first();
   }

   private List<Direction> search()
   {
      CellInfo c = new CellInfo(start, minDistanceToEnd(start), currentCellInfoNumber++);
//      c.pathFromStart = new ArrayList<Direction>();
      cellsPool.add(c);

      if (start.equals(end))
      {
         return new ArrayList<Direction>();
      }

      while (cellsPool.size() > 0 && shortestPath == null)
      {
         searchInternal(getNearestCellFromPool());
      }

      return shortestPath;
   }

   private CellInfo getCellInfo(Point pos)
   {
//      CellInfo cell = cellInfos[pos.y][pos.x];
      CellInfo cell = cellInfos[maxX*pos.y + pos.x];
//      CellInfo cell = cellInfos.get(pos);
      if (cell == null)
      {
         cell = new CellInfo(pos, minDistanceToEnd(pos), currentCellInfoNumber++);
//         cellInfos[pos.y][pos.x] = cell;
         cellInfos[maxX*pos.y + pos.x] = cell;
//         cellInfos.put(pos, cell);
      }

      return cell;
   }

   private double minDistanceToEnd(Point pos)
   {
      int dx = Math.abs(end.x - pos.x);
      int dy = Math.abs(end.y - pos.y);

      dx = Math.min(dx, maxX - dx);
      dy = Math.min(dy, maxY - dy);
      return Math.sqrt(dx*dx + dy*dy);
   }

   private int minDistanceToEndInCells(Point pos)
   {
      int dx = Math.abs(end.x - pos.x);
      int dy = Math.abs(end.y - pos.y);

      dx = Math.min(dx, maxX - dx);
      dy = Math.min(dy, maxY - dy);
      return dx + dy;
   }

   private void setNewPathToEnd()
   {
//      System.out.println("shortest path: " + shortestPath.size());
      shortestPath = new ArrayList<Direction>();
      Point currPos = end;
      CellInfo cell = getCellInfo(currPos);

//      try
      {
         while (cell.previousCell != null)
         {
            shortestPath.add(cell.previousCell.behind());
            currPos = currPos.plus(cell.previousCell);
            cell = getCellInfo(currPos);
         }
      }
//      catch (Throwable e)
//      {
//         System.out.println(e);
//      }
      Collections.reverse(shortestPath);
   }

   private boolean isAllowedPointType(PointType type)
   {
      return !type.isWater() && !type.isFood();
   }

   private void searchInternal(CellInfo cellInfo)
   {
      Point pos = cellInfo.pos;

      if (cellInfo.directions == null)
      {
         cellInfo.directions = Direction.values;
      }

      for (int i = cellInfo.currentDirection; i < cellInfo.directions.size(); ++i)
      {
         cellInfo.currentDirection = i + 1;
         Direction d = cellInfo.directions.get(i);
         Point next = plus(pos, d);

         int dist = start.distanceInCellsTo(next);

         PointType nextPointType = map[next.y][next.x];
         if (next.equals(end) ||
             (isAllowedPointType(nextPointType) &&
               (dist > 1 ||
               (forbiddenPoints == null || !forbiddenPoints.contains(next)) ||
               (whiteListPoints != null && whiteListPoints.contains(next)))
             ))
         {
            CellInfo nextCell = getCellInfo(next);
            if (nextCell.currentDirection != 0)
            {
               continue;
            }

            int nextPathFromStartLen = cellInfo.pathFromStartLen + 1;

            if (next.equals(end))
            {
               if (shortestPath == null)
               {
                  nextCell.pathFromStartLen = nextPathFromStartLen;
                  nextCell.previousCell = d.behind();
                  setNewPathToEnd();
                  return;
               }
               break;
            }

            if (nextCell.pathFromStartLen == 0 && !next.equals(start))
            {
               int minPathToEndLen = nextPathFromStartLen + minDistanceToEndInCells(next);
               if (minPathToEndLen > maxSearchDepth)
               {
                  continue;
               }

               nextCell.pathFromStartLen = nextPathFromStartLen;
               nextCell.previousCell = d.behind();
               cellsPool.add(nextCell);
            }
         }
      }

      if (cellInfo.isAnalyzed())
      {
         cellsPool.remove(cellInfo);
      }
   }
}
