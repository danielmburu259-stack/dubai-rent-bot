import os
import sys
import re
import datetime
import threading
import traceback
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
from telegram import LabeledPrice
from telegram.ext import ApplicationBuilder
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler
from telegram.ext import CallbackQueryHandler
from telegram.ext import PreCheckoutQueryHandler
from telegram.ext import ContextTypes
from telegram.ext import filters
from telegram.ext import ConversationHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN")
print("STARTING...", flush=True)
print("TOKEN LEN:", len(BOT_TOKEN or ""), flush=True)
print("ADMIN_ID:", os.environ.get("ADMIN_ID"), flush=True)

CHANNEL_ID = -1004386364968
CHANNEL_LINK = "https://t.me/dubairentonly"
BOT_LINK = "https://t.me/Dubairentalsbot"
ADMIN_ID = os.environ.get("ADMIN_ID")
ADMIN_USERNAME = "@Givon5"
PRICE_CONTACT = 10
PRICE_PIN = 25
STARS_CONTACT = 150
STARS_PIN = 375

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
A_BACKUP = 22
T_BACKUP = 23
INT_BACKUP = 24

users = {}
agent_posts = []
tenant_posts = []
leads = []
interested = set()

DAILY_TIPS = [
 "Good morning Dubai. Take your time. The right home is worth waiting for.",
 "A calm search finds a better home than a rushed search.",
 "Prepare your documents early. When the right home appears, you will be ready.",
 "Visit a home in daylight. You will see it clearly.",
 "Ask questions. A good decision comes from clear information.",
 "Write down what matters most to you. It makes choosing easier.",
 "A good home is not only about rooms. It is about how you feel there.",
 "Be patient with your search. Good things take a little time.",
 "Keep your search organised. Save the homes you like.",
 "A short visit today can save you a long regret later.",
 "Respect makes every rental journey smoother.",
 "Think about your daily life. Choose a home that fits it.",
 "Small details matter. Check them before you decide.",
 "Stay positive. Your next home is closer than you think.",
 "A clear mind makes a clear choice.",
 "Do not rush because others are rushing. Move at your pace.",
 "Good communication avoids most problems.",
 "Be ready, be calm, be patient. The right home will come.",
 "Look beyond photos. A visit tells the full story.",
 "Your comfort matters. Choose a place where you can rest well.",
 "Plan your search. A plan saves time and stress.",
 "A new home is a new chapter. Choose it with care.",
 "Take notes during viewings. Memory fades, notes stay.",
 "Be kind to agents and landlords. Kindness returns.",
 "Focus on what you need, not only what you want.",
 "A quiet evening walk around the area tells you a lot.",
 "Trust your feeling, but also check the facts.",
 "Every search teaches you something. Keep learning.",
 "Start your day with a clear goal. It makes the search easier.",
 "Your home should support your life, not stress it.",
]

# --- ONLY THIS FUNCTION WAS CHANGED FOR THE FIX ---
def is_valid_backup(txt):
    t = (txt or "").strip()
    if not t:
        return False
    # Email - must have @ and .
    if "@" in t:
        if " " in t:
            return False
        parts = t.split("@")
        if len(parts) != 2:
            return False
        if not parts[0] or not parts[1]:
            return False
        if "." not in parts[1]:
            return False
        if parts[1].startswith(".") or parts[1].endswith("."):
            return False
        return True
    # Phone - MUST start with + and country code
    # FIX: 7667876, 501234567, 0501234567 now REJECTED
    if not t.startswith("+"):
        return False
    cleaned = t[1:].replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not cleaned.isdigit():
        return False
    # +971501234567 = 12 digits after +
    if len(cleaned) < 8 or len(cleaned) > 15:
        return False
    return True

def format_contact(primary, backup):
    txt = "1. Verified: " + str(primary)
    if backup:
        txt += "\n2. Backup: " + str(backup) + "\n"
        txt += "(Not verified, added by user)"
    return txt

