import java.util.EnumSet;
import java.util.HashMap;
import java.util.Map;

public enum PointType
{
   PATH(-10, 'x'),
   UNSEEN(-5, '?'),
   WATER(-4, '%'),
   FOOD(-3, '*'),
   LAND(-2, '.'),
   DEAD(-1, '!'),
   MY_ANT(0, 'A'),
   PLAYER1(1, 'B'),
   PLAYER2(2, 'C'),
   PLAYER3(3, 'D'),
   PLAYER4(4, 'E'),
   PLAYER5(5, 'F'),
   PLAYER6(6, 'G'),
   PLAYER7(7, 'H'),
   PLAYER8(8, 'I'),
   PLAYER9(9, 'J'),
   PLAYER10(10, 'K'),
   PLAYER11(11, 'L'),
   PLAYER12(12, 'M'),
   PLAYER13(13, 'N'),
   PLAYER14(14, 'O'),
   PLAYER15(15, 'P'),
   PLAYER16(16, 'Q'),
   PLAYER17(17, 'R'),
   PLAYER18(18, 'S'),
   PLAYER19(19, 'T'),
   PLAYER20(20, 'U'),
   PLAYER21(21, 'V'),
   PLAYER22(22, 'W'),
   PLAYER23(23, 'X'),
   PLAYER24(24, 'Y'),
   PLAYER25(25, 'Z');

   private static final Map<Integer, PointType> idLookup = new HashMap<Integer, PointType>();
   private static final Map<Character, PointType> symbolLookup = new HashMap<Character, PointType>();

   static
   {
      for (PointType i : EnumSet.allOf(PointType.class))
      {
         idLookup.put(i.id, i);
         symbolLookup.put(i.symbol, i);
      }
   }

   public final int id;
   public final char symbol;

   private PointType(int id, char symbol)
   {
      this.id = id;
      this.symbol = symbol;
   }

   public boolean isAnt()
   {
      return this.id >= MY_ANT.id;
   }

   public boolean isMyAnt()
   {
      return this.id == MY_ANT.id;
   }

   public boolean isEnemy()
   {
      return this.id > MY_ANT.id;
   }

   public boolean isPassable()
   {
      return this.id > WATER.id;
   }

   public boolean isLand()
   {
      return this.id == LAND.id;
   }

   public boolean isWater()
   {
      return this.id == WATER.id;
   }

   public boolean isUnoccupied()
   {
      return this.id == LAND.id || this.id == DEAD.id;
   }

   public boolean isEnemyOf(PointType ant)
   {
      return this.id >= MY_ANT.id && this.id != ant.id;
   }

   public boolean isFood()
   {
      return this.id == FOOD.id;
   }

   public static PointType fromId(int id)
   {
      return idLookup.get(id);
   }

   public static PointType fromSymbol(char symbol)
   {
      return symbolLookup.get(symbol);
   }
}
