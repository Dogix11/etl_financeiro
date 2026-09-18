import os
import hashlib
import logging
from infrastructure.dao_financeiro import verificar_hash_existente, registrar_entrada_bronze

def _gerar_hash_arquivo(caminho_arquivo):
    if not caminho_arquivo or not os.path.exists(caminho_arquivo):
        return None
    hasher = hashlib.sha256()
    with open(caminho_arquivo, 'rb') as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

def _gerar_hash_texto(texto):
    if not texto:
        return None
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()

def processar_ingestao_bronze(tipo_midia, comando, conteudo_texto=None, caminho_arquivo=None, nome_remetente="Desconhecido"):
    hash_dado = _gerar_hash_arquivo(caminho_arquivo) if caminho_arquivo else _gerar_hash_texto(conteudo_texto)

    if hash_dado and verificar_hash_existente(hash_dado):
        if caminho_arquivo and os.path.exists(caminho_arquivo):
            os.remove(caminho_arquivo)
            logging.info(f"🗑️ Arquivo duplicado descartado: {caminho_arquivo}")
        return False, "⚠️ Dado ignorado: Este arquivo ou texto já foi processado anteriormente."

    id_gerado = registrar_entrada_bronze(
        tipo_midia=tipo_midia, 
        comando=comando, 
        conteudo_texto=conteudo_texto, 
        caminho_arquivo=caminho_arquivo, 
        hash_arquivo=hash_dado,
        nome_remetente=nome_remetente
    )

    if id_gerado:
        return True, f"✅ Recebido! Protocolo #{id_gerado} gerado com sucesso."
    return False, "❌ Ocorreu uma falha ao salvar os dados no banco."
