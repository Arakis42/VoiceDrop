# 02 — KI-Analyse

## Klassenhierarchie

```
mage.players.PlayerImpl                      (Engine, Mage)
└── mage.player.ai.ComputerPlayer            (Mage.Player.AI — "Basis-Bot")
    ├── mage.player.ai.ComputerPlayer6       (Mage.Player.AI.MA — Minimax "mad", Kern)
    │   └── mage.player.ai.ComputerPlayer7   (aktuelle "mad"-Version, Step-Steuerung)
    │       └── ComputerPlayerControllableProxy  (Server-Eintrag für "Computer - mad";
    │                                             erlaubt Übernahme durch Menschen)
    ├── mage.player.ai.SimulatedPlayer2      (Ersatzspieler INNERHALB der Simulationen)
    ├── mage.player.ai.ComputerPlayerMCTS    (Mage.Player.AIMCTS — "Computer - monte carlo")
    │   └── MCTSPlayer / SimulatedPlayerMCTS (Rollout-Spieler)
    └── mage.player.ai.ComputerDraftPlayer   (Mage.Player.AI.DraftBot — nur Draft-Picks)
```

Skill-Level (1–8, UI) wirkt bei „mad“ auf: `maxDepth` (= skill, min. 4) und
`maxThinkTimeSecs` (= skill × 3). `maxNodes` ist fix 5000 pro Berechnung
(`ComputerPlayer6.java:54`, Konstruktor `:92`).

## 1. `ComputerPlayer` (Basis, `Mage.Player.AI`)

Zweck laut Kommentar: *„minimum implementation of all choose dialogs to allow AI
to start and finish a real game“*. Wichtig:

- `priority()` **passt immer** (`ComputerPlayer.java:387`) — allein spielt dieser
  Bot also gar nichts; die Spiel-Logik kommt erst in CP6/7.
- Implementiert dafür **alle Auswahl-Dialoge heuristisch**: Ziele
  (`chooseTarget`, mit `PossibleTargetsSelector`/`PossibleTargetsComparator`:
  gute/schlechte Ziele je nach Outcome, Kill-Priorität bei Schaden),
  Mana-Bezahlung (`playMana`), Mulligan (`chooseMulligan`: < 2 oder fast nur
  Länder), Modi (`chooseMode`), Reihenfolge von Triggern, X-Werte
  (`announceX`), Ersatzeffekte, Haufen-Wahl, usw.
- Außerdem: Deckbau (`buildDeck`), Draft-Picks (`pickCard` mit `RateCard`),
  Sideboarding (rudimentär).
- **Konsequenz:** Selbst wenn CP7 die "richtige" Aktion per Simulation findet,
  werden viele Detail-Entscheidungen (Ziele von Triggern, Auswahlen während der
  Resolution, Discards, …) von diesen einfachen Heuristiken getroffen —
  eine große, unsichtbare Fehlerquelle.

## 2. `ComputerPlayer6/7` — „Computer — mad“ (die Haupt-KI)

Dateien: `Mage.Server.Plugins/Mage.Player.AI.MA/src/mage/player/ai/`
(`ComputerPlayer6.java` ~1355 Zeilen, `ComputerPlayer7.java`, `SimulatedPlayer2.java`,
`SimulationNode2.java`, `score/GameStateEvaluator2.java`, `score/ArtificialScoringSystem.java`).

### Wie sie denkt (CP7 → CP6)

1. `priority(game)` (`ComputerPlayer7.java:38`): Nur in **Main 1, Declare Attackers,
   Declare Blockers, Main 2** wird gerechnet; in Upkeep/Draw/Damage/End wird gepasst.
2. `calculateActions()` (`ComputerPlayer7.java:113`): kopiert das Spiel
   (`createSimulation`, ersetzt **alle** Spieler durch `SimulatedPlayer2`,
   `ComputerPlayer6.java:1205`), baut einen Simulationsbaum (`SimulationNode2`)
   und ruft `addActionsTimed()` mit Timeout (`maxThinkTimeSecs`).
3. `addActions()` + `minimaxAB()` (`ComputerPlayer6.java:206,335`): klassisches
   **Minimax mit Alpha-Beta**, Tiefe `maxDepth` (Skill), Abbruch bei `maxNodes`
   (5000), Timeout oder Spielende. Blattbewertung: `GameStateEvaluator2`.
