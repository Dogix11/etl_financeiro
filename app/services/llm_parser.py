import os
import json
import logging
from datetime import datetime
from google import genai
from google.genai import types

# Usando o modelo 3.5
MODELO_LLM = "gemini-3.5-flash"

def _obter_data_atual():
    # Injetamos a data para o LLM ter referencial temporal em comandos como "gasto de ontem"
    return datetime.now().strftime("%Y-%m-%d")

def _construir_prompt(comando_telegram):
    data_hoje = _obter_data_atual()
    
    instrucoes_base = f"""
    Você é um extrator de dados financeiros. Hoje é {data_hoje}.
    Sua única saída deve ser um JSON válido, sem formatação markdown (```json).
    Regras de Rateio: Se o texto ou nota indicar divisão com parceira (ex: "esposa", "Flora"),
    calcule os campos percentual_seu, percentual_esposa, valor_cota_sua e valor_cota_esposa de acordo com as instruções fornecidas.
    Caso não tenha os percentuais informados a divisão é metade, metade.
    O padrão é percentual_seu = 100.0 e percentual_esposa = 0.0.
    """

    if comando_telegram == "/gasto":
        return instrucoes_base + """
        Extraia as informações do texto e retorne EXATAMENTE este JSON:
        {
            "tipo_registro": "gasto_avulso",
            "data_transacao": "YYYY-MM-DD HH:MM:SS",
            "valor": 0.00,
            "tipo_movimentacao": "despesa|receita",
            "direcao": "OUT|IN",
            "contraparte": "Nome do local ou pessoa",
            "categoria": "Categoria inferida",
            "descricao": "Descrição original",
            "titular_pagamento": "seu nome ou da conta",
            "centro_custo": "geral",
            "percentual_seu": 100.0,
            "percentual_esposa": 0.0,
            "valor_cota_sua": 0.00,
            "valor_cota_esposa": 0.00
        }
        """
    elif comando_telegram == "/nota":
        return instrucoes_base + """
        Analise a imagem da nota fiscal e retorne EXATAMENTE este JSON:
        {
            "tipo_registro": "nota_fiscal",
            "chave_acesso": "Somente números, se houver",
            "cnpj_emissor": "Apenas números",
            "nome_emissor": "Nome do estabelecimento",
            "data_emissao": "YYYY-MM-DD",
            "valor_subtotal": 0.00,
            "valor_desconto": 0.00,
            "valor_acrescimo": 0.00,
            "valor_total": 0.00,
            "categoria": "Categoria geral da compra",
            "forma_pagamento": "PIX, Cartão, Dinheiro, etc",
            "natureza_operacao": "Venda, Serviço, etc",
            "titular_pagamento": "seu nome",
            "centro_custo": "geral",
            "percentual_seu": 100.0,
            "percentual_esposa": 0.0,
            "valor_cota_sua": 0.00,
            "valor_cota_esposa": 0.00,
            "itens": [
                {
                    "nome_produto": "Nome",
                    "quantidade": 1.000,
                    "unidade_medida": "UN|KG",
                    "preco_unitario": 0.00,
                    "preco_total_item": 0.00,
                    "preco_total_liquido": 0.00,
                    "categoria_produto": "Subcategoria"
                }
            ]
        }
        """
    elif comando_telegram == "/fatura":
        return instrucoes_base + """
        Analise o PDF da fatura e retorne EXATAMENTE este JSON:
        {
            "tipo_registro": "fatura",
            "banco": "Nome do Banco",
            "mes_referencia": "MM/YYYY",
            "valor_fatura": 0.00,
            "data_vencimento": "YYYY-MM-DD",
            "data_pagamento": null,
            "status_pagamento": "ABERTO",
            "instituicao_emissora": "Emissora",
            "titular_cartao": "Nome no cartão"
        }
        """
    return None

def extrair_dados_financeiros(tipo_midia, conteudo_texto, caminho_arquivo, comando_telegram):
    prompt = _construir_prompt(comando_telegram)
    if not prompt:
        logging.error(f"Comando não suportado pelo LLM: {comando_telegram}")
        return None

    # Inicialização correta da nova biblioteca
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    arquivo_gemini = None
    conteudos_envio = [prompt]

    try:
        # File API no novo SDK
        if caminho_arquivo and os.path.exists(caminho_arquivo):
            logging.info(f"Fazendo upload para o Gemini: {caminho_arquivo}")
            arquivo_gemini = client.files.upload(file=caminho_arquivo)
            conteudos_envio.append(arquivo_gemini)
        
        if conteudo_texto:
            conteudos_envio.append(f"Texto do usuário: {conteudo_texto}")

        # Configuração estruturada e chamada no novo SDK
        resposta = client.models.generate_content(
            model=MODELO_LLM,
            contents=conteudos_envio,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        if arquivo_gemini:
            client.files.delete(name=arquivo_gemini.name)

        return json.loads(resposta.text)

    except Exception as e:
        logging.error(f"Falha na extração LLM: {e}")
        if arquivo_gemini:
            try:
                client.files.delete(name=arquivo_gemini.name)
            except Exception:
                pass
        return None
