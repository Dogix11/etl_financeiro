import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

from usecases.ingestao import processar_ingestao_bronze

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

# --- Configuração de Permissões e Acesso ---
ID_DIOGO = int(os.getenv("TELEGRAM_ID_DIOGO", 0))
ID_FLORA = int(os.getenv("TELEGRAM_ID_FLORA", 0))

USUARIOS_AUTORIZADOS = {
    ID_DIOGO: {"nome": "Diogo", "permissoes": ["/start", "/gasto", "/nota", "/fatura"]},
    ID_FLORA: {"nome": "Flora", "permissoes": ["/start", "/gasto", "/nota"]}
}

def obter_autorizacao(update: Update, comando_necessario: str):
    """Verifica se o ID do Telegram tem acesso ao bot e permissão para o comando."""
    id_user = update.message.from_user.id
    if id_user not in USUARIOS_AUTORIZADOS:
        logging.warning(f"⚠️ Acesso negado. Tentativa de ID desconhecido: {id_user}")
        return False, None
    
    usuario = USUARIOS_AUTORIZADOS[id_user]
    if comando_necessario not in usuario["permissoes"]:
        logging.warning(f"⚠️ {usuario['nome']} tentou usar {comando_necessario} sem permissão.")
        return False, usuario["nome"]
        
    return True, usuario["nome"]

# --- Configuração de Diretórios ---
BASE_NOTAS = "/volumes/notas_fiscais"
BASE_FATURAS = "/volumes/faturas"

for subpasta in ['pendentes', 'processadas', 'erros']:
    os.makedirs(os.path.join(BASE_NOTAS, subpasta), exist_ok=True)
    os.makedirs(os.path.join(BASE_FATURAS, subpasta), exist_ok=True)

PASTA_NOTAS_PENDENTES = os.path.join(BASE_NOTAS, 'pendentes')
PASTA_FATURAS_PENDENTES = os.path.join(BASE_FATURAS, 'pendentes')
AGUARDANDO_PDF = 1

# --- Handlers do Bot ---

async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    autorizado, nome = obter_autorizacao(update, "/start")
    if not autorizado: return
    await update.message.reply_text(f"🤖 Bot Financeiro Ativo, {nome}!\n/nota (legenda na foto)\n/fatura (inicia fluxo PDF)\n/gasto [texto]")

async def comando_gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    autorizado, nome = obter_autorizacao(update, "/gasto")
    if not autorizado:
        if nome: await update.message.reply_text(f"⚠️ {nome}, você não tem permissão para este comando.")
        return

    texto_bruto = " ".join(context.args) if context.args else update.message.text.replace("/gasto", "").strip()
    if not texto_bruto:
        await update.message.reply_text("⚠️ Informe o gasto.")
        return

    # Enviamos o nome_remetente para a camada de ingestão!
    sucesso, mensagem = processar_ingestao_bronze(
        tipo_midia="texto", 
        comando="/gasto", 
        conteudo_texto=texto_bruto,
        nome_remetente=nome
    )
    await update.message.reply_text(mensagem)

async def comando_nota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    autorizado, nome = obter_autorizacao(update, "/nota")
    if not autorizado:
        if nome: await update.message.reply_text(f"⚠️ {nome}, você não tem permissão para este comando.")
        return

    if not update.message.photo: return

    # Extrai o texto da legenda caso você digite regras (ex: "dividir o milka")
    texto_legenda = ""
    if update.message.caption:
        texto_legenda = update.message.caption.replace("/nota", "").strip()

    foto_id = update.message.photo[-1].file_id
    arquivo = await context.bot.get_file(foto_id)
    caminho_local = os.path.join(PASTA_NOTAS_PENDENTES, f"nota_{foto_id}.jpg")
    await arquivo.download_to_drive(caminho_local)

    # Enviamos a legenda e o nome_remetente para a ingestão!
    sucesso, mensagem = processar_ingestao_bronze(
        tipo_midia="imagem", 
        comando="/nota", 
        caminho_arquivo=caminho_local,
        conteudo_texto=texto_legenda, 
        nome_remetente=nome
    )
    await update.message.reply_text(mensagem)

async def iniciar_comando_fatura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    autorizado, nome = obter_autorizacao(update, "/fatura")
    if not autorizado:
        if nome: await update.message.reply_text(f"⚠️ {nome}, você não tem permissão para usar o comando /fatura.")
        return ConversationHandler.END # Encerra o fluxo para quem não tem permissão

    await update.message.reply_text("📄 Envie o arquivo PDF da fatura agora.")
    return AGUARDANDO_PDF

async def receber_pdf_fatura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Recupera o nome de forma segura, já que a autorização foi feita no passo anterior
    id_remetente = update.message.from_user.id
    nome = USUARIOS_AUTORIZADOS.get(id_remetente, {}).get("nome", "Desconhecido")

    if not update.message.document or not update.message.document.file_name.lower().endswith('.pdf'):
        await update.message.reply_text("⚠️ Envie um PDF ou digite /cancelar.")
        return AGUARDANDO_PDF

    doc_id = update.message.document.file_id
    arquivo = await context.bot.get_file(doc_id)
    caminho_local = os.path.join(PASTA_FATURAS_PENDENTES, f"fatura_{doc_id}.pdf")
    await arquivo.download_to_drive(caminho_local)

    sucesso, mensagem = processar_ingestao_bronze(
        tipo_midia="pdf", 
        comando="/fatura", 
        caminho_arquivo=caminho_local,
        nome_remetente=nome
    )
    await update.message.reply_text(mensagem)
    return ConversationHandler.END

async def cancelar_fatura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Fluxo de fatura cancelado.")
    return ConversationHandler.END

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", iniciar))
    app.add_handler(CommandHandler("gasto", comando_gasto))
    app.add_handler(CommandHandler("nota", comando_nota))
    app.add_handler(MessageHandler(filters.CaptionRegex(r'(?i)^/nota'), comando_nota))

    fatura_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('fatura', iniciar_comando_fatura)],
        states={AGUARDANDO_PDF: [MessageHandler(filters.Document.PDF, receber_pdf_fatura)]},
        fallbacks=[CommandHandler('cancelar', cancelar_fatura)]
    )
    app.add_handler(fatura_conv_handler)
    
    print("🤖 Bot rodando com portaria ativa!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
