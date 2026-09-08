import os
import logging
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}

def _obter_planilha():
    escopos = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    # Agora ele lê do .env ou usa o fallback direto para a pasta montada pelo Docker
    caminho_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/secrets/google_credentials.json")
    credenciais = Credentials.from_service_account_file(caminho_creds, scopes=escopos)
    
    cliente = gspread.authorize(credenciais)
    planilha_id = os.getenv("SPREADSHEET_ID")
    return cliente.open_by_key(planilha_id)

def _garantir_aba_do_mes(planilha, data_obj):
    nome_mes = MESES_PT[data_obj.month]
    ano = data_obj.year
    nome_aba = f"Gastos Conjuntos {nome_mes} {ano}"

    try:
        aba = planilha.worksheet(nome_aba)
    except gspread.exceptions.WorksheetNotFound:
        # Garante colunas suficientes para conter até a coluna J (10 colunas)
        aba = planilha.add_worksheet(title=nome_aba, rows="1000", cols="10")
        
        # 1. Inserção dos cabeçalhos principais na linha 1
        cabecalhos = [
            "data", "descricao_do_gasto", 
            "valor_do_gasto_diogo", "booleano_confirmacao_diogo", 
            "valor_do_gasto_flora", "booleano_confirmacao_flora", "pagar"
        ]
        aba.append_row(cabecalhos)
        
        # 2. Inserção das fórmulas EXATAS com ponto e vírgula
        # 2. Inserção das fórmulas e rótulos estruturados nas colunas I e J
        formulas_lote = [
            # Coluna I: Rótulos nas linhas 1, 2 e 3
            {"range": "I1", "values": [[ "Total Diogo" ]]},
            {"range": "I2", "values": [[ "Total Flora" ]]},
            {"range": "I3", "values": [[ '=IF(J1>J2; "Flora deve : "; "Diogo deve: ")' ]]},
            
            # Coluna J: Fórmulas nas linhas 1, 2 e 3
            {"range": "J1", "values": [["=SUMPRODUCT(C:C;D:D;G:G)"]]},
            {"range": "J2", "values": [["=SUMPRODUCT(E:E;F:F;G:G)"]]},
            {"range": "J3", "values": [[ "=IF(J1>J2; J1-J2; J2-J1)" ]]}
        ]
        
        aba.batch_update(formulas_lote, value_input_option='USER_ENTERED')
        logging.info(f"✨ Nova aba criada e estruturada no Sheets com fórmulas: {nome_aba}")
        
        # O parâmetro USER_ENTERED é OBRIGATÓRIO aqui para aceitar o ponto e vírgula regional
        aba.batch_update(formulas_lote, value_input_option='USER_ENTERED')
        logging.info(f"✨ Nova aba criada e estruturada no Sheets com fórmulas: {nome_aba}")

    return aba

def exportar_registro_sheets(dados_movimentacao):
    logging.info(f"📊 Payload recebido para exportação no Sheets: {dados_movimentacao}")
    
    try:
        data_str = dados_movimentacao.get("data_transacao")
        data_obj = datetime.strptime(data_str, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        data_obj = datetime.now()

    valor = float(dados_movimentacao.get("valor", 0))
    titular = str(dados_movimentacao.get("titular_pagamento", "")).lower()
    descricao = dados_movimentacao.get("descricao") or dados_movimentacao.get("contraparte", "")

    perc_diogo = float(dados_movimentacao.get("percentual_seu", 100)) / 100
    perc_flora = float(dados_movimentacao.get("percentual_esposa", 0)) / 100

    # Lógica de titularidade e booleano de confirmação
    if "flora" in titular:
        v_diogo, bool_diogo = "", 0
        v_flora, bool_flora = valor, 1
        pagar = perc_diogo
    else:
        v_diogo, bool_diogo = valor, 1
        v_flora, bool_flora = "", 0
        pagar = perc_flora

    # Array exato correspondente às colunas A, B, C, D, E, F, G
    linha = [
        data_obj.strftime("%d/%m/%Y"), # Coluna A
        descricao,                    # Coluna B
        v_diogo,                      # Coluna C
        bool_diogo,                   # Coluna D
        v_flora,                      # Coluna E
        bool_flora,                   # Coluna F
        pagar                         # Coluna G
    ]

    try:
        planilha = _obter_planilha()
        aba = _garantir_aba_do_mes(planilha, data_obj)
        
        # Força o append a começar estritamente a partir da coluna A (tabela principal)
        # Usamos table_range para ancorar o append no bloco inicial
        aba.append_row(linha, value_input_option='USER_ENTERED', table_range='A1:G1000')
        
        logging.info(f"✅ Linha inserida corretamente na tabela principal de A-G na aba '{aba.title}': {linha}")
    except Exception as e:
        logging.error(f"❌ ERRO CRÍTICO ao escrever no Google Sheets: {e}", exc_info=True)
        raise e
