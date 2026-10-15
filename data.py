import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from difflib import get_close_matches

import pandas as pd
import streamlit as st
from nba_api.live.nba.endpoints import boxscore, scoreboard
from nba_api.stats.endpoints import (
    BoxScoreTraditionalV3,
    PlayerCareerStats,
    PlayerGameLog,
)
from nba_api.stats.static import players

# config -- fail fast: a blocked/throttled cloud IP used to cost 60s x 3 tries per call
TIMEOUT = 20
MAX_RETRIES = 2
RETRY_DELAY = 1
LIVE_TTL = 20  # seconds to reuse scoreboard/boxscore responses
FALLBACK_SEASONS = 4  # only used if the career-stats lookup fails

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


class DataUnavailable(Exception):
    """The NBA stats API couldn't be reached (as opposed to 'player has no games')."""


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


@st.cache_data(ttl=3600, show_spinner=False)
def _player_index():
    """Built once: lowercase-name -> (id, name), the name list, and active ids."""
    plist = players.get_players()
    by_lower = {p["full_name"].lower(): (p["id"], p["full_name"]) for p in plist}
    names = [p["full_name"] for p in plist]
    active = {p["id"] for p in plist if p["is_active"]}
    return by_lower, names, active


def get_player_id(name, player_list=None):
    if not name or not name.strip():
        return None, None
    by_lower, names, _ = _player_index()
    name = name.strip()
    # exact (case-insensitive) match skips fuzzy matching entirely
    hit = by_lower.get(name.lower())
    if hit:
        return hit
    matches = get_close_matches(name, names, n=1, cutoff=0.6)
    if not matches:
        return None, None
    return by_lower[matches[0].lower()]


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_game_log(player_id, season, stype):
    """One PlayerGameLog call. Raises on failure (so failures are never cached)."""
    t0 = time.perf_counter()
    try:
        log = _retry_call(
            PlayerGameLog,
            player_id=player_id,
            season=season,
            season_type_all_star=stype,
            timeout=TIMEOUT,
        )
        df = log.get_data_frames()[0]
    except Exception as e:
        print(
            f"[game_log] season={season} type={stype} FAILED "
            f"{time.perf_counter() - t0:.1f}s: {e}"
        )
        raise
    print(
        f"[game_log] season={season} type={stype} "
        f"{time.perf_counter() - t0:.1f}s empty={df.empty}"
    )
    if not df.empty:
        df = df.copy()
        df["SEASON_TYPE"] = stype
        # format='mixed' handles both "Apr 25, 2026" and "2026-04-25"
        df["MATCH_DATE"] = pd.to_datetime(df["GAME_DATE"], format="mixed").dt.date
    return df


def _season_games(player_id, season, season_types):
    """Concatenate game logs for the given season types.

    Raises DataUnavailable only if every request failed (nothing came back at all),
    so "player has no games" and "API unreachable" are told apart.
    """
    frames, errors = [], []
    for stype in season_types:
        try:
            df = _fetch_game_log(player_id, season, stype)
        except Exception as e:
            errors.append(e)
            continue
        if not df.empty:
            frames.append(df)
    if not frames and errors:
        raise DataUnavailable(f"{type(errors[-1]).__name__}: {errors[-1]}")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def _career_seasons(player_id):
    """One call that replaces the season-by-season guessing loop.

    Returns (last_regular_season, last_playoff_season); either can be None.
    """
    t0 = time.perf_counter()
    c = _retry_call(PlayerCareerStats, player_id=player_id, timeout=TIMEOUT)
    reg = c.season_totals_regular_season.get_data_frame()
    post = c.season_totals_post_season.get_data_frame()
    print(f"[career] player={player_id} {time.perf_counter() - t0:.1f}s")
    last_reg = reg["SEASON_ID"].max() if not reg.empty else None
    last_post = post["SEASON_ID"].max() if not post.empty else None
    return last_reg, last_post


def _latest_row(df):
    df = df.dropna(subset=["MATCH_DATE"])
    if df.empty:
        return None
    return df.sort_values("MATCH_DATE", ascending=False).iloc[0]


@st.cache_data(ttl=60, show_spinner=False)
def get_game_stats(player_id, date_obj=None):
    t0 = time.perf_counter()
    try:
        if date_obj:
            return _game_on_date(player_id, date_obj)
        return _latest_game(player_id)
    finally:
        print(f"[get_game_stats] player={player_id} date={date_obj} "
              f"total={time.perf_counter() - t0:.1f}s")


def _game_on_date(player_id, date_obj):
    season = date_to_season(date_obj)
    target = pd.to_datetime(date_obj).date()
    # regular season first (most dates live there); only hit playoffs if no match
    for stype in SEASON_TYPES:
        df = _season_games(player_id, season, [stype])
        if df.empty:
            continue
        hit = df[df["MATCH_DATE"] == target]
        if not hit.empty:
            return hit.iloc[0]
    return None


