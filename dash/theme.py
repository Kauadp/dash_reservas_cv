"""
theme.py — Tema visual do Exagerado - Dash Vendas
────────────────────────────────────────────────────
Paleta, CSS customizado, config de página e helpers de layout
(KPI cards, template plotly, headers de seção).

Uso básico no app principal:

    import streamlit as st
    from theme import PAGE_CONFIG, inject_custom_css, kpi_row, section_header, plotly_layout

    st.set_page_config(**PAGE_CONFIG)
    inject_custom_css()

    section_header("🤝", "Comercial & Funil", "Visão geral do funil de vendas")
    kpi_row([
        {"label": "Expositores Totais", "value": "128"},
        {"label": "TO Dentro", "value": "42"},
        {"label": "Contratos Enviados", "value": "97"},
        {"label": "Contratos Assinados", "value": "63"},
        {"label": "Taxa de Conversão", "value": "64,9%", "delta": "+3,2 p.p."},
    ])

    fig.update_layout(**plotly_layout(title="Enviados vs Assinados"))
    st.plotly_chart(fig, use_container_width=True)
"""

import streamlit as st

# ──────────────────────────────────────────────────────────────────
#  PALETA DE CORES
#  Baseada na identidade visual do meuexagerado.com.br
#  (theme-color oficial do site: #E54E88 + acento roxo da campanha de cupom)
# ──────────────────────────────────────────────────────────────────
COLORS = {
    "primary":        "#E54E88",  # rosa/magenta — cor de destaque principal da marca
    "primary_light":  "#F080AC",  # rosa mais claro (hover, áreas secundárias)
    "primary_dark":   "#B5316A",  # rosa escuro (texto sobre fundo claro, bordas ativas)
    "accent":         "#7B4FD1",  # roxo — acento secundário (roleta/campanhas)
    "accent_light":   "#A487E0",
    "background":     "#FAF7F9",  # fundo geral, levemente rosado
    "surface":        "#FFFFFF",  # fundo de cards/gráficos
    "text":           "#241B22",
    "text_muted":     "#7A6D75",
    "border":         "#EDE3E8",
    "success":        "#2E9E6B",
    "warning":        "#ED8936",
    "danger":         "#C0392B",
    "grid":           "#F0E7EC",
}

# Sequência de cores usada nos gráficos (plotly `colorway`)
CHART_PALETTE = [
    COLORS["primary"],
    COLORS["accent"],
    COLORS["primary_dark"],
    COLORS["accent_light"],
    COLORS["warning"],
    COLORS["success"],
    "#4A4453",
]

FONT_FAMILY = "'Inter', 'Segoe UI', sans-serif"

