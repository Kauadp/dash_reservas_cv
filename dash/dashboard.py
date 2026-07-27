import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path
from geo_utils import geocodificar, obter_centro_estado, calcular_distancia_km
from plotly.subplots import make_subplots
from maps import METAS, TABELA_METRO, ABL_TOTAL, ESTADO_EVENTO, EVENT_DATE, EVENT_CITY
from theme import (
    PAGE_CONFIG,
    COLORS,
    CHART_PALETTE,
    inject_custom_css,
    section_header,
    kpi_row,
    plotly_layout,
    donut_layout,
    format_delta,
)

project_root = Path(__file__).resolve().parents[1]
dash_dir = Path(__file__).resolve().parent
for path in (str(project_root), str(dash_dir)):
    if path not in sys.path:
        sys.path.insert(0, path)


from app.database import DatabaseManager
from app.main import PipelineController, url, headers

db_uri = st.secrets["db_uri"]

st.set_page_config(**PAGE_CONFIG)
inject_custom_css()


# ──────────────────────────────────────────────────────────────────
#  CARGA DE DADOS
# ──────────────────────────────────────────────────────────────────
@st.cache_resource
def get_db_manager():
    return DatabaseManager(db_uri)


db = get_db_manager()


@st.cache_data(ttl=600)
def load_data():
    return db.carregar_reservas()


df_reservas_all = load_data()

if st.sidebar.button("🔄 Atualizar Base de Dados"):
    controller = PipelineController(db_uri, url, headers)
    controller.run()
    st.cache_data.clear()
    st.rerun()


# ──────────────────────────────────────────────────────────────────
#  SELEÇÃO DE EVENTO
# ──────────────────────────────────────────────────────────────────
eventos_disponiveis = sorted(
    set(df_reservas_all["imobiliaria_nome"].dropna().unique()) & set(METAS.keys())
)

if not eventos_disponiveis:
    st.error(
        "Nenhum evento em `reservas_cvcrm` bate com as chaves de `METAS` em maps.py. "
        "Confira se os nomes de empreendimento estão exatamente iguais nos dois lugares."
    )
    st.stop()

evento_selecionado = st.sidebar.selectbox("📅 Evento", eventos_disponiveis)

meta_evento = METAS[evento_selecionado]
valor_m2_evento = TABELA_METRO[evento_selecionado]

raw_event_date = EVENT_DATE.get(evento_selecionado)
event_date = pd.to_datetime(raw_event_date) if raw_event_date else None
if event_date is not None:
    today = pd.Timestamp.now().normalize()
    if event_date < today:
        event_date = event_date + pd.DateOffset(years=1)
    days_to_event = (event_date - today).days
    event_date_info = (
        f"{event_date.strftime('%d/%m/%Y')} · Faltam {days_to_event} dias"
        if days_to_event > 0
        else f"{event_date.strftime('%d/%m/%Y')} · Hoje"
    )
else:
    event_date_info = "Data do evento não informada"

df = df_reservas_all[df_reservas_all["imobiliaria_nome"] == evento_selecionado].copy()

df["receita_prevista_unidade"] = df["area_m2"].astype(float) * valor_m2_evento
df["desconto_unidade"] = df["receita_prevista_unidade"] - df["valor_contrato"].astype(float)

vendidos = df[(df["situacao"] == "Contrato Assinado") | 
              (df["situacao"] == "Vendida")].copy()


# Geocodificação do ponto do evento para calcular distância média
event_city, event_state = EVENT_CITY.get(evento_selecionado, (None, None))
event_location = None
if event_city and event_state:
    event_point = pd.DataFrame(
        {"titular_cidade": [event_city], "titular_estado": [event_state]}
    )
    event_geo = geocodificar(event_point, "titular_cidade", "titular_estado").iloc[0]
    if pd.notna(event_geo["latitude"]) and pd.notna(event_geo["longitude"]):
        event_location = (event_geo["latitude"], event_geo["longitude"])


df_geo = geocodificar(df, "titular_cidade", "titular_estado")
if event_location is not None:
    df_geo["distancia_evento_km"] = df_geo.apply(
        lambda row: calcular_distancia_km(
            row["latitude"], row["longitude"], event_location[0], event_location[1]
        ),
        axis=1,
    )
