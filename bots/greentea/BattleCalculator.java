import java.util.*;
import java.util.List;

/**
 * Created by IntelliJ IDEA. User: GreenTea Date: 10.06.11 Time: 22:28 To change this template use
 * File | Settings | File Templates.
 */
public class BattleCalculator
{
   public static enum AttackMode
   {
      Exchange
              {
                 @Override
                 public double calcScores(List<Point> myAntsAlive, List<Point> enemyAntsAlive,
                                          double scoresForExchange)
                 {
                    double myAntsAliveCount = myAntsAlive.size() -
                            calcPenaltyForNearWalls(myAntsAlive, enemyAntsAlive);
                    double enemyAntsAliveCount = enemyAntsAlive.size();
                    if (myAntsAliveCount == 0 && enemyAntsAliveCount == 0)
                    {
                       return scoresForExchange;
                    }
                    return myAntsAliveCount * 0.75 - enemyAntsAliveCount;
                 }
              },
      Aggressive
              {
                 @Override
                 public double calcScores(List<Point> myAntsAlive, List<Point> enemyAntsAlive,
                                          double scoresForExchange)
                 {
                    double myAntsAliveCount = myAntsAlive.size() -
                            calcPenaltyForNearWalls(myAntsAlive, enemyAntsAlive);
                    double enemyAntsAliveCount = enemyAntsAlive.size();
                    if (myAntsAliveCount == 0 && enemyAntsAliveCount == 0)
                    {
                       return scoresForExchange;
                    }
                    if (enemyAntsAliveCount == 0)
                    {
                       return 3 * myAntsAliveCount;
                    }
                    if (myAntsAliveCount == 0)
                    {
                       return 1.0 / (3 * enemyAntsAliveCount);
                    }

                    return myAntsAliveCount / enemyAntsAliveCount;
                 }
              },
      Defensive
              {
                 @Override
                 public double calcScores(List<Point> myAntsAlive, List<Point> enemyAntsAlive,
                                          double scoresForExchange)
                 {
                    double myAntsAliveCount = myAntsAlive.size() -
                            calcPenaltyForNearWalls(myAntsAlive, enemyAntsAlive);
                    double enemyAntsAliveCount = enemyAntsAlive.size();
                    if (myAntsAliveCount == 0 && enemyAntsAliveCount == 0)
                    {
                       return scoresForExchange;
                    }
                    return myAntsAliveCount * 2 - enemyAntsAliveCount;
                 }
              };

      public abstract double calcScores(List<Point> myAntsAlive, List<Point> enemyAntsAlive,
                                        double scoresForExchange);

      private static double calcPenaltyForNearWalls(List<Point> myAntsAlive,
                                                    List<Point> enemyAntsAlive)
      {
         double res = 0;
         Ants ants = MyBot.ants;
         for (Point ant : myAntsAlive)
         {
            int countOfWaters = 0;
            for (Direction d2 : Direction.values)
            {
               if (ant.plus(d2).getType(ants).isWater())
               {
                  countOfWaters++;
               }
            }

            if (countOfWaters == 3)
            {
               res += 1.0;
            }
            if (countOfWaters == 2 && myAntsAlive.size() < enemyAntsAlive.size())
            {
               res += 0.5;
            }
         }
         return res;
      }
   }

   private static final double DEFAULT_SCORES_FOR_EXCHANGE = 0.9;
   private static final double DEFAULT_SCORES_FOR_DANGER_MOVE = 1.0;

   private static final int MAX_ANTS_TO_CALC_FOR_REGULAR_BATTLE = 7;
   private static Set<Point> newDestinationPoints = new HashSet<Point>();
   private static long maxTime = 0;

   public static Set<Point> destinations = new HashSet<Point>();
   public static Set<Point> freeMovedAnts = new HashSet<Point>();
   public static Set<Point> newFreePoints = new HashSet<Point>();
   public static int countOfStrongOpponents = 0;
   public static AttackMethod attackMethod = AttackMethod.Focus;
   public static int attackRange = 5;
   public static AttackMode globalAttackMode = AttackMode.Aggressive;

