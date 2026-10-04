import java.util.*;

/**
 * This class implements the generic Collection contract. In addition,
 * it allows access to the smallest element in the collection,
 * based on the element natural order or a provided comparator.
 * Modification to the collection have O(log(n)) complexity.
 */
public final class Heap<E> extends AbstractCollection<E>
{
  protected transient int             magic = 0;
  private final ArrayList<E>          list  = new ArrayList<E>();
  private final Comparator<? super E> comparator;

  private class HeapIterator implements Iterator<E>
  {
    private int index     = 0;
    private int last      = -1;
    private int iterMagic = magic;

    @Override
    public boolean hasNext()
    {
      if (iterMagic != magic) throw new ConcurrentModificationException();
      return index < size();
    }

    @Override
    public E next()
    {
      if (iterMagic != magic) throw new ConcurrentModificationException();
      if (index >= size()) throw new NoSuchElementException();
      last = index++;
      return list.get(last);
    }

    @Override
    public void remove()
    {
      if (iterMagic != magic) throw new ConcurrentModificationException();
      if (last < 0) throw new IllegalStateException();
      Heap.this.remove(last);
      index = last;
      last  = -1;
    }
  }

  @SuppressWarnings("unchecked")
  private int compare(E o1, E o2)
  {
    return comparator != null ? comparator.compare(o1, o2) : ((Comparable<? super E>)o1).compareTo(o2);
  }

  private E remove(int i)
  {
    int last = size() - 1;
    if (i == last) return list.remove(i);
    E ei     = list.remove(last);
    E result = list.set(i, ei);
    for (;;)
    {
      int j = i + i + 1;
      if (j >= last) break;
      E ej = list.get(j);
      int j1 = j + 1;
      if (j1 < last)
      {
        E ej1 = list.get(j1);
        if (compare(ej, ej1) > 0) // 'j' belongs after 'j+1'
        {
          j  = j1;
          ej = ej1;
        }
      }
      if (compare(ei, ej) <= 0) break; // Proper order
      list.set(i, ej); // Swap 'i' and 'j'
      list.set(j, ei);
      i = j;
    }
    return result;
  }

  /****************
   * PUBLIC STUFF *
   ****************/

  /**
   * Construct an empty heap using the element natural order.
   */
  public Heap()
  {
    this((Comparator<? super E>)null);
  }

  /**
   * Construct a heap using the element natural order.
   * The heap is initialized with the elements from the collection.
   */
  public Heap(Collection<E> collection)
  {
    this((Comparator<? super E>)null);
    addAll(collection);
  }

  /**
   * Construct a heap using the provided comparator.
   * The heap is initialized with the elements from the collection.
   */
  public Heap(Collection<E> collection, Comparator<? super E> comparator)
  {
    this(comparator);
    addAll(collection);
  }

  /**
   * Construct an empty heap using the provided comparator.
   */
  public Heap(Comparator<? super E> comparator)
  {
    super();
    this.comparator = comparator;
  }

  /**
   * {@inheritDoc}
   */
  @Override
  public int size()
  {
    return list.size();
  }

  /**
   * {@inheritDoc}
   */
  @Override
  public Iterator<E> iterator()
  {
    return new HeapIterator();
  }

  /**
   * {@inheritDoc}
   */
  @Override
  public boolean add(E element)
  {
    ++magic;
    list.add(element);
    for (int i = size() - 1; i != 0;)
    {
      int j  = (i - 1) >> 1;
      E   ej = list.get(j);
      if (compare(ej, element) <= 0) break;; // Proper order
      list.set(i, ej); // Swap 'i' and 'j'
      list.set(j, element);
      i = j;
    }
    return true;
  }

  /**
   * Remove and return the smallest element from the collection,
   * based on the natural order or the provided comparator.
   * @return the smallest element
   */
  public E removeFirst()
  {
    if (isEmpty()) throw new NoSuchElementException();
    ++magic;
    return remove(0);
  }

  /**
   * Unit test.
   * @param args not used
   */
  public static void main(String[] args)
  {
    try
    {
      int    m      = 100;
      int    n      = 1000;
      Random random = new Random();
      int[]  values = new int[n];
      for (int i = 0; i < n; ++i) values[i] = random.nextInt(m);
      Heap<Integer> heap = new Heap<Integer>();
      for (int i : values) heap.add(Integer.valueOf(i));
      System.out.println("heap.size() = " + heap.size());
      Arrays.sort(values);
      int i = 0;
      while (!heap.isEmpty())
      {
        int v1 = values[i++];
        int v2 = heap.removeFirst().intValue();
        if (v1 != v2) throw new Exception(v1 + " mistmatch " + v2 + " at position " + i);
      }
      if (i != n) throw new Exception("Unexpected stop at position " + i);
      System.out.println("Test completed successfully!");
    }
    catch (Exception e)
    {
      e.printStackTrace();
    }
  }
}
