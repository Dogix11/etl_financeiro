import time
import logging
from core.logger_config import configurar_logger
from usecases.processamento_silver import executar_pipeline_silver

configurar_logger()

def iniciar_worker():
    logging.info("⚙️ Worker de Processamento Silver iniciado...")
    while True:
        try:
            executar_pipeline_silver()
        except Exception as e:
            logging.error(f"Erro crítico no loop do worker: {e}")
        
        # Aguarda 30 segundos antes de buscar novos registros
        time.sleep(30)

if __name__ == "__main__":
    iniciar_worker()
