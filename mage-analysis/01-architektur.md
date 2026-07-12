# 01 — Architektur-Überblick

## Module (Maven Multi-Modul-Projekt)

| Modul | Zweck |
|---|---|
| `Mage` | **Engine-Kern**: Regeln, Spielzustand, Abilities, Effects, Stack, Kampf, Spieler-Interface |
| `Mage.Common` | Gemeinsamer Code Client/Server: Views (serialisierte Sichten auf den Spielzustand), Netzwerk-Interfaces, `RateCard` (Kartenbewertung für Draft) |
| `Mage.Sets` | Alle Karten-Implementierungen (>30.000 Java-Klassen, eine pro Karte) + Set-Definitionen |
| `Mage.Server` | Server: Tische, Matches, Turniere, Chat, User-Verwaltung; lädt Spielmodi/KIs als Plugins |
| `Mage.Server.Plugins/*` | Plugins: Spielmodi (TwoPlayerDuel, Commander, …), Deck-Validatoren, **KI-Spieler** (`Mage.Player.AI`, `Mage.Player.AI.MA`, `Mage.Player.AIMCTS`, `Mage.Player.AI.DraftBot`), `Mage.Player.Human` |
| `Mage.Client` | Swing-Client (UI) |
| `Mage.Server.Console` | Admin-Konsole für den Server (Swing) |
| `Mage.Tests` | **Test-Framework** — für uns zentral: Spiele laufen hier headless im Prozess, ohne Server/Client |
| `Mage.Verify` | Konsistenzprüfungen der Kartenimplementierungen gegen MTGJSON |

Build: `pom.xml` (Wurzel), Java 8 als Ziel (`<java.version>1.8</java.version>`).

## Engine-Kern (`Mage/src/main/java/mage/`)

Wichtige Pakete:

- `game/` — `Game`/`GameImpl` (zentrale Spielsteuerung), `GameState`,
  `TwoPlayerDuel` u.a. liegen als Spielmodus-Plugins in `Mage.Server.Plugins/Mage.Game.*`
- `players/` — `Player` (riesiges Interface: alle Entscheidungen, die ein Spieler
  treffen kann: `priority()`, `chooseTarget()`, `chooseUse()`, `selectAttackers()`, …),
  `PlayerImpl` (Basisimplementierung), `PlayerType` (Enum: HUMAN, COMPUTER_MAD,
  COMPUTER_MONTE_CARLO, COMPUTER_DRAFT_BOT)
- `abilities/`, `abilities/effects/` — Fähigkeiten/Effekte-System (Continuous Effects,
  Triggered/Activated Abilities, Kostensystem)
- `cards/` — Kartenmodell, `cards/decks/importer/` — **Deck-Importer** für viele Formate:
  `.dck` (XMage-eigen), `.txt`, `.dec`, `.dek`, `.cod`, `.o8d`, MTGA-Export, MTGJSON, XML
- `cards/repository/` — Karten-Datenbank (H2 via ORMLite), `CardScanner.scan()` baut
  die DB beim ersten Start auf
- `target/`, `choices/`, `filter/`, `counters/`, `watchers/` — Zielauswahl, Auswahlen,
  Filtersystem, Marken, Beobachter (für „seit letztem Zug“-Infos)

### Spielablauf (headless-relevant)

Ein Spiel ist ein **synchroner** Ablauf, kein Server nötig:

- `GameImpl.start(choosingPlayerId)` → `init()` → `play(startingPlayerId)`
  (`Mage/src/main/java/mage/game/GameImpl.java:1058`)
- `play()` ist eine simple Schleife: solange nicht `checkIfGameIsOver()`,
  spiele Züge (`playTurn`), inkl. Extra-Turns (`GameImpl.java:1067` ff.)
- Innerhalb eines Zugs wird bei jeder Priorität `player.priority(game)` aufgerufen —
  **hier hängt die gesamte KI-Logik dran** (Polymorphie über das `Player`-Interface)
- Ergebnis: `game.getWinner()` (String), `game.hasEnded()`, Turn-Zähler `game.getTurnNum()`

### Wichtige Engine-Eigenschaften für Simulationen

- **Spielzustand ist kopierbar**: `game.copy()` bzw. `game.createSimulationForAI()`
  (`GameImpl.java:269`) — darauf basiert die gesamte KI-Simulation. Der komplette
  Zustand (inkl. aller Karten) wird tief kopiert; das ist auch der Performance-Engpass.