def help_text():
    t1 = "HELP\n\n"
    t2 = "Agent: Post PROPERTY free.\n"
    t3 = "Verification + Contact on 1st post only.\n\n"
    t4 = "Tenant: Post WANTED free.\n"
    t5 = "Contact at END. Never public.\n\n"
    t6 = "Contacts: 10 AED (150 Stars).\n"
    t7 = "Pin: 25 AED (375 Stars) for 24h.\n\n"
    t8 = "Payment: Telegram Stars ONLY.\n"
    t9 = "Fast & automatic. No screenshot.\n"
    t10 = "Pay with Stars, get contact instantly.\n\n"
    t11 = "Backup: You can add optional 2nd\n"
    t12 = "number / email. Hidden too.\n"
    t13 = "Backup number must start with +\n"
    t14 = "e.g. +971501234567\n"
    t15 = "Backup is NOT verified by bot.\n\n"
    t16 = "Channel: @dubairentonly\n"
    t17 = "Complaints / Problem / Refund?\n"
    t18 = "Contact Admin directly: @Givon5\n"
    t19 = "Admin will reply fast."
    return t1 + t2 + t3 + t4 + t5 + t6 + t7 + t8 + t9 + t10 + t11 + t12 + t13 + t14 + t15 + t16 + t17 + t18 + t19

