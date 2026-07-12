# 03 — Auto-Battle / Deck-Simulation: vorhandene Wege + Bauplan

## Weg A (empfohlen): Headless über das Test-Framework — kein Server

Das Test-Framework startet komplette Spiele **im Prozess**, synchron, ohne
Netzwerk. Beide Spieler können volle KI sein. Beweis im Repo:
`Mage.Tests/src/test/java/org/mage/test/AI/basic/SimulationPerformanceAITest.java`
→ `test_Simple_LongGame()` spielt bis zu 50 Züge KI gegen KI und prüft den Sieger.

Minimal-Muster:

```java
public class MyAutoBattle extends CardTestPlayerBaseAI {          // PlayerA = volle KI

    @Override
    public List<String> getFullSimulatedPlayers() {
        return Arrays.asList("PlayerA", "PlayerB");               // beide Spieler = volle KI
    }

    @Override
    public int getSkillLevel() { return 6; }                      // Tiefe/Denkzeit

    @Test
    public void deckAvsDeckB() {
        // Standard: beide bekommen "RB Aggro.dck"; andere Decks über
        // createPlayer(game, "PlayerA", "meinDeck.dck") in createNewGameAndPlayers()
        setStrictChooseMode(true);
        setStopAt(100, PhaseStep.END_TURN);                       // Sicherheits-Limit
        execute();
        // Ergebnis: currentGame.hasEnded(), currentGame.getWinner(), currentGame.getTurnNum()
    }
}
```

Relevante Bausteine:

- `CardTestPlayerBaseAI` (`org.mage.test.serverside.base`) — erzeugt `TwoPlayerDuel`
  (60 Karten, 20 Leben, 7 Handkarten) und `TestPlayer`, der an `TestComputerPlayer7`
  delegiert; `testPlayer.setAIPlayer(true)` aktiviert KI für **alle** Entscheidungen.
- Deck laden: `CardTestPlayerAPIImpl.createPlayer(game, name, "X.dck")` →
  `DeckImporter.importDeckFromFile(...)`. Beispieldecks liegen in `Mage.Tests/`
  (`RB Aggro.dck`, `CommanderDuel_*.dck`, …).
- `execute()` → `currentGame.start(...)`; danach ist der komplette Endzustand
  abfragbar (Leben, Friedhöfe, Züge, Sieger).
- Mulligan ist im Testmodus abgeschaltet (`ComputerPlayer.chooseMulligan`:
  `isTestMode() → false`) — für realistische Simulationen ggf. ändern.
- Karten-DB: beim ersten Lauf baut `CardScanner.scan()` die H2-Datenbank auf
  (dauert einmalig einige Minuten).

Ausführen: `mvn test -pl Mage.Tests -Dtest=MyAutoBattle` (Abhängigkeiten vorher
einmal mit `mvn install -DskipTests` bauen).

### Vom JUnit-Test zum echten Simulator

Für Massen-Simulationen sollte man den JUnit-Rahmen abstreifen und die gleichen
Bausteine direkt verwenden (eigene `main()`-Klasse, z.B. als neues Modul
`Mage.Simulator` neben `Mage.Tests`):

1. `CardScanner.scan()` einmalig (Karten-DB).
2. Pro Spiel:
   - `Game game = new TwoPlayerDuel(MultiplayerAttackOption.LEFT, RangeOfInfluence.ONE, MulliganType.GAME_DEFAULT.getMulligan(0), 60, 20, 7);`
   - Zwei Spieler erzeugen — direkt `ComputerPlayer7("ai1", RangeOfInfluence.ONE, skill)`
     (der `TestPlayer`-Wrapper ist nur nötig, wenn man geskriptete Aktionen mischen will),
   - Deck laden: `DeckImporter.importDeckFromFile(path)` → `Deck.load(list, false, false, cardInfo)`
     → `game.loadCards(deck.getCards(), player.getId())` → `game.addPlayer(player, deck)`,
   - `GameOptions` setzen (`testMode=true`, optional `stopOnTurn` als Notbremse),
   - `game.start(startingPlayerId)` — blockiert bis Spielende,
   - Ergebnis einsammeln: Sieger, Zuganzahl, Restleben, ggf. Spielverlauf.
3. Seeds: `RandomUtil.setSeed(n)` vor jedem Spiel für Reproduzierbarkeit;
   Startspieler abwechseln (Play/Draw-Bias!).
