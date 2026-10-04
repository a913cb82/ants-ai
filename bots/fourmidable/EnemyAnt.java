import java.util.*;

public class EnemyAnt
{
  private static final int MAX_PREV_POS = 10;

  private Coord currentPos;
  private int   owner;
  private LinkedList<Coord> previousPosList = new LinkedList<Coord>();

  public EnemyAnt(int owner, Coord pos)
  {
    this.owner = owner;
    this.currentPos = pos;
  }

  public void move(Coord newPos)
  {
    previousPosList.add(currentPos);
    if(previousPosList.size()>MAX_PREV_POS) previousPosList.remove(0);
    currentPos = newPos;
  }

  public Coord getPos()
  {
    return currentPos;
  }

  public int getOwner()
  {
    return owner;
  }

  public List<Coord> getPrevPosList()
  {
    return previousPosList;
  }

  public boolean isStill(int threshold)
  {
    if (previousPosList.size() < threshold) return false;
    Iterator<Coord> iter = previousPosList.descendingIterator();
    for (int i = 0; i < threshold; ++i) if (!iter.next().equals(currentPos)) return false;
    return true;
  }

  public Coord getSameDirection(int threshold, Ants ants)
  {
    if (previousPosList.size() < threshold) return null;
    Aim direction = null;
    Coord prev = currentPos;
    Iterator<Coord> iter = previousPosList.descendingIterator();
    for(int i=0; i < threshold; ++i)
    {
      Coord c = iter.next();
      if(c.equals(prev)) return null;
      if(direction == null)
      {
        direction = prev.getDirection(c);
      }
      else
      {
        if(!direction.equals(prev.getDirection(c))) return null;
      }
      prev = c;
    }
    Coord predicted = currentPos.move(direction);
    return ants.getTile(predicted).isBlocked()? null : predicted;
  }

  public Coord getToggle(int threshold)
  {
    if (previousPosList.size() < threshold) return null;
    Coord toggle = null;
    boolean checkToggle = false;
    Iterator<Coord> iter = previousPosList.descendingIterator();
    for(int i=0; i < threshold; ++i)
    {
      Coord c = iter.next();
      if(toggle == null)
      {
        toggle = c;
      }
      else
      {
        Coord check = checkToggle ? toggle : currentPos;
        if(!check.equals(c)) return null;
        checkToggle = !checkToggle;
      }
    }
    return toggle;
  }

  public Coord getPredictedMove(Ants ants)
  {
    if (isStill(MyBot.STILL_THRESHOLD)) return currentPos;
    Coord predicted = getSameDirection(MyBot.SAME_DIR_THRESHOLD, ants);
    if (predicted != null) return predicted;
    return getToggle(MyBot.TOGGLE_THRESHOLD);
  }
}
