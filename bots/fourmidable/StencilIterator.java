import java.util.*;


public final class StencilIterator
{
  private static class RadiusMove
  {
    public RadiusMove(int radius2, int moves)
    {
      super();
      this.radius2 = radius2;
      this.moves = moves;
    }

    @Override
    public int hashCode()
    {
      final int prime = 31;
      int result = 1;
      result = prime * result + moves;
      result = prime * result + radius2;
      return result;
    }

    @Override
    public boolean equals(Object obj)
    {
      if (this == obj) return true;
      if (obj == null) return false;
      if (getClass() != obj.getClass()) return false;
      RadiusMove other = (RadiusMove) obj;
      if (moves != other.moves) return false;
      if (radius2 != other.radius2) return false;
      return true;
    }

    private int radius2;
    private int moves;
  }

  // No synchronization as we are single threaded.
  private static HashMap<RadiusMove, int[]> cache = new HashMap<RadiusMove, int[]>();

  private int[] stencil; // One quarter of the stencil shape. For each row -> half row length.
  private Coord center;
  private int   dr;
  private int   dc;

  /**
   * Iterator through coordinates around a center comprising a circle
   * with augmented by a number or orthogonal squares.
   * Handles wrap-around.
   * Assumption: sqrt(radius2) + moves < min(rows, cols)
   * @param center the center
   * @param radius2 the radius of the circle
   * @param moves the number of additional steps outside the circle
   */
  public StencilIterator(Coord center, int radius2, int moves)
  {
    RadiusMove key = new RadiusMove(radius2, moves);
    stencil        = cache.get(key);
    if (stencil == null)
    {
      // Compute the radius
      int radius = 1;
      while (radius*radius <= radius2) ++radius;
      --radius;
      stencil = new int[radius + moves + 1];

      // Fill-in the values
      for (int i = 0; i < stencil.length; ++i)
      {
        for (int j = 0; j < stencil.length; ++j)
        {
          int dx = j;
          int dy = i;
          int z  = moves;
          while (z-- > 0)
          {
            // Move toward the diagonal
            if (dx >= dy)
            {
              dx = Math.max(0,  dx - 1);
            }
            else if (dy > 0)
            {
              dy = Math.max(0,  dy - 1);
            }
          }

          // Remember if inside the radius
          if (dx*dx + dy*dy > radius2) break; // j
          stencil[i] = j;
        }
      }

      // Remember in cache
      cache.put(key,  stencil);
    }

    // Initialize iteration
    this.center = center;
    this.dr     = 1 - stencil.length;
    this.dc     = -stencil[-dr];
  }

  public boolean hasNext()
  {
    return dr < stencil.length;
  }

  public Coord next()
  {
    // Slightly obfuscated but nice nonetheless.
    Coord result = center.smallOffset(dr, dc);
    if (++dc > stencil[Math.abs(dr)] && ++dr < stencil.length) dc = -stencil[Math.abs(dr)];
    return result;
  }

  public boolean contains(Coord coord)
  {
    int dr = Math.abs(center.row - coord.row);
    dr     = Math.min(dr, Coord.rows - dr);
    if (dr >= stencil.length) return false;
    int dc = Math.abs(center.col - coord.col);
    dc     = Math.min(dc, Coord.cols - dc);
    return dc <= stencil[dr];
  }

  /**
   * @param args
   */
  public static void main(String[] args)
  {
    // Unit test.
    Coord.rows = 100;
    Coord.cols = 100;
    int i = 0;
    for (StencilIterator iter = new StencilIterator(new Coord(10, 10), 77, 0); iter.hasNext();)
    {
      Coord c = iter.next();
      System.out.println(++i + ": " + c + " " + iter.contains(c));
    }
  }
}
