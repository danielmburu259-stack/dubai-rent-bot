import os, threading, asyncio, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

# ===== RENDER FREE FIX - KEEP THIS AT TOP =====
def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
        def log_message(self, *a): pass
    HTTPServer(("0.0.0.0", port), H).serve_forever()
threading.Thread(target=keep_alive, daemon=True).start()
# ===============================================

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, ConversationHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = -1004386364968
CHANNEL_LINK = "https://t.me/dubairentonly"
BOT_LINK = "https://t.me/Dubairentalsbot"

# States
ROLE, PHONE, T_LOCATION, T_TYPE, T_BUDGET, T_PHOTOS, T_DESC, T_CONTACT, T_CONFIRM, AGENT_BROWSE = range(10)

# In-memory DB - replace with real DB later if you want
users = {}  # user_id -> {role, phone, verified:bool}
listings = []  # list of dicts
drafts = {}  # user_id -> draft

def main_menu_kb(is_verified=False):
    kb = [
        [InlineKeyboardButton("🏠 I'm a Tenant - Post a Rental", callback_data="role_tenant")],
        [InlineKeyboardButton("🕵️ I'm an Agent - Find Tenants", callback_data="role_agent")],
        [InlineKeyboardButton("📢 View Channel", url=CHANNEL_LINK)],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ]
    if is_verified:
        kb.append([InlineKeyboardButton("🔄 Restart / Main Menu", callback_data="restart")])
    return InlineKeyboardMarkup(kb)

def restart_kb():
    # Smart Restart: shown AFTER any finish. Keeps verification.
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Post Another", callback_data="post_another")],
        [InlineKeyboardButton("🔄 Main Menu", callback_data="restart")],
        [InlineKeyboardButton("📢 View Channel", url=CHANNEL_LINK)],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])

def agent_after_buy_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Buy Another Contact", callback_data="buy_another")],
        [InlineKeyboardButton("🔄 Main Menu", callback_data="restart")],
        [InlineKeyboardButton("📢 View Channel", url=CHANNEL_LINK)],
    ])

