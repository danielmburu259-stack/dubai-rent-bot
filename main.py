import os, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
        def log_message(self, *a): pass
    HTTPServer(("0.0.0.0", port), H).serve_forever()
threading.Thread(target=keep_alive, daemon=True).start()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, ConversationHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = -1004386364968
CHANNEL_LINK = "https://t.me/dubairentonly"
BOT_LINK = "https://t.me/Dubairentalsbot"
BINANCE_ID = os.environ.get("BINANCE_ID", "Ask admin")
TRC20 = os.environ.get("TRC20_ADDRESS", os.environ.get("TRC20", "Ask admin"))
ADMIN_ID = os.environ.get("ADMIN_ID")
PRICE_CONTACT = 10
PRICE_PIN = 25

# FIXED: 23 states, so range(23) - not 26
ROLE = 0
A_LOC = 1
A_RENT = 2
A_TYPE = 3
A_FURN = 4
A_AVAIL = 5
A_PHOTOS = 6
A_DESC = 7
A_NAME = 8
A_VERIFY = 9
A_CONTACT = 10
A_CONFIRM = 11
T_LOC = 12
T_BUDGET = 13
T_TYPE = 14
T_CONTACT = 15
T_CONFIRM = 16
INT_BUDGET = 17
INT_MOVEIN = 18
INT_CONTACT = 19
INT_CONFIRM = 20
PAY_METHOD = 21
PAY_SCREENSHOT = 22

users = {}
agent_posts = []
tenant_posts = []
leads = []
pending = {}
interested = set()

def help_text():
    return ("❓ HELP\n\nAgent: Post PROPERTY free. Verification + Contact only on 1st post, at the END.\n\nTenant: Post WANTED free. Contact at the END via Share button. Never posted publicly.\n\nContacts: 10 AED per contact. Agent pays to get Tenant contact. Tenant can pay 10 AED to get Agent contact.\n\nPinned Post: 25 AED - Pinned on top of @dubairentonly for 24 hours, then auto-unpinned.\n\nChannel: @dubairentonly\nAdmin: @Givon5")

def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🕵️ I'm an Agent - Post PROPERTY", callback_data="role_agent")],
        [InlineKeyboardButton("🏠 I'm a Tenant - Post WANTED", callback_data="role_tenant")],
        [InlineKeyboardButton("📢 View Channel", url=CHANNEL_LINK)],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
        [InlineKeyboardButton("🔄 Post Again / Main Menu", callback_data="restart")],
    ])

def share_phone_kb():
    return ReplyKeyboardMarkup([[KeyboardButton("📱 Share My Contact", request_contact=True)]], one_time_keyboard=True, resize_keyboard=True)

def pin_kb(post_kind, post_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📌 Pin This Post - 25 AED (24h)", callback_data="pin_" + post_kind + "_" + str(post_id))],
        [InlineKeyboardButton("🔄 Main Menu", callback_data="restart")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])

async def unpin_after_24h(context: ContextTypes.DEFAULT_TYPE):
    msg_id = context.job.data
    try:
        await context.bot.unpin_chat_message(CHANNEL_ID, msg_id)
        print("Auto-unpinned after 24h")
    except Exception as e:
        print("Auto-unpin failed:", e)

def schedule_unpin(app, msg_id):
    if app.job_queue:
        app.job_queue.run_once(unpin_after_24h, when=86400, data=msg_id, name="unpin_" + str(msg_id))

async def unpin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if ADMIN_ID and uid != str(ADMIN_ID):
        await update.message.reply_text("❌ Only admin can unpin.")
        return
    args = context.args or []
    try:
        if args and args[0].lower() == "all":
            await context.bot.unpin_all_chat_messages(CHANNEL_ID)
            await update.message.reply_text("✅ All pinned posts unpinned.")
            return
        if args:
            msg_id = int(args[0])
            await context.bot.unpin_chat_message(CHANNEL_ID, msg_id)
            await update.message.reply_text("✅ Unpinned message " + str(msg_id))
            return
        await context.bot.unpin_all_chat_messages(CHANNEL_ID)
        await update.message.reply_text("✅ Unpinned. Usage: /unpin <message_id> or /unpin all")
    except Exception as e:
        await update.message.reply_text("Pin failed - is bot admin with Pin permission? Error: " + str(e))

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Your ID: " + str(update.effective_user.id) + "\nIf you are admin, put this number in Render as ADMIN_ID.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if args and args[0].startswith("interested_"):
        return await show_agent_post_in_dm(update, context, int(args[0].split("_")[1]))
    if args and args[0].startswith("wanted_"):
        return await show_wanted_in_dm(update, context, int(args[0].split("_")[1]))
    await update.message.reply_text("👋 Welcome to Dubai Rentals!\n\nPosting is FREE. Contacts 10 AED. Pinned Post 25 AED (24h).\n\nWho are you?", reply_markup=main_kb(), parse_mode="Markdown")
    return ROLE