4. `simulatePriority()` (`SimulatedPlayer2.java:76`): enumeriert pro Knoten alle
   spielbaren Abilities inkl. **aller Zieloptionen** und X-Werte
   (`getPlayableOptions`, `addVariableXOptions`), plus „Pass“.
   `optimizeOptions()` filtert offensichtlich sinnlose Ziele (gute Effekte nicht
   auf Gegner, schlechte nicht auf sich selbst).
   `TreeOptimizer` (Paket `ma/optimizers/`) streicht weitere Aktionen:
   `DiscardCardOptimizer`, `EquipOptimizer`, `LevelUpOptimizer`, `OutcomeOptimizer`,
   `WrongCodeUsageOptimizer`.
5. Die beste Aktionskette wird gemerkt und in `act()` abgespielt; bei
   Zustandsänderung wird neu gerechnet (`getNextAction`, Hash-Vergleich des
   Spielzustands). Gegen Endlosschleifen gibt es einen `actionCache` (gleiche
   kostenlose Aktion nicht zweimal) und eine `PASSIVITY_PENALTY` (−5) fürs Passen.

### Kampf: NICHT simuliert! (wichtigste Einzelschwäche)

`selectAttackers`/`selectBlockers` (`ComputerPlayer6.java:1019–1197`) nutzen
**reine Heuristiken**, nicht den Minimax:

- Kommentar im Code: `// The sim minmax does not work at the moment.` und
  `// TODO: add game simulations here to find best attackers/blockers combination`
- Ablauf Angriff: (1) „Alpha Strike“, wenn `CombatUtil.canKillOpponent(...)`;
  (2) sonst nur „sichere“ Angreifer (können nicht sterben — grob über P/T +
  ein paar Keywords wie Flying/Deathtouch/First Strike geprüft);
  (3) Planeswalker/Battles vor Spieler.
- Blocken analog heuristisch über `CombatUtil`/`CombatInfo`.
- `SimulatedPlayer2.addAttackers()` (Powerset aller Angreifer, 2^n Kombinationen!)
  und `addBlockers()` existieren zwar für die Simulation, werden aber im echten
  Kampfentscheid nicht wirksam genutzt — und würden ohnehin exponentiell explodieren.

**Folgen im Spiel:** kein Anreiz-Angriff („attack into open board“ nur wenn
„sicher“), kein Chump-Block-Kalkül, keine Kombat-Tricks-Antizipation, kein
Attackieren zum Erzwingen schlechter Blocks, Planeswalker-Verteidigung schwach.

### Bewertungsfunktion (`GameStateEvaluator2` + `ArtificialScoringSystem`)

Score = (eigenes Leben − Gegnerleben, nichtlinear via `LIFE_SCORES`-Tabelle)
+ (eigene Permanents − gegnerische) + (Handkarten × 5 − gegnerische Handkarten × 5).

Permanent-Score (`ArtificialScoringSystem`):
- `getCardDefinitionScore`: **`int value = 3; //TODO: add new rating system card value`**
  → jede Nichtland-Karte ist pauschal gleich viel „wert“; nur Manakosten, P/T und
  Seltenheit modifizieren leicht. Die KI kennt also keinen Unterschied zwischen
  einer schwachen und einer starken Karte gleicher Kosten.
- `getDynamicPermanentScore`: Power × 300 + Toughness × 200 + Ability-Scores
  (`MagicAbility`-Tabelle: Flying=17, Deathtouch=17, Trample=13, …), Auren/Equipment,
  Counter, Schaden.
- `getCombatPermanentScore`: kleine Mali für getappt/kann nicht angreifen/blocken.
- Handkarten pauschal 5 Punkte — egal welche Karte (TODO im Code beschreibt
  genau das Problem inkl. Lösungsidee mit Zonen-Multiplikatoren).
- **Nur 2-Spieler**: `// This evaluator is only good for two player games`
  (`GameStateEvaluator2.java:16`) — es wird schlicht der erste Gegner bewertet.
  Für Commander-FFA & Co. ist die Bewertung damit strukturell falsch.

### Perfekte Information (Cheating by design)

