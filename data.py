import time
from datetime import datetime
from difflib import get_close_matches

import pandas as pd
import streamlit as st
from nba_api.live.nba.endpoints import boxscore, scoreboard
from nba_api.stats.endpoints import BoxScoreTraditionalV3, PlayerGameLog
from nba_api.stats.static import players

# config
TIMEOUT = 60
MAX_RETRIES = 3
RETRY_DELAY = 2

SEASON_TYPES = [
    "Regular Season",
    "Playoffs",
]


# utilities
def calculate_ts_pct(pts, fga, fta):
    denom = 2 * (fga + 0.44 * fta)
    return pts / denom if denom else 0.0


def get_current_season():
    now = datetime.now()
    year = now.year
    return (
        f"{year - 1}-{str(year)[-2:]}"
        if now.month < 10
        else f"{year}-{str(year + 1)[-2:]}"
    )


def date_to_season(date_obj):
    year = date_obj.year
    return (
        f"{year}-{str(year + 1)[-2:]}"
        if date_obj.month >= 10
        else f"{year - 1}-{str(year)[-2:]}"
    )


def _retry_call(func, *args, **kwargs):
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)
    raise last_err


# cached fetches
@st.cache_data(ttl=3600, show_spinner=False)
def get_all_players():
    return players.get_players()


def get_player_id(name, player_list):
    if not name or not name.strip():
        return None, None
    names = [p["full_name"] for p in player_list]
    matches = get_close_matches(name.strip(), names, n=1, cutoff=0.6)
    if not matches:
        return None, None
    for p in player_list:
        if p["full_name"] == matches[0]:
            return p["id"], matches[0]
    return None, None


def _fetch_season_games(player_id, season):
    frames = []
    for stype in SEASON_TYPES:
        try:
            log = _retry_call(
                PlayerGameLog,
                player_id=player_id,
                season=season,
                season_type_all_star=stype,
                timeout=TIMEOUT,
            )
            df = log.get_data_frames()[0]
            if not df.empty:
                df["SEASON_TYPE"] = stype
                df["MATCH_DATE"] = pd.to_datetime(df["GAME_DATE"]).dt.date
                frames.append(df)
            time.sleep(0.3)
        except Exception as e:
            print(f"[_fetch_season_games] season={season} type={stype} error: {e}")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def get_game_stats(player_id, date_obj=None):
    if date_obj:
        season = date_to_season(date_obj)
        target_date = pd.to_datetime(date_obj).date()
        df = _fetch_season_games(player_id, season)
        if df.empty:
            return None
        mask = df["MATCH_DATE"] == target_date
        return df[mask].iloc[0] if mask.any() else None

    current = get_current_season()
    current_year = int(current.split("-")[0])
    seasons = [f"{y}-{str(y + 1)[-2:]}" for y in range(current_year, 1946, -1)]

    for season in seasons:
        df = _fetch_season_games(player_id, season)
        if not df.empty:
            return df.sort_values("MATCH_DATE", ascending=False).iloc[0]

    return None


# no cache — always fresh for live data
def get_live_game_stats(player_id):
    """Returns live game stats for a player if they have a game today, else None."""
    try:
        today = scoreboard.ScoreBoard()
        games = today.get_dict()["scoreboard"]["games"]
    except Exception as e:
        print(f"[get_live_game_stats] scoreboard error: {e}")
        return None

    for game in games:
        game_id = game["gameId"]
        game_status_text = game.get("gameStatusText", "")
        game_status = game.get("gameStatus", 1)  # 1=scheduled, 2=live, 3=final

        # pull scores from scoreboard — more reliable than boxscore on cloud
        home_tri = game.get("homeTeam", {}).get("teamTricode", "")
        away_tri = game.get("awayTeam", {}).get("teamTricode", "")
        home_score = game.get("homeTeam", {}).get("score", 0)
        away_score = game.get("awayTeam", {}).get("score", 0)

        try:
            bs = boxscore.BoxScore(game_id=game_id)
            bs_data = bs.get_dict()
            if "game" not in bs_data:
                continue
            bs_dict = bs_data["game"]
            if not home_tri:
                home_tri = bs_dict["homeTeam"]["teamTricode"]
            if not away_tri:
                away_tri = bs_dict["awayTeam"]["teamTricode"]
            for team_side in ["homeTeam", "awayTeam"]:
                if team_side not in bs_dict:
                    continue
                for player in bs_dict[team_side].get("players", []):
                    if str(player.get("personId", "")) == str(player_id):
                        s = player["statistics"]
                        matchup = f"{away_tri} @ {home_tri}"
                        return {
                            "PTS": float(s.get("points", 0)),
                            "REB": float(s.get("reboundsTotal", 0)),
                            "AST": float(s.get("assists", 0)),
                            "STL": float(s.get("steals", 0)),
                            "BLK": float(s.get("blocks", 0)),
                            "FGA": float(s.get("fieldGoalsAttempted", 0)),
                            "FTA": float(s.get("freeThrowsAttempted", 0)),
                            "Game_ID": game_id,
                            "MATCHUP": matchup,
                            "GAME_DATE": datetime.now().strftime("%Y-%m-%d"),
                            "LIVE": True,
                            "GAME_STATUS": game_status_text,
                            "GAME_STATUS_CODE": game_status,
                            "HOME_TRICODE": home_tri,
                            "AWAY_TRICODE": away_tri,
                            "HOME_SCORE": home_score,
                            "AWAY_SCORE": away_score,
                        }
        except Exception as e:
            print(f"[get_live_game_stats] boxscore error game={game_id}: {e}")
            continue

    return None


