
import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.util.*;

public class MyBot
{
   public static final double CHANCE_TO_WIN1 = 50;
   public static final double CHANCE_TO_WIN2 = 120;
   public static final double CHANCE_TO_WIN3 = 180;
   public static final double CHANCE_TO_WIN4 = 240;
   public static final double CHANCE_TO_WIN5 = 300;
   private static final int MY_HILL_DANGER_RANGE = 15;

   private static final int DEFENDERS_AGGRESSION_RANGE_FOR_MAZE = 15;
   private static final int DEFENDERS_AGGRESSION_RANGE_FOR_OPEN_MAP = 15;
   public static final int DEFENDERS_WAVES_COUNT = 20;

   private static final double ATTACK_HILL_ANTS_FACTOR = 1.5;
   private static final int MIN_ANTS_TO_ATTACK_HILL = 2;
   private static final int ATTACK_HILL_DIST_FOR_MAZE = 25;
   private static final int ATTACK_HILL_DIST_FOR_OPEN_MAP = 25;
   private static final int MIN_ANTS_FOR_HILL_FOR_START_DEFENDING = 10;
   private static final int HOSTAGE_HILL_MAX_TURNS = 200;
   private static final int HOSTAGE_HILL_STOP_BEFORE_END = 50;

   private static class TakeFoodOrderEstimation
   {
      public Integer distanceToFood;
      public Set<Point> antsWhichMakeMoveNotDanger;

      private TakeFoodOrderEstimation(int distanceToFood, Set<Point> antsWhichMakeMoveNotDanger)
      {
         this.distanceToFood = distanceToFood;
         this.antsWhichMakeMoveNotDanger = antsWhichMakeMoveNotDanger;
      }
   }

   private static class HostageHillInfo
   {
      public final int capturingTurn;

      public HostageHillInfo(int capturingTurn)
      {
         this.capturingTurn = capturingTurn;
      }
   }

   public static Ants ants;

   public static Set<Point> destinations = new HashSet<Point>();
   public static Set<Point> notMovedAnts = new HashSet<Point>();
   public static Set<Point> movedAnts = new HashSet<Point>();
   public static Set<Point> newFreePoints = new HashSet<Point>();

   private int maxGoByVectorRange;
   private int maxTakeTargetsRange;
   private double chanceToWin;
   private int attackRangeSquared;
   private int attackRange;
   private int viewRangeSquared;
   private int viewRange;
   private int countOfStrongOpponents;

   private boolean pendingMovesMode;
   private Map<Order, TakeFoodOrderEstimation> pendingMovesForTakingFood = new HashMap<Order, TakeFoodOrderEstimation>();

   private DangerMoveValidator dangerMoveValidator;
   private Map<Point, MoveTask> explorationTaskMap = new HashMap<Point, MoveTask>();

   private boolean isMultihillMap = false;
   public static Map<Point, HostageHillInfo> hostagedHills = new HashMap<Point, HostageHillInfo>();

   public static void main(String[] args)
   {
      if (args.length > 0)
      {
         try
         {
            Ants.run(new MyBot(), new FileInputStream(args[0]));
         }
         catch (FileNotFoundException e)
         {
            throw new RuntimeException(e);
         }
      }
      else
      {
         Ants.run(new MyBot());
      }
   }

   // Utility ######################################################################################
   public static boolean isPointFreeForMove(Point point)
   {
       return !point.getType(ants).isWater() && !point.getType(ants).isFood() &&
         (!destinations.contains(point) &&
         (!point.getType(ants).isMyAnt() || newFreePoints.contains(point)));
   }

   private Set<Point> intersectionWithAvailablePoints(Point target, int squaredRange,
                                                      Collection<Point> otherPoints)
   {
      Set<Point> availablePoints = BFSManager.getAvailablePoints(target, squaredRange);
      return Utils.intersection(availablePoints, otherPoints);
   }

//   public Set<Point> getMyAntsSet()
//   {
//
//   }

   // Moves ########################################################################################
   private void moveUnsafe(Point ant, Direction direction, Point target)
   {
      if (direction == null)
      {
         nullMove(ant);
         return;
      }

      Point newPos = ant.plus(direction);
      Order order = new Order(ant, direction, target);
      order.setPending(pendingMovesMode);

      ants.issueOrder(order);
      destinations.add(newPos);
      movedAnts.add(ant);
      notMovedAnts.remove(ant);
      if (!destinations.contains(ant))
      {
         newFreePoints.add(ant);
      }
      newFreePoints.remove(newPos);
   }

   private void moveUnsafe(Point ant, Direction direction)
   {
      moveUnsafe(ant, direction, null);
   }

   private void moveUnsafe(Map<Point, Direction> moves)
   {
      for (Map.Entry<Point, Direction> move : moves.entrySet())
      {
         moveUnsafe(move.getKey(), move.getValue());
      }
   }

   private void revertMove(Order order)
   {
      Point ant = order.getPoint();
      Direction direction = order.getDirection();

      if (direction != null)
      {
         Point newPos = ant.plus(direction);
         destinations.remove(newPos);
         movedAnts.remove(ant);
         notMovedAnts.add(ant);
         newFreePoints.remove(ant);
      }
      else
      {
         movedAnts.remove(ant);
         notMovedAnts.add(ant);
         destinations.remove(ant);
      }
   }

   private boolean move(Point ant, List<Direction> directions, IMoveValidator moveValidator,
                        Point target)
   {
      boolean issued = false;
      for (Direction direction : directions)
      {
         Point destination = ant.plus(direction);
         if ((destination.getType().isUnoccupied() && !destinations.contains(destination)) ||
                 newFreePoints.contains(destination))
         {
            if (moveValidator != null && !moveValidator.isValid(ant, direction))
            {
               break;
            }

            moveUnsafe(ant, direction, target);
            issued = true;
            break;
         }
      }

      return issued;
   }

   private boolean move(Point ant, List<Direction> directions, IMoveValidator moveValidator)
   {
      return move(ant, directions, moveValidator, null);
   }

   private void nullMove(Point ant)
   {
      movedAnts.add(ant);
      notMovedAnts.remove(ant);
      destinations.add(ant);
      ants.issueOrder(new Order(ant, null, null));
   }

   // Go To ########################################################################################

   private boolean goToPoint(Point p1, Point p2, IMoveValidator moveValidator,
                             Integer maxRangeSquared)
   {
      if (maxRangeSquared != null)
      {
         Set<Point> available = BFSManager.getAvailablePoints(p2,
                 maxRangeSquared);
         if (!available.contains(p1))
         {
            return false;
         }
      }

      List<Direction> shortestPath = maxRangeSquared == null ?
              p1.findShortestPath(p2) :
              p1.findShortestPath(p2, (int)Math.sqrt(maxRangeSquared) + 1);
      boolean success = false;
      if (shortestPath != null)
      {
         if (shortestPath.size() > 0)
         {
            success = move(p1, Collections.singletonList(shortestPath.get(0)), moveValidator, p2);
         }
         else
         {
            nullMove(p1);
            success = true;
         }
      }

      return success;
   }


   private boolean goToPoint(Point p1, Point p2, IMoveValidator moveValidator)
   {
      return goToPoint(p1, p2, moveValidator, null);
   }

   public boolean goByVector(Point ant, Vector vector, IMoveValidator moveValidator,
                             Direction rotateDirectionIfCantMove)
   {
      boolean success = false;
      for (int len = maxGoByVectorRange; len >= 3; --len)
      {
         Point newPos = ant.plus(vector.withLength(len));
         if (newPos.getType() != PointType.WATER)
         {
            success = goToPoint(ant, newPos, moveValidator);
            break;
         }
      }

      if (rotateDirectionIfCantMove != null && !success)
      {
         Vector nextVector = rotateDirectionIfCantMove.equals(Direction.LEFT) ?
                 vector.rotate(90) : vector.rotate(180);
         Direction nextDirection = rotateDirectionIfCantMove.equals(Direction.LEFT) ?
                 Direction.RIGHT : null;
         success = goByVector(ant, nextVector, moveValidator, nextDirection);
      }

      return success;
   }

   // Taking targets ###############################################################################

