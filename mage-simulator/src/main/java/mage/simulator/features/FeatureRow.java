package mage.simulator.features;

/**
 * One observation: game state features for both players at the start of a turn.
 * Written as one JSONL line (flattened, ML-friendly) together with the game outcome.
 */
public class FeatureRow {

    public int turn;
    public String activePlayer;
    public PlayerFeatures p1;
    public PlayerFeatures p2;

    public static class PlayerFeatures {
        public int life;
        public int handSize;
        public int librarySize;
        public int graveyardSize;
        public int lands;
        public int untappedLands;
        public int creatures;
        public int otherPermanents;
        public int totalPower;
        public int totalToughness;

        public void appendJson(StringBuilder sb, String prefix) {
            sb.append('"').append(prefix).append("_life\":").append(life);
            sb.append(",\"").append(prefix).append("_hand\":").append(handSize);
            sb.append(",\"").append(prefix).append("_library\":").append(librarySize);
            sb.append(",\"").append(prefix).append("_graveyard\":").append(graveyardSize);
            sb.append(",\"").append(prefix).append("_lands\":").append(lands);
            sb.append(",\"").append(prefix).append("_untapped_lands\":").append(untappedLands);
            sb.append(",\"").append(prefix).append("_creatures\":").append(creatures);
            sb.append(",\"").append(prefix).append("_other_permanents\":").append(otherPermanents);
            sb.append(",\"").append(prefix).append("_power\":").append(totalPower);
            sb.append(",\"").append(prefix).append("_toughness\":").append(totalToughness);
        }
    }

    /**
     * @param outcome 1 = player1 won, 0 = player1 lost, -1 = draw/unknown
     */
    public String toJson(int gameIndex, long seed, int outcome) {
        StringBuilder sb = new StringBuilder(384);
        sb.append('{');
        sb.append("\"game\":").append(gameIndex);
        sb.append(",\"seed\":").append(seed);
        sb.append(",\"turn\":").append(turn);
        sb.append(",\"active\":\"").append(activePlayer == null ? "" : activePlayer).append('"');
        sb.append(',');
        p1.appendJson(sb, "p1");
        sb.append(',');
        p2.appendJson(sb, "p2");
        sb.append(",\"p1_won\":").append(outcome);
        sb.append('}');
        return sb.toString();
    }
}
