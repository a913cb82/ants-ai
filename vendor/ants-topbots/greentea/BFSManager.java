import java.util.*;

/**
 * Created by IntelliJ IDEA. User: GreenTea Date: 10.12.11 Time: 15:59 To change this template use
 * File | Settings | File Templates.
 */
public class BFSManager
{
   private static abstract class BFSVisitor
   {
      public boolean isAllowed(Point p, Ants ants)
      {
         return !p.getType(ants).isWater();
      }

      public abstract void onPointReached(Point p, int distanceFromTarget, Ants ants);

      public void onGoOutPointReached(Point p, int distanceFromTarget, Ants ants)
      {

      }

      public boolean shouldStop(Point p, Ants ants)
      {
         return false;
      }
   }

   private static boolean getValue(boolean[][] map, Point p)
   {
      return map[p.y][p.x];
   }

   private static void setValue(boolean[][] map, Point p, boolean value)
   {
      map[p.y][p.x] = value;
   }

   private static int getValue(int[][] map, Point p)
   {
      return map[p.y][p.x];
   }

   private static void setValue(int[][] map, Point p, int value)
   {
      map[p.y][p.x] = value;
   }

   private static double getValue(double[][] map, Point p)
   {
      return map[p.y][p.x];
   }

   private static void setValue(double[][] map, Point p, double value)
   {
      map[p.y][p.x] = value;
   }

   private static final double RESEARCH_NEW_POINTS_FACTOR = 1.0;
   private static final double RESEARCH_OLD_POINTS_FACTOR = 0.05;
   private static final int RESEARCH_OLD_POINTS_MAX_TURNS_TO_START = 20;
   private static final double CLOSE_ATTACK_POINTS = 0.01;
   private static final double FAR_ATTACK_POINTS_FACTOR = 0.1;
   private static final double ATTACK_ENEMY_HILLS_FACTOR = 0.5;
   private static final int INVESTIGATION_VIEW_FACTOR = 2;

   private static Ants ants;
   private static double[][] availabilityMap;
   private static boolean[][] currentTurnVisiblePoints;
   private static List<Point> currentTurnGoOutPoints = new ArrayList<Point>();
   private static Set<Point> allTurnsGoOutPoints = new HashSet<Point>();
   private static int[][] allTurnsVisiblePoints;

   private static double[][] cumulativeInvestigationMap;
   private static Map<Point, Set<Point>> availablePointsMap = new HashMap<Point, Set<Point>>();

   public static void initializeGame(Ants ants)
   {
      BFSManager.ants = ants;
      int rows = Ants.getRows();
      int cols = Ants.getColumns();
      allTurnsGoOutPoints.clear();
      allTurnsVisiblePoints = new int[rows][cols];
      cumulativeInvestigationMap = new double[rows][cols];
      for (int i = 0; i < rows; ++i)
      {
         for (int j = 0; j < cols; ++j)
         {
            allTurnsVisiblePoints[i][j] = -1;
         }
      }
   }

   public static void signalNewWaterFound(Point p)
   {
      allTurnsGoOutPoints.remove(p);
   }

   public static double getCumulativeInvestigation(Point p)
   {
      return cumulativeInvestigationMap[p.y][p.x];
   }

   public static void decInvestigation(Point p, double value)
   {
      cumulativeInvestigationMap[p.y][p.x] -= value;
      if (cumulativeInvestigationMap[p.y][p.x] < 0)
      {
         cumulativeInvestigationMap[p.y][p.x] = 0;
      }
   }

   public static void updateInvestigationMap(Point myAnt, AntInfo info)
   {
      Set<Point> goOutPoints = new HashSet<Point>();
      Set<Point> visiblePoints = BFSManager.calcAvailablePoints(myAnt,
              INVESTIGATION_VIEW_FACTOR*INVESTIGATION_VIEW_FACTOR*ants.getViewSquaredRange(),
              goOutPoints);
      for (Point p : visiblePoints)
      {
         cumulativeInvestigationMap[p.y][p.x]++;
      }

      info.setCurrentVisiblePoints(visiblePoints);
      info.setGoOutPoints(goOutPoints);
   }