   public static class LocalBattleInfo
   {
      List<Point> myAnts = new ArrayList<Point>();
      List<Point> enemyAnts = new ArrayList<Point>();

      Set<Point> myMovedAnts = new HashSet<Point>();

      public LocalBattleInfo()
      {

      }

      public LocalBattleInfo(LocalBattleInfo other)
      {
         myAnts = new ArrayList<Point>(other.myAnts);
         enemyAnts = new ArrayList<Point>(other.enemyAnts);

         myMovedAnts = new HashSet<Point>(other.myMovedAnts);
      }

      public int getTotalAntsCount()
      {
         return myAnts.size() + myMovedAnts.size() + enemyAnts.size();
      }

      public boolean isValid()
      {
         return myAnts.size() + myMovedAnts.size() > 0 && enemyAnts.size() > 0;
      }
   }

   private static class Complexity
   {
      private int antsCount;
      private boolean hasNearFood;

      public Complexity(int antsCount, boolean hasNearFood)
      {
         this.antsCount = antsCount;
         this.hasNearFood = hasNearFood;
      }

      @Override
      public boolean equals(Object o)
      {
         if (this == o)
         {
            return true;
         }
         if (o == null || getClass() != o.getClass())
         {
            return false;
         }

         Complexity that = (Complexity) o;

         if (antsCount != that.antsCount)
         {
            return false;
         }
         if (hasNearFood != that.hasNearFood)
         {
            return false;
         }

         return true;
      }

      @Override
      public int hashCode()
      {
         int result = antsCount;
         result = 31 * result + (hasNearFood ? 1 : 0);
         return result;
      }
   }

   private static void collectAnts(LocalBattleInfo battleInfo, Point ant, boolean isMyAnt,
                                      Set<Point> freeMyAnts, Set<Point> freeEnemyAnts)
   {
      Set<Point> player1FreeAnts =  freeMyAnts;
      Set<Point> player2FreeAnts =  freeEnemyAnts;
      List<Point> player1GroupAnts = battleInfo.myAnts;
      if (!isMyAnt)
      {
         player1FreeAnts =  freeEnemyAnts;
         player2FreeAnts =  freeMyAnts;
         player1GroupAnts = battleInfo.enemyAnts;
      }

      List<Point> enemies = freeMovedAnts.contains(ant) ?
              ant.filterNearToSquaredRangeFromPoints(player2FreeAnts, attackRange) :
              ant.filterNear2ToSquaredRange(player2FreeAnts, attackRange);
      player2FreeAnts.removeAll(enemies);

      if (!isMyAnt)
      {
         List<Point> movedAnts = ant.filterNearToSquaredRangeFromAnt(freeMovedAnts,
                 attackRange);
         battleInfo.myMovedAnts.addAll(movedAnts);
         enemies.addAll(movedAnts);
      }

      if (!freeMovedAnts.contains(ant))
      {
         player1GroupAnts.add(ant);
         player1FreeAnts.remove(ant);
      }

      for (Point enemy : enemies)
      {
         collectAnts(battleInfo, enemy, !isMyAnt, freeMyAnts, freeEnemyAnts);
      }
   }

   public static List<LocalBattleInfo> splitOnLocalBattles(
      List<Point> myAnts, List<Point> enemyAnts)
   {
      List<LocalBattleInfo> localBattles = new ArrayList<LocalBattleInfo>();

      Set<Point> freeMyAnts = new HashSet<Point>(myAnts);
      Set<Point> freeEnemyAnts = new HashSet<Point>(enemyAnts);

      freeMovedAnts.clear();
      freeMovedAnts.addAll(destinations);
      freeMovedAnts.addAll(newDestinationPoints);

      while (freeEnemyAnts.size() > 0)
      {
         Point enemyAnt = freeEnemyAnts.iterator().next();
         LocalBattleInfo battleInfo = new LocalBattleInfo();
         collectAnts(battleInfo, enemyAnt, false, freeMyAnts, freeEnemyAnts);
         if (battleInfo.isValid())
         {
            localBattles.add(battleInfo);
         }
      }

      Collections.sort(localBattles, new Comparator<LocalBattleInfo>()
      {
         public int compare(LocalBattleInfo o1, LocalBattleInfo o2)
         {
            Integer count1 = o1.getTotalAntsCount();
            Integer count2 = o2.getTotalAntsCount();

            return count1.compareTo(count2);
         }
      });

      return localBattles;
   }

