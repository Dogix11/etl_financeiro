import os
import json
import logging
from datetime import datetime
from google import genai
from google.genai import types
from pypdf import PdfReader, PdfWriter

MODELO_LLM = "gemini-3.5-flash"

def _obter_data_atual():
    return datetime.now().strftime("%Y-%m-%d")

def _construir_prompt(comando_telegram):
    data_hoje = _obter_data_atual()
    
    instrucoes_base = f"""
    Você é um extrator de dados financeiros. Hoje é {data_hoje}.
    Sua única saída deve ser um JSON válido, sem formatação markdown (```json).
    Regras de Rateio: Se o texto ou nota indicar divisão com parceira (ex: "esposa", "Flora"), 
    calcule os campos percentual_seu, percentual_esposa, valor_cota_sua e valor_cota_esposa.
    O padrão é percentual_seu = 100.0 e percentual_esposa = 0.0.
    """

    if comando_telegram == "/gasto":
        return instrucoes_base + """
        Extraia as informações do texto fornecido e substitua os valores do JSON abaixo pelos DADOS REAIS.
        Se uma informação não for encontrada, retorne null.
        Mantenha EXATAMENTE esta estrutura de chaves:
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
        Analise a imagem da nota fiscal anexa e substitua os valores do JSON abaixo pelos DADOS REAIS extraídos da imagem.
        Se uma informação não for encontrada na nota, retorne null.
        Mantenha EXATAMENTE esta estrutura de chaves:
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
                    "nome_produto": "Nome do produto real da nota",
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
        Analise o PDF da fatura anexa e substitua os valores do JSON abaixo pelos DADOS REAIS extraídos.
        Se uma informação não for encontrada, retorne null.
        Mantenha EXATAMENTE esta estrutura de chaves:
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

def _desbloquear_pdf(caminho_arquivo):
    """Tenta desbloquear o PDF com as senhas configuradas e retorna um arquivo temporário."""
    senhas_env = os.getenv("SENHA_FATURA", "")
    senhas = [s.strip() for s in senhas_env.split(",")] if senhas_env else []
    
    try:
        reader = PdfReader(caminho_arquivo)
        if not reader.is_encrypted:
            return caminho_arquivo, False # Não estava bloqueado
            
        for senha in senhas:
            if reader.decrypt(senha) != 0:
                writer = PdfWriter()
                for page in reader.pages:
                    writer.add_page(page)
                
                caminho_temp = caminho_arquivo.replace(".pdf", "_temp_desbloqueado.pdf")
                with open(caminho_temp, "wb") as f:
                    writer.write(f)
                
                logging.info(f"🔓 PDF desbloqueado com sucesso.")
                return caminho_temp, True
                
        logging.error("Nenhuma das senhas fornecidas conseguiu desbloquear a fatura.")
        raise ValueError("Falha de descriptografia: Senha incorreta ou ausente no .env.")
        
    except Exception as e:
        logging.error(f"Erro ao tentar ler o PDF: {e}")
        raise e

def extrair_dados_financeiros(tipo_midia, conteudo_texto, caminho_arquivo, comando_telegram):
    prompt = _construir_prompt(comando_telegram)
    if not prompt:
        logging.error(f"Comando não suportado pelo LLM: {comando_telegram}")
        return None

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    arquivo_gemini = None
    conteudos_envio = [prompt]
    
    caminho_upload = caminho_arquivo
    arquivo_temp_criado = False

    try:
        if caminho_arquivo and os.path.exists(caminho_arquivo):
            if comando_telegram == "/fatura" and caminho_arquivo.lower().endswith(".pdf"):
                caminho_upload, arquivo_temp_criado = _desbloquear_pdf(caminho_arquivo)

            logging.info(f"Fazendo upload para o Gemini: {caminho_upload}")
            arquivo_gemini = client.files.upload(file=caminho_upload)
            conteudos_envio.append(arquivo_gemini)
        
        if conteudo_texto:
            conteudos_envio.append(f"Texto do usuário: {conteudo_texto}")

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
        raise e
    finally:
        # Garante que o PDF temporário sem senha será deletado do seu disco, 
        # independentemente de a API do Gemini ter falhado ou não
        if arquivo_temp_criado and caminho_upload and os.path.exists(caminho_upload):
            os.remove(caminho_upload)
            logging.info("🗑️ Arquivo temporário descriptografado apagado por segurança.")
