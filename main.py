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

(ROLE, A_LOC, A_RENT, A_TYPE, A_FURN, A_AVAIL, A_PHOTOS, A_DESC, A_NAME, A_VERIFY, A_CONTACT, A_CONFIRM, T_LOC, T_BUDGET, T_TYPE, T_CONTACT, T_CONFIRM, INT_BUDGET, INT_MOVEIN, INT_CONTACT, INT_CONFIRM, PAY_METHOD, PAY_SCREENSHOT) = range(26)

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
        [InlineKeyboardButton("✅ Yes, Send to Agent", callback_data="int_confirm")],
        [InlineKeyboardButton("❌ Cancel", callback_data="restart")],
    ])
    await update.message.reply_text(txt, reply_markup=kb, parse_mode="Markdown")
    return INT_CONFIRM

async def int_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    pid = context.user_data.get("interested_pid")
    p = agent_posts[pid]
    interested.add((uid, pid))
    lead_id = len(leads)
    new_lead = {}
    new_lead["id"] = lead_id
    new_lead["agent_post_id"] = pid
    new_lead["tenant_id"] = uid
    new_lead["agent_id"] = p["owner"]
    new_lead["budget"] = context.user_data.get("lead_budget")
    new_lead["movein"] = context.user_data.get("lead_movein")
    new_lead["contact"] = context.user_data.get("lead_contact")
    leads.append(new_lead)
    agent_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Pay 10 AED to Unlock Contact", callback_data="pay_lead_" + str(lead_id))],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])
    try:
        msg_text = "🔔 NEW INTERESTED TENANT!\n\nProperty: " + str(p.get("location")) + " - " + str(p.get("rent")) + "\nTenant Budget: " + str(context.user_data.get("lead_budget")) + "\nMove-in: " + str(context.user_data.get("lead_movein")) + "\nContact: HIDDEN - Pay 10 AED to unlock"
        await context.bot.send_message(p["owner"], msg_text, reply_markup=agent_kb, parse_mode="Markdown")
    except Exception as e:
        print("Agent DM failed", e)
    tenant_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Yes, Get Agent Contact - 10 AED", callback_data="pay_agent_" + str(lead_id))],
        [InlineKeyboardButton("⏳ No, Let Agent Contact Me", callback_data="restart")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])
    await q.edit_message_text("✅ Sent to Agent!\nAgent got your Budget + Move-in, but NOT your contact yet. He must pay 10 AED to see it.\n\nDo you want Agent's contact now?", reply_markup=tenant_kb, parse_mode="Markdown")
    return ROLE

async def show_wanted_in_dm(update: Update, context: ContextTypes.DEFAULT_TYPE, pid):
    if pid >= len(tenant_posts):
        await update.message.reply_text("Post not found.", reply_markup=main_kb())
        return ROLE
    p = tenant_posts[pid]
    context.user_data["wanted_pid"] = pid
    txt = "🔍 WANTED\n\nLocation: " + str(p.get("location")) + "\nBudget: " + str(p.get("budget")) + "\nType: " + str(p.get("type")) + "\n\nGet Tenant contact for 10 AED?"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Pay 10 AED - Get Contact", callback_data="pay_wanted_" + str(pid))],
        [InlineKeyboardButton("❌ No", callback_data="restart")],
    ])
    await update.message.reply_text(txt, reply_markup=kb, parse_mode="Markdown")
    return ROLE

def pay_kb(kind, ref_id, price):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟡 Binance ID", callback_data="paymethod_binance_" + kind + "_" + str(ref_id) + "_" + str(price))],
        [InlineKeyboardButton("🔵 TRC20 USDT", callback_data="paymethod_trc20_" + kind + "_" + str(ref_id) + "_" + str(price))],
        [InlineKeyboardButton("⭐ Telegram Stars (Auto)", callback_data="paymethod_stars_" + kind + "_" + str(ref_id) + "_" + str(price))],
        [InlineKeyboardButton("❌ Cancel", callback_data="restart")],
    ])

async def pay_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("_")
    kind = parts[1]
    ref = int(parts[2])
    await q.edit_message_text("💳 Pay 10 AED to Unlock Contact\n\nChoose payment method:", reply_markup=pay_kb(kind, ref, PRICE_CONTACT), parse_mode="Markdown")
    return PAY_METHOD

async def pin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("_")
    kind = "pin_" + parts[1]
    ref = int(parts[2])
    await q.edit_message_text("📌 Pin This Post - 25 AED (24h)\n\nYour post will stay on top of @dubairentonly for 24 hours, then auto-unpin.\n\nChoose payment method:", reply_markup=pay_kb(kind, ref, PRICE_PIN), parse_mode="Markdown")
    return PAY_METHOD

