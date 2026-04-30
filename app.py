# mpls.hassan
# strictly visual - streamlit ui rendering only
from datetime import datetime

import pandas as pd
import streamlit as st

import data
from charts import build_comparison_figure, build_single_player_figure
from config import ACCENT, CUSTOM_CSS, TEAM_COLORS
from processing import get_fracs_and_raws, team_from_matchup, validate_player_data

# page config
st.set_page_config(
    page_title="Polarity", layout="wide", initial_sidebar_state="collapsed"
)

# custom styling
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# main header
st.markdown(
    """
    <div class="polarity-header">Polarity</div>
    <div class="polarity-tagline">aesthetic polar charts for NBA players.</div>
    """,
    unsafe_allow_html=True,
)

# sidebar
with st.sidebar:
    # mode toggle
    mode = st.radio("Mode", ["Single", "Flux"], horizontal=True)

    # date selection
    use_specific_date = st.checkbox("Search specific date")
    sel_date = (
        st.date_input("Game date", max_value=datetime.now().date())
        if use_specific_date
        else None
    )

    # player input form
    with st.form(key="search_form"):
        if mode == "Single":
            player_name = st.text_input("Player", placeholder="e.g. Anthony Edwards")
            player2_name = None
        else:
            col1, col2 = st.columns(2)
            with col1:
                player_name = st.text_input("Player 1", placeholder="e.g. LeBron James")
            with col2:
                player2_name = st.text_input(
                    "Player 2", placeholder="e.g. Anthony Edwards"
                )

        search_btn = st.form_submit_button("Pull Stats", type="primary")

    st.markdown("---")
    st.caption("Find your favorite player's polarity!")


def _fetch_player_game(player_id, resolved_name, use_specific_date, sel_date):
    """
    Try live first (unless a specific date is requested), then fall back to
    the historical game log. Returns (game_dict, is_live).
    """
    if not use_specific_date:
        live = data.get_live_game_stats(player_id)
        if live is not None:
            return live, True
    historical = data.get_game_stats(player_id, sel_date)
    return historical, False


def _get_highs(game):
    """Return highs from the right endpoint depending on whether the game is live."""
    if game.get("LIVE"):
        return data.get_live_game_highs(game["Game_ID"])
    return data.get_game_highs(game["Game_ID"])


def _score_line(p):
    """Build a score string like 'CLE 99 @ LAL 112' from a live game dict."""
    away = p.get("AWAY_TRICODE", "")
    home = p.get("HOME_TRICODE", "")
    away_score = p.get("AWAY_SCORE", "")
    home_score = p.get("HOME_SCORE", "")
    if away and home and away_score != "" and home_score != "":
        return f"{away} {away_score} @ {home} {home_score}"
    return p.get("MATCHUP", "—")


def live_badge(p, matchup, game_date):
    caption = f"{matchup}  ·  {game_date}"
    if p.get("LIVE"):
        status_code = p.get("GAME_STATUS_CODE", 1)
        status_text = p.get("GAME_STATUS", "")
        score_line = _score_line(p)
        if status_code == 2:
            # in-progress: show score + game clock/period from status_text
            badge = (
                f'<span style="color:#e81648; font-weight:700;">'
                f"LIVE — {score_line} &nbsp;·&nbsp; {status_text}"
                f"</span>"
            )
        else:
            # final: show score
            badge = (
                f'<span style="color:#888; font-weight:600;">'
                f"FINAL — {score_line}"
                f"</span>"
            )
        return caption, badge
    return caption, None


