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
        """Executa a ETL: Extrai da API, Trata e Grava no Banco via DatabaseManager."""
        print("\n🚀 [Pipeline] Iniciando atualização de reservas...")

        df_dados = fetch_reservas_cvcrm(self.api_url, self.headers)

        sucesso = self.db_manager.salvar_reservas(df_dados)

        if sucesso:
            print("🎉 [Pipeline] Carga concluída com sucesso!")
        else:
            print("❌ [Pipeline] Falha ao gravar dados no banco.")

        return sucesso


if __name__ == "__main__":
    controller = PipelineController(db_uri, url, headers)
    controller.run()