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
ADMIN_ID = os.environ.get("ADMIN_ID")  # NUMERIC ID of @Givon5 - e.g. 7123456789, NOT @Givon5
PRICE_CONTACT = 10
PRICE_PIN = 25

(ROLE, A_LOC, A_RENT, A_TYPE, A_FURN, A_AVAIL, A_PHOTOS, A_DESC, A_NAME,
 A_VERIFY, A_CONTACT, A_CONFIRM,
 T_LOC, T_BUDGET, T_TYPE, T_CONTACT, T_CONFIRM,
 INT_BUDGET, INT_MOVEIN, INT_CONTACT, INT_CONFIRM,
 PAY_METHOD, PAY_SCREENSHOT) = range(26)

users = {}
agent_posts = []
tenant_posts = []
leads = []
pending = {}
interested = set()

def help_text():
    return ("❓ *HELP*\n\n"
            "🕵️ *Agent:* Post PROPERTY free. Verification + Contact only on 1st post, at the END.\n\n"
            "🏠 *Tenant:* Post WANTED free. Contact at the END via Share button. Never posted publicly.\n\n"
            "💰 *Contacts:* 10 AED per contact. Agent pays to get Tenant contact. Tenant can pay 10 AED to get Agent contact.\n\n"
            "📌 *Pinned Post:* 25 AED - Pinned on top of @dubairentonly for 24 hours, then auto-unpinned.\n\n"
            "📢 Channel: @dubairentonly\nAdmin: @Givon5")

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
        [InlineKeyboardButton(f"📌 Pin This Post - {PRICE_PIN} AED (24h)", callback_data=f"pin_{post_kind}_{post_id}")],
        [InlineKeyboardButton("🔄 Main Menu", callback_data="restart")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])

# ---------- PIN 24H + ADMIN COMMANDS ----------
async def unpin_after_24h(context: ContextTypes.DEFAULT_TYPE):
    msg_id = context.job.data
    try:
        await context.bot.unpin_chat_message(CHANNEL_ID, msg_id)
        print(f"Auto-unpinned {msg_id} after 24h")
    except Exception as e:
        print("Auto-unpin failed:", e)

def schedule_unpin(app, msg_id):
    if app.job_queue:
        app.job_queue.run_once(unpin_after_24h, when=86400, data=msg_id, name=f"unpin_{msg_id}")

async def unpin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Only Admin can use this
    uid = str(update.effective_user.id)
    if ADMIN_ID and uid != str(ADMIN_ID):
        await update.message.reply_text("❌ Only admin can unpin.")
        return
    # /unpin 123  (message id) or /unpin all
    args = context.args or []
    try:
        if args and args[0].lower() == "all":
            await context.bot.unpin_all_chat_messages(CHANNEL_ID)
            await update.message.reply_text("✅ All pinned posts unpinned.")
            return
        if args:
            msg_id = int(args[0])
            await context.bot.unpin_chat_message(CHANNEL_ID, msg_id)
            await update.message.reply_text(f"✅ Unpinned message {msg_id}.")
            return
        # No args: unpin latest pinned - try to unpin all as fallback
        await context.bot.unpin_all_chat_messages(CHANNEL_ID)
        await update.message.reply_text("✅ Unpinned. Usage: /unpin <message_id> or /unpin all")
    except Exception as e:
        await update.message.reply_text(f"Pin failed - is bot admin with Pin permission? Error: {e}\nUsage: /unpin <message_id> or /unpin all")

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your ID: {update.effective_user.id}\nUsername: @{update.effective_user.username or 'none'}\n\nIf you are admin, put this number in Render as ADMIN_ID.")

# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if args and args[0].startswith("interested_"):
        return await show_agent_post_in_dm(update, context, int(args[0].split("_")[1]))
    if args and args[0].startswith("wanted_"):
        return await show_wanted_in_dm(update, context, int(args[0].split("_")[1]))
    await update.message.reply_text("👋 *Welcome to Dubai Rentals!*\n\nPosting is FREE. Contacts 10 AED. Pinned Post 25 AED (24h).\n\nWho are you?", reply_markup=main_kb(), parse_mode="Markdown")
    return ROLE