def main_kb():
    b1 = InlineKeyboardButton(
        "Agent - Post PROPERTY",
        callback_data="role_agent")
    b2 = InlineKeyboardButton(
        "Tenant - Post WANTED",
        callback_data="role_tenant")
    b3 = InlineKeyboardButton(
        "Help", callback_data="help")
    b4 = InlineKeyboardButton(
        "Channel", url=CHANNEL_LINK)
    return InlineKeyboardMarkup([
        [b1], [b2], [b3, b4]
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

async def daily_tip_job(context):
    day = datetime.datetime.now().day
    tip = DAILY_TIPS[day % len(DAILY_TIPS)]
    txt = "Daily Thought\n\n" + tip + "\n\n"
    txt += "Channel: @dubairentonly"
    try:
        await context.bot.send_message(
            CHANNEL_ID, txt)
    except Exception as e:
        print("Daily tip fail", e)

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

async def on_error(update, context):
    print("ERROR:", context.error, flush=True)
    try:
        traceback.print_exc()
    except Exception:
        pass

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

async def menu_cmd(update, context):
    context.user_data.clear()
    await update.message.reply_text(
        "Main Menu\nWhat do you want to do?",
        reply_markup=main_kb(),
        parse_mode="Markdown")
    return ROLE

async def start(update, context):
    args = context.args or []
    if args and args[0].startswith("interested_"):
        pid = int(args[0].split("_")[1])
        return await show_agent_post(update, context, pid)
    if args and args[0].startswith("wanted_"):
        pid = int(args[0].split("_")[1])
        return await show_wanted(update, context, pid)
    context.user_data.clear()
    txt = "Welcome to Dubai Rentals!\n"
    txt += "Posting FREE. Contacts 10 AED.\n"
    txt += "Pin 25 AED (24h).\n\nWho are you?"
    await update.message.reply_text(
        txt, reply_markup=main_kb(),
        parse_mode="Markdown")
    return ROLE

async def restart_handler(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data.clear()
    await q.edit_message_text(
        "Main Menu\nWhat do you want to do?",
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
    context.user_data.clear()
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
        context.user_data["draft"]["agent_backup"] = \
            users[uid].get("agent_backup")
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
        "Contact saved (private).\n\n"
        "Optional Backup (helps if your\n"
        "main number is virtual / not working)\n"
        "Send a 2nd number WITH + country code\n"
        "e.g. +971501234567\n"
        "OR email. Or type skip.\n\n"
        "Backup is also private. Only buyer sees it.",
        reply_markup=ReplyKeyboardRemove())
    return A_BACKUP

async def a_backup(update, context):
    uid = update.effective_user.id
    txt = (update.message.text or "").strip()
    if txt.lower() == "skip":
        context.user_data["draft"]["agent_backup"] = None
        if uid in users:
            users[uid]["agent_backup"] = None
        await update.message.reply_text(
            "No backup added. Continuing.")
        return await a_preview(update, context)
    if not is_valid_backup(txt):
        await update.message.reply_text(
            "That doesn't look like a number or email.\n"
            "Number MUST start with + and country code\n"
            "e.g. +971501234567\n"
            "or email (e.g. name@gmail.com)\n"
            "Or type skip.")
        return A_BACKUP
    context.user_data["draft"]["agent_backup"] = txt
    if uid not in users:
        users[uid] = {}
    users[uid]["agent_backup"] = txt
    await update.message.reply_text(
        "Backup saved (private).")
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
    post["agent_backup"] = d.get("agent_backup")
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
    b3 = InlineKeyboardButton(
        "Channel", url=CHANNEL_LINK)
    kb = InlineKeyboardMarkup([[b1], [b3]])
    posted = False
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
        posted = True
    except Exception as e:
        print("Channel post fail", e)
        posted = False
    if not posted:
        await q.edit_message_text(
            "Saved, but NOT posted to channel!\n"
            "Bot is NOT admin in @dubairentonly.\n"
            "Add bot as Admin, then post again.",
            reply_markup=main_kb(),
            parse_mode="Markdown")
        context.user_data.clear()
        return ROLE
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
        "Contact saved (private).\n\n"
        "Optional Backup (helps if your\n"
        "main number is virtual / not working)\n"
        "Send a 2nd number WITH + country code\n"
        "e.g. +971501234567\n"
        "OR email. Or type skip.\n\n"
        "Backup is also private.",
        reply_markup=ReplyKeyboardRemove())
    return T_BACKUP

async def t_backup(update, context):
    txt = (update.message.text or "").strip()
    if txt.lower() == "skip":
        context.user_data["draft"]["backup"] = None
        await update.message.reply_text(
            "No backup added. Continuing.")
        return await t_preview(update, context)
    if not is_valid_backup(txt):
        await update.message.reply_text(
            "That doesn't look like a number or email.\n"
            "Number MUST start with + and country code\n"
            "e.g. +971501234567\n"
            "or email (e.g. name@gmail.com)\n"
            "Or type skip.")
        return T_BACKUP
    context.user_data["draft"]["backup"] = txt
    await update.message.reply_text(
        "Backup saved (private).")
    return await t_preview(update, context)

async def t_preview(update, context):
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
    post["backup"] = d.get("backup")
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
    b3 = InlineKeyboardButton(
        "Channel", url=CHANNEL_LINK)
    kb = InlineKeyboardMarkup([[b1], [b3]])
    posted = False
    try:
        msg = await context.bot.send_message(
            CHANNEL_ID, cap, reply_markup=kb,
            parse_mode="Markdown")
        post["channel_msg_id"] = msg.message_id
        posted = True
    except Exception as e:
        print("Channel post fail", e)
        posted = False
    if not posted:
        await q.edit_message_text(
            "Saved, but NOT posted to channel!\n"
            "Bot is NOT admin in @dubairentonly.\n"
            "Add bot as Admin, then post again.",
            reply_markup=main_kb(),
            parse_mode="Markdown")
        context.user_data.clear()
        return ROLE
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
        "Contact saved.\n\n"
        "Optional Backup (helps if your\n"
        "main number is virtual / not working)\n"
        "Send a 2nd number WITH + country code\n"
        "e.g. +971501234567\n"
        "OR email. Or type skip.",
        reply_markup=ReplyKeyboardRemove())
    return INT_BACKUP

async def int_backup(update, context):
    txt = (update.message.text or "").strip()
    if txt.lower() == "skip":
        context.user_data["lead_backup"] = None
        await update.message.reply_text(
            "No backup added. Continuing.")
        return await int_preview(update, context)
    if not is_valid_backup(txt):
        await update.message.reply_text(
            "That doesn't look like a number or email.\n"
            "Number MUST start with + and country code\n"
            "e.g. +971501234567\n"
            "or email (e.g. name@gmail.com)\n"
            "Or type skip.")
        return INT_BACKUP
    context.user_data["lead_backup"] = txt
    await update.message.reply_text(
        "Backup saved (private).")
    return await int_preview(update, context)

async def int_preview(update, context):
    pid = context.user_data.get("interested_pid")
    p = agent_posts[pid]
    txt = "CONFIRM - Send to Agent?\n\n"
    txt += "Property: " + str(p.get("location"))
    txt += " - " + str(p.get("rent")) + "\n"
    txt += "Your Budget: "
    txt += str(context.user_data.get("lead_budget")) + "\n"
    txt += "Move-in: "
    txt += str(context.user_data.get("lead_movein")) + "\n"
    txt += "Your Contact: "
    txt += str(context.user_data.get("lead_contact"))
    txt += " (private)\n\nSend?"
    b1 = InlineKeyboardButton(
        "Yes, Send to Agent",
        callback_data="int_confirm")
    b2 = InlineKeyboardButton(
        "Cancel", callback_data="restart")
    kb = InlineKeyboardMarkup([[b1], [b2]])
    await update.message.reply_text(
        txt, reply_markup=kb, parse_mode="Markdown")
    return INT_CONFIRM

async def int_confirm(update, context):
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
    new_lead["budget"] = \
        context.user_data.get("lead_budget")
    new_lead["movein"] = \
        context.user_data.get("lead_movein")
    new_lead["contact"] = \
        context.user_data.get("lead_contact")
    new_lead["backup"] = \
        context.user_data.get("lead_backup")
    leads.append(new_lead)
    cb1 = "pay_lead_" + str(lead_id)
    b1 = InlineKeyboardButton(
        "Pay 10 AED to Unlock Contact",
        callback_data=cb1)
    b2 = InlineKeyboardButton(
        "Help", callback_data="help")
    agent_kb = InlineKeyboardMarkup([[b1], [b2]])
    try:
        m = "NEW INTERESTED TENANT!\n\n"
        m += "Property: " + str(p.get("location"))
        m += " - " + str(p.get("rent")) + "\n"
        m += "Tenant Budget: "
        m += str(context.user_data.get("lead_budget")) + "\n"
        m += "Move-in: "
        m += str(context.user_data.get("lead_movein")) + "\n"
        m += "Contact: HIDDEN - Pay 10 AED to unlock"
        await context.bot.send_message(
            p["owner"], m,
            reply_markup=agent_kb,
            parse_mode="Markdown")
    except Exception as e:
        print("Agent DM fail", e)
    cb2 = "pay_agent_" + str(lead_id)
    b3 = InlineKeyboardButton(
        "Get Agent Contact - 10 AED",
        callback_data=cb2)
    b4 = InlineKeyboardButton(
        "Let Agent Contact Me",
        callback_data="restart")
    b5 = InlineKeyboardButton(
        "Help", callback_data="help")
    tenant_kb = InlineKeyboardMarkup(
        [[b3], [b4], [b5]])
    await q.edit_message_text(
        "Sent to Agent!\n"
        "Agent got Budget + Move-in,\n"
        "but NOT your contact yet.\n"
        "He must pay 10 AED to see it.\n\n"
        "Do you want Agent contact now?",
        reply_markup=tenant_kb,
        parse_mode="Markdown")
    return ROLE

async def show_wanted(update, context, pid):
    if pid >= len(tenant_posts):
        await update.message.reply_text(
            "Post not found.", reply_markup=main_kb())
        return ROLE
    p = tenant_posts[pid]
    context.user_data["wanted_pid"] = pid
    txt = "WANTED\n\n"
    txt += "Location: " + str(p.get("location")) + "\n"
    txt += "Budget: " + str(p.get("budget")) + "\n"
    txt += "Type: " + str(p.get("type")) + "\n\n"
    txt += "Get Tenant contact for 10 AED?"
    cb = "pay_wanted_" + str(pid)
    b1 = InlineKeyboardButton(
        "Pay 10 AED - Get Contact",
        callback_data=cb)
    b2 = InlineKeyboardButton(
        "No", callback_data="restart")
    kb = InlineKeyboardMarkup([[b1], [b2]])
    await update.message.reply_text(
        txt, reply_markup=kb, parse_mode="Markdown")
    return ROLE

def pay_kb(kind, ref_id, price):
    base3 = "paymethod_stars_" + kind
    base3 += "_" + str(ref_id) + "_" + str(price)
    if price == PRICE_PIN:
        star_txt = "Pay with Stars - 375 Stars"
    else:
        star_txt = "Pay with Stars - 150 Stars"
    b3 = InlineKeyboardButton(
        star_txt, callback_data=base3)
    b4 = InlineKeyboardButton(
        "Cancel", callback_data="restart")
    return InlineKeyboardMarkup(
        [[b3], [b4]])

async def pay_start(update, context):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("_")
    kind = parts[1]
    ref = int(parts[2])
    await q.edit_message_text(
        "Pay 10 AED to Unlock Contact\n\n"
        "Payment: Telegram Stars ONLY.\n"
        "Fast & automatic.",
        reply_markup=pay_kb(kind, ref, PRICE_CONTACT),
        parse_mode="Markdown")
    return PAY_METHOD

async def pin_start(update, context):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("_")
    kind = "pin_" + parts[1]
    ref = int(parts[2])
    await q.edit_message_text(
        "Pin This Post - 25 AED (24h)\n\n"
        "Your post stays on top for 24h,\n"
        "then auto-unpin.\n\n"
        "Payment: Telegram Stars ONLY.",
        reply_markup=pay_kb(kind, ref, PRICE_PIN),
        parse_mode="Markdown")
    return PAY_METHOD

async def send_stars_invoice(update, context, kind, ref, price):
    q = update.callback_query
    chat_id = q.from_user.id
    if price == PRICE_PIN:
        stars = STARS_PIN
        title = "Pin Post 24h - 25 AED"
        desc = "Pin your post on top for 24h"
    else:
        stars = STARS_CONTACT
        title = "Unlock Contact - 10 AED"
        desc = "Unlock one contact"
    payload = "stars_" + kind + "_" + str(ref)
    prices = [LabeledPrice(title, stars)]
    await context.bot.send_invoice(
        chat_id, title, desc, payload,
        provider_token="",
        currency="XTR",
        prices=prices)
    await q.edit_message_text(
        "Stars invoice sent.\n"
        "Tap PAY above to pay with Stars.\n"
        "Telegram will confirm automatically\n"
        "after you pay.",
        parse_mode="Markdown")
    return PAY_METHOD

async def pay_method(update, context):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("_")
    price = int(parts[-1])
    ref = int(parts[-2])
    kind = "_".join(parts[2:-2])
    return await send_stars_invoice(
        update, context, kind, ref, price)

async def precheckout(update, context):
    q = update.pre_checkout_query
    await q.answer(ok=True)

async def successful_payment(update, context):
    pay = update.message.successful_payment
    payload = pay.invoice_payload
    parts = payload.split("_")
    kind = "_".join(parts[1:-1])
    ref = int(parts[-1])
    buyer = update.effective_user.id
    price = PRICE_PIN
    if kind in ["lead", "agent", "wanted"]:
        price = PRICE_CONTACT
    context.user_data.clear()
    await deliver_to_buyer(
        context, buyer, kind, ref, price)
    return ROLE

def get_contact_for(kind, ref):
    if kind == "lead":
        lead = leads[ref]
        return format_contact(
            lead.get("contact"),
            lead.get("backup"))
    if kind == "agent":
        lead = leads[ref]
        post = agent_posts[lead["agent_post_id"]]
        return format_contact(
            post.get("agent_contact"),
            post.get("agent_backup"))
    if kind == "wanted":
        post = tenant_posts[ref]
        return format_contact(
            post.get("contact"),
            post.get("backup"))
    return "Not found"

async def deliver_to_buyer(context, buyer, kind, ref, price):
    if kind.startswith("pin_"):
        pk = kind.split("_")[1]
        posts = agent_posts
        if pk != "agent":
            posts = tenant_posts
        if ref >= len(posts):
            await context.bot.send_message(
                buyer,
                "Payment received, but post not found.\n"
                "It was deleted after restart.\n"
                "Contact admin @Givon5 for refund.",
                parse_mode="Markdown")
            return
        mid = posts[ref].get("channel_msg_id")
        if not mid:
            await context.bot.send_message(
                buyer,
                "Payment received, but post was never\n"
                "posted to channel. Bot is not admin.\n"
                "Contact admin @Givon5 for refund.",
                parse_mode="Markdown")
            return
        try:
            await context.bot.pin_chat_message(
                CHANNEL_ID, mid,
                disable_notification=True)
            schedule_unpin(
                context.application, mid)
            await context.bot.send_message(
                buyer,
                "Payment Approved!\n\n"
                "Your post is PINNED for 24h.\n"
                "Then auto-unpin.\n\n"
                "What next?",
                reply_markup=main_kb(),
                parse_mode="Markdown")
        except Exception as e:
            await context.bot.send_message(
                buyer,
                "Approved, but pin failed: " + str(e)
                + "\nBot must be admin with Pin rights.",
                reply_markup=main_kb(),
                parse_mode="Markdown")
        return
    contact = get_contact_for(kind, ref)
    await context.bot.send_message(
        buyer,
        "Payment Approved!\n\n"
        "Here is contact:\n" + str(contact)
        + "\n\nIf both don't work, contact @Givon5\n\n"
        "What next?",
        reply_markup=main_kb(),
        parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CommandHandler("unpin", unpin_cmd))
    app.add_handler(
        PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(
        filters.SUCCESSFUL_PAYMENT,
        successful_payment))
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("menu", menu_cmd),
            CommandHandler("help", help_cmd),
        ],
        states={
            ROLE: [
                CallbackQueryHandler(
                    role_handler, pattern="^role_"),
                CallbackQueryHandler(
                    restart_handler, pattern="^restart$"),
                CallbackQueryHandler(
                    help_handler, pattern="^help$"),
                CallbackQueryHandler(
                    int_yes, pattern="^int_yes$"),
                CallbackQueryHandler(
                    int_confirm, pattern="^int_confirm$"),
                CallbackQueryHandler(
                    pay_start,
                    pattern="^pay_(lead|agent|wanted)_"),
                CallbackQueryHandler(
                    pin_start,
                    pattern="^pin_(agent|tenant)_"),
                CallbackQueryHandler(
                    pay_method, pattern="^paymethod_"),
                CallbackQueryHandler(
                    agent_confirm,
                    pattern="^agent_confirm$"),
                CallbackQueryHandler(
                    tenant_confirm,
                    pattern="^tenant_confirm$"),
            ],
            A_LOC: [MessageHandler(
                filters.TEXT & ~filters.COMMAND, a_loc)],
            A_RENT: [MessageHandler(
                filters.TEXT & ~filters.COMMAND, a_rent)],
            A_TYPE: [MessageHandler(
                filters.TEXT & ~filters.COMMAND, a_type)],
            A_FURN: [MessageHandler(
                filters.TEXT & ~filters.COMMAND, a_furn)],
            A_AVAIL: [MessageHandler(
                filters.TEXT & ~filters.COMMAND, a_avail)],
            A_PHOTOS: [MessageHandler(
                filters.PHOTO | filters.TEXT, a_photos)],
            A_DESC: [MessageHandler(
                filters.TEXT & ~filters.COMMAND, a_desc)],
            A_NAME: [MessageHandler(
                filters.TEXT & ~filters.COMMAND, a_name)],
            A_VERIFY: [MessageHandler(
                filters.CONTACT, a_verify)],
            A_CONTACT: [MessageHandler(
                filters.CONTACT, a_contact)],
            A_BACKUP: [MessageHandler(
                filters.TEXT & ~filters.COMMAND, a_backup)],
            A_CONFIRM: [
                CallbackQueryHandler(
                    agent_confirm,
                    pattern="^agent_confirm$"),
                CallbackQueryHandler(
                    restart_handler, pattern="^restart$"),
                CallbackQueryHandler(
                    help_handler, pattern="^help$")],
            T_LOC: [MessageHandler(
                filters.TEXT & ~filters.COMMAND, t_loc)],
            T_BUDGET: [MessageHandler(
                filters.TEXT & ~filters.COMMAND, t_budget)],
            T_TYPE: [MessageHandler(
                filters.TEXT & ~filters.COMMAND, t_type)],
            T_CONTACT: [MessageHandler(
                filters.CONTACT, t_contact)],
            T_BACKUP: [MessageHandler(
                filters.TEXT & ~filters.COMMAND, t_backup)],
            T_CONFIRM: [
                CallbackQueryHandler(
                    tenant_confirm,
                    pattern="^tenant_confirm$"),
                CallbackQueryHandler(
                    restart_handler, pattern="^restart$"),
                CallbackQueryHandler(
                    help_handler, pattern="^help$")],
            INT_BUDGET: [MessageHandler(
                filters.TEXT & ~filters.COMMAND, int_budget)],
            INT_MOVEIN: [MessageHandler(
                filters.TEXT & ~filters.COMMAND, int_movein)],
            INT_CONTACT: [MessageHandler(
                filters.CONTACT, int_contact)],
            INT_BACKUP: [MessageHandler(
                filters.TEXT & ~filters.COMMAND, int_backup)],
            INT_CONFIRM: [
                CallbackQueryHandler(
                    int_confirm, pattern="^int_confirm$"),
                CallbackQueryHandler(
                    restart_handler, pattern="^restart$"),
                CallbackQueryHandler(
                    help_handler, pattern="^help$")],
            PAY_METHOD: [
                CallbackQueryHandler(
                    pay_method, pattern="^paymethod_"),
                CallbackQueryHandler(
                    restart_handler, pattern="^restart$"),
                CallbackQueryHandler(
                    help_handler, pattern="^help$"),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("menu", menu_cmd),
            CommandHandler("help", help_cmd),
            CallbackQueryHandler(
                restart_handler, pattern="^restart$"),
            CallbackQueryHandler(
                help_handler, pattern="^help$"),
            CallbackQueryHandler(
                role_handler, pattern="^role_"),
        ],
        allow_reentry=True,
        per_message=False,
    )
    app.add_handler(conv)
    app.add_error_handler(on_error)
    if app.job_queue:
        app.job_queue.run_daily(
            daily_tip_job,
            time=datetime.time(hour=5, minute=0),
            name="daily_tip")
    print("Bot running...", flush=True)
    try:
        app.run_polling()
    except Exception as e:
        print("CRASH:", e, flush=True)
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
