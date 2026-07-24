import streamlit as st
import pandas as pd
from app.database import DatabaseManager
from app.get_data import fetch_reservas_cvcrm

url = 'https://exagerado.cvcrm.com.br/api/v1/comercial/reservas'
email = st.secrets["email"]
token = st.secrets["token"]
db_uri = st.secrets["db_uri"]
headers = {
    "email": email,
    "token": token,
    "accept": "application/json"
}

class PipelineController:

    def __init__(self, db_uri: str, api_url: str, headers: dict):
        self.db_manager = DatabaseManager(db_uri)
        self.api_url = api_url
        self.headers = headers

    def run(self) -> bool:
        """Executa a ETL: Extrai da API (Ativas e Vendidas), Trata e Grava no Banco."""
        print("\n🚀 [Pipeline] Iniciando atualização de reservas...")

        # 1. Parâmetros para esteira ativa / não vendidas
        params_ativas = {
            "faturar": "false",
            "condicao_completa": "true",
            "campos_adicionais_reserva_contrato": "true",
            "pagina": 1,
            "registros_por_pagina": 500,
        }

        # 2. Parâmetros para vendidas / integradas
        params_vendidas = {
            "retornar_integradas": "true",
            "situacao": "todas",
            "condicao_completa": "true",
            "campos_adicionais_reserva_contrato": "true",
            "pagina": 1,
            "registros_por_pagina": 500,
        }

        print("🔄 [Pipeline] Buscando reservas ativas...")
        df_ativas = fetch_reservas_cvcrm(
            self.api_url, self.headers, params=params_ativas
        )

        print("🔄 [Pipeline] Buscando reservas vendidas...")
        df_vendidas = fetch_reservas_cvcrm(
            self.api_url, self.headers, params=params_vendidas
        )

        df_dados = pd.concat([df_ativas, df_vendidas], ignore_index=True)
        df_dados = df_dados.drop_duplicates(
            subset=["id_proposta_cv"], keep="last"
        )

        print(
            f"📦 [Pipeline] Total consolidado sem duplicatas: {len(df_dados)} registros."
        )

        sucesso = self.db_manager.salvar_reservas(df_dados)

        if sucesso:
            print("🎉 [Pipeline] Carga concluída com sucesso!")
        else:
            print("❌ [Pipeline] Falha ao gravar dados no banco.")

        return sucesso


if __name__ == "__main__":
    controller = PipelineController(db_uri, url, headers)
    controller.run()