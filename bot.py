# import os
# import json
# import time
# from datetime import datetime
# from telegram import Update
# from telegram.ext import (
#     ApplicationBuilder, CommandHandler, MessageHandler,
#     ContextTypes, filters
# )
# import threading
# from http.server import HTTPServer, BaseHTTPRequestHandler

# # ── Storage ──────────────────────────────────────────────────────────────────
# DATA_FILE = "data.json"

# def load():
#     if not os.path.exists(DATA_FILE):
#         return {}
#     with open(DATA_FILE) as f:
#         return json.load(f)

# def save(data):
#     with open(DATA_FILE, "w") as f:
#         json.dump(data, f, indent=2)

# def get_user(data, user_id):
#     uid = str(user_id)
#     if uid not in data:
#         data[uid] = {"name": None, "partner_id": None, "transactions": [], "message_map": {}}
#     return data[uid]

# # ── Helpers ───────────────────────────────────────────────────────────────────
# def balance_summary(data, user_id):
#     uid = str(user_id)
#     user = get_user(data, uid)
#     partner_id = user["partner_id"]
#     if not partner_id:
#         return None, None
#     partner = get_user(data, partner_id)

#     total = 0.0
#     for t in data.get("transactions", []):
#         if t["payer"] == uid:
#             total += t["amount"]
#         elif t["payer"] == partner_id:
#             total -= t["amount"]

#     user_name = user["name"] or "You"
#     partner_name = partner["name"] or "Your partner"

#     if total > 0:
#         return total, f"💰 {partner_name} owes {user_name} {total:.0f} birr"
#     elif total < 0:
#         return total, f"💰 {user_name} owes {partner_name} {abs(total):.0f} birr"
#     else:
#         return 0, "✅ You're all settled up!"

# async def notify_partner(context, partner_id, message):
#     try:
#         await context.bot.send_message(chat_id=int(partner_id), text=message)
#     except Exception:
#         pass

# # ── /start ────────────────────────────────────────────────────────────────────
# async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     data = load()
#     uid = str(update.effective_user.id)
#     user = get_user(data, uid)
#     user["name"] = update.effective_user.first_name
#     user["username"] = (update.effective_user.username or "").lower()
#     save(data)

#     await update.message.reply_text(
#         f"👋 Hey {update.effective_user.first_name}!\n\n"
#         "I track shared expenses between you and a friend.\n\n"
#         "To get started, link with your partner:\n"
#         "👉 Send their Telegram username like this:\n"
#         "/link @username"
#     )

# # ── /link ─────────────────────────────────────────────────────────────────────
# async def link(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     data = load()
#     uid = str(update.effective_user.id)
#     user = get_user(data, uid)

#     if not context.args:
#         await update.message.reply_text("Usage: /link @username")
#         return

#     username = context.args[0].lstrip("@").lower()

#     # find partner by telegram username
#     partner_id = None
#     for pid, pdata in data.items():
#         if pid == uid:
#             continue
#         if not isinstance(pdata, dict):
#             continue
#         stored_username = pdata.get("username", "").lower()
#         if stored_username == username:
#             partner_id = pid
#             break

#     if not partner_id:
#         await update.message.reply_text(
#             f"❌ Couldn't find @{username}.\n\n"
#             "Make sure they have started the bot first by sending /start to me.\n"
#             "Then try linking again."
#         )
#         return

#     user["partner_id"] = partner_id
#     partner = get_user(data, partner_id)
#     partner["partner_id"] = uid
#     save(data)

#     partner_name = partner.get("name") or username
#     await update.message.reply_text(f"✅ Linked with {partner_name}! You're all set.\n\nTry: /paid 500 lunch")
#     await notify_partner(context, partner_id,
#         f"✅ {user['name']} linked with you! You're connected and ready to track expenses.")

# # ── /paid ─────────────────────────────────────────────────────────────────────
# async def paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     data = load()
#     uid = str(update.effective_user.id)
#     user = get_user(data, uid)

#     if not user["partner_id"]:
#         await update.message.reply_text("⚠️ You haven't linked with a partner yet.\nUse /link @username first.")
#         return

