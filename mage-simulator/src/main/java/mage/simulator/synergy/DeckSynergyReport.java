package mage.simulator.synergy;

import mage.cards.Card;
import mage.cards.decks.Deck;
import mage.cards.decks.DeckCardLists;
import mage.cards.decks.importer.DeckImporter;

import java.util.*;

/**
 * Loads a deck and prints a produces/consumes synergy report (backlog item 2.1).
 * Output: tags per unique card, then per-tag producer/consumer counts and the
 * active synergy pairs (tags having both producers and consumers in the deck).
 */
public final class DeckSynergyReport {

    private DeckSynergyReport() {
    }

    public static void print(String deckFile) throws Exception {
        DeckCardLists list = DeckImporter.importDeckFromFile(deckFile, false);
        Deck deck = Deck.load(list, false, false);
        if (deck.getMaindeckCards().isEmpty()) {
            throw new IllegalArgumentException("Could not load deck: " + deckFile);
        }

        // unique cards with counts
        Map<String, Integer> counts = new LinkedHashMap<>();
        Map<String, Card> byName = new LinkedHashMap<>();
        for (Card card : deck.getCards()) {
            counts.merge(card.getName(), 1, Integer::sum);
            byName.putIfAbsent(card.getName(), card);
        }

        Map<SynergyTag, Integer> producers = new EnumMap<>(SynergyTag.class);
        Map<SynergyTag, Integer> consumers = new EnumMap<>(SynergyTag.class);
        Map<SynergyTag, List<String>> consumerCards = new EnumMap<>(SynergyTag.class);

        System.out.println("=== Synergy tag report: " + deckFile + " ===");
        System.out.println();
        System.out.println("--- Cards ---");
        for (Map.Entry<String, Card> e : byName.entrySet()) {
            CardSynergyTags tags = CardSynergyTags.analyze(e.getValue());
            int n = counts.get(e.getKey());
            System.out.printf("%dx %-30s produces=%s consumes=%s%n",
                    n, e.getKey(), tags.produces, tags.consumes);
            for (SynergyTag t : tags.produces) {
                producers.merge(t, n, Integer::sum);
            }
            for (SynergyTag t : tags.consumes) {
                consumers.merge(t, n, Integer::sum);
                consumerCards.computeIfAbsent(t, k -> new ArrayList<>()).add(e.getKey());
            }
        }

        System.out.println();
        System.out.println("--- Active synergy pairs (tag: producers x consumers) ---");
        boolean any = false;
        for (SynergyTag tag : SynergyTag.values()) {
            int p = producers.getOrDefault(tag, 0);
            int c = consumers.getOrDefault(tag, 0);
            if (p > 0 && c > 0) {
                any = true;
                System.out.printf("%-18s %3d producers x %2d consumers (%s)%n",
                        tag, p, c, String.join(", ", consumerCards.get(tag)));
            }
        }
        if (!any) {
            System.out.println("(none — deck has no detected internal synergies)");
        }

        System.out.println();
        System.out.println("--- All tag counts ---");
        for (SynergyTag tag : SynergyTag.values()) {
            int p = producers.getOrDefault(tag, 0);
            int c = consumers.getOrDefault(tag, 0);
            if (p > 0 || c > 0) {
                System.out.printf("%-18s producers=%3d consumers=%3d%n", tag, p, c);
            }
        }
    }
}
