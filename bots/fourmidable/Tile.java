/**
 * Represents a tile of the game map.
 */
public final class Tile
{
  private static int turn;

  private final Coord   coord;           // FINAL: Never changes
  private       boolean water;           // PERSISTENT: Can change from false->true first time it is seen
  private       boolean food;            // Changes only when visible.
  private       boolean inferredWater;   // Guessing water here
  private       boolean inferredHill;    // Guessing hill here
  private       int     wasHill;         // PERSISTENT: ID of the hill's owner, never reset
  private       int     firstFood;       // PERSISTENT: first turn we saw food here
  private       int     lastSeen;        // Turn at which the tile was seen last (0 if unseen)
  private       int     hill;            // ID of the hill's owner, 0 if none
  private       int     ant;             // ID or the hill's owner, 0 if none
  private       int     inferredFood;    // Guessing food at turn

  public Tile(int r, int c)
  {
    this.coord = new Coord(r, c);
  }

  public Coord getCoord()
  {
    return coord;
  }

  // TURN ////////////////////////////////////////////////////////////////////

  public static int getTurn()
  {
    return turn;
  }

  public static void incrementTurn()
  {
    ++turn;
  }

  // VISIBILITY ////////////////////////////////////////////////////////////////////

  public void setVisible()
  {
    if (lastSeen < turn)
    {
      // Water is reported only once, don't lose the old value.
      lastSeen        = turn;
      food            = false;
      hill            = 0;
      ant             = 0;
      inferredWater   = false;
      inferredHill    = false;
      inferredFood    = 0;
    }
  }

  public boolean isVisible()
  {
    return lastSeen == turn;
  }

  public boolean hasBeenSeen()
  {
    return lastSeen != 0;
  }

  /**
   * @return the number of turn seen the tile was seen, 0 if visible.
   */
  public int getAge()
  {
    return turn - lastSeen;
  }

  public void unInfer()
  {
    inferredWater   = false;
    inferredHill    = false;
    inferredFood    = 0;
  }

  // WATER ////////////////////////////////////////////////////////////////////

  public void setWater()
  {
    water = true;
  }

  public void inferWater()
  {
    inferredWater = true;
  }

  public boolean hasWater()
  {
    return water || inferredWater;
  }

  public boolean hasInferredWater()
  {
    return inferredWater;
  }

  // FOOD ////////////////////////////////////////////////////////////////////

  public void setFood()
  {
    food = true;
    if (firstFood == 0) firstFood = turn;
  }

  public boolean hasVisibleFood()
  {
    return food && turn == lastSeen;
  }

  public boolean neverSeenFood()
  {
    return firstFood == 0;
  }

  public boolean hasRecentFood(int ageLimit)
  {
    return (food && turn - lastSeen <= ageLimit) || (inferredFood != 0 && turn - inferredFood <= ageLimit);
  }

  public boolean hasInferredFood()
  {
    return inferredFood != 0;
  }

  public boolean hasRecentInferredFood(int ageLimit)
  {
    return inferredFood != 0 && turn - inferredFood <= ageLimit;
  }

  public int getInferredFoodAge()
  {
    return turn - inferredFood;
  }

  // HILLS ////////////////////////////////////////////////////////////////////

  public void setHill(int id)
  {
    hill    = id;
    wasHill = id;
  }

  /**
   * @return if there was an enemy hill the last time we saw this tile.
   */
  public boolean hasEnemyHill()
  {
    return hill > 1 || inferredHill;
  }

  public boolean hasInferredHill()
  {
    return inferredHill;
  }

  public boolean wasOrIsOwnHill()
  {
    return wasHill == 1;
  }

  /**
   * @return the owner of the hill, 1 is us, 0 is none.
   */
  public int getHill()
  {
    return hill;
  }

  // ANTS ////////////////////////////////////////////////////////////////////

  public void setAnt(int id)
  {
    ant = id;
  }

  /**
   * @return the owner of the ant, 1 is us, 0 is none.
   */
  public int getAnt()
  {
    return ant;
  }

  public boolean hasOwnAnt()
  {
    return ant == 1;
  }

  /**
   * @return if we currently see an enemy on this tile
   */
  public boolean hasVisibleEnemyAnt()
  {
    return ant > 1 && lastSeen == turn;
  }

  // MISCELLANEOUS ////////////////////////////////////////////////////////////////////

  /**
   * Can't move on water or visible food (invisible food is too far for us to care).
   * @return if we can move on this tile
   */
  public boolean isBlocked()
  {
    return water || (food && turn == lastSeen);
  }

  public boolean isVisibleLand()
  {
    return !water && turn == lastSeen;
  }

  public boolean hasOwnAntOrWater()
  {
    return ant == 1 || water;
  }

  public int getAgeIfLand()
  {
    return water ? 0 : turn - lastSeen;
  }

  public boolean hasSomethingToInfer()
  {
    return water || wasHill == 1 || firstFood != 0;
  }

  public void inferFrom(Tile other)
  {
    if (lastSeen == 0 && other.water) inferredWater = true;
    if (lastSeen == 0 && other.wasHill == 1) inferredHill = true;
    if (lastSeen != turn && other.firstFood != 0 && (inferredFood == 0 || inferredFood > other.firstFood)) inferredFood = other.firstFood;
  }

  public boolean contradicts(Tile other)
  {
    // This as just been seen
    return lastSeen != 0 && other.lastSeen != 0 && water != other.water;
  }
}