   public static Map<Point, Direction> findBestMoves(List<Point> myAnts, List<Point> enemyAnts)
   {
      Map<Point, Direction> res = new HashMap<Point, Direction>();
      newDestinationPoints.clear();

      List<LocalBattleInfo> localBattles = splitOnLocalBattles(myAnts, enemyAnts);
      for (LocalBattleInfo localBattleInfo : localBattles)
      {
         BattleCalculator calculator = new BattleCalculator(localBattleInfo);
         Map<Point, Direction> localBestMoves = calculator.findBestMovesLocal();
         for (Map.Entry<Point, Direction> move : localBestMoves.entrySet())
         {
            Point ant = move.getKey();
            Direction d = move.getValue();

            Point newPos = d == null ? ant : ant.plus(d);
            newDestinationPoints.add(newPos);

            res.put(ant, d);
         }
      }

      newDestinationPoints.clear();
      return res;
   }

   private static Set<Point> antsWhichMakeMoveNotDanger;
   public static Set<Point> popAntsWhichMakeMoveNotDanger()
   {
      Set<Point> res = antsWhichMakeMoveNotDanger;
      antsWhichMakeMoveNotDanger = null;
      return res;
   }

   public static boolean isMoveDanger(Point ant, Direction move,
                                      Collection<Point> myAnts, Collection<Point> enemyAnts)
   {
      Point newPos = ant.plus(move);
      List<Point> nearEnemies = newPos.filterNear2ToSquaredRange(enemyAnts, attackRange);
      if (nearEnemies.size() == 0)
      {
         return false;
      }

      List<LocalBattleInfo> localBattles0 = splitOnLocalBattles(
              new ArrayList<Point>(myAnts), nearEnemies);
      if (localBattles0.size() == 0)
      {
         return false;
      }

      LocalBattleInfo localBattle01 = localBattles0.get(0);
      BattleCalculator calculator01 = new BattleCalculator(localBattle01);
      double startScores01 = calculator01.evaluateStartPosition();

      LocalBattleInfo localBattle02 = new LocalBattleInfo(localBattle01);
      localBattle02.myAnts.clear();
      localBattle02.myAnts.add(ant);
      BattleCalculator calculator02 = new BattleCalculator(localBattle02);
      double startScores02 = calculator02.evaluateStartPosition();

      newDestinationPoints.add(newPos);
      newFreePoints.add(ant);

      Set<Point> myAntsWithoutCurrent = new HashSet<Point>(myAnts);
      myAntsWithoutCurrent.remove(ant);

      List<LocalBattleInfo> localBattles1 = splitOnLocalBattles(
              new ArrayList<Point>(myAntsWithoutCurrent), nearEnemies);
      if (localBattles1.size() == 0)
      {
         return false;
      }
      LocalBattleInfo localBattle1 = localBattles1.get(0);
      if (!localBattle1.myMovedAnts.contains(newPos))
      {
         return false;
      }

      BattleCalculator calculator1 = new BattleCalculator(localBattle1);

      if (localBattle1.myAnts.size() + localBattle1.myMovedAnts.size() ==
              localBattle1.enemyAnts.size())
      {
         calculator1.setScoresForExchange(DEFAULT_SCORES_FOR_DANGER_MOVE);
      }
      calculator1.findBestMovesLocal();
      double bestScoresAfterMove1 = calculator1.getMinScoresForBestMove();

      LocalBattleInfo localBattle2 = new LocalBattleInfo(localBattle1);
      localBattle2.myAnts.clear();
      BattleCalculator calculator2 = new BattleCalculator(localBattle2);

      if (localBattle2.myAnts.size() + localBattle2.myMovedAnts.size() ==
              localBattle2.enemyAnts.size())
      {
         calculator2.setScoresForExchange(DEFAULT_SCORES_FOR_DANGER_MOVE);
      }
      calculator2.findBestMovesLocal();
      double bestScoresAfterMove2 = calculator2.getMinScoresForBestMove();

      newDestinationPoints.remove(newPos);
      newFreePoints.remove(ant);

      boolean danger1 = startScores01 > bestScoresAfterMove1;
      boolean danger2 = startScores02 > bestScoresAfterMove2;

      if (danger2 && !danger1)
      {
         antsWhichMakeMoveNotDanger = new HashSet<Point>(localBattle1.myAnts);
      }
      return danger1;
   }

