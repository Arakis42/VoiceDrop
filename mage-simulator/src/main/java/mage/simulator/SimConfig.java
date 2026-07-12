package mage.simulator;

/**
 * Simulator configuration parsed from CLI args.
 */
public class SimConfig {

    public String deck1;
    public String deck2;
    public String name1 = "AI_1";
    public String name2 = "AI_2";
    public int games = 10;
    public int skill1 = 5;
    public int skill2 = 5;
    public int thinkTimeSecs = 0; // 0 = engine default (skill * 3)
    public long seed = 0;         // 0 = random base seed
    public int maxTurns = 60;
    public String out = "results.jsonl";
    public boolean verbose = false;

    public static SimConfig parse(String[] args) {
        SimConfig cfg = new SimConfig();
        int skillBoth = 0;
        for (int i = 0; i < args.length; i++) {
            String a = args[i];
            switch (a) {
                case "--deck1": cfg.deck1 = args[++i]; break;
                case "--deck2": cfg.deck2 = args[++i]; break;
                case "--games": cfg.games = Integer.parseInt(args[++i]); break;
                case "--skill": skillBoth = Integer.parseInt(args[++i]); break;
                case "--skill1": cfg.skill1 = Integer.parseInt(args[++i]); break;
                case "--skill2": cfg.skill2 = Integer.parseInt(args[++i]); break;
                case "--thinkTime": cfg.thinkTimeSecs = Integer.parseInt(args[++i]); break;
                case "--seed": cfg.seed = Long.parseLong(args[++i]); break;
                case "--maxTurns": cfg.maxTurns = Integer.parseInt(args[++i]); break;
                case "--out": cfg.out = args[++i]; break;
                case "--verbose": cfg.verbose = true; break;
                case "--help":
                    printUsage();
                    System.exit(0);
                default:
                    throw new IllegalArgumentException("Unknown argument: " + a + " (use --help)");
            }
        }
        if (skillBoth > 0) {
            cfg.skill1 = skillBoth;
            cfg.skill2 = skillBoth;
        }
        if (cfg.deck1 == null || cfg.deck2 == null) {
            printUsage();
            throw new IllegalArgumentException("--deck1 and --deck2 are required");
        }
        if (cfg.seed == 0) {
            cfg.seed = System.currentTimeMillis();
        }
        return cfg;
    }

    public static void printUsage() {
        System.out.println("Usage: SimulatorMain --deck1 <a.dck> --deck2 <b.dck> [options]");
        System.out.println("  --games N        number of games (default 10)");
        System.out.println("  --skill N        AI skill for both players 1-8 (default 5)");
        System.out.println("  --skill1/--skill2 N  per-player skill override (A/B testing)");
        System.out.println("  --thinkTime S    max AI think time per decision in seconds (default: skill*3)");
        System.out.println("  --seed N         base seed, game i uses seed+i (default: current time)");
        System.out.println("  --maxTurns N     abort game as draw after N turns (default 60)");
        System.out.println("  --out FILE       JSONL output file (default results.jsonl)");
        System.out.println("  --verbose        show AI logs (log4j INFO)");
    }
}
