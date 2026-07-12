package mage.simulator.players;

import mage.constants.RangeOfInfluence;
import mage.players.Player;
import mage.simulator.features.FeatureCollector;

/**
 * Creates simulator players by config type (backlog item 0.2 — A/B testing of
 * different AI configurations per seat).
 * <p>
 * Types:
 * - "mad":   ComputerPlayer7, the strongest built-in AI (game simulations)
 * - "basic": ComputerPlayer, plays nothing proactively — goldfish target
 */
public final class PlayerFactory {

    private PlayerFactory() {
    }

    public static Player create(String type, String name, int skill, int thinkTimeSecs) {
        switch (type) {
            case "mad": {
                InstrumentedPlayer7 player = new InstrumentedPlayer7(name, RangeOfInfluence.ONE, skill);
                if (thinkTimeSecs > 0) {
                    player.setMaxThinkTimeSecs(thinkTimeSecs);
                }
                return player;
            }
            case "basic":
                return new InstrumentedBasicPlayer(name, RangeOfInfluence.ONE);
            default:
                throw new IllegalArgumentException("Unknown player type '" + type + "' (supported: mad, basic)");
        }
    }

    public static void attachCollector(Player player, FeatureCollector collector) {
        if (player instanceof InstrumentedPlayer7) {
            ((InstrumentedPlayer7) player).setCollector(collector);
        } else if (player instanceof InstrumentedBasicPlayer) {
            ((InstrumentedBasicPlayer) player).setCollector(collector);
        }
    }
}