   private boolean onTurnAndPoint(int turn, Point ant, int col, int row)
   {
      Ants ants = Ants.getInstance();
      return (ants.getTurn() == 61 && ant.equals(Point.get(row, col)));
   }

   public static void main(String[] args)
   {
      String[] mapStr = new String[]
              {". . . . . . . . . . . . . . . . . . . .",
               ". . . . . . . . . . . . . . . . . . . .",
               ". . . . . . . . . . . . . . . . . . . .",
               "% . . . . . . . . . . . . . . . . . . .",
               "% . . . . . . . . . . . . . . . . . . .",
               "% . . . . . . . . . . . A . . B . . . .",
               "% % % % % % % % . . . A A . . B . . . .",
               ". . . . . . . % . . . . . . . B . . . .",
               ". . . . . . . % . . . . . . . . . . . .",
               ". . . . . . . . . . B B B . . . . . . .",
               ". . . . . . . . . . . . . . . . . . . .",
               ". . . . . . . . . . . . . . . . . . . .",
               ". . . . . . . . . . . . . . . . . . . .",
               ". . . . . . . . . . . . . . . . . . . .",
               ". . . . . . . . . . . . . . . . . . . .",};

      PointType[][] map = Utils.parseMap(mapStr);
      Ants ants = new Ants(map);

      Ants.pushAnts(ants);

      long startTime = System.currentTimeMillis();
      int count = 1;

      MyBot bot = new MyBot();
      bot.doTurn(ants);

      for (int i = 0; i < count; ++i)
      {
//            System.out.println(findBestMoves(ants.getMyAnts(), ants.getEnemyAnts()));
//         findBestMoves(ants.getMyAnts(), ants.getEnemyAnts());
      }


      long time = System.currentTimeMillis() - startTime;
      System.out.println("Time of " + count + " executions: " + time);

      Ants.popAnts();
   }

   private int myAntsCount;
   private int enemyAntsCount;
   private List<Point> myAnts;
   private List<Point> enemyAnts;
   private List<Point> allAnts;
   private Point[] antsPositionsAfterMove;
   private List<Point> myMovedAnts;

   private Direction[] currentMoves;
   private Direction[] currentBestMoves;

   private double minScoresForBestMove = Integer.MIN_VALUE;
   private double totalScoresForBestMove = Integer.MIN_VALUE;

   private double minScoresForCurrMove;
   private double totalScoresForCurrMove;

//   private IntSet evaluatedPositions;
//   private int positionHashCode;

   private static List<Direction> directions =
           Arrays.asList(Direction.UP, Direction.DOWN, Direction.LEFT, Direction.RIGHT, null);
   private static List<Direction> noDirections = Arrays.asList((Direction)null);

   private AttackMode localAttackMode;

   private boolean hasNearFood = false;
   private boolean hasNearHill = false;
   private double scoresForExchange = DEFAULT_SCORES_FOR_EXCHANGE;

   public BattleCalculator(LocalBattleInfo localBattleInfo)
   {
      myAntsCount = localBattleInfo.myAnts.size();
      enemyAntsCount = localBattleInfo.enemyAnts.size();

      myAnts = new ArrayList<Point>(localBattleInfo.myAnts);
      enemyAnts = new ArrayList<Point>(localBattleInfo.enemyAnts);
      allAnts = new ArrayList<Point>(myAntsCount + enemyAntsCount);
      allAnts.addAll(localBattleInfo.myAnts);
      allAnts.addAll(localBattleInfo.enemyAnts);

      myMovedAnts = new ArrayList<Point>(localBattleInfo.myMovedAnts);
      currentMoves = new Direction[allAnts.size()];

      antsPositionsAfterMove = new Point[allAnts.size()];

      testHasNearFood();
      testHasNearHill();
      localAttackMode = hasNearHill ? AttackMode.Exchange : BattleCalculator.globalAttackMode;
   }

