import java.util.List;

/**
 * Created by IntelliJ IDEA. User: GreenTea Date: 07.06.11 Time: 0:12 To change this template use
 * File | Settings | File Templates.
 */
public class MinEnemiesCanAttack implements IMoveValidator
{
   private List<Point> enemies;
   private int canAttack;
   private int attackRange = Ants.getInstance().getAttackRangeSquared();

   public MinEnemiesCanAttack(List<Point> enemyAnts, int minAttacksCount)
   {
      this.enemies = enemyAnts;
      this.canAttack = minAttacksCount;
   }

   public boolean isValid(Point ant, Direction move)
   {
      return ant.plus(move).inSquaredDistance(enemies,
              attackRange, attackRange).size() <= canAttack;
   }
}
