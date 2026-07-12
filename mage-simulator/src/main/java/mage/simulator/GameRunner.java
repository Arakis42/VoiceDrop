package mage.simulator;

import mage.cards.decks.Deck;
import mage.cards.decks.DeckCardLists;
import mage.cards.decks.importer.DeckImporter;
import mage.constants.MultiplayerAttackOption;
import mage.constants.RangeOfInfluence;
import mage.game.Game;
import mage.game.GameOptions;
import mage.game.TwoPlayerDuel;
import mage.game.match.Match;
import mage.game.match.MatchOptions;
import mage.game.FreeForAllMatch;
import mage.game.mulligan.MulliganType;
import mage.players.Player;
import mage.simulator.features.FeatureCollector;
import mage.simulator.players.PlayerFactory;
import mage.util.RandomUtil;

/**
 * Runs a single headless AI-vs-AI game and returns the result.
 * <p>
 * Must run in a thread whose name starts with ThreadUtils.THREAD_PREFIX_GAME
 * (or "main") — the engine enforces this, see ThreadUtils.ensureRunInGameThread.
 * <p>
 * Uses the same building blocks as the unit test framework
 * (CardTestPlayerAPIImpl / CardTestPlayerBaseAI): TwoPlayerDuel, ComputerPlayer7,
 * a fake match for MatchPlayer wiring, and GameOptions.stopOnTurn as safety stop.
 */
public class GameRunner {

    public GameResult run(int gameIndex, long seed, SimConfig cfg) throws Exception {
        GameResult result = new GameResult();
        result.gameIndex = gameIndex;
        result.seed = seed;
        result.deck1 = cfg.deck1;
        result.deck2 = cfg.deck2;

        RandomUtil.setSeed(seed);

        Game game = new TwoPlayerDuel(MultiplayerAttackOption.LEFT, RangeOfInfluence.ONE,
                MulliganType.GAME_DEFAULT.getMulligan(0), 60, 20, 7);

        // fake match so player.getMatchPlayer() works inside AI simulations
        MatchOptions matchOptions = new MatchOptions("sim match", "sim game type", true);
        Match match = new FreeForAllMatch(matchOptions);

        Player player1 = PlayerFactory.create(cfg.player1, cfg.name1, cfg.skill1, cfg.thinkTimeSecs);
        Player player2 = PlayerFactory.create(cfg.player2, cfg.name2, cfg.skill2, cfg.thinkTimeSecs);
        addPlayer(game, match, player1, cfg.deck1);
        addPlayer(game, match, player2, cfg.deck2);

        FeatureCollector collector = null;
        if (cfg.featuresOut != null) {
            collector = new FeatureCollector(player1.getId(), player2.getId());
            PlayerFactory.attachCollector(player1, collector);
            PlayerFactory.attachCollector(player2, collector);
        }

        GameOptions options = new GameOptions();
        options.stopOnTurn = cfg.maxTurns; // with default stopAtStep=UNTAP this ends the game as a draw
        game.setGameOptions(options);

        // alternate who gets the "choose starting player" decision to balance play/draw
        Player choosing = (gameIndex % 2 == 0) ? player1 : player2;
        result.firstChoice = choosing.getName();

        long t0 = System.currentTimeMillis();
        game.start(choosing.getId());
        result.durationMs = System.currentTimeMillis() - t0;

        result.turns = game.getTurnNum();
        result.life1 = game.getPlayer(player1.getId()).getLife();
        result.life2 = game.getPlayer(player2.getId()).getLife();
        if (game.getPlayer(player1.getId()).hasWon()) {
            result.winner = player1.getName();
            result.endReason = "game_over";
        } else if (game.getPlayer(player2.getId()).hasWon()) {
            result.winner = player2.getName();
            result.endReason = "game_over";
        } else {
            result.winner = "draw";
            result.endReason = game.hasEnded() ? "game_over" : "max_turns";
        }
        if (collector != null) {
            result.featureRows = collector.getRows();
        }
        return result;
    }

    private void addPlayer(Game game, Match match, Player player, String deckFile) throws Exception {
        DeckCardLists list = DeckImporter.importDeckFromFile(deckFile, false);
        Deck deck = Deck.load(list, false, false);
        if (deck.getMaindeckCards().size() < 40) {
            throw new IllegalArgumentException("Could not load deck '" + deckFile
                    + "', main deck size = " + deck.getMaindeckCards().size()
                    + " (card database missing or deck file invalid?)");
        }
        game.loadCards(deck.getCards(), player.getId());
        game.loadCards(deck.getSideboard(), player.getId());
        game.addPlayer(player, deck);
        match.addPlayer(player, deck);
    }
}
