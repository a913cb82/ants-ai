import java.io.*;
import java.util.*;

/**
 * Provides basic game state handling.
 */
public abstract class Bot
{
  private static final String  READY          = "ready";
  private static final String  GO             = "go";
  private static final String  END            = "end";
  private static final char    COMMENT_CHAR   = '#';

  private final List<String> input = new ArrayList<String>();
  protected     Ants         ants;

  /**
   * Reads system input stream line by line. All characters are converted to lower case and each line is passed for processing to
   * {@link #processLine(String)} method.
   * @throws IOException if an I/O error occurs
   * @throws TimeRunningOutException
   */
  public final void readSystemInput(InputStream stream) throws IOException
  {
    BufferedReader reader = new BufferedReader(new InputStreamReader(stream));
    for (;;)
    {
      String line = reader.readLine();
      if (line == null) break;
      doProcessLine(line);
      int commentCharIndex = line.indexOf(COMMENT_CHAR);
      if (commentCharIndex >= 0) line = line.substring(0, commentCharIndex);
      processLine(line.toLowerCase().trim());
    }
  }

  /**
   * Issues an order by sending it to the system output.
   * @param myAnt map tile with my ant
   * @param direction direction in which to move my ant
   */
  public final void issueOrder(Coord myAnt, Aim direction)
  {
    System.out.println("o " + myAnt.row + " " + myAnt.col + " " + direction.getSymbol());
  }

  /**
   * Collects lines read from system input stream until a keyword appears and then parses them.
   * @throws TimeRunningOutException
   */
  private void processLine(String line)
  {
    if (line.equals(READY))
    {
      parseSetup(input);
      input.clear();
      doSetup();
      finishTurn();
    }
    else if (line.equals(GO))
    {
      parseUpdate(input);
      input.clear();
      doTurn();
      finishTurn();
    }
    else if (line.equals(END))
    {
      input.clear();
      doEnd();
    }
    else if (!line.isEmpty())
    {
      input.add(line);
    }
  }

  /**
   * Parses the setup information from system input stream.
   * @param inputList setup information
   */
  private void parseSetup(List<String> inputList)
  {
    long start = System.currentTimeMillis();
    int  loadTime      = 0;
    int  turnTime      = 0;
    int  rows          = 0;
    int  cols          = 0;
    int  turns         = 0;
    int  viewRadius2   = 0;
    int  attackRadius2 = 0;
    int  spawnRadius2  = 0;
    long playerSeed    = 0;
    for (String line : inputList)
    {
      List<String> tokens = tokenize(line);
      if (tokens.size() == 2 && "loadtime".equals(tokens.get(0)))
      {
        loadTime = Integer.parseInt(tokens.get(1));
      }
      else if (tokens.size() == 2 && "turntime".equals(tokens.get(0)))
      {
        turnTime = Integer.parseInt(tokens.get(1));
      }
      else if (tokens.size() == 2 && "rows".equals(tokens.get(0)))
      {
        rows = Integer.parseInt(tokens.get(1));
      }
      else if (tokens.size() == 2 && "cols".equals(tokens.get(0)))
      {
        cols = Integer.parseInt(tokens.get(1));
      }
      else if (tokens.size() == 2 && "turns".equals(tokens.get(0)))
      {
        turns = Integer.parseInt(tokens.get(1));
      }
      else if (tokens.size() == 2 && "viewradius2".equals(tokens.get(0)))
      {
        viewRadius2 = Integer.parseInt(tokens.get(1));
      }
      else if (tokens.size() == 2 && "attackradius2".equals(tokens.get(0)))
      {
        attackRadius2 = Integer.parseInt(tokens.get(1));
      }
      else if (tokens.size() == 2 && "spawnradius2".equals(tokens.get(0)))
      {
        spawnRadius2 = Integer.parseInt(tokens.get(1));
      }
      else if (tokens.size() == 2 && "player_seed".equals(tokens.get(0)))
      {
        playerSeed = Long.parseLong(tokens.get(1));
      }
    }
    Coord.init(rows, cols, viewRadius2, attackRadius2, spawnRadius2);
    ants = new Ants(start, loadTime, turnTime, turns, playerSeed); // After Coord.init().
  }

  /**
   * Parses the update information from system input stream.
   * @param inputList update information
   */
  protected void parseUpdate(List<String> inputList)
  {
    ants.preUpdate();
    for (String line : inputList)
    {
      List<String> tokens = tokenize(line);
      if (tokens.size() == 3 && "w".equals(tokens.get(0)))
      {
        ants.observeWater(Integer.parseInt(tokens.get(1)), Integer.parseInt(tokens.get(2)));
      }
      else if (tokens.size() == 3 && "f".equals(tokens.get(0)))
      {
        ants.observeFood(Integer.parseInt(tokens.get(1)), Integer.parseInt(tokens.get(2)));
      }
      else if (tokens.size() == 4 && "a".equals(tokens.get(0)))
      {
        ants.observeAnt(Integer.parseInt(tokens.get(1)), Integer.parseInt(tokens.get(2)), Integer.parseInt(tokens.get(3)) + 1);
      }
      else if (tokens.size() == 4 && "d".equals(tokens.get(0)))
      {
        ants.observeDead(Integer.parseInt(tokens.get(1)), Integer.parseInt(tokens.get(2)), Integer.parseInt(tokens.get(3)) + 1);
      }
      else if (tokens.size() == 4 && "h".equals(tokens.get(0)))
      {
        ants.observeHill(Integer.parseInt(tokens.get(1)), Integer.parseInt(tokens.get(2)), Integer.parseInt(tokens.get(3)) + 1);
      }
    }
    ants.postUpdate();
  }

  private List<String> tokenize(String line)
  {
    List<String> list   = new ArrayList<String>(4);
    int          length = line.length();
    if (length == 0) return list;
    for (int i = 0;;)
    {
      while (i < length && Character.isWhitespace(line.charAt(i))) ++i;
      if (i >= length) return list;
      int j = i + 1;
      while (j < length && !Character.isWhitespace(line.charAt(j))) ++j;
      list.add(line.substring(i, j));
      i = j + 1;
    }
  }

  /**
   * Finishes turn.
   */
  private void finishTurn()
  {
    System.out.println("go");
    System.out.flush();
  }

  protected abstract void doProcessLine(String line);

  /**
   * Subclass use this method to peek at the input text before processing it.
   * @param input the game setup input
   */
  protected abstract void doSetup();

  /**
   * Subclasses are supposed to use this method to process the game state and send orders.
   * @param input the game turn input
   */
  protected abstract void doTurn();

  /**
   * Subclasses are supposed to use this method to cleanup at the end of the game.
   */
  protected abstract void doEnd();
}