   private TakeTargetResult calcTakeTargetResult(Point target, int maxRange)
   {
      List<Point> allAnts = new ArrayList<Point>(notMovedAnts);
      allAnts.addAll(ants.getEnemyAnts());

      List<Point> nearest = target.getNearest(
              Utils.intersection(BFSManager.getAvailablePoints(target, maxRange*maxRange),
                      allAnts), 4, false);
      if (nearest.size() == 0)
      {
         return TakeTargetResult.NONE;
      }

      long minDistFromMy = Integer.MAX_VALUE;
      long minDistFromEnemy = Integer.MAX_VALUE;

      List<Point> ants1 = new ArrayList<Point>();
      List<Point> ants2 = new ArrayList<Point>();
      Map<Point, List<Direction>> shortestPaths = new HashMap<Point, List<Direction>>();
      Map<Point, PointType> pointTypes = new HashMap<Point, PointType>();

      for (Point ant : nearest)
      {
         PointType type = ant.getType();
         if (type.isMyAnt())
         {
            List<Direction> sp = ant.findShortestPath(target);
            if (sp != null)
            {
               if (sp.size() == 1)
               {
                  return TakeTargetResult.MY;
               }
               ants1.add(ant);
               shortestPaths.put(ant, Utils.withoutLast(sp));
               pointTypes.put(ant, ant.getType());
               int dist = sp.size();
               if (dist < minDistFromMy)
               {
                  minDistFromMy = dist;
               }
            }

         }
         else
         {
            List<Direction> sp = ant.findShortestPath(target);
            if (sp != null)
            {
               if (sp.size() == 1)
               {
                  return TakeTargetResult.ENEMY;
               }
               ants2.add(ant);
               shortestPaths.put(ant, Utils.withoutLast(sp));
               pointTypes.put(ant, ant.getType());
               int dist = sp.size();
               if (dist < minDistFromEnemy)
               {
                  minDistFromEnemy = dist;
               }
            }
         }
      }

      int startAnts1Size = ants1.size();
      int startAnts2Size = ants2.size();

      if (minDistFromMy + attackRange < minDistFromEnemy)
      {
         return TakeTargetResult.MY;
      }
      if (minDistFromEnemy + attackRange < minDistFromMy)
      {
         return TakeTargetResult.ENEMY;
      }

      for (int step = 0; true; ++step)
      {
         int tag = 0;

         Map<Point, List<Direction>> newShortestPaths = new HashMap<Point, List<Direction>>();
         Map<Point, PointType> newPointTypes = new HashMap<Point, PointType>();
         List<Point> ants1NearFood = new ArrayList<Point>();
         PointType[] types = new PointType[ants1.size() + ants2.size()];
         for (int i = 0; i < ants1.size(); ++i)
         {
            Point ant = ants1.get(i);
            List<Direction> sp = shortestPaths.get(ant);
            Direction d = sp.get(step);
            Point newPos = ant.plus(d);
            newPos.tag = tag++;

            types[newPos.tag] = pointTypes.get(ant);
            newPointTypes.put(newPos, types[newPos.tag]);

            newShortestPaths.put(newPos, sp);
            ants1.set(i, newPos);

            if (newPos.distanceInCellsTo(target) == 1)
            {
               ants1NearFood.add(newPos);
            }
         }

         List<Point> ants2NearFood = new ArrayList<Point>();
         for (int i = 0; i < ants2.size(); ++i)
         {
            Point ant = ants2.get(i);
            List<Direction> sp = shortestPaths.get(ant);
            Direction d = sp.get(step);
            Point newPos = ant.plus(d);
            newPos.tag = tag++;

            types[newPos.tag] = pointTypes.get(ant);
            newPointTypes.put(newPos, types[newPos.tag]);

            newShortestPaths.put(newPos, sp);
            ants2.set(i, newPos);

            if (newPos.distanceInCellsTo(target) == 1)
            {
               ants2NearFood.add(newPos);
            }
         }
         shortestPaths = newShortestPaths;
         pointTypes = newPointTypes;

         List<Point> ants1Alive = new ArrayList<Point>();
         List<Point> ants2Alive = new ArrayList<Point>();
         BattleCalculator.fight(ants1, ants2, types, ants1Alive, ants2Alive);

         if (Utils.containsAny(ants1Alive, ants1NearFood))
         {
            if (ants1Alive.size() == startAnts1Size)
            {
               return TakeTargetResult.MY;
            }
            else
            {
               return TakeTargetResult.NONE;
            }
         }
         if (Utils.containsAny(ants2Alive, ants2NearFood))
         {
            if (countOfStrongOpponents < 2 && ants2Alive.size() < startAnts2Size)
            {
               return TakeTargetResult.NONE;
            }
            return TakeTargetResult.ENEMY;
         }

         if (ants1Alive.size() == 0 && ants2Alive.size() > 0)
         {
            return TakeTargetResult.ENEMY;
         }
         else if (ants2Alive.size() == 0)
         {
            if (ants1Alive.size() == startAnts1Size)
            {
               return TakeTargetResult.MY;
            }
            else
            {
               return TakeTargetResult.NONE;
            }
         }

         ants1.clear();
         ants1.addAll(ants1Alive);

         ants2.clear();
         ants2.addAll(ants2Alive);
      }
   }

   private boolean isPoint2FarToMyAnt(Point ant, Point next1, Point next2)
   {
      Set<Point> otherAnts = new HashSet<Point>(ants.getMyAnts());
      otherAnts.remove(ant);
      Point nearestAnt1 = next1.getNearestHalfX(otherAnts, false);
      Point nearestAnt2 = next2.getNearestHalfX(otherAnts, false);
      int distToAnt1 = 1;
      int distToAnt2 = 1;
      if (nearestAnt1 != null && nearestAnt2 != null)
      {
         distToAnt1 = next1.findShortestPathLen(nearestAnt1);
         distToAnt2 = next2.findShortestPathLen(nearestAnt2);
      }

      return distToAnt2 > distToAnt1;
   }

   private void tryTakeFoodWise(Point ant, Point food, int maxRadius)
   {
      List<Point> enemiesInRange =
              ant.filterNear2ToSquaredRange(ants.getEnemyAnts(), ants.getAttackRangeSquared());
      if (enemiesInRange.size() > 0)
      {
         Map<Point, Direction> bestMoves =
                 BattleCalculator.findBestMoves(new ArrayList<Point>(notMovedAnts), enemiesInRange);
         if (bestMoves.size() > 0)
         {
            Direction d = bestMoves.get(ant);
            if (d != null && food.distanceInCellsTo(ant.plus(d)) == 1)
            {
               moveUnsafe(ant, d);
               return;
            }
         }
      }

      List<Direction> directions = new ArrayList<Direction>();
      for (Direction d : Direction.values)
      {
         if (food.distanceInCellsTo(ant.plus(d)) == 1)
         {
            directions.add(d);
         }
      }

      Point next1 = ant.plus(directions.get(0));
      Point next2 = ant.plus(directions.get(1));

      Set<Point> otherFood = new HashSet<Point>(Utils.intersection(BFSManager.getAvailablePoints(
              food, maxRadius*maxRadius), ants.getFood()));
      otherFood.remove(food);

      Point nearestFood0 = food.getNearestHalfX(otherFood, false);
      Point nearestFood1 = next1.getNearestHalfX(otherFood, false);
      if (nearestFood1 != null)
      {
         Point nearestMyAnt = nearestFood1.getNearestHalfX(ants.getMyAnts(), false);
         if (!ant.equals(nearestMyAnt))
         {
            nearestFood1 = null;
         }
      }

      Point nearestFood2 = next2.getNearestHalfX(otherFood, false);
      if (nearestFood2 != null)
      {
         Point nearestMyAnt = nearestFood2.getNearestHalfX(ants.getMyAnts(), false);
         if (!ant.equals(nearestMyAnt))
         {
            nearestFood1 = null;
         }
      }

      if (nearestFood0 != null && nearestFood1 != null && nearestFood2 != null)
      {
         int dist0 = food.findShortestPathLen(nearestFood0);
         int dist1 = next1.findShortestPathLen(nearestFood1);
         int dist2 = next2.findShortestPathLen(nearestFood2);

         int nearToFood0 = 0;
         int votesFor2 = 0;
         if (nearestFood0.equals(nearestFood1) && dist0 < dist1)
         {
            nearToFood0++;
            votesFor2 += 2;
         }
         if (nearestFood0.equals(nearestFood2) && dist0 < dist2)
         {
            nearToFood0++;
            votesFor2 -= 2;
         }
         if (nearToFood0 < 2)
         {
            if (dist2 < dist1)
            {
               votesFor2++;
            }
            if (dist2 > dist1)
            {
               votesFor2--;
            }
         }

         if (votesFor2 > 0 || (votesFor2 == 0 && isPoint2FarToMyAnt(ant, next1, next2)))
         {
            Collections.reverse(directions);
         }
      }
      else if (isPoint2FarToMyAnt(ant, next1, next2))
      {
         Collections.reverse(directions);
      }

      move(ant, directions, dangerMoveValidator);
   }

   private int calcTakeTargetsBenefit(Point currentAnt, List<Point> possibleTargets,
                                      int[] permutation)
   {
      int currentBenefit = 0;
      int totalDist = 0;
      int totalBenefit = 0;

      Point currentPoint = currentAnt;
      for (int i = 0; i < permutation.length; ++i)
      {
         Point next = possibleTargets.get(permutation[i]);
         int dist = currentPoint.distanceInCellsTo(next);
         totalDist += dist;
         totalBenefit += currentBenefit * dist;
         currentBenefit++;
         currentPoint = next;
      }

      totalBenefit += (100 - totalDist) * currentBenefit;
      return totalBenefit;
   }

   private Point selectBestTarget(final Point currentAnt, final List<Point> possibleTargets)
   {
      final Point[] bestTarget = new Point[1];
      if (possibleTargets.size() <= 5)
      {
         final int[] maxBenefit = new int[1];
         Utils.generatePermutations(possibleTargets.size(), new Utils.IPermutationFoundCallback()
         {
            public void permutationFound(int[] permutation)
            {
               int benefit = calcTakeTargetsBenefit(currentAnt, possibleTargets, permutation);
               if (benefit > maxBenefit[0])
               {
                  maxBenefit[0] = benefit;
                  bestTarget[0] = possibleTargets.get(permutation[0]);
               }
            }
         });
      }
      else
      {
         bestTarget[0] = currentAnt.getNearestX(possibleTargets, false);
      }

      return bestTarget[0];
   }