#     if len(context.args) < 1:
#         await update.message.reply_text("Usage: /paid 500 lunch")
#         return

#     try:
#         amount = float(context.args[0])
#     except ValueError:
#         await update.message.reply_text("❌ Amount must be a number. Example: /paid 500 lunch")
#         return

#     description = " ".join(context.args[1:]) if len(context.args) > 1 else "no description"
#     now = time.time()

#     # ── duplicate check ───────────────────────────────────────────────────────
#     if "transactions" not in data:
#         data["transactions"] = []

#     recent = [
#         t for t in data["transactions"]
#         if t["amount"] == amount and now - t["timestamp"] < 600
#         and (t["payer"] == uid or t["payer"] == user["partner_id"])
#     ]

#     if recent:
#         r = recent[-1]
#         payer_name = user["name"] if r["payer"] == uid else get_user(data, user["partner_id"])["name"]
#         dt = datetime.fromtimestamp(r["timestamp"]).strftime("%H:%M")
#         # store pending
#         if "pending" not in data:
#             data["pending"] = {}
#         data["pending"][uid] = {"amount": amount, "description": description, "timestamp": now}
#         save(data)
#         await update.message.reply_text(
#             f"⚠️ Heads up! A similar transaction was recorded recently:\n"
#             f"👉 {payer_name} paid {r['amount']:.0f} birr for {r['description']} at {dt}\n\n"
#             f"Is this a duplicate?\n"
#             f"✅ /confirm — save it anyway\n"
#             f"❌ /cancel — don't save"
#         )
#         return

#     _save_transaction(data, uid, user, amount, description, now, update.message.message_id)
#     save(data)

#     _, bal = balance_summary(data, uid)
#     partner_name = get_user(data, user["partner_id"])["name"] or "Your partner"
#     msg = (
#         f"✅ {user['name']} paid {amount:.0f} birr for {description}\n"
#         f"🕐 {datetime.fromtimestamp(now).strftime('%H:%M')}\n"
#         f"{bal}"
#     )
#     await update.message.reply_text(msg)
#     await notify_partner(context, user["partner_id"], f"👀 New transaction logged!\n{msg}")

# def _save_transaction(data, uid, user, amount, description, timestamp, message_id):
#     if "transactions" not in data:
#         data["transactions"] = []
#     txn = {
#         "id": len(data["transactions"]) + 1,
#         "payer": uid,
#         "amount": amount,
#         "description": description,
#         "timestamp": timestamp,
#         "message_id": message_id,
#         "edits": []
#     }
#     data["transactions"].append(txn)
#     # map message_id → transaction id for edit detection
#     if "message_map" not in data:
#         data["message_map"] = {}
#     data["message_map"][str(message_id)] = txn["id"]

# # ── /confirm & /cancel ────────────────────────────────────────────────────────
# async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     data = load()
#     uid = str(update.effective_user.id)
#     pending = data.get("pending", {}).get(uid)
#     if not pending:
#         await update.message.reply_text("No pending transaction to confirm.")
#         return
#     user = get_user(data, uid)
#     _save_transaction(data, uid, user, pending["amount"], pending["description"], pending["timestamp"], update.message.message_id)
#     del data["pending"][uid]
#     save(data)
#     _, bal = balance_summary(data, uid)
#     await update.message.reply_text(f"✅ Saved!\n{bal}")

# async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     data = load()
#     uid = str(update.effective_user.id)
#     if uid in data.get("pending", {}):
#         del data["pending"][uid]
#         save(data)
#     await update.message.reply_text("❌ Transaction cancelled. Nothing was saved.")

# # ── /balance ──────────────────────────────────────────────────────────────────
# async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     data = load()
#     uid = str(update.effective_user.id)
#     user = get_user(data, uid)
#     if not user["partner_id"]:
#         await update.message.reply_text("⚠️ Link with a partner first using /link @username")
#         return
#     _, bal = balance_summary(data, uid)
#     await update.message.reply_text(bal)

