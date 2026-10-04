import java.util.ArrayList;
import java.util.List;

/**
 * Created by IntelliJ IDEA. User: GreenTea Date: 27.09.11 Time: 21:18 To change this template use
 * File | Settings | File Templates.
 */
public class MoveTask
{
   private int startTurn;
   private int endTurn;
   private List<Direction> pathDirections;
   private List<Point> path;
   private Point target;

   public MoveTask(int startTurn, int turnsCount, Point startPoint, List<Direction> pathDirections)
   {
      this.startTurn = startTurn;
      this.endTurn = startTurn + turnsCount;
      this.pathDirections = pathDirections;

      path = new ArrayList<Point>(pathDirections.size());
      Point current = startPoint;
      for (Direction d : pathDirections)
      {
         path.add(current);
         current = current.plus(d);
      }

      target = current;
   }

   public int getPointIndexOnPath(Point ant)
   {
      return path.indexOf(ant);
   }

   public boolean isPathFree()
   {
      boolean res = true;
      for (Point p : path)
      {
         if (p.getType().isWater())
         {
            res = false;
            break;
         }
      }

      return res;
   }

   public MoveTask createNewTask(Point ant)
   {
      List<Direction> newPath = ant.findShortestPath(target);
      MoveTask res = null;
      if (newPath != null)
      {
         int turn = Ants.getInstance().getTurn();
         int turnsLeft = endTurn - turn;
         res = new MoveTask(turn, turnsLeft, ant, newPath);
      }
      return res;
   }

   public boolean isFinished(Point ant, int turn)
   {
      return ant.equals(target) ||
              turn > endTurn || (turn - startTurn) > (pathDirections.size() - 1);
   }

   public Direction getNextDirection(int currentPosIndex)
   {
      return pathDirections.get(currentPosIndex);
   }

   public Point getNextSubTarget(Point ant, int posIndex, int turnsForward)
   {
      if (posIndex < 0)
      {
         Point nearest = ant.getNearest(path, true);
         posIndex = getPointIndexOnPath(nearest);
      }

      int nextPosIndex = Math.min(posIndex + turnsForward, path.size() - 1);
      return path.get(nextPosIndex);
   }





}
