import java.util.Iterator;
import java.util.LinkedList;
import java.util.ListIterator;

/**
 * Created by IntelliJ IDEA. User: GreenTea Date: 02.12.11 Time: 19:44 To change this template use
 * File | Settings | File Templates.
 */
public class CellsPool
{
   private LinkedList<CellInfo> cellInfos = new LinkedList<CellInfo>();

   public void remove(CellInfo info)
   {
      cellInfos.remove(info);
   }

   public void add(CellInfo info)
   {
      if (cellInfos.size() == 0)
      {
         cellInfos.add(info);
         return;
      }

      ListIterator<CellInfo> i = cellInfos.listIterator(0);
      boolean added = false;
      while (i.hasNext())
      {
         CellInfo next = i.next();
         int cmp = info.compareTo(next);
         if (cmp < 0)
         {
            i.previous();
            i.add(info);
            added = true;
            break;
         }
      }

      if (!added)
      {
         i.add(info);
      }

   }

   public int size()
   {
      return cellInfos.size();
   }

   public CellInfo first()
   {
      CellInfo info = null;
      if (size() > 0)
      {
         info = cellInfos.iterator().next();
      }

      return info;
   }
}