   public void setScoresForExchange(double scoresForExchange)
   {
      this.scoresForExchange = scoresForExchange;
   }

   private void testHasNearFood()
   {
      List<Point> allAntsWithMoved = new ArrayList<Point>(allAnts);
      allAntsWithMoved.addAll(myMovedAnts);

      for (Point ant : allAntsWithMoved)
      {
         if (ant.inRange(Ants.getInstance().getFood(), 1, 2).size() > 0)
         {
            hasNearFood = true;
            break;
         }
      }
   }

   private void testHasNearHill()
   {
      for (Point ant : allAnts)
      {
         if (ant.inRange(Ants.getInstance().getMyHills(), 5).size() > 0)
         {
            hasNearHill = true;
            break;
         }

         if (ant.getType().isEnemy() && myAntsCount > enemyAntsCount &&
                 ant.inRange(Ants.getInstance().getEnemyHills(), 5).size() > 0)
         {
            hasNearHill = true;
            break;
         }
      }
   }

   private void resetScoresForCurrentMove()
   {
      minScoresForCurrMove = Double.MAX_VALUE;
      totalScoresForCurrMove = -1;
   }

   private double calcScores(List<Point> myAntsAlive, List<Point> enemyAntsAlive)
   {
      return localAttackMode.calcScores(myAntsAlive, enemyAntsAlive, scoresForExchange);
   }

   private static void calcAliveAntsByDamage(double[] damageTable, List<Point> ants,
                                             List<Point> ants1Alive)
   {
      List<Point> alive = new ArrayList<Point>();
      for (int i = 0; i < ants.size(); ++i)
      {
         Point ant = ants.get(i);
         if (damageTable[ant.tag] < 1.0)
         {
            alive.add(ant);
         }
      }

      ants1Alive.clear();
      ants1Alive.addAll(alive);
   }

   private static void calcAliveAntsByPowerX(List<Point> allAnts, PointType[] types,
                                             double[] powerTable,
                                            List<Point> myAntsAlive, List<Point> otherAntsAlive)
   {
      myAntsAlive.clear();
      otherAntsAlive.clear();
      A: for (int i = 0; i < allAnts.size(); ++i)
      {
         Point ant = allAnts.get(i);
         PointType type = types[ant.tag];
         double power = powerTable[ant.tag];

         for (int j = 0; j < allAnts.size(); ++j)
         {
            Point otherAnt = allAnts.get(j);
            if (!type.equals(types[otherAnt.tag]) &&
                    ant.squaredDistanceTo(otherAnt) <= attackRange)
            {
               double otherPower = powerTable[otherAnt.tag];
               if (power <= otherPower)
               {
                  continue A;
               }
            }
         }

         if (type.equals(PointType.MY_ANT))
         {
            myAntsAlive.add(ant);
         }
         else
         {
            otherAntsAlive.add(ant);
         }
      }
   }

   private void takeFood(List<Point> myAntsAlive, List<Point> otherAntsAlive,
                         Map<Point, PointType> afterToBeforeType)
   {
      Set<Point> bornAnts = new HashSet<Point>();
      for (Point ant : myAntsAlive)
      {
         Set<Point> foods = new HashSet<Point>(ant.inRange(Ants.getInstance().getFood(), 1, 1));
         for (Point food : foods)
         {
            afterToBeforeType.put(food, afterToBeforeType.get(ant));
         }
         bornAnts.addAll(foods);
      }
      myAntsAlive.addAll(bornAnts);
   }

   private int counter = 0;

