import os
import logging

def configurar_logger():
    pasta_logs = "/volumes/logs"
    os.makedirs(pasta_logs, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(pasta_logs, "etl_financeiro.log")),
            logging.StreamHandler()
        ],
        force=True # Garante que as configurações sobrescrevam qualquer log base do Python
    )