- `GameOptions` (`Mage/src/main/java/mage/game/GameOptions.java`) steuert Testmodus:
  `testMode`, `stopOnTurn`, `stopAtStep`, `skipInitShuffling` — gemacht für
  programmatische Spiele.
- `RandomUtil.setSeed(...)` — zentraler RNG, Seeds machen Läufe reproduzierbar
  (so nutzt es der `LoadTest`).
- Bookmark/Undo-System im `GameState` (Rollback einzelner Aktionen), wird von der KI
  beim Ausprobieren von Angriffen genutzt.

## Server-Seite (nur zum Verständnis, für Simulation nicht nötig)

- `Mage.Server` lädt Spielmodi/Spielertypen aus `Mage.Server/config/config.xml`:
  ```xml
  <playerType name="Human"                jar="mage-player-human.jar"  className="mage.player.human.HumanPlayer"/>
  <playerType name="Computer - mad"       jar="mage-player-ai-ma.jar"  className="mage.player.ai.ComputerPlayerControllableProxy"/>
  <playerType name="Computer - monte carlo" jar="mage-player-aimcts.jar" className="mage.player.ai.ComputerPlayerMCTS"/>
  ```
- Ablauf: Session → Room → Table → Match → Game. KI-Spieler treten einem Tisch wie
  normale Spieler bei (`session.joinTable(..., PlayerType.COMPUTER_MAD, skill, deckList, ...)`).
- Die normale Client-UI sieht nur „Mensch erstellt Tisch und sitzt selbst drin“ vor —
  deshalb wirkt es, als gäbe es kein Computer-gegen-Computer. Per API (siehe
  `Mage.Tests/.../load/LoadTest.java:226` `playTwoAIGame`) geht es problemlos.

## Test-Framework (`Mage.Tests`) — das Herzstück für Auto-Battle

- `org.mage.test.serverside.base.impl.CardTestPlayerAPIImpl` — Basisklasse:
  erstellt Spiel + Spieler ohne Server, lädt Decks
  (`createPlayer(game, name, "RB Aggro.dck")`, Default-Deck liegt in `Mage.Tests/RB Aggro.dck`),
  `execute()` ruft direkt `currentGame.start(...)` auf (synchron im Testthread).
- `TestPlayer` (`org.mage.test.player.TestPlayer`, ~4700 Zeilen) — Wrapper um einen
  `ComputerPlayer`: führt geskriptete Aktionen aus (`castSpell`, `attack`, …) und/oder
  delegiert an die echte KI. Mit `testPlayer.setAIPlayer(true)` spielt die volle KI
  **alle** Entscheidungen.
- `CardTestPlayerBaseAI` — Spieler A (und optional B via `getFullSimulatedPlayers()`)
  laufen als **volle `ComputerPlayer7`-KI** (Skill-Level per `getSkillLevel()`, Default 6).
- `CardTestPlayerBaseWithAIHelps` — normale Skript-Tests, aber mit punktuellen
  KI-Kommandos: `aiPlayPriority(...)`, `aiPlayStep(...)` (eine Priorität / ein Step
  wird von der KI entschieden).
- **Beispiel für ein komplettes KI-gegen-KI-Spiel headless**:
  `org.mage.test.AI.basic.SimulationPerformanceAITest.test_Simple_LongGame`
  (beide Spieler AI, eigene Libraries, `setStopAt(50, ...)`, `execute()`,
  danach `currentGame.hasEnded()` / Sieger prüfbar).
- `DataCollectorServices` kann Spielhistorien speichern (in Tests via
  `DebugUtil.TESTS_DATA_COLLECTORS_ENABLE_SAVE_GAME_HISTORY`).

## Deck-Dateien

- `.dck`-Format (XMage): Zeilen wie `71 [SOM:242] Mountain`, `NAME:`-Header,
  `SB:`-Präfix für Sideboard. Import über
  `DeckImporter.importDeckFromFile(path)` → `DeckCardLists` → `Deck.load(...)`.
- Zufallsdecks für Tests: `DeckTestUtils.buildRandomDeck("GR", ...)` sowie
  `ComputerPlayer.buildDeck(...)` (einfacher Deckbauer der KI, wird auch im
  Draft/Sealed fürs Deckbauen genutzt).
