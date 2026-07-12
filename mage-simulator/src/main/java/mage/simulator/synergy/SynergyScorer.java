package mage.simulator.synergy;

import mage.cards.Card;
import mage.game.Game;
import mage.game.permanent.Permanent;
import mage.player.ai.score.GameStateEvaluator2;
import mage.players.Player;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Backlog item 2.2: synergy-aware extra scoring plugged into GameStateEvaluator2.
 * <p>
 * Scores active producer/consumer tag pairs so the AI prefers game states where
 * synergies are assembled and prefers casting cards that feed a payoff on board:
 * - board consumer x board producer: full bonus (running engine)
 * - board consumer x hand producer:  small bonus (casting it upgrades to full — gradient up)
 * - hand consumer  x board producers: small bonus (casting the payoff is attractive)
 * <p>
 * Values are calibrated against ArtificialScoringSystem magnitudes
 * (a permanent is worth ~600-1500, a hand card 5): a running pair ~ a small buff,
 * hand bonuses intentionally tiny but larger than HAND_CARD_SCORE differences.
 * Per-tag caps avoid runaway scores on token swarms.
 * <p>
 * Enabled per player id (A/B testing: only the "mad-synergy" player uses it).
 */
public final class SynergyScorer implements GameStateEvaluator2.ExtraScorer {

    private static final int BOARD_PAIR_SCORE = 60;      // per producer matching a board consumer
    private static final int HAND_PRODUCER_SCORE = 15;   // producer in hand, consumer on board
    private static final int HAND_CONSUMER_SCORE = 10;   // consumer in hand, per board producer
    private static final int PER_TAG_CAP = 300;

    private static final SynergyScorer INSTANCE = new SynergyScorer();

    private final Set<UUID> enabledPlayers = ConcurrentHashMap.newKeySet();
    private final Map<String, CardSynergyTags> tagCache = new ConcurrentHashMap<>();

    private SynergyScorer() {
    }

    public static SynergyScorer getInstance() {
        return INSTANCE;
    }

    /**
     * Install as the evaluator's extra scorer (idempotent).
     */
    public static void install() {
        GameStateEvaluator2.setExtraScorer(INSTANCE);
    }

    public void enablePlayer(UUID playerId) {
        enabledPlayers.add(playerId);
    }

    public void reset() {
        enabledPlayers.clear();
    }

    private CardSynergyTags tagsOf(Card card) {
        return tagCache.computeIfAbsent(card.getName(), n -> CardSynergyTags.analyze(card));
    }

    @Override
    public int score(UUID playerId, Game game) {
        if (!enabledPlayers.contains(playerId)) {
            return 0;
        }
        Player player = game.getPlayer(playerId);
        if (player == null) {
            return 0;
        }

        // collect tags on battlefield and hand
        Map<SynergyTag, Integer> boardProduces = new EnumMap<>(SynergyTag.class);
        Map<SynergyTag, Integer> boardConsumes = new EnumMap<>(SynergyTag.class);
        for (Permanent permanent : game.getBattlefield().getAllActivePermanents(playerId)) {
            CardSynergyTags tags = tagsOf(permanent); // Permanent extends Card
            for (SynergyTag t : tags.produces) {
                boardProduces.merge(t, 1, Integer::sum);
            }
            for (SynergyTag t : tags.consumes) {
                boardConsumes.merge(t, 1, Integer::sum);
            }
        }
        Map<SynergyTag, Integer> handProduces = new EnumMap<>(SynergyTag.class);
        Map<SynergyTag, Integer> handConsumes = new EnumMap<>(SynergyTag.class);
        for (Card card : player.getHand().getCards(game)) {
            CardSynergyTags tags = tagsOf(card);
            for (SynergyTag t : tags.produces) {
                handProduces.merge(t, 1, Integer::sum);
            }
            for (SynergyTag t : tags.consumes) {
                handConsumes.merge(t, 1, Integer::sum);
            }
        }

        int total = 0;
        for (SynergyTag tag : SynergyTag.values()) {
            int bc = boardConsumes.getOrDefault(tag, 0);
            if (bc == 0 && !handConsumes.containsKey(tag)) {
                continue;
            }
            int bp = boardProduces.getOrDefault(tag, 0);
            int hp = handProduces.getOrDefault(tag, 0);
            int hc = handConsumes.getOrDefault(tag, 0);

            int tagScore = 0;
            if (bc > 0) {
                // running engine: each board producer feeds the consumer(s)
                tagScore += Math.min(bc, 3) * bp * BOARD_PAIR_SCORE / Math.max(1, Math.min(bc, 3));
                tagScore = Math.min(tagScore, PER_TAG_CAP);
                // producers still in hand: casting them will feed the engine
                tagScore += Math.min(hp * HAND_PRODUCER_SCORE, 60);
            }
            if (hc > 0 && bp > 0) {
                // payoff in hand, producers already on board: casting it is attractive
                tagScore += Math.min(hc * Math.min(bp, 4) * HAND_CONSUMER_SCORE, 80);
            }
            total += tagScore;
        }
        return total;
    }
}
