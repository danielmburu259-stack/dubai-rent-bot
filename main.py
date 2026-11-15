print("STARTING...", flush=True)
print("TOKEN LEN:", len(BOT_TOKEN or ""), flush=True)
import os
import threading
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        def log_message(self, *a):
            pass
    HTTPServer(("0.0.0.0", port), H).serve_forever()

threading.Thread(
    target=keep_alive,
    daemon=True
).start()

from telegram import Update
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import KeyboardButton
from telegram import ReplyKeyboardMarkup
from telegram import ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler
from telegram.ext import CallbackQueryHandler
from telegram.ext import ContextTypes
from telegram.ext import filters
from telegram.ext import ConversationHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = -1004386364968
CHANNEL_LINK = "https://t.me/dubairentonly"
BOT_LINK = "https://t.me/Dubairentalsbot"
BINANCE_ID = os.environ.get("BINANCE_ID", "Ask admin")
TRC20 = os.environ.get("TRC20_ADDRESS", "Ask admin")
ADMIN_ID = os.environ.get("ADMIN_ID")
PRICE_CONTACT = 10
PRICE_PIN = 25

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
    t1 = "HELP\n\n"
    t2 = "Agent: Post PROPERTY free.\n"
    t3 = "Verification + Contact on 1st post only.\n\n"
    t4 = "Tenant: Post WANTED free.\n"
    t5 = "Contact at END. Never public.\n\n"
    t6 = "Contacts: 10 AED each.\n"
    t7 = "Pin: 25 AED for 24h.\n\n"
    t8 = "Channel: @dubairentonly\n"
    t9 = "Admin: @Givon5"
    return t1 + t2 + t3 + t4 + t5 + t6 + t7 + t8 + t9

def main_kb():
    b1 = InlineKeyboardButton(
        "Agent - Post PROPERTY",
        callback_data="role_agent")
    b2 = InlineKeyboardButton(
        "Tenant - Post WANTED",
        callback_data="role_tenant")
    b3 = InlineKeyboardButton(
        "View Channel", url=CHANNEL_LINK)
    b4 = InlineKeyboardButton(
        "Help", callback_data="help")
    b5 = InlineKeyboardButton(
        "Main Menu", callback_data="restart")
    return InlineKeyboardMarkup([
        [b1], [b2], [b3], [b4], [b5]
    ])

def share_phone_kb():
    b = KeyboardButton(
        "Share My Contact",
        request_contact=True)
    return ReplyKeyboardMarkup(
        [[b]],
        one_time_keyboard=True,
        resize_keyboard=True)

def pin_kb(kind, pid):
    cb = "pin_" + kind + "_" + str(pid)
    b1 = InlineKeyboardButton(
        "Pin This Post - 25 AED (24h)",
        callback_data=cb)
    b2 = InlineKeyboardButton(
        "Main Menu", callback_data="restart")
    b3 = InlineKeyboardButton(
        "Help", callback_data="help")
    return InlineKeyboardMarkup([[b1], [b2], [b3]])

async def unpin_after_24h(context):
    mid = context.job.data
    try:
        await context.bot.unpin_chat_message(
            CHANNEL_ID, mid)
    except Exception as e:
        print("Unpin fail", e)

def schedule_unpin(app, mid):
    if app.job_queue:
        app.job_queue.run_once(
            unpin_after_24h,
            when=86400,
            data=mid,
            name="unpin_" + str(mid))

async def unpin_cmd(update, context):
    uid = str(update.effective_user.id)
    if ADMIN_ID and uid != str(ADMIN_ID):
        await update.message.reply_text(
            "Only admin can unpin.")
        return
    args = context.args or []
    try:
        if args and args[0].lower() == "all":
            await context.bot.unpin_all_chat_messages(
                CHANNEL_ID)
            await update.message.reply_text(
                "All unpinned.")
            return
        if args:
            mid = int(args[0])
            await context.bot.unpin_chat_message(
                CHANNEL_ID, mid)
            await update.message.reply_text("Unpinned.")
            return
        await context.bot.unpin_all_chat_messages(
            CHANNEL_ID)
        await update.message.reply_text("Unpinned.")
    except Exception as e:
        await update.message.reply_text(
            "Pin fail: " + str(e))

async def id_cmd(update, context):
    txt = "Your ID: " + str(
        update.effective_user.id)
    await update.message.reply_text(txt)

async def start(update, context):
    args = context.args or []
    if args and args[0].startswith("interested_"):
        pid = int(args[0].split("_")[1])
        return await show_agent_post(update, context, pid)
    if args and args[0].startswith("wanted_"):
        pid = int(args[0].split("_")[1])
        return await show_wanted(update, context, pid)
    txt = "Welcome to Dubai Rentals!\n"
    txt += "Posting FREE. Contacts 10 AED.\n"
    txt += "Pin 25 AED (24h).\n\nWho are you?"
    await update.message.reply_text(
        txt, reply_markup=main_kb(), parse_mode="Markdown")
    return ROLE