async def restart_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data.clear()
    await q.edit_message_text("🔄 *Main Menu*\nWho are you?", reply_markup=main_kb(), parse_mode="Markdown")
    return ROLE

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(help_text(), reply_markup=main_kb(), parse_mode="Markdown")
    return ROLE

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(help_text(), reply_markup=main_kb(), parse_mode="Markdown")
    return ROLE

async def role_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "role_agent":
        context.user_data["role"] = "agent"; context.user_data["draft"] = {}
        await q.edit_message_text("🕵️ *AGENT - PROPERTY Post*\n\nStep 1: Location? (e.g. Marina, Downtown)", parse_mode="Markdown")
        return A_LOC
    else:
        context.user_data["role"] = "tenant"; context.user_data["draft"] = {}
        await q.edit_message_text("🏠 *TENANT - WANTED Post*\n\nStep 1: Location you want? (e.g. JLT, Marina)", parse_mode="Markdown")
        return T_LOC

# ---------- AGENT ----------
async def a_loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["draft"]["location"] = update.message.text
    await update.message.reply_text("Step 2: Rent? (e.g. 6000 AED/month)"); return A_RENT
async def a_rent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["draft"]["rent"] = update.message.text
    await update.message.reply_text("Step 3: Type? (Studio, 1BR, 2BR, Villa)"); return A_TYPE
async def a_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["draft"]["type"] = update.message.text
    await update.message.reply_text("Step 4: Furnished / Unfurnished / Semi?"); return A_FURN
async def a_furn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["draft"]["furn"] = update.message.text
    await update.message.reply_text("Step 5: Available From? (e.g. 1 Dec, Immediately)"); return A_AVAIL
async def a_avail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["draft"]["avail"] = update.message.text
    await update.message.reply_text("Step 6: Send photos (or type 'skip')"); return A_PHOTOS
async def a_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data["draft"]
    if update.message.photo:
        d.setdefault("photos", []).append(update.message.photo[-1].file_id)
        await update.message.reply_text("Photo saved. Send another or type 'done'"); return A_PHOTOS
    if update.message.text and update.message.text.lower() in ["skip", "done"]:
        await update.message.reply_text("Step 7: Short description + any other things tenants need?"); return A_DESC
    await update.message.reply_text("Send photo or type 'done'"); return A_PHOTOS
async def a_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["draft"]["desc"] = update.message.text
    await update.message.reply_text("Step 8: Agent / Landlord Name?"); return A_NAME
async def a_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["draft"]["name"] = update.message.text
    uid = update.effective_user.id
    if not users.get(uid, {}).get("verified"):
        await update.message.reply_text("🔐 *Final Step - Verification (only this first time)*\n\nPlease share your phone. You will NOT be asked again.", reply_markup=share_phone_kb(), parse_mode="Markdown")
        return A_VERIFY
    return await a_check_contact(update, context)
async def a_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not update.message.contact:
        await update.message.reply_text("Please tap Share My Contact button."); return A_VERIFY
    users.setdefault(uid, {})["verified"] = True
    users[uid]["verify_phone"] = update.message.contact.phone_number
    await update.message.reply_text("✅ Verified! You won't need this again.", reply_markup=ReplyKeyboardRemove())
    return await a_check_contact(update, context)
async def a_check_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if users.get(uid, {}).get("agent_contact"):
        context.user_data["draft"]["agent_contact"] = users[uid]["agent_contact"]
        return await a_preview(update, context)
    await update.message.reply_text("📱 *Final Step - Your Contact*\n\nThis contact will NEVER be in the channel post. It will only be given to interested tenants who pay 10 AED.\n\nPlease share your contact:", reply_markup=share_phone_kb(), parse_mode="Markdown")
    return A_CONTACT