   private void takeTargets(Set<Point> antsSet,
                            List<Point> targetsList, int takeRadius, int maxRadius,
                            List<Point> mootPoints)
   {
      final Map<Point, Set<Point>> antsToTargets = new HashMap<Point, Set<Point>>();

      Set<Point> takenPoints = new HashSet<Point>();
      A: for (int i = 0; i < targetsList.size(); ++i)
      {
         Point target = targetsList.get(i);
         if (takenPoints.contains(target))
         {
            continue;
         }

         List<Point> nearestAnts = new ArrayList<Point>();
         List<Point> myAntsInRange = target.inRange(antsSet, maxRadius);

         if (myAntsInRange.size() > 0)
         {
            nearestAnts = target.getMultipleNearestHalfX(Utils.intersection(myAntsInRange,
                    BFSManager.getAvailablePoints(target, maxRadius*maxRadius)), false);
         }

         if (nearestAnts.size() > 0 && mootPoints != null)
         {
            TakeTargetResult takeFoodResult = calcTakeTargetResult(target, maxRadius);
            if (takeFoodResult.equals(TakeTargetResult.ENEMY))
            {
               ants.getFood().remove(target);
               continue;
            }
            if (takeFoodResult.equals(TakeTargetResult.NONE))
            {
               mootPoints.add(target);
            }
         }

         for (Point nearestAnt : nearestAnts)
         {
            if (nearestAnt != null)
            {
               int dist = target.findShortestPathLen(nearestAnt, maxRadius);

               if (dist <= takeRadius)
               {
                  antsSet.remove(nearestAnt);
                  if (antsToTargets.containsKey(nearestAnt))
                  {
                     antsToTargets.remove(nearestAnt);
                  }

                  nullMove(nearestAnt);
                  if (pendingMovesMode)
                  {
                     Order o = ants.popLastPendingOrder();
                     TakeFoodOrderEstimation e = new TakeFoodOrderEstimation(0, null);
                     pendingMovesForTakingFood.put(o, e);
                  }
                  takenPoints.addAll(nearestAnt.inRange(targetsList, takeRadius));

                  continue A;
               }
               else if (dist < maxRadius)
               {
                  Set<Point> targets;
                  if (antsToTargets.containsKey(nearestAnt))
                  {
                     targets = antsToTargets.get(nearestAnt);
                  }
                  else
                  {
                     targets = new HashSet<Point>();
                     antsToTargets.put(nearestAnt, targets);
                  }

                  targets.add(target);
               }
            }
         }
      }

      antsSet.removeAll(antsToTargets.keySet());
      Set<Point> takenTargets = new HashSet<Point>();

//      final Map<Point, Integer> antsToSumDistToTargets = new HashMap<Point, Integer>();
//      for (Map.Entry<Point, Set<Point>> antToTargets : antsToTargets.entrySet())
//      {
//         Point ant = antToTargets.getKey();
//         Set<Point> targets = antToTargets.getValue();
//         antsToSumDistToTargets.put(ant, ant.sumDistance(targets));
//      }

      List<Point> sortedAnts = new ArrayList<Point>(antsToTargets.keySet());
      Collections.sort(sortedAnts, new Comparator<Point>() {
         public int compare(Point p1, Point p2)
         {
            Integer targets1 = antsToTargets.get(p1).size();
            Integer targets2 = antsToTargets.get(p2).size();

            Integer res = targets1.compareTo(targets2);
            return res;
//            return res != 0 ? res :
//                    -antsToSumDistToTargets.get(p1).compareTo(antsToSumDistToTargets.get(p2));
         }
      });

      for (Point ant : sortedAnts)
      {
         if (movedAnts.contains(ant))
         {
            continue;
         }

         Set<Point> targets = antsToTargets.get(ant);
         targets.removeAll(takenTargets);

         Point selectedTarget = null;
         if (targets.size() > 1)
         {
            selectedTarget = selectBestTarget(ant, new ArrayList<Point>(targets));
         }
         else if (targets.size() == 1)
         {
            selectedTarget = targets.iterator().next();
         }


         if (selectedTarget != null)
         {
            takenTargets.add(selectedTarget);
            int shortestPathLen = ant.findShortestPathLen(selectedTarget, maxRadius);
            if (takeRadius == 1 && ant.dX(selectedTarget) == 1 && ant.dY(selectedTarget) == 1 &&
                    shortestPathLen == 2)
            {
               tryTakeFoodWise(ant, selectedTarget, maxRadius);
            }
            else
            {
               goToPoint(ant, selectedTarget, dangerMoveValidator);
               if (pendingMovesMode)
               {
                  Order o = ants.popLastPendingOrder();
                  if (o != null)
                  {
                     TakeFoodOrderEstimation e = new TakeFoodOrderEstimation(shortestPathLen,
                             BattleCalculator.popAntsWhichMakeMoveNotDanger());
                     pendingMovesForTakingFood.put(o, e);
                  }
               }
            }

            if (pendingMovesMode)
            {
               Order o = ants.popLastPendingOrder();
               if (o != null)
               {
                  TakeFoodOrderEstimation e = new TakeFoodOrderEstimation(shortestPathLen,
                          BattleCalculator.popAntsWhichMakeMoveNotDanger());
                  pendingMovesForTakingFood.put(o, e);
               }
            }
         }
      }
   }

   private Set<Point> analyzePendingOrdersAndTakeFood()
   {
      List<Order> pendingOrders = ants.getPendingOrders();
      Collections.sort(pendingOrders, new Comparator<Order>()
      {
         public int compare(Order o1, Order o2)
         {
            TakeFoodOrderEstimation e1 = pendingMovesForTakingFood.get(o1);
            TakeFoodOrderEstimation e2 = pendingMovesForTakingFood.get(o2);
            Integer myAnts1 = e1.antsWhichMakeMoveNotDanger == null ||
                    e1.antsWhichMakeMoveNotDanger.size() ==  0 ? 0 : 1;
            Integer myAnts2 = e2.antsWhichMakeMoveNotDanger == null ||
                    e2.antsWhichMakeMoveNotDanger.size() ==  0 ? 0 : 1;

            int res = myAnts1.compareTo(myAnts2);
            if (res == 0)
            {
               res = e1.distanceToFood.compareTo(e2.distanceToFood);
            }

            return res;
         }
      });

      List<Point> movedAnts = new ArrayList<Point>();
      List<Order> goodPendingOrder = new ArrayList<Order>();
      List<Order> badPendingOrder = new ArrayList<Order>();
      Set<Point> antsUsedForMakeMoveNotDanger = new HashSet<Point>();
      for (Order o : pendingOrders)
      {
         TakeFoodOrderEstimation e = pendingMovesForTakingFood.get(o);
         if (e.antsWhichMakeMoveNotDanger == null || e.antsWhichMakeMoveNotDanger.size() == 0)
         {
            movedAnts.add(o.getPoint());
            goodPendingOrder.add(o);
         }
         else if (!antsUsedForMakeMoveNotDanger.contains(o.getPoint()) &&
                 !e.antsWhichMakeMoveNotDanger.removeAll(movedAnts))
         {
            movedAnts.add(o.getPoint());
            goodPendingOrder.add(o);
            antsUsedForMakeMoveNotDanger.addAll(e.antsWhichMakeMoveNotDanger);
         }
         else
         {
            badPendingOrder.add(o);
         }
      }

      pendingOrders.clear();
      pendingOrders.addAll(goodPendingOrder);

      for (Order o : badPendingOrder)
      {
         revertMove(o);
      }

      return antsUsedForMakeMoveNotDanger;
   }

   // Attack #######################################################################################

   private void attackUsingBattleCalculator()
   {
      moveUnsafe(BattleCalculator.findBestMoves(
              new ArrayList<Point>(notMovedAnts), ants.getEnemyAnts()));
   }

   @SuppressWarnings(value = "unchecked")
   private double calcPower(Point ant, Collection<Point> enemyAnts, List<Point> enemies1)
   {
      List<Point> enemies2 = ant.filterNear2ToSquaredRange(enemyAnts, attackRangeSquared);

      Set<Point> enemies1Set = new HashSet<Point>();
      enemies1Set.addAll(ant.filterNearToSquaredRangeFromPoints(enemies2, attackRangeSquared));
      enemies1Set.addAll(ant.filterNearToSquaredRangeFromAnt(enemies2, attackRangeSquared));
      enemies1.addAll(enemies1Set);

      int enemies2Count = enemies2.size() - enemies1.size();
      int enemies1Count = enemies1.size();

      return  1 / (0.25 * enemies2Count + enemies1Count);
   }

   private List<Point> calcAntsGoodForAttack(Collection<Point> candidates, double[] powerTable,
                                             List<List<Point>> enemies1List, boolean rage)
   {
      List<Point> antsGoodForAttack = new ArrayList<Point>();

      A:
      for (Point ant : candidates)
      {
         double power = powerTable[ant.tag];

         List<Point> enemies1 = enemies1List.get(ant.tag);
         for (Point enemy : enemies1)
         {
            if ((rage && power < 0.5*powerTable[enemy.tag]) ||
                (!rage && power <= powerTable[enemy.tag]))
            {
               continue A;
            }
         }

         if (enemies1.size() > 0)
         {
            antsGoodForAttack.add(ant);
         }
      }

      return antsGoodForAttack;
   }

   private Point findBestTarget(Point attacker, double[] powerTable, List<List<Point>> enemies1List)
   {
      List<Point> enemies1 = enemies1List.get(attacker.tag);
      double minPower = Double.MAX_VALUE;
      Point bestTarget = null;
      for (Point enemy : enemies1)
      {
         double power = powerTable[enemy.tag];
         if (minPower > power)
         {
            bestTarget = enemy;
            minPower = power;
         }
      }

      return bestTarget;
   }

   private boolean powerOfAntIsMax(Point ant, Collection<Point> otherAnts, double[] powerTable)
   {
      boolean res = true;
      double powerOfAnt = powerTable[ant.tag];

      for (Point otherAnt : otherAnts)
      {
         double powerOfOther = powerTable[otherAnt.tag];
         if (powerOfAnt <= powerOfOther)
         {
            res = false;
            break;
         }
      }

      return res;
   }

   private Direction findClosestSquareDirection(Point attacker, List<Point> targets,
                                                Collection<Point> enemyAttackersAfterMove)
   {
      Direction bestDirection = null;
      int minDistOfBestDirection = attacker.sumSquaredDistance(targets);
      for (Direction d : Direction.values)
      {
         Point newPos = attacker.plus(d);
         if (isPointFreeForMove(newPos) &&
                 newPos.inSquaredDistance(enemyAttackersAfterMove, attackRangeSquared).size() == 0)
         {
            int distForDirection = newPos.sumSquaredDistance(targets);
            if (distForDirection < minDistOfBestDirection)
            {
               bestDirection = d;
               minDistOfBestDirection = distForDirection;
            }
         }
      }

      return bestDirection;
   }

