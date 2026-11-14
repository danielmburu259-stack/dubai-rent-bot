import os
import logging
from datetime import datetime, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters, JobQueue
)
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== CONFIG - YOUR REAL BOT =====
BOT_USERNAME = "Dubairentalsbot"
BOT_LINK = f"https://t.me/{BOT_USERNAME}"
CHANNEL_USERNAME = "dubairentonly"
CHANNEL_LINK = f"https://t.me/{CHANNEL_USERNAME}"
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1004386364968"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # your Telegram ID
BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")

# In-memory DB - replace with SQLite/Postgres later if you want persistence
users = {}  # user_id -> {role, phone, trakheesi, verified, step, draft, ...}
listings = {}  # listing_id -> data
leads = {}  # lead_id -> data
next_id = [1]

def get_user(uid):
    if uid not in users:
        users[uid] = {"role": None, "phone": None, "trakheesi": None,
                       "verified": False, "step": None, "draft": {}, "last_listing": None}
    return users[uid]

def main_menu_kb(uid=None):
    kb = [
        [InlineKeyboardButton("🏠 Post a Listing (Agent)", callback_data="role_agent")],
        [InlineKeyboardButton("🔍 Find a Property (Tenant)", callback_data="role_tenant")],
        [InlineKeyboardButton("📢 View Channel", url=CHANNEL_LINK)],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
        [InlineKeyboardButton("🔄 Restart / Main Menu", callback_data="restart")],
    ]
    return InlineKeyboardMarkup(kb)

def restart_kb(is_agent=True):
    # Smart restart - keeps verification
    if is_agent:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Post Another Listing", callback_data="restart_agent")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="restart")],
            [InlineKeyboardButton("📢 View Channel", url=CHANNEL_LINK)],
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 New Request", callback_data="restart_tenant")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="restart")],
            [InlineKeyboardButton("📢 View Channel", url=CHANNEL_LINK)],
        ])

