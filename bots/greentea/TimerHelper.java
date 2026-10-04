import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Created by IntelliJ IDEA. User: GreenTea Date: 20.09.11 Time: 19:21 To change this template use
 * File | Settings | File Templates.
 */
public final class TimerHelper
{
   private static class TimeInfo
   {
      private long sum;
      private long max;
      private int count;

      public long getSum()
      {
         return sum;
      }

      public long getMax()
      {
         return max;
      }

      public int getCount()
      {
         return count;
      }

      public long getAverage()
      {
         return count > 0 ? (sum / count) : 0;
      }

      public void update(long newTime)
      {
         count++;
         sum += newTime;
         if (max < newTime)
         {
            max = newTime;
         }
      }
   }

   private TimerHelper()
   {

   }

   private static Map<Object, Long> startTimes = new HashMap<Object, Long>();
   private static Map<Object, TimeInfo> timesHistory = new HashMap<Object, TimeInfo>();

   public static void start(Object obj)
   {
      startTimes.put(obj, System.currentTimeMillis());
   }

   public static long stop(Object obj)
   {
      long res = System.currentTimeMillis() - startTimes.get(obj);
      startTimes.remove(obj);

      TimeInfo history = timesHistory.get(obj);
      if (history == null)
      {
         history = new TimeInfo();
         timesHistory.put(obj, history);
      }
      history.update(res);

      return res;
   }

   public static long getAverageTime(Object obj)
   {
      long res = -1;
      TimeInfo history = timesHistory.get(obj);
      if (history != null)
      {
         res = history.getAverage();
      }

      return res;
   }

   public static long getMaxTime(Object obj)
   {
      long res = -1;
      TimeInfo history = timesHistory.get(obj);
      if (history != null)
      {
         res = history.getMax();
      }

      return res;
   }
}