async def a_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not update.message.contact:
        await update.message.reply_text("Please tap Share My Contact button."); return A_CONTACT
    users.setdefault(uid, {})["agent_contact"] = update.message.contact.phone_number
    context.user_data["draft"]["agent_contact"] = update.message.contact.phone_number
    await update.message.reply_text("✅ Contact saved (private).", reply_markup=ReplyKeyboardRemove())
    return await a_preview(update, context)
async def a_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data["draft"]
    txt = f"👀 *PREVIEW - PROPERTY*\n\n📍 {d.get('location')}\n💰 {d.get('rent')}\n🏡 {d.get('type')} | {d.get('furn')}\n📅 Available: {d.get('avail')}\n👤 {d.get('name')}\n📝 {d.get('desc')}\n\n⚠️ No contact will be shown in channel.\n\nPost this?"
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
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    d = context.user_data.get("draft", {})
    pid = len(agent_posts)
    post = {**d, "id": pid, "owner": uid, "channel_msg_id": None}
    agent_posts.append(post)
    caption = f"🏠 *PROPERTY FOR RENT*\n\n📍 {d.get('location')}\n💰 Rent: {d.get('rent')}\n🏡 {d.get('type')} | {d.get('furn')}\n📅 Available: {d.get('avail')}\n👤 Agent: {d.get('name')}\n📝 {d.get('desc')}\n\n👇 Tap to show interest"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 I'm Interested", url=f"{BOT_LINK}?start=interested_{pid}")],
        [InlineKeyboardButton("🔗 Share", switch_inline_query=f"Property in {d.get('location')} - {d.get('rent')}")],
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
    await q.edit_message_text("✅ *Posted to @dubairentonly!*\nNo contact was posted publicly.\n\nWant to pin it on top for 25 AED (24h)?", reply_markup=pin_kb("agent", pid), parse_mode="Markdown")
    context.user_data.clear()
    return ROLE

# ---------- TENANT WANTED ----------
async def t_loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["draft"]["location"] = update.message.text
    await update.message.reply_text("Step 2: Budget? (e.g. 5000 AED/month)"); return T_BUDGET
async def t_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["draft"]["budget"] = update.message.text
    await update.message.reply_text("Step 3: Type needed? (Studio, 1BR, 2BR, Villa)"); return T_TYPE
async def t_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["draft"]["type"] = update.message.text
    await update.message.reply_text("🔒 *Last Step - Your Contact*\n\nYour contact is SAFE. It will NEVER be posted publicly. It will only be given to agents who pay 10 AED to contact you.\n\nPlease share your contact:", reply_markup=share_phone_kb(), parse_mode="Markdown")
    return T_CONTACT
async def t_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.contact:
        await update.message.reply_text("Please tap Share My Contact button to avoid fake numbers."); return T_CONTACT
    context.user_data["draft"]["contact"] = update.message.contact.phone_number
    await update.message.reply_text("✅ Contact saved (private).", reply_markup=ReplyKeyboardRemove())
    d = context.user_data["draft"]
    txt = f"👀 *PREVIEW - WANTED*\n\n📍 Location: {d.get('location')}\n💰 Budget: {d.get('budget')}\n🏡 Type: {d.get('type')}\n\n⚠️ No contact will be shown in channel.\n\nPost this?"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, POST", callback_data="tenant_confirm")],
        [InlineKeyboardButton("❌ Cancel", callback_data="restart")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])
    await update.message.reply_text(txt, reply_markup=kb, parse_mode="Markdown")
    return T_CONFIRM