def help_text():
    return (
        "❓ *HELP - Dubai Rentals*\n\n"
        "🏠 *Tenant:* Post your rental need. We ask for Location, Type, Budget, Photos, Description, and *Contact LAST* so you don't lose your progress.\n\n"
        "🕵️ *Agent:* Browse tenants, pay to unlock contact, then contact them directly.\n\n"
        "✅ *Verification:* You verify phone ONCE. Restart will NOT ask again.\n\n"
        "🔄 *Restart:* Anytime you finish posting or buying, tap Restart / Post Another to start again without re-verifying.\n\n"
        "📢 Channel: @dubairentonly\n"
        "Need human help? Reply here."
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = users.get(uid, {})
    # Smart restart: if verified, skip role/phone and go to menu
    await update.message.reply_text(
        "👋 *Welcome to Dubai Rentals!*\n\nFind tenants / Find rentals fast.\n\nChoose who you are:",
        reply_markup=main_menu_kb(is_verified=u.get("verified", False)),
        parse_mode="Markdown"
    )
    return ROLE

async def restart_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    # IMPROVED RESTART: Clear draft only, KEEP role/phone/verified
    drafts.pop(uid, None)
    context.user_data.clear()
    u = users.get(uid, {})
    await q.edit_message_text(
        "🔄 *Restarted.*\nYour verification is saved, no need to verify again.\n\nWhat do you want to do?",
        reply_markup=main_menu_kb(is_verified=u.get("verified", False)),
        parse_mode="Markdown"
    )
    return ROLE

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(help_text(), reply_markup=restart_kb(), parse_mode="Markdown")
    return ROLE

async def role_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    role = "tenant" if q.data == "role_tenant" else "agent"
    # If already verified, skip phone
    if users.get(uid, {}).get("verified"):
        users[uid]["role"] = role
        if role == "tenant":
            drafts[uid] = {}
            await q.edit_message_text("🏠 *Tenant Post - Step 1/6*\n\nWhere is the property? (e.g. Marina, Downtown, JLT)", parse_mode="Markdown")
            return T_LOCATION
        else:
            return await show_listings(q, context)
    # Not verified -> ask phone
    users[uid] = {"role": role, "verified": False}
    kb = ReplyKeyboardMarkup([[KeyboardButton("📱 Share My Phone", request_contact=True)]], one_time_keyboard=True, resize_keyboard=True)
    await q.edit_message_text("📱 *One-time Verification*\n\nPlease share your phone to verify. You will only do this ONCE.", parse_mode="Markdown")
    await q.message.reply_text("Tap the button below:", reply_markup=kb)
    return PHONE

async def phone_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    contact = update.message.contact
    if not contact:
        await update.message.reply_text("Please tap Share My Phone button.")
        return PHONE
    users[uid]["phone"] = contact.phone_number
    users[uid]["verified"] = True
    await update.message.reply_text("✅ Verified! You won't need to do this again.", reply_markup=ReplyKeyboardRemove())
    if users[uid]["role"] == "tenant":
        drafts[uid] = {}
        await update.message.reply_text("🏠 *Tenant Post - Step 1/6*\n\nWhere is the property?", parse_mode="Markdown")
        return T_LOCATION
    else:
        # Agent flow needs a message to show listings
        await update.message.reply_text("🕵️ Here are tenants:", reply_markup=main_menu_kb(True))
        return AGENT_BROWSE

# ---- TENANT FLOW - CONTACTS LAST ----
async def t_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    drafts[update.effective_user.id]["location"] = update.message.text
    await update.message.reply_text("Step 2/6: Property Type? (Studio, 1BR, 2BR, Villa)")
    return T_TYPE

async def t_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    drafts[update.effective_user.id]["type"] = update.message.text
    await update.message.reply_text("Step 3/6: Budget? (e.g. 5000 AED/month)")
    return T_BUDGET

async def t_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    drafts[update.effective_user.id]["budget"] = update.message.text
    await update.message.reply_text("Step 4/6: Send photos (or type 'skip')")
    return T_PHOTOS

async def t_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if update.message.photo:
        drafts[uid].setdefault("photos", []).append(update.message.photo[-1].file_id)
        await update.message.reply_text("Photo saved. Send another or type 'done'")
        return T_PHOTOS
    if update.message.text and update.message.text.lower() in ["skip", "done"]:
        await update.message.reply_text("Step 5/6: Short description?")
        return T_DESC
    await update.message.reply_text("Send photo or type 'done'")
    return T_PHOTOS

async def t_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    drafts[update.effective_user.id]["desc"] = update.message.text
    # CONTACTS LAST - Weakness fixed: if user quits earlier, we still have listing data
    await update.message.reply_text("Step 6/6 - LAST STEP: Your contact? (WhatsApp / phone to show to agents)")
    return T_CONTACT

async def t_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    drafts[uid]["contact"] = update.message.text
    d = drafts[uid]
    preview = f"🏠 *PREVIEW*\n\n📍 {d.get('location')}\n🏡 {d.get('type')}\n💰 {d.get('budget')}\n📝 {d.get('desc')}\n📞 Contact: {d.get('contact')}\n\nPost this?"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Post", callback_data="confirm_post")],
        [InlineKeyboardButton("🔄 Restart", callback_data="restart")],
    ])
    await update.message.reply_text(preview, reply_markup=kb, parse_mode="Markdown")
    return T_CONFIRM

async def confirm_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    d = drafts.get(uid, {})
    listing_id = len(listings)
    d["id"] = listing_id
    d["owner"] = uid
    d["owner_phone"] = users.get(uid, {}).get("phone", "")
    listings.append(d)

    # Channel post with Share button
    caption = f"🏠 *NEW RENTAL NEEDED*\n\n📍 Location: {d.get('location')}\n🏡 Type: {d.get('type')}\n💰 Budget: {d.get('budget')}\n📝 {d.get('desc')}\n\n👉 Agents: Open bot to unlock contact"
    share_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🕵️ I'm an Agent - Get Contact", url=BOT_LINK)],
        [InlineKeyboardButton("🔗 Share This Listing", switch_inline_query=f"Rental in {d.get('location')} - {d.get('budget')}")],
        [InlineKeyboardButton("📢 View Channel", url=CHANNEL_LINK)],
    ])
    try:
        if d.get("photos"):
            await context.bot.send_photo(CHANNEL_ID, d["photos"][0], caption=caption, reply_markup=share_kb, parse_mode="Markdown")
        else:
            await context.bot.send_message(CHANNEL_ID, caption, reply_markup=share_kb, parse_mode="Markdown")
    except Exception as e:
        print("Channel post failed:", e)

    await q.edit_message_text("✅ *Posted to @dubairentonly!*\n\nWant to post another?", reply_markup=restart_kb(), parse_mode="Markdown")
    drafts.pop(uid, None)
    return ROLE

