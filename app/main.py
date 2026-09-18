import os
import telebot
from dotenv import load_dotenv

# 1. Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
# Converte o ID para inteiro, pois o Telegram trata IDs como números
ADMIN_ID = int(os.getenv('TELEGRAM_ADMIN_ID')) 

# Inicializa o bot
bot = telebot.TeleBot(TOKEN)

# Cria as pastas caso elas não existam (garantia de estabilidade)
os.makedirs('/app/notas_fiscais/pendentes', exist_ok=True)
os.makedirs('/app/faturas/pendentes', exist_ok=True)

# 2. FUNÇÃO DE SEGURANÇA (O Porteiro)
def is_admin(message):
    """Retorna True apenas se o remetente for você. Ignora o resto do mundo."""
    return message.from_user.id == ADMIN_ID


# 3. ROTINA PARA NOTAS FISCAIS (Fotos)
@bot.message_handler(func=is_admin, content_types=['photo'])
def handle_photo(message):
    try:
        bot.reply_to(message, "📸 Recebi a foto! Baixando e enviando para o datalake de Notas Fiscais...")
        
        # O Telegram envia a foto em vários tamanhos, pega o maior tamanho
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Cria um nome único baseado no ID da mensagem
        file_name = f"nota_fiscal_{message.message_id}.jpg"
        file_path = os.path.join('/app/notas_fiscais/pendentes', file_name)
        
        # Salva o arquivo fisicamente na pasta
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        bot.reply_to(message, f"✅ Salvo com sucesso como `{file_name}` na fila de processamento!")
        
        # Aqui, no futuro, chamaremos a função de OCR e Qwen para processar a nota...

    except Exception as e:
        bot.reply_to(message, f"❌ Erro ao processar a imagem: {e}")


# 4. ROTINA PARA FATURAS (Arquivos PDF)
@bot.message_handler(func=is_admin, content_types=['document'])
def handle_document(message):
    try:
        # Verifica se o arquivo é um PDF
        if message.document.mime_type == 'application/pdf':
            bot.reply_to(message, "📄 Recebi o PDF! Baixando e enviando para o datalake de Faturas...")
            
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            # Cria um nome único usando o nome original do arquivo
            file_name = f"fatura_{message.message_id}_{message.document.file_name}"
            file_path = os.path.join('/app/faturas/pendentes', file_name)
            
            # Salva o arquivo fisicamente na pasta
            with open(file_path, 'wb') as new_file:
                new_file.write(downloaded_file)
                
            bot.reply_to(message, f"✅ PDF salvo com sucesso como `{file_name}` na fila de processamento!")
            
            # Aqui, no futuro, chamaremos a função de conversão para imagem e OCR...
        else:
            bot.reply_to(message, "⚠️ O arquivo enviado não é um PDF. Por favor, envie a fatura em formato PDF.")

    except Exception as e:
        bot.reply_to(message, f"❌ Erro ao processar o documento: {e}")


# 5. INICIA O BOT (Loop infinito)
if __name__ == "__main__":
    print("🤖 Bot iniciado com sucesso! Escutando mensagens...")
    # O infinite_polling garante que o bot continue rodando mesmo se houver falha de rede temporária
    bot.infinity_polling()