async def tenant_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    d = context.user_data.get("draft", {})
    pid = len(tenant_posts)
    post = {**d, "id": pid, "owner": uid, "channel_msg_id": None}
    tenant_posts.append(post)
    caption = f"🔍 *TENANT LOOKING FOR RENT*\n\n📍 Wanted: {d.get('location')}\n💰 Budget: {d.get('budget')}\n🏡 Type: {d.get('type')}\n\n👇 Agents: Tap to get Tenant contact (10 AED)"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Get Tenant Contact - 10 AED", url=f"{BOT_LINK}?start=wanted_{pid}")],
        [InlineKeyboardButton("🔗 Share", switch_inline_query=f"Wanted in {d.get('location')} - {d.get('budget')}")],
        [InlineKeyboardButton("📢 Channel", url=CHANNEL_LINK)],
    ])
    try:
        msg = await context.bot.send_message(CHANNEL_ID, caption, reply_markup=kb, parse_mode="Markdown")
        post["channel_msg_id"] = msg.message_id
    except Exception as e:
        print("Channel post failed", e)
    await q.edit_message_text("✅ *Posted to @dubairentonly!*\nNo contact was posted publicly.\n\nWant to pin it on top for 25 AED (24h)?", reply_markup=pin_kb("tenant", pid), parse_mode="Markdown")
    context.user_data.clear()
    return ROLE

# ---------- INTERESTED ----------
async def show_agent_post_in_dm(update: Update, context: ContextTypes.DEFAULT_TYPE, pid):
    if pid >= len(agent_posts):
        await update.message.reply_text("Post not found.", reply_markup=main_kb()); return ROLE
    p = agent_posts[pid]
    context.user_data["interested_pid"] = pid
    txt = f"🏠 *PROPERTY*\n\n📍 {p.get('location')}\n💰 {p.get('rent')}\n🏡 {p.get('type')} | {p.get('furn')}\n📅 {p.get('avail')}\n👤 {p.get('name')}\n📝 {p.get('desc')}\n\nAre you interested?"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, I'm Interested", callback_data="int_yes")],
        [InlineKeyboardButton("❌ No", callback_data="restart")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ])
    await update.message.reply_text(txt, reply_markup=kb, parse_mode="Markdown")
    return ROLE
async def int_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id; pid = context.user_data.get("interested_pid")
    if (uid, pid) in interested:
        await q.edit_message_text("You already sent interest for this property. Agent will contact you.", reply_markup=main_kb()); return ROLE
    await q.edit_message_text("✅ *Interested!*\n\nWhat is your Budget?", parse_mode="Markdown")
    return INT_BUDGET
async def int_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lead_budget"] = update.message.text
    await update.message.reply_text("Move-in Date? (e.g. 1 Dec)"); return INT_MOVEIN
async def int_movein(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lead_movein"] = update.message.text
    await update.message.reply_text("🔒 *Your Contact*\n\nGive your number so Agent can contact you. It will NOT be posted publicly. It will only be shown to this Agent if he pays 10 AED.", reply_markup=share_phone_kb(), parse_mode="Markdown")
    return INT_CONTACT
async def int_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.contact:
        await update.message.reply_text("Please tap Share My Contact button."); return INT_CONTACT
    context.user_data["lead_contact"] = update.message.contact.phone_number
    await update.message.reply_text("✅ Contact saved.", reply_markup=ReplyKeyboardRemove())
    pid = context.user_data.get("interested_pid"); p = agent_posts[pid]
    txt = f"👀 *CONFIRM - Send to Agent?*\n\nProperty: {p.get('location')} - {p.get('rent')}\n💰 Your Budget: {context.user_data.get('lead_budget')}\n📅 Move-in: {context.user_data.get('lead_movein')}\n📱 Your Contact: {context.user_data.get('lead_contact')} (private, only Agent sees after paying)\n\nSend?"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Send to Agent", callback_data="int_confirm")],
        [InlineKeyboardButton("❌ Cancel", callback_data="restart")],
    ])
    await update.message.reply_text(txt, reply_markup=kb, parse_mode="Markdown")
    return INT_CONFIRM
async def int_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id; pid = context.user_data.get("interested_pid"); p = agent_posts[pid]
    interested.add((uid, pid))
    lead_id = len(leads)
    leads.append({"id": lead_id, "agent_post_id": pid, "tenant_id": uid, "agent_id": p["owner"],
                  "budget": context.user_data