# # ── /history ──────────────────────────────────────────────────────────────────
# async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     data = load()
#     uid = str(update.effective_user.id)
#     user = get_user(data, uid)
#     if not user["partner_id"]:
#         await update.message.reply_text("⚠️ Link with a partner first using /link @username")
#         return

#     txns = data.get("transactions", [])
#     if not txns:
#         await update.message.reply_text("📜 No transactions yet.")
#         return

#     partner = get_user(data, user["partner_id"])
#     lines = ["📜 *Transaction History*\n"]
#     for t in txns[-10:][::-1]:
#         payer_name = user["name"] if t["payer"] == uid else partner["name"]
#         dt = datetime.fromtimestamp(t["timestamp"]).strftime("%b %d %H:%M")
#         lines.append(f"#{t['id']} — {payer_name} paid {t['amount']:.0f} birr for {t['description']} ({dt})")

#     await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# # ── /undo ─────────────────────────────────────────────────────────────────────
# async def undo(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     data = load()
#     uid = str(update.effective_user.id)
#     user = get_user(data, uid)
#     txns = data.get("transactions", [])

#     # find last transaction by this user
#     for i in range(len(txns) - 1, -1, -1):
#         if txns[i]["payer"] == uid:
#             removed = txns.pop(i)
#             save(data)
#             _, bal = balance_summary(data, uid)
#             msg = (f"↩️ Removed: {user['name']} paid {removed['amount']:.0f} birr "
#                    f"for {removed['description']}\n{bal}")
#             await update.message.reply_text(msg)
#             await notify_partner(context, user["partner_id"],
#                 f"↩️ {user['name']} undid a transaction:\n{msg}")
#             return

#     await update.message.reply_text("Nothing to undo.")

# # ── /edit ─────────────────────────────────────────────────────────────────────
# async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     data = load()
#     uid = str(update.effective_user.id)
#     user = get_user(data, uid)

#     if len(context.args) < 2:
#         await update.message.reply_text("Usage: /edit <transaction_number> <new_amount> [new description]\nExample: /edit 3 450 dinner")
#         return

#     try:
#         txn_id = int(context.args[0])
#         new_amount = float(context.args[1])
#     except ValueError:
#         await update.message.reply_text("❌ Invalid format. Example: /edit 3 450 dinner")
#         return

#     new_desc = " ".join(context.args[2:]) if len(context.args) > 2 else None
#     txns = data.get("transactions", [])

#     for t in txns:
#         if t["id"] == txn_id:
#             if t["payer"] != uid:
#                 await update.message.reply_text("❌ You can only edit your own transactions.")
#                 return
#             old_amount = t["amount"]
#             old_desc = t["description"]
#             t["edits"].append({"amount": old_amount, "description": old_desc, "edited_at": time.time()})
#             t["amount"] = new_amount
#             if new_desc:
#                 t["description"] = new_desc
#             save(data)
#             _, bal = balance_summary(data, uid)
#             msg = (f"✏️ Transaction #{txn_id} updated!\n"
#                    f"Was:  {old_amount:.0f} birr for {old_desc}\n"
#                    f"Now:  {new_amount:.0f} birr for {t['description']}\n"
#                    f"{bal}")
#             await update.message.reply_text(msg)
#             await notify_partner(context, user["partner_id"], f"✏️ {user['name']} edited a transaction:\n{msg}")
#             return

#     await update.message.reply_text(f"❌ Transaction #{txn_id} not found. Use /history to see IDs.")

# # ── /settle ───────────────────────────────────────────────────────────────────
# async def settle(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     data = load()
#     uid = str(update.effective_user.id)
#     user = get_user(data, uid)
#     if not user["partner_id"]:
#         await update.message.reply_text("⚠️ Link with a partner first.")
#         return
#     data["transactions"] = []
#     save(data)
#     msg = "✅ All settled up! Balance is now zero. Starting fresh 🎉"
#     await update.message.reply_text(msg)
#     await notify_partner(context, user["partner_id"], f"✅ {user['name']} marked everything as settled! Balance is now zero.")

