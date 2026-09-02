import time
import logging
from core.logger_config import configurar_logger
from usecases.processamento_silver import executar_pipeline_silver
from usecases.processamento_outbox import executar_consumidores_outbox

# Inicializa o logger centralizado
configurar_logger()

if __name__ == "__main__":
    logging.info("⚙️ Worker de Processamento Silver e Outbox iniciado com sucesso. Aguardando tarefas...")
    
    while True:
        try:
            # 1. Processa mídias novas da Bronze para a Silver
            executar_pipeline_silver()
            
            # 2. Consome eventos finalizados (Outbox) e envia para o Telegram
            executar_consumidores_outbox()
            
        except Exception as e:
            logging.error(f"❌ Erro crítico no loop principal do worker: {e}")
        
        # Descanso: Evita que o script consuma 100% da CPU do servidor
        time.sleep(15)