else:
    df_geo["distancia_evento_km"] = float("nan")

JANELAS_COMPARACAO = {
    "Dia anterior (D-1)": 1,
    "Semana anterior (D-7)": 7,
    "Mês anterior (D-30)": 30,
}
janela_label = st.sidebar.selectbox(
    "📊 Comparar KPIs com", list(JANELAS_COMPARACAO.keys()), index=1
)

comparison_days = JANELAS_COMPARACAO[janela_label]
reference_date = pd.Timestamp.now().normalize()
current_start = reference_date - pd.Timedelta(days=comparison_days)
current_end = reference_date
previous_start = reference_date - pd.Timedelta(days=2 * comparison_days)
previous_end = reference_date - pd.Timedelta(days=comparison_days)


def slice_period(data: pd.DataFrame, date_column: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    return data[(data[date_column] >= start) & (data[date_column] < end)].copy()


df_current = slice_period(df, "data_cadastro", current_start, current_end)
df_previous = slice_period(df, "data_cadastro", previous_start, previous_end)

df_before_current = df[df["data_cadastro"] < current_start].copy()

vendidos_current = slice_period(vendidos, "data_venda", current_start, current_end)
vendidos_previous = slice_period(vendidos, "data_venda", previous_start, previous_end)

vendidos_before_current = vendidos[vendidos["data_venda"] < current_start].copy()


# ──────────────────────────────────────────────────────────────────
#  ABAS
# ──────────────────────────────────────────────────────────────────
tab_comercial, tab_receita, tab_descontos, tab_espaco = st.tabs(
    [
        "🤝 Comercial & Funil",
        "💵 Receita & Metas",
        "🏷️ Política de Descontos",
        "📐 Espaço & ABL",
    ]
)

# ════════════════════════════════════════════════════════════════
#  ABA 1 — COMERCIAL & FUNIL
# ════════════════════════════════════════════════════════════════
with tab_comercial:
    section_header(
        "🤝",
        "Comercial & Funil",
        f"Evento: {evento_selecionado} · {event_date_info} · Comparação: {janela_label}",
    )

    expositores_totais = df["titular_nome"].nunique()
    expositores_totais_prev = df_before_current["titular_nome"].nunique()

    to_dentro = df[df["situacao"] == "Link To Dentro Recebido e Validado"]
    to_dentro_prev = df_before_current[df_before_current["situacao"] == "Link To Dentro Recebido e Validado"]

    contratos_enviados = df[df["situacao"] == "Contrato Enviado"]
    contratos_enviados_prev = df_before_current[df_before_current["situacao"] == "Contrato Enviado"]

    total_reservas = len(df)
    total_reservas_prev = len(df_before_current)

    contratos_assinados = len(vendidos)
    contratos_assinados_prev = len(vendidos_before_current)

    taxa_conversao = (contratos_assinados / total_reservas * 100) if total_reservas else 0
    taxa_conversao_prev = (contratos_assinados_prev / total_reservas_prev * 100) if total_reservas_prev else 0

    expositores_delta, expositores_delta_color = format_delta(
        expositores_totais,
        expositores_totais_prev,
        higher_is_better=True,
        abs_format="{:+,.0f}",
    )
    to_dentro_delta, to_dentro_delta_color = format_delta(
        len(to_dentro),
        len(to_dentro_prev),
        higher_is_better=True,
        abs_format="{:+,.0f}",
    )
    contratos_enviados_delta, contratos_enviados_delta_color = format_delta(
        len(contratos_enviados),
        len(contratos_enviados_prev),
        higher_is_better=True,
        abs_format="{:+,.0f}",
    )
    contratos_assinados_delta, contratos_assinados_delta_color = format_delta(
        contratos_assinados,
        contratos_assinados_prev,
        higher_is_better=True,
        abs_format="{:+,.0f}",
    )
    taxa_conversao_delta, taxa_conversao_delta_color = format_delta(
        taxa_conversao,
        taxa_conversao_prev,
        higher_is_better=True,
        abs_format="{:+.1f} pp",
    )

    kpi_row(
        [
            {
                "label": "Expositores Totais",
                "value": f"{expositores_totais}",
                "delta": expositores_delta,
                "delta_color": expositores_delta_color,
            },
            {
                "label": "To Dentro",
                "value": f"{len(to_dentro)}",
                "delta": to_dentro_delta,
                "delta_color": to_dentro_delta_color,
            },
            {
                "label": "Contratos Enviados",
                "value": f"{len(contratos_enviados)}",
                "delta": contratos_enviados_delta,
                "delta_color": contratos_enviados_delta_color,
            },
            {
                "label": "Contratos Assinados",
                "value": f"{contratos_assinados}",
                "delta": contratos_assinados_delta,
                "delta_color": contratos_assinados_delta_color,
            },
            {
                "label": "Taxa de Conversão",
                "value": f"{taxa_conversao:.1f}%",
                "delta": taxa_conversao_delta,
                "delta_color": taxa_conversao_delta_color,
                "help": "Contratos assinados / Total de Leads",
            },
        ]
    )

    st.write("")
    col_funil, col_map = st.columns(2)

    with col_funil:
        funil_df = df["situacao"].value_counts().reset_index()
        funil_df.columns = ["situacao", "quantidade"]
        fig_funil = go.Figure(
            go.Funnel(
                y=funil_df["situacao"],
                x=funil_df["quantidade"],
                marker=dict(color=CHART_PALETTE[: len(funil_df)]),
            )
        )
        fig_funil.update_layout(**plotly_layout(title="Funil por Situação"))
        st.plotly_chart(fig_funil, use_container_width=True)

    geo_counts = (
        df_geo.dropna(subset=["latitude", "longitude"])
        .groupby(["cidade_norm", "latitude", "longitude"])
        .size()
        .reset_index(name="quantidade")
    )
    cidades_nao_localizadas = df_geo["titular_cidade"].notna().sum() - geo_counts["quantidade"].sum()
    median_distance_km = df_geo["distancia_evento_km"].dropna().median()

    if geo_counts.empty:
        st.info("Nenhuma cidade de `titular_cidade` foi reconhecida na base de municípios pra montar o mapa.")
    else:
        uf_evento = ESTADO_EVENTO.get(evento_selecionado)
        centro_estado = obter_centro_estado(uf_evento) if uf_evento else None

        ver_brasil_todo = st.checkbox("🔍 Ver Brasil inteiro (em vez de focar no estado do evento)")

        if centro_estado and not ver_brasil_todo:
            centro, zoom = centro_estado, 6
        else:
            centro, zoom = dict(lat=-14.2, lon=-51.9), 3
    with col_map:
        fig_mapa = px.density_map(
            geo_counts,
            lat="latitude",
            lon="longitude",
            z="quantidade",
            radius=28,
            center=centro,
            zoom=zoom,
            map_style="open-street-map",
            color_continuous_scale=[COLORS["background"], COLORS["accent"], COLORS["primary"]],
            hover_name="cidade_norm",
        )
        fig_mapa.update_layout(**plotly_layout(title="Concentração de Expositores por Cidade", height=440))
        fig_mapa.update_layout(margin=dict(l=0, r=0, t=50, b=0))
        st.plotly_chart(fig_mapa, use_container_width=True)

        if pd.notna(median_distance_km):
            st.metric(
                label="Distância mediana até o evento",
                value=f"{median_distance_km:,.0f} km",
                help="Mediana da distância geográfica entre expositores e a cidade do evento.",
            )
            if event_location is not None:
                st.caption(f"Local do evento: {event_city}, {event_state}")

        if cidades_nao_localizadas > 0:
            st.caption(
                    f"⚠️ {int(cidades_nao_localizadas)} registro(s) com cidade não reconhecida na base do IBGE "
                    "não aparecem no mapa (nome digitado fora do padrão, cidade estrangeira, ou em branco)."
                )

    st.write("")
    diario = (
        df.groupby(df["data_cadastro"].dt.date)
        .size()
        .reset_index(name="enviados")
        .rename(columns={"data_cadastro": "data"})
    )
    diario_assinados = (
        vendidos.groupby(vendidos["data_venda"].dt.date)
        .size()
        .reset_index(name="assinados")
        .rename(columns={"data_venda": "data"})
    )
    temporal_comercial = diario.merge(diario_assinados, on="data", how="outer").fillna(0)
    temporal_comercial = temporal_comercial.sort_values("data")

    fig_temporal_comercial = go.Figure()
    fig_temporal_comercial.add_trace(
        go.Scatter(
            x=temporal_comercial["data"],
            y=temporal_comercial["enviados"],
            name="Enviados",
            mode="lines+markers",
            line=dict(color=COLORS["primary"], width=2),
        )
    )
    fig_temporal_comercial.add_trace(
        go.Scatter(
            x=temporal_comercial["data"],
            y=temporal_comercial["assinados"],
            name="Assinados",
            mode="lines+markers",
            line=dict(color=COLORS["accent"], width=2),
        )
    )
    fig_temporal_comercial.update_layout(
        **plotly_layout(title="Evolução Diária — Enviados x Assinados", height=340)
    )
    st.plotly_chart(fig_temporal_comercial, use_container_width=True)


# ════════════════════════════════════════════════════════════════
#  ABA 2 — RECEITA & METAS
# ════════════════════════════════════════════════════════════════
with tab_receita:
    section_header(
        "💵",
        "Receita & Metas",
        f"Evento: {evento_selecionado} · {event_date_info} · Comparação: {janela_label}",
    )

    receita_total = vendidos["valor_contrato"].astype(float).sum()
    receita_total_prev = vendidos_before_current["valor_contrato"].astype(float).sum()

    receita_prevista_total = vendidos["receita_prevista_unidade"].sum()
    receita_prevista_total_prev = vendidos_before_current["receita_prevista_unidade"].sum()

    faltante_valor = max(meta_evento - receita_total, 0)
    faltante_valor_prev = max(meta_evento - receita_total_prev, 0)
    faltante_pct = (faltante_valor / meta_evento * 100) if meta_evento else 0
    faltante_pct_prev = (faltante_valor_prev / meta_evento * 100) if meta_evento else 0

    receita_total_delta, receita_total_delta_color = format_delta(
        receita_total,
        receita_total_prev,
        higher_is_better=True,
        format_str="{:+,.0f}",
    )
    receita_prevista_delta, receita_prevista_delta_color = format_delta(
        receita_prevista_total,
        receita_prevista_total_prev,
        higher_is_better=True,
        format_str="{:+,.0f}",
    )
    faltante_delta, faltante_delta_color = format_delta(
        faltante_valor,
        faltante_valor_prev,
        higher_is_better=False,
        format_str="{:+,.0f}",
    )
    faltante_pct_delta, faltante_pct_delta_color = format_delta(
        faltante_pct,
        faltante_pct_prev,
        higher_is_better=False,
        format_str="{:+.1f}%",
    )

    kpi_row(
        [
            {
                "label": "Receita Total",
                "value": f"R$ {receita_total:,.0f}",
                "delta": f"R$ {receita_total_delta}",
                "delta_color": receita_total_delta_color,
            },
            {"label": "Meta", "value": f"R$ {meta_evento:,.0f}"},
            {
                "label": "Faltante p/ Meta",
                "value": f"R$ {faltante_valor:,.0f}",
                "delta": f"R$ {faltante_delta}",
                "delta_color": faltante_delta_color,
            },
            {
                "label": "% Faltante",
                "value": f"{faltante_pct:.1f}%",
                "delta": faltante_pct_delta,
                "delta_color": faltante_pct_delta_color,
                "help": "Percentual da meta que ainda falta atingir",
            },
        ]
    )

    progresso = min(receita_total / meta_evento, 1.0) if meta_evento else 0
    st.progress(progresso, text=f"{progresso * 100:.1f}% da meta atingida")

    st.write("")
    col_top3, col_prev_real = st.columns(2)

    with col_top3:
        top3 = (
            vendidos.groupby("titular_nome")["valor_contrato"]
            .sum()
            .sort_values(ascending=False)
            .head(3)
            .reset_index()
        )
        fig_top3 = px.bar(
            top3,
            x="valor_contrato",
            y="titular_nome",
            orientation="h",
            color_discrete_sequence=[COLORS["primary"]],
            text="valor_contrato",
        )
        fig_top3.update_traces(texttemplate="R$ %{text:,.0f}", textposition="outside")
        fig_top3.update_layout(**plotly_layout(title="Top 3 Expositores por Receita"))
        fig_top3.update_yaxes(autorange="reversed", title=None)
        fig_top3.update_xaxes(title=None)
        st.plotly_chart(fig_top3, use_container_width=True)

    with col_prev_real:
        prev_real_df = pd.DataFrame(
            {
                "tipo": ["Prevista (tabela m²)", "Realizada"],
                "valor": [receita_prevista_total, receita_total],
            }
        )
        fig_prev_real = px.bar(
            prev_real_df,
            x="tipo",
            y="valor",
            color="tipo",
            color_discrete_sequence=[COLORS["accent"], COLORS["primary"]],
            text="valor",
        )
        fig_prev_real.update_traces(texttemplate="R$ %{text:,.0f}", textposition="outside")
        fig_prev_real.update_layout(**plotly_layout(title="Receita Prevista vs Realizada"))
        fig_prev_real.update_xaxes(title=None)
        st.plotly_chart(fig_prev_real, use_container_width=True)

    st.write("")
    diario_receita = (
        vendidos.groupby(vendidos["data_venda"].dt.date)
        .agg(realizada=("valor_contrato", "sum"), prevista=("receita_prevista_unidade", "sum"))
        .reset_index()
        .rename(columns={"data_venda": "data"})
        .sort_values("data")
    )
    diario_receita["realizada_acum"] = diario_receita["realizada"].cumsum()
    diario_receita["prevista_acum"] = diario_receita["prevista"].cumsum()

    fig_temporal_receita = go.Figure()
    fig_temporal_receita.add_trace(
        go.Scatter(
            x=diario_receita["data"],
            y=diario_receita["realizada_acum"],
            name="Receita Realizada (acum.)",
            mode="lines+markers",
            line=dict(color=COLORS["primary"], width=2),
        )
    )
    fig_temporal_receita.add_trace(
        go.Scatter(
            x=diario_receita["data"],
            y=diario_receita["prevista_acum"],
            name="Receita Prevista (acum.)",
            mode="lines+markers",
            line=dict(color=COLORS["accent"], width=2, dash="dot"),
        )
    )
    fig_temporal_receita.update_layout(
        **plotly_layout(title="Evolução Acumulada da Receita", height=340)
    )
    st.plotly_chart(fig_temporal_receita, use_container_width=True)


# ════════════════════════════════════════════════════════════════
#  ABA 3 — POLÍTICA DE DESCONTOS
# ════════════════════════════════════════════════════════════════
with tab_descontos:
    section_header(
        "🏷️",
        "Política de Descontos",
        f"Evento: {evento_selecionado} · {event_date_info} · Comparação: {janela_label}",
    )

    descontos_positivos = vendidos[vendidos["desconto_unidade"] > 0]
    descontos_positivos_prev = vendidos_before_current[vendidos_before_current["desconto_unidade"] > 0]

    desconto_total = descontos_positivos["desconto_unidade"].sum()
    desconto_total_prev = descontos_positivos_prev["desconto_unidade"].sum()

    desconto_medio = descontos_positivos["desconto_unidade"].mean() if len(descontos_positivos) else 0
    desconto_medio_prev = descontos_positivos_prev["desconto_unidade"].mean() if len(descontos_positivos_prev) else 0

    pct_desconto_medio = (
        (descontos_positivos["desconto_unidade"] / descontos_positivos["receita_prevista_unidade"]).mean() * 100
        if len(descontos_positivos)
        else 0
    )
    pct_desconto_medio_prev = (
        (descontos_positivos_prev["desconto_unidade"] / descontos_positivos_prev["receita_prevista_unidade"]).mean() * 100
        if len(descontos_positivos_prev)
        else 0
    )

    desconto_total_delta, desconto_total_delta_color = format_delta(
        desconto_total,
        desconto_total_prev,
        higher_is_better=False,
        format_str="{:+,.0f}",
    )
    desconto_medio_delta, desconto_medio_delta_color = format_delta(
        desconto_medio,
        desconto_medio_prev,
        higher_is_better=False,
        format_str="{:+,.0f}",
    )
    pct_desconto_medio_delta, pct_desconto_medio_delta_color = format_delta(
        pct_desconto_medio,
        pct_desconto_medio_prev,
        higher_is_better=False,
        format_str="{:+.1f}%",
    )

    kpi_row(
        [
            {
                "label": "Desconto Total",
                "value": f"R$ {desconto_total:,.0f}",
                "delta": f"R$ {desconto_total_delta}",
                "delta_color": desconto_total_delta_color,
            },
            {
                "label": "Desconto Médio",
                "value": f"R$ {desconto_medio:,.0f}",
                "delta": f"R$ {desconto_medio_delta}",
                "delta_color": desconto_medio_delta_color,
            },
            {
                "label": "% Desconto Médio",
                "value": f"{pct_desconto_medio:.1f}%",
                "delta": pct_desconto_medio_delta,
                "delta_color": pct_desconto_medio_delta_color,
                "help": "Média do desconto concedido sobre o valor previsto pela tabela de m²",
            },
        ]
    )

    st.write("")
    diario_desconto = (
        descontos_positivos.groupby(descontos_positivos["data_venda"].dt.date)["desconto_unidade"]
        .sum()
        .reset_index()
        .rename(columns={"data_venda": "data", "desconto_unidade": "desconto"})
        .sort_values("data")
    )
    fig_desconto = px.line(
        diario_desconto,
        x="data",
        y="desconto",
        markers=True,
        color_discrete_sequence=[COLORS["danger"]],
    )
    fig_desconto.update_layout(**plotly_layout(title="Desconto Concedido por Dia", height=320))
    st.plotly_chart(fig_desconto, use_container_width=True)

    st.write("")
    col_desc_corretor, col_desc_top5 = st.columns(2)

    with col_desc_corretor:
        desc_corretor = (
            descontos_positivos.groupby("corretor_nome")["desconto_unidade"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
        )
        fig_desc_corretor = px.bar(
            desc_corretor,
            x="desconto_unidade",
            y="corretor_nome",
            orientation="h",
            color_discrete_sequence=[COLORS["primary_dark"]],
        )
        fig_desc_corretor.update_layout(**plotly_layout(title="Desconto Total por Executivo"))
        fig_desc_corretor.update_yaxes(autorange="reversed", title=None)
        fig_desc_corretor.update_xaxes(title=None)
        st.plotly_chart(fig_desc_corretor, use_container_width=True)

    with col_desc_top5:
        st.markdown("**Top 5 Maiores Descontos Concedidos**")
        top5_desconto = descontos_positivos.sort_values("desconto_unidade", ascending=False).head(5)
        st.dataframe(
            top5_desconto[
                ["titular_nome", "corretor_nome", "desconto_unidade"]
            ].rename(
                columns={
                    "titular_nome": "Expositor",
                    "corretor_nome": "Executivo",
                    "desconto_unidade": "Desconto (R$)",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )


# ════════════════════════════════════════════════════════════════
#  ABA 4 — ESPAÇO & ABL
# ════════════════════════════════════════════════════════════════
with tab_espaco:
    section_header(
        "📐",
        "Espaço & ABL",
        f"Evento: {evento_selecionado} · {event_date_info} · Comparação: {janela_label}",
    )

    abl_total = ABL_TOTAL.get(evento_selecionado, vendidos["area_m2"].astype(float).sum())

    area_preenchida = vendidos["area_m2"].astype(float).sum()
    area_preenchida_prev = vendidos_before_current["area_m2"].astype(float).sum()

    area_disponivel = max(abl_total - area_preenchida, 0)
    area_disponivel_prev = max(abl_total - area_preenchida_prev, 0)

    taxa_ocupacao = (area_preenchida / abl_total * 100) if abl_total else 0
    taxa_ocupacao_prev = (area_preenchida_prev / abl_total * 100) if abl_total else 0

    receita_por_m2 = (receita_total / area_preenchida) if area_preenchida else 0
    receita_por_m2_prev = (receita_total_prev / area_preenchida_prev) if area_preenchida_prev else 0

    receita_potencial_vaga = receita_por_m2 * area_disponivel
    receita_potencial_vaga_prev = receita_por_m2_prev * area_disponivel_prev

    area_preenchida_delta, area_preenchida_delta_color = format_delta(
        area_preenchida,
        area_preenchida_prev,
        higher_is_better=True,
        format_str="{:+,.0f}",
    )
    taxa_ocupacao_delta, taxa_ocupacao_delta_color = format_delta(
        taxa_ocupacao,
        taxa_ocupacao_prev,
        higher_is_better=True,
        format_str="{:+.1f}%",
    )
    receita_por_m2_delta, receita_por_m2_delta_color = format_delta(
        receita_por_m2,
        receita_por_m2_prev,
        higher_is_better=True,
        format_str="{:+,.0f}",
    )
    area_disponivel_delta, area_disponivel_delta_color = format_delta(
        area_disponivel,
        area_disponivel_prev,
        higher_is_better=False,
        format_str="{:+,.0f}",
    )
    receita_potencial_vaga_delta, receita_potencial_vaga_delta_color = format_delta(
        receita_potencial_vaga,
        receita_potencial_vaga_prev,
        higher_is_better=False,
        format_str="{:+,.0f}",
    )

    kpi_row(
        [
            {"label": "ABL Total", "value": f"{abl_total:,.0f} m²"},
            {
                "label": "Área Preenchida",
                "value": f"{area_preenchida:,.0f} m²",
                "delta": f"{area_preenchida_delta} m²",
                "delta_color": area_preenchida_delta_color,
            },
            {
                "label": "Taxa de Ocupação",
                "value": f"{taxa_ocupacao:.1f}%",
                "delta": taxa_ocupacao_delta,
                "delta_color": taxa_ocupacao_delta_color,
            },
            {
                "label": "Receita/m²",
                "value": f"R$ {receita_por_m2:,.0f}",
                "delta": f"R$ {receita_por_m2_delta}",
                "delta_color": receita_por_m2_delta_color,
            },
            {
                "label": "Área Disponível",
                "value": f"{area_disponivel:,.0f} m²",
                "delta": f"{area_disponivel_delta} m²",
                "delta_color": area_disponivel_delta_color,
            },
            {
                "label": "Receita Potencial Vaga",
                "value": f"R$ {receita_potencial_vaga:,.0f}",
                "delta": f"R$ {receita_potencial_vaga_delta}",
                "delta_color": receita_potencial_vaga_delta_color,
                "help": "Receita/m² operado × área ainda disponível",
            },
        ]
    )

    st.write("")
    col_donut, col_scatter = st.columns(2)

    with col_donut:
        donut_df = pd.DataFrame(
            {
                "status": ["Preenchida", "Disponível"],
                "area": [area_preenchida, area_disponivel],
            }
        )
        fig_donut = px.pie(
            donut_df,
            names="status",
            values="area",
            hole=0.55,
            color="status",
            color_discrete_map={"Preenchida": COLORS["primary"], "Disponível": COLORS["border"]},
        )
        fig_donut.update_layout(**donut_layout(title="Área Preenchida vs Disponível"))
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_scatter:
        fig_scatter = px.scatter(
            vendidos,
            x="area_m2",
            y="valor_contrato",
            color="desconto_unidade",
            color_continuous_scale=[COLORS["success"], COLORS["warning"], COLORS["danger"]],
            hover_name="titular_nome",
        )
        fig_scatter.update_layout(**plotly_layout(title="Relação Área × Receita por Unidade"))
        fig_scatter.update_xaxes(title="Área (m²)")
        fig_scatter.update_yaxes(title="Valor do Contrato (R$)")
        st.plotly_chart(fig_scatter, use_container_width=True)

    st.write("")
    if "bloco_pavilhao" in vendidos.columns and "etapa" in vendidos.columns:
        heatmap_df = (
            vendidos.groupby(["etapa", "bloco_pavilhao"])["area_m2"]
            .sum()
            .reset_index()
            .pivot(index="etapa", columns="bloco_pavilhao", values="area_m2")
            .fillna(0)
        )
        fig_heatmap = px.imshow(
            heatmap_df,
            color_continuous_scale=[COLORS["surface"], COLORS["primary"]],
            aspect="auto",
            labels=dict(color="Área ocupada (m²)"),
        )
        fig_heatmap.update_layout(**plotly_layout(title="Ocupação por Etapa × Bloco", height=340))
        st.plotly_chart(fig_heatmap, use_container_width=True)
 
    st.write("")
    st.markdown("**Distribuição por Rua/Pavilhão**")
 
    agg_bloco = (
        vendidos.groupby("bloco_pavilhao")
        .agg(
            qtd_stands=("estande_unidade", "nunique"),
            area_total=("area_m2", "sum"),
            receita_total=("valor_contrato", "sum"),
        )
        .reset_index()
    )
    agg_bloco["receita_por_m2"] = agg_bloco["receita_total"] / agg_bloco["area_total"]
 
    fig_bloco = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=(
            "Qtd. de Stands",
            "Área Total (m²)",
            "Receita Total (R$)",
            "Receita por m² (R$)",
        ),
        horizontal_spacing=0.15,
        vertical_spacing=0.22,
    )
 
    metricas_bloco = [
        ("qtd_stands", 1, 1, CHART_PALETTE[0]),
        ("area_total", 1, 2, CHART_PALETTE[1]),
        ("receita_total", 2, 1, CHART_PALETTE[2]),
        ("receita_por_m2", 2, 2, CHART_PALETTE[3]),
    ]
 
    for coluna, row, col, cor in metricas_bloco:
        ordenado = agg_bloco.sort_values(coluna, ascending=True)
        fig_bloco.add_trace(
            go.Bar(
                x=ordenado[coluna],
                y=ordenado["bloco_pavilhao"],
                orientation="h",
                marker_color=cor,
                showlegend=False,
            ),
            row=row,
            col=col,
        )
 
    layout_base_bloco = plotly_layout(height=540)
    layout_base_bloco.pop("xaxis", None)
    layout_base_bloco.pop("yaxis", None)
    fig_bloco.update_layout(**layout_base_bloco)
    fig_bloco.update_xaxes(gridcolor=COLORS["grid"], zeroline=False, linecolor=COLORS["border"])
    fig_bloco.update_yaxes(gridcolor=COLORS["grid"], zeroline=False, linecolor=COLORS["border"])
    st.plotly_chart(fig_bloco, use_container_width=True)
 
    with st.expander("Ver tabela detalhada por rua/pavilhão"):
        tabela_bloco = (
            agg_bloco.rename(
                columns={
                    "bloco_pavilhao": "Rua/Pavilhão",
                    "qtd_stands": "Qtd. Stands",
                    "area_total": "Área Total (m²)",
                    "receita_total": "Receita Total (R$)",
                    "receita_por_m2": "Receita/m² (R$)",
                }
            )
            .sort_values("Receita Total (R$)", ascending=False)
        )
        st.dataframe(tabela_bloco, hide_index=True, use_container_width=True)

    diario_area = (
        vendidos.groupby(vendidos["data_venda"].dt.date)["area_m2"]
        .sum()
        .reset_index()
        .rename(columns={"data_venda": "data", "area_m2": "area"})
        .sort_values("data")
    )
    diario_area["area_acum"] = diario_area["area"].cumsum()
    fig_temporal_espaco = px.line(
        diario_area,
        x="data",
        y="area_acum",
        markers=True,
        color_discrete_sequence=[COLORS["primary"]],
    )
    fig_temporal_espaco.update_layout(
        **plotly_layout(title="Ocupação Acumulada (m²) ao Longo do Tempo", height=320)
    )
    st.plotly_chart(fig_temporal_espaco, use_container_width=True)