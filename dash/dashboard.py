import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from geo_utils import geocodificar, obter_centro_estado
from maps import METAS, TABELA_METRO, ABL_TOTAL, ESTADO_EVENTO
from theme import (
    PAGE_CONFIG,
    COLORS,
    CHART_PALETTE,
    inject_custom_css,
    section_header,
    kpi_row,
    plotly_layout,
    donut_layout,
)
import sys
from pathlib import Path

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

df = df_reservas_all[df_reservas_all["imobiliaria_nome"] == evento_selecionado].copy()

df["receita_prevista_unidade"] = df["area_m2"].astype(float) * valor_m2_evento
df["desconto_unidade"] = df["receita_prevista_unidade"] - df["valor_contrato"].astype(float)

vendidos = df[(df["situacao"] == "Contrato Assinado") | 
              (df["situacao"] == "Vendida")].copy()


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
    section_header("🤝", "Comercial & Funil", f"Evento: {evento_selecionado}")

    expositores_totais = df["titular_nome"].nunique()
    to_dentro = df[df["situacao"] == "Link To Dentro Recebido e Validado"]
    contratos_enviados = df[df["situacao"] == "Contrato Enviado"]
    total_reservas = len(df)
    contratos_assinados = len(vendidos)
    taxa_conversao = (contratos_assinados / total_reservas * 100) if total_reservas else 0

    kpi_row(
        [
            {"label": "Expositores Totais", "value": f"{expositores_totais}"},
            {"label": "To Dentro", "value": f"{len(to_dentro)}"},
            {"label": "Contratos Enviados", "value": f"{len(contratos_enviados)}"},
            {"label": "Contratos Assinados", "value": f"{contratos_assinados}"},
            {
                "label": "Taxa de Conversão",
                "value": f"{taxa_conversao:.1f}%",
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

    df_geo = geocodificar(df, "titular_cidade", "titular_estado")
    geo_counts = (
        df_geo.dropna(subset=["latitude", "longitude"])
        .groupby(["cidade_norm", "latitude", "longitude"])
        .size()
        .reset_index(name="quantidade")
    )
    cidades_nao_localizadas = df_geo["titular_cidade"].notna().sum() - geo_counts["quantidade"].sum()

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
    section_header("💵", "Receita & Metas", f"Evento: {evento_selecionado}")

    receita_total = vendidos["valor_contrato"].astype(float).sum()
    receita_prevista_total = vendidos["receita_prevista_unidade"].sum()
    faltante_valor = max(meta_evento - receita_total, 0)
    faltante_pct = (faltante_valor / meta_evento * 100) if meta_evento else 0

    kpi_row(
        [
            {"label": "Receita Total", "value": f"R$ {receita_total:,.0f}"},
            {"label": "Meta", "value": f"R$ {meta_evento:,.0f}"},
            {"label": "Faltante p/ Meta", "value": f"R$ {faltante_valor:,.0f}"},
            {
                "label": "% Faltante",
                "value": f"{faltante_pct:.1f}%",
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
    section_header("🏷️", "Política de Descontos", f"Evento: {evento_selecionado}")

    descontos_positivos = vendidos[vendidos["desconto_unidade"] > 0]

    desconto_total = descontos_positivos["desconto_unidade"].sum()
    desconto_medio = descontos_positivos["desconto_unidade"].mean() if len(descontos_positivos) else 0
    pct_desconto_medio = (
        (descontos_positivos["desconto_unidade"] / descontos_positivos["receita_prevista_unidade"]).mean() * 100
        if len(descontos_positivos)
        else 0
    )

    kpi_row(
        [
            {"label": "Desconto Total", "value": f"R$ {desconto_total:,.0f}"},
            {"label": "Desconto Médio", "value": f"R$ {desconto_medio:,.0f}"},
            {
                "label": "% Desconto Médio",
                "value": f"{pct_desconto_medio:.1f}%",
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
        fig_desc_corretor.update_layout(**plotly_layout(title="Desconto Total por Corretor"))
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
                    "corretor_nome": "Corretor",
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
    section_header("📐", "Espaço & ABL", f"Evento: {evento_selecionado}")

    abl_total = ABL_TOTAL.get(evento_selecionado, vendidos["area_m2"].astype(float).sum())

    area_preenchida = vendidos["area_m2"].astype(float).sum()
    area_disponivel = max(abl_total - area_preenchida, 0)
    taxa_ocupacao = (area_preenchida / abl_total * 100) if abl_total else 0
    receita_por_m2 = (receita_total / area_preenchida) if area_preenchida else 0
    receita_potencial_vaga = receita_por_m2 * area_disponivel

    kpi_row(
        [
            {"label": "ABL Total", "value": f"{abl_total:,.0f} m²"},
            {"label": "Área Preenchida", "value": f"{area_preenchida:,.0f} m²"},
            {"label": "Taxa de Ocupação", "value": f"{taxa_ocupacao:.1f}%"},
            {"label": "Receita/m²", "value": f"R$ {receita_por_m2:,.0f}"},
            {"label": "Área Disponível", "value": f"{area_disponivel:,.0f} m²"},
            {
                "label": "Receita Potencial Vaga",
                "value": f"R$ {receita_potencial_vaga:,.0f}",
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
    if "bloco" in vendidos.columns and "etapa" in vendidos.columns:
        heatmap_df = (
            vendidos.groupby(["etapa", "bloco"])["area_m2"]
            .sum()
            .reset_index()
            .pivot(index="etapa", columns="bloco", values="area_m2")
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