async def restart_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data.clear()
    await q.edit_message_text("🔄 Main Menu\nWho are you?", reply_markup=main_kb(), parse_mode="Markdown")
    return ROLE

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(help_text(), reply_markup=main_kb(), parse_mode="Markdown")
    return ROLE

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(help_text(), reply_markup=main_kb(), parse_mode="Markdown")
    return ROLE

async def role_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "role_agent":
        context.user_data["role"] = "agent"
        context.user_data["draft"] = {}
        await q.edit_message_text("🕵️ AGENT - PROPERTY Post\n\nStep 1: Location? (e.g. Marina, Downtown)", parse_mode="Markdown")
        return A_LOC
    else:
        context.user_data["role"] = "tenant"
        context.user_data["draft"] = {}
        await q.edit_message_text("🏠 TENANT - WANTED Post\n\nStep 1: Location you want? (e.g. JLT, Marina)", parse_mode="Markdown")
        return T_LOC

async def a_loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["draft"]["location"] = update.message.text
    await update.message.reply_text("Step 2: Rent? (e.g. 6000 AED/month)")
    return A_RENT

async def a_rent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["draft"]["rent"] = update.message.text
    await update.message.reply_text("Step 3: Type? (Studio, 1BR, 2BR, Villa)")
    return A_TYPE

async def a_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["draft"]["type"] = update.message.text
    await update.message.reply_text("Step 4: Furnished / Unfurnished / Semi?")
    return A_FURN

async def a_furn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["draft"]["furn"] = update.message.text
    await update.message.reply_text("Step 5: Available From? (e.g. 1 Dec, Immediately)")
    return A_AVAIL

async def a_avail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["draft"]["avail"] = update.message.text
    await update.message.reply_text("Step 6: Send photos (or type 'skip')")
    return A_PHOTOS

async def a_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data["draft"]
    if update.message.photo:
        if "photos" not in d:
            d["photos"] = []
        d["photos"].append(update.message.photo[-1].file_id)
        await update.message.reply_text("Photo saved. Send another or type 'done'")
        return A_PHOTOS
    if update.message.text and update.message.text.lower() in ["skip", "done"]:
        await update.message.reply_text("Step 7: Short description + any other things tenants need?")
        return A_DESC
    await update.message.reply_text("Send photo or type 'done'")
    return A_PHOTOS

async def a_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["draft"]["desc"] = update.message.text
    await update.message.reply_text("Step 8: Agent / Landlord Name?")
    return A_NAME

async def a_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["draft"]["name"] = update.message.text
    uid = update.effective_user.id
    if not users.get(uid, {}).get("verified"):
        await update.message.reply_text("🔐 Final Step - Verification (only this first time)\n\nPlease share your phone. You will NOT be asked again.", reply_markup=share_phone_kb(), parse_mode="Markdown")
        return A_VERIFY
    return await a_check_contact(update, context)

async def a_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not update.message.contact:
        await update.message.reply_text("Please tap Share My Contact button.")
        return A_VERIFY
    if uid not in users:
        users[uid] = {}
    users[uid]["verified"] = True
    users[uid]["verify_phone"] = update.message.contact.phone_number
    await update.message.reply_text("✅ Verified! You won't need this again.", reply_markup=ReplyKeyboardRemove())
    return await a_check_contact(update, context)

async def a_check_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if users.get(uid, {}).get("agent_contact"):
        context.user_data["draft"]["agent_contact"] = users[uid]["agent_contact"]
        return await a_preview(update, context)
    await update.message.reply_text("📱 Final Step - Your Contact\n\nThis contact will NEVER be in the channel post. It will only be given to interested tenants who pay 10 AED.\n\nPlease share your contact:", reply_markup=share_phone_kb(), parse_mode="Markdown")
    return A_CONTACT

