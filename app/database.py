import logging
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.types import DateTime, Float, String

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DatabaseManager")


class DatabaseManager:

    def __init__(self, connection_string: str):
        """Inicializa a conexão com o Banco de Dados através do SQLAlchemy Engine."""
        self.connection_string = connection_string
        try:
            self.engine = create_engine(
                self.connection_string,
                pool_pre_ping=True,
                pool_size=5,  
                max_overflow=10,
            )
            logger.info("Engine do Banco de Dados inicializado com sucesso.")
        except Exception as e:
            logger.error(
                f"Erro ao criar o Engine do Banco de Dados: {str(e)}"
            )
            raise e

    def salvar_reservas(
        self, df: pd.DataFrame, tabela_nome: str = "reservas_cvcrm"
    ) -> bool:
        if df is None or df.empty:
            logger.warning("DataFrame enviado está vazio. Operação ignorada.")
            return False

        dtypes_especificos = {
            "id_reserva": String(50),
            "data_cadastro": DateTime(),
            "data_venda": DateTime(),
            "data_contrato": DateTime(),
            "data_cancelamento": DateTime(),
            "area_m2": Float(),
            "valor_contrato": Float(),
            "valor_por_m2": Float(),
        }

        try:
            with self.engine.begin() as conn:
                df.to_sql(
                    name=tabela_nome,
                    con=conn,
                    if_exists="replace",
                    index=False,
                    dtype=dtypes_especificos,
                )
            logger.info(
                f"Tabela '{tabela_nome}' recriada e populada com sucesso ({len(df)} linhas)."
            )
            return True
        except SQLAlchemyError as e:
            logger.error(f"Erro ao salvar dados na tabela {tabela_nome}: {e}")
            return False

    def carregar_reservas(
            self, tabela_nome: str = "reservas_cvcrm"
        ) -> pd.DataFrame:
            """Lê os dados brutos de reservas gravados no banco pelo ETL."""
            query = text(f"SELECT * FROM {tabela_nome}")
            try:
                with self.engine.connect() as conn:
                    df = pd.read_sql(query, con=conn)
    
                colunas_datas = [
                    "data_cadastro",
                    "data_venda",
                    "data_contrato",
                    "data_cancelamento",
                ]
                for col in colunas_datas:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors="coerce")
    
                logger.info(
                    f"Carregadas {len(df)} linhas da tabela '{tabela_nome}'."
                )
                return df
            except SQLAlchemyError as e:
                logger.error(f"Erro ao carregar reservas do banco: {e}")
                return pd.DataFrame()

    