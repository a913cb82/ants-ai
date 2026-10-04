import java.util.*;
import java.io.InputStream;

public class Ants
{
   private static int rows = 1000;
   private static int cols = 1000;
   private static Stack<Ants> instances = new Stack<Ants>();

   public static Ants getInstance()
   {
      return instances.peek();
   }

   public static void pushAnts(Ants ants)
   {
      instances.push(ants);
   }

   public static void popAnts()
   {
      instances.pop();
   }

   public static int getRows()
   {
      return rows;
   }

   public static int getColumns()
   {
      return cols;
   }

   public AttackMethod getAttackMethod()
   {
      return attackMethod;
   }

   private int turn = 0;
   private int turns = 0;
   private int loadTime = 3000;
   private int turnTime = 1000;
   private int viewSquaredRange = 77;
   private int attackRangeSquared = 5;
   private int spawnRadius = 0;
   private AttackMethod attackMethod = AttackMethod.Focus;
   private long startTurnTime;
   private boolean disableOutput;

   private PointType[][] map;
   private List<Point> antList = new ArrayList<Point>();
   private List<Point> foodList = new ArrayList<Point>();
   private List<Point> deadList = new ArrayList<Point>();

   private List<Point> myAnts = new ArrayList<Point>();
   private Map<Point, AntInfo> myAntsInfo = new HashMap<Point, AntInfo>();
   private Map<Point, AntInfo> myAntsInfoAfterMove = new HashMap<Point, AntInfo>();
   private int[] antsCountHistory;

   private List<Point> enemyAnts = new ArrayList<Point>();

   private List<Point> myHills = new ArrayList<Point>();
   private Map<Point, List<AntInfo>> hillsAntsMap = new HashMap<Point, List<AntInfo>>();

   private List<Point> enemyHills = new ArrayList<Point>();

   private List<Order> issuedOrders = new ArrayList<Order>();
   private List<Order> pendingOrders = new ArrayList<Order>();
   private Order lastPendingOrder;

   private boolean testInstance;

   public int getTurn()
   {
      return turn;
   }

   public int getTurns()
   {
      return turns;
   }

   public int getLoadTime()
   {
      return loadTime;
   }

   public int getTurnTime()
   {
      return turnTime;
   }

   public int getViewSquaredRange()
   {
      return viewSquaredRange;
   }

   public int getAttackRangeSquared()
   {
      return attackRangeSquared;
   }

   public int getSpawnRadius()
   {
      return spawnRadius;
   }

   public PointType[][] getMap()
   {
      return map;
   }

   private int getCurrentTurnDuration()
   {
      return (int)(System.currentTimeMillis() - startTurnTime);
   }

   public List<Order> getIssuedOrders()
   {
      return issuedOrders;
   }

   public Order getLastIssuedOrder()
   {
      return issuedOrders.size() > 0 ? issuedOrders.get(issuedOrders.size() - 1) : null;
   }

   public List<Order> getPendingOrders()
   {
      return pendingOrders;
   }

   public Map<Point, List<AntInfo>> getHillsAntsMap()
   {
      return hillsAntsMap;
   }

   public Order popLastPendingOrder()
   {
      Order res = lastPendingOrder;
      lastPendingOrder = null;
      return res;
   }

   public void setDisableOutput(boolean disableOutput)
   {
      this.disableOutput = disableOutput;
   }

   public boolean isTestInstance()
   {
      return testInstance;
   }

   public AntInfo getMyAntInfo(Point ant)
   {
      return myAntsInfo.get(ant);
   }

   public int[] getAntsCountHistory()
   {
      return antsCountHistory;
   }

   public Ants()
   {

   }

   public Ants(PointType[][] map)
   {
      this.map = map;
      rows = map.length;
      cols = map[0].length;
      turn = 1;
      turns = Integer.MAX_VALUE;

      for (int row = 0; row < rows; ++row)
      {
         for (int col = 0; col < cols; ++col)
         {
            Point p = Point.get(col, row);
            PointType type = map[row][col];
            if (type.isAnt())
            {
               if (type.isMyAnt())
               {
                  myAnts.add(p);
               }
               else
               {
                  enemyAnts.add(p);
               }
            }
            else if (type.isFood())
            {
               foodList.add(p);
            }
         }
      }

      pushAnts(this);
      for (Point myAnt : myAnts)
      {
         signalMyAntAdded(myAnt);
      }
      popAnts();

      startTurnTime = System.currentTimeMillis();
      antsCountHistory = new int[100];
      testInstance = true;
      BFSManager.initializeGame(this);
      MyBot.ants = this;
   }

