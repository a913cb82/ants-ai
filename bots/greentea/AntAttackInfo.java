import java.util.List;

/**
* Created by IntelliJ IDEA. User: GreenTea Date: 30.09.11 Time: 21:08 To change this template use
* File | Settings | File Templates.
*/
class AntAttackInfo implements Comparable<AntAttackInfo>
{
   public Point ant;
   public List<Point> enemyAnts;
   public Point nearest;
   public int distanceToNearest;

   AntAttackInfo(Point ant, List<Point> enemyAnts, Point nearest, int distanceToNearest)
   {
      this.ant = ant;
      this.enemyAnts = enemyAnts;
      this.nearest = nearest;
      this.distanceToNearest = distanceToNearest;
   }

   public int compareTo(AntAttackInfo o)
   {
      if (distanceToNearest < o.distanceToNearest)
      {
         return -1;
      }
      else if (distanceToNearest > o.distanceToNearest)
      {
         return 1;
      }
      return 0;
   }
}
