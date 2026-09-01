import logging
from infrastructure.dao_financeiro import (
    buscar_pendentes_bronze,
    atualizar_status_bronze,
    inserir_movimentacao_silver,
    inserir_nota_fiscal_silver,
    inserir_fatura_silver
)
from services.llm_parser import extrair_dados_financeiros

def executar_pipeline_silver():
    pendentes = buscar_pendentes_bronze()
    
    if not pendentes:
        return
        
    for registro in pendentes:
        id_bronze, origem, tipo_midia, conteudo, caminho, payload_original = registro
        
        # Extrai o comando exato que originou o registro (ex: "/gasto", "/nota")
        comando_telegram = payload_original.get("comando_telegram")
        
        logging.info(f"🔄 Processando Bronze ID: {id_bronze} | Comando: {comando_telegram}")
        
        try:
            # Passamos o comando_telegram para o parser saber qual prompt usar
            dados_extraidos = extrair_dados_financeiros(tipo_midia, conteudo, caminho, comando_telegram)
            
            if not dados_extraidos:
                raise ValueError("LLM não retornou um JSON válido.")
                
            # Roteamento determinístico baseado na origem do dado
            if comando_telegram == "/gasto":
                inserir_movimentacao_silver(id_bronze, dados_extraidos)
            elif comando_telegram == "/nota":
                inserir_nota_fiscal_silver(id_bronze, dados_extraidos)
            elif comando_telegram == "/fatura":
                inserir_fatura_silver(id_bronze, dados_extraidos)
            else:
                raise ValueError(f"Comando de roteamento desconhecido: {comando_telegram}")
                
            atualizar_status_bronze(id_bronze, "PROCESSADO")
            logging.info(f"✅ Registro {id_bronze} migrado para a camada Silver com sucesso.")
            
        except Exception as e:
            logging.error(f"❌ Erro no registro {id_bronze}: {e}")
            atualizar_status_bronze(id_bronze, "ERRO", str(e))