def _latest_game(player_id):
    try:
        last_reg, last_post = _career_seasons(player_id)
    except Exception as e:
        print(f"[get_game_stats] career lookup failed, using fallback: {e}")
        return _latest_game_fallback(player_id)

    if last_reg is None and last_post is None:
        return None

    # playoffs always come after the regular season of the same year, so if the
    # last playoff season is >= the last regular season, the newest game is there
    if last_post is not None and (last_reg is None or last_post >= last_reg):
        order = [(last_post, "Playoffs"), (last_reg, "Regular Season")]
    else:
        order = [(last_reg, "Regular Season")]

    for season, stype in order:
        if season is None:
            continue
        df = _season_games(player_id, season, [stype])
        row = _latest_row(df) if not df.empty else None
        if row is not None:
            return row
    return None


def _latest_game_fallback(player_id):
    """Career endpoint unavailable: check a few recent seasons only (never back to 1947)."""
    current_year = int(get_current_season().split("-")[0])
    for y in range(current_year, current_year - FALLBACK_SEASONS, -1):
        season = f"{y}-{str(y + 1)[-2:]}"
        # newest games are playoffs; stop at the first season type that has data
        for stype in reversed(SEASON_TYPES):
            df = _season_games(player_id, season, [stype])
            row = _latest_row(df) if not df.empty else None
            if row is not None:
                return row
    return None


# live data: short in-process TTL cache (shared by Single, Flux, and highs lookups)
_live_cache = {}
_live_lock = threading.Lock()


def _live_cached(key, fetch):
    now = time.time()
    with _live_lock:
        hit = _live_cache.get(key)
        if hit and now - hit[0] < LIVE_TTL:
            return hit[1]
    try:
        val = fetch()
    except Exception as e:
        print(f"[live] {key} error: {e}")
        val = None
    with _live_lock:
        _live_cache[key] = (time.time(), val)
    return val


def _get_scoreboard_games():
    def f():
        return scoreboard.ScoreBoard(timeout=TIMEOUT).get_dict()["scoreboard"]["games"]

    return _live_cached("scoreboard", f) or []


def _get_live_boxscore(game_id):
    def f():
        d = boxscore.BoxScore(game_id=game_id, timeout=TIMEOUT).get_dict()
        return d.get("game")

    return _live_cached(f"box:{game_id}", f)


def _player_line(bs_dict, game, player_id):
    """Pull one player's line out of a boxscore dict, or None if he isn't in it."""
    game_id = game["gameId"]
    home_tri = game.get("homeTeam", {}).get("teamTricode", "") or bs_dict["homeTeam"]["teamTricode"]
    away_tri = game.get("awayTeam", {}).get("teamTricode", "") or bs_dict["awayTeam"]["teamTricode"]
    for side in ("homeTeam", "awayTeam"):
        for p in bs_dict.get(side, {}).get("players", []):
            if str(p.get("personId", "")) == str(player_id):
                s = p["statistics"]
                return {
                    "PTS": float(s.get("points", 0)),
                    "REB": float(s.get("reboundsTotal", 0)),
                    "AST": float(s.get("assists", 0)),
                    "STL": float(s.get("steals", 0)),
                    "BLK": float(s.get("blocks", 0)),
                    "FGA": float(s.get("fieldGoalsAttempted", 0)),
                    "FTA": float(s.get("freeThrowsAttempted", 0)),
                    "Game_ID": game_id,
                    "MATCHUP": f"{away_tri} @ {home_tri}",
                    "GAME_DATE": datetime.now().strftime("%Y-%m-%d"),
                    "LIVE": True,
                    "GAME_STATUS": game.get("gameStatusText", ""),
                    "GAME_STATUS_CODE": game.get("gameStatus", 1),
                    "HOME_TRICODE": home_tri,
                    "AWAY_TRICODE": away_tri,
                    "HOME_SCORE": game.get("homeTeam", {}).get("score", 0),
                    "AWAY_SCORE": game.get("awayTeam", {}).get("score", 0),
                }
    return None


def get_live_game_stats(player_id):
    """Returns live game stats for a player if they have a game today, else None."""
    # retired players can't be in a live game: skip every network call
    if player_id not in _player_index()[2]:
        return None

    # scheduled games (status 1) have no boxscore yet, so only look at started games
    started = [g for g in _get_scoreboard_games() if g.get("gameStatus", 1) >= 2]
    if not started:
        return None

    def check(game):
        bs = _get_live_boxscore(game["gameId"])
        return _player_line(bs, game, player_id) if bs else None

    # one request per game, in parallel instead of one after another
    with ThreadPoolExecutor(max_workers=min(8, len(started))) as ex:
        for line in ex.map(check, started):
            if line is not None:
                return line
    return None


def get_live_game_highs(game_id):
    """Compute per-game highs from the live boxscore endpoint."""
    bs_dict = _get_live_boxscore(game_id)
    if bs_dict is None:
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
