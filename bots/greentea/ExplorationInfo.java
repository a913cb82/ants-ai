/**
 * Created by IntelliJ IDEA. User: GreenTea Date: 15.10.11 Time: 14:56 To change this template use
 * File | Settings | File Templates.
 */
public class ExplorationInfo
{
   public Point target;
   public double minVisitValue;

   public ExplorationInfo(Point target, double minVisitValue)
   {
      this.target = target;
      this.minVisitValue = minVisitValue;
   }
}
