/**
 * Created by IntelliJ IDEA. User: GreenTea Date: 01.06.11 Time: 0:50 To change this template use
 * File | Settings | File Templates.
 */
public class Vector
{
   public static Vector fromAngleAndLength(double angle, double length)
   {
      double angleInRadians = Math.toRadians(angle);
      double x = length * Math.cos(angleInRadians);
      double y = length * Math.sin(angleInRadians);

      return new Vector((int)x, (int)y);
   }

   public final int dx;
   public final int dy;

   public Vector(Direction d)
   {
      dx = d.dx;
      dy = d.dy;
   }

   public Vector(int dx, int dy)
   {
      this.dx = dx;
      this.dy = dy;
   }

   public Vector(Point p1, Point p2)
   {
      int dX = p2.x - p1.x;
      if (2*Math.abs(dX) > Ants.getColumns())
      {
         if (dX < 0)
         {
            dX += Ants.getColumns();
         }
         else
         {
            dX -= Ants.getColumns();
         }
      }

      int dY = p2.y - p1.y;
      if (2*Math.abs(dY) > Ants.getRows())
      {
         if (dY < 0)
         {
            dY += Ants.getRows();
         }
         else
         {
            dY -= Ants.getRows();
         }
      }

      dx = dX;
      dy = dY;
   }

   public Vector plus(Vector other)
   {
      return new Vector(dx + other.dx, dy + other.dy);
   }

   public int length()
   {
      return (int)Math.sqrt(dx*dx + dy*dy);
   }

   public boolean isZero()
   {
      return dx == 0 && dy == 0;
   }

   public Vector withLength(double size)
   {
      int thisLen = length();
      if (thisLen == 0)
      {
         return new Vector(0, 0);
      }

      double m = (double)size / (double)thisLen;
      int dX = (int) (dx * m);
      int dY = (int) (dy * m);

      return new Vector(dX, dY);
   }

   public Vector negate()
   {
      return new Vector(-dx, -dy);
   }

      /**
    * @return angle of vector in degrees in range [0, 360)
    */
   public double angle()
   {
      double z = Math.sqrt(dx*dx + dy*dy);
      double sin = dy / z;
      double asin = Math.asin(sin);

      double resAngle = 0;
      if (dx >= 0 && dy >= 0) // 1 quarter
      {
         resAngle = asin;
      }
      else if (dx < 0) // 2, 3 quarters
      {
         resAngle = Math.PI - asin;
      }
      else // 4 quarter
      {
         resAngle = 2*Math.PI + asin;
      }

      return (180 / Math.PI) * resAngle;
   }

   public Vector rotate(double dAngle)
   {
      double newAngle = angle() + dAngle;
      return fromAngleAndLength(newAngle, length());
   }
}
