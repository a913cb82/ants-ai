import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Created by IntelliJ IDEA. User: GreenTea Date: 30.09.11 Time: 20:17 To change this template use
 * File | Settings | File Templates.
 */
public class AntInfo
{
   private final int pathStep = 10;

   private boolean alive = true;
   private Point homeHill;
   private Point currentPosition;
   private List<Point> positions = new ArrayList<Point>();
   private Set<Point> currentVisiblePoints;
   private Set<Point> uniquePositions = new HashSet<Point>();
   private Set<Point> goOutPoints = new HashSet<Point>();

   public AntInfo(Point homeHill)
   {
      this.homeHill = homeHill;
      currentPosition = homeHill;
   }

   public Point getCurrentPosition()
   {
      return currentPosition;
   }

   public List<Point> getPositions()
   {
      return positions;
   }

   public Set<Point> getGoOutPoints()
   {
      return goOutPoints;
   }

   public void setGoOutPoints(Set<Point> goOutPoints)
   {
      this.goOutPoints = goOutPoints;
   }

   public boolean isAlive()
   {
      return alive;
   }

   public void setAlive(boolean alive)
   {
      this.alive = alive;
   }

   public Set<Point> getCurrentVisiblePoints()
   {
      return currentVisiblePoints;
   }

   public void setCurrentVisiblePoints(Set<Point> currentVisiblePoints)
   {
      this.currentVisiblePoints = currentVisiblePoints;
   }

   public void markPathAsInteresting()
   {
      Set<Point> processedPoints = new HashSet<Point>();
      int positionsCount = positions.size();
      if (positionsCount > 0)
      {
         for (int i = 0; i < positionsCount; ++i)
         {
            Point p = positions.get(i);
            if (!processedPoints.contains(p))
            {
               double value = i / (double)positionsCount;
               value = value*value;
               BFSManager.decInvestigation(p, value);
               processedPoints.add(p);
            }
         }
      }
   }

   public void updatePosition(Point newPos)
   {
      positions.add(newPos);
      uniquePositions.add(newPos);
      currentPosition = newPos;
   }

}