   private Direction findClosestSquareDirection(Point attacker, Point target)
   {
      return findClosestSquareDirection(attacker, Arrays.asList(target), new ArrayList<Point>());
   }

   private Direction findMostFarSquareDirection(Point defender, Collection<Point> attackers,
                                                Map<Point, MoveRequest> moveRequests)
   {
      Direction bestDirection = null;
      int maxDistOfBestDirection = 0;
      for (Point attacker : attackers)
      {
         maxDistOfBestDirection += defender.squaredDistanceTo(attacker);
      }
      int startMinDist = defender.getMinDist(attackers);

      boolean bestPointHasMyAnt = false;
      for (Direction d : Direction.values)
      {
         Point newPos = defender.plus(d);
         if (!newPos.getType(ants).isWater() && !newPos.getType(ants).isFood() &&
                 !destinations.contains(newPos) && !moveRequests.containsKey(newPos))
         {
            int distForDirection = 0;
            for (Point attacker : attackers)
            {
               distForDirection += newPos.squaredDistanceTo(attacker);
            }

            boolean hasMyAnt = notMovedAnts.contains(newPos);
            if (distForDirection > maxDistOfBestDirection ||
                    (bestPointHasMyAnt && !hasMyAnt && newPos.getMinDist(attackers) > startMinDist))
            {
               bestDirection = d;
               maxDistOfBestDirection = distForDirection;
               bestPointHasMyAnt = hasMyAnt;
            }
         }
      }

      return bestDirection;
   }

   private boolean isSafeToMoveWithFarAnt(Point newPos, List<Point> enemies2)
   {
      boolean res = true;
      List<Point> enemies1 = newPos.filterNearToSquaredRangeFromPoints(enemies2,
              attackRangeSquared);
      if (enemies1.size() > 1)
      {
         res = false;
         for (Point enemy : enemies1)
         {
            Set<Point> near1MyAnts = new HashSet<Point>();
            near1MyAnts.addAll(enemy.filterNearToSquaredRangeFromAnt(destinations,
                    attackRangeSquared));
            near1MyAnts.addAll(enemy.filterNearToSquaredRangeFromAnt(notMovedAnts,
                    attackRangeSquared));

            if (near1MyAnts.size() > 0)
            {
               res = true;
               break;
            }
         }
      }

      return res;
   }

   private void recalcPowerTableForEnemyAnts(double[] powerTable, List<Point> enemyAnts,
                                             Set<Point> newPositionsOfMyAnts)
   {
      for (int i = 0; i < enemyAnts.size(); ++i)
      {
         Point ant = enemyAnts.get(i);
         List<Point> enemies1 = new ArrayList<Point>();
         powerTable[ant.tag] = calcPower(ant, newPositionsOfMyAnts, enemies1);
      }
   }

   private void attackMedium2(List<BattleCalculator.LocalBattleInfo> localBattleInfos)
   {
      Set<Point> moveRequestAnts = new HashSet<Point>();
      Map<Point, MoveRequest> moveRequests = new HashMap<Point, MoveRequest>();
      boolean rage = BattleCalculator.AttackMode.Exchange.equals(BattleCalculator.globalAttackMode);
      for (BattleCalculator.LocalBattleInfo localBattleInfo : localBattleInfos)
      {
         localBattleInfo.myAnts.removeAll(movedAnts);
         if (localBattleInfo.myAnts.size() == 0)
         {
            continue;
         }

         List<Point> myAnts = localBattleInfo.myAnts;
         List<Point> enemyAnts = localBattleInfo.enemyAnts;
         Set<Point> newPositionsOfMyAnts = new HashSet<Point>(myAnts);

         double[] powerTable = new double[myAnts.size() + enemyAnts.size()];
         List<List<Point>> enemies1List = new ArrayList<List<Point>>();
         for (int i = 0; i < myAnts.size(); ++i)
         {
            Point ant = myAnts.get(i);
            ant.tag = i;
            List<Point> enemies1 = new ArrayList<Point>();
            powerTable[i] = calcPower(ant, enemyAnts, enemies1);
            enemies1List.add(enemies1);
         }

         for (int i = 0; i < enemyAnts.size(); ++i)
         {
            Point ant = enemyAnts.get(i);
            int j = myAnts.size() + i;
            ant.tag = j;
            List<Point> enemies1 = new ArrayList<Point>();
            powerTable[j] = calcPower(ant, myAnts, enemies1);
            enemies1List.add(enemies1);
         }

         List<List<Point>> targetsToAttackers = new ArrayList<List<Point>>();
         Point[] targets = new Point[myAnts.size() + enemyAnts.size()];
         for (int i = 0; i < myAnts.size() + enemyAnts.size(); ++i)
         {
            targetsToAttackers.add(new ArrayList<Point>());
         }

         // Attack
         List<Point> myAntsGoodForAttack =
                 calcAntsGoodForAttack(myAnts, powerTable, enemies1List, rage);
         List<Point> enemyAntsGoodForAttack =
                 calcAntsGoodForAttack(enemyAnts, powerTable, enemies1List, false);
         if (myAntsGoodForAttack.size() == 0 && enemyAntsGoodForAttack.size() > 0)
         {
            defendMediumForLocalBattle(localBattleInfo, moveRequestAnts, moveRequests);
            continue;
         }

         // phase 1 - analyze attackers and targets
         for (Point myAttacker : myAntsGoodForAttack)
         {
            Point target = findBestTarget(myAttacker, powerTable, enemies1List);
            targets[myAttacker.tag] = target;

            Direction bestDirection = findClosestSquareDirection(myAttacker, target);
            if (bestDirection != null)
            {
               Point newPos = myAttacker.plus(bestDirection);
               List<Point> targetsAfterMove = newPos.inSquaredDistance(
                       enemyAnts, attackRangeSquared);
               for (Point targetAfterMove : targetsAfterMove)
               {
                  targetsToAttackers.get(targetAfterMove.tag).add(myAttacker);
                  targetsToAttackers.get(myAttacker.tag).add(targetAfterMove);
               }
            }
         }

         // phase 2 - remove attackers if there are no enough ants to attack
         final int MIN_ATTACKERS_FOR_ONE_TARGET = 2;
         for (Point myAttacker : myAntsGoodForAttack)
         {
            Point target = targets[myAttacker.tag];
            if (target != null)
            {
               int attackersCount = targetsToAttackers.get(target.tag).size();
               int defendersCount = targetsToAttackers.get(myAttacker.tag).size();

               if (!(attackersCount >= MIN_ATTACKERS_FOR_ONE_TARGET &&
                       defendersCount < attackersCount) ||
                       (findClosestSquareDirection(myAttacker, target) == null))
               {
                  targets[myAttacker.tag] = null;
                  for (Point otherTarget : targetsToAttackers.get(myAttacker.tag))
                  {
                     targetsToAttackers.get(otherTarget.tag).remove(myAttacker);
                     int newAttackersCount = targetsToAttackers.get(otherTarget.tag).size();
                     if (newAttackersCount < MIN_ATTACKERS_FOR_ONE_TARGET)
                     {
                        for (Point attacker : targetsToAttackers.get(otherTarget.tag))
                        {
                           targets[attacker.tag] = null;
                        }
                     }
                  }
                  targetsToAttackers.get(myAttacker.tag).clear();
               }
            }
         }

         // phase 3 - attack
         for (Point myAttacker : myAntsGoodForAttack)
         {
            Point target = targets[myAttacker.tag];
            if (target != null)
            {
               Direction bestDirection = findClosestSquareDirection(myAttacker, target);

               if (bestDirection != null)
               {
                  moveUnsafe(myAttacker, bestDirection);
                  newPositionsOfMyAnts.remove(myAttacker);
                  newPositionsOfMyAnts.add(myAttacker.plus(bestDirection));
               }
            }
         }


         for (int i = 0; i < targetsToAttackers.size(); ++i)
         {
            targetsToAttackers.get(i).clear();
         }

         // Defence
         for (Point enemyAttacker : enemyAntsGoodForAttack)
         {
            Point target = findBestTarget(enemyAttacker, powerTable, enemies1List);
            targets[enemyAttacker.tag] = target;

            Direction bestDirection = findClosestSquareDirection(enemyAttacker, target);
            if (bestDirection != null)
            {
               Point newPos = enemyAttacker.plus(bestDirection);
               List<Point> targetsAfterMove = newPos.inSquaredDistance(
                       myAnts, attackRangeSquared);

               if (targetsAfterMove.size() == 0)
               {
                  targets[enemyAttacker.tag] = null;
               }
               for (Point targetAfterMove : targetsAfterMove)
               {
                  targetsToAttackers.get(targetAfterMove.tag).add(enemyAttacker);
                  targetsToAttackers.get(enemyAttacker.tag).add(targetAfterMove);
               }
            }
         }

         Set<Point> enemyAntsAfterAttack = new HashSet<Point>();
         for (Point enemyAttacker : enemyAntsGoodForAttack)
         {
            Point myAnt = targets[enemyAttacker.tag];
            if (myAnt != null  && !movedAnts.contains(myAnt) && !moveRequestAnts.contains(myAnt))
            {
               List<Point> attackers = targetsToAttackers.get(myAnt.tag);
               int attackersCount = attackers.size();
               int defendersCount = targetsToAttackers.get(enemyAttacker.tag).size();
               if (/*attackersCount >= 2 && */defendersCount <= attackersCount)
               {
                  Direction bestDirection = findMostFarSquareDirection(myAnt, attackers,
                          moveRequests);

                  if (bestDirection != null)
                  {
                     Point newPos = myAnt.plus(bestDirection);
                     if (ants.getMyAnts().contains(newPos) && !newFreePoints.contains(newPos))
                     {
                        moveRequests.put(newPos, new MoveRequest(myAnt, bestDirection, newPos));
                        moveRequestAnts.add(myAnt);
                     }
                     else
                     {
                        moveUnsafe(myAnt, bestDirection);
                        newPositionsOfMyAnts.remove(myAnt);
                        newPositionsOfMyAnts.add(newPos);
                     }
                  }

                  for (Point attacker : attackers)
                  {
                     Direction bestAttackDirection = findClosestSquareDirection(attacker, myAnt);
                     if (bestAttackDirection != null)
                     {
                        enemyAntsAfterAttack.add(attacker.plus(bestAttackDirection));
                     }
                  }
               }
            }
         }


         // Defence, phase 2
         for (Point otherMyAnt : myAnts)
         {
            if (!movedAnts.contains(otherMyAnt) && !moveRequestAnts.contains(otherMyAnt))
            {
               if (otherMyAnt.inSquaredDistance(enemyAntsAfterAttack, attackRangeSquared).size() >
                       0)
               {
                  List<Point> nearEnemyAntsAfterAttack = otherMyAnt
                          .inSquaredDistance(enemyAntsAfterAttack, attackRangeSquared);
                  Direction bestDirection =
                          findMostFarSquareDirection(otherMyAnt, nearEnemyAntsAfterAttack,
                                  moveRequests);
                  if (bestDirection != null)
                  {
                     Point newPos = otherMyAnt.plus(bestDirection);
                     if (ants.getMyAnts().contains(newPos) && !newFreePoints.contains(newPos))
                     {
                        moveRequests.put(newPos, new MoveRequest(otherMyAnt, bestDirection, newPos));
                        moveRequestAnts.add(otherMyAnt);
                     }
                     else
                     {
                        moveUnsafe(otherMyAnt, bestDirection);
                        newPositionsOfMyAnts.remove(otherMyAnt);
                        newPositionsOfMyAnts.add(newPos);
                     }
                  }
               }
            }
         }

         // far ants
         int movedAntsCount = movedAnts.size();
         while (true)
         {
            recalcPowerTableForEnemyAnts(powerTable, enemyAnts, newPositionsOfMyAnts);
            for (Point myAnt : myAnts)
            {
               if (movedAnts.contains(myAnt))
               {
                  continue;
               }

               if (moveRequests.containsKey(myAnt))
               {
                  tryRandomMove(myAnt, moveRequests.get(myAnt));
               }
               else
               {
                  if (enemies1List.get(myAnt.tag).size() == 0)
                  {
                     List<Point> enemies2 = myAnt.filterNear2ToSquaredRange(
                             enemyAnts, attackRangeSquared);

                     if (powerOfAntIsMax(myAnt, enemies2, powerTable))
                     {
                        Direction bestDirection =
                                findClosestSquareDirection(myAnt, enemies2, enemyAntsAfterAttack);
                        Point newPos = bestDirection != null ? myAnt.plus(bestDirection) : myAnt;
                        if (isSafeToMoveWithFarAnt(newPos, enemies2))
                        {
                           newPositionsOfMyAnts.remove(myAnt);
                           newPositionsOfMyAnts.add(newPos);
                           moveUnsafe(myAnt, bestDirection);
                        }
                     }
                  }
               }
            }

            int newMovedAntsCount = movedAnts.size();
            if (movedAntsCount == newMovedAntsCount)
            {
               break;
            }
            else
            {
               movedAntsCount = newMovedAntsCount;
            }
         }

         // null moves for rest ants
         for (Point myAnt : myAnts)
         {
            if (!movedAnts.contains(myAnt) && !moveRequests.containsKey(myAnt))
            {
               nullMove(myAnt);
            }
         }

      }

      executeMoveRequests(moveRequestAnts, moveRequests);
   }