# data fetch
if search_btn:
    if mode == "Single":
        if not player_name or not player_name.strip():
            st.error("Please enter a player name.")
        else:
            with st.spinner("Fetching data…"):
                all_players = data.get_all_players()
                player_id, resolved_name = data.get_player_id(player_name, all_players)

                if not player_id:
                    st.error("Player not found. Try a different spelling.")
                else:
                    game, is_live = _fetch_player_game(
                        player_id, resolved_name, use_specific_date, sel_date
                    )
                    if game is None:
                        msg = (
                            "No game found on that date."
                            if use_specific_date
                            else "No game data found for the current season."
                        )
                        st.error(msg)
                    else:
                        st.session_state["player_data"] = game
                        st.session_state["player2_data"] = None
                        st.session_state["game_id"] = game["Game_ID"]
                        st.session_state["resolved_name"] = resolved_name
                        st.session_state["mode"] = "Single"

    else:
        if not player_name or not player_name.strip():
            st.error("Please enter a name for Player 1.")
        elif not player2_name or not player2_name.strip():
            st.error("Please enter a name for Player 2.")
        else:
            with st.spinner("Fetching data for both players…"):
                all_players = data.get_all_players()

                player1_id, resolved_name1 = data.get_player_id(
                    player_name, all_players
                )
                if not player1_id:
                    st.error(f"Player 1 not found: {player_name}")
                    st.stop()

                player2_id, resolved_name2 = data.get_player_id(
                    player2_name, all_players
                )
                if not player2_id:
                    st.error(f"Player 2 not found: {player2_name}")
                    st.stop()

                game1, _ = _fetch_player_game(
                    player1_id, resolved_name1, use_specific_date, sel_date
                )
                game2, _ = _fetch_player_game(
                    player2_id, resolved_name2, use_specific_date, sel_date
                )

                if game1 is None:
                    st.error(f"No game data found for {resolved_name1}")
                    st.stop()
                if game2 is None:
                    st.error(f"No game data found for {resolved_name2}")
                    st.stop()

                st.session_state["player_data"] = game1
                st.session_state["player2_data"] = game2
                st.session_state["game_id"] = game1["Game_ID"]
                st.session_state["game2_id"] = game2["Game_ID"]
                st.session_state["resolved_name"] = resolved_name1
                st.session_state["resolved_name2"] = resolved_name2
                st.session_state["mode"] = "Flux"


