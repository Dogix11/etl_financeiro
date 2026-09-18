import os
import requests
import logging

def _formatar_mensagem(id_evento, tipo_evento, payload):
    # Garante que o payload é um dicionário, mesmo se vier nulo do banco
    payload = payload or {}

    if tipo_evento == 'NOVA_NOTA_FISCAL':
        return (
            f"🛒 <b>Nota Fiscal Processada</b>\n"
            f"Registro ID: {payload.get('id_nota', 'N/A')}\n"
            f"<i>Itens extraídos e espelhados no Livro-Razão com sucesso.</i>"
        )
    elif tipo_evento == 'NOVA_MOVIMENTACAO':
        # Calcula as cotas baseado no percentual para exibir na notificação
        valor = float(payload.get('valor', 0))
        perc_flora = float(payload.get('percentual_flora', 0))
        cota_flora = valor * (perc_flora / 100)
        cota_diogo = valor - cota_flora
        
        return (
            f"💸 <b>Gasto / Movimentação</b>\n"
            f"Produto: {payload.get('descricao', 'N/A')}\n"
            f"Valor Total: R$ {valor:.2f}\n"
            f"Cota Diogo: R$ {cota_diogo:.2f}\n"
            f"Cota Flora: R$ {cota_flora:.2f}"
        )
    elif tipo_evento == 'NOVA_FATURA':
        return (
            f"💳 <b>Fatura Processada</b>\n"
            f"Registro ID: {payload.get('id_fatura', 'N/A')}\n"
            f"<i>Transações filhas extraídas com sucesso.</i>"
        )

    return f"✅ <b>Evento Processado:</b> {tipo_evento}\nProtocolo: <code>{id_evento}</code>"

def disparar_mensagem_telegram(id_evento, tipo_evento, payload):
    """Envia uma única mensagem formatada para a API do Telegram."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    # Busca o TELEGRAM_ADMIN_ID, se não achar, usa o seu TELEGRAM_ID_DIOGO como fallback
    chat_id = os.getenv("TELEGRAM_ADMIN_ID") or os.getenv("TELEGRAM_ID_DIOGO")

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
