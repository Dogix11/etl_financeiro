import os
import cv2
import pytesseract
import requests
import json

OLLAMA_API_URL = "http://ollama_server:11434/api/generate"
MODELO_LLM = "qwen2.5:latest"

def preprocessar_imagem(caminho_imagem: str):
    imagem = cv2.imread(caminho_imagem)
    if imagem is None:
        raise ValueError(f"Erro ao carregar a imagem: {caminho_imagem}")

    # 1. Redimensionamento de segurança
    altura, largura = imagem.shape[:2]
    if largura > 1000:
        escala = 1000 / largura
        imagem = cv2.resize(imagem, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)

    # 2. Converte para tons de cinza
    tons_cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)

    # 3. Filtro CLAHE (A Mágica para Sombras e Reflexos)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contraste_melhorado = clahe.apply(tons_cinza)

    # 4. Suavização leve e Binarização Adaptativa
    suavizada = cv2.GaussianBlur(contraste_melhorado, (5, 5), 0)
    binarizada = cv2.adaptiveThreshold(
        suavizada, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 15
    )

    # Salva para inspeção visual
    caminho_debug = caminho_imagem.replace("pendentes", "processadas").replace(".jpg", "_debug.jpg")
    cv2.imwrite(caminho_debug, binarizada)

    return binarizada


def extrair_texto(imagem_tratada) -> str:
    # Retornamos para o PSM 6 ou 4. O 4 é melhor para colunas de cupom.
    config = r'--oem 3 --psm 4 -l por'
    return pytesseract.image_to_string(imagem_tratada, config=config)


def estruturar_dados_qwen(texto_bruto: str) -> dict:
    prompt_sistema = """Você é um sistema especialista em extração de dados fiscais brasileiros.
Você receberá um texto ruidoso extraído via OCR.
Sua tarefa é ignorar o lixo visual, deduzir o contexto e extrair os fatos, corrigindo alucinações numéricas do OCR.

EXEMPLOS DE COMPORTAMENTO ESPERADO:

[Exemplo 1]
Texto OCR:
SUPERVAREJAO SAUDE LTDA.
RUA CARAMURU, 41
Qtd. total de itens 1
Valor total R$ 2.29

Saída JSON:
{
  "estabelecimento": "SUPERVAREJAO SAUDE LTDA",
  "data_emissao": null,
  "valor_total": 2.29
}

[Exemplo 2]
Texto OCR:
LAVANDERIA PRIMAVIRA
28:05:2026 RU
(Ccréito R$ 113, EE
VISA - 241775

Saída JSON:
{
  "estabelecimento": "LAVANDERIA PRIMAVIRA",
  "data_emissao": "2026-05-28",
  "valor_total": 113.00
}

[Exemplo 3]
Texto OCR:
SUPERMERCADO ZONA SUL SA POS7 - ZSPOS7-FIL21
RUA SENADOR VERGUEIRO.45-FLAMENGO - Rio de Janeiro - RJ
VALOR A PAGAR R$ 10.97
Data de Autorizacao: 08/07/2026 18:56:12
VALOR: 10,97

Saída JSON:
{
  "estabelecimento": "SUPERMERCADO ZONA SUL SA",
  "data_emissao": "2026-07-08",
  "valor_total": 10.97
}

AGORA É A SUA VEZ. Analise o texto abaixo e retorne ESTRITAMENTE o JSON no mesmo formato, sem adicionar textos antes ou depois.
"""

    payload = {
        "model": MODELO_LLM,
        "prompt": f"{prompt_sistema}\n\nTexto OCR:\n{texto_bruto}",
        "stream": False,
        "format": "json"
    }
    
    try:
        resposta = requests.post(OLLAMA_API_URL, json=payload, timeout=180)
        resposta.raise_for_status()
        return json.loads(resposta.json().get("response", "{}"))
    except requests.exceptions.RequestException as e:
        detalhe = e.response.text if e.response else str(e)
        return {"erro": f"Falha na comunicação com Ollama: {detalhe}"}
    except json.JSONDecodeError:
        return {"erro": "O modelo não retornou um JSON válido."}


# --- MOTOR DE EXECUÇÃO ---
if __name__ == "__main__":
    pasta_pendentes = "/app/notas_fiscais/pendentes"
    os.makedirs("/app/notas_fiscais/processadas", exist_ok=True)

    arquivos = [f for f in os.listdir(pasta_pendentes) if f.endswith(('.jpg', '.jpeg', '.png'))]

    if not arquivos:
        print("Nenhuma imagem encontrada na pasta pendentes.")
    else:
        for arq in arquivos:
            caminho = os.path.join(pasta_pendentes, arq)
            print(f"\n{'='*20} PROCESSANDO: {arq} {'='*20}")
            
            img_tratada = preprocessar_imagem(caminho)
            texto = extrair_texto(img_tratada)
            
            # ---> DEBUG DO OCR <---
            print("\n--- TEXTO BRUTO EXTRAÍDO PELO TESSERACT ---")
            print(texto if texto.strip() else "[AVISO: Nenhum texto lido pelo OCR]")
            print("-------------------------------------------\n")
            
            dados = estruturar_dados_qwen(texto)
            
            print("--- RESULTADO QWEN ---")
            print(json.dumps(dados, indent=2, ensure_ascii=False))
            print(f"{'='*60}\n")


