import os
import logging
from contextlib import contextmanager
from dotenv import load_dotenv
from psycopg2 import pool, DatabaseError

# Configuração básica de logs para rastrear erros
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Carrega as variáveis do arquivo .env
load_dotenv()

class DatabaseManager:
    _pool = None

    @classmethod
    def inicializar_pool(cls):
        """Cria o pool de conexões (Deve ser chamado apenas uma vez ao iniciar a aplicação)"""
        if cls._pool is None:
            try:
                cls._pool = pool.SimpleConnectionPool(
                    minconn=1,
                    maxconn=10,
                    host=os.getenv("DB_HOST"),
                    port=os.getenv("DB_PORT"),
                    database=os.getenv("DB_NAME"),
                    user=os.getenv("DB_USER"),
                    password=os.getenv("DB_PASSWORD")
                )
                if cls._pool:
                    logging.info("Pool de conexões com o PostgreSQL criado com sucesso.")
            except DatabaseError as e:
                logging.error(f"Erro ao inicializar o pool de conexões: {e}")
                raise

    @classmethod
    @contextmanager
    def get_conexao(cls):
        """
        Gerenciador de contexto para emprestar e devolver conexões ao pool de forma segura.
        Uso:
            with DatabaseManager.get_conexao() as conn:
                cursor = conn.cursor()
                cursor.execute(...)
        """
        if cls._pool is None:
            cls.inicializar_pool()
            
        conn = None
        try:
            # Pega uma conexão emprestada do pool
            conn = cls._pool.getconn()
            yield conn
        except DatabaseError as e:
            logging.error(f"Erro de banco de dados durante a transação: {e}")
            if conn:
                conn.rollback() # Desfaz qualquer alteração se houver erro
            raise
        finally:
            if conn:
                # Devolve a conexão para o pool
                cls._pool.putconn(conn)

    @classmethod
    def fechar_pool(cls):
        """Encerra todas as conexões (Ideal para quando desligar o bot/servidor)"""
        if cls._pool:
            cls._pool.closeall()
            logging.info("Pool de conexões encerrado.")

# Inicializa o pool automaticamente ao importar este arquivo
DatabaseManager.inicializar_pool()