   private void defendMediumForLocalBattle(BattleCalculator.LocalBattleInfo localBattleInfo,
                                           Set<Point> moveRequestAnts,
                                           Map<Point, MoveRequest> moveRequests)
   {
      int j = 0;
      for (int i = 0; i < localBattleInfo.myAnts.size(); ++i, ++j)
      {
         Point ant = localBattleInfo.myAnts.get(i);
         ant.tag = j;
      }
      for (int i = 0; i < localBattleInfo.enemyAnts.size(); ++i, ++j)
      {
         Point ant = localBattleInfo.enemyAnts.get(i);
         ant.tag = j;
      }

      List<Point> myAntsSorted = new ArrayList<Point>(localBattleInfo.myAnts);
      List<Point> enemyAnts = new ArrayList<Point>(localBattleInfo.enemyAnts);
      final Integer[] distances1 = new Integer[myAntsSorted.size()];
      final Integer[] distances2 = new Integer[myAntsSorted.size()];

      final List<List<Point>> near1Enemies = new ArrayList<List<Point>>();
      final List<List<Point>> near2Enemies = new ArrayList<List<Point>>();
      for (Point myAnt : myAntsSorted)
      {
         List<Point> near1EnemyAnts = myAnt.filterNearToSquaredRangeFromPoints(enemyAnts, attackRangeSquared);
         near1Enemies.add(near1EnemyAnts);

         List<Point> near2EnemyAnts = myAnt.filterNear2ToSquaredRange(enemyAnts, attackRangeSquared);
         near2Enemies.add(near2EnemyAnts);
         distances1[myAnt.tag] = myAnt.sumDistance(near2EnemyAnts);
         distances2[myAnt.tag] = myAnt.sumSquaredDistance(near2EnemyAnts);
      }

      Collections.sort(myAntsSorted, new Comparator<Point>()
      {
         public int compare(Point o1, Point o2)
         {
            return Utils.compareTo(
                    Arrays.asList(-near1Enemies.get(o1.tag).size(),
                            distances1[o1.tag], distances2[o1.tag]),
                    Arrays.asList(-near1Enemies.get(o2.tag).size(),
                            distances1[o2.tag], distances2[o2.tag]));
         }
      });

      for (Point myAnt : myAntsSorted)
      {
         if (movedAnts.contains(myAnt))
         {
            continue;
         }

         Direction bestDirection = null;
         int maxDist1 = distances1[myAnt.tag];
         int maxDist2 = distances2[myAnt.tag];
         int maxNear2EnemiesAfterMove = -1;
         MoveRequest request = null;

         for (Direction d : Direction.values)
         {
            Point newPos = myAnt.plus(d);
            boolean currentPointIsRequested = moveRequests.containsKey(myAnt);
            if (!newPos.getType(ants).isWater() && !newPos.getType(ants).isFood() &&
                    (!destinations.contains(newPos)))
            {
               List<Point> near1EnemyAnts = near1Enemies.get(myAnt.tag);
               List<Point> near2EnemyAnts = near2Enemies.get(myAnt.tag);
               if (near1EnemyAnts.size() > 0)
               {
                  int dist1 = newPos.sumDistance(near2EnemyAnts);
                  int dist2 = newPos.sumSquaredDistance(near2EnemyAnts);

                  if (Utils.compareTo(dist1, dist2, maxDist1, maxDist2) > 0)
                  {
                     bestDirection = d;
                     maxDist1 = dist1;
                     maxDist2 = dist2;

                     if (ants.getMyAnts().contains(newPos) && !newFreePoints.contains(newPos))
                     {
                        request = new MoveRequest(myAnt, bestDirection, newPos);
                     }
                     else
                     {
                        request = null;
                     }
                  }
               }
               else
               {
                  if (currentPointIsRequested)
                  {
                     if (!moveRequests.containsKey(newPos) &&
                             newPos.filterNearToSquaredRangeFromPoints(
                                     near2EnemyAnts, attackRangeSquared).size() == 0)
                     {
                        int near2EnemiesAfterMove = newPos.filterNear2ToSquaredRange(
                                near2EnemyAnts, attackRangeSquared).size();

                        if (near2EnemiesAfterMove > maxNear2EnemiesAfterMove
                                || (near2EnemiesAfterMove == maxNear2EnemiesAfterMove &&
                                request != null))
                        {
                           bestDirection = d;
                           maxNear2EnemiesAfterMove = near2EnemiesAfterMove;

                           if (ants.getMyAnts().contains(newPos) && !newFreePoints.contains(newPos))
                           {
                              request = new MoveRequest(myAnt, bestDirection, newPos);
                           }
                           else
                           {
                              request = null;
                           }
                        }
                     }
                  }
               }
            }
         }

         if (request == null)
         {
            if (bestDirection == null)
            {
               nullOrRandomMove(myAnt, moveRequests, moveRequestAnts);
            }
            else
            {
               moveUnsafe(myAnt, bestDirection);
               if (moveRequests.containsKey(myAnt))
               {
                  MoveRequest oldRequest = moveRequests.get(myAnt);
                  moveUnsafe(oldRequest.ant, oldRequest.direction);
                  moveRequests.remove(myAnt);
               }
            }
         }
         else if (!moveRequests.containsKey(request.newPos))
         {
            moveRequests.put(request.newPos, request);
            moveRequestAnts.add(request.ant);
         }
      }
   }

   private void executeMoveRequests(Set<Point> moveRequestAnts,
                                    Map<Point, MoveRequest> moveRequests)
   {
      LinkedList<Map.Entry<Point, MoveRequest>> sortedRequests =
              new LinkedList<Map.Entry<Point, MoveRequest>>();
      for (Map.Entry<Point, MoveRequest> entry : moveRequests.entrySet())
      {
         if (moveRequestAnts.contains(entry.getKey()))
         {
            sortedRequests.add(entry);
         }
         else
         {
            sortedRequests.add(0, entry);
         }
      }

      for (Map.Entry<Point, MoveRequest> entry : sortedRequests)
      {
         MoveRequest request = entry.getValue();
         if (notMovedAnts.contains(request.ant))
         {
            boolean moved = false;
            if (notMovedAnts.contains(entry.getKey()))
            {
               moved = tryRandomMove(entry.getKey(), request);
            }
            else if (newFreePoints.contains(entry.getKey()))
            {
               moveUnsafe(request.ant, request.direction);
               moved = true;
            }

            if (!moved)
            {
               nullMove(request.ant);
            }
         }
      }
   }

