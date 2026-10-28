
public class Test {

    public static void main(String[] args) {

        // usage: java Test [players [seed [outfile]]]
        MapGenerator map = new MapGenerator();
        String outFile = null;
        try {
            if (args.length > 0) {
                map.setNbrOfPlayers(Integer.parseInt(args[0]));
            }
            if (args.length > 1) {
                map.setSeed(Long.parseLong(args[1]));
            }
            if (args.length > 2) {
                outFile = args[2];
            }
            if (args.length > 3) {
                throw new IllegalArgumentException("too many args");
            }
        } catch (Exception e) {
            System.err.println("usage: java Test [players [seed [outfile]]]");
            System.err.println("  " + e.getMessage());
            System.exit(2);
            return;
        }
        String text = map.map2String(map.generateMap());
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
