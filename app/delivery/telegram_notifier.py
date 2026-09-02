import os
import requests
import logging

def _formatar_mensagem(id_evento, tipo_evento, payload):
    # Garante que o payload é um dicionário, mesmo se vier nulo do banco
    payload = payload or {}
    
    if tipo_evento == 'nota_fiscal_inserida':
        return (
            f"🛒 <b>Nota Fiscal Processada</b>\n"
            f"Emissor: {payload.get('nome_emissor', 'N/A')}\n"
            f"Valor Total: R$ {payload.get('valor_total', 0):.2f}\n"
            f"Sua Cota: R$ {payload.get('valor_cota_sua', 0):.2f}\n"
            f"Cota Flora: R$ {payload.get('valor_cota_esposa', 0):.2f}"
        )
    elif tipo_evento == 'movimentacao_inserida':
        return (
            f"💸 <b>Gasto Avulso Processado</b>\n"
            f"Local: {payload.get('contraparte', 'N/A')}\n"
            f"Valor Total: R$ {payload.get('valor', 0):.2f}\n"
            f"Sua Cota: R$ {payload.get('valor_cota_sua', 0):.2f}\n"
            f"Cota Flora: R$ {payload.get('valor_cota_esposa', 0):.2f}"
        )
    elif tipo_evento == 'fatura_inserida':
        return (
            f"💳 <b>Fatura Processada</b>\n"
            f"Banco: {payload.get('banco', 'N/A')}\n"
            f"Vencimento: {payload.get('data_vencimento', 'N/A')}\n"
            f"Valor Total: R$ {payload.get('valor_fatura', 0):.2f}"
        )
    elif tipo_evento == 'NOVANOTAFISCAL':
        return (
            f"🧾 <b>Nova Nota Fiscal Recebida</b>\n"
            f"Status: Aguardando processamento\n"
            f"Protocolo: <code>{id_evento}</code>"
        )
        
    return f"✅ <b>Evento Processado:</b> {tipo_evento}\nProtocolo: <code>{id_evento}</code>"

def disparar_mensagem_telegram(id_evento, tipo_evento, payload):
    """Envia uma única mensagem formatada para a API do Telegram."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID") 
    
    if not bot_token or not chat_id:
        raise ValueError("Credenciais do Telegram ausentes no .env")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    mensagem = _formatar_mensagem(id_evento, tipo_evento, payload)
    
    resposta = requests.post(url, json={
        "chat_id": chat_id,
        "text": mensagem,
        "parse_mode": "HTML"
    }, timeout=10)
    
    if resposta.status_code == 200:
        logging.info(f"📲 Notificação enviada via Telegram para Outbox ID: {id_evento}")
    else:
        raise Exception(f"Falha na API do Telegram: {resposta.text}")