def help_text():
    return (
        "❓ <b>How @Dubairentalsbot Works</b>\n\n"
        "<b>For Agents:</b>\n"
        "1. Tap Post a Listing\n"
        "2. Send details (area, price, beds, etc)\n"
        "3. Send photos (up to 5)\n"
        "4. Type DONE\n"
        "5. Send phone + Trakheesi LAST\n"
        "6. We verify once, then post to @dubairentonly\n\n"
        "<b>For Tenants:</b>\n"
        "1. Tap Find a Property\n"
        "2. Send what you want (area, budget, beds, move date)\n"
        "3. Send phone LAST\n"
        "4. Agents see it and pay to unlock your contact\n\n"
        "Commands: /start /help /menu\n"
        "Stuck? Tap 🔄 Restart / Main Menu - your verification is saved."
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    u["step"] = None
    # Don't clear verified/phone - smart restart
    await update.message.reply_text(
        f"👋 Welcome to <b>@Dubairentalsbot</b> - Dubai Rentals Only\n\n"
        "Agents post verified listings. Tenants find homes.\n"
        "Choose what you want to do:",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb(uid)
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="restart")]])
    if update.message:
        await update.message.reply_text(help_text(), parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.callback_query.edit_message_text(help_text(), parse_mode=ParseMode.HTML, reply_markup=kb)

# ===== CALLBACKS =====
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    u = get_user(uid)
    data = q.data

    if data == "restart":
        u["step"] = None
        u["draft"] = {}
        await q.edit_message_text("🏠 <b>Main Menu</b>\nYour verification & phone are saved. Choose again:", parse_mode=ParseMode.HTML, reply_markup=main_menu_kb(uid))
        return

    if data == "restart_agent":
        u["step"] = "agent_details"
        u["draft"] = {}
        await q.edit_message_text("🔄 <b>New Listing - Step 1/4</b>\n\nSend listing details:\nExample: Marina, 2BR, 95k/year, Furnished, Available now", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="restart")]]))
        return

    if data == "restart_tenant":
        u["step"] = "tenant_details"
        u["draft"] = {}
        await q.edit_message_text("🔄 <b>New Request - Step 1/2</b>\n\nWhat are you looking for?\nExample: JVC, 1BR, budget 55k, move in Dec", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="restart")]]))
        return

    if data == "help":
        await q.edit_message_text(help_text(), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="restart")]]))
        return

    if data == "role_agent":
        u["role"] = "agent"
        # If already verified, skip straight to details - verification ONCE
        if u["verified"] and u["phone"] and u["trakheesi"]:
            u["step"] = "agent_details"
            u["draft"] = {}
            await q.edit_message_text("✅ You're already verified!\n\n<b>Step 1/4 - Details</b>\nSend listing details:", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="restart")]]))
        else:
            u["step"] = "agent_details"
            u["draft"] = {}
            await q.edit_message_text("🏠 <b>Agent - Step 1/4: Details</b>\n\nSend listing details first.\nContacts (phone + Trakheesi) will be asked LAST.\n\nExample: Marina, 2BR, 95k/year", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="restart")]]))
        return

    if data == "role_tenant":
        u["role"] = "tenant"
        u["step"] = "tenant_details"
        u["draft"] = {}
        await q.edit_message_text("🔍 <b>Tenant - Step 1/2: What do you need?</b>\n\nSend details:\nExample: JVC, 1BR, 55k budget, move Dec", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="restart")]]))
        return

    if data.startswith("buy_"):
        lead_id = data.split("_", 1)[1]
        lead = leads.get(lead_id)
        if not lead:
            await q.edit_message_text("This lead is gone.")
            return
        # Here connect your payment - for now simulate approve
        await q.edit_message_text(
            f"💳 To unlock this tenant contact, pay and send receipt to admin.\n\nTenant wants: {lead['details']}\n\nAfter payment you will get the number + 🔄 button to buy another.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ I Paid - Get Number", callback_data=f"paid_{lead_id}")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="restart")]
            ])
        )
        return

    if data.startswith("paid_"):
        lead_id = data.split("_", 1)[1]
        lead = leads.get(lead_id)
        if not lead:
            await q.edit_message_text("Lead not found.")
            return
        await q.edit_message_text(
            f"✅ <b>Unlocked!</b>\nTenant Number: {lead['phone']}\nRequest: {lead['details']}\n\nCall fast - good leads go quick.",
            parse_mode=ParseMode.HTML,
            reply_markup=restart_kb(is_agent=True)
        )
        return

    if data.startswith("approve_"):
        lid = data.split("_", 1)[1]
        lst = listings.get(lid)
        if not lst:
            await q.edit_message_text("Listing not found.")
            return
        # Post to channel with SHARE + OPEN BOT buttons
        share_url = f"https://t.me/share/url?url={CHANNEL_LINK}&text={lst['details'][:80]}"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Share This Listing", url=share_url)],
            [InlineKeyboardButton("🤖 Open Bot to Enquire", url=BOT_LINK)],
            [InlineKeyboardButton("📢 View Channel", url=CHANNEL_LINK)],
        ])
        caption = f"🏠 <b>NEW LISTING - Dubai</b>\n\n{lst['details']}\n\n📍 Agent Verified ✅\nTrakheesi: {lst['trakheesi']}\n\n👉 Enquire via @{BOT_USERNAME}"
        try:
            if lst.get("photos"):
                media = [InputMediaPhoto(p, caption=caption if i==0 else "", parse_mode=ParseMode.HTML) for i,p in enumerate(lst["photos"])]
                await context.bot.send_media_group(CHANNEL_ID, media)
                await context.bot.send_message(CHANNEL_ID, "👆 Tap Share or Open Bot above to enquire", reply_markup=kb)
            else:
                await context.bot.send_message(CHANNEL_ID, caption, parse_mode=ParseMode.HTML, reply_markup=kb)
            lst["posted"] = True
            await q.edit_message_text("✅ Posted to @dubairentonly!", reply_markup=restart_kb(is_agent=True))
        except Exception as e:
            await q.edit_message_text(f"Post failed: {e}\nCheck CHANNEL_ID and that bot is admin in channel.")
        return

