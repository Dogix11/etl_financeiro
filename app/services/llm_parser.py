import os
import json
import logging
import mimetypes
import time
import uuid
from datetime import datetime
from google import genai
from google.genai import types
from pypdf import PdfReader, PdfWriter

MODELO_LLM = "gemini-2.5-pro"

def _obter_data_atual():
    return datetime.now().strftime("%Y-%m-%d")

def _construir_prompt(comando_telegram, nome_remetente):
    data_hoje = _obter_data_atual()

    instrucoes_base = f"""
    Você é um extrator de dados financeiros. Hoje é {data_hoje}.
    O usuário que enviou esta mensagem é: {nome_remetente}.
    Sua única saída deve ser um JSON válido, sem formatação markdown (```json).

    Regras de Rateio (Aplicadas ITEM A ITEM):
    1. REGRA PADRÃO: Se o texto do usuário não mencionar divisões, 100% do valor de CADA item pertence a {nome_remetente}. O outro parceiro recebe 0%.
    2. EXCEÇÃO: O usuário pode instruir no texto divisões específicas (ex: "dividir a manteiga", "o milka é da flora").
    3. Aplique as exceções APENAS aos itens mencionados. Os demais itens continuam na Regra Padrão.
    """

    if comando_telegram == "/gasto":
        return instrucoes_base + """
        O texto fornecido pode conter UM ou MÚLTIPLOS produtos/gastos.
        Identifique e separe CADA PRODUTO individualmente.
        Retorne SEMPRE uma lista JSON. Se houver apenas um gasto, retorne uma lista contendo apenas um objeto. Se houver vários, retorne um objeto para cada um.
        Se o usuário não fornecer a data e o horário, utilize o momento atual da extração no formato YYYY-MM-DD HH:MM:SS.
        Mantenha EXATAMENTE esta estrutura de chaves:
        [
            {
                "tipo_registro": "gasto_avulso",
                "data_transacao": "YYYY-MM-DD HH:MM:SS",
                "valor": 0.00,
                "tipo_movimentacao": "despesa|receita",
                "direcao": "OUT|IN",
                "contraparte": "Nome do local ou pessoa",
                "categoria": "Categoria inferida",
                "descricao": "Descrição original do item",
                "titular_pagamento": "seu nome ou da conta",
                "centro_custo": "geral",
                "percentual_diogo": 100.0,
                "percentual_flora": 0.0,
                "valor_cota_diogo": 0.00,
                "valor_cota_flora": 0.00
            }
        ]
        """

    elif comando_telegram == "/nota":
        return instrucoes_base + """
        Analise a imagem da nota fiscal anexa e substitua os valores do JSON abaixo pelos DADOS REAIS extraídos.
        Se uma informação não for encontrada, retorne null.

        Atenção aos Itens: O campo 'quantidade_cupom' refere-se ao multiplicador exato impresso na nota (ex: 1 UN).
        No entanto, leia atentamente o 'nome_produto'. Se a descrição contiver volumes, pesos ou pacotes (ex: '200G', '1KG', '500ML', 'C/25'), extraia esse valor numérico para 'quantidade_embutida' e a unidade para 'unidade_medida_embutida' (G, KG, ML, L, UN). Caso não haja, retorne null em ambos.
        Atenção: Procure o horário exato impresso na nota fiscal para preencher a data_emissao de forma completa.

        Mantenha EXATAMENTE esta estrutura de chaves:
        {
            "tipo_registro": "nota_fiscal",
            "chave_acesso": "Somente números",
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
            "itens": [
                {
                    "nome_produto": "Nome do produto real da nota",
                    "quantidade_cupom": 1.000,
                    "unidade_medida_cupom": "UN|KG",
                    "quantidade_embutida": 200.00,
                    "unidade_medida_embutida": "G|KG|ML|L|UN",
                    "preco_unitario": 0.00,
                    "preco_total_item": 0.00,
                    "preco_total_liquido": 0.00,
                    "categoria_produto": "Subcategoria",
                    "percentual_diogo": 100.0,
                    "percentual_flora": 0.0,
                    "valor_cota_diogo": 0.00,
                    "valor_cota_flora": 0.00
                }
            ]
        }
        """

    elif comando_telegram == "/fatura":
        return instrucoes_base + """
        Analise o PDF da fatura anexa e extraia os dados gerais e TODAS as transações individuais listadas.
        Se uma informação não for encontrada, retorne null.
        Para as transações, observe o cabeçalho do titular/cartão (ex: DIOGO F CARVALHO - 4998********1275) e atribua-o aos itens abaixo dele.
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
            "titular_cartao": "Nome no cartão principal",
            "transacoes": [
                {
                    "data_transacao": "YYYY-MM-DD",
                    "estabelecimento": "Nome do estabelecimento na fatura (ex: BULLGUER, POINTDALIA)",
                    "valor_brl": 0.00,
                    "identificacao_cartao": "Nome e/ou final do cartão (ex: DIOGO F CARVALHO - 1275)"
                }
            ]
        }
        """
    return None

