import java.util.*;

/**
 * Created by IntelliJ IDEA. User: GreenTea Date: 10.06.11 Time: 22:32 To change this template use
 * File | Settings | File Templates.
 */
public class Utils
{
   public static interface IPermutationFoundCallback
   {
      void permutationFound(int[] permutation);
   }

   public static PointType[][] parseMap(String[] mapStr)
   {
      PointType[][] res = new PointType[mapStr.length][(mapStr[0].length() + 1)/2];
      for (int i = 0; i < mapStr.length; ++i)
      {
         String line = mapStr[i];
         String[] cells = line.split(" ");
         for (int j = 0; j < cells.length; ++j)
         {
            res[i][j] = PointType.fromSymbol(cells[j].charAt(0));
         }
      }
      return res;
   }

   public static void printMap(PointType[][] map)
   {
      for (int i = 0; i < map.length; ++i)
      {
         StringBuilder line = new StringBuilder();
         PointType[] row = map[i];
         for (int j = 0; j < row.length; ++j)
         {
            line.append(row[j].symbol).append(" ");
         }
         System.out.println(line);
      }
   }

   public static <T> List<T> withoutLast(List<T> list)
   {
      List<T> res = new ArrayList<T>(list);
      if (res.size() > 0)
      {
         res.remove(res.size() - 1);
      }

      return res;
   }

   public static <T> boolean containsAny(Collection<T> targetCollection, Collection<T> elements)
   {
      for (T elem : elements)
      {
         if (targetCollection.contains(elem))
         {
            return true;
         }
      }

      return false;
   }

   public static <T> Set<T> intersection(Collection<T> c1, Collection<T> c2)
   {
      Set<T> res = new HashSet<T>(c1);
      if (!(c2 instanceof Set))
      {
         c2 = new HashSet<T>(c2);
      }

      res.retainAll(c2);

      return res;
   }

   public static int compareTo(Integer v11, Integer v12, Integer v21, Integer v22)
   {
      int res = v11.compareTo(v21);
      if (res == 0)
      {
         res = v12.compareTo(v22);
      }
      return res;
   }

   public static int compareTo(List<Integer> l1, List<Integer> l2)
   {
      if (l1.size() != l2.size())
      {
         throw new IllegalArgumentException("Size of lists should be same");
      }

      int res = 0;
      for (int i = 0; i < l1.size(); ++i)
      {
         res = l1.get(i).compareTo(l2.get(i));
         if (res != 0)
         {
            break;
         }
      }
      return res;
   }

   public static Point getPointOnPath(Point start, List<Direction> path, double pathPart)
   {
      if (path == null)
      {
         return null;
      }

      if (path.size() == 0)
      {
         return start;
      }

      int pointIndex = (int) (path.size() * pathPart);

      Point res = start;
      for (int i = 0; i <= pointIndex; ++i)
      {
         res = res.plus(path.get(i));
      }

      return res;
   }

   private static int[] nextPossibleValues(int[] res, int currentIndex)
   {
      boolean[] valueIsPresent = new boolean[res.length];
      for (int i = 0; i < currentIndex; ++i)
      {
         valueIsPresent[res[i]] = true;
      }

      int j = 0;
      int[] possibleValues = new int[res.length - currentIndex];
      for (int i = 0; i < res.length; ++i)
      {
         if (!valueIsPresent[i])
         {
            possibleValues[j++] = i;
         }
      }


      return possibleValues;
   }

   private static void generatePermutationsInternal(int[] res, int currentIndex,
                                           IPermutationFoundCallback callback)
   {
      if (currentIndex == res.length - 2)
      {
         int[] rest = nextPossibleValues(res, currentIndex);

         res[currentIndex] = rest[0];
         res[currentIndex + 1] = rest[1];

         callback.permutationFound(res);

         res[currentIndex] = rest[1];
         res[currentIndex + 1] = rest[0];
         callback.permutationFound(res);

         return;
      }

      int[] nextPossible = nextPossibleValues(res, currentIndex);
      for (int i = 0; i < nextPossible.length; ++i)
      {
         res[currentIndex] = nextPossible[i];
         generatePermutationsInternal(res, currentIndex + 1, callback);
      }
   }

   public static void generatePermutations(int size, IPermutationFoundCallback callback)
   {
      int[] res = new int[size];
      generatePermutationsInternal(res, 0, callback);
   }

}