   private static void search(Collection<Point> targets, int range, boolean squaredRange,
                             BFSVisitor visitor)
   {
      boolean[][] reached = new boolean[ants.getMap().length][ants.getMap()[0].length];

      List<Point> targetsList = new ArrayList<Point>(targets);
      for (int i = 0; i < targetsList.size(); ++i)
      {
         Point p = targetsList.get(i);
         p.tag = i;
         setValue(reached, p, true);
         visitor.onPointReached(p, 1, ants);
      }

      List<Point> notExecutedPoints = new ArrayList<Point>(targets);
      for (int i = 1; (squaredRange || i <= range) && notExecutedPoints.size() > 0; ++i)
      {
         List<Point> newNotExecutedPoints = new ArrayList<Point>();

         for (int j = 0; j < notExecutedPoints.size(); j++)
         {
            Point p = notExecutedPoints.get(j);
            for (Direction d : Direction.values)
            {
               Point next = p.plus(d);
               if (!getValue(reached, next) && visitor.isAllowed(next, ants))
               {
                  next.tag = p.tag;
                  if ((!squaredRange && i == range) ||
                          (squaredRange &&
                                  targetsList.get(next.tag).squaredDistanceTo(next) > range))
                  {
                     visitor.onGoOutPointReached(next, i, ants);
                  }
                  else
                  {
                     setValue(reached, next, true);
                     visitor.onPointReached(next, i, ants);
                     newNotExecutedPoints.add(next);

                     if (visitor.shouldStop(p, ants))
                     {
                        break;
                     }
                  }
               }
            }
         }

         notExecutedPoints = newNotExecutedPoints;
      }

   }

   private static void calcCurrentTurnVisiblePoints()
   {
      final int turn = ants.getTurn();
      currentTurnVisiblePoints = new boolean[Ants.getRows()][Ants.getColumns()];
      currentTurnGoOutPoints.clear();

      search(ants.getMyAnts(), ants.getViewSquaredRange(), true, new BFSVisitor()
      {
         @Override
         public void onPointReached(Point p, int distanceFromTarget, Ants ants)
         {
            setValue(currentTurnVisiblePoints, p, true);

            int lastTurnVisited = getValue(allTurnsVisiblePoints, p);
            if (lastTurnVisited < 0)
            {
               allTurnsGoOutPoints.remove(p);
            }

            setValue(allTurnsVisiblePoints, p, turn);
         }

         @Override
         public void onGoOutPointReached(Point p, int distanceFromTarget, Ants ants)
         {
            currentTurnGoOutPoints.add(p);

            int lastTurnVisited = getValue(allTurnsVisiblePoints, p);
            if (lastTurnVisited < 0)
            {
               allTurnsGoOutPoints.add(p);
            }
         }
      });
   }

   private static void calcResearchNewPoints()
   {
      search(allTurnsGoOutPoints, 1000, false, new BFSVisitor()
      {
         @Override
         public boolean isAllowed(Point p, Ants ants)
         {
            return super.isAllowed(p, ants) && getValue(allTurnsVisiblePoints, p) > 0
                    && !p.getType(ants).isMyAnt();
         }

         @Override
         public void onPointReached(Point p, int distanceFromTarget, Ants ants)
         {
//            if (ants.getTurn() == 41 && Point.get(187, 39).equals(p))
//            {
//               System.out.println();
//            }
            double availability = RESEARCH_NEW_POINTS_FACTOR / (distanceFromTarget*distanceFromTarget);
            setValue(availabilityMap, p, getValue(availabilityMap, p) + availability);
         }
      });
   }

   private static void calcResearchOldPoints()
   {
      int turn = ants.getTurn();
      List<Point> targets = new ArrayList<Point>();
      for (int i = 0; i < allTurnsVisiblePoints.length; ++i)
      {
         for (int j = 0; j < allTurnsVisiblePoints[i].length; ++j)
         {
            if (allTurnsVisiblePoints[i][j] >= 0)
            {
               int turnsNotSeen = turn - allTurnsVisiblePoints[i][j];
               if (turnsNotSeen > RESEARCH_OLD_POINTS_MAX_TURNS_TO_START)
               {
                  targets.add(Point.get(j, i));
               }
            }
         }
      }

      search(targets, 1000, false, new BFSVisitor()
      {
         @Override
         public boolean isAllowed(Point p, Ants ants)
         {
            return super.isAllowed(p, ants) && getValue(allTurnsVisiblePoints, p) > 0;
         }

         @Override
         public void onPointReached(Point p, int distanceFromTarget, Ants ants)
         {
            double availability = RESEARCH_OLD_POINTS_FACTOR / (distanceFromTarget*distanceFromTarget);
            setValue(availabilityMap, p, getValue(availabilityMap, p) + availability);
//            setValue(patrolOldPositionsMap, p, getValue(patrolOldPositionsMap, p) + availability);
         }

         @Override
         public boolean shouldStop(Point p, Ants ants)
         {
            //return p.getType(ants).isMyAnt();
            return false;
         }
      });
   }