def _desbloquear_pdf(caminho_arquivo):
    senhas_env = os.getenv("SENHA_FATURA", "")
    senhas = [s.strip() for s in senhas_env.split(",")] if senhas_env else []

    try:
        reader = PdfReader(caminho_arquivo)
        if not reader.is_encrypted:
            return caminho_arquivo, False

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

def extrair_dados_financeiros(tipo_midia, conteudo_texto, caminho_arquivo, comando_telegram, nome_remetente="Desconhecido"):
    prompt = _construir_prompt(comando_telegram, nome_remetente)
    if not prompt:
        logging.error(f"Comando não suportado pelo LLM: {comando_telegram}")
        return None, None

    client = genai.Client(
        vertexai=True,
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        location="us-central1"
    )

    conteudos_envio = [prompt]
    caminho_upload = caminho_arquivo
    arquivo_temp_criado = False

    try:
        if caminho_arquivo and os.path.exists(caminho_arquivo):
            if comando_telegram == "/fatura" and caminho_arquivo.lower().endswith(".pdf"):
                caminho_upload, arquivo_temp_criado = _desbloquear_pdf(caminho_arquivo)

            mime_type, _ = mimetypes.guess_type(caminho_upload)
            if not mime_type:
                mime_type = "application/pdf" if caminho_upload.lower().endswith(".pdf") else "image/jpeg"

            with open(caminho_upload, "rb") as f:
                file_bytes = f.read()

            conteudos_envio.append(
                types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
            )

        if conteudo_texto:
            conteudos_envio.append(f"Texto do usuário: {conteudo_texto}")

        # Início do rastreamento de performance
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()

        resposta = client.models.generate_content(
            model=MODELO_LLM,
            contents=conteudos_envio,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        # Fim do rastreamento de performance
        latency = time.perf_counter() - start_time

        # Extração segura dos metadados (prevenindo quebras se a API omitir algo)
        try:
            prompt_tokens = resposta.usage_metadata.prompt_token_count
            output_tokens = resposta.usage_metadata.candidates_token_count
        except AttributeError:
            prompt_tokens = 0
            output_tokens = 0

        try:
            # Algumas versões da API retornam Enum, outras string. Tratamos para string.
            finish_reason = str(resposta.candidates[0].finish_reason.name) if resposta.candidates else "UNKNOWN"
        except AttributeError:
            finish_reason = str(resposta.candidates[0].finish_reason) if resposta.candidates else "UNKNOWN"

        log_requisicao = {
            "request_id": request_id,
            "modelo": MODELO_LLM,
            "latency_seconds": round(latency, 2),
            "prompt_tokens": prompt_tokens,
            "output_tokens": output_tokens,
            "finish_reason": finish_reason
        }

        resultado = json.loads(resposta.text)

        if isinstance(resultado, dict):
            resultado = [resultado]

        return resultado, log_requisicao

    except Exception as e:
        logging.error(f"Falha na extração Vertex AI: {e}")
        raise e
    finally:
        if arquivo_temp_criado and caminho_upload and os.path.exists(caminho_upload):
            os.remove(caminho_upload)
            logging.info("🗑️ Arquivo temporário descriptografado apagado por segurança.")
