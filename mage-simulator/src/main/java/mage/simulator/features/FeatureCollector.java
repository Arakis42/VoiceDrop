package mage.simulator.features;

import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.players.Player;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * Collects one FeatureRow per turn from the real (non-simulated) game.
 * Backlog item 0.3: training data source for a learned evaluator.
 * <p>
 * Thread note: recording happens from the single game thread, results are read
 * after the game thread finished (join), so a plain list is sufficient.
 */
public class FeatureCollector {

    private final UUID player1Id;
    private final UUID player2Id;
    private final List<FeatureRow> rows = new ArrayList<>();
    private int lastRecordedTurn = 0;

    public FeatureCollector(UUID player1Id, UUID player2Id) {
        this.player1Id = player1Id;
        this.player2Id = player2Id;
    }

    /**
     * Record once per turn; safe to call from every priority.
     */
    public void recordIfNewTurn(Game game) {
        if (game.isSimulation()) {
            return; // never record from AI what-if games
        }
        int turn = game.getTurnNum();
        if (turn == lastRecordedTurn) {
            return;
        }
        lastRecordedTurn = turn;

        FeatureRow row = new FeatureRow();
        row.turn = turn;
        Player active = game.getPlayer(game.getActivePlayerId());
        row.activePlayer = active == null ? null : active.getName();
        row.p1 = extract(game, player1Id);
        row.p2 = extract(game, player2Id);
        rows.add(row);
    }

    public List<FeatureRow> getRows() {
        return rows;
    }

    static FeatureRow.PlayerFeatures extract(Game game, UUID playerId) {
        FeatureRow.PlayerFeatures f = new FeatureRow.PlayerFeatures();
        Player player = game.getPlayer(playerId);
        if (player == null) {
            return f;
        }
        f.life = player.getLife();
        f.handSize = player.getHand().size();
        f.librarySize = player.getLibrary().size();
        f.graveyardSize = player.getGraveyard().size();
        for (Permanent permanent : game.getBattlefield().getAllActivePermanents(playerId)) {
            if (permanent.isLand(game)) {
                f.lands++;
                if (!permanent.isTapped()) {
                    f.untappedLands++;
                }
            } else if (permanent.isCreature(game)) {
                f.creatures++;
                f.totalPower += Math.max(0, permanent.getPower().getValue());
                f.totalToughness += Math.max(0, permanent.getToughness().getValue());
            } else {
                f.otherPermanents++;
            }
        }
        return f;
    }
}
