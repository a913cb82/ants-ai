import java.util.*;

/**
 * Represents a the coordinates of tile on the game map.
 */
public final class Coord
{
  public static int rows;
  public static int cols;
  public static int viewRadius2;
  public static int attackRadius2;
  public static int spawnRadius2;

  public final int row;
  public final int col;

  public static void init(int rows, int cols, int viewRadius2, int attackRadius2, int spawnRadius2)
  {
    Coord.rows          = rows;
    Coord.cols          = cols;
    Coord.viewRadius2   = viewRadius2;
    Coord.attackRadius2 = attackRadius2;
    Coord.spawnRadius2  = spawnRadius2;
  }

  /**
   * Creates new {@link Coord} object.
   * @param row row index
   * @param col column index
   */
  public Coord(int row, int col)
  {
    this.row = row;
    this.col = col;
  }

  public boolean equals(int r, int c)
  {
    return row == r && col == c;
  }

  public boolean equals(Coord other)
  {
    return other != null && row == other.row && col == other.col;
  }

  /**
   * {@inheritDoc}
   */
  @Override
  public int hashCode()
  {
    return row * Ants.MAX_MAP_SIZE + col;
  }

  /**
   * {@inheritDoc}
   */
  @Override
  public boolean equals(Object other)
  {
    return other instanceof Coord && row == ((Coord)other).row && col == ((Coord)other).col;
  }

  /**
   * {@inheritDoc}
   */
  @Override
  public String toString()
  {
    return row + " " + col;
  }

  public Coord smallOffset(int dr, int dc)
  {
    return new Coord(normalizeRow(row + dr), normalizeCol(col + dc));
  }

  public static int normalizeRow(int r)
  {
    if (r < 0) r += rows; else if (r >= rows) r -= rows;
    return r;
  }

  public static int normalizeCol(int c)
  {
    if (c < 0) c += cols; else if (c >= cols) c -= cols;
    return c;
  }

  public Coord getEast()
  {
    return new Coord(row, col + 1 == cols ? 0 : col + 1);
  }

  public Coord getNorth()
  {
    return new Coord(row == 0 ? rows - 1 : row - 1, col);
  }

  public Coord getWest()
  {
    return new Coord(row, col == 0 ? cols - 1 : col - 1);
  }

  public Coord getSouth()
  {
    return new Coord(row + 1 == rows ? 0 : row + 1, col);
  }

  public Aim getDirection(Coord other)
  {
    if (col == other.col)
    {
      return (row == 0 ? rows - 1 : row - 1) == other.row ? Aim.NORTH : Aim.SOUTH;
    }
    return (col + 1 == cols ? 0 : col + 1) == other.col ? Aim.EAST : Aim.WEST;
  }

  public Coord move(Aim aim)
  {
    switch(aim)
    {
    case EAST:  return getEast();
    case WEST:  return getWest();
    case NORTH: return getNorth();
    case SOUTH: return getSouth();
    }
    return null;
  }

  public int getDistance2(Coord other)
  {
    int dr = getRowDistance(other);
    int dc = getColDistance(other);
    return dr*dr + dc*dc;
  }

  /**
   * Positive if going down, negative if going up. Handles wrap-around.
   * @param other the destination
   * @return the number of rows to cross from this to other
   */
  public int getRowDistance(Coord other)
  {
    int dr = other.row - row;
    if (2*dr <= -rows) return dr + rows;
    if (2*dr >   rows) return dr - rows;
    return dr;
  }

  /**
   * Positive if going right, negative if going left. Handles wrap-around.
   * @param other the destination
   * @return the number of columns to cross from this to other
   */
  public int getColDistance(Coord other)
  {
    int dc = other.col - col;
    if (2*dc <= -cols) return dc + cols;
    if (2*dc >   cols) return dc - cols;
    return dc;
  }

  public int getDistanceOrthogonal(Coord other)
  {
    int dr = Math.abs(other.row - row);
    int dc = Math.abs(other.col - col);
    return Math.min(dr, rows - dr) + Math.min(dc,  cols - dc);
  }

  /**
   * Returns a list of all unblocked moves for this ant, including not moving.
   * Blocked destinations are excluded.
   * @param ants the world state
   * @return the list of available moves
   */
  public List<Coord> getMovesExcludingSleeping(Ants ants)
  {
    ArrayList<Coord> moves = new ArrayList<Coord>(5);
    Coord east = getEast();
    if (!ants.getTile(east).isBlocked()) moves.add(east);
    Coord north = getNorth();
    if (!ants.getTile(north).isBlocked()) moves.add(north);
    Coord west = getWest();
    if (!ants.getTile(west).isBlocked()) moves.add(west);
    Coord south = getSouth();
    if (!ants.getTile(south).isBlocked()) moves.add(south);
    return moves;
  }

  /**
   * Returns a list of all unblocked moves for this ant, including not moving.
   * Blocked destinations are excluded.
   * @param ants the world state
   * @return the list of available moves
   */
  public List<Coord> getMovesIncludingSleeping(Ants ants)
  {
    List<Coord> moves = getMovesExcludingSleeping(ants);
    moves.add(this);
    return moves;
  }
}