# # ── Edited message detection ──────────────────────────────────────────────────
# async def on_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     if not update.edited_message:
#         return
#     data = load()
#     uid = str(update.effective_user.id)
#     user = get_user(data, uid)
#     msg_id = str(update.edited_message.message_id)
#     txn_id = data.get("message_map", {}).get(msg_id)
#     if not txn_id:
#         return

#     text = update.edited_message.text or ""
#     parts = text.strip().split()
#     if not parts or parts[0].lower() != "/paid":
#         return

#     try:
#         new_amount = float(parts[1])
#     except (IndexError, ValueError):
#         return

#     new_desc = " ".join(parts[2:]) if len(parts) > 2 else None
#     for t in data.get("transactions", []):
#         if t["id"] == txn_id:
#             old_amount = t["amount"]
#             old_desc = t["description"]
#             t["edits"].append({"amount": old_amount, "description": old_desc, "edited_at": time.time()})
#             t["amount"] = new_amount
#             if new_desc:
#                 t["description"] = new_desc
#             save(data)
#             _, bal = balance_summary(data, uid)
#             msg = (f"✏️ Transaction updated via message edit!\n"
#                    f"Was:  {old_amount:.0f} birr for {old_desc}\n"
#                    f"Now:  {new_amount:.0f} birr for {t['description']}\n"
#                    f"{bal}")
#             await update.edited_message.reply_text(msg)
#             await notify_partner(context, user["partner_id"], f"✏️ {user['name']} edited a transaction:\n{msg}")
#             return

# # ── /help ─────────────────────────────────────────────────────────────────────
# async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text(
#         "📖 *Commands*\n\n"
#         "/start — Register yourself\n"
#         "/link @username — Link with your partner\n"
#         "/paid 500 lunch — Log a payment\n"
#         "/balance — See who owes who\n"
#         "/history — See last 10 transactions\n"
#         "/edit 3 450 dinner — Fix a transaction\n"
#         "/undo — Remove your last transaction\n"
#         "/settle — Mark everything as paid\n"
#         "/confirm — Confirm a flagged duplicate\n"
#         "/cancel — Cancel a flagged duplicate\n\n"
#         "✏️ You can also long-press a /paid message → Edit → the bot updates automatically!",
#         parse_mode="Markdown"
#     )

# # ── Main ──────────────────────────────────────────────────────────────────────
# class Handler(BaseHTTPRequestHandler):
#     def do_GET(self):
#         self.send_response(200)
#         self.end_headers()
#         self.wfile.write(b"Bot is running!")
#     def log_message(self, format, *args):
#         pass

# def run_server():
#     server = HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 8080))), Handler)
#     server.serve_forever()
# def main():
#     token = os.environ.get("BOT_TOKEN")
#     if not token:
#         print("❌ BOT_TOKEN environment variable not set!")
#         print("Set it with: export BOT_TOKEN=your_token_here")
#         return

#     app = ApplicationBuilder().token(token).build()
#     app.add_handler(CommandHandler("start", start))
#     app.add_handler(CommandHandler("link", link))
#     app.add_handler(CommandHandler("paid", paid))
#     app.add_handler(CommandHandler("confirm", confirm))
#     app.add_handler(CommandHandler("cancel", cancel))
#     app.add_handler(CommandHandler("balance", balance))
#     app.add_handler(CommandHandler("history", history))
#     app.add_handler(CommandHandler("undo", undo))
#     app.add_handler(CommandHandler("edit", edit_cmd))
#     app.add_handler(CommandHandler("settle", settle))
#     app.add_handler(CommandHandler("help", help_cmd))
#     app.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE, on_edit))

#     t = threading.Thread(target=run_server)
#     t.daemon = True
#     t.start()

#     print("🤖 Bot is running...")
#     app.run_polling()

# if __name__ == "__main__":
#     main()
import os
import json
import time
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

DATA_FILE = "data.json"

def load():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE) as f:
        return json.load(f)

def save(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_user(data, user_id):
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"name": None, "username": "", "partner_id": None, "transactions": [], "message_map": {}}
    return data[uid]

