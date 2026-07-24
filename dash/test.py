import sys
from pathlib import Path
import streamlit as st

from maps import METAS

project_root = Path(__file__).resolve().parents[1]
dash_dir = Path(__file__).resolve().parent
for path in (str(project_root), str(dash_dir)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.database import DatabaseManager
from app.main import PipelineController, url, headers
db_uri = st.secrets["db_uri"]

def get_db_manager():
    return DatabaseManager(db_uri)


db = get_db_manager()

def load_data():
    return db.carregar_reservas()

df_reservas_all = load_data()


eventos_disponiveis = sorted(
    set(df_reservas_all["imobiliaria_nome"].dropna().unique()) & set(METAS.keys())
)

print(eventos_disponiveis)