async def restart_handler(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data.clear()
    await q.edit_message_text(
        "Main Menu\nWho are you?",
        reply_markup=main_kb(),
        parse_mode="Markdown")
    return ROLE

async def help_handler(update, context):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        help_text(),
        reply_markup=main_kb(),
        parse_mode="Markdown")
    return ROLE

async def help_cmd(update, context):
    await update.message.reply_text(
        help_text(),
        reply_markup=main_kb(),
        parse_mode="Markdown")
    return ROLE

async def role_handler(update, context):
    q = update.callback_query
    await q.answer()
    if q.data == "role_agent":
        context.user_data["role"] = "agent"
        context.user_data["draft"] = {}
        await q.edit_message_text(
            "AGENT - PROPERTY\n\nStep 1: Location?",
            parse_mode="Markdown")
        return A_LOC
    context.user_data["role"] = "tenant"
    context.user_data["draft"] = {}
    await q.edit_message_text(
        "TENANT - WANTED\n\nStep 1: Location?",
        parse_mode="Markdown")
    return T_LOC

async def a_loc(update, context):
    context.user_data["draft"]["location"] = \
        update.message.text
    await update.message.reply_text(
        "Step 2: Rent? (e.g. 6000 AED/month)")
    return A_RENT

async def a_rent(update, context):
    context.user_data["draft"]["rent"] = \
        update.message.text
    await update.message.reply_text(
        "Step 3: Type? (Studio, 1BR, 2BR, Villa)")
    return A_TYPE

async def a_type(update, context):
    context.user_data["draft"]["type"] = \
        update.message.text
    await update.message.reply_text(
        "Step 4: Furnished / Unfurnished?")
    return A_FURN

async def a_furn(update, context):
    context.user_data["draft"]["furn"] = \
        update.message.text
    await update.message.reply_text(
        "Step 5: Available From?")
    return A_AVAIL

async def a_avail(update, context):
    context.user_data["draft"]["avail"] = \
        update.message.text
    await update.message.reply_text(
        "Step 6: Send photos (or type skip)")
    return A_PHOTOS

async def a_photos(update, context):
    d = context.user_data["draft"]
    if update.message.photo:
        if "photos" not in d:
            d["photos"] = []
        d["photos"].append(
            update.message.photo[-1].file_id)
        await update.message.reply_text(
            "Photo saved. Send more or type done")
        return A_PHOTOS
    txt = update.message.text or ""
    if txt.lower() in ["skip", "done"]:
        await update.message.reply_text(
            "Step 7: Short description?")
        return A_DESC
    await update.message.reply_text(
        "Send photo or type done")
    return A_PHOTOS

async def a_desc(update, context):
    context.user_data["draft"]["desc"] = \
        update.message.text
    await update.message.reply_text(
        "Step 8: Agent / Landlord Name?")
    return A_NAME

async def a_name(update, context):
    context.user_data["draft"]["name"] = \
        update.message.text
    uid = update.effective_user.id
    if not users.get(uid, {}).get("verified"):
        await update.message.reply_text(
            "Final Step - Verification (1st time only)\n"
            "Please share your phone.",
            reply_markup=share_phone_kb(),
            parse_mode="Markdown")
        return A_VERIFY
    return await a_check_contact(update, context)

async def a_verify(update, context):
    uid = update.effective_user.id
    if not update.message.contact:
        await update.message.reply_text(
            "Tap Share My Contact button.")
        return A_VERIFY
    if uid not in users:
        users[uid] = {}
    users[uid]["verified"] = True
    users[uid]["verify_phone"] = \
        update.message.contact.phone_number
    await update.message.reply_text(
        "Verified! No need again.",
        reply_markup=ReplyKeyboardRemove())
    return await a_check_contact(update, context)

async def a_check_contact(update, context):
    uid = update.effective_user.id
    if users.get(uid, {}).get("agent_contact"):
        context.user_data["draft"]["agent_contact"] = \
            users[uid]["agent_contact"]
        return await a_preview(update, context)
    await update.message.reply_text(
        "Final Step - Your Contact\n"
        "Never in channel post. Only for\n"
        "tenants who pay 10 AED.\n"
        "Please share contact:",
        reply_markup=share_phone_kb(),
        parse_mode="Markdown")
    return A_CONTACT

