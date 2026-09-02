import os
import shutil
import logging
from infrastructure.dao_financeiro import (
    buscar_pendentes_bronze,
    atualizar_status_bronze,
    inserir_movimentacao_silver,
    inserir_nota_fiscal_silver,
    inserir_fatura_silver
)
from services.llm_parser import extrair_dados_financeiros

def _mover_arquivo_fisico(caminho_atual, pasta_destino):
    """Move o arquivo e retorna o novo caminho absoluto."""
    if not caminho_atual or not os.path.exists(caminho_atual):
        return caminho_atual
    
    diretorio_base = os.path.dirname(os.path.dirname(caminho_atual))
    nome_arquivo = os.path.basename(caminho_atual)
    caminho_novo = os.path.join(diretorio_base, pasta_destino, nome_arquivo)
    
    try:
        shutil.move(caminho_atual, caminho_novo)
        logging.info(f"📁 Arquivo movido para: {pasta_destino}/{nome_arquivo}")
        return caminho_novo
    except Exception as e:
        logging.error(f"Falha ao mover arquivo físico {nome_arquivo}: {e}")
        return caminho_atual # Se falhar, retorna o original para não quebrar o banco

def _deletar_arquivo_fisico(caminho_atual):
    """Deleta o arquivo duplicado."""
    if not caminho_atual or not os.path.exists(caminho_atual):
        return None
    
    try:
        os.remove(caminho_atual)
        logging.info(f"🗑️ Arquivo duplicado deletado: {os.path.basename(caminho_atual)}")
        return "DELETADO"
    except Exception as e:
        logging.error(f"Falha ao deletar arquivo físico {caminho_atual}: {e}")
        return caminho_atual

def executar_pipeline_silver():
    pendentes = buscar_pendentes_bronze()
    
    if not pendentes:
        return
        
    for registro in pendentes:
        id_bronze, origem, tipo_midia, conteudo, caminho, payload_original = registro
        comando_telegram = payload_original.get("comando_telegram")
        
        logging.info(f"🔄 Processando Bronze ID: {id_bronze} | Comando: {comando_telegram}")
        
        try:
            dados_extraidos = extrair_dados_financeiros(tipo_midia, conteudo, caminho, comando_telegram)
            
            if not dados_extraidos:
                raise ValueError("LLM não retornou um JSON válido.")
                
            if comando_telegram == "/gasto":
                inserir_movimentacao_silver(id_bronze, dados_extraidos)
            elif comando_telegram == "/nota":
                inserir_nota_fiscal_silver(id_bronze, dados_extraidos)
            elif comando_telegram == "/fatura":
                inserir_fatura_silver(id_bronze, dados_extraidos)
            else:
                raise ValueError(f"Comando de roteamento desconhecido: {comando_telegram}")
                
            # Move o arquivo físico e pega o novo caminho ANTES de atualizar o banco
            novo_caminho = _mover_arquivo_fisico(caminho, "processadas")
            atualizar_status_bronze(id_bronze, "PROCESSADO", novo_caminho=novo_caminho)
            logging.info(f"✅ Registro {id_bronze} concluído.")
            
        except Exception as e:
            msg_erro = str(e).lower()
            
            # 1. Intercepta erros de violação de UNIQUE constraint
            if "unique constraint" in msg_erro or "duplicate key" in msg_erro or "já existe" in msg_erro:
                logging.warning(f"⚠️ Registro {id_bronze} identificado como DUPLICADO. Descartando...")
                status_caminho = _deletar_arquivo_fisico(caminho)
                atualizar_status_bronze(id_bronze, "DUPLICADO", "Registro já existe na camada Silver.", novo_caminho=status_caminho)
                
            # 2. Intercepta erros transitórios da API do Gemini (503, 429, etc)
            elif "503" in msg_erro or "unavailable" in msg_erro or "429" in msg_erro or "quota" in msg_erro or "500" in msg_erro:
                logging.warning(f"⏳ Indisponibilidade temporária da API no registro {id_bronze}. Será reprocessado no próximo ciclo.")
                
            # 3. Erros definitivos
            else:
                logging.error(f"❌ Erro definitivo no registro {id_bronze}: {e}")
                novo_caminho = _mover_arquivo_fisico(caminho, "erros")
                atualizar_status_bronze(id_bronze, "ERRO", str(e), novo_caminho=novo_caminho)
