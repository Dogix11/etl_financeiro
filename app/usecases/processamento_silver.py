import os
import shutil
import logging
from infrastructure.dao_financeiro import (
    buscar_pendentes_bronze,
    atualizar_status_bronze,
    inserir_movimentacao_silver,
    inserir_nota_fiscal_silver,
    inserir_fatura_silver,
    registrar_log_llm
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
        return caminho_atual

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

        # 1. Extrai as informações salvas no payload para encontrar o fluxo correto
        comando_telegram = payload_original.get("comando_telegram")
        nome_remetente = payload_original.get("nome_remetente", "Desconhecido")

        logging.info(f"🔄 Processando Bronze ID: {id_bronze} | Comando: {comando_telegram} | De: {nome_remetente}")

        try:
            # 2. Desempacota a tupla (Dados + Metadados de Performance)
            dados_extraidos, metadados = extrair_dados_financeiros(tipo_midia, conteudo, caminho, comando_telegram, nome_remetente)

            if not dados_extraidos:
                raise ValueError("LLM não retornou um JSON válido.")

            # 3. Grava o log de performance LLM no banco de dados
            if metadados:
                registrar_log_llm(id_bronze, metadados)
                logging.info(f"📊 Metadados LLM: {metadados.get('latency_seconds')}s | In: {metadados.get('prompt_tokens')} tokens | Out: {metadados.get('output_tokens')} tokens")

            if comando_telegram == "/gasto":
                logging.info(f"Tentando inserir {len(dados_extraidos)} itens referentes ao registro {id_bronze}.")
                for gasto in dados_extraidos:
                    inserir_movimentacao_silver(id_bronze, gasto)

            elif comando_telegram == "/nota":
                nota_dict = dados_extraidos[0]
                id_nota_fiscal, itens_inseridos = inserir_nota_fiscal_silver(id_bronze, nota_dict)

                for item_nota in itens_inseridos:
                    movimentacao_espelho = {
                        "data_transacao": nota_dict.get('data_emissao'),
                        "valor": item_nota['preco_total_liquido'],
                        "tipo_movimentacao": "despesa",
                        "direcao": "OUT",
                        "contraparte": nota_dict.get('nome_emissor'),
                        "categoria": item_nota['categoria_produto'],
                        "descricao": item_nota['nome_produto'],
                        "titular_pagamento": nota_dict.get('titular_pagamento'),
                        "centro_custo": nota_dict.get('centro_custo'),
                        "percentual_diogo": item_nota['percentual_diogo'],
                        "percentual_flora": item_nota['percentual_flora'],
                        "valor_cota_diogo": item_nota['valor_cota_diogo'],
                        "valor_cota_flora": item_nota['valor_cota_flora'],
                        "nota_fiscal_id": id_nota_fiscal,
                        "item_nota_id": item_nota['id']
                    }
                    inserir_movimentacao_silver(id_bronze, movimentacao_espelho)
                logging.info(f"Nota Fiscal {id_nota_fiscal} e {len(itens_inseridos)} itens espelhados no Livro-Razão.")

            elif comando_telegram == "/fatura":
                fatura_dict = dados_extraidos[0]
                inserir_fatura_silver(id_bronze, fatura_dict)
            else:
                raise ValueError(f"Comando de roteamento desconhecido: {comando_telegram}")

            novo_caminho = _mover_arquivo_fisico(caminho, "processadas")
            atualizar_status_bronze(id_bronze, "PROCESSADO", novo_caminho=novo_caminho)
            logging.info(f"✅ Registro {id_bronze} concluído.")

        except Exception as e:
            msg_erro = str(e).lower()

            if "unique constraint" in msg_erro or "duplicate key" in msg_erro or "já existe" in msg_erro:
                logging.warning(f"⚠️ Registro {id_bronze} identificado como DUPLICADO. Descartando...")
                status_caminho = _deletar_arquivo_fisico(caminho)
                atualizar_status_bronze(id_bronze, "DUPLICADO", "Registro já existe na camada Silver.", novo_caminho=status_caminho)

            elif "503" in msg_erro or "unavailable" in msg_erro or "429" in msg_erro or "quota" in msg_erro or "500" in msg_erro:
                logging.warning(f"⏳ Indisponibilidade temporária da API no registro {id_bronze}. Será reprocessado no próximo ciclo.")

            else:
                logging.error(f"❌ Erro definitivo no registro {id_bronze}: {e}")
                novo_caminho = _mover_arquivo_fisico(caminho, "erros")
                atualizar_status_bronze(id_bronze, "ERRO", str(e), novo_caminho=novo_caminho)