4. Parallelisierung: mehrere Spiele in parallelen Threads sind möglich
   (der Server macht das auch), aber Achtung: der KI-interne Simulations-Pool ist
   global auf 5 Threads begrenzt (`COMPUTER_MAX_THREADS_FOR_SIMULATIONS`) und die
   Spiele sind CPU-hungrig → eher N Spiele parallel mit Skill runter, oder
   mehrere JVM-Prozesse.
5. Statistik über viele Spiele: Winrate + Konfidenzintervall (bei ~55/45-Fragen
   braucht man hunderte Spiele), Median-Zuglänge, Mulligan-/Screw-Quoten (wenn
   man Mulligans aktiviert), Verteilung „Sieg durch Lebenspunkte/Decking/Konzession“.

### Praktische Fallstricke

- **Denkzeit**: Skill 6 ⇒ bis zu 18 s pro Entscheidung (Timeout). In zähen
  Board-States kann ein einziges Spiel Minuten dauern. Für Massensimulation:
  Skill 4–5, oder `setMaxThinkTimeSecs(...)` (öffentlich, `ComputerPlayer6.java:120`).
- **Freezes/Endlosspiele**: immer `stopOnTurn` setzen; der LoadTest protokolliert
  eingefrorene Spiele als bekanntes Phänomen (`test_TwoAIPlayGame_Debug` existiert
  extra dafür).
- **Fehler in Simulationen**: In Tests wirft die KI Simulationsfehler als Exception
  (fast-fail), im „echten“ Modus werden sie nur geloggt (`addActionsTimed`,
  `ComputerPlayer6.java:470`).
- **Speicher**: jede simulierte Aktion = tiefe Game-Kopie; JVM mit genug Heap starten.

## Weg B: Über einen laufenden Server (wie `LoadTest`)

`Mage.Tests/src/test/java/org/mage/test/load/LoadTest.java`:

- `playTwoAIGame(...)` (`:226`): verbindet sich als „Monitor“-Client, erstellt einen
  Tisch (`session.createTable`), setzt **zwei** Spieler vom Typ
  `PlayerType.COMPUTER_MAD` mit Decks hinein (`session.joinTable(...)`), startet das
  Match (`session.startMatch`) und pollt den Spielzustand bis `TableState.FINISHED`.
- `test_TwoAIPlayGame_One` / `_Multiple` (`:339,377`): 1 bzw. N solcher Spiele,
  mit Seeds, Zufallsdecks (`DeckTestUtils.buildRandomDeck`) oder festen
  `.dck`-Dateien (`TEST_AI_CUSTOM_DECK_PATH_1/2`), Ergebnis-Tabelle am Ende.
- Voraussetzung: Server läuft separat (localhost:17171).

Sinnvoll, wenn man das Spiel **zuschauen** will (man kann sich mit dem normalen
Client als Watcher verbinden) oder Server-Verhalten testen will. Für reine
Deck-Statistik ist Weg A schneller und robuster.

## Weg C: Punktuelle KI in Skript-Tests (`CardTestPlayerBaseWithAIHelps`)

`aiPlayPriority(turn, step, player)` / `aiPlayStep(turn, step, player)` lassen die
KI genau eine Priorität/einen Step spielen, der Rest ist geskriptet. Gut, um
KI-Verhalten in konstruierten Situationen zu debuggen (so sind die Tests unter
`org.mage.test.AI.basic.*` gebaut).

## Empfehlung

1. **Kurzfristig**: Eigenes Modul `Mage.Simulator` (Weg A ohne JUnit) mit CLI:
   `simulator --deck1 a.dck --deck2 b.dck --games 200 --skill 5 --seed 42 --maxTurns 60 --out results.json`.
2. **Ergebnisse als JSON/CSV** pro Spiel (Seed, Sieger, Züge, Endleben,
   Spiellog-Pfad) — daraus Winrate-Matrix über mehrere Decks.
3. **Danach** gezielt KI-Schwächen angehen (siehe `04-verbesserungen-und-ideen.md`),
   denn: Deck-Winrates sind nur so aussagekräftig wie die KI, die die Decks pilotiert.
   Fürs Ranking ähnlicher Decks reicht die „mad“-KI aber oft schon, weil beide
   Seiten gleich (schlecht) spielen.