def balance_summary(data, user_id):
    uid = str(user_id)
    user = get_user(data, uid)
    partner_id = user["partner_id"]
    if not partner_id:
        return None, None
    partner = get_user(data, partner_id)
    total = 0.0
    for t in data.get("transactions", []):
        if t["payer"] == uid:
            total += t["amount"]
        elif t["payer"] == partner_id:
            total -= t["amount"]
    user_name = user["name"] or "You"
    partner_name = partner["name"] or "Your partner"
    if total > 0:
        return total, f"💰 {partner_name} owes {user_name} {total:.0f} birr"
    elif total < 0:
        return total, f"💰 {user_name} owes {partner_name} {abs(total):.0f} birr"
    else:
        return 0, "✅ You're all settled up!"

async def notify_partner(context, partner_id, message):
    try:
        await context.bot.send_message(chat_id=int(partner_id), text=message)
    except Exception:
        pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = str(update.effective_user.id)
    user = get_user(data, uid)
    user["name"] = update.effective_user.first_name
    user["username"] = (update.effective_user.username or "").lower()
    save(data)
    await update.message.reply_text(
        f"👋 Hey {update.effective_user.first_name}!\n\n"
        "I track shared expenses between you and a friend.\n\n"
        "To get started, link with your partner:\n"
        "👉 /link @theirusername"
    )

async def link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = str(update.effective_user.id)
    user = get_user(data, uid)
    if not context.args:
        await update.message.reply_text("Usage: /link @username")
        return
    username = context.args[0].lstrip("@").lower()
    partner_id = None
    for pid, pdata in data.items():
        if pid == uid:
            continue
        if not isinstance(pdata, dict):
            continue
        if pdata.get("username", "").lower() == username:
            partner_id = pid
            break
    if not partner_id:
        await update.message.reply_text(
            f"❌ Couldn't find @{username}.\n\n"
            "Make sure they sent /start to the bot first, then try again."
        )
        return
    user["partner_id"] = partner_id
    partner = get_user(data, partner_id)
    partner["partner_id"] = uid
    save(data)
    partner_name = partner.get("name") or username
    await update.message.reply_text(f"✅ Linked with {partner_name}! You're all set.\n\nTry: /paid 500 lunch")
    await notify_partner(context, partner_id, f"✅ {user['name']} linked with you! You're connected.")

