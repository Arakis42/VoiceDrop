package mage.simulator.synergy;

import java.io.BufferedReader;
import java.io.FileReader;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.*;

/**
 * Optional external tag source, e.g. Scryfall Tagger oracle tags (otags).
 * <p>
 * File format (tags/external_tags.csv, one line per card):
 * card name;otag1,otag2,...
 * <p>
 * Example:
 * Healing Salve;lifegain
 * Tortured Existence;discard outlet,graveyard
 * <p>
 * Oracle tags are mapped to SynergyTags via OTAG_MAPPING (curated, extensible).
 * This complements the rule-text analysis in CardSynergyTags: crowd-sourced
 * semantic tags catch what pattern matching misses (modal effects, archetype
 * knowledge like "discard payoff"). Data must be provided offline — there is
 * no official bulk API for the Scryfall Tagger project; see README for options.
 */
public final class ExternalTags {

    /** curated mapping: scryfall oracle tag -> (produces, consumes) */
    private static final Map<String, SynergyTag[]> OTAG_PRODUCES = new HashMap<>();
    private static final Map<String, SynergyTag[]> OTAG_CONSUMES = new HashMap<>();

    static {
        OTAG_PRODUCES.put("lifegain", new SynergyTag[]{SynergyTag.LIFE_GAINED});
        OTAG_PRODUCES.put("tokens", new SynergyTag[]{SynergyTag.TOKEN_CREATED, SynergyTag.CREATURE_ETB});
        OTAG_PRODUCES.put("token-generator", new SynergyTag[]{SynergyTag.TOKEN_CREATED, SynergyTag.CREATURE_ETB});
        OTAG_PRODUCES.put("card-draw", new SynergyTag[]{SynergyTag.CARD_DRAWN});
        OTAG_PRODUCES.put("cantrip", new SynergyTag[]{SynergyTag.CARD_DRAWN});
        OTAG_PRODUCES.put("discard outlet", new SynergyTag[]{SynergyTag.DISCARD});
        OTAG_PRODUCES.put("self-discard", new SynergyTag[]{SynergyTag.DISCARD});
        OTAG_PRODUCES.put("sacrifice outlet", new SynergyTag[]{SynergyTag.SACRIFICE, SynergyTag.CREATURE_DIES});
        OTAG_PRODUCES.put("ramp", new SynergyTag[]{SynergyTag.LANDFALL});
        OTAG_PRODUCES.put("counters-matter", new SynergyTag[]{SynergyTag.COUNTERS_P1P1});

        OTAG_CONSUMES.put("lifegain-payoff", new SynergyTag[]{SynergyTag.LIFE_GAINED});
        OTAG_CONSUMES.put("discard payoff", new SynergyTag[]{SynergyTag.DISCARD});
        OTAG_CONSUMES.put("madness", new SynergyTag[]{SynergyTag.DISCARD});
        OTAG_CONSUMES.put("death-trigger-payoff", new SynergyTag[]{SynergyTag.CREATURE_DIES});
        OTAG_CONSUMES.put("aristocrats", new SynergyTag[]{SynergyTag.CREATURE_DIES, SynergyTag.SACRIFICE});
        OTAG_CONSUMES.put("etb-payoff", new SynergyTag[]{SynergyTag.CREATURE_ETB});
        OTAG_CONSUMES.put("landfall", new SynergyTag[]{SynergyTag.LANDFALL});
        OTAG_CONSUMES.put("prowess", new SynergyTag[]{SynergyTag.NONCREATURE_CAST});
        OTAG_CONSUMES.put("graveyard", new SynergyTag[]{SynergyTag.GRAVEYARD_USE});
        OTAG_CONSUMES.put("token-payoff", new SynergyTag[]{SynergyTag.TOKEN_CREATED});
    }

    private static Map<String, List<String>> cardOtags = new HashMap<>();
    private static boolean loaded = false;

    private ExternalTags() {
    }

    /**
     * Load external tag file if present (silent no-op otherwise).
     */
    public static synchronized void loadIfPresent(String path) {
        if (loaded || !Files.exists(Paths.get(path))) {
            return;
        }
        try (BufferedReader reader = new BufferedReader(new FileReader(path))) {
            String line;
            while ((line = reader.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("#")) {
                    continue;
                }
                int sep = line.indexOf(';');
                if (sep <= 0) {
                    continue;
                }
                String name = line.substring(0, sep).trim();
                List<String> otags = new ArrayList<>();
                for (String tag : line.substring(sep + 1).split(",")) {
                    otags.add(tag.trim().toLowerCase(Locale.ENGLISH));
                }
                cardOtags.put(name, otags);
            }
            loaded = true;
        } catch (Exception e) {
            System.err.println("Could not load external tags from " + path + ": " + e);
        }
    }

    /**
     * Merge external tags for the given card name into the tag sets.
     */
    public static void mergeInto(String cardName, Set<SynergyTag> produces, Set<SynergyTag> consumes) {
        List<String> otags = cardOtags.get(cardName);
        if (otags == null) {
            return;
        }
        for (String otag : otags) {
            SynergyTag[] p = OTAG_PRODUCES.get(otag);
            if (p != null) {
                produces.addAll(Arrays.asList(p));
            }
            SynergyTag[] c = OTAG_CONSUMES.get(otag);
            if (c != null) {
                consumes.addAll(Arrays.asList(c));
            }
        }
    }

    public static int loadedCardCount() {
        return cardOtags.size();
    }
}
