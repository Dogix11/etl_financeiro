import os
import json
import logging
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_conexao():
    try:
        return psycopg2.connect(
            host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
            dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
    except Exception as e:
        logging.error(f"Erro de conexão PostgreSQL: {e}")
        return None

def verificar_hash_existente(hash_arquivo):
    conexao = get_conexao()
    if not conexao: return False
    try:
        with conexao.cursor() as cursor:
            cursor.execute("SELECT 1 FROM bronze.extracao_bruta WHERE hash_arquivo = %s", (hash_arquivo,))
            return cursor.fetchone() is not None
    finally:
        conexao.close()

def registrar_entrada_bronze(tipo_midia, comando, conteudo_texto=None, caminho_arquivo=None, hash_arquivo=None):
    conexao = get_conexao()
    if not conexao: return False
    
    payload_llm = json.dumps({"comando_telegram": comando})
    origem_dado = "telegram"
    
    query = """
        INSERT INTO bronze.extracao_bruta 
        (origem_dado, tipo_midia, conteudo_texto, caminho_arquivo, hash_arquivo, payload_llm)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
        RETURNING id;
    """
    try:
        with conexao.cursor() as cursor:
            cursor.execute(query, (origem_dado, tipo_midia, conteudo_texto, caminho_arquivo, hash_arquivo, payload_llm))
            id_gerado = cursor.fetchone()[0]
        conexao.commit()
        return id_gerado
    except Exception as e:
        logging.error(f"Erro inserção Bronze: {e}")
        conexao.rollback()
        return False
    finally:
        conexao.close()

def buscar_pendentes_bronze():
    conexao = get_conexao()
    if not conexao: return []
    try:
        with conexao.cursor() as cursor:
            cursor.execute("""
                SELECT id, origem_dado, tipo_midia, conteudo_texto, caminho_arquivo, payload_llm
                FROM bronze.extracao_bruta
                WHERE status_integracao = 'PENDENTE'
                ORDER BY inserido_em ASC;
            """)
            return cursor.fetchall()
    finally:
        conexao.close()

def atualizar_status_bronze(id_bronze, status, mensagem_erro=None):
    conexao = get_conexao()
    if not conexao: return
    try:
        with conexao.cursor() as cursor:
            cursor.execute("""
                UPDATE bronze.extracao_bruta
                SET status_integracao = %s, mensagem_erro = %s
                WHERE id = %s;
            """, (status, mensagem_erro, id_bronze))
        conexao.commit()
    except Exception as e:
        logging.error(f"Erro ao atualizar status Bronze: {e}")
        conexao.rollback()
    finally:
        conexao.close()

def inserir_movimentacao_silver(id_bronze, dados):
    conexao = get_conexao()
    if not conexao: raise Exception("Sem conexão com o banco de dados.")
    
    try:
        with conexao.cursor() as cursor:
            # 1. Inserir dados na Silver
            query = """
                INSERT INTO silver.movimentacoes_financeiras (
                    bronze_id, data_transacao, valor, tipo_movimentacao, direcao, 
                    contraparte, categoria, descricao, titular_pagamento, centro_custo, 
                    percentual_seu, percentual_esposa, valor_cota_sua, valor_cota_esposa
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """
            cursor.execute(query, (
                id_bronze, dados.get('data_transacao'), dados.get('valor'), 
                dados.get('tipo_movimentacao'), dados.get('direcao'), dados.get('contraparte'), 
                dados.get('categoria'), dados.get('descricao'), dados.get('titular_pagamento'), 
                dados.get('centro_custo'), dados.get('percentual_seu'), dados.get('percentual_esposa'), 
                dados.get('valor_cota_sua'), dados.get('valor_cota_esposa')
            ))
            silver_id = cursor.fetchone()[0]

            # 2. Registrar no Outbox
            payload_outbox = json.dumps({"id": silver_id, "bronze_id": id_bronze})
            cursor.execute("""
                INSERT INTO public.outbox_events (tipo_evento, payload)
                VALUES (%s, %s::jsonb);
            """, ("NOVA_MOVIMENTACAO", payload_outbox))
            
        conexao.commit()
    except Exception as e:
        conexao.rollback()
        raise Exception(f"Erro na transação Silver (Movimentação): {e}")
    finally:
        conexao.close()


def inserir_nota_fiscal_silver(id_bronze, dados):
    conexao = get_conexao()
    if not conexao: raise Exception("Sem conexão com o banco de dados.")
    
    try:
        with conexao.cursor() as cursor:
            # 1. Inserir Nota Fiscal
            query_nota = """
                INSERT INTO silver.notas_fiscais (
                    bronze_id, chave_acesso, cnpj_emissor, nome_emissor, data_emissao,
                    valor_subtotal, valor_desconto, valor_acrescimo, valor_total,
                    categoria, forma_pagamento, natureza_operacao, titular_pagamento,
                    centro_custo, percentual_seu, percentual_esposa, valor_cota_sua, valor_cota_esposa
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """
            cursor.execute(query_nota, (
                id_bronze, dados.get('chave_acesso'), dados.get('cnpj_emissor'), dados.get('nome_emissor'), 
                dados.get('data_emissao'), dados.get('valor_subtotal'), dados.get('valor_desconto'), 
                dados.get('valor_acrescimo'), dados.get('valor_total'), dados.get('categoria'), 
                dados.get('forma_pagamento'), dados.get('natureza_operacao'), dados.get('titular_pagamento'), 
                dados.get('centro_custo'), dados.get('percentual_seu'), dados.get('percentual_esposa'), 
                dados.get('valor_cota_sua'), dados.get('valor_cota_esposa')
            ))
            id_nota = cursor.fetchone()[0]

            # 2. Inserir Itens da Nota
            itens = dados.get('itens', [])
            if itens:
                query_item = """
                    INSERT INTO silver.itens_nota_fiscal (
                        nota_fiscal_id, nome_produto, quantidade, unidade_medida, 
                        preco_unitario, preco_total_item, preco_total_liquido, categoria_produto
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """
                for item in itens:
                    cursor.execute(query_item, (
                        id_nota, item.get('nome_produto'), item.get('quantidade'), 
                        item.get('unidade_medida'), item.get('preco_unitario'), 
                        item.get('preco_total_item'), item.get('preco_total_liquido'), 
                        item.get('categoria_produto')
                    ))

            # 3. Registrar no Outbox
            payload_outbox = json.dumps({"id_nota": id_nota, "bronze_id": id_bronze})
            cursor.execute("""
                INSERT INTO public.outbox_events (tipo_evento, payload)
                VALUES (%s, %s::jsonb);
            """, ("NOVA_NOTA_FISCAL", payload_outbox))

        conexao.commit()
    except Exception as e:
        conexao.rollback()
        raise Exception(f"Erro na transação Silver (Nota): {e}")
    finally:
        conexao.close()


def inserir_fatura_silver(id_bronze, dados):
    conexao = get_conexao()
    if not conexao: raise Exception("Sem conexão com o banco de dados.")
    
    try:
        with conexao.cursor() as cursor:
            # 1. Inserir Fatura
            query = """
                INSERT INTO silver.faturas (
                    bronze_id, banco, mes_referencia, valor_fatura, data_vencimento, 
                    data_pagamento, status_pagamento, instituicao_emissora, titular_cartao
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """
            cursor.execute(query, (
                id_bronze, dados.get('banco'), dados.get('mes_referencia'), 
                dados.get('valor_fatura'), dados.get('data_vencimento'), dados.get('data_pagamento'), 
                dados.get('status_pagamento'), dados.get('instituicao_emissora'), dados.get('titular_cartao')
            ))
            silver_id = cursor.fetchone()[0]

            # 2. Registrar no Outbox
            payload_outbox = json.dumps({"id_fatura": silver_id, "bronze_id": id_bronze})
            cursor.execute("""
                INSERT INTO public.outbox_events (tipo_evento, payload)
                VALUES (%s, %s::jsonb);
            """, ("NOVA_FATURA", payload_outbox))
            
        conexao.commit()
    except Exception as e:
        conexao.rollback()
        raise Exception(f"Erro na transação Silver (Fatura): {e}")
    finally:
        conexao.close()
