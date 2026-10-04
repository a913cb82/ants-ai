/**
 * Created by IntelliJ IDEA. User: GreenTea Date: 11.08.11 Time: 1:15 To change this template use
 * File | Settings | File Templates.
 */
public class IntSet
{
   private int[] arr;

   public IntSet(int size)
   {
      arr = new int[size];
   }

   private int index(int value)
   {
      return Math.abs(value) % arr.length;
   }

   public void add(int value)
   {
      int i = index(value);
      while (true)
      {
         if (arr[i] == 0)
         {
            arr[i] = value;
            break;
         }
         else if (arr[i] != value)
         {
            i = (i + 1) % arr.length;
         }
      }
   }

   public boolean contains(int value)
   {
      int i = index(value);
      while (true)
      {
         if (arr[i] == 0)
         {
            return false;
         }
         else if (arr[i] == value)
         {
            return true;
         }
         else
         {
            i = (i + 1) % arr.length;
         }
      }
   }
}