   private static void calcEnemyCloseAttackPoints()
   {
      search(ants.getEnemyAnts(), ants.getAttackRangeSquared(), true, new BFSVisitor()
      {
         @Override
         public boolean isAllowed(Point p, Ants ants)
         {
            return super.isAllowed(p, ants) && getValue(allTurnsVisiblePoints, p) > 0;
         }

         @Override
         public void onPointReached(Point p, int distanceFromTarget, Ants ants)
         {
         }

         @Override
         public void onGoOutPointReached(Point p, int distanceFromTarget, Ants ants)
         {
            setValue(availabilityMap, p, getValue(availabilityMap, p) + CLOSE_ATTACK_POINTS);
         }
      });
   }

   private static void calcEnemyFarAttackPoints()
   {
      search(ants.getEnemyAnts(), 1000, false, new BFSVisitor()
      {
         @Override
         public boolean isAllowed(Point p, Ants ants)
         {
            return super.isAllowed(p, ants)  && !p.getType(ants).isMyAnt()
                    && getValue(allTurnsVisiblePoints, p) > 0;
         }

         @Override
         public void onPointReached(Point p, int distanceFromTarget, Ants ants)
         {
            double availability = FAR_ATTACK_POINTS_FACTOR / (distanceFromTarget*distanceFromTarget);
            setValue(availabilityMap, p, getValue(availabilityMap, p) + availability);
         }
      });
   }

   private static void calcEnemyHillsPoints()
   {
      List<Point> enemyHills = ants.getEnemyHills();
      enemyHills.removeAll(MyBot.hostagedHills.keySet());

      search(enemyHills, 1000, false, new BFSVisitor()
      {
         @Override
         public boolean isAllowed(Point p, Ants ants)
         {
            return super.isAllowed(p, ants)  && !p.getType(ants).isMyAnt()
                    && getValue(allTurnsVisiblePoints, p) > 0;
         }

         @Override
         public void onPointReached(Point p, int distanceFromTarget, Ants ants)
         {
            double availability = ATTACK_ENEMY_HILLS_FACTOR / (distanceFromTarget*distanceFromTarget);
            setValue(availabilityMap, p, getValue(availabilityMap, p) + availability);
         }
      });

      for (Point h : enemyHills)
      {
         double availability = ATTACK_ENEMY_HILLS_FACTOR * 2;
         setValue(availabilityMap, h, getValue(availabilityMap, h) + availability);
      }
   }

   public static Set<Point> getAvailablePoints(Point center, int squaredRange)
   {
      Set<Point> res = availablePointsMap.get(center);
      if (res == null)
      {
         res = calcAvailablePoints(center, squaredRange, null);
      }

      return res;
   }

   public static void clearAvailablePointsMap()
   {
      availablePointsMap.clear();
   }

   public static Set<Point> calcAvailablePoints(Point center, int squaredRange,
                                                /*OUT*/ final Set<Point> goOutPoints)
   {
      int range = (int)Math.sqrt(squaredRange) + 1;

      final Set<Point> result = new HashSet<Point>();
      search(Arrays.asList(center), range, false, new BFSVisitor()
      {
         @Override
         public void onPointReached(Point p, int distanceFromTarget, Ants ants)
         {
            result.add(p);
         }

         @Override
         public void onGoOutPointReached(Point p, int distanceFromTarget, Ants ants)
         {
            if (goOutPoints != null)
            {
               goOutPoints.add(p);
            }
         }
      });
      availablePointsMap.put(center, result);
      return result;
   }

   public static void buildVisiblePoints()
   {
      calcCurrentTurnVisiblePoints();
   }

   public static void buildAvailabilityMap()
   {
      int rows = Ants.getRows();
      int cols = Ants.getColumns();
      availabilityMap = new double[rows][cols];

      calcResearchNewPoints();
      calcResearchOldPoints();
      calcEnemyCloseAttackPoints();
      calcEnemyFarAttackPoints();
      calcEnemyHillsPoints();
   }

   private static Point getPointWithBestScores(Point ant, final double[][] scoresMap)
   {
      final Point[] bestTarget = new Point[1];
      final double[] bestScores = new double[1];

      search(Arrays.asList(ant), ants.getViewSquaredRange(), true, new BFSVisitor()
      {
         @Override
         public boolean isAllowed(Point p, Ants ants)
         {
            return super.isAllowed(p, ants) && !p.getType(ants).isMyAnt() &&
                    getValue(allTurnsVisiblePoints, p) > 0;
         }

         @Override
         public void onPointReached(Point p, int distanceFromTarget, Ants ants)
         {
            double availability = getValue(scoresMap, p);
            if (availability > bestScores[0])
            {
               bestScores[0] = availability;
               bestTarget[0] = p;
            }
         }
      });

      return bestTarget[0];
   }

   public static Point getPointWithBestAvailability(Point ant)
   {
      return getPointWithBestScores(ant, availabilityMap);
   }
}
