/**
 * Created by IntelliJ IDEA. User: GreenTea Date: 23.07.11 Time: 19:20 To change this template use
 * File | Settings | File Templates.
 */
public class Order implements Comparable<Order>
{
   private Point point;
   private Direction direction;
   private Point target;
   private boolean pending;

   public Order(Point point, Direction direction, Point target)
   {
      this.point = point;
      this.direction = direction;
      this.target = target;
   }

   public Point getPoint()
   {
      return point;
   }

   public Direction getDirection()
   {
      return direction;
   }

   public boolean isPending()
   {
      return pending;
   }

   public void setPending(boolean pending)
   {
      this.pending = pending;
   }

   public Point getTarget()
   {
      return target;
   }

   public int compareTo(Order o)
   {
      int dx = Integer.valueOf(point.x).compareTo(o.point.x);
      int dy = Integer.valueOf(point.y).compareTo(o.point.y);
      return dy != 0 ? dy : dx;
   }

   @Override
   public String toString()
   {
      return point + " => " + direction;
   }

}