`createSimulationForAI()` kopiert den **kompletten** Spielzustand — inklusive
gegnerischer Hand und Bibliotheksreihenfolge. `SimulatedPlayer2` enumeriert für
den Gegner dessen tatsächlich spielbare Karten. Der „mad“-Bot plant also gegen
die echte gegnerische Hand (für Auto-Battle-Fairness egal, solange beide Seiten
gleich cheaten — aber es verzerrt Deckvergleiche mit viel verdeckter Information).

### Weitere Limits (aus Code-Kommentaren/TODOs)

- Trigger mit mehreren Optionen werden simuliert, aber das Ergebnis wird nicht
  genutzt: `// TODO: AI run all sims, but do not use best option for triggers yet`
  (`SimulatedPlayer2.java:331`).
- Instant-Spiel in gegnerischen Zügen ist stark eingeschränkt (CP7 rechnet nur in
  den eigenen 4 Steps; in fremden Zügen wird meist gepasst).
- `maxNodes=5000` ist schnell erschöpft (TODO fragt selbst, ob 50000 besser wäre).
- Timeout-Verhalten: bei Überschreitung passiert einfach nichts
  (`SimulationPerformanceAITest`-Kommentar: „AI fail on time out and do nothing“).
- Ein Thread pro Berechnung, Aktionen sequenziell:
  `// TODO: rework AI implementation to use multiple sims calculation instead one by one`
  (`ComputerPlayer.java:67`), Pool `COMPUTER_MAX_THREADS_FOR_SIMULATIONS = 5`.

## 3. `ComputerPlayerMCTS` — „Computer — monte carlo“

Dateien: `Mage.Server.Plugins/Mage.Player.AIMCTS/src/mage/player/ai/`.

- Klassisches **MCTS**: `MCTSNode` (UCT, `select`/`expand`/`simulate`/`backpropagate`),
  Rollouts mit `SimulatedPlayerMCTS` (spielt **zufällige** Aktionen bis Spielende),
  Belohnung = Sieg/Niederlage.
- Multi-threaded (Root-Parallelisierung: ein Baum pro Thread, danach `merge`),
  Denkzeit = `skill × 2` Sekunden, Aktions-Cache optional.
- **Verdeckte Information wird korrekt behandelt**: `createMCTSGame()`
  (`ComputerPlayerMCTS.java:298`) mischt die gegnerische Hand zurück in die
  Bibliothek und zieht neu (Determinisierung) und mischt die eigene Bibliothek.
  Konzeptionell sauberer als der „mad“-Bot!
- Entscheidet auch **Angriff und Block** über den Baum
  (`SELECT_ATTACKERS`/`SELECT_BLOCKERS` als eigene Knotentypen).
- Praxisstatus: experimentell; zufällige Rollouts sind bei MTG-Verzweigungsgrad
  extrem verrauscht, Spielstärke daher gering; im Server zwar konfiguriert,
  aber die Community nutzt praktisch nur „mad“.

## 4. `ComputerDraftPlayer` (DraftBot)

Nur für Drafts (`PlayerType.COMPUTER_DRAFT_BOT`, `isWorkablePlayer=false`).
Nutzt `RateCard` (`Mage.Common/src/main/java/mage/cards/RateCard.java`):
CSV-Ratings pro Set unter `resources/ratings/` + Bonuspunkte für Removal/Typen —
**diese Kartenbewertung wird im normalen Spiel nicht verwendet** (Ansatzpunkt!).

## Schwächen-Ranking (für Auto-Battle-Zwecke)

1. **Kampfentscheidungen ohne Simulation** — verliert Spiele in Board-Stall- und
   Race-Situationen; für Deck-Simulationen verzerrend, weil aggro-lastige Decks
   systematisch falsch bewertet werden.
2. **Kartenwert-blinde Evaluation** (Fixwert 3 + Hand=5/Karte) — Mulligan-,
   Discard-, Tausch-Entscheidungen („2 Karten für 1“) sind wertfrei.
3. **Kein Instant-/Reaktionsspiel in fremden Zügen** (CP7-Step-Whitelist).
4. **Horizonteffekt**: Tiefe 4–8 Prioritäten ≠ 1 Zug; Züge des Gegners werden mit
   „passen bis Stack leer“ abgekürzt (`simulatePriority`-Workaround in CP6:556).
5. **Node-/Zeitbudget klein**, single-threaded pro Entscheidung.
6. **Multiplayer-Bewertung fehlt** komplett.
7. Trigger-/Resolution-Entscheidungen fallen auf Basis-Heuristiken zurück.