# display
if "player_data" in st.session_state:
    player = st.session_state["player_data"]
    mode = st.session_state.get("mode", "Single")

    if mode == "Single":
        game_id = st.session_state["game_id"]
        resolved_name = st.session_state["resolved_name"]

        missing = validate_player_data(player)
        if missing:
            st.error(f"Incomplete data from NBA API (missing: {', '.join(missing)}).")
            st.stop()

        highs = _get_highs(player)
        if highs is None:
            st.error("Could not load box-score data for this game.")
            st.stop()

        team = team_from_matchup(player.get("MATCHUP"))
        team_color = TEAM_COLORS.get(team, ACCENT)
        game_date = pd.to_datetime(player["GAME_DATE"]).strftime("%b %d, %Y")
        matchup = player.get("MATCHUP", "—")

        st.title(resolved_name)

        cap, badge = live_badge(player, matchup, game_date)
        st.caption(cap)
        if badge:
            st.markdown(badge, unsafe_allow_html=True)

        # stat cards
        c1, c2, c3, c4 = st.columns(4)
        stats = [
            (c1, "Points", int(player["PTS"])),
            (c2, "Rebounds", int(player["REB"])),
            (c3, "Assists", int(player["AST"])),
            (c4, "STOCKS", int(player["STL"]) + int(player["BLK"])),
        ]
        for col, label, val in stats:
            col.markdown(
                f'<div class="stat-card"><div class="stat-label">{label}</div>'
                f'<div class="stat-value">{val}</div></div>',
                unsafe_allow_html=True,
            )

        # radar chart
        fig = build_single_player_figure(player, resolved_name, team_color, highs)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # detail table
        _, raw = get_fracs_and_raws(player, highs)
        detail_df = pd.DataFrame(
            [
                {"Stat": "Points", "Value": raw["PTS"], "Game High": highs["PTS"]},
                {"Stat": "Rebounds", "Value": raw["REB"], "Game High": highs["REB"]},
                {"Stat": "Assists", "Value": raw["AST"], "Game High": highs["AST"]},
                {
                    "Stat": "STOCKS",
                    "Value": raw["STOCKS"],
                    "Game High": highs["STOCKS"],
                },
                {
                    "Stat": "TS%",
                    "Value": round(raw["TS%"] * 100, 1),
                    "Game High": round(highs["TS%"] * 100, 1),
                },
            ]
        )

        st.dataframe(
            detail_df,
            column_config={
                "Stat": st.column_config.TextColumn("Stat", width="small"),
                "Value": st.column_config.TextColumn("Player", width="small"),
                "Game High": st.column_config.TextColumn("Game High", width="small"),
            },
            hide_index=True,
            use_container_width=True,
        )

    else:
        # flux mode
        player2 = st.session_state["player2_data"]
        resolved_name1 = st.session_state["resolved_name"]
        resolved_name2 = st.session_state["resolved_name2"]

        highs1 = _get_highs(player)
        highs2 = _get_highs(player2)

        if highs1 is None or highs2 is None:
            st.error("Could not load box-score data for one of the games.")
            st.stop()

        team1 = team_from_matchup(player.get("MATCHUP"))
        team2 = team_from_matchup(player2.get("MATCHUP"))
        color1 = TEAM_COLORS.get(team1, ACCENT)
        color2 = TEAM_COLORS.get(team2, "#E03A3E")

        game_date1 = pd.to_datetime(player["GAME_DATE"]).strftime("%b %d, %Y")
        game_date2 = pd.to_datetime(player2["GAME_DATE"]).strftime("%b %d, %Y")
        matchup1 = player.get("MATCHUP", "—")
        matchup2 = player2.get("MATCHUP", "—")

        # comparison header
        st.title(f"{resolved_name1} vs {resolved_name2}")

        cap1, badge1 = live_badge(player, matchup1, game_date1)
        cap2, badge2 = live_badge(player2, matchup2, game_date2)
        combined_caption = f"{cap1}  |  {cap2}"
        st.caption(combined_caption)
        if badge1 or badge2:
            b1 = badge1 or ""
            b2 = badge2 or ""
            sep = "  &nbsp;|&nbsp;  " if badge1 and badge2 else ""
            st.markdown(b1 + sep + b2, unsafe_allow_html=True)

        # comparison stat cards
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(resolved_name1)
            c1a, c1b, c1c, c1d = st.columns(4)
            stats1 = [
                (c1a, "Points", int(player["PTS"])),
                (c1b, "Rebounds", int(player["REB"])),
                (c1c, "Assists", int(player["AST"])),
                (c1d, "Stocks", int(player["STL"]) + int(player["BLK"])),
            ]
            for col, label, val in stats1:
                col.markdown(
                    f'<div class="stat-card"><div class="stat-label">{label}</div>'
                    f'<div class="stat-value">{val}</div></div>',
                    unsafe_allow_html=True,
                )

        with col2:
            st.subheader(resolved_name2)
            c2a, c2b, c2c, c2d = st.columns(4)
            stats2 = [
                (c2a, "Points", int(player2["PTS"])),
                (c2b, "Rebounds", int(player2["REB"])),
                (c2c, "Assists", int(player2["AST"])),
                (c2d, "Stocks", int(player2["STL"]) + int(player2["BLK"])),
            ]
            for col, label, val in stats2:
                col.markdown(
                    f'<div class="stat-card"><div class="stat-label">{label}</div>'
                    f'<div class="stat-value">{val}</div></div>',
                    unsafe_allow_html=True,
                )

        # overlay radar chart
        categories = ["PTS", "REB", "AST", "STOCKS", "TS%"]
        combined_highs = {
            cat: max(highs1.get(cat, 0), highs2.get(cat, 0)) for cat in categories
        }

        fig = build_comparison_figure(
            player,
            resolved_name1,
            color1,
            player2,
            resolved_name2,
            color2,
            combined_highs,
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # comparison table
        _, raw1 = get_fracs_and_raws(player, combined_highs)
        _, raw2 = get_fracs_and_raws(player2, combined_highs)

        st.subheader("Detailed Comparison")
        comparison_df = pd.DataFrame(
            [
                {
                    "Stat": "Points",
                    resolved_name1: raw1["PTS"],
                    resolved_name2: raw2["PTS"],
                    "Game High": combined_highs["PTS"],
                },
                {
                    "Stat": "Rebounds",
                    resolved_name1: raw1["REB"],
                    resolved_name2: raw2["REB"],
                    "Game High": combined_highs["REB"],
                },
                {
                    "Stat": "Assists",
                    resolved_name1: raw1["AST"],
                    resolved_name2: raw2["AST"],
                    "Game High": combined_highs["AST"],
                },
                {
                    "Stat": "Stocks",
                    resolved_name1: raw1["STOCKS"],
                    resolved_name2: raw2["STOCKS"],
                    "Game High": combined_highs["STOCKS"],
                },
                {
                    "Stat": "TS%",
                    resolved_name1: round(raw1["TS%"] * 100, 1),
                    resolved_name2: round(raw2["TS%"] * 100, 1),
                    "Game High": round(combined_highs["TS%"] * 100, 1),
                },
            ]
        )

        st.dataframe(
            comparison_df,
            column_config={
                "Stat": st.column_config.TextColumn("Stat", width="small"),
                resolved_name1: st.column_config.TextColumn(
                    resolved_name1, width="small"
                ),
                resolved_name2: st.column_config.TextColumn(
                    resolved_name2, width="small"
                ),
                "Game High": st.column_config.TextColumn("Game High", width="small"),
            },
            hide_index=True,
            use_container_width=True,
        )
