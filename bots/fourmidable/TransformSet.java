import java.util.*;

public final class TransformSet extends TreeSet<Transform> implements Comparable<TransformSet>
{
  public TransformSet()
  {
    add(Transform.IDENTITY);
  }

  public TransformSet(Transform init)
  {
    this();
    add(init);
  }

  public TransformSet(Collection<Transform> other)
  {
    super(other);
  }

  public List<Coord> apply(Coord c)
  {
    List<Coord> list = new ArrayList<Coord>(size()-1);
    for (Transform t : this)
    {
      if (!t.isIdentity())
      {
        list.add(t.apply(c));
      }
    }
    return list;
  }

  @Override
  public int compareTo(TransformSet other)
  {
    int r1 = size() - other.size();
    if (r1 != 0) return r1;

    Iterator<Transform> it      = descendingIterator();
    Iterator<Transform> otherit = other.descendingIterator();
    while (it.hasNext())
    {
      int r2 = it.next().compareTo(otherit.next());
      if( r2 != 0) return r2;
    }
    return 0;
  }

  public TransformSet merge(TransformSet other)
  {
    TransformSet res = new TransformSet(this);
    for (Transform t : other)
    {
      res.add(t);
      for (Transform t2 : this)
      {
        res.add(t2.multiply(t));
        res.add(t.multiply(t2));
      }
    }
    return res;
  }

  public boolean isClosed()
  {
    for (Transform t : this)
    {
      for (Transform t2 : this)
      {
        Transform t3 = t.multiply(t2);
        if (!contains(t3))
        {
          return false;
        }
      }
    }
    return true;
  }
}