PAGE_CONFIG = dict(
    page_title="Exagerado - Dash Vendas",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ──────────────────────────────────────────────────────────────────
#  CSS CUSTOMIZADO
# ──────────────────────────────────────────────────────────────────
def inject_custom_css() -> None:
    """Injeta CSS global: fonte, cores, cards de métrica, abas, etc."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {{
            font-family: {FONT_FAMILY};
        }}

        .stApp {{
            background-color: {COLORS["background"]};
        }}

        /* ── Esconde branding padrão do Streamlit ───────────────── */
        #MainMenu, footer {{visibility: hidden;}}

        /* ── Tabs ────────────────────────────────────────────────── */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 4px;
            border-bottom: 1px solid {COLORS["border"]};
        }}
        .stTabs [data-baseweb="tab"] {{
            height: 44px;
            padding: 0 18px;
            background-color: transparent;
            border-radius: 8px 8px 0 0;
            color: {COLORS["text_muted"]};
            font-weight: 600;
            font-size: 14px;
        }}
        .stTabs [aria-selected="true"] {{
            background-color: {COLORS["surface"]};
            color: {COLORS["primary"]};
            border-bottom: 3px solid {COLORS["primary"]};
        }}

        /* ── Cards de métrica (st.metric) ───────────────────────── */
        div[data-testid="stMetric"] {{
            background-color: {COLORS["surface"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 12px;
            padding: 16px 18px 12px 18px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }}
        div[data-testid="stMetricLabel"] {{
            color: {COLORS["text_muted"]};
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            white-space: normal;
        }}
        div[data-testid="stMetricValue"] {{
            color: {COLORS["text"]};
            font-size: clamp(18px, 2vw, 28px);
            font-weight: 700;
            line-height: 1.2;
            white-space: normal !important;
            overflow-wrap: break-word;
        }}
        div[data-testid="stMetricValue"] > div {{
            overflow: visible !important;
            text-overflow: unset !important;
            white-space: normal !important;
        }}

        /* ── Containers gerais (gráficos) ───────────────────────── */
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            background-color: {COLORS["surface"]};
            border-radius: 12px;
            border: 1px solid {COLORS["border"]};
        }}

        /* ── Section header customizado ─────────────────────────── */
        .section-header {{
            display: flex;
            align-items: baseline;
            gap: 10px;
            margin: 6px 0 2px 0;
        }}
        .section-header .icon {{
            font-size: 22px;
        }}
        .section-header .title {{
            font-size: 22px;
            font-weight: 700;
            color: {COLORS["text"]};
        }}
        .section-subtitle {{
            color: {COLORS["text_muted"]};
            font-size: 14px;
            margin-bottom: 14px;
        }}

        /* ── Progress bar de meta ───────────────────────────────── */
        .stProgress > div > div > div > div {{
            background-color: {COLORS["primary"]};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────
#  HELPERS DE LAYOUT
# ──────────────────────────────────────────────────────────────────
def section_header(icon: str, title: str, subtitle: str | None = None) -> None:
    """Cabeçalho padronizado de seção dentro de uma aba."""
    st.markdown(
        f"""<div class="section-header"><span class="icon">{icon}</span>
        <span class="title">{title}</span></div>""",
        unsafe_allow_html=True,
    )
    if subtitle:
        st.markdown(f'<div class="section-subtitle">{subtitle}</div>', unsafe_allow_html=True)


def kpi_row(kpis: list[dict]) -> None:
    """
    Renderiza uma linha de KPI cards usando st.metric.

    Cada item de `kpis` é um dict com:
        label (str, obrigatório)
        value (str, obrigatório)
        delta (str, opcional)
        delta_color ("normal" | "inverse" | "off", opcional)
        help (str, opcional — tooltip, útil p/ diferenciar Meta vs Receita Prevista)
    """
    cols = st.columns(len(kpis))
    for col, kpi in zip(cols, kpis):
        with col:
            st.metric(
                label=kpi["label"],
                value=kpi["value"],
                delta=kpi.get("delta"),
                delta_color=kpi.get("delta_color", "normal"),
                help=kpi.get("help"),
            )


def format_delta(
    current: float,
    previous: float,
    higher_is_better: bool = True,
    abs_format: str = "{:+,.0f}",
    rel_format: str = "{:+.1f}%",
    suffix: str = "",
    format_str: str | None = None,
    relative_to_current: bool = True,
) -> tuple[str, str]:
    """Formata delta para st.metric com cor e percentual de variação.

    Args:
        current: valor do período atual.
        previous: valor do período anterior.
        higher_is_better: se True, um delta positivo é bom.
        abs_format: formato do delta absoluto.
        rel_format: formato do delta percentual.
        suffix: sufixo opcional para o valor absoluto (por exemplo, ' pp' ou ' m²').
        relative_to_current: se True, calcula a porcentagem em relação ao valor atual.

    Returns:
        tuple[str, str]: delta formatado e delta_color para st.metric.
    """
    delta = current - previous
    if format_str is not None:
        abs_format = format_str

    denominator = current if relative_to_current else previous
    if denominator:
        relative_change = delta / denominator * 100
    else:
        relative_change = 100.0 if delta > 0 else 0.0

    delta_color = "normal" if (delta >= 0) == higher_is_better else "inverse"
    delta_text = f"{abs_format.format(delta)}{suffix} ({rel_format.format(relative_change)})"
    return delta_text, delta_color


def plotly_layout(title: str | None = None, height: int = 380) -> dict:
    """Retorna um dict de layout pronto para fig.update_layout(**plotly_layout(...))."""
    layout = dict(
        template="plotly_white",
        font=dict(family=FONT_FAMILY, color=COLORS["text"], size=13),
        colorway=CHART_PALETTE,
        paper_bgcolor=COLORS["surface"],
        plot_bgcolor=COLORS["surface"],
        height=height,
        margin=dict(l=30, r=20, t=50 if title else 20, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(gridcolor=COLORS["grid"], zeroline=False, linecolor=COLORS["border"]),
        yaxis=dict(gridcolor=COLORS["grid"], zeroline=False, linecolor=COLORS["border"]),
    )
    if title:
        layout["title"] = dict(text=title, font=dict(size=15, color=COLORS["text"]), x=0.0)
    return layout


def donut_layout(title: str | None = None, height: int = 340) -> dict:
    """Variante enxuta de plotly_layout para gráficos de rosca (sem eixos)."""
    layout = plotly_layout(title=title, height=height)
    layout.pop("xaxis", None)
    layout.pop("yaxis", None)
    return layout