   private void evaluatePosition()
   {
      counter++;
      List<Point> myAntsAfterMove = new ArrayList<Point>(myAntsCount + myMovedAnts.size());
      for (int i = 0; i < myAntsCount; ++i)
      {
         myAntsAfterMove.add(antsPositionsAfterMove[i]);
      }

      List<Point> enemyAntsAfterMove = new ArrayList<Point>(enemyAntsCount);
      for (int i = 0; i < enemyAntsCount; ++i)
      {
         enemyAntsAfterMove.add(antsPositionsAfterMove[myAntsCount + i]);
      }

      List<Point> myAntsAlive = new ArrayList<Point>();
      List<Point> enemyAntsAlive = new ArrayList<Point>();

      myAntsAfterMove.addAll(myMovedAnts);

      int totalMyAntsCount = myAntsAfterMove.size();

      Map<Point, PointType> afterToBeforeType = new HashMap<Point, PointType>();
      PointType[] types = new PointType[totalMyAntsCount + enemyAntsCount];
      for (int i = 0; i < totalMyAntsCount; ++i)
      {
         Point ant = myAntsAfterMove.get(i);
         ant.tag = i;
         types[ant.tag] = PointType.MY_ANT;
         if (hasNearFood)
         {
            afterToBeforeType.put(ant, PointType.MY_ANT);
         }

      }
      for (int i = 0; i < enemyAntsCount; ++i)
      {
         Point ant = enemyAntsAfterMove.get(i);
         ant.tag = totalMyAntsCount + i;
         types[ant.tag] = allAnts.get(myAntsCount + i).getType(MyBot.ants);
         if (hasNearFood)
         {
            afterToBeforeType.put(ant, types[ant.tag]);
         }
      }

      fight(myAntsAfterMove, enemyAntsAfterMove, types,
              myAntsAlive, enemyAntsAlive);

      if (hasNearFood)
      {
         takeFood(myAntsAlive, enemyAntsAlive, afterToBeforeType);
         takeFood(enemyAntsAlive, myAntsAlive, afterToBeforeType);

         types = new PointType[myAntsAlive.size() + enemyAntsAlive.size()];
         for (int i = 0; i < myAntsAlive.size(); ++i)
         {
            Point ant = myAntsAlive.get(i);
            ant.tag = i;
            types[ant.tag] = afterToBeforeType.get(ant);
         }
         for (int i = 0; i < enemyAntsAlive.size(); ++i)
         {
            Point ant = enemyAntsAlive.get(i);
            ant.tag = myAntsAlive.size() + i;
            types[ant.tag] = afterToBeforeType.get(ant);
         }

         fight(new ArrayList<Point>(myAntsAlive), new ArrayList<Point>(enemyAntsAlive),
                 types, myAntsAlive, enemyAntsAlive);
      }

      double scores = calcScores(myAntsAlive, enemyAntsAlive);
      if (scores < minScoresForCurrMove)
      {
         minScoresForCurrMove = scores;
      }
      totalScoresForCurrMove += scores;
   }

   @SuppressWarnings(value = "unchecked")
   public static void fight(List<Point> myAntsAfterMove, List<Point> enemyAntsAfterMove,
                            PointType[] types,
                            /* OUT */ List<Point> myAntsAlive, /* OUT */ List<Point> enemyAntsAlive)
   {
      if (attackMethod.equals(AttackMethod.Damage))
      {
         double[] damageTable = new double[types.length];

         makeDamageToPlayer2(damageTable, myAntsAfterMove, enemyAntsAfterMove);
         makeDamageToPlayer2(damageTable, enemyAntsAfterMove, myAntsAfterMove);

         calcAliveAntsByDamage(damageTable, myAntsAfterMove, myAntsAlive);
         calcAliveAntsByDamage(damageTable, enemyAntsAfterMove, enemyAntsAlive);
      }
      else
      {
         double[] powerTable = new double[types.length];
         List<Point> allAnts = new ArrayList<Point>();
         allAnts.addAll(myAntsAfterMove);
         allAnts.addAll(enemyAntsAfterMove);

         countPowerX(powerTable, types, allAnts);
         calcAliveAntsByPowerX(allAnts, types, powerTable, myAntsAlive, enemyAntsAlive);
      }
   }

