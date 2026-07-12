package mage.simulator.players;

import mage.constants.RangeOfInfluence;
import mage.game.Game;
import mage.player.ai.ComputerPlayer7;
import mage.simulator.features.FeatureCollector;

/**
 * ComputerPlayer7 ("mad" AI) that records game features once per turn.
 * The collector is consulted only for the real game (never inside AI simulations,
 * guarded twice: here and in FeatureCollector via game.isSimulation()).
 */
public class InstrumentedPlayer7 extends ComputerPlayer7 {

    private transient FeatureCollector collector;

    public InstrumentedPlayer7(String name, RangeOfInfluence range, int skill) {
        super(name, range, skill);
    }

    public InstrumentedPlayer7(final InstrumentedPlayer7 player) {
        super(player);
        this.collector = player.collector;
    }

    public void setCollector(FeatureCollector collector) {
        this.collector = collector;
    }

    @Override
    public InstrumentedPlayer7 copy() {
        return new InstrumentedPlayer7(this);
    }

    @Override
    public boolean priority(Game game) {
        if (collector != null && !game.isSimulation()) {
            collector.recordIfNewTurn(game);
        }
        return super.priority(game);
    }
}