   private void defendMedium(List<BattleCalculator.LocalBattleInfo> localBattleInfos)
   {
      Set<Point> moveRequestAnts = new HashSet<Point>();
      Map<Point, MoveRequest> moveRequests = new HashMap<Point, MoveRequest>();
      for (BattleCalculator.LocalBattleInfo localBattleInfo : localBattleInfos)
      {
         localBattleInfo.myAnts.removeAll(movedAnts);
         if (localBattleInfo.myAnts.size() == 0 ||
                 localBattleInfo.myAnts.size() >= localBattleInfo.enemyAnts.size())
         {
            continue;
         }

         defendMediumForLocalBattle(localBattleInfo, moveRequestAnts, moveRequests);
      }

      executeMoveRequests(moveRequestAnts, moveRequests);
   }

   private static class MoveRequest
   {
      Point ant;
      Direction direction;
      Point newPos;

      private MoveRequest(Point ant, Direction direction, Point newPos)
      {
         this.ant = ant;
         this.direction = direction;
         this.newPos = newPos;
      }
   }

   private boolean tryRandomMove(Point ant, MoveRequest request)
   {
      boolean res = false;
      for (Direction d : Direction.values)
      {
         Point newPos = ant.plus(d);
         int enemiesCount = newPos.filterNearToSquaredRangeFromPoints(
                 ants.getEnemyAnts(), attackRangeSquared).size();
         if (enemiesCount == 0 && isPointFreeForMove(newPos))
         {
            moveUnsafe(ant, d);
            moveUnsafe(request.ant, request.direction);
            res = true;
            break;
         }
      }
      return res;
   }

   private void nullOrRandomMove(Point ant, Map<Point, MoveRequest> moveRequests,
                                 Set<Point> moveRequestsAnts)
   {
      boolean moved = false;
      if (moveRequests.containsKey(ant))
      {
         MoveRequest request = moveRequests.get(ant);
         for (Direction d : Direction.values)
         {
            Point newPos = ant.plus(d);
            if (isPointFreeForMove(newPos) && !moveRequests.containsKey(newPos))
            {
               moveUnsafe(ant, d);

               moveUnsafe(request.ant, request.direction);
               moved = true;

               break;
            }
         }

         if (!moved)
         {
            nullMove(request.ant);
         }

         if (moveRequestsAnts != null)
         {
            moveRequestsAnts.remove(request.ant);
         }
      }
      else
      {
         nullMove(ant);
      }

      moveRequests.remove(ant);
   }

   private void attackSimple()
   {
      final List<AntAttackInfo> antsInfo = new ArrayList<AntAttackInfo>();

      int aggressionRangeSquared = ants.getAttackRangeSquared();
      if (countOfStrongOpponents > 1)
      {
         if (chanceToWin > CHANCE_TO_WIN1)
         {
            aggressionRangeSquared *= 2;
         }
         if (chanceToWin > CHANCE_TO_WIN4)
         {
            aggressionRangeSquared *= 2;
         }
      }

      for (Point ant : ants.getMyAnts())
      {
         if (movedAnts.contains(ant))
         {
            continue;
         }

         int antAggressionRangeSquared = aggressionRangeSquared;
         if (ant.inSquaredDistance(ants.getMyAnts(), ants.getViewSquaredRange()).size() == 1)
         {
            antAggressionRangeSquared = ants.getAttackRangeSquared();
         }

         List<Point> enemyAnts = ant.filterNear2ToSquaredRange(ants.getEnemyAnts(),
                 antAggressionRangeSquared);

         Point nearest = chanceToWin < CHANCE_TO_WIN5 ? ant.getNearestHalfX(enemyAnts, false) :
                 ant.getNearest(enemyAnts, false);

         if (nearest != null)
         {
            int dist = 0;

            if (chanceToWin < CHANCE_TO_WIN5)
            {
               List<Direction> shortestPath = ant.findShortestPath(nearest);
               if (shortestPath != null)
               {
                  dist = shortestPath.size();
               }
            }
            else
            {
               dist = ant.distanceInCellsTo(nearest);
            }

            antsInfo.add(new AntAttackInfo(ant, enemyAnts, nearest, dist));
         }
      }

      Collections.sort(antsInfo);

      Map<Point, MoveRequest> moveRequests = new HashMap<Point, MoveRequest>();

      for (AntAttackInfo antAttackInfo : antsInfo)
      {
         Point ant = antAttackInfo.ant;
         Point nearest = antAttackInfo.nearest;
         if (!ant.isNear2ToSquaredRange(nearest, attackRangeSquared))
         {
            goToPoint(ant, nearest, null, aggressionRangeSquared);
            continue;
         }

         int attackRadius = ants.getAttackRangeSquared();
         List<Point> allyAnts = nearest.filterNear2ToSquaredRange(ants.getMyAnts(), attackRadius);
         List<Point> enemyAnts = antAttackInfo.enemyAnts;

         int allyAntsCount = allyAnts.size();
         int enemyAntsCount = enemyAnts.size();

         boolean keepDistance = false;
         boolean attack = false;
         if (allyAntsCount > enemyAntsCount && allyAntsCount < enemyAntsCount * 2)
         {
            keepDistance = false;
         }
         else if (allyAntsCount <= enemyAntsCount)
         {
            keepDistance = true;
         }
         else if (allyAntsCount > enemyAntsCount * 2 ||
                 nearest.filterNearToSquaredRangeFromPoints(allyAnts, attackRadius).size() >= 3)
         {
            attack = true;
         }

         if (!keepDistance && !attack)
         {
            if (ant.isNearToSquaredDist(nearest, attackRadius))
            {
               nullMove(ant);
            }
            else
            {
               if (!goToPoint(ant, nearest, new MinEnemiesCanAttack(enemyAnts, 1),
                       aggressionRangeSquared))
               {
                  nullMove(ant);
               }
            }
         }
         else if (keepDistance && !attack)
         {
            if (ant.isNearToSquaredDist(nearest, attackRadius))
            {
               Direction bestDirection = null;
               MoveRequest request = null;
               int minEnemies = enemyAnts.size();
               for (Direction d : Direction.values)
               {
                  Point newPos = ant.plus(d);

                  if (newPos.inSquaredDistance(enemyAnts, attackRadius).size() == 0 &&
                         !newPos.getType().isWater() && (!destinations.contains(newPos)))
                  {
                     List<Point> newEnemies =
                             newPos.filterNearToSquaredRangeFromAnt(enemyAnts, attackRangeSquared);
                     if (newEnemies.size() < minEnemies)
                     {
                        minEnemies = newEnemies.size();
                        bestDirection = d;

                        if (ants.getMyAnts().contains(newPos) && !newFreePoints.contains(newPos))
                        {
                           request = new MoveRequest(ant, bestDirection, newPos);
                        }
                        else
                        {
                           request = null;
                        }
                     }
                  }
               }

               if (request == null)
               {
                  moveUnsafe(ant, bestDirection);
               }
               else
               {
                  moveRequests.put(request.newPos, request);
               }
            }
            else if (ant.isNear2ToSquaredRange(nearest, attackRadius))
            {
               nullOrRandomMove(ant, moveRequests, null);
            }
            else
            {
               if (!goToPoint(ant, nearest, new MinEnemiesCanAttack(enemyAnts, 1),
                       aggressionRangeSquared))
               {
                  nullMove(ant);
               }
            }
         }
         else
         {
            if (!goToPoint(ant, nearest, new MinEnemiesCanAttack(enemyAnts, 1),
                    aggressionRangeSquared))
            {
               nullMove(ant);
            }
         }
      }

   }

   // Exploration ##################################################################################
   private boolean defaultMove(Point ant, int shift)
   {
      boolean success = false;
      if (!movedAnts.contains(ant))
      {
         List<Direction> directions = Direction.getDirections(((ants.getTurn() + shift) / 25) % 4);
         for (Direction d : directions)
         {
            Vector v = new Vector(d);
            if (goByVector(ant, v, null, Direction.LEFT))
            {
               success = true;
               break;
            }
         }
      }
      return success;
   }

   private void processMoveTasks(Map<Point, MoveTask> moveTaskMap)
   {
      int currentTurn = ants.getTurn();
      for (Point ant : new ArrayList<Point>(moveTaskMap.keySet()))
      {
         if (movedAnts.contains(ant) || !ants.getMyAnts().contains(ant))
         {
            moveTaskMap.remove(ant);
            continue;
         }

         MoveTask task = moveTaskMap.get(ant);
         moveTaskMap.remove(ant);

         if (!task.isPathFree())
         {
            task = task.createNewTask(ant);
            if (task == null)
            {
               moveTaskMap.remove(ant);
               continue;
            }
         }

         if (task.isFinished(ant, currentTurn))
         {
            moveTaskMap.remove(ant);
            continue;
         }

         int posIndex = task.getPointIndexOnPath(ant);
         if (posIndex >= 0)
         {
            Direction d = task.getNextDirection(posIndex);
            Point newPos = ant.plus(d);
            if (isPointFreeForMove(newPos))
            {
               moveUnsafe(ant, d);
               moveTaskMap.put(newPos, task);
               continue;
            }
         }

         Point nextSubTarget = task.getNextSubTarget(ant, posIndex, 5);
         if (goToPoint(ant, nextSubTarget, null))
         {
            Order last = ants.getLastIssuedOrder();
            if (last != null && last.getDirection() != null)
            {
               Point newPos = ant.plus(last.getDirection());
               moveTaskMap.put(newPos, task);
            }
         }
         else
         {
            moveTaskMap.remove(ant);
         }

      }
   }

