# Mage.Simulator — Headless Auto-Battle (KI gegen KI)

Batch-Simulator für Deck-Tests: spielt N komplette Spiele `ComputerPlayer7` gegen
`ComputerPlayer7` ohne Server/Client, schreibt ein JSONL-Ergebnis pro Spiel und
eine Zusammenfassung (Winrate mit 95%-Konfidenzintervall).

## Voraussetzungen

Einmalig alle mage-Artefakte ins lokale Maven-Repo installieren:

```bash
cd ..            # mage-Wurzel
mvn -DskipTests install
```

## Benutzung

```bash
cd Mage.Simulator
mvn -q package
mvn -q exec:java -Dexec.args="--deck1 decks/mono_red_aggro.txt --deck2 decks/mono_green_stompy.txt --games 10 --skill 5 --seed 42 --out results.jsonl"
```

Verifizierter Beispiel-Lauf (Skill 4, Seed 42):

```
game 1/3: winner=AI_2, turns=14, life=-4/6, 1805 ms (game_over)
game 2/3: winner=AI_2, turns=21, life=-7/5, 2834 ms (game_over)
game 3/3: winner=AI_1, turns=21, life=1/-3, 1076 ms (game_over)
deck1 winrate (of decided): 33.3% [95% CI 6.1%..79.2%]
```

**Achtung Deck-Format:** `.txt` = Kartenname-basiert (`4 Lightning Bolt`),
`.dck` = XMage-Format mit Set-Codes. Das in `Mage.Tests/` liegende
`RB Aggro.dck` ist ein 71-Mountain-Dummy (Unit-Tests ersetzen die Library) —
nicht für Simulationen verwenden. Zwei spielbare Demo-Decks liegen in `decks/`.

Optionen: `--games N`, `--skill N` (1–8, beide), `--skill1/--skill2` (A/B-Test),
`--player1/--player2 TYP` (`mad` = volle KI, `basic` = Goldfish, spielt nichts),
`--thinkTime S` (Denkzeit-Limit pro Entscheidung, Default skill×3),
`--seed N` (Spiel i nutzt seed+i), `--maxTurns N` (Abbruch als Draw, Default 60),
`--out DATEI`, `--features DATEI` (Trainingsdaten: ein Feature-Vektor pro Zug
mit Spielausgang, JSONL), `--verbose` (KI-Logs).

Weitere Modi:

```bash
# Synergie-Report für ein Deck (produces/consumes-Tags, aktive Synergie-Paare)
mvn -q exec:java -Dexec.args="--tags decks/synergy_lifegain.txt"

# Goldfish-Test: Wie schnell tötet Deck A einen passiven Gegner? (kill turn)
mvn -q exec:java -Dexec.args="--deck1 decks/mono_red_aggro.txt --deck2 decks/mono_green_stompy.txt --player2 basic --games 20 --skill 4"
```

Beim ersten Lauf wird die Karten-Datenbank gebaut (`CardScanner.scan()`, dauert
einige Minuten, legt `db/` im Arbeitsverzeichnis an).

## Ausgabe

`results.jsonl`, eine Zeile pro Spiel:

```json
{"game":0,"seed":42,"deck1":"…","deck2":"…","first_choice":"AI_1","winner":"AI_2","turns":11,"life1":0,"life2":14,"duration_ms":63210,"end_reason":"game_over"}
```

`winner` ist `AI_1`/`AI_2`/`draw`/`error`; `end_reason` `game_over`, `max_turns`
(Abbruch durch `--maxTurns`) oder `error`.

## Design-Notizen

- Nutzt dieselben Bausteine wie das Unit-Test-Framework (`CardTestPlayerBaseAI`):
  `TwoPlayerDuel`, `ComputerPlayer7`, Fake-`Match` (für `MatchPlayer`-Verdrahtung),
  `GameOptions.stopOnTurn` als Notbremse.
- Jedes Spiel läuft in einem eigenen Thread mit `GAME`-Namenspräfix — die Engine
  erzwingt das (`ThreadUtils.ensureRunInGameThread`).
- Play/Draw-Balance: die „Wer beginnt?“-Entscheidung wechselt pro Spiel.
- Bewusst sequenziell: der KI-interne Simulations-Threadpool ist eine geteilte
  statische Ressource (`COMPUTER_MAX_THREADS_FOR_SIMULATIONS = 5`). Parallelität
  besser über mehrere JVM-Prozesse (verschiedene `--seed`-Bereiche, gleiche Decks).
- Mulligans sind aktiv (Spieler laufen nicht im Test-Modus).

## Umgesetzte Backlog-Items

- **0.1** CLI-Runner (verifiziert, s.o.)
- **0.2** Spieler-Typen pro Seite: `--player1/--player2 mad|basic`
  (verifiziert: mad vs. basic = 2:0 in 11/14 Zügen — Kill-Turn-Messung)
- **0.3** Feature-Logger: `--features f.jsonl`, ein flacher Feature-Vektor pro Zug
  (Leben, Hand, Library, Friedhof, Länder/untapped, Kreaturen, Power/Toughness
  beider Spieler) + `p1_won`-Label — direkt ML-tauglich
- **2.1 (v1)** Synergie-Tagging: `--tags deck.txt` — produces/consumes-Tags pro
  Karte via Regeltext-Analyse (`mage.simulator.synergy`), Report mit aktiven
  Synergie-Paaren. Verifiziert an Lifegain-Kette (Soul Warden → Ajani's Pridemate).
  Bekannte v1-Lücke: modale Effekte (z.B. Healing Salve) werden noch nicht erkannt —
  schließbar über externe Tags (s.u.).
- **2.2** SynergyScorer: Spielertyp `mad-synergy` (Synergie-Bewertung in
  `GameStateEvaluator2` via ExtraScorer-Hook, Patch in `patches/`).
  **Lehrstück in Messdisziplin:** v1 (Bonus für liegende Producer/Consumer-Paare)
  verlor die A/B-Messung **9:21 (30%, CI 17–48%)** gegen die Standard-KI —
  der Bonus verzerrte Kampf-Trades und belohnte vergangene Einmal-Events.
  v2 („realisierte Synergie“: Producer in Feld+Friedhof zählen, monoton →
  Casten wird belohnt, Trades nicht bestraft): 30 Spiele **16:14 (53%)**,
  100 Spiele **48:52 (48%, CI 38.5–57.7%)** — Regression behoben, Effekt auf
  dem kleinen Lifegain-Testdeck statistisch **neutral**. Fazit: Das Testdeck
  bietet zu wenig Entscheidungsspielraum (beide KIs spielen fast identisch);
  nächster Messschritt sind Synergie-Decks mit echten Sequencing-Entscheidungen
  (Sacrifice/Tokens) oder die Integration erst nach dem Evaluator-Umbau (Phase 1).
- **ExternalTags** (Scryfall-Tagger-Anbindung, offline): `tags/external_tags.csv`
  (`Kartenname;otag1,otag2`) wird beim Start geladen; kuratiertes Mapping
  otag→SynergyTag in `ExternalTags.java`. Verifiziert: Healing Salve bekommt via
  externem `lifegain`-Tag korrekt `LIFE_GAINED`. Datenquelle: Scryfall-Suche
  unterstützt `otag:`-Queries (`api.scryfall.com/cards/search?q=otag:lifegain`,
  Rate-Limits beachten) oder Community-Dumps; keine offizielle Bulk-API.

## Nächste Schritte (siehe mage-analysis/06-coding-backlog.md)

- 2.2: SynergyScore in die Bewertungsfunktion einbauen
- 1.1/1.2: GameFeatures + RaceCalculator als Evaluator-Fundament
