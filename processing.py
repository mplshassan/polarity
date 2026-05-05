# mpls.hassan
# data transformation helpers that aren't chart-specific

import data


def get_fracs_and_raws(player_row, highs):
    categories = ["PTS", "REB", "AST", "STOCKS", "TS%"]
    pts = float(player_row.get("PTS", 0))
    reb = float(player_row.get("REB", 0))
    ast = float(player_row.get("AST", 0))
    stl = float(player_row.get("STL", 0))
    blk = float(player_row.get("BLK", 0))
    fga = float(player_row.get("FGA", 0))
    fta = float(player_row.get("FTA", 0))

    raw = {
        "PTS": pts,
        "REB": reb,
        "AST": ast,
        "STOCKS": stl + blk,
        "TS%": data.calculate_ts_pct(pts, fga, fta),
    }

    fracs = []
    for cat in categories:
        high = highs.get(cat, 1) or 1
        fracs.append(min(raw[cat] / high, 1.0))

    return fracs, raw


def team_from_matchup(matchup_str):
    return matchup_str.split()[0] if matchup_str else "NBA"


def validate_player_data(player):
    required = [
        "PTS", "REB", "AST", "STL", "BLK",
        "FGA", "FTA", "Game_ID", "MATCHUP", "GAME_DATE",
    ]
    return [k for k in required if k not in player]