   private void signalMyAntAdded(Point myAnt)
   {
      if (!myAntsInfo.containsKey(myAnt))
      {
         List<AntInfo> antsFromHill = hillsAntsMap.get(myAnt);
         if (antsFromHill == null)
         {
            antsFromHill = new ArrayList<AntInfo>();
            hillsAntsMap.put(myAnt, antsFromHill);
         }
         AntInfo antInfo = new AntInfo(myAnt);

         antsFromHill.add(antInfo);
         myAntsInfo.put(myAnt, antInfo);
      }
   }

   public boolean setup(List<String> data)
   {
      try
      {
         for (String line : data)
         {
            String tokens[] = line.toLowerCase().split(" ");
            if (tokens[0].equals("cols"))
            {
               cols = Integer.parseInt(tokens[1]);
            }
            else if (tokens[0].equals("rows"))
            {
               rows = Integer.parseInt(tokens[1]);
            }
            else if (tokens[0].equals("turns"))
            {
               turns = Integer.parseInt(tokens[1]);
            }
            else if (tokens[0].equals("loadtime"))
            {
               loadTime = Integer.parseInt(tokens[1]);
            }
            else if (tokens[0].equals("turntime"))
            {
               turnTime = Integer.parseInt(tokens[1]);
            }
            else if (tokens[0].equals("viewradius2"))
            {
               viewSquaredRange = Integer.parseInt(tokens[1]);
            }
            else if (tokens[0].equals("attackradius2"))
            {
               attackRangeSquared = Integer.parseInt(tokens[1]);
            }
            else if (tokens[0].equals("spawnradius2"))
            {
               spawnRadius = Integer.parseInt(tokens[1]);
            }
            else if (tokens[0].equals("turn"))
            {
            }
            else if (tokens[0].equals("player_seed"))
            {
            }
            else
            {
               //throw new RuntimeException(tokens[0]);
            }
         }
         map = new PointType[rows][cols];
         for (PointType[] row : map)
         {
            Arrays.fill(row, PointType.LAND);
         }

         antsCountHistory = new int[turns + 1];

         BFSManager.initializeGame(this);
         return true;
      }
      catch (Exception ex)
      {
         throw new RuntimeException(ex);
      }
   }

   private void updateStartTime()
   {
      startTurnTime = System.currentTimeMillis();
   }

   private boolean update(List<String> data)
   {
      // clear ants and getFood
      for (Point ant : this.antList)
      {
         map[ant.y][ant.x] = PointType.LAND;
      }
      antList.clear();
      for (Point food : this.foodList)
      {
         map[food.y][food.x] = PointType.LAND;
      }
      Set<Point> oldFood = new HashSet<Point>(foodList);
      foodList.clear();
      for (Point dead : this.deadList)
      {
         map[dead.y][dead.x] = PointType.LAND;
      }
      deadList.clear();
      myAnts.clear();
      myAntsInfoAfterMove = new HashMap<Point, AntInfo>();
      enemyAnts.clear();
      myHills.clear();

      Set<Point> oldEnemyHills = new HashSet<Point>(enemyHills);
      enemyHills.clear();

      // get new getPoint ilks
      for (String line : data)
      {
         String tokens[] = line.split(" ");
         if (tokens.length > 2)
         {
            int row = Integer.parseInt(tokens[1]);
            int col = Integer.parseInt(tokens[2]);
            if (tokens[0].equals("w"))
            {
               map[row][col] = PointType.WATER;
               BFSManager.signalNewWaterFound(Point.get(col, row));
            }
            else if (tokens[0].equals("a"))
            {
               PointType pointType = PointType.fromId(Integer.parseInt(tokens[3]));
               Point ant = Point.get(col, row);
               if (pointType == PointType.MY_ANT)
               {
                  myAnts.add(ant);
               }
               else if (pointType.isEnemy())
               {
                  enemyAnts.add(ant);
               }

               map[row][col] = pointType;
               antList.add(ant);
            }
            else if (tokens[0].equals("h"))
            {
               PointType pointType = PointType.fromId(Integer.parseInt(tokens[3]));
               Point hill = Point.get(col, row);
               if (pointType == PointType.MY_ANT)
               {
                  myHills.add(hill);
               }
               else if (pointType.isEnemy())
               {
                  enemyHills.add(hill);
               }

               antList.add(hill);
            }
            else if (tokens[0].equals("f"))
            {
               map[row][col] = PointType.FOOD;
               foodList.add(Point.get(col, row));
            }
            else if (tokens[0].equals("d"))
            {
               map[row][col] = PointType.DEAD;
               deadList.add(Point.get(col, row));
            }
         }
      }

      for (Point ant : myAnts)
      {
         signalMyAntAdded(ant);
      }

      oldFood.removeAll(foodList);
      for (Point food : oldFood)
      {
         if (food.inSquaredDistance(myAnts, viewSquaredRange).size() == 0)
         {
            foodList.add(food);
         }
      }
      for (Point hill : oldEnemyHills)
      {
         if (hill.inSquaredDistance(myAnts, viewSquaredRange).size() == 0)
         {
            enemyHills.add(hill);
         }
      }
      for (AntInfo info : myAntsInfo.values())
      {
         info.setAlive(true);
      }

      removeDeadAntsInfo();
      issuedOrders.clear();
      pendingOrders.clear();

      antsCountHistory[turn] = myAnts.size();

      return true;
   }

