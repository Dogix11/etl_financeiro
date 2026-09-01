import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

from usecases.ingestao import processar_ingestao_bronze

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

BASE_NOTAS = "/volumes/notas_fiscais"
BASE_FATURAS = "/volumes/faturas"

for subpasta in ['pendentes', 'processadas', 'erros']:
    os.makedirs(os.path.join(BASE_NOTAS, subpasta), exist_ok=True)
    os.makedirs(os.path.join(BASE_FATURAS, subpasta), exist_ok=True)

PASTA_NOTAS_PENDENTES = os.path.join(BASE_NOTAS, 'pendentes')
PASTA_FATURAS_PENDENTES = os.path.join(BASE_FATURAS, 'pendentes')
AGUARDANDO_PDF = 1

async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot Financeiro Ativo!\n/nota (legenda na foto)\n/fatura (inicia fluxo PDF)\n/gasto [texto]")

async def comando_gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto_bruto = " ".join(context.args) if context.args else update.message.text.replace("/gasto", "").strip()
    if not texto_bruto:
        await update.message.reply_text("⚠️ Informe o gasto.")
        return
    
    sucesso, mensagem = processar_ingestao_bronze(tipo_midia="texto", comando="/gasto", conteudo_texto=texto_bruto)
    await update.message.reply_text(mensagem)

async def comando_nota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo: return
    
    foto_id = update.message.photo[-1].file_id
    arquivo = await context.bot.get_file(foto_id)
    caminho_local = os.path.join(PASTA_NOTAS_PENDENTES, f"nota_{foto_id}.jpg")
    await arquivo.download_to_drive(caminho_local)
    
    sucesso, mensagem = processar_ingestao_bronze(tipo_midia="imagem", comando="/nota", caminho_arquivo=caminho_local)
    await update.message.reply_text(mensagem)

async def iniciar_comando_fatura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📄 Envie o arquivo PDF da fatura agora.")
    return AGUARDANDO_PDF

async def receber_pdf_fatura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document or not update.message.document.file_name.lower().endswith('.pdf'):
        await update.message.reply_text("⚠️ Envie um PDF ou /cancelar.")
        return AGUARDANDO_PDF 

    doc_id = update.message.document.file_id
    arquivo = await context.bot.get_file(doc_id)
    caminho_local = os.path.join(PASTA_FATURAS_PENDENTES, f"fatura_{doc_id}.pdf")
    await arquivo.download_to_drive(caminho_local)
    
    sucesso, mensagem = processar_ingestao_bronze(tipo_midia="pdf", comando="/fatura", caminho_arquivo=caminho_local)
    await update.message.reply_text(mensagem)
    return ConversationHandler.END

async def cancelar_fatura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelado.")
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
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

