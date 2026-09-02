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
    # O arquivo deve estar na raiz do projeto (mesmo nível do docker-compose)
    caminho_creds = os.path.join(os.getcwd(), "google_credentials.json")
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
        aba = planilha.add_worksheet(title=nome_aba, rows="1000", cols="10")
        cabecalhos = [
            "data", "descricao_do_gasto", 
            "valor_do_gasto_diogo", "booleano_confirmacao_diogo", 
            "valor_do_gasto_flora", "booleano_confirmacao_flora", "pagar"
        ]
        aba.append_row(cabecalhos)
        logging.info(f"Nova aba criada no Sheets: {nome_aba}")
        
    return aba

def exportar_registro_sheets(dados_movimentacao):
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

    linha = [
        data_obj.strftime("%d/%m/%Y"),
        descricao,
        v_diogo,
        bool_diogo,
        v_flora,
        bool_flora,
        pagar
    ]
    
    planilha = _obter_planilha()
    aba = _garantir_aba_do_mes(planilha, data_obj)
    aba.append_row(linha)