async def a_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not update.message.contact:
        await update.message.reply_text("Please tap Share My Contact button.")
        return A_CONTACT
    if uid not in users:
        users[uid] = {}
    users[uid]["agent_contact"] = update.message.contact.phone_number
    context.user_data["draft"]["agent_contact"] = update.message.contact.phone_number
    await update.message.reply_text("✅ Contact saved (private).", reply_markup=ReplyKeyboardRemove())
    return await a_preview(update, context)

async def a_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data["draft"]
    txt = "👀 PREVIEW - PROPERTY\n\nLocation: " + str(d.get("location")) + "\nRent: " + str(d.get("rent")) + "\nType: " + str(d.get("type")) + " | " + str(d.get("furn")) + "\nAvailable: " + str(d.get("avail")) + "\nAgent: " + str(d.get("name")) + "\nDesc: " + str(d.get("desc")) + "\n\nNo contact will be shown in channel.\n\nPost this?"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, POST", callback_data="agent_confirm")],
        [InlineKeyboardButton("❌ Cancel", callback_data="restart")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=kb, parse_mode="Markdown")
    else:
        await update.message.reply_text(txt, reply_markup=kb, parse_mode="Markdown")
    return A_CONFIRM

async def agent_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    d = context.user_data.get("draft", {})
    pid = len(agent_posts)
    post = {}
    post["id"] = pid
    post["owner"] = uid
    post["location"] = d.get("location")
    post["rent"] = d.get("rent")
    post["type"] = d.get("type")
    post["furn"] = d.get("furn")
    post["avail"] = d.get("avail")
    post["desc"] = d.get("desc")
    post["name"] = d.get("name")
    post["photos"] = d.get("photos", [])
    post["agent_contact"] = d.get("agent_contact")
    post["channel_msg_id"] = None
    agent_posts.append(post)
    caption = "🏠 PROPERTY FOR RENT\n\nLocation: " + str(d.get("location")) + "\nRent: " + str(d.get("rent")) + "\nType: " + str(d.get("type")) + " | " + str(d.get("furn")) + "\nAvailable: " + str(d.get("avail")) + "\nAgent: " + str(d.get("name")) + "\nDesc: " + str(d.get("desc")) + "\n\nTap to show interest"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 I'm Interested", url=BOT_LINK + "?start=interested_" + str(pid))],
        [InlineKeyboardButton("🔗 Share", switch_inline_query="Property in " + str(d.get("location")))],
        [InlineKeyboardButton("📢 Channel", url=CHANNEL_LINK)],
    ])
    try:
        if d.get("photos"):
            msg = await context.bot.send_photo(CHANNEL_ID, d["photos"][0], caption=caption, reply_markup=kb, parse_mode="Markdown")
        else:
            msg = await context.bot.send_message(CHANNEL_ID, caption, reply_markup=kb, parse_mode="Markdown")
        post["channel_msg_id"] = msg.message_id
    except Exception as e:
        print("Channel post failed", e)
    await q.edit_message_text("✅ Posted to @dubairentonly!\nNo contact was posted publicly.\n\nWant to pin it on top for 25 AED (24h)?", reply_markup=pin_kb("agent", pid), parse_mode="Markdown")
    context.user_data.clear()
    return ROLE

async def t_loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["draft"]["location"] = update.message.text
    await update.message.reply_text("Step 2: Budget? (e.g. 5000 AED/month)")
    return T_BUDGET

async def t_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["draft"]["budget"] = update.message.text
    await update.message.reply_text("Step 3: Type needed? (Studio, 1BR, 2BR, Villa)")
    return T_TYPE

async def t_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["draft"]["type"] = update.message.text
    await update.message.reply_text("🔒 Last Step - Your Contact\n\nYour contact is SAFE. It will NEVER be posted publicly. It will only be given to agents who pay 10 AED to contact you.\n\nPlease share your contact:", reply_markup=share_phone_kb(), parse_mode="Markdown")
    return T_CONTACT

async def t_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.contact:
        await update.message.reply_text("Please tap Share My Contact button to avoid fake numbers.")
        return T_CONTACT
    context.user_data["draft"]["contact"] = update.message.contact.phone_number
    await update.message.reply_text("✅ Contact saved (private).", reply_markup=ReplyKeyboardRemove())
    d = context.user_data["draft"]
    txt = "👀 PREVIEW - WANTED\n\nLocation: " + str(d.get("location")) + "\nBudget: " + str(d.get("budget")) + "\nType: " + str(d.get("type")) + "\n\nNo contact will be shown in channel.\n\nPost this?"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, POST", callback_data="tenant_confirm")],
        [InlineKeyboardButton("❌ Cancel", callback_data="restart")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])
    await update.message.reply_text(txt, reply_markup=kb, parse_mode="Markdown")
    return T_CONFIRM

