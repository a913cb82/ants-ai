import java.util.Collection;
import java.util.List;

/**
 * Created by IntelliJ IDEA. User: GreenTea Date: 05.07.11 Time: 22:53 To change this template use
 * File | Settings | File Templates.
 */
public class DangerMoveValidator implements IMoveValidator
{
   private Collection<Point> notMovedAnts;
   private Collection<Point> enemies;
   public DangerMoveValidator(Collection<Point> notMovedAnts, Collection<Point> enemies)
   {
      this.notMovedAnts = notMovedAnts;
      this.enemies = enemies;
   }

   public boolean isValid(Point ant, Direction move)
   {
      return !BattleCalculator.isMoveDanger(ant, move,
              notMovedAnts, enemies);
   }
}
