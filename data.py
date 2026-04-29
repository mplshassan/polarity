# mpls.hassan
import time
from datetime import datetime
from difflib import get_close_matches

import pandas as pd
import streamlit as st
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
    seasons = [
        f"{y}-{str(y + 1)[-2:]}" for y in range(current_year, current_year - 10, -1)
    ]

    for season in seasons:
        df = _fetch_season_games(player_id, season)
        if not df.empty:
            return df.sort_values("MATCH_DATE", ascending=False).iloc[0]

    return None


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