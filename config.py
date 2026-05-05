# mpls.hassan
# visual constants and styling for the polarity app

ACCENT = "#1648e8"

TEAM_COLORS = {
    "ATL": "#E03A3E",
    "BOS": "#007A33",
    "BKN": "#000000",
    "CHA": "#1D1160",
    "CHI": "#CE1141",
    "CLE": "#860038",
    "DAL": "#00538C",
    "DEN": "#0E2240",
    "DET": "#C8102E",
    "GSW": "#1D428A",
    "HOU": "#CE1141",
    "IND": "#002D62",
    "LAC": "#C8102E",
    "LAL": "#FDB927",
    "MEM": "#5D76A9",
    "MIA": "#98002E",
    "MIL": "#00471B",
    "MIN": "#236192",
    "NOP": "#0C2340",
    "NYK": "#F58426",
    "OKC": "#007AC1",
    "ORL": "#0077C0",
    "PHI": "#006BB6",
    "PHX": "#1D1160",
    "POR": "#E03A3E",
    "SAC": "#5A2D81",
    "SAS": "#C4CED4",
    "TOR": "#CE1141",
    "UTA": "#002B5C",
    "WAS": "#002B5C",
}

CUSTOM_CSS = """
<style>
/* google fonts */
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;1,400&family=Source+Serif+4:ital,wght@0,300;0,400;0,600;1,300;1,400&display=swap');

/* global serif body */
html, body, [class*="css"], .stApp, .stMarkdown, p, li, label,
.stTextInput input, .stRadio label, .stCheckbox label,
[data-testid="stSidebar"], .stDataFrame {
    font-family: 'Source Serif 4', Georgia, serif !important;
}

/* headings */
h1, h2, h3, h4, h5, h6,
.stTitle, [data-testid="stHeading"] {
    font-family: 'Playfair Display', Georgia, serif !important;
    letter-spacing: -0.01em;
}

/* main title banner */
.polarity-header {
    font-family: 'Playfair Display', Georgia, serif !important;
    font-size: clamp(2.4rem, 5vw, 4rem);
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #1648e8;
    line-height: 1.1;
    margin-bottom: 0.15rem;
}
.polarity-tagline {
    font-family: 'Source Serif 4', Georgia, serif !important;
    font-size: 0.95rem;
    font-style: italic;
    color: rgba(128,128,128,0.8);
    margin-bottom: 1.5rem;
    letter-spacing: 0.01em;
}

/* primary button styles */
button[kind="primary"] {
    background-color: #1648e8 !important;
    border-color: #1648e8 !important;
    color: white !important;
}
button[kind="primary"]:hover {
    background-color: #0f35b5 !important;
    border-color: #0f35b5 !important;
}
button[kind="primary"]:active {
    background-color: #0a2785 !important;
}

/* radio selected dot */
[data-testid="stRadio"] [aria-checked="true"] {
    background-color: #1648e8 !important;
}

/* hide input instructions tooltip */
[data-testid="InputInstructions"] { display: none; }
</style>
"""


def hex_to_rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return f"rgba({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}, {alpha})"
