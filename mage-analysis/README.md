# XMage (magefree/mage) — Analyse für Auto-Battle / Deck-Simulation

Strukturierte Notizen zur Codebasis von https://github.com/magefree/mage
(analysiert am 2026-07-12, shallow clone des `master`-Branches).

**Ziel:** Eine Auto-Battle-/Deck-Simulation bauen (Computer gegen Computer,
viele Spiele automatisiert, Statistiken) und verstehen, warum die aktuelle
KI zu schwach ist bzw. wo man ansetzen kann.

## Wichtigste Erkenntnisse vorab (TL;DR)

1. **Computer gegen Computer existiert bereits** — nur nicht in der normalen
   Client-UI. Es gibt zwei fertige Wege:
   - **Headless über das Test-Framework** (`Mage.Tests`, ohne Server, im Prozess) —
     der beste Ausgangspunkt für eine Deck-Simulation.
   - **Über einen laufenden Server** (`LoadTest.playTwoAIGame`): zwei Spieler vom Typ
     `PlayerType.COMPUTER_MAD` an einen Tisch setzen und starten.
2. **Die stärkste KI ist „Computer — mad“** (`ComputerPlayer7`, Minimax mit
   Alpha-Beta über echte Spielsimulationen). Ihre größten Schwächen:
   - Kampf (Angreifer/Blocker) wird **nicht** simuliert, sondern nur mit einer
     groben Heuristik entschieden (im Code explizit als „sim minmax does not work
     at the moment“ markiert).
   - Die Bewertungsfunktion kennt **keine Kartenqualität** (jede Karte hat den
     Fixwert 3) und ist nur für 2-Spieler-Spiele ausgelegt.
   - Sie simuliert mit **vollständiger Information** (sieht faktisch die
     gegnerische Hand in der Simulation).
3. **Ein MCTS-Bot existiert** (`ComputerPlayerMCTS`, „Computer — monte carlo“),
   determinisiert sogar korrekt die gegnerische Hand, gilt aber als
   experimentell/instabil und wird kaum gepflegt.
4. Für eine eigene Simulation muss man **nicht den Server anfassen**: Ein Spiel ist
   ein synchroner Aufruf `game.start(playerId)`, der komplett im aufrufenden
   Thread durchläuft. Decks lassen sich aus `.dck`-Dateien laden.

## Dateien in diesem Ordner

| Datei | Inhalt |
|---|---|
| `01-architektur.md` | Modul-/Paketstruktur, Engine-Kern, Spielablauf, Test-Framework |
| `02-ki-analyse.md` | Alle KI-Implementierungen im Detail, Bewertungsfunktion, Schwächen |
| `03-auto-battle.md` | Konkrete Wege zu Computer-vs-Computer + Bauplan für einen eigenen Simulator |
| `04-verbesserungen-und-ideen.md` | Verbesserungsvorschläge für die KI + weitere Ideen |

## Hinweise

- Alle Pfadangaben sind relativ zur Repo-Wurzel des mage-Clones.
- Build: Maven, Multi-Modul (`pom.xml` in der Wurzel), Zielversion Java 8
  (`<java.version>1.8</java.version>`), läuft aber auch mit neueren JDKs.
  Achtung: `Mage.Sets` enthält >30.000 Kartenklassen — der erste Komplett-Build
  dauert lange und braucht viel Speicher.
- Es wurde nichts zum Original-Repo hochgeladen; der Clone liegt nur lokal.
