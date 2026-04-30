# mpls.hassan
# radar chart creation and layout
import plotly.graph_objects as go

from config import hex_to_rgba
from processing import get_fracs_and_raws

LABEL_COLOR = "#1648e8"


def build_radar_trace(player_data, player_name, team_color, highs):
    fracs, raw = get_fracs_and_raws(player_data, highs)
    categories = ["PTS", "REB", "AST", "STOCKS", "TS%"]
    hover_data = [[raw[c], highs[c]] for c in categories]
    hover_data.append(hover_data[0])
    return go.Scatterpolar(
        r=fracs + [fracs[0]],
        theta=categories + [categories[0]],
        fill="toself",
        fillcolor=hex_to_rgba(team_color, 0.20),
        line=dict(color=team_color, width=3),
        marker=dict(size=6, color=team_color),
        name=player_name,
        customdata=hover_data,
        hovertemplate=(
            f"<b>{player_name}</b><br>"
            "<b>%{theta}</b><br>"
            "Value: %{customdata[0]:.1f}<br>"
            "Game High: %{customdata[1]:.1f}<extra></extra>"
        ),
    )


def build_single_player_figure(player_data, player_name, team_color, highs):
    fig = go.Figure()
    fig.add_trace(build_radar_trace(player_data, player_name, team_color, highs))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                tickvals=[0.25, 0.5, 0.75, 1.0],
                ticktext=["25%", "50%", "75%", "100%"],
                tickfont=dict(size=10),
                gridcolor="rgba(128,128,128,0.15)",
            ),
            angularaxis=dict(
                tickfont=dict(
                    size=14,
                    family="Playfair Display, Georgia, serif",
                    color=LABEL_COLOR,
                ),
                gridcolor="rgba(128,128,128,0.15)",
            ),
            bgcolor="rgba(0,0,0,0)",
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=60, r=60, t=40, b=40),
        showlegend=False,
        height=500,
    )
    return fig


def build_comparison_figure(
    player1_data,
    player1_name,
    player1_color,
    player2_data,
    player2_name,
    player2_color,
    combined_highs,
):
    fig = go.Figure()
    fig.add_trace(
        build_radar_trace(player1_data, player1_name, player1_color, combined_highs)
    )
    fig.add_trace(
        build_radar_trace(player2_data, player2_name, player2_color, combined_highs)
    )
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                tickvals=[0.25, 0.5, 0.75, 1.0],
                ticktext=["25%", "50%", "75%", "100%"],
                tickfont=dict(size=10),
                gridcolor="rgba(128,128,128,0.15)",
            ),
            angularaxis=dict(
                tickfont=dict(
                    size=14,
                    family="Playfair Display, Georgia, serif",
                    color=LABEL_COLOR,
                ),
                gridcolor="rgba(128,128,128,0.15)",
            ),
            bgcolor="rgba(0,0,0,0)",
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=60, r=60, t=40, b=40),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=500,
    )
    return fig