   public double evaluateStartPosition()
   {
      for (int i = 0; i < allAnts.size(); ++i)
      {
         antsPositionsAfterMove[i] = allAnts.get(i);
      }

      resetScoresForCurrentMove();
      evaluatePosition();

      return minScoresForCurrMove;
   }

   public double getMinScoresForBestMove()
   {
      return minScoresForBestMove;
   }

   private static void makeDamageToPlayer2(/* OUT */ double[] damageTable,
                                    List<Point> p1AntsAfterMove, List<Point> p2AntsAfterMove)
   {
      for (int i = 0; i < p1AntsAfterMove.size(); ++i)
      {
         Point ant = p1AntsAfterMove.get(i);
         List<Point> enemies = ant.inSquaredDistance(p2AntsAfterMove, attackRange);
         double damageToOne = 1 / (double)enemies.size();
         for (int j = 0; j < enemies.size(); ++j)
         {
            damageTable[enemies.get(j).tag] += damageToOne;
         }
      }
   }

   private static void countPowerX(/* OUT */ double[] powerTable, PointType[] types,
                                   List<Point> allAnts)
   {
      for (int i = 0; i < allAnts.size(); ++i)
      {
         Point ant = allAnts.get(i);
         PointType type = types[ant.tag];
         int enemiesCount = 0;
         for (int j = 0; j < allAnts.size(); ++j)
         {
            Point otherAnt = allAnts.get(j);
            PointType otherType = types[otherAnt.tag];

            if (!type.equals(otherType))
            {
               if (ant.squaredDistanceTo(otherAnt) <= attackRange)
               {
                  enemiesCount++;
               }
            }
         }
         powerTable[ant.tag] = 1.0 / enemiesCount;
      }
   }

   private boolean contains(Point[] points, int endIndex, Point target)
   {
      boolean res = false;
      for (int i = 0; i < endIndex; ++i)
      {
         if (points[i].equals(target))
         {
            res = true;
            break;
         }
      }

      return res;
   }

   List<Direction> generateDirectionsOfMyAnt(Point myAnt, int antNumber)
   {
      Ants ants = Ants.getInstance();
      List<Point> hills = new ArrayList<Point>();
      hills.addAll(ants.getMyHills());
      hills.addAll(ants.getEnemyHills());

      Point nearestHill = null;
      if (hills.size() != 0)
      {
         nearestHill = myAnt.getNearest(myAnt.inRange(hills, 15), true);
      }

      if (nearestHill == null && myAntsCount == 1)
      {
         return directions;
      }

      List<Direction> res = new ArrayList<Direction>(directions);

      List<Point> myAnts = new ArrayList<Point>(myAntsCount);
      if (nearestHill == null)
      {
         for (int i = 0; i < antNumber; ++i)
         {
            myAnts.add(antsPositionsAfterMove[i]);
         }
         myAnts.addAll(allAnts.subList(antNumber, myAntsCount));
      }

      final Map<Object, Integer> dirToDist = new HashMap<Object, Integer>();
      final Object none = new Object();
      for (Direction d : new ArrayList<Direction>(res))
      {
         Point nextPos = d != null ? myAnt.plus(d) : myAnt;

         int sum = 0;
         if (nearestHill != null)
         {
            sum = nearestHill.distanceInCellsTo(nextPos);
         }
         else
         {
             sum = nextPos.sumDistance(myAnts);
         }

         dirToDist.put((d != null) ? d : none, sum);
      }

      Collections.sort(res, new Comparator<Direction>()
      {
         public int compare(Direction o1, Direction o2)
         {
            Integer sum1 = dirToDist.get(o1 != null ? o1 : none);
            Integer sum2 = dirToDist.get(o2 != null ? o2 : none);

            return sum1.compareTo(sum2);
         }
      });

      return res;
   }

   List<Direction> generateDirectionsOfEnemyAnt(Point enemyAnt)
   {
      return directions;
   }

   List<Direction> generateDirections(Point ant, int antNumber)
   {
      return antNumber < myAntsCount ?
              generateDirectionsOfMyAnt(ant,antNumber) : generateDirectionsOfEnemyAnt(ant);
   }

