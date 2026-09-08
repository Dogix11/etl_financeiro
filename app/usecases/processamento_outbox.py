import logging
from infrastructure.dao_financeiro import buscar_pendentes_outbox, atualizar_status_outbox
from usecases.exportacao_sheets import exportar_registro_sheets
from delivery.telegram_notifier import disparar_mensagem_telegram

def executar_consumidores_outbox():
    eventos = buscar_pendentes_outbox()
    if not eventos:
        return

    for evento in eventos:
        id_evento, tipo_evento, payload = evento
        
        try:
            # 1. Integração com o Google Sheets (Apenas para movimentações e notas financeiras)
            if tipo_evento in ['NOVA_MOVIMENTACAO']:
                exportar_registro_sheets(payload)
                logging.info(f"📊 Dados exportados para o Sheets (Evento: {id_evento})")
            
            # 2. Integração com o Telegram (Para todos os eventos)
            disparar_mensagem_telegram(id_evento, tipo_evento, payload)
            
            # 3. Sucesso em todos os sistemas externos: Marca como concluído
            atualizar_status_outbox(id_evento, 'PROCESSADO')
            
        except Exception as e:
            # Se o Google ou o Telegram falharem, o status continua PENDENTE 
            # e o worker tentará novamente no próximo ciclo, garantindo zero perda de dados.
            logging.error(f"❌ Erro ao processar evento Outbox ID {id_evento}: {e}")