   private void removeDeadAntsInfo()
   {
      Set<Point> dead = new HashSet<Point>(myAntsInfo.keySet());
      dead.removeAll(myAnts);
      for (Point deadAnt : dead)
      {
         myAntsInfo.get(deadAnt).setAlive(false);
         myAntsInfo.remove(deadAnt);
      }
   }

   public double calcTimeUsed()
   {
      return (double) getCurrentTurnDuration() / turnTime;
   }

   public int calcTimeLeft()
   {
      return turnTime - getCurrentTurnDuration();
   }

   public void validateTurnDuration()
   {
      double timeUsed = calcTimeUsed();
      if (timeUsed > 0.9)
      {
         throw new NearToTimeoutException();
      }
   }

   private void updateAntInfoAfterMove(Point ant, Direction d)
   {
      AntInfo antInfo = myAntsInfo.get(ant);
      Point newPos = d != null ? ant.plus(d) : ant;
      antInfo.updatePosition(newPos);
      myAntsInfoAfterMove.put(newPos, antInfo);
   }

   public void issueOrder(Order order)
   {
      Point ant = order.getPoint();
      Direction direction = order.getDirection();
//      if (direction != null)
//      {
//         stopOnPoint(ant, 1, 17, 56);
//      }
      if (direction != null && !order.isPending() && !disableOutput)
      {
         String output = "o " + ant.y + " " + ant.x + " " + direction.symbol;
//         if (output.startsWith("o 71 41") && turn >= 209)
//         {
//            System.out.println();
//         }

         System.out.println(output);
         System.out.flush();
      }

      if (!order.isPending())
      {
         issuedOrders.add(order);
         updateAntInfoAfterMove(ant, direction);
      }
      else
      {
         pendingOrders.add(order);
         lastPendingOrder = order;
      }

      if (!disableOutput)
      {
         validateTurnDuration();
      }
   }

   public void issueAllPendingOrders()
   {
      for (Order o : pendingOrders)
      {
         o.setPending(false);
         issueOrder(o);
      }

      pendingOrders.clear();
   }

   private void stopOnPoint(Point ant, int turn, int row, int col)
   {
      if (this.turn == turn && ant.x == col && ant.y == row)
      {
         throw new RuntimeException("Stop!");
      }
   }

   public void finishTurn()
   {
      System.out.println("go");
      System.out.flush();
      this.turn++;

      myAntsInfo = myAntsInfoAfterMove;
   }

   public List<Point> getMyAnts()
   {
      return myAnts;
   }

   public List<Point> getEnemyAnts()
   {
      return enemyAnts;
   }

   public List<Point> getMyHills()
   {
      return myHills;
   }

   public List<Point> getEnemyHills()
   {
      return enemyHills;
   }

   public List<Point> getFood()
   {
      return this.foodList;
   }

   public PointType getPointType(Point location)
   {
      return this.map[location.y][location.x];
   }

   public static void run(MyBot bot, InputStream is)
   {
      Ants ants = new Ants();
      pushAnts(ants);
      StringBuilder line = new StringBuilder();
      ArrayList<String> data = new ArrayList<String>();
      int c;
      boolean firstInput = true;
      try
      {
         while ((c = is.read()) >= 0)
         {
            switch (c)
            {
               case '\n':
               case '\r':
                  if (line.length() > 0)
                  {
                     String full_line = line.toString();
                     if (full_line.equals("ready"))
                     {
                        ants.setup(data);
                        ants.finishTurn();
                        data.clear();
                     }
                     else if (full_line.equals("go"))
                     {
                        ants.update(data);
                        bot.doTurn(ants);
//                        if (Ants.getInstance().getTurn() > 148)
//                        {
//                           throw new RuntimeException("end");
//                        }
                        firstInput = true;
                        ants.finishTurn();
                        data.clear();
                     }
                     else
                     {
                        if (line.length() > 0)
                        {
                           data.add(full_line);
                        }
                     }
                     line = new StringBuilder();
                  }
                  break;
               default:
                  if (firstInput)
                  {
                     ants.updateStartTime();
                     firstInput = false;
                  }
                  line.append((char) c);
                  break;
            }
         }
      }
      catch (Exception e)
      {
         e.printStackTrace(System.err);
      }
   }

   public static void run(MyBot bot)
   {
      run(bot, System.in);
   }
}