   private void generateAntMoves(int antNumber)
   {
      if (antNumber == allAnts.size())
      {
         evaluatePosition();
         return;
      }

      Point ant = allAnts.get(antNumber);

      List<Direction> sortedDirections = generateDirections(ant, antNumber);
      for (int i = 0; i < sortedDirections.size(); ++i)
      {
         Direction d = sortedDirections.get(i);
         Point newPos = d != null ? ant.plus(d) : ant;

         Ants ants = MyBot.ants;
         if (contains(antsPositionsAfterMove, antNumber, newPos) ||
             newPos.getType(ants).isWater() || newPos.getType(ants).isFood() ||
             destinations.contains(newPos) || newDestinationPoints.contains(newPos) ||
             (newPos.getType(ants).isMyAnt() && !allAnts.contains(newPos) &&
                         !newFreePoints.contains(newPos)))
         {
            continue;
         }

//         int newPosHash = newPos.newHashCode();
         antsPositionsAfterMove[antNumber] = newPos;
//         positionHashCode += newPosHash;

//         if (evaluatedPositions.contains(positionHashCode))
//         {
//            positionHashCode -= newPosHash;
//            continue;
//         }
//         else
//         {
//            evaluatedPositions.add(positionHashCode);
//         }

         currentMoves[antNumber] = d;

         generateAntMoves(antNumber + 1);

         if (antNumber + 1 == myAntsCount)
         {
            updateScores();
         }

//         positionHashCode -= newPosHash;
      }
   }

   private void updateScores()
   {
      if (minScoresForCurrMove > minScoresForBestMove
              ||
         (minScoresForCurrMove == minScoresForBestMove &&
          totalScoresForCurrMove > totalScoresForBestMove))
      {
         currentBestMoves = Arrays.copyOf(currentMoves, myAntsCount);

         minScoresForBestMove = minScoresForCurrMove;
         totalScoresForBestMove = totalScoresForCurrMove;
      }

      resetScoresForCurrentMove();
   }

   private int getMaxAntsToCountForRegular()
   {
      double timeUsed = Ants.getInstance().calcTimeUsed();
      int maxAntsToCalc = MAX_ANTS_TO_CALC_FOR_REGULAR_BATTLE;
      if (hasNearFood)
      {
         maxAntsToCalc -= 1;
      }
      if (timeUsed > 0.65)
      {
         maxAntsToCalc -= 1;
      }
      if (timeUsed > 0.8)
      {
         maxAntsToCalc -= 2;
      }
      if (timeUsed > 0.9)
      {
         maxAntsToCalc = 1;
      }
      return maxAntsToCalc;
   }

   public Map<Point, Direction> findBestMovesLocal()
   {
      int totalAntsCount = myAntsCount + enemyAntsCount;
      boolean skip = false;
      if (totalAntsCount > getMaxAntsToCountForRegular())
      {
         skip = true;
      }

      if (!skip)
      {
         Complexity complexity = new Complexity(totalAntsCount, hasNearFood);

         long timeLeft = Ants.getInstance().calcTimeLeft();
         long time = TimerHelper.getAverageTime(complexity);
//         if (time < 0)
//         {
//            time = maxTime * 5;
//         }
//         else if (maxTime < time)
//         {
//            maxTime = time;
//         }
         if (Ants.getInstance().isTestInstance() || timeLeft > 2 * time)
         {
            TimerHelper.start(complexity);

            resetScoresForCurrentMove();
//            evaluatedPositions = new IntSet(2*(int)Math.pow(5, allAnts.size()));
            generateAntMoves(0);

            if (myAntsCount == 0)
            {
               updateScores();
            }

            TimerHelper.stop(complexity);
         }
      }

      Map<Point, Direction> res = new HashMap<Point, Direction>();
      if (currentBestMoves != null)
      {
         for (int i = 0; i < myAntsCount; ++i)
         {
            res.put(allAnts.get(i), currentBestMoves[i]);
         }
      }

      return res;
   }

}
