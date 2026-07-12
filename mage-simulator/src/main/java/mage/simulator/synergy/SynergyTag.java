package mage.simulator.synergy;

/**
 * Event tags for the produces/consumes synergy model (backlog item 2.1).
 * A card CONSUMES a tag when it has a trigger/payoff caring about that event.
 * A card PRODUCES a tag when playing/using it causes that event.
 * Synergy = producer and consumer of the same tag in one deck.
 */
public enum SynergyTag {
    CREATURE_CAST,      // casting creature spells
    NONCREATURE_CAST,   // casting instants/sorceries/noncreature (prowess-like)
    CREATURE_ETB,       // a creature entering the battlefield
    CREATURE_DIES,      // a creature dying
    TOKEN_CREATED,      // token creation
    LIFE_GAINED,        // controller gains life
    CARD_DRAWN,         // controller draws (beyond first)
    DISCARD,            // controller discards / madness-like
    SACRIFICE,          // sacrificing permanents (outlet or payoff)
    GRAVEYARD_USE,      // uses cards in graveyard (return/delve/flashback)
    COUNTERS_P1P1,      // +1/+1 counter placement
    ATTACK,             // attacking matters
    LANDFALL            // land entering the battlefield
}
