package mage.simulator.synergy;

import mage.abilities.Ability;
import mage.abilities.TriggeredAbility;
import mage.cards.Card;
import mage.constants.CardType;

import java.util.EnumSet;
import java.util.Locale;
import java.util.Set;

/**
 * Derives produces/consumes synergy tags for a card (backlog item 2.1).
 * <p>
 * v1 strategy: rule-text pattern matching on ability rules (robust across the
 * ~30k card classes) + card type analysis. Ability class introspection can be
 * added later for higher precision. The model tolerates partial coverage —
 * unrecognized abilities simply yield no tags.
 */
public final class CardSynergyTags {

    public final Set<SynergyTag> produces = EnumSet.noneOf(SynergyTag.class);
    public final Set<SynergyTag> consumes = EnumSet.noneOf(SynergyTag.class);

    private CardSynergyTags() {
    }

    public static CardSynergyTags analyze(Card card) {
        CardSynergyTags tags = new CardSynergyTags();
        boolean isCreature = card.getCardType().contains(CardType.CREATURE);
        boolean isLand = card.getCardType().contains(CardType.LAND);
        boolean isInstantSorcery = card.getCardType().contains(CardType.INSTANT)
                || card.getCardType().contains(CardType.SORCERY);

        // --- produces from card type ---
        if (isCreature) {
            tags.produces.add(SynergyTag.CREATURE_CAST);
            tags.produces.add(SynergyTag.CREATURE_ETB);
            tags.produces.add(SynergyTag.CREATURE_DIES); // will eventually die/be sacrificeable
        }
        if (isInstantSorcery) {
            tags.produces.add(SynergyTag.NONCREATURE_CAST);
        }
        if (isLand) {
            tags.produces.add(SynergyTag.LANDFALL);
        }

        for (Ability ability : card.getAbilities()) {
            String rule;
            try {
                rule = ability.getRule();
            } catch (Exception e) {
                continue; // some rules need a game context; skip
            }
            if (rule == null || rule.isEmpty()) {
                continue;
            }
            String r = rule.toLowerCase(Locale.ENGLISH);

            // --- consumes: triggered abilities & static payoffs that care about events ---
            if (ability instanceof TriggeredAbility) {
                if (r.contains("whenever you cast a creature spell")
                        || r.contains("whenever you cast another creature spell")) {
                    tags.consumes.add(SynergyTag.CREATURE_CAST);
                }
                if (r.contains("cast a noncreature spell")
                        || r.contains("cast an instant or sorcery")
                        || r.contains("whenever you cast a spell")) {
                    tags.consumes.add(SynergyTag.NONCREATURE_CAST);
                }
                if (r.contains("creature you control enters")
                        || r.contains("creature enters the battlefield under your control")
                        || r.contains("another creature enters")) {
                    tags.consumes.add(SynergyTag.CREATURE_ETB);
                }
                if (r.contains("creature you control dies")
                        || r.contains("another creature dies")
                        || r.contains("creature dies,")) {
                    tags.consumes.add(SynergyTag.CREATURE_DIES);
                }
                if (r.contains("whenever you gain life")) {
                    tags.consumes.add(SynergyTag.LIFE_GAINED);
                }
                if (r.contains("whenever you draw a card")) {
                    tags.consumes.add(SynergyTag.CARD_DRAWN);
                }
                if (r.contains("whenever you discard")) {
                    tags.consumes.add(SynergyTag.DISCARD);
                }
                if (r.contains("whenever you sacrifice")) {
                    tags.consumes.add(SynergyTag.SACRIFICE);
                }
                if (r.contains("one or more +1/+1 counters")
                        || r.contains("whenever a +1/+1 counter is put")) {
                    tags.consumes.add(SynergyTag.COUNTERS_P1P1);
                }
                if (r.contains("whenever") && r.contains("attacks")) {
                    tags.consumes.add(SynergyTag.ATTACK);
                }
                if (r.contains("whenever a land you control enters")
                        || r.contains("landfall")) {
                    tags.consumes.add(SynergyTag.LANDFALL);
                }
                if (r.contains("token")) {
                    // trigger that creates tokens also produces
                    if (r.contains("create")) {
                        tags.produces.add(SynergyTag.TOKEN_CREATED);
                        tags.produces.add(SynergyTag.CREATURE_ETB);
                    }
                }
            }

            // --- produces from rule text (any ability type) ---
            if (r.contains("create") && r.contains("token")) {
                tags.produces.add(SynergyTag.TOKEN_CREATED);
                tags.produces.add(SynergyTag.CREATURE_ETB);
                tags.produces.add(SynergyTag.CREATURE_DIES);
            }
            if (r.contains("you gain") && r.contains("life")) {
                tags.produces.add(SynergyTag.LIFE_GAINED);
            }
            if (r.contains("draw a card") || r.contains("draw two cards")
                    || r.contains("draw three cards")) {
                tags.produces.add(SynergyTag.CARD_DRAWN);
            }
            if (r.contains("discard a card") || r.contains("discard two cards")) {
                tags.produces.add(SynergyTag.DISCARD);
            }
            if (r.contains("sacrifice a creature") || r.contains("sacrifice another creature")
                    || r.contains("sacrifice a permanent")) {
                // sacrifice as cost or effect: outlet produces the DIES event and consumes bodies
                tags.produces.add(SynergyTag.SACRIFICE);
                tags.produces.add(SynergyTag.CREATURE_DIES);
                tags.consumes.add(SynergyTag.CREATURE_DIES); // wants bodies around
            }
            if (r.contains("put a +1/+1 counter") || r.contains("put x +1/+1 counters")
                    || r.contains("put two +1/+1 counters")) {
                tags.produces.add(SynergyTag.COUNTERS_P1P1);
            }
            if (r.contains("return") && r.contains("from your graveyard")) {
                tags.consumes.add(SynergyTag.GRAVEYARD_USE);
            }
            if (r.contains("flashback") || r.contains("delve") || r.contains("escape")) {
                tags.consumes.add(SynergyTag.GRAVEYARD_USE);
            }
            if (r.contains("search your library") && r.contains("land")) {
                tags.produces.add(SynergyTag.LANDFALL);
            }
        }
        return tags;
    }
}
