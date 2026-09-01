import os
import glob
import json
from google import genai
from google.genai import types
from PIL import Image

# Inicializa o cliente consumindo automaticamente a GEMINI_API_KEY do .env
client = genai.Client()

def extrair_dados_nota(caminho_imagem: str) -> dict:
    """Envia a imagem da nota fiscal para o Gemini extrair os itens."""
    
    print(f"\n Processando: {os.path.basename(caminho_imagem)}")
    
    try:
        imagem = Image.open(caminho_imagem)
    except Exception as e:
        return {"erro": f"Não foi possível abrir a imagem: {str(e)}"}

    prompt_sistema = """Você é um sistema especialista em extração de cupons fiscais brasileiros.
Sua tarefa é analisar a imagem do cupom fiscal e extrair os dados solicitados.

REGRAS:
- Ignore ruídos, amassados ou textos que não sejam do cupom.
- Converta valores numéricos usando ponto como separador decimal (ex: 10.97).
- Se a quantidade não estiver explícita, assuma 1.0.

Formato JSON esperado ESTRITAMENTE:
{
  "estabelecimento": "Nome Limpo",
  "data_emissao": "YYYY-MM-DD",
  "itens": [
    {"produto": "Nome do item", "quantidade": 0.0, "valor_unitario": 0.0, "valor_total_item": 0.0}
  ],
  "valor_total_nota": 0.00
}"""

    try:
        resposta = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=[imagem, prompt_sistema],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1 # Temperatura baixa para evitar alucinações
            ),
        )
        return json.loads(resposta.text)
        
    except Exception as e:
        return {"erro": f"Falha na API da Google: {str(e)}"}

if __name__ == "__main__":
    # Caminho mapeado dentro do container pelo docker-compose
    pasta_pendentes = "/app/notas_fiscais/pendentes"
    
    # Busca por imagens jpg, jpeg e png
    extensoes = ['*.jpg', '*.jpeg', '*.png']
    arquivos_pendentes = []
    for ext in extensoes:
        arquivos_pendentes.extend(glob.glob(os.path.join(pasta_pendentes, ext)))
    
    if not arquivos_pendentes:
        print(f"Nenhuma imagem encontrada na pasta: {pasta_pendentes}")
    else:
        print(f"🚀 Iniciando extração de {len(arquivos_pendentes)} nota(s) fiscal(is)...\n")
        
        for arquivo in arquivos_pendentes:
            dados_estruturados = extrair_dados_nota(arquivo)
            print("=== RESULTADO DA EXTRAÇÃO ===")
            print(json.dumps(dados_estruturados, indent=2, ensure_ascii=False))
            print("=============================\n")
