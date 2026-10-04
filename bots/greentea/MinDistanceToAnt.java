/**
 * Created by IntelliJ IDEA. User: GreenTea Date: 24.09.11 Time: 0:03 To change this template use
 * File | Settings | File Templates.
 */
public class MinDistanceToAnt implements IMoveValidator
{
   private Point targetAnt;
   private int minDistanceToAnt;

   public MinDistanceToAnt(Point targetAnt, int minDistanceToAnt)
   {
      this.targetAnt = targetAnt;
      this.minDistanceToAnt = minDistanceToAnt;
   }

   public boolean isValid(Point ant, Direction move)
   {
      Point newPos = move != null ? ant.plus(move) : ant;
      return targetAnt.distanceInCellsTo(newPos) > minDistanceToAnt;
   }
}