async def paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = str(update.effective_user.id)
    user = get_user(data, uid)
    if not user["partner_id"]:
        await update.message.reply_text("⚠️ Link with a partner first using /link @username")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /paid 500 lunch")
        return
    try:
        amount = float(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Amount must be a number. Example: /paid 500 lunch")
        return
    description = " ".join(context.args[1:]) if len(context.args) > 1 else "no description"
    now = time.time()
    if "transactions" not in data:
        data["transactions"] = []
    recent = [
        t for t in data["transactions"]
        if t["amount"] == amount and now - t["timestamp"] < 600
        and (t["payer"] == uid or t["payer"] == user["partner_id"])
    ]
    if recent:
        r = recent[-1]
        payer_name = user["name"] if r["payer"] == uid else get_user(data, user["partner_id"])["name"]
        dt = datetime.fromtimestamp(r["timestamp"]).strftime("%H:%M")
        if "pending" not in data:
            data["pending"] = {}
        data["pending"][uid] = {"amount": amount, "description": description, "timestamp": now}
        save(data)
        await update.message.reply_text(
            f"⚠️ Similar transaction recorded recently:\n"
            f"👉 {payer_name} paid {r['amount']:.0f} birr for {r['description']} at {dt}\n\n"
            f"Duplicate?\n✅ /confirm — save anyway\n❌ /cancel — don't save"
        )
        return
    _save_transaction(data, uid, user, amount, description, now, update.message.message_id)
    save(data)
    _, bal = balance_summary(data, uid)
    msg = (
        f"✅ {user['name']} paid {amount:.0f} birr for {description}\n"
        f"🕐 {datetime.fromtimestamp(now).strftime('%H:%M')}\n"
        f"{bal}"
    )
    await update.message.reply_text(msg)
    await notify_partner(context, user["partner_id"], f"👀 New transaction!\n{msg}")

def _save_transaction(data, uid, user, amount, description, timestamp, message_id):
    if "transactions" not in data:
        data["transactions"] = []
    if "message_map" not in data:
        data["message_map"] = {}
    txn = {
        "id": len(data["transactions"]) + 1,
        "payer": uid,
        "amount": amount,
        "description": description,
        "timestamp": timestamp,
        "message_id": message_id,
        "edits": []
    }
    data["transactions"].append(txn)
    data["message_map"][str(message_id)] = txn["id"]

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = str(update.effective_user.id)
    pending = data.get("pending", {}).get(uid)
    if not pending:
        await update.message.reply_text("No pending transaction to confirm.")
        return
    user = get_user(data, uid)
    _save_transaction(data, uid, user, pending["amount"], pending["description"], pending["timestamp"], update.message.message_id)
    del data["pending"][uid]
    save(data)
    _, bal = balance_summary(data, uid)
    await update.message.reply_text(f"✅ Saved!\n{bal}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = str(update.effective_user.id)
    if uid in data.get("pending", {}):
        del data["pending"][uid]
        save(data)
    await update.message.reply_text("❌ Transaction cancelled.")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = str(update.effective_user.id)
    user = get_user(data, uid)
    if not user["partner_id"]:
        await update.message.reply_text("⚠️ Link with a partner first using /link @username")
        return
    _, bal = balance_summary(data, uid)
    await update.message.reply_text(bal)

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = str(update.effective_user.id)
    user = get_user(data, uid)
    if not user["partner_id"]:
        await update.message.reply_text("⚠️ Link with a partner first.")
        return
    txns = data.get("transactions", [])
    if not txns:
        await update.message.reply_text("📜 No transactions yet.")
        return
    partner = get_user(data, user["partner_id"])
    lines = ["📜 *Transaction History*\n"]
    for t in txns[-10:][::-1]:
        payer_name = user["name"] if t["payer"] == uid else partner["name"]
        dt = datetime.fromtimestamp(t["timestamp"]).strftime("%b %d %H:%M")
        lines.append(f"#{t['id']} — {payer_name} paid {t['amount']:.0f} birr for {t['description']} ({dt})")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def undo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = str(update.effective_user.id)
    user = get_user(data, uid)
    txns = data.get("transactions", [])
    for i in range(len(txns) - 1, -1, -1):
        if txns[i]["payer"] == uid:
            removed = txns.pop(i)
            save(data)
            _, bal = balance_summary(data, uid)
            msg = f"↩️ Removed: {user['name']} paid {removed['amount']:.0f} birr for {removed['description']}\n{bal}"
            await update.message.reply_text(msg)
            await notify_partner(context, user["partner_id"], f"↩️ {user['name']} undid a transaction:\n{msg}")
            return
    await update.message.reply_text("Nothing to undo.")

async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = str(update.effective_user.id)
    user = get_user(data, uid)
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /edit <number> <amount> [description]\nExample: /edit 3 450 dinner")
        return
    try:
        txn_id = int(context.args[0])
        new_amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid format. Example: /edit 3 450 dinner")
        return
    new_desc = " ".join(context.args[2:]) if len(context.args) > 2 else None
    for t in data.get("transactions", []):
        if t["id"] == txn_id:
            if t["payer"] != uid:
                await update.message.reply_text("❌ You can only edit your own transactions.")
                return
            old_amount = t["amount"]
            old_desc = t["description"]
            t["edits"].append({"amount": old_amount, "description": old_desc, "edited_at": time.time()})
            t["amount"] = new_amount
            if new_desc:
                t["description"] = new_desc
            save(data)
            _, bal = balance_summary(data, uid)
            msg = (f"✏️ Transaction #{txn_id} updated!\nWas: {old_amount:.0f} birr for {old_desc}\nNow: {new_amount:.0f} birr for {t['description']}\n{bal}")
            await update.message.reply_text(msg)
            await notify_partner(context, user["partner_id"], f"✏️ {user['name']} edited a transaction:\n{msg}")
            return
    await update.message.reply_text(f"❌ Transaction #{txn_id} not found. Use /history to see IDs.")

async def unlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = str(update.effective_user.id)
    user = get_user(data, uid)
    partner_id = user["partner_id"]
    if not partner_id:
        await update.message.reply_text("⚠️ You're not linked with anyone.")
        return
    partner = get_user(data, partner_id)
    partner_name = partner.get("name") or "Your partner"
    user["partner_id"] = None
    partner["partner_id"] = None
    save(data)
    await update.message.reply_text(f"🔗 Unlinked from {partner_name}. Use /link @username to reconnect.")
    await notify_partner(context, partner_id, f"🔗 {user['name']} has unlinked from you.")

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = str(update.effective_user.id)
    user = get_user(data, uid)
    partner_id = user["partner_id"]
    data["transactions"] = []
    data["pending"] = {}
    data["message_map"] = {}
    save(data)
    msg = "🔄 All transactions cleared! Starting fresh 🎉\nYou're still linked with your partner."
    await update.message.reply_text(msg)
    if partner_id:
        await notify_partner(context, partner_id, f"🔄 {user['name']} reset all transactions. Starting fresh!")

async def settle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    uid = str(update.effective_user.id)
    user = get_user(data, uid)
    if not user["partner_id"]:
        await update.message.reply_text("⚠️ Link with a partner first.")
        return
    data["transactions"] = []
    save(data)
    msg = "✅ All settled up! Balance is zero. Starting fresh 🎉"
    await update.message.reply_text(msg)
    await notify_partner(context, user["partner_id"], f"✅ {user['name']} marked everything as settled!")

async def on_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.edited_message:
        return
    data = load()
    uid = str(update.effective_user.id)
    user = get_user(data, uid)
    msg_id = str(update.edited_message.message_id)
    txn_id = data.get("message_map", {}).get(msg_id)
    if not txn_id:
        return
    text = update.edited_message.text or ""
    parts = text.strip().split()
    if not parts or parts[0].lower() != "/paid":
        return
    try:
        new_amount = float(parts[1])
    except (IndexError, ValueError):
        return
    new_desc = " ".join(parts[2:]) if len(parts) > 2 else None
    for t in data.get("transactions", []):
        if t["id"] == txn_id:
            old_amount = t["amount"]
            old_desc = t["description"]
            t["edits"].append({"amount": old_amount, "description": old_desc, "edited_at": time.time()})
            t["amount"] = new_amount
            if new_desc:
                t["description"] = new_desc
            save(data)
            _, bal = balance_summary(data, uid)
            msg = (f"✏️ Updated via edit!\nWas: {old_amount:.0f} birr for {old_desc}\nNow: {new_amount:.0f} birr for {t['description']}\n{bal}")
            await update.edited_message.reply_text(msg)
            await notify_partner(context, user["partner_id"], f"✏️ {user['name']} edited a transaction:\n{msg}")
            return

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Commands*\n\n"
        "/start — Register yourself\n"
        "/link @username — Link with your partner\n"
        "/paid 500 lunch — Log a payment\n"
        "/balance — See who owes who\n"
        "/history — See last 10 transactions\n"
        "/edit 3 450 dinner — Fix a transaction\n"
        "/undo — Remove your last transaction\n"
        "/settle — Mark everything as paid\n"
        "/restart — Wipe transactions, start fresh\n"
        "/unlink — Disconnect from your partner\n"
        "/confirm — Save a flagged duplicate\n"
        "/cancel — Discard a flagged duplicate\n\n"
        "✏️ Long-press a /paid message → Edit → bot updates automatically!",
        parse_mode="Markdown"
    )

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    def log_message(self, format, *args):
        pass

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        print("❌ BOT_TOKEN not set!")
        return

    t = threading.Thread(target=run_server)
    t.daemon = True
    t.start()

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("link", link))
    app.add_handler(CommandHandler("paid", paid))
    app.add_handler(CommandHandler("confirm", confirm))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("undo", undo))
    app.add_handler(CommandHandler("edit", edit_cmd))
    app.add_handler(CommandHandler("unlink", unlink))
    app.add_handler(CommandHandler("restart", restart))
    app.add_handler(CommandHandler("settle", settle))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE, on_edit))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()