async def pay_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("_")
    price = int(parts[-1])
    ref = int(parts[-2])
    kind = "_".join(parts[2:-2])
    method = parts[1]
    context.user_data["pay_kind"] = kind
    context.user_data["pay_ref"] = ref
    context.user_data["pay_method"] = method
    context.user_data["pay_price"] = price
    if method == "stars":
        await q.edit_message_text("⭐ Telegram Stars - " + str(price) + " AED\n\nStars payment is automatic. Tap Confirm.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Confirm Stars Paid", callback_data="stars_done_" + kind + "_" + str(ref) + "_" + str(price))]]), parse_mode="Markdown")
        return PAY_METHOD
    if method == "binance":
        txt = "🟡 Binance Pay - " + str(price) + " AED\n\nSend " + str(price) + " AED equivalent to Binance ID:\n" + BINANCE_ID + "\n\nThen send screenshot here."
    else:
        txt = "🔵 TRC20 USDT - " + str(price) + " AED\n\nSend " + str(price) + " AED equivalent USDT to:\n" + TRC20 + "\n\nThen send screenshot here."
    await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📸 I Sent - Upload Screenshot", callback_data="upload_shot")]]), parse_mode="Markdown")
    return PAY_SCREENSHOT

async def upload_shot_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("📸 Please send the payment screenshot now as a photo.")
    return PAY_SCREENSHOT

async def pay_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("Please send screenshot as a photo.")
        return PAY_SCREENSHOT
    uid = update.effective_user.id
    kind = context.user_data.get("pay_kind")
    ref = context.user_data.get("pay_ref")
    price = context.user_data.get("pay_price")
    pid = len(pending)
    new_pending = {}
    new_pending["kind"] = kind
    new_pending["ref"] = ref
    new_pending["buyer"] = uid
    new_pending["price"] = price
    pending[pid] = new_pending
    if ADMIN_ID:
        try:
            cap = "🧾 New Payment\nBuyer: " + str(uid) + "\nKind: " + str(kind) + " Ref: " + str(ref) + "\nAmount: " + str(price) + " AED\nMethod: " + str(context.user_data.get("pay_method"))
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Approve", callback_data="admin_approve_" + str(pid))],
                [InlineKeyboardButton("❌ Reject", callback_data="admin_reject_" + str(pid))],
            ])
            await context.bot.send_photo(int(ADMIN_ID), update.message.photo[-1].file_id, caption=cap, reply_markup=kb, parse_mode="Markdown")
        except Exception as e:
            print("Admin forward failed", e)
    await update.message.reply_text("⏳ PENDING - Waiting for Admin Approval\n\nScreenshot sent to admin. You will get it as soon as admin approves.", parse_mode="Markdown")
    return ROLE

async def stars_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("_")
    price = int(parts[-1])
    ref = int(parts[-2])
    kind = "_".join(parts[2:-2])
    await deliver_payment(q, context, kind, ref, price)
    return ROLE

async def admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("_")
    action = parts[1]
    pid = int(parts[2])
    p = pending.get(pid)
    if not p:
        await q.edit_message_text("Already handled.")
        return ROLE
    buyer = p["buyer"]
    kind = p["kind"]
    ref = p["ref"]
    price = p["price"]
    if action == "approve":
        await q.edit_message_text("✅ Approved " + str(pid) + ".")
        await deliver_to_buyer(context, buyer, kind, ref, price)
    else:
        await q.edit_message_text("❌ Rejected " + str(pid) + ".")
        await context.bot.send_message(buyer, "❌ Payment Rejected - Payment Not Received\n\nAdmin did not find your payment. Please try again.", parse_mode="Markdown")
    pending.pop(pid, None)
    return ROLE

def get_contact_for(kind, ref):
    if kind == "lead":
        return leads[ref]["contact"]
    if kind == "agent":
        lead = leads[ref]
        post = agent_posts[lead["agent_post_id"]]
        return post.get("agent_contact", "No contact")
    if kind == "wanted":
        return tenant_posts[ref]["contact"]
    return "Not found"

async def deliver_to_buyer(context, buyer, kind, ref, price):
    if kind.startswith("pin_"):
        post_kind = kind.split("_")[1]
        posts = agent_posts if post_kind == "agent" else tenant_posts
        if ref < len(posts):
            msg_id = posts[ref].get("channel_msg_id")
            try:
                if msg_id:
                    await context.bot.pin_chat_message(CHANNEL_ID, msg_id, disable_notification=True)
                    schedule_unpin(context.application, msg_id)
                    await context.bot.send_message(buyer, "✅ Payment Approved!\n\n📌 Your post is now PINNED on top of @dubairentonly for 24 hours.\nAfter 24h it will be unpinned automatically.", parse_mode="Markdown")
                else:
                    await context.bot.send_message(buyer, "✅ Payment Approved, but post message not found to pin. Contact admin @Givon5", parse_mode="Markdown")
            except Exception as e:
                await context.bot.send_message(buyer, "✅ Payment Approved, but pin failed (bot must be admin with Pin permission): " + str(e), parse_mode="Markdown")
        return
    contact = get_contact_for(kind, ref)
    await context.bot.send_message(buyer, "✅ Payment Approved!\n\nHere is the contact:\n" + str(contact) + "\n\nGood luck!", parse_mode="Markdown")

