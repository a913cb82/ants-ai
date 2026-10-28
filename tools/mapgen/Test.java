
public class Test {

    public static void main(String[] args) {
        int players = -1;
        long seed = System.currentTimeMillis();

        for (int i = 0; i < args.length; i++) {
            if (args[i].equals("--players") && i + 1 < args.length) {
                players = Integer.parseInt(args[++i]);
            } else if (args[i].equals("--seed") && i + 1 < args.length) {
                seed = Long.parseLong(args[++i]);
            } else {
                System.err.println("Usage: Test [--players 2|4|8] [--seed N]");
                System.exit(2);
            }
        }

        MapGenerator map = new MapGenerator();
        map.setSeed(seed);
        MapWalker.setSeed(seed);
        if (players != -1) {
            map.setNbrOfPlayers(players);
            // Fair assignment tables: 2p -> 7 ({A,B}), 4p -> 5, 8p -> 0.
            map.setSymOverride(players == 2 ? 7 : (players == 4 ? 5 : 0));
        }
        int[][] res = map.generateMap();
        map.printMap(res);
    }

    public static void print(int[][] map) {
        unit = 'a';
        StringBuilder sb = new StringBuilder();

        for (int r = 0; r < map.length; r++) {
            sb.append("m ");
            for (int c = 0; c < map[0].length; c++) {
                sb.append(form(map[r][c]));
                //sb.append(getVal4(r, c));
            }
            sb.append("\n");
        }
        System.out.println(sb.toString());
    }

    private static char unit = 'a';
    private static String prefix = " ";
    private static String form(int i) {
        if (i == 1) {
            return prefix + ".";
        }
        else if (i == 0) {
            return prefix + "%";
        }
        else if (i == 2) {
            return prefix + unit++;
        }
        else if (i == -1) {
            return prefix + " ";
        }

        if (i < 10 && i >= 0) {
            return "  " + i;
        }
        else if (i < 100 || i < 0) {
            return " " + i;
        }

        return "" + i;
    }
}
