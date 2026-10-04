import java.util.*;

/**
 * See https://github.com/j-h-a/aichallenge/blob/vis_overlay/VIS_OVERLAY.md for the overlay grammar.
 */
public final class Overlay
{
  public enum Type
  {
    ENEMYANT,
    FEATURES,
    BATTLE,
    FOOD,
    HUNT,
    VISIT,
    ATTACK,
    IDLE,
    INFER
  }
  public enum LineColor
  {
    BLACK("v slc 0 0 0 1"),
    RED  ("v slc 255 0 0 1"),
    GREEN("v slc 0 255 0 1"),
    BLUE ("v slc 0 0 255 1"),
    YELLOW("v slc 255 255 0 1"),
    MAGENTA("v slc 255 0 255 1"),
    CYAN("v slc 0 255 255 1"),
    WHITE("v slc 255 255 255 1");

    private String command;
    LineColor(String command) { this.command = command; }
    public void println() { System.out.println(command); }
  }

  public enum FillColor
  {
    BLACK("v sfc 0 0 0 0.3"),
    LIGHT_RED("v sfc 255 0 0 0.1"),
    RED  ("v sfc 255 0 0 0.3"),
    LIGHT_GREEN("v sfc 0 255 0 0.1"),
    GREEN("v sfc 0 255 0 0.3"),
    BLUE ("v sfc 0 0 255 0.3"),
    WHITE("v sfc 255 255 255 0.3");

    private String command;
    FillColor(String command) { this.command = command; }
    public void println() { System.out.println(command); }
  }

  private Set<Type> active = EnumSet.noneOf(Type.class);
  private LineColor lineColor;
  private FillColor fillColor;

  public Overlay(String options)
  {
    for (int start = 0;;)
    {
      int end = options.indexOf(",", start);
      if (end == -1)
      {
        active.add(Type.valueOf(options.substring(start).toUpperCase()));
        break;
      }
      active.add(Type.valueOf(options.substring(start, end).toUpperCase()));
      start = end + 1;
    }
  }

  public boolean isActive(Type type)
  {
    return active.contains(type);
  }

  public void init()
  {
    lineColor = null;
    fillColor = null;
  }

  public void setLineColor(LineColor color)
  {
    if (color != null && color != lineColor)
    {
      lineColor = color;
      color.println();
    }
  }

  public void setFillColor(FillColor color)
  {
    if (color != null && color != fillColor)
    {
      fillColor = color;
      color.println();
    }
  }

  public void line(Coord c1, Coord c2, LineColor color)
  {
    setLineColor(color);
    System.out.println("v l " + c1 + " " + c2);
  }

  public void arrow(Coord c1, Coord c2, LineColor color)
  {
    setLineColor(color);
    System.out.println("v a " + c1 + " " + c2);
  }

  public void circle(Coord c, int radius, LineColor color)
  {
    setLineColor(color);
    System.out.println("v c " + c + " " + radius + " false");
  }

  public void star(Coord c, int radius, LineColor color)
  {
    setLineColor(color);
    System.out.println("v s " + c + " " + radius/2 + " " + radius + " 6 false");
  }

  public void highlight(Coord c, FillColor color)
  {
    setFillColor(color);
    System.out.println("v t " + c);
  }

  public void popup(Coord c, String text)
  {
    System.out.println("i " + c + " " + text);
  }
}
