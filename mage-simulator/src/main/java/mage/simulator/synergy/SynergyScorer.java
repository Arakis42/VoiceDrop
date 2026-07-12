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
 * V2 design ("realized synergy"), after v1 measurably LOST 9:21 against plain mad:
 * v1 scored standing board producer/consumer pairs, which inflated own-permanent
 * value and distorted combat trades (AI hoarded creatures instead of trading),
 * and rewarded past one-shot events (ETB/CAST) that cannot fire again.
 * <p>
 * V2 scores, per consumer tag on the battlefield, the producers in
 * battlefield + graveyard — a monotone "events realized" counter:
 * - casting a producer moves it hand -> battlefield: score increases (cast is rewarded)
 * - a creature trading moves battlefield -> graveyard: score unchanged (no trade distortion)
 * Plus a tiny bonus for a consumer in hand while future producers are in hand,
 * so the AI prefers deploying the payoff early (board consumer unlocks the full bonus).
 * <p>
 * Values are deliberately small tie-breakers relative to ArtificialScoringSystem
 * magnitudes (a permanent ~600-1500), not overrides of material judgement.
 * Enabled per player id (A/B testing: only the "mad-synergy" player uses it).
 */
public final class SynergyScorer implements GameStateEvaluator2.ExtraScorer {

    private static final int REALIZED_PRODUCER_SCORE = 20; // per producer in field+yard, consumer on board
    private static final int REALIZED_PRODUCER_MAX = 8;    // cap counted producers per tag
    private static final int HAND_CONSUMER_SCORE = 5;      // consumer in hand x future producer in hand
    private static final int HAND_CONSUMER_CAP = 30;

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

        // realized producers = battlefield + graveyard (monotone: casting increases it, trading does not decrease it)
        Map<SynergyTag, Integer> realizedProduces = new EnumMap<>(SynergyTag.class);
        Map<SynergyTag, Integer> boardConsumes = new EnumMap<>(SynergyTag.class);
        for (Permanent permanent : game.getBattlefield().getAllActivePermanents(playerId)) {
            CardSynergyTags tags = tagsOf(permanent); // Permanent extends Card
            for (SynergyTag t : tags.produces) {
                realizedProduces.merge(t, 1, Integer::sum);
            }
            for (SynergyTag t : tags.consumes) {
                boardConsumes.merge(t, 1, Integer::sum);
            }
        }
        for (Card card : player.getGraveyard().getCards(game)) {
            for (SynergyTag t : tagsOf(card).produces) {
                realizedProduces.merge(t, 1, Integer::sum);
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
            int hc = handConsumes.getOrDefault(tag, 0);
            if (bc == 0 && hc == 0) {
                continue;
            }
            int rp = realizedProduces.getOrDefault(tag, 0);
            int hp = handProduces.getOrDefault(tag, 0);

            if (bc > 0) {
                // consumer deployed: reward every realized producer event (cast-friendly, trade-neutral)
                total += Math.min(rp, REALIZED_PRODUCER_MAX) * REALIZED_PRODUCER_SCORE;
            } else if (hp > 0) {
                // consumer still in hand, future producers available: deploying the payoff is attractive
                total += Math.min(hc * hp * HAND_CONSUMER_SCORE, HAND_CONSUMER_CAP);
            }
        }
        return total;
    }
}
