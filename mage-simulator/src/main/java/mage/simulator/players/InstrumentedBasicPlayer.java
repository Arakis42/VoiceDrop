package mage.simulator.players;

import mage.constants.RangeOfInfluence;
import mage.game.Game;
import mage.player.ai.ComputerPlayer;
import mage.simulator.features.FeatureCollector;

/**
 * Basic ComputerPlayer ("goldfish" opponent): makes all mandatory choices via
 * simple heuristics but never proactively casts anything (priority = pass).
 * Useful to measure a deck's raw speed (kill turn) without AI interaction.
 */
public class InstrumentedBasicPlayer extends ComputerPlayer {

    private transient FeatureCollector collector;

    public InstrumentedBasicPlayer(String name, RangeOfInfluence range) {
        super(name, range);
    }

    public InstrumentedBasicPlayer(final InstrumentedBasicPlayer player) {
        super(player);
        this.collector = player.collector;
    }

    public void setCollector(FeatureCollector collector) {
        this.collector = collector;
    }

    @Override
    public InstrumentedBasicPlayer copy() {
        return new InstrumentedBasicPlayer(this);
    }

    @Override
    public boolean priority(Game game) {
        if (collector != null && !game.isSimulation()) {
            collector.recordIfNewTurn(game);
        }
        return super.priority(game);
    }
}
