package mage.simulator;

/**
 * Result of a single simulated game, serializable as one JSONL line.
 */
public class GameResult {

    public int gameIndex;
    public long seed;
    public String deck1;
    public String deck2;
    public String firstChoice;   // player who got the "choose starting player" decision
    public String winner;        // player name, "draw" or "error"
    public int turns;
    public int life1;
    public int life2;
    public long durationMs;
    public String endReason;     // game_over | max_turns | error
    public String error;         // exception message if endReason == error

    private static String esc(String s) {
        if (s == null) {
            return "";
        }
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    public String toJson() {
        StringBuilder sb = new StringBuilder(256);
        sb.append('{');
        sb.append("\"game\":").append(gameIndex);
        sb.append(",\"seed\":").append(seed);
        sb.append(",\"deck1\":\"").append(esc(deck1)).append('"');
        sb.append(",\"deck2\":\"").append(esc(deck2)).append('"');
        sb.append(",\"first_choice\":\"").append(esc(firstChoice)).append('"');
        sb.append(",\"winner\":\"").append(esc(winner)).append('"');
        sb.append(",\"turns\":").append(turns);
        sb.append(",\"life1\":").append(life1);
        sb.append(",\"life2\":").append(life2);
        sb.append(",\"duration_ms\":").append(durationMs);
        sb.append(",\"end_reason\":\"").append(esc(endReason)).append('"');
        if (error != null) {
            sb.append(",\"error\":\"").append(esc(error)).append('"');
        }
        sb.append('}');
        return sb.toString();
    }
}
