import java.util.*;

public enum BattleMode
{
  CAREFUL // Avoid any loss; try to kill
  {
    @Override
    public int getScore(int ownDead, int oppKilled)
    {
      return oppKilled - 16*ownDead;
    }

    @Override
    public Coord move(MyBot bot, Coord source, List<Coord> moves)
    {
      return bot.doMoveCarefully(source, moves);
    }
  },
  BOLD // Allow exchanges but avoid deficit; try to kill
  {
    @Override
    public int getScore(int ownDead, int oppKilled)
    {
      return oppKilled + 16*(oppKilled - ownDead);
    }

    @Override
    public Coord move(MyBot bot, Coord source, List<Coord> moves)
    {
      return bot.doMoveBoldly(source, moves);
    }
  },
  FEARLESS // Ignore any loss; try to kill
  {
    @Override
    public int getScore(int ownDead, int oppKilled)
    {
      return Math.max(0, 16*oppKilled - ownDead);
    }

    @Override
    public Coord move(MyBot bot, Coord source, List<Coord> moves)
    {
      return bot.doMoveFearlessly(source, moves);
    }
  };

  abstract public int getScore(int ownKilled, int oppKilled);
  abstract Coord move(MyBot bot, Coord source, List<Coord> moves);
}
