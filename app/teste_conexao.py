from db_conexao import DatabaseManager

def testar_conexao():
    try:
        # Pega a conexão gerenciada
        with DatabaseManager.get_conexao() as conn:
            with conn.cursor() as cursor:
                # Tenta buscar a versão do PostgreSQL
                cursor.execute("SELECT version();")
                versao = cursor.fetchone()
                print(f"Sucesso! Conectado ao: {versao[0]}")
    except Exception as e:
        print(f"Falha ao conectar: {e}")

if __name__ == "__main__":
    testar_conexao()