   private ExplorationInfo findBestGoOutPoint(Point myAnt, Collection<Point> goOutPoints)
   {
      double minInvestigation = Double.MAX_VALUE;
      List<Point> res = new ArrayList<Point>();

      for (Point goOutPoint : goOutPoints)
      {
         double investigation = BFSManager.getCumulativeInvestigation(goOutPoint);
         if (investigation < minInvestigation)
         {
            res.clear();
            res.add(goOutPoint);
            minInvestigation = investigation;
         }
         else if (investigation == minInvestigation)
         {
            res.add(goOutPoint);
         }
      }

      Vector vectorFromMyAnt = new Vector(0, 0);

      for (Point p : res)
      {
         vectorFromMyAnt = vectorFromMyAnt.plus(new Vector(myAnt, p));
      }
      Point nearToTargetPoint = myAnt.plus(vectorFromMyAnt);
      Point target = nearToTargetPoint.getNearest(res, true);

      return new ExplorationInfo(target, minInvestigation);
   }

   Set<Point> findAntsWithMinVisitValue(Map<Point, ExplorationInfo> explorationInfoMap)
   {
      double minVisitValue = Double.MAX_VALUE;
      Set<Point> res = new HashSet<Point>();

      for (Map.Entry<Point, ExplorationInfo> entry : explorationInfoMap.entrySet())
      {
         if (entry.getValue().minVisitValue < minVisitValue)
         {
            res.clear();
            res.add(entry.getKey());
            minVisitValue = entry.getValue().minVisitValue;
         }
         else if (entry.getValue().minVisitValue == minVisitValue)
         {
            res.add(entry.getKey());
         }
      }

      return res;
   }

   private void explorationUsingAvailabilityMap()
   {
      List<Point> myAnts = ants.getMyAnts();

      for (int i = 0; i < myAnts.size(); ++i)
      {
         Point currentAnt = myAnts.get(i);
         if (movedAnts.contains(currentAnt))
         {
            continue;
         }

         Point target = BFSManager.getPointWithBestAvailability(currentAnt);
         if (target != null)
         {
            goToPoint(currentAnt, target, null);
         }
      }
   }

   private void explorationForOpenMap()
   {
      processMoveTasks(explorationTaskMap);

      List<Point> myAnts = ants.getMyAnts();
      List<Point> holdDistanceAnts = new ArrayList<Point>(ants.getMyAnts());
      if (countOfStrongOpponents > 1 && chanceToWin < CHANCE_TO_WIN1)
      {
         holdDistanceAnts.addAll(ants.getEnemyAnts());
      }

      for (int i = 0; i < myAnts.size(); ++i)
      {
         Point currentAnt = myAnts.get(i);
         if (movedAnts.contains(currentAnt))
         {
            continue;
         }

         Vector vectorOfMove = new Vector(0, 0);

         if (chanceToWin < CHANCE_TO_WIN4)
         {
            int antsToConsider = 4;
            List<Point> nearest = currentAnt.getNearest(holdDistanceAnts, antsToConsider, false);
            for (int j = 0; j < nearest.size(); ++j)
            {
               Point otherAnt = nearest.get(j);

               Vector vectorFromAnt = new Vector(otherAnt, currentAnt).withLength(10);
               if (countOfStrongOpponents > 1 &&
                       currentAnt.distanceInCellsTo(otherAnt) > viewRange &&
                       currentAnt.inRange(ants.getEnemyAnts(), viewRange).size() > 2)
               {
                  vectorFromAnt = vectorFromAnt.negate();
               }

               vectorOfMove = vectorOfMove.plus(vectorFromAnt);
            }
         }
         else if (chanceToWin < CHANCE_TO_WIN5)
         {
            Point nearest = currentAnt.getNearest(ants.getMyAnts(), false);
            if (nearest != null)
            {
               Vector vectorFromAnt = new Vector(nearest, currentAnt);
               vectorOfMove = vectorOfMove.plus(vectorFromAnt);
            }
         }

         if (chanceToWin > CHANCE_TO_WIN1)
         {
            int enemiesToConsider = 1;
            List<Point> enemies =
                    currentAnt.getNearest(ants.getEnemyAnts(), enemiesToConsider, false);
            for (int j = 0; j < enemies.size(); ++j)
            {
               Point otherAnt = enemies.get(j);

               List<Direction> shortestPath = currentAnt.findShortestPath(otherAnt);
               Point p = Utils.getPointOnPath(currentAnt, shortestPath, 0.2);

               Vector v = new Vector(currentAnt, p != null ? p : otherAnt).withLength(15);
               vectorOfMove = vectorOfMove.plus(v);
            }

            if (ants.getEnemyHills().size() > 0)
            {
               Point enemyHill = currentAnt.getNearestX(ants.getEnemyHills(), true);
               if (enemyHill != null)
               {
                  List<Direction> shortestPath = currentAnt.findShortestPath(enemyHill);
                  Point p = Utils.getPointOnPath(currentAnt, shortestPath, 0.2);
                  Vector v = new Vector(currentAnt, p).withLength(10);
                  vectorOfMove = vectorOfMove.plus(v);
               }
            }
         }

         BFSManager.updateInvestigationMap(currentAnt, ants.getMyAntInfo(currentAnt));
         ExplorationInfo info = findBestGoOutPoint(currentAnt,
                    ants.getMyAntInfo(currentAnt).getGoOutPoints());
         if (info.target != null)
         {
            Vector v = new Vector(currentAnt, info.target).withLength(10);
            vectorOfMove = vectorOfMove.plus(v);
         }

//         Point availabilityTarget = BFSManager.getPointWithBestAvailability(currentAnt);
//         if (availabilityTarget != null)
//         {
//            Vector v = new Vector(currentAnt, availabilityTarget).withLength(10);
//            vectorOfMove = vectorOfMove.plus(v);
//         }

         boolean success;
         if (vectorOfMove.isZero())
         {
            success = defaultMove(currentAnt, i);
         }
         else
         {
            success = goByVector(currentAnt, vectorOfMove, null, Direction.LEFT);
         }

         if (success)
         {
            Order last = ants.getLastIssuedOrder();
            Point newPos = currentAnt;
            if (last != null && last.getDirection() != null)
            {
               newPos = currentAnt.plus(last.getDirection());
            }

            if (chanceToWin > CHANCE_TO_WIN2)
            {
               MoveTask explorationTask = new MoveTask(ants.getTurn(), 3 + i % 5, currentAnt,
                       PathFinding.lastCalculatedShortestPath);
               explorationTaskMap.put(newPos, explorationTask);
            }
         }
      }
   }

   private boolean isExplorationUsingAvailabilityMap()
   {
      return PathFinding.isMaze2();
   }

   private void exploration()
   {
//      explorationForMaze();
//      explorationForOpenMap();
//      explorationUsingAvailabilityMap();

      BFSManager.buildAvailabilityMap();
      if (isExplorationUsingAvailabilityMap())
      {
//         explorationForMaze();
         explorationUsingAvailabilityMap();
      }
      else
      {
         explorationForOpenMap();
      }
   }

   // Defend & Attack ##############################################################################
   private boolean isNeedToPatrolMyHills()
   {
      return ants.getMyAnts().size() >
              ants.getMyHills().size()*MIN_ANTS_FOR_HILL_FOR_START_DEFENDING;
   }

   private void patrolMyHills()
   {
      int patrolRange = 3;
      List<Point> myHillsNeedToPatrol = new ArrayList<Point>();
      for (Point p : ants.getMyHills())
      {
         if (p.inRange(ants.getMyAnts(), patrolRange).size() == 0)
         {
            myHillsNeedToPatrol.add(p);
         }
      }

      takeTargets(new HashSet<Point>(notMovedAnts), myHillsNeedToPatrol, 3,
              maxTakeTargetsRange, null);
   }

   private boolean isNeedToDefendHills()
   {
      int hillsCount = ants.getMyHills().size();
      return hillsCount == 1 ||
              ants.getMyAnts().size() > hillsCount*MIN_ANTS_FOR_HILL_FOR_START_DEFENDING;
   }

   private void defendMyHills()
   {
      List<Point> allEnemies = new ArrayList<Point>();
      for (Point hill : ants.getMyHills())
      {
         Set<Point> hillAvailablePoints = BFSManager.getAvailablePoints(hill,
                 MY_HILL_DANGER_RANGE * MY_HILL_DANGER_RANGE);

         Collection<Point> enemies = Utils.intersection(hillAvailablePoints, ants.getEnemyAnts());
         allEnemies.addAll(enemies);
      }

      int defendRange = !PathFinding.isOpenMap() ?
              DEFENDERS_AGGRESSION_RANGE_FOR_MAZE : DEFENDERS_AGGRESSION_RANGE_FOR_OPEN_MAP;
      int lastNotMovedAntsCount = notMovedAnts.size();
      for (int i = 0; i < DEFENDERS_WAVES_COUNT; ++i)
      {
         Set<Point> defenders = new HashSet<Point>(notMovedAnts);

         takeTargets(defenders, allEnemies, 0, defendRange, null);
         if (notMovedAnts.size() == lastNotMovedAntsCount)
         {
            break;
         }

         lastNotMovedAntsCount = notMovedAnts.size();
      }
   }