async def a_contact(update, context):
    uid = update.effective_user.id
    if not update.message.contact:
        await update.message.reply_text(
            "Tap Share My Contact button.")
        return A_CONTACT
    if uid not in users:
        users[uid] = {}
    users[uid]["agent_contact"] = \
        update.message.contact.phone_number
    context.user_data["draft"]["agent_contact"] = \
        update.message.contact.phone_number
    await update.message.reply_text(
        "Contact saved (private).",
        reply_markup=ReplyKeyboardRemove())
    return await a_preview(update, context)

async def a_preview(update, context):
    d = context.user_data["draft"]
    txt = "PREVIEW - PROPERTY\n\n"
    txt += "Location: " + str(d.get("location")) + "\n"
    txt += "Rent: " + str(d.get("rent")) + "\n"
    txt += "Type: " + str(d.get("type")) + "\n"
    txt += "Furn: " + str(d.get("furn")) + "\n"
    txt += "Available: " + str(d.get("avail")) + "\n"
    txt += "Agent: " + str(d.get("name")) + "\n"
    txt += "Desc: " + str(d.get("desc")) + "\n\n"
    txt += "No contact in channel.\n\nPost this?"
    b1 = InlineKeyboardButton(
        "Yes, POST", callback_data="agent_confirm")
    b2 = InlineKeyboardButton(
        "Cancel", callback_data="restart")
    b3 = InlineKeyboardButton(
        "Help", callback_data="help")
    kb = InlineKeyboardMarkup([[b1], [b2], [b3]])
    if update.callback_query:
        await update.callback_query.edit_message_text(
            txt, reply_markup=kb, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            txt, reply_markup=kb, parse_mode="Markdown")
    return A_CONFIRM

async def agent_confirm(update, context):
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
    cap = "PROPERTY FOR RENT\n\n"
    cap += "Location: " + str(d.get("location")) + "\n"
    cap += "Rent: " + str(d.get("rent")) + "\n"
    cap += "Type: " + str(d.get("type")) + "\n"
    cap += "Furn: " + str(d.get("furn")) + "\n"
    cap += "Available: " + str(d.get("avail")) + "\n"
    cap += "Agent: " + str(d.get("name")) + "\n"
    cap += "Desc: " + str(d.get("desc")) + "\n\n"
    cap += "Tap to show interest"
    url1 = BOT_LINK + "?start=interested_" + str(pid)
    b1 = InlineKeyboardButton(
        "I am Interested", url=url1)
    b2 = InlineKeyboardButton(
        "Share",
        switch_inline_query="Property in " + str(
            d.get("location")))
    b3 = InlineKeyboardButton(
        "Channel", url=CHANNEL_LINK)
    kb = InlineKeyboardMarkup([[b1], [b2], [b3]])
    try:
        if d.get("photos"):
            msg = await context.bot.send_photo(
                CHANNEL_ID, d["photos"][0],
                caption=cap, reply_markup=kb,
                parse_mode="Markdown")
        else:
            msg = await context.bot.send_message(
                CHANNEL_ID, cap, reply_markup=kb,
                parse_mode="Markdown")
        post["channel_msg_id"] = msg.message_id
    except Exception as e:
        print("Channel post fail", e)
    await q.edit_message_text(
        "Posted to @dubairentonly!\n"
        "No contact posted publicly.\n\n"
        "Want to pin it for 25 AED (24h)?",
        reply_markup=pin_kb("agent", pid),
        parse_mode="Markdown")
    context.user_data.clear()
    return ROLE

async def t_loc(update, context):
    context.user_data["draft"]["location"] = \
        update.message.text
    await update.message.reply_text(
        "Step 2: Budget? (e.g. 5000 AED/month)")
    return T_BUDGET

async def t_budget(update, context):
    context.user_data["draft"]["budget"] = \
        update.message.text
    await update.message.reply_text(
        "Step 3: Type needed? (Studio, 1BR, Villa)")
    return T_TYPE

async def t_type(update, context):
    context.user_data["draft"]["type"] = \
        update.message.text
    await update.message.reply_text(
        "Last Step - Your Contact\n"
        "SAFE. Never posted publicly.\n"
        "Only for agents who pay 10 AED.\n"
        "Please share contact:",
        reply_markup=share_phone_kb(),
        parse_mode="Markdown")
    return T_CONTACT

