"""
geo_utils.py — Geocodificação de cidades brasileiras
──────────────────────────────────────────────────────
Baixa (e cacheia) a base pública de municípios do IBGE
(kelvins/municipios-brasileiros no GitHub) e expõe funções pra:
  - juntar `titular_cidade` (+ opcionalmente `titular_estado`) com lat/lon
  - achar o centróide de um estado (UF), pra centralizar/dar zoom no mapa
"""

import unicodedata

import pandas as pd
import streamlit as st

URL_MUNICIPIOS = "https://raw.githubusercontent.com/kelvins/Municipios-Brasileiros/main/csv/municipios.csv"
URL_ESTADOS = "https://raw.githubusercontent.com/kelvins/Municipios-Brasileiros/main/csv/estados.csv"


def normalizar_texto(texto) -> str | None:
    """Uppercase + remove acentos, pra join tolerante a 'São Paulo' vs 'Sao paulo'."""
    if pd.isna(texto) or str(texto).strip() == "":
        return None
    texto = str(texto).strip().upper()
    texto = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return texto


@st.cache_data(ttl=60 * 60 * 24)  # 24h — dados de municípios não mudam
def carregar_municipios() -> pd.DataFrame:
    """Base completa (sem dedupe) — cidade_norm pode se repetir entre UFs diferentes."""
    df_mun = pd.read_csv(URL_MUNICIPIOS)
    df_uf = pd.read_csv(URL_ESTADOS)[["codigo_uf", "uf"]]
    df_mun = df_mun.merge(df_uf, on="codigo_uf", how="left")
    df_mun["cidade_norm"] = df_mun["nome"].apply(normalizar_texto)
    return df_mun[["cidade_norm", "uf", "latitude", "longitude"]]


@st.cache_data(ttl=60 * 60 * 24)
def carregar_estados() -> pd.DataFrame:
    df_uf = pd.read_csv(URL_ESTADOS)
    df_uf["nome_norm"] = df_uf["nome"].apply(normalizar_texto)
    df_uf["uf_norm"] = df_uf["uf"].apply(normalizar_texto)
    return df_uf  # codigo_uf, uf, nome, latitude, longitude, regiao, nome_norm, uf_norm


def resolver_uf(valor_estado) -> str | None:
    """Aceita sigla ('RJ') ou nome completo ('Rio de Janeiro') e devolve a sigla (UF)."""
    valor_norm = normalizar_texto(valor_estado)
    if valor_norm is None:
        return None
    df_uf = carregar_estados()
    match = df_uf[(df_uf["uf_norm"] == valor_norm) | (df_uf["nome_norm"] == valor_norm)]
    return match.iloc[0]["uf"] if not match.empty else None


def obter_centro_estado(uf: str) -> dict | None:
    """{'lat': ..., 'lon': ...} do centróide de um estado, pra centralizar o mapa nele."""
    df_uf = carregar_estados()
    match = df_uf[df_uf["uf"] == uf]
    if match.empty:
        return None
    row = match.iloc[0]
    return {"lat": row["latitude"], "lon": row["longitude"]}


def geocodificar(df: pd.DataFrame, col_cidade: str, col_estado: str | None = None) -> pd.DataFrame:
    """
    Adiciona `latitude`/`longitude` ao DataFrame a partir da coluna de cidade.

    Se `col_estado` for passado, faz o join preciso por (cidade, UF) primeiro
    — resolve casos como duas cidades "Bom Jesus" em estados diferentes.
    Linhas sem UF (ou sem match nesse join) caem no fallback por cidade,
    mantendo a primeira ocorrência encontrada. Cidades não reconhecidas
    ficam com lat/lon nulos e simplesmente não aparecem no mapa.
    """
    df = df.copy()
    df["cidade_norm"] = df[col_cidade].apply(normalizar_texto)
    df_mun = carregar_municipios()

    fallback = df_mun.drop_duplicates(subset="cidade_norm", keep="first")[
        ["cidade_norm", "latitude", "longitude"]
    ]

    if col_estado and col_estado in df.columns:
        df["uf"] = df[col_estado].apply(resolver_uf)
        df = df.merge(df_mun, on=["cidade_norm", "uf"], how="left")

        sem_match = df["latitude"].isna()
        if sem_match.any():
            preenchido = df.loc[sem_match, ["cidade_norm"]].merge(fallback, on="cidade_norm", how="left")
            df.loc[sem_match, "latitude"] = preenchido["latitude"].values
            df.loc[sem_match, "longitude"] = preenchido["longitude"].values
    else:
        df = df.merge(fallback, on="cidade_norm", how="left")

    return df