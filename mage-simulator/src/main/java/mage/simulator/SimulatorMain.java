package mage.simulator;

import mage.cards.repository.CardScanner;
import mage.collectors.DataCollectorServices;
import mage.util.ThreadUtils;
import org.apache.log4j.Level;
import org.apache.log4j.Logger;

import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Headless AI-vs-AI batch simulator (auto-battle) for deck testing.
 * <p>
 * Example:
 * mvn -q package exec:java -Dexec.args="--deck1 ../Mage.Tests/RB Aggro.dck --deck2 ../Mage.Tests/RB Aggro.dck --games 10 --skill 5 --seed 42"
 */
public class SimulatorMain {

    public static void main(String[] args) throws Exception {
        SimConfig cfg = SimConfig.parse(args);

        Logger.getRootLogger().setLevel(cfg.verbose ? Level.INFO : Level.WARN);

        if (cfg.tagsDeck != null) {
            // synergy tag report mode (backlog 2.1)
            DataCollectorServices.init(false, false);
            CardScanner.scan();
            mage.simulator.synergy.DeckSynergyReport.print(cfg.tagsDeck);
            return;
        }

        System.out.println("=== XMage Auto-Battle Simulator ===");
        System.out.printf("deck1=%s (skill %d)%n", cfg.deck1, cfg.skill1);
        System.out.printf("deck2=%s (skill %d)%n", cfg.deck2, cfg.skill2);
        System.out.printf("games=%d, baseSeed=%d, maxTurns=%d, out=%s%n", cfg.games, cfg.seed, cfg.maxTurns, cfg.out);

        System.out.println("Loading card database (first run takes a few minutes)...");
        long t0 = System.currentTimeMillis();
        DataCollectorServices.init(false, false);
        CardScanner.scan();
        System.out.printf("Card database ready in %d ms%n", System.currentTimeMillis() - t0);

        List<GameResult> results = new ArrayList<>();
        PrintWriter features = null;
        if (cfg.featuresOut != null) {
            features = new PrintWriter(new BufferedWriter(new FileWriter(cfg.featuresOut)));
        }
        try (PrintWriter out = new PrintWriter(new BufferedWriter(new FileWriter(cfg.out)))) {
            for (int i = 0; i < cfg.games; i++) {
                long seed = cfg.seed + i;
                GameResult result = runInGameThread(i, seed, cfg);
                results.add(result);
                out.println(result.toJson());
                out.flush();
                if (features != null && result.featureRows != null) {
                    int outcome = cfg.name1.equals(result.winner) ? 1
                            : cfg.name2.equals(result.winner) ? 0 : -1;
                    for (mage.simulator.features.FeatureRow row : result.featureRows) {
                        features.println(row.toJson(i, seed, outcome));
                    }
                    features.flush();
                }
                System.out.printf("game %d/%d: winner=%s, turns=%d, life=%d/%d, %d ms (%s)%n",
                        i + 1, cfg.games, result.winner, result.turns,
                        result.life1, result.life2, result.durationMs, result.endReason);
            }
        } finally {
            if (features != null) {
                features.close();
            }
        }

        printSummary(cfg, results);
    }

    /**
     * The engine requires game code to run in a thread named GAME* (see ThreadUtils.ensureRunInGameThread),
     * so each game gets its own properly named thread. One game at a time for now —
     * the AI's internal simulation pool is a shared static resource.
     */
    private static GameResult runInGameThread(int gameIndex, long seed, SimConfig cfg) throws InterruptedException {
        AtomicReference<GameResult> ref = new AtomicReference<>();
        Thread t = new Thread(() -> {
            try {
                ref.set(new GameRunner().run(gameIndex, seed, cfg));
            } catch (Throwable e) {
                GameResult result = new GameResult();
                result.gameIndex = gameIndex;
                result.seed = seed;
                result.deck1 = cfg.deck1;
                result.deck2 = cfg.deck2;
                result.winner = "error";
                result.endReason = "error";
                result.error = e.getClass().getSimpleName() + ": " + e.getMessage();
                ref.set(result);
                e.printStackTrace();
            }
        }, ThreadUtils.THREAD_PREFIX_GAME + "-sim-" + gameIndex);
        t.setDaemon(true);
        t.start();
        t.join();
        return ref.get();
    }

    private static void printSummary(SimConfig cfg, List<GameResult> results) {
        int wins1 = 0;
        int wins2 = 0;
        int draws = 0;
        int errors = 0;
        long totalTurns = 0;
        long totalMs = 0;
        for (GameResult r : results) {
            if (cfg.name1.equals(r.winner)) {
                wins1++;
            } else if (cfg.name2.equals(r.winner)) {
                wins2++;
            } else if ("draw".equals(r.winner)) {
                draws++;
            } else {
                errors++;
            }
            totalTurns += r.turns;
            totalMs += r.durationMs;
        }
        int decided = wins1 + wins2;
        System.out.println();
        System.out.println("=== SUMMARY ===");
        System.out.printf("%s (deck1): %d wins%n", cfg.name1, wins1);
        System.out.printf("%s (deck2): %d wins%n", cfg.name2, wins2);
        System.out.printf("draws: %d, errors: %d%n", draws, errors);
        if (decided > 0) {
            double p = (double) wins1 / decided;
            double[] ci = wilson(wins1, decided);
            System.out.printf("deck1 winrate (of decided): %.1f%% [95%% CI %.1f%%..%.1f%%]%n",
                    p * 100, ci[0] * 100, ci[1] * 100);
        }
        if (!results.isEmpty()) {
            System.out.printf("avg turns: %.1f, avg game time: %.1f s%n",
                    (double) totalTurns / results.size(), totalMs / 1000.0 / results.size());
        }
    }

    /**
     * Wilson score interval for a binomial proportion, z=1.96 (95%).
     */
    static double[] wilson(int successes, int n) {
        double z = 1.96;
        double p = (double) successes / n;
        double denom = 1 + z * z / n;
        double center = (p + z * z / (2 * n)) / denom;
        double half = (z / denom) * Math.sqrt(p * (1 - p) / n + z * z / (4.0 * n * n));
        return new double[]{Math.max(0, center - half), Math.min(1, center + half)};
    }
}
