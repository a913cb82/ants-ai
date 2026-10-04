import java.util.*;

/**
 * MultiSet is a {@link Collection} similar to a {@link Set}, but which allows
 * multiple instances of the same element. While this is also allowed in
 * a {@link List}, MultiSet is optimized to provide fast access to
 * specific instancea in the collection.
 * @param <E> the type of element in the MultiSet
 */
public final class MultiSet<E> extends AbstractCollection<E>
{
  protected transient int magic = 0;
  private int             size  = 0;
  private Map<E, Integer> map   = new HashMap<E, Integer>();

  private class MultiSetIterator implements Iterator<E>
  {
    private int                             iterMagic   = magic;
    private int                             count       = 0;
    private boolean                         removable   = false;
    private Iterator<Map.Entry<E, Integer>> mapIterator = map.entrySet().iterator();
    private Map.Entry<E, Integer>           entry       = null;

    /**
     * {@inheritDoc}
     */
    @Override
    public boolean hasNext()
    {
      if (iterMagic != magic) throw new ConcurrentModificationException();
      return mapIterator.hasNext() || count > 0;
    }

    /**
     * {@inheritDoc}
     * @throws ConcurrentModificationException
     * @throws NoSuchElementException
     */
    @Override
    public E next()
    {
      if (iterMagic != magic) throw new ConcurrentModificationException();
      if (count == 0)
      {
        if (!mapIterator.hasNext()) throw new NoSuchElementException();
        entry = mapIterator.next();
        count = entry.getValue().intValue();
      }
      removable = true;
      --count;
      return entry.getKey();
    }

    /**
     * {@inheritDoc}
     * @throws ConcurrentModificationException
     * @throws IllegalStateException
     */
    @Override
    public void remove()
    {
      if (iterMagic != magic) throw new ConcurrentModificationException();
      if (!removable) throw new IllegalStateException();
      --size;
      removable = false;
      int count = entry.getValue().intValue();
      if (count == 1)
      {
        mapIterator.remove();
      }
      else
      {
        entry.setValue(Integer.valueOf(count - 1));
      }
    }
  }

  /******************************
   * Collection Implementation. *
   ******************************/

  /**
   * Construct an empty multiset.
   */
  public MultiSet()
  {
  }

  /**
   * Construct a multiset. The multiset is initialized with the elements from the collection.
   */
  public MultiSet(Collection<E> collection)
  {
    this();
    addAll(collection);
  }

  /**
   * {@inheritDoc}
   */
  @Override
  public Iterator<E> iterator()
  {
    return new MultiSetIterator();
  }

  /**
   * {@inheritDoc}
   */
  @Override
  public int size()
  {
    return size;
  }

  /**
   * {@inheritDoc}
   */
  @Override
  public void clear()
  {
    ++magic;
    size = 0;
    map.clear();
  }

  /**
   * {@inheritDoc}
   */
  @Override
  public boolean add(E element)
  {
    add(element, 1);
    return true;
  }

  /**
   * {@inheritDoc}
   */
  @Override
  public boolean remove(Object element)
  {
    return remove(element, 1) > 0;
  }

  /**
   * {@inheritDoc}
   */
  @Override
  public boolean removeAll(Collection<?> collection)
  {
    int removed = 0;
    for (Object o : collection) removed += remove(o, 1);
    return removed > 0;
  }

  /**
   * {@inheritDoc}
   */
  @Override
  public boolean contains(Object element)
  {
    return map.containsKey(element);
  }

  /*************************************
   * MultiSet specific implementation. *
   *************************************/

  /**
   * Add multiple instances of a single element.
   * @param element element to be added
   * @param count number of instances to be added
   * @throws IllegalArgumentException
   */
  public void add(E element, int count)
  {
    if (count <= 0) throw new IllegalArgumentException();
    ++magic;
    size += count;
    map.put(element, Integer.valueOf(count(element) + count));
  }

  /**
   * Remove multiple instance of an element from the multiset.
   * If removing more instances then contained, then all
   * contained instances are removed.
   * @param element the element to be removed
   * @param count the number of instance to be removed
   * @return the number of instance actually removed.
   */
  @SuppressWarnings("unchecked")
  public int remove(Object element, int count)
  {
    Integer value = map.remove(element);
    if (value == null) return 0;
    ++magic;
    int current = value.intValue();
    int result  = current - count;
    if (result <= 0)
    {
      size -= current;
      return current;
    }
    size -= count;
    map.put((E)element, Integer.valueOf(result));
    return count;
  }

  /**
   * Returns the number of instances of the object in the multiset
   * @param element element to be counted
   * @return the number of instances, zero if absent
   */
  public int count(Object element)
  {
    Integer value = map.get(element);
    return value == null ? 0 : value.intValue();
  }

  /**
   * Return an iterator through each unique element in the multiset.
   * Repeated instances are returned only once.
   * @return the iterator
   */
  public Iterator<E> uniqueIterator()
  {
    return map.keySet().iterator();
  }

  /**
   * Return a set of unique elements in the multiset.
   * Repeated elements are present only once in the set.
   * @return the set
   */
  public Set<E> unique()
  {
    return map.keySet();
  }
}
