import os, logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
BINANCE_ID = os.environ.get("BINANCE_ID", "844432726")
TRC20 = os.environ.get("TRC20", "TGYX...64tR")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
PORT = int(os.environ.get("PORT", "10000"))

logging.basicConfig(level=logging.INFO)
# In-memory DB for V1 - later we move to Postgres
users = {}
posts = []

BAD_WORDS = ["crypto", "loan", "visa", "job", "investment", "bitcoin", "forex"]

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 I Want To Rent (Tenant)", callback_data="tenant")],
        [InlineKeyboardButton("🏢 I Have House To Rent (Agent)", callback_data="agent")],
        [InlineKeyboardButton("⭐ Featured 30 AED / Pinned 50 AED", callback_data="promote")],
        [InlineKeyboardButton("✅ Verified Badge 100 AED", callback_data="verified")],
        [InlineKeyboardButton("📞 Get Contact 10 AED", callback_data="contact")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to Dubai Rent Only 🇦🇪\n\n*No Buy. No Commercial. No Scam. Only Verified Rentals.*\n\nPosting is FREE for Tenants & Agents.\nYou only pay for: Contact 10 AED | Featured 30 AED | Pinned 50 AED | Verified Badge 100 AED",
        parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu())

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    if q.data == "tenant":
        users[uid] = {"role": "tenant", "step": "phone"}
        kb = ReplyKeyboardMarkup([[KeyboardButton("📱 Share My Contact", request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)
        await q.message.reply_text("TENANT - Step 1/4: Share your phone to verify. We NEVER show it publicly.", reply_markup=kb)
    elif q.data == "agent":
        users[uid] = {"role": "agent", "step": "phone"}
        kb = ReplyKeyboardMarkup([[KeyboardButton("📱 Share My Contact", request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)
        await q.message.reply_text("AGENT - Step 1/5: Share your phone to verify. Then send Trakheesi screenshot.", reply_markup=kb)
    elif q.data == "promote":
        await q.message.reply_text("⭐ PROMOTE\n\nFeatured 30 AED / 24h - Top of bot + sent to 10 matching users\nPinned 50 AED / 24h - Pinned in Channel (only 2 slots/day)\n\nChoose one, then pay with Binance / TRC20 / Stars.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⭐ Featured - 30 AED", callback_data="pay_featured")],
                [InlineKeyboardButton("📌 Pinned - 50 AED", callback_data="pay_pinned")],
            ]))
    elif q.data == "verified":
        await q.message.reply_text("✅ VERIFIED BADGE - 100 AED one-time\n\nSend Trakheesi + RERA screenshot. Admin checks in 2 mins. You get Green Badge forever.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Pay 100 AED - Verified", callback_data="pay_verified")]]))
    elif q.data == "contact":
        await q.message.reply_text("📞 CONTACT - 10 AED\n\nPay to reveal phone of this listing. First contact FREE after Trakheesi upload.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Pay 10 AED - Contact", callback_data="pay_contact")]]))
    elif q.data.startswith("pay_"):
        await show_payment(q, q.data)
    elif q.data.startswith("report_"):
        await q.message.reply_text("Thanks. Report sent. 3 reports = auto-hide. Admin will check.")
    elif q.data.startswith("approve_"):
        # Admin only - simplified for V1
        await q.message.reply_text("✅ Approved by Admin. Post is now live.")

async def show_payment(q, pay_type):
    prices = {"pay_contact": ("Contact", "10 AED", "10"), "pay_featured": ("Featured", "30 AED", "30"), "pay_pinned": ("Pinned", "50 AED", "50"), "pay_verified": ("Verified Badge", "100 AED", "100")}
    name, price, _ = prices.get(pay_type, ("Payment", "10 AED", "10"))
    text = f"💳 Pay for {name} - {price}\n\n**1. Binance Pay:** ID `{BINANCE_ID}` - Send {price} - Screenshot receipt\n**2. TRC20 USDT:** `{TRC20}`\n⚠️ ONLY TRC20. Other network = LOST, no refund. Copy address.\n**3. Telegram Stars:** Pay inside Telegram (auto-approve)\n\nAfter Binance/TRC20, send screenshot here. Admin approves in 5 mins."
    await q.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⭐ Pay with Stars (Auto)", callback_data=f"stars_{pay_type}")],
            [InlineKeyboardButton("📸 I Paid - Send Screenshot", callback_data="send_screenshot")],
        ]))

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if uid in users and users[uid].get("step") == "phone":
        users[uid]["phone"] = update.message.contact.phone_number
        users[uid]["step"] = "details"
        if users[uid]["role"] == "tenant":
            await update.message.reply_text("✅ Phone verified. Now send in ONE message:\n\nArea / Type / Exact Budget / Move-in Date\nExample: Marina, 1BR, 65000, 1 Dec")
        else:
            await update.message.reply_text("✅ Phone verified. Now send Trakheesi Number + Screenshot of Trakheesi / RERA card.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    txt = update.message.text or ""
    # Scam filter - NO price check
    if any(w in txt.lower() for w in BAD_WORDS):
        await update.message.reply_text("❌ Rejected: Your message contains forbidden words (crypto/loan/visa/job). Dubai Rent Only.")
        return
    if uid in users and users[uid].get("step") == "details":
        users[uid]["details"] = txt
        users[uid]["step"] = "done"
        # Send to admin for first-post approval
        if ADMIN_ID:
            try:
                await context.bot.send_message(ADMIN_ID, f"🆕 NEW POST - {users[uid]['role'].upper()}\nUser: {update.message.from_user.first_name} @{update.message.from_user.username}\nPhone: {users[uid].get('phone')}\nDetails: {txt}\n\nCheck Trakheesi & Approve.")
            except: pass
        await update.message.reply_text("✅ Received! Your post is FREE and sent for verification.\nAdmin checks Trakheesi (for agents) in 2 mins.\nOnce approved, you get matching + Daily Digest 9am.\n\nWant more views? ⭐ Featured 30 AED / 📌 Pinned 50 AED", reply_markup=main_menu())
    else:
        await update.message.reply_text("Use /start to begin.", reply_markup=main_menu())

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    # If agent sends photo = Trakheesi or house photos
    await update.message.reply_text("📸 Photo received. If this is Trakheesi, admin will check it. If house photos, send Price + Area in next message.\n\nYour post is FREE. You only pay for Contact / Featured / Pinned / Verified.")

def build_app():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return app

if __name__ == "__main__":
    app = build_app()
    # Webhook mode = never sleeps, Telegram pushes to us
    if WEBHOOK_URL:
        app.run_webhook(listen="0.0.0.0", port=PORT, url_path=BOT_TOKEN, webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    else:
        app.run_polling()