async def deliver_payment(q, context, kind, ref, price):
    if kind.startswith("pin_"):
        post_kind = kind.split("_")[1]
        posts = agent_posts if post_kind == "agent" else tenant_posts
        if ref < len(posts):
            msg_id = posts[ref].get("channel_msg_id")
            try:
                if msg_id:
                    await context.bot.pin_chat_message(CHANNEL_ID, msg_id, disable_notification=True)
                    schedule_unpin(context.application, msg_id)
                    await q.edit_message_text("✅ Payment Confirmed (Stars)!\n\n📌 Your post is now PINNED for 24 hours.\nAfter 24h it will be unpinned automatically.", reply_markup=main_kb(), parse_mode="Markdown")
                else:
                    await q.edit_message_text("✅ Payment Confirmed, but post not found to pin.", reply_markup=main_kb())
            except Exception as e:
                await q.edit_message_text("✅ Payment Confirmed, but pin failed - bot must be admin with Pin permission: " + str(e), reply_markup=main_kb())
        return
    contact = get_contact_for(kind, ref)
    await q.edit_message_text("✅ Payment Confirmed (Stars)!\n\nContact:\n" + str(contact) + "\n\nGood luck!", reply_markup=main_kb(), parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CallbackQueryHandler(help_handler, pattern="^help$"))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CommandHandler("unpin", unpin_cmd))
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ROLE: [
                CallbackQueryHandler(role_handler, pattern="^role_"),
                CallbackQueryHandler(restart_handler, pattern="^restart$"),
                CallbackQueryHandler(int_yes, pattern="^int_yes$"),
                CallbackQueryHandler(int_confirm, pattern="^int_confirm$"),
                CallbackQueryHandler(pay_start, pattern="^pay_(lead|agent|wanted)_"),
                CallbackQueryHandler(pin_start, pattern="^pin_(agent|tenant)_"),
                CallbackQueryHandler(pay_method, pattern="^paymethod_"),
                CallbackQueryHandler(admin_decision, pattern="^admin_"),
                CallbackQueryHandler(stars_done, pattern="^stars_done_"),
                CallbackQueryHandler(agent_confirm, pattern="^agent_confirm$"),
                CallbackQueryHandler(tenant_confirm, pattern="^tenant_confirm$"),
                CallbackQueryHandler(upload_shot_prompt, pattern="^upload_shot$"),
            ],
            A_LOC: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_loc)],
            A_RENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_rent)],
            A_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_type)],
            A_FURN: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_furn)],
            A_AVAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_avail)],
            A_PHOTOS: [MessageHandler(filters.PHOTO | filters.TEXT, a_photos)],
            A_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_desc)],
            A_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_name)],
            A_VERIFY: [MessageHandler(filters.CONTACT, a_verify)],
            A_CONTACT: [MessageHandler(filters.CONTACT, a_contact)],
            A_CONFIRM: [CallbackQueryHandler(agent_confirm, pattern="^agent_confirm$"), CallbackQueryHandler(restart_handler, pattern="^restart$")],
            T_LOC: [MessageHandler(filters.TEXT & ~filters.COMMAND, t_loc)],
            T_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, t_budget)],
            T_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, t_type)],
            T_CONTACT: [MessageHandler(filters.CONTACT, t_contact)],
            T_CONFIRM: [CallbackQueryHandler(tenant_confirm, pattern="^tenant_confirm$"), CallbackQueryHandler(restart_handler, pattern="^restart$")],
            INT_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, int_budget)],
            INT_MOVEIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, int_movein)],
            INT_CONTACT: [MessageHandler(filters.CONTACT, int_contact)],
            INT_CONFIRM: [CallbackQueryHandler(int_confirm, pattern="^int_confirm$"), CallbackQueryHandler(restart_handler, pattern="^restart$")],
            PAY_METHOD: [
                CallbackQueryHandler(pay_method, pattern="^paymethod_"),
                CallbackQueryHandler(stars_done, pattern="^stars_done_"),
                CallbackQueryHandler(upload_shot_prompt, pattern="^upload_shot$"),
                CallbackQueryHandler(restart_handler, pattern="^restart$"),
            ],
            PAY_SCREENSHOT: [MessageHandler(filters.PHOTO, pay_screenshot)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True, per_message=False,
    )
    app.add_handler(conv)
    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
