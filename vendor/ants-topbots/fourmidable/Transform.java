import java.io.*;

public final class Transform implements Comparable<Transform>
{
  public static final int MAX_TYPE = 8;
  public static final int MAX_REGULAR_TYPE = 4;

  private static final int BASEMATRIX[][][] =
  {
    { { 1,  0 },
      { 0,  1 } },
    { { 1,  0 },
      { 0, -1 } },
    { {-1,  0 },
      { 0, -1 } },
    { {-1,  0 },
      { 0,  1 } },

    { { 0,  1 },
      { 1,  0 } },
    { { 0, -1 },
      { 1,  0 } },
    { { 0, -1 },
      {-1,  0 } },
    { { 0,  1 },
      {-1,  0 } }
  };

  private static final int MULTTYPE[][] =
  {
    { 0, 1, 2, 3, 4, 5, 6, 7 },
    { 1, 0, 3, 2, 7, 6, 5, 4 },
    { 2, 3, 0, 1, 6, 7, 4, 5 },
    { 3, 2, 1, 0, 5, 4, 7, 6 },
    { 4, 5, 6, 7, 0, 1, 2, 3 },
    { 5, 4, 7, 6, 3, 2, 1, 0 },
    { 6, 7, 4, 5, 2, 3, 0, 1 },
    { 7, 6, 5, 4, 1, 0, 3, 2 },
  };

  public static final Transform IDENTITY = new Transform(0,0,0);

  private int dx;
  private int dy;
  private int type;
  private int land;
  private int water;

  public Transform(int type, int dx, int dy)
  {
    this.type = type;
    this.dx   = dx;
    this.dy   = dy;
  }

  public void confirmLand()  { ++land; }
  public void confirmWater() { ++water; }
  public int evidence() { return Math.min(land,  water); }

  public Coord apply(Coord c)
  {
    int col = Coord.normalizeCol(BASEMATRIX[type][0][0]*c.col + BASEMATRIX[type][0][1]*c.row + dx);
    int row = Coord.normalizeRow(BASEMATRIX[type][1][0]*c.col + BASEMATRIX[type][1][1]*c.row + dy);
    return new Coord(row, col);
  }

  public Transform multiply(Transform other)
  {
    int restype = MULTTYPE[type][other.type];
    int m[][] = BASEMATRIX[type];
    int resdx = Coord.normalizeCol(m[0][0]*other.dx + m[0][1]*other.dy + dx);
    int resdy = Coord.normalizeRow(m[1][0]*other.dx + m[1][1]*other.dy + dy);
    return new Transform(restype, resdx, resdy);
  }

  @Override
  public int hashCode()
  {
    final int prime = 31;
    int result = 1;
    result = prime * result + dx;
    result = prime * result + dy;
    result = prime * result + type;
    return result;
  }

  @Override
  public boolean equals(Object o)
  {
    if(!(o instanceof Transform)) return false;
    Transform ot = (Transform)o;
    return type==ot.type && dx==ot.dx && dy==ot.dy;
  }

  @Override
  public int compareTo(Transform other)
  {
    int ret = type - other.type;
    if(ret == 0) ret = dx - other.dx;
    if(ret == 0) ret = dy - other.dy;
    return ret;
  }

  @Override
  public String toString()
  {
    return "type = " + type + " dx = " + dx + " dy = " + dy;
  }

  public void print(PrintStream stream)
  {
    int m[][] = BASEMATRIX[type];
    for(int i=0; i<2; ++i)
    {
      for(int j=0; j<2; ++j)
        stream.print(m[i][j]+" ");
      stream.println(i==0?dx:dy);
    }
  }

  public boolean isIdentity()
  {
    return type == 0 && dx == 0 && dy == 0;
  }
}