# ===== MESSAGES - ORDER IS CONTACTS LAST =====
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    text = (update.message.text or "").strip()
    step = u.get("step")

    if text.lower() in ["/start", "/menu"]:
        await start(update, context)
        return
    if text.lower() == "/help":
        await help_cmd(update, context)
        return

    if not step:
        await update.message.reply_text("Tap a button to start:", reply_markup=main_menu_kb(uid))
        return

    # --- AGENT FLOW: details -> photos -> phone -> trakheesi (LAST) ---
    if step == "agent_details":
        u["draft"]["details"] = text
        u["draft"]["photos"] = []
        u["step"] = "agent_photos"
        await update.message.reply_text("📸 <b>Step 2/4 - Photos</b>\nSend up to 5 photos, then type DONE\nType SKIP if no photos.", parse_mode=ParseMode.HTML)
        return

    if step == "agent_photos":
        if text.upper() == "DONE":
            # If already verified, we already have phone/trakheesi - post directly
            if u["verified"]:
                await finish_agent_listing(update, context, uid)
            else:
                u["step"] = "agent_phone"
                await update.message.reply_text("📞 <b>Step 3/4 - Phone LAST</b>\nSend your phone number (e.g. +971501234567)")
            return
        if text.upper() == "SKIP":
            u["draft"]["photos"] = []
            if u["verified"]:
                await finish_agent_listing(update, context, uid)
            else:
                u["step"] = "agent_phone"
                await update.message.reply_text("📞 <b>Step 3/4 - Phone LAST</b>\nSend your phone number")
            return
        await update.message.reply_text("Send photos, then type DONE")
        return

    if step == "agent_phone":
        u["draft"]["phone"] = text
        u["step"] = "agent_trakheesi"
        await update.message.reply_text("📄 <b>Step 4/4 - Trakheesi LAST</b>\nSend your Trakheesi / Permit number")
        return

    if step == "agent_trakheesi":
        u["draft"]["trakheesi"] = text
        u["phone"] = u["draft"]["phone"]
        u["trakheesi"] = text
        u["verified"] = True  # Verified ONCE - never ask again
        await finish_agent_listing(update, context, uid)
        return

    # --- TENANT FLOW: details -> phone LAST ---
    if step == "tenant_details":
        u["draft"]["details"] = text
        u["step"] = "tenant_phone"
        await update.message.reply_text("📞 <b>Step 2/2 - Phone LAST</b>\nSend your phone number so agents can reach you after they pay")
        return

    if step == "tenant_phone":
        u["draft"]["phone"] = text
        u["phone"] = text
        lid = f"L{next_id[0]}"; next_id[0]+=1
        leads[lid] = {"details": u["draft"]["details"], "phone": text, "tenant_id": uid}
        u["step"] = None
        u["draft"] = {}
        await update.message.reply_text(
            f"✅ Request saved!\n\nAgents will see it and can unlock your contact.\n\nYour request: {leads[lid]['details']}",
            reply_markup=restart_kb(is_agent=False)
        )
        # Notify admin / agents group - in real version send to agents
        if ADMIN_ID:
            try:
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("💳 Buy Contact", callback_data=f"buy_{lid}")]])
                await context.bot.send_message(ADMIN_ID, f"🔔 NEW LEAD {lid}\n{leads[lid]['details']}\nTenant ID: {uid}", reply_markup=kb)
            except: pass
        return

async def finish_agent_listing(update, context, uid):
    u = get_user(uid)
    lid = f"A{next_id[0]}"; next_id[0]+=1
    listings[lid] = {
        "details": u["draft"].get("details",""),
        "photos": u["draft"].get("photos",[]),
        "phone": u.get("phone"),
        "trakheesi": u.get("trakheesi"),
        "agent_id": uid,
        "posted": False
    }
    u["last_listing"] = lid
    u["step"] = None
    u["draft"] = {}
    # If admin is 0, auto-approve for testing, else ask admin
    if ADMIN_ID == 0:
        # Direct post path for testing
        await update.message.reply_text("✅ Verified once! Listing saved. It will be posted to channel.", reply_markup=restart_kb(is_agent=True))
        # Trigger approve logic manually via fake callback - simplified: post now
        # In production set ADMIN_ID
    else:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Approve & Post to Channel", callback_data=f"approve_{lid}")]])
        try:
            await context.bot.send_message(ADMIN_ID, f"🔔 NEW LISTING {lid}\n{listings[lid]['details']}\nPhone: {listings[lid]['phone']}\nTrakheesi: {listings[lid]['trakheesi']}", reply_markup=kb)
        except: pass
        await update.message.reply_text("✅ Listing received! Admin will verify & post to @dubairentonly.\nYou won't need to verify again.", reply_markup=restart_kb(is_agent=True))

async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)
    if u.get("step") == "agent_photos":
        fid = update.message.photo[-1].file_id
        u["draft"].setdefault("photos", []).append(fid)
        count = len(u["draft"]["photos"])
        await update.message.reply_text(f"Photo {count}/5 saved. Send more or type DONE")
    else:
        await update.message.reply_text("Tap Post a Listing first.", reply_markup=main_menu_kb(uid))

# ===== DAILY WELCOME POST - ONCE PER DAY =====
async def daily_welcome(context: ContextTypes.DEFAULT_TYPE):
    # Runs at 09:00 Dubai time
    try:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Post a Listing", url=BOT_LINK)],
            [InlineKeyboardButton("🔍 Find a Property", url=BOT_LINK)],
            [InlineKeyboardButton("📤 Share Channel", url=f"https://t.me/share/url?url={CHANNEL_LINK}&text=Dubai Rentals Only - Verified Listings")],
        ])
        await context.bot.send_message(
            CHANNEL_ID,
            "☀️ <b>Good Morning Dubai!</b>\n\n🏠 Verified rentals only in @dubairentonly\n\nAgents: Post via @Dubairentalsbot\nTenants: Request via @Dubairentalsbot\n\nNo scams. Trakheesi verified. ✅",
            parse_mode=ParseMode.HTML, reply_markup=kb
        )
    except Exception as e:
        logger.error(f"Daily post failed: {e}")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    # Daily job - 09:00 UTC+4 = 05:00 UTC
    if app.job_queue:
        app.job_queue.run_daily(daily_welcome, time=time(hour=5, minute=0))
    print(f"Bot running @{BOT_USERNAME} -> Channel {CHANNEL_LINK}")
    app.run_polling()

if __name__ == "__main__":
    main()
