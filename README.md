# What is *polarity*?
Polarity creates visually pleasing polar charts for NBA players. Quantify a player's performance across points, rebounds, assists, steals, STOCKS (steals + blocks), and true shooting percentage in a single glance!

## Features
- **Single mode** — view one player's game performance as a radar chart, normalized against the game's top performers
- **Flux mode** — overlay two players' radar charts for direct visual comparison
- **Date search** — look up any specific game from the current or past seasons
- **Team-colored charts** — each player's radar is styled with their team's official color
- **Detail tables** — raw stat values and game highs displayed alongside the chart

    
## Setup
```bash
git clone https://github.com/mplshassan/polarity
cd polarity
pip install -r requirements.txt
streamlit run app.py
```

## Usage:
1. Select Single or Flux mode in the sidebar

2. Enter a player name (use standard NBA spelling, e.g. "Anthony Edwards")

3. Optionally check "Search specific date" to look up a past game

4. Click Pull Stats

5. Hover over the radar chart for detailed values

## Credits

Built by Mustafa Hassan; powered by the nba_api package.