   private void attackEnemyHills()
   {
      List<Point> defenders = new ArrayList<Point>();
      if (!PathFinding.isOpenMap())
      {
         for (Point hill : ants.getMyHills())
         {
            Set<Point> pointsNearToHill =
                    BFSManager.getAvailablePoints(hill, MY_HILL_DANGER_RANGE *
                            MY_HILL_DANGER_RANGE);
            Set<Point> myAntsNearToHIll = Utils.intersection(notMovedAnts, pointsNearToHill);
            defenders.addAll(hill.getNearest(myAntsNearToHIll, 2, true));
         }
      }

      List<Order> orders = ants.getIssuedOrders();
      int ordersCount = orders.size();
      int attackHillDist = !PathFinding.isOpenMap() ?
              ATTACK_HILL_DIST_FOR_MAZE : ATTACK_HILL_DIST_FOR_OPEN_MAP;
      List<Point> enemyHills = ants.getEnemyHills();
      int[] maxAntsToAttack = new int[enemyHills.size()];
      Map<Point, Integer> hillPositions = new HashMap<Point, Integer>();

      Set<Point> attackers = new HashSet<Point>();
      for (int i = 0; i < maxAntsToAttack.length; ++i)
      {
         Point hill = enemyHills.get(i);
         hillPositions.put(hill, i);

         Set<Point> enemyAntsInRange = intersectionWithAvailablePoints(hill,
                 attackHillDist * attackHillDist, ants.getEnemyAnts());

         Set<Point> myAntsInRange = intersectionWithAvailablePoints(hill,
                 attackHillDist * attackHillDist, notMovedAnts);
         attackers.addAll(myAntsInRange);

         maxAntsToAttack[i] = (int)(enemyAntsInRange.size()* ATTACK_HILL_ANTS_FACTOR) +
            MIN_ANTS_TO_ATTACK_HILL;
      }

      int lastNotMovedAntsCount = notMovedAnts.size();
      Set<Point> targetEnemyHills = new HashSet<Point>(ants.getEnemyHills());
      targetEnemyHills.removeAll(hostagedHills.keySet());

      attackers.removeAll(defenders);
      while (targetEnemyHills.size() > 0)
      {
         takeTargets(attackers, new ArrayList<Point>(targetEnemyHills), 0, attackHillDist, null);

         if (notMovedAnts.size() == lastNotMovedAntsCount)
         {
            break;
         }

         attackers.removeAll(movedAnts);

         for (int i = ordersCount; i < orders.size(); ++i)
         {
            Point target = orders.get(i).getTarget();
            if (target != null && targetEnemyHills.contains(target))
            {
               if (--maxAntsToAttack[hillPositions.get(target)] <= 0)
               {
                  targetEnemyHills.remove(target);
               }
            }
         }
         ordersCount = orders.size();

         lastNotMovedAntsCount = notMovedAnts.size();
      }

   }

   private boolean isShouldKillAllHostagedHills()
   {
      return ants.getTurn() > ants.getTurns() - HOSTAGE_HILL_STOP_BEFORE_END ||
              calcChanceToWin() > CHANCE_TO_WIN2;
   }

   private void hostageEnemyHills()
   {
      if (isShouldKillAllHostagedHills())
      {
         hostagedHills.clear();
         return;
      }

      for (Point h : ants.getEnemyHills())
      {
         if (!hostagedHills.containsKey(h))
         {
            if (h.inSquaredDistance(ants.getMyAnts(), attackRangeSquared).size() > 0
                    && h.inSquaredDistance(ants.getEnemyAnts(), viewRangeSquared).size() == 0)
            {
               hostagedHills.put(h, new HostageHillInfo(ants.getTurn()));
            }
         }
      }

      A: for (Point h : new ArrayList<Point>(hostagedHills.keySet()))
      {
         List<Point> nearMyAnts = h.getNearest(h.inRange(ants.getMyAnts(), attackRange), 2, false);
         HostageHillInfo hostageHillInfo = hostagedHills.get(h);
         if (nearMyAnts.size() < 2 ||
                 ants.getTurn() > hostageHillInfo.capturingTurn + HOSTAGE_HILL_MAX_TURNS)
         {
            hostagedHills.remove(h);
            continue;
         }

         for (Point ant : nearMyAnts)
         {
            List<Point> nearEnemyAnts = ant.inRange(ants.getEnemyAnts(), attackRange + 3);
            nearEnemyAnts.remove(h);

            if (nearEnemyAnts.size() > 0)
            {
               hostagedHills.remove(h);
               continue A;
            }
         }

         for (Point ant : nearMyAnts)
         {
            if (ant.distanceInCellsTo(h) > 1)
            {
               goToPoint(ant, h, null);
            }
            else
            {
               nullMove(ant);
            }
         }
      }
   }

   // Initializations ##############################################################################
   private void clean()
   {
      destinations.clear();
      notMovedAnts.clear();
      notMovedAnts.addAll(ants.getMyAnts());
      movedAnts.clear();
      newFreePoints.clear();
      pendingMovesForTakingFood.clear();
      BFSManager.clearAvailablePointsMap();
   }

   private void initGame()
   {
      MyBot.ants = Ants.getInstance();
      PathFinding.clearStatistics();
      BattleCalculator.newFreePoints = MyBot.newFreePoints;
      BattleCalculator.destinations = MyBot.destinations;
      BattleCalculator.attackRange = ants.getAttackRangeSquared();
      BattleCalculator.attackMethod = ants.getAttackMethod();

      maxGoByVectorRange = 2 * (int)Math.sqrt(ants.getViewSquaredRange());
      if (Ants.getColumns() / 2 < maxGoByVectorRange)
      {
         maxGoByVectorRange = Ants.getColumns() / 2;
      }
      if (Ants.getRows() / 2 < maxGoByVectorRange)
      {
         maxGoByVectorRange = Ants.getRows() / 2;
      }

      maxTakeTargetsRange = 2 * (int)Math.sqrt(ants.getViewSquaredRange());
      dangerMoveValidator = new DangerMoveValidator(notMovedAnts, ants.getEnemyAnts());
      attackRangeSquared = ants.getAttackRangeSquared();
      attackRange = (int)Math.sqrt(attackRangeSquared) + 1;
      viewRangeSquared = ants.getViewSquaredRange();
      viewRange = (int)Math.sqrt(viewRangeSquared) + 1;
      isMultihillMap = ants.getMyHills().size() > 1;
      hostagedHills.clear();
   }

   private double calcChanceToWin()
   {
      return ants.getMyAnts().size();
   }

   private int calcCountOfStrongOpponents()
   {
      int[] enemiesCount = new int[25];
      for (Point enemy : ants.getEnemyAnts())
      {
         if (enemy.getType().id >= 0)
         {
            enemiesCount[enemy.getType().id]++;
         }
      }

      int maxCount = 0;
      final int border1 = 2;

      for (int i = 0; i < enemiesCount.length; ++i)
      {
         if (enemiesCount[i] >= border1 && enemiesCount[i] > maxCount)
         {
            maxCount = enemiesCount[i];
         }
      }

      final int border2 = Math.max(border1, maxCount / 5);

      int res = 0;
      for (int i = 0; i < enemiesCount.length; ++i)
      {
         if (enemiesCount[i] >= border2)
         {
            res++;
         }
      }

      return res;
   }

   private BattleCalculator.AttackMode selectAttackMode()
   {
      BattleCalculator.AttackMode attackMode = null;
      if (countOfStrongOpponents > 1 && ants.getMyAnts().size() < ants.getEnemyAnts().size() * 3)
      {
         attackMode = BattleCalculator.AttackMode.Defensive;
      }
      else
      {
         if (chanceToWin > CHANCE_TO_WIN3) // RAGE MODE ON!!
         {
            attackMode = BattleCalculator.AttackMode.Exchange;
         }
         else
         {
            attackMode = BattleCalculator.AttackMode.Aggressive;
         }
      }

      return attackMode;
   }

   private void initTurn()
   {
      chanceToWin = calcChanceToWin();
      countOfStrongOpponents = calcCountOfStrongOpponents();

      BattleCalculator.countOfStrongOpponents = countOfStrongOpponents;
      if (!ants.isTestInstance())
      {
         BattleCalculator.globalAttackMode = selectAttackMode();
      }

      BFSManager.buildVisiblePoints();
      clean();
   }

   private void makeNullMoveForAllNotMovedAnts()
   {
      ants.setDisableOutput(true);
      for (Point ant : new ArrayList<Point>(notMovedAnts))
      {
         nullMove(ant);
      }
      ants.setDisableOutput(false);
   }

   private void markInterestingPaths()
   {
      for (Point ant : ants.getMyAnts())
      {
         if (ant.inSquaredDistance(ants.getEnemyAnts(), viewRangeSquared).size() >= 1)
         {
            ants.getMyAntInfo(ant).markPathAsInteresting();
         }
      }
   }

   public void doTurn(Ants ants)
   {
      try
      {
         if (Ants.getInstance().getTurn() == 1)
         {
            initGame();
         }

         initTurn();

         if (isMultihillMap)
         {
            hostageEnemyHills();
         }

         List<Point> mootPoints = new ArrayList<Point>();
         pendingMovesMode = true;
         takeTargets(new HashSet<Point>(notMovedAnts), new ArrayList<Point>(ants.getFood()), 1,
                 maxTakeTargetsRange, mootPoints);
         pendingMovesMode = false;
         Set<Point> antsUsedForMakeMoveNotDanger = analyzePendingOrdersAndTakeFood();
         ants.issueAllPendingOrders();

         Set<Point> freeAnts = new HashSet<Point>(notMovedAnts);
         freeAnts.removeAll(antsUsedForMakeMoveNotDanger);
         takeTargets(freeAnts, mootPoints, 1, maxTakeTargetsRange, null);

         List<BattleCalculator.LocalBattleInfo> localBattleInfos =
                 BattleCalculator.splitOnLocalBattles(ants.getMyAnts(), ants.getEnemyAnts());

         if (isNeedToPatrolMyHills())
         {
            patrolMyHills();
         }

         ants.validateTurnDuration();
         attackUsingBattleCalculator();

         ants.validateTurnDuration();
         defendMedium(localBattleInfos);
         attackMedium2(localBattleInfos);

         ants.validateTurnDuration();
         attackSimple();

         if (!isExplorationUsingAvailabilityMap())
         {
            ants.validateTurnDuration();
            attackEnemyHills();
         }

         if (isNeedToDefendHills())
         {
            ants.validateTurnDuration();
            defendMyHills();
         }

//         freeAnts.removeAll(movedAnts);

         ants.validateTurnDuration();
         exploration();

         markInterestingPaths();

      }
      catch (NearToTimeoutException exc)
      {
//         System.out.println("timeout");
         // end turn
      }
      finally
      {
         makeNullMoveForAllNotMovedAnts();
      }
   }
}