async def tenant_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    d = context.user_data.get("draft", {})
    pid = len(tenant_posts)
    post = {}
    post["id"] = pid
    post["owner"] = uid
    post["location"] = d.get("location")
    post["budget"] = d.get("budget")
    post["type"] = d.get("type")
    post["contact"] = d.get("contact")
    post["channel_msg_id"] = None
    tenant_posts.append(post)
    caption = "🔍 TENANT LOOKING FOR RENT\n\nWanted: " + str(d.get("location")) + "\nBudget: " + str(d.get("budget")) + "\nType: " + str(d.get("type")) + "\n\nAgents: Tap to get Tenant contact (10 AED)"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Get Tenant Contact - 10 AED", url=BOT_LINK + "?start=wanted_" + str(pid))],
        [InlineKeyboardButton("🔗 Share", switch_inline_query="Wanted in " + str(d.get("location")))],
        [InlineKeyboardButton("📢 Channel", url=CHANNEL_LINK)],
    ])
    try:
        msg = await context.bot.send_message(CHANNEL_ID, caption, reply_markup=kb, parse_mode="Markdown")
        post["channel_msg_id"] = msg.message_id
    except Exception as e:
        print("Channel post failed", e)
    await q.edit_message_text("✅ Posted to @dubairentonly!\nNo contact was posted publicly.\n\nWant to pin it on top for 25 AED (24h)?", reply_markup=pin_kb("tenant", pid), parse_mode="Markdown")
    context.user_data.clear()
    return ROLE

async def show_agent_post_in_dm(update: Update, context: ContextTypes.DEFAULT_TYPE, pid):
    if pid >= len(agent_posts):
        await update.message.reply_text("Post not found.", reply_markup=main_kb())
        return ROLE
    p = agent_posts[pid]
    context.user_data["interested_pid"] = pid
    txt = "🏠 PROPERTY\n\nLocation: " + str(p.get("location")) + "\nRent: " + str(p.get("rent")) + "\nType: " + str(p.get("type")) + " | " + str(p.get("furn")) + "\nAvailable: " + str(p.get("avail")) + "\nAgent: " + str(p.get("name")) + "\nDesc: " + str(p.get("desc")) + "\n\nAre you interested?"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, I'm Interested", callback_data="int_yes")],
        [InlineKeyboardButton("❌ No", callback_data="restart")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])
    await update.message.reply_text(txt, reply_markup=kb, parse_mode="Markdown")
    return ROLE

async def int_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    pid = context.user_data.get("interested_pid")
    if (uid, pid) in interested:
        await q.edit_message_text("You already sent interest for this property. Agent will contact you.", reply_markup=main_kb())
        return ROLE
    await q.edit_message_text("✅ Interested!\n\nWhat is your Budget?", parse_mode="Markdown")
    return INT_BUDGET

async def int_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lead_budget"] = update.message.text
    await update.message.reply_text("Move-in Date? (e.g. 1 Dec)")
    return INT_MOVEIN

async def int_movein(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lead_movein"] = update.message.text
    await update.message.reply_text("🔒 Your Contact\n\nGive your number so Agent can contact you. It will NOT be posted publicly. It will only be shown to this Agent if he pays 10 AED.", reply_markup=share_phone_kb(), parse_mode="Markdown")
    return INT_CONTACT

async def int_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.contact:
        await update.message.reply_text("Please tap Share My Contact button.")
        return INT_CONTACT
    context.user_data["lead_contact"] = update.message.contact.phone_number
    await update.message.reply_text("✅ Contact saved.", reply_markup=ReplyKeyboardRemove())
    pid = context.user_data.get("interested_pid")
    p = agent_posts[pid]
    txt = "👀 CONFIRM - Send to Agent?\n\nProperty: " + str(p.get("location")) + " - " + str(p.get("rent")) + "\nYour Budget: " + str(context.user_data.get("lead_budget")) + "\nMove-in: " + str(context.user_data.get("lead_movein")) + "\nYour Contact: " + str(context.user_data.get("lead_contact")) + " (private, only Agent sees after paying)\n\nSend?"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Send