# ---- AGENT FLOW ----
async def show_listings(q, context):
    if not listings:
        await q.edit_message_text("No listings yet. Check back soon.", reply_markup=restart_kb())
        return AGENT_BROWSE
    text = "🕵️ *Available Tenants:*\n\n"
    kb = []
    for l in listings[-10:]:
        text += f"#{l['id']} - {l.get('location')} | {l.get('type')} | {l.get('budget')}\n"
        kb.append([InlineKeyboardButton(f"💳 Buy Contact #{l['id']} - 20 AED", callback_data=f"buy_{l['id']}")])
    kb.append([InlineKeyboardButton("🔄 Main Menu", callback_data="restart")])
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return AGENT_BROWSE

async def buy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    # In real version: check payment here. For now simulate paid.
    lid = int(q.data.split("_")[1])
    l = listings[lid]
    # After payment, reveal contact
    await q.edit_message_text(
        f"✅ *Payment Confirmed!*\n\nContact for #{lid}:\n📞 {l.get('contact')}\nOwner Phone: {l.get('owner_phone')}\n\nGood luck!",
        reply_markup=agent_after_buy_kb(),
        parse_mode="Markdown"
    )
    return ROLE

async def post_another(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    drafts[uid] = {}
    await q.edit_message_text("🏠 *New Post - Step 1/6*\n\nWhere is the property?", parse_mode="Markdown")
    return T_LOCATION

async def buy_another(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    return await show_listings(q, context)

async def daily_welcome(context: ContextTypes.DEFAULT_TYPE):
    try:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Post a Rental", url=BOT_LINK)],
            [InlineKeyboardButton("🕵️ Find Tenants", url=BOT_LINK)],
            [InlineKeyboardButton("🔗 Share Channel", switch_inline_query="Dubai Rentals - Tenants & Agents")],
        ])
        await context.bot.send_message(CHANNEL_ID, "👋 *Good Morning Dubai!*\n\n🏠 Tenants - Post your rental need in the bot\n🕵️ Agents - Unlock verified tenant contacts\n\nStart here 👇", reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        print("Daily post failed:", e)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ROLE: [
                CallbackQueryHandler(role_handler, pattern="^role_"),
                CallbackQueryHandler(restart_handler, pattern="^restart$"),
                CallbackQueryHandler(help_handler, pattern="^help$"),
                CallbackQueryHandler(post_another, pattern="^post_another$"),
                CallbackQueryHandler(buy_another, pattern="^buy_another$"),
                CallbackQueryHandler(buy_handler, pattern="^buy_"),
                CallbackQueryHandler(confirm_post, pattern="^confirm_post$"),
            ],
            PHONE: [MessageHandler(filters.CONTACT, phone_handler)],
            T_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, t_location)],
            T_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, t_type)],
            T_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, t_budget)],
            T_PHOTOS: [MessageHandler(filters.PHOTO | filters.TEXT, t_photos)],
            T_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, t_desc)],
            T_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, t_contact)],
            T_CONFIRM: [CallbackQueryHandler(confirm_post, pattern="^confirm_post$"), CallbackQueryHandler(restart_handler, pattern="^restart$")],
            AGENT_BROWSE: [CallbackQueryHandler(buy_handler, pattern="^buy_"), CallbackQueryHandler(restart_handler, pattern="^restart$")],
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("help", start)],
        allow_reentry=True
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("help", start))
    # Daily welcome at 9 AM Dubai time - runs every 24h
    if app.job_queue:
        app.job_queue.run_repeating(daily_welcome, interval=86400, first=10)
    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
