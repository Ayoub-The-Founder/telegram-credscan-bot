import os
import re
import tempfile
import zipfile
import shutil
from rarfile import RarFile, BadRarFile
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# === CONFIGURATION ===
BOT_TOKEN = "8252130993:AAECiJ-C5WNEbtI7Z-z4z258ubNQQqQLpvE"
OWNER_ID = 6148342677

temp_passwords = {}
regex_patterns = {
    "cpanels": r"cpanel\.[\w.-]+:[0-9]+|:[0-9]{4,5}.*cpanel",
    "smtps": r"smtp\.[\w.-]+\|\d{2,4}\|[\w@.-]+\|.*",
    "webmails": r"webmail\.[\w.-]+",
    "plesk": r"plesk\.[\w.-]+|:[0-9]{4,5}.*plesk",
    "whms": r"whm\.[\w.-]+|:[0-9]{4,5}.*whm",
    "cms": r"/user/login#[^\s@]+@[^\s@]+"
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    await update.message.reply_text("Bot ready. Send .zip, .rar or .txt file.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    if update.message.text and update.message.text.strip():
        context.user_data['password'] = update.message.text.strip()
        await update.message.reply_text("Password received. Now re-send your archive.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    file = update.message.document
    file_ext = file.file_name.lower()
    if not (file_ext.endswith(".zip") or file_ext.endswith(".rar") or file_ext.endswith(".txt")):
        await update.message.reply_text("Unsupported file type.")
        return

    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, file.file_name)
    new_file = await file.get_file()
    await new_file.download_to_drive(file_path)

    password = context.user_data.get('password')
    extract_dir = os.path.join(tmp_dir, "extracted")
    os.makedirs(extract_dir, exist_ok=True)

    found = {key: [] for key in regex_patterns.keys()}

    try:
        if file_ext.endswith(".zip"):
            with zipfile.ZipFile(file_path) as zipf:
                if password:
                    zipf.setpassword(password.encode())
                zipf.extractall(path=extract_dir)
        elif file_ext.endswith(".rar"):
            with RarFile(file_path) as rarf:
                if password:
                    rarf.extractall(path=extract_dir, pwd=password)
                else:
                    rarf.extractall(path=extract_dir)
        elif file_ext.endswith(".txt"):
            shutil.copy(file_path, os.path.join(extract_dir, file.file_name))

        for root, _, files in os.walk(extract_dir):
            for name in files:
                if name.endswith(".txt"):
                    with open(os.path.join(root, name), errors="ignore") as f:
                        content = f.read()
                        for key, pattern in regex_patterns.items():
                            matches = re.findall(pattern, content)
                            found[key].extend(matches)

        for key, lines in found.items():
            if lines:
                result_path = os.path.join(tmp_dir, f"{key}.txt")
                with open(result_path, "w") as f:
                    f.write("\n".join(set(lines)))
                await update.message.reply_document(InputFile(result_path))

        if not any(found.values()):
            await update.message.reply_text("No credentials found.")

    except (RuntimeError, zipfile.BadZipFile, BadRarFile) as e:
        await update.message.reply_text(f"Error processing archive: {str(e)}")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        context.user_data['password'] = None

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