async def t_contact(update, context):
    if not update.message.contact:
        await update.message.reply_text(
            "Tap Share My Contact button.")
        return T_CONTACT
    context.user_data["draft"]["contact"] = \
        update.message.contact.phone_number
    await update.message.reply_text(
        "Contact saved (private).",
        reply_markup=ReplyKeyboardRemove())
    d = context.user_data["draft"]
    txt = "PREVIEW - WANTED\n\n"
    txt += "Location: " + str(d.get("location")) + "\n"
    txt += "Budget: " + str(d.get("budget")) + "\n"
    txt += "Type: " + str(d.get("type")) + "\n\n"
    txt += "No contact in channel.\n\nPost this?"
    b1 = InlineKeyboardButton(
        "Yes, POST", callback_data="tenant_confirm")
    b2 = InlineKeyboardButton(
        "Cancel", callback_data="restart")
    b3 = InlineKeyboardButton(
        "Help", callback_data="help")
    kb = InlineKeyboardMarkup([[b1], [b2], [b3]])
    await update.message.reply_text(
        txt, reply_markup=kb, parse_mode="Markdown")
    return T_CONFIRM

async def tenant_confirm(update, context):
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
    cap = "TENANT LOOKING FOR RENT\n\n"
    cap += "Wanted: " + str(d.get("location")) + "\n"
    cap += "Budget: " + str(d.get("budget")) + "\n"
    cap += "Type: " + str(d.get("type")) + "\n\n"
    cap += "Agents: Tap to get contact (10 AED)"
    url1 = BOT_LINK + "?start=wanted_" + str(pid)
    b1 = InlineKeyboardButton(
        "Get Tenant Contact - 10 AED", url=url1)
    b2 = InlineKeyboardButton(
        "Share",
        switch_inline_query="Wanted in " + str(
            d.get("location")))
    b3 = InlineKeyboardButton(
        "Channel", url=CHANNEL_LINK)
    kb = InlineKeyboardMarkup([[b1], [b2], [b3]])
    try:
        msg = await context.bot.send_message(
            CHANNEL_ID, cap, reply_markup=kb,
            parse_mode="Markdown")
        post["channel_msg_id"] = msg.message_id
    except Exception as e:
        print("Channel post fail", e)
    await q.edit_message_text(
        "Posted to @dubairentonly!\n"
        "No contact posted publicly.\n\n"
        "Want to pin it for 25 AED (24h)?",
        reply_markup=pin_kb("tenant", pid),
        parse_mode="Markdown")
    context.user_data.clear()
    return ROLE

async def show_agent_post(update, context, pid):
    if pid >= len(agent_posts):
        await update.message.reply_text(
            "Post not found.", reply_markup=main_kb())
        return ROLE
    p = agent_posts[pid]
    context.user_data["interested_pid"] = pid
    txt = "PROPERTY\n\n"
    txt += "Location: " + str(p.get("location")) + "\n"
    txt += "Rent: " + str(p.get("rent")) + "\n"
    txt += "Type: " + str(p.get("type")) + "\n"
    txt += "Furn: " + str(p.get("furn")) + "\n"
    txt += "Available: " + str(p.get("avail")) + "\n"
    txt += "Agent: " + str(p.get("name")) + "\n"
    txt += "Desc: " + str(p.get("desc")) + "\n\n"
    txt += "Are you interested?"
    b1 = InlineKeyboardButton(
        "Yes, I am Interested",
        callback_data="int_yes")
    b2 = InlineKeyboardButton(
        "No", callback_data="restart")
    b3 = InlineKeyboardButton(
        "Help", callback_data="help")
    kb = InlineKeyboardMarkup([[b1], [b2], [b3]])
    await update.message.reply_text(
        txt, reply_markup=kb, parse_mode="Markdown")
    return ROLE

async def int_yes(update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    pid = context.user_data.get("interested_pid")
    if (uid, pid) in interested:
        await q.edit_message_text(
            "You already sent interest.",
            reply_markup=main_kb())
        return ROLE
    await q.edit_message_text(
        "Interested!\n\nWhat is your Budget?",
        parse_mode="Markdown")
    return INT_BUDGET

async def int_budget(update, context):
    context.user_data["lead_budget"] = \
        update.message.text
    await update.message.reply_text(
        "Move-in Date? (e.g. 1 Dec)")
    return INT_MOVEIN

async def int_movein(update, context):
    context.user_data["lead_movein"] = \
        update.message.text
    await update.message.reply_text(
        "Your Contact\n"
        "Give number so Agent can contact you.\n"
        "NOT public. Only Agent after paying 10 AED.",
        reply_markup=share_phone_kb(),
        parse_mode="Markdown")
    return INT_CONTACT

async def int_contact(update, context):
    if not update.message.contact:
        await update.message.reply_text(
            "Tap Share My Contact button.")
        return INT_CONTACT
    context.user_data["lead_contact"] = \
        update.message.contact.phone_number
    await update.message.reply_text(
        "Contact saved.",
        reply_markup=ReplyKeyboardRemove())
    pid = context.user_data.get("interested_pid")
    p = agent_posts[pid]
    txt = "CONFIRM - Send to Agent?\n\n"
    txt += "Property: " + str(p.get("location"))
    tx
