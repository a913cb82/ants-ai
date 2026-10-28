import java.util.Random;
import java.util.Stack;

/**
 * Uses "walkers" that randomly moves around a water filled map and adds lands
 */
public class MapWalker {

    private static Random rnd = new Random();

    //Land proportions
    private final static double MIN_LAND_PROPORTION = 0.5;
    private final static double MAX_LAND_PROPORTION = 0.8;

    private final static int[][] DIRECTIONS = {{-1, 0}, {1, 0}, {0, 1}, {0, -1}};

    //Amount of walkers to use
    private int nbrOfWalkers;

    //Some temp values
    private int[][] tMap;
    private int[][] tMapWalkers;
    int tLandSquares = 0;

    /**
     * Uses walkers to fill a water map with land. Specify amount of walkers and
     * if it's a diagonal map.
     */
    public MapWalker(int nbrOfWalkers) {
        this.nbrOfWalkers = nbrOfWalkers;
    }

    public static void setSeed(long seed) {
        rnd.setSeed(seed);
    }

    /**
     * Headless demo: fills a small part with walkers, mirrors it for a second
     * player and prints a parseable 2-player map to stdout (or --out FILE).
     * usage: java MapWalker [--seed N] [--out FILE]
     */
    public static void main(String[] args) {
        long seed = System.currentTimeMillis();
        String outFile = null;
        try {
            for (int i = 0; i < args.length; i++) {
                if (args[i].equals("--seed")) {
                    seed = Long.parseLong(args[++i]);
                } else if (args[i].equals("--out")) {
                    outFile = args[++i];
                } else {
                    throw new IllegalArgumentException("unknown arg: " + args[i]);
                }
            }
        } catch (Exception e) {
            System.err.println("usage: java MapWalker [--seed N] [--out FILE]");
            System.err.println("  " + e.getMessage());
            System.exit(2);
            return;
        }
        rnd.setSeed(seed);
        int partRows = 14;
        int partCols = 26;
        int[][] part = new int[partRows][partCols];
        int[] start = {partRows / 2, partCols / 2};
        part = new MapWalker(4).fillMap(part, start);
        // Second hill: 180-degree rotation of the start, like MapGenerator's
        // 2-player mirror, so both players own a hill.
        int[] start2 = {partRows - 1 - start[0], partCols - 1 - start[1]};
        int[][] full = new int[partRows * 2][partCols];
        for (int r = 0; r < partRows; r++) {
            for (int c = 0; c < partCols; c++) {
                full[r][c] = part[r][c];
                full[full.length - 1 - r][c] = part[r][c];
            }
        }
        full[start[0]][start[1]] = MapGenerator.ANT_START_POS_TILE;
        full[start2[0]][start2[1]] = MapGenerator.ANT_START_POS_TILE;
        MapGenerator gen = new MapGenerator();
        gen.setNbrOfPlayers(2);
        String text = gen.map2String(full);
        if (outFile != null) {
            try {
                java.nio.file.Files.writeString(java.nio.file.Path.of(outFile), text);
            } catch (java.io.IOException e) {
                System.err.println("cannot write " + outFile + ": " + e.getMessage());
                System.exit(1);
                return;
            }
        } else {
            System.out.print(text);
        }
    }

    /**
     * Fills the provided map with land
     */
    public int[][] fillMap(int[][] map, int[] startPos) {
        tMap = map;

        tMapWalkers = new int[nbrOfWalkers][2];
        tMapWalkers[0] = startPos;

        for (int i = 1; i < nbrOfWalkers; i++) {
            tMapWalkers[i] = pickRandomSquare();
        }

        addLand();

        return map;
    }

    /**
     * Randomly picks a valid location inside the map
     */
    private int[] pickRandomSquare() {
        int[] pos;
        do {
            pos = new int[] {rnd.nextInt(tMap.length), rnd.nextInt(tMap[0].length)};
        } while (tMap[pos[0]][pos[1]] == -1);

        return pos;
    }

    /**
     * Adds land to a map of water
     */
    private void addLand() {
        int waterSquares = countWaterSquares();
        int min = (int)(MIN_LAND_PROPORTION * (double)waterSquares);
        int max = (int)(MAX_LAND_PROPORTION * (double)waterSquares);

        int nbrOfLandSquares = rnd.nextInt(max - min) + min;

        while(tLandSquares < nbrOfLandSquares || !isValidMap()) {
            walkersInRandomDirection();

            for (int i = 0; i < tMapWalkers.length; i++) {
                if (tMap[tMapWalkers[i][0]][tMapWalkers[i][1]] == MapGenerator.WATER_TILE) {
                    tLandSquares++;
                    tMap[tMapWalkers[i][0]][tMapWalkers[i][1]] = MapGenerator.LAND_TILE;
                }
            }
        }
    }

    /**
     * Count amount of water squares in the map
     */
    private int countWaterSquares() {
        int amount = 0;

        for (int r = 0; r  < tMap.length; r++) {
            for (int c = 0; c < tMap[0].length; c++) {
                amount += tMap[r][c] == MapGenerator.WATER_TILE ? 1 : 0;
            }
        }

        return amount;
    }

    /**
     * Make all walkers move in a random direction
     */
    private void walkersInRandomDirection() {
        for (int i = 0; i < tMapWalkers.length; i++) {
            int[] direction = DIRECTIONS[rnd.nextInt(DIRECTIONS.length)];
            tMapWalkers[i] = getValidLocation(tMapWalkers[i], direction);
        }
    }

    /**
     * Returns a valid location based on the old location and a direction
     */
    private int[] getValidLocation(int[] loc, int[] direction) {
        int row = loc[0] + direction[0];
        int col = loc[1] + direction[1];

        row = Math.min(row, tMap.length - 1);
        row = Math.max(row, 0);

        col = Math.min(col, tMap[0].length - 1);
        col = Math.max(col, 0);

        return new int[] {row, col};
    }

    /**
     * Checks whether the players can reach every non-wall square
     */
    private boolean isValidMap() {
        int[][] visited = new int[tMap.length][tMap[0].length];

        visited[tMapWalkers[0][0]][tMapWalkers[0][1]] = 1;
        int squaresVisited = 1;

        Stack<int[]> stack = new Stack<int[]>();
        stack.add(new int[] {tMapWalkers[0][0], tMapWalkers[0][1]});

        while (!stack.empty()) {
            int[] tmpLoc = stack.pop();

            for (int i = 0; i < DIRECTIONS.length; i++) {
                int[] newLoc = getValidLocation(tmpLoc, DIRECTIONS[i]);

                if (visited[newLoc[0]][newLoc[1]] == 0 && tMap[newLoc[0]][newLoc[1]] == 1) {
                    visited[newLoc[0]][newLoc[1]] = 1;
                    stack.add(newLoc);
                    squaresVisited++;
                }
            }
        }

        if (squaresVisited == tLandSquares) {
            return true;
        }

        return false;
    }
}