def get_live_game_highs(game_id):
    """Compute per-game highs from the live boxscore endpoint."""
    try:
        bs = boxscore.BoxScore(game_id=game_id)
        bs_data = bs.get_dict()
        if "game" not in bs_data:
            return None
        bs_dict = bs_data["game"]
    except Exception as e:
        print(f"[get_live_game_highs] error: {e}")
        return None

    all_players = []
    for team_side in ["homeTeam", "awayTeam"]:
        if team_side in bs_dict:
            all_players.extend(bs_dict[team_side].get("players", []))

    rows = []
    for p in all_players:
        s = p.get("statistics", {})
        # only include players with meaningful minutes
        mins_str = s.get("minutesCalculated", "PT0M")
        try:
            mins = float(mins_str.replace("PT", "").replace("M", ""))
        except ValueError:
            mins = 0.0
        if mins < 10:
            continue
        pts = float(s.get("points", 0))
        fga = float(s.get("fieldGoalsAttempted", 0))
        fta = float(s.get("freeThrowsAttempted", 0))
        rows.append(
            {
                "PTS": pts,
                "REB": float(s.get("reboundsTotal", 0)),
                "AST": float(s.get("assists", 0)),
                "STOCKS": float(s.get("steals", 0)) + float(s.get("blocks", 0)),
                "TS%": calculate_ts_pct(pts, fga, fta),
            }
        )

    if not rows:
        return None

    df = pd.DataFrame(rows)
    return {
        "PTS": df["PTS"].max(),
        "REB": df["REB"].max(),
        "AST": df["AST"].max(),
        "STOCKS": df["STOCKS"].max(),
        "TS%": df["TS%"].max(),
    }


@st.cache_data(ttl=300, show_spinner=False)
def get_game_highs(game_id):
    try:
        bs = _retry_call(
            BoxScoreTraditionalV3,
            game_id=game_id,
            timeout=TIMEOUT,
        )
        df = bs.get_data_frames()[0]
    except Exception as e:
        print(f"[get_game_highs] game_id={game_id} error: {e}")
        return None

    if df.empty:
        return None

    def parse_minutes(x):
        s = str(x).strip()
        if not s or s in ("", "None", "nan"):
            return 0.0
        if ":" in s:
            return float(s.split(":")[0])
        try:
            return float(s)
        except ValueError:
            return 0.0

    df["MIN_FLOAT"] = df["minutes"].apply(parse_minutes)
    df = df[df["MIN_FLOAT"] >= 10].copy()
    if df.empty:
        return None

    df["STOCKS"] = df["steals"].fillna(0) + df["blocks"].fillna(0)
    df["TS%"] = df.apply(
        lambda r: calculate_ts_pct(
            r["points"], r["fieldGoalsAttempted"], r["freeThrowsAttempted"]
        ),
        axis=1,
    )

    return {
        "PTS": df["points"].max(),
        "REB": df["reboundsTotal"].max(),
        "AST": df["assists"].max(),
        "STOCKS": df["STOCKS"].max(),
        "TS%": df["TS%"].max(),
    }
