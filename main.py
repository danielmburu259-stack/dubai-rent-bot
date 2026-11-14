import os, logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
BINANCE_ID = os.environ.get("BINANCE_ID", "844432726")
TRC20 = os.environ.get("TRC20", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@dubairentonly")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
PORT = int(os.environ.get("PORT", "10000"))

logging.basicConfig(level=logging.INFO)
users = {}  # uid -> {role, step, phone, interested_post, pending_pay}
posts = {}  # pid -> {owner_id, role, details, phone, status}
leads = {}  # lid -> {tenant_id, agent_id, post_id, info, phone}
post_counter = [0]
lead_counter = [0]

BAD_WORDS = ["crypto","loan","visa","job","investment","bitcoin","forex"]

# ---------- KEYBOARDS ----------
def role_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 I am TENANT - I Want To Rent", callback_data="role_tenant")],
        [InlineKeyboardButton("🏢 I am AGENT / LANDLORD - I Have House", callback_data="role_agent")],
    ])

def main_menu(role):
    if role == "tenant":
        # TENANT: NO Get Contact button. Tenant NEVER gets agent contact.
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Post My Request (FREE)", callback_data="post")],
            [InlineKeyboardButton("🏘️ Browse Agent Houses", callback_data="browse_agent")],
            [InlineKeyboardButton("⭐ Promote My Request - Featured 30 / Pinned 50", callback_data="promote")],
        ])
    else:
        # AGENT: Only agent can pay for contacts
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Post My House (FREE)", callback_data="post")],
            [InlineKeyboardButton("👀 Browse Tenant Requests", callback_data="browse_tenant")],
            [InlineKeyboardButton("⭐ Promote My House - Featured 30 / Pinned 50", callback_data="promote")],
            [InlineKeyboardButton("✅ Verified Badge 100 AED", callback_data="verified")],
        ])

# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to Dubai Rent Only 🇦🇪\n\n*No Buy. No Commercial. No Scam. Only Verified Rentals.*\n\nFirst, who are you?\n\n🏠 TENANT = You want to rent. You NEVER pay for contacts. You only pay if you want your request Featured / Pinned.\n🏢 AGENT = You have house. Posting is FREE. You pay 10 AED ONLY to reveal a Tenant's phone.",
        parse_mode=ParseMode.MARKDOWN, reply_markup=role_keyboard())

# ---------- BUTTONS ----------
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); uid = q.from_user.id; data = q.data

    # 1. ROLE SELECTION - Bot must know who you are
    if data in ["role_tenant","role_agent"]:
        role = "tenant" if data=="role_tenant" else "agent"
        users[uid] = {"role": role, "step": "phone"}
        kb = ReplyKeyboardMarkup([[KeyboardButton("📱 Share My Contact", request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)
        if role=="tenant":
            await q.message.reply_text("You are TENANT. Step 1: Share your phone to verify. We NEVER show it publicly. Agent will pay to get it.", reply_markup=kb)
        else:
            await q.message.reply_text("You are AGENT. Step 1: Share your phone to verify. Then send Trakheesi screenshot.", reply_markup=kb)
        return

    if uid not in users:
        await q.message.reply_text("Please send /start first and choose Tenant or Agent.", reply_markup=role_keyboard()); return
    role = users[uid].get("role")

    # 2. POSTING
    if data == "post":
        users[uid]["step"] = "details"
        if role=="tenant":
            await q.message.reply_text("TENANT - Post FREE.\nSend in ONE message:\nArea / Type / Budget / Move-in Date\nExample: Marina, 1BR, 65000, 1 Dec")
        else:
            await q.message.reply_text("AGENT - Post FREE.\nSend in ONE message:\nArea / Type / Rent / Available Date\nExample: Marina, 1BR, 70000, Available Now\nThen send photos + Trakheesi.")
        return

    # 3. BROWSE
    if data in ["browse_agent","browse_tenant"]:
        want = "agent" if data=="browse_agent" else "tenant"
        # Only show LIVE approved posts
        found = [(pid,p) for pid,p in posts.items() if p["role"]==want and p.get("status")=="live"]
        if not found:
            await q.message.reply_text("No live posts yet in this category. Check channel @dubairentonly or post yours FREE.", reply_markup=main_menu(role)); return
        for pid,p in found[-5:]:
            if want=="agent":
                # Tenant viewing Agent house -> ONLY I'm Interested, NEVER Get Contact
                txt = f"🏢 HOUSE - ID {pid}\n\n{p['details']}\n\nInterested? Click below (FREE)."
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("🙋 I'm Interested (FREE)", callback_data=f"interested_{pid}")]])
            else:
                # Agent viewing Tenant request -> DIRECT PAY
                txt = f"🏠 TENANT WANTS - ID {pid}\n\n{p['details']}\n\n📞 Phone: HIDDEN - Pay 10 AED to reveal."
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("📞 Pay 10 AED - Reveal Tenant Phone", callback_data=f"reveal_tenant_{pid}")]])
            await q.message.reply_text(txt, reply_markup=kb)
        return

    # 4. TENANT CLICKS AGENT POST -> COLLECT DETAILS TO SELL TO AGENT
    if data.startswith("interested_"):
        if role != "tenant":
            await q.message.reply_text("Only Tenants click I'm Interested. Agents, use Browse Tenant Requests."); return
        pid = int(data.split("_")[1])
        if pid not in posts: await q.message.reply_text("Post not found."); return
        users[uid]["interested_post"] = pid
        users[uid]["step"] = "lead_details"
        await q.message.reply_text("Great! To send interest to Agent, send in ONE message:\n\nYour Budget / Area / Move-in Date\nExample: 65000, Marina, 1 Dec\nYour phone is already saved. We will NOT show it until Agent pays 10 AED.")
        return

    # 5. AGENT CLICKS LEAD NOTIFICATION -> PREVIEW (phone hidden)
    if data.startswith("lead_"):
        lid = int(data.split("_")[1]); lead = leads.get(lid)
        if not lead: await q.message.reply_text("Lead not found."); return
        if uid != lead["agent_id"]:
            await q.message.reply_text("This lead is for another agent."); return
        await q.message.reply_text(
            f"🔔 NEW LEAD for your post ID {lead['post_id']}:\n\nTenant says: {lead['info']}\n\n📞 Phone: HIDDEN - Pay 10 AED to reveal",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📞 Pay 10 AED - Reveal Phone", callback_data=f"pay_lead_{lid}")]]))
        return

    # 6. AGENT CLICKS TENANT POST -> DIRECT PAY
    if data.startswith("reveal_tenant_"):
        if role != "agent":
            await q.message.reply_text("Only Agents pay for contacts. Tenants never pay for contacts."); return
        pid = int(data.split("_")[2])
        await show_payment(q, "pay_contact", pid=pid, kind="tenant_post"); return

    # 7. PAYMENTS
    if data.startswith("pay_lead_"):
        lid = int(data.split("_")[2])
        await show_payment(q, "pay_contact", lead_id=lid, kind="lead"); return
    if data.startswith("pay_"):
        await show_payment(q, data); return
    if data == "send_screenshot":
        await q.message.reply_text("Send your payment screenshot now. Admin will approve and reveal phone."); return

    if data == "promote":
        await q.message.reply_text("⭐ PROMOTE\n\nFeatured 30 AED / 24h - Top of bot + Channel\nPinned 50 AED / 24h - Pinned in Channel @dubairentonly (only 2 slots/day)\n\nBoth Tenants AND Agents can promote their OWN post.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⭐ Featured - 30 AED", callback_data="pay_featured")],
                [InlineKeyboardButton("📌 Pinned - 50 AED", callback_data="pay_pinned")],
            ])); return
    if data == "verified":
        if role != "agent":
            await q.message.reply_text("Verified Badge is for Agents only."); return
        await q.message.reply_text("✅ VERIFIED BADGE - 100 AED one-time (Agents only)\n\nSend Trakheesi + RERA screenshot. Admin checks in 2 mins. You get Green Badge forever.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Pay 100 AED - Verified", callback_data="pay_verified")]])); return

    # 8. ADMIN APPROVE -> PUBLISH TO CHANNEL
    if data.startswith("approve_"):
        if uid != ADMIN_ID:
            await q.message.reply_text("Only admin can approve."); return
        pid = int(data.split("_")[1]); post = posts.get(pid)
        if not post: await q.message.reply_text("Post not found."); return
        post["status"]="live"
        # Publish to channel with CORRECT button per role
        try:
            if post["role"]=="agent":
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("🙋 I'm Interested (Tenant - FREE)", callback_data=f"interested_{pid}")]])
                await context.bot.send_message(CHANNEL_ID, f"🏢 NEW HOUSE - Dubai Rent Only\n\n{post['details']}\n\nInterested? Open bot @dubairentonly bot and click I'm Interested.", reply_markup=kb)
            else:
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("📞 Agent - Pay 10 AED to Reveal Tenant Phone", callback_data=f"reveal_tenant_{pid}")]])
                await context.bot.send_message(CHANNEL_ID, f"🏠 NEW TENANT WANTS:\n\n{post['details']}\n\nAgents: Pay 10 AED in bot to get this tenant's phone.", reply_markup=kb)
        except Exception as e:
            await q.message.reply_text(f"Approved but channel post failed: {e}. Is bot Admin in @dubairentonly?")
            return
        await q.message.reply_text(f"✅ Approved Post {pid}. Now LIVE in Channel + Bot.")
        try: await context.bot.send_message(post["owner_id"], f"✅ Your post is APPROVED and LIVE in @dubairentonly!\n\n{post['details']}", reply_markup=main_menu(post["role"]))
        except: pass
        return

    if data.startswith("report_"):
        await q.message.reply_text("Thanks. Report sent. 3 reports = auto-hide. Admin will check."); return

async def show_payment(q, pay_type, pid=None, lead_id=None, kind=None):
    prices = {"pay_contact": ("Tenant Contact Reveal","10 AED"), "pay_featured": ("Featured","30 AED"), "pay_pinned": ("Pinned","50 AED"), "pay_verified": ("Verified Badge","100 AED")}
    name, price = prices.get(pay_type, ("Payment","10 AED"))
    uid = q.from_user.id
    users[uid]["pending_pay"] = {"type": pay_type, "pid": pid, "lead_id": lead_id, "kind": kind}
    text = f"💳 Pay for {name} - {price}\n\n**1. Binance Pay:** ID `{BINANCE_ID}` - Send {price}\n**2. TRC20 USDT:** `{TRC20}`\n⚠️ ONLY TRC20. Other network = LOST, no refund.\n**3. Telegram Stars:** Pay inside Telegram (auto-approve)\n\nAfter Binance/TRC20, send screenshot here. Admin approves in 5 mins and phone is revealed."
    await q.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⭐ Pay with Stars (Auto)", callback_data=f"stars_{pay_type}")],
            [InlineKeyboardButton("📸 I Paid - Send Screenshot", callback_data="send_screenshot")],
        ]))

# ---------- CONTACT ----------
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if uid in users and users[uid].get("step")=="phone":
        users[uid]["phone"] = update.message.contact.phone_number
        users[uid]["step"] = "choose"
        await update.message.reply_text(f"✅ Phone verified. Welcome {users[uid]['role'].upper()}!", reply_markup=main_menu(users[uid]["role"]))
    else:
        await update.message.reply_text("Send /start first.")

# ---------- TEXT ----------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id; txt = update.message.text or ""
    if any(w in txt.lower() for w in BAD_WORDS):
        await update.message.reply_text("❌ Rejected: Forbidden words (crypto/loan/visa/job). Dubai Rent Only."); return
    if uid not in users: await update.message.reply_text("Send /start first.", reply_markup=role_keyboard()); return
    step = users[uid].get("step"); role = users[uid].get("role")

    # TENANT LEAD DETAILS -> NOTIFY AGENT, phone stays hidden
    if step=="lead_details" and role=="tenant":
        pid = users[uid].get("interested_post"); post = posts.get(pid)
        if not post: await update.message.reply_text("Post not found."); return
        lead_counter[0]+=1; lid = lead_counter[0]
        leads[lid] = {"tenant_id": uid, "agent_id": post["owner_id"], "post_id": pid, "info": txt, "phone": users[uid].get("phone")}
        users[uid]["step"]="choose"
        try:
            await context.bot.send_message(post["owner_id"],
                f"🔔 SOMEONE IS INTERESTED in your post ID {pid}:\n\nYour Post: {post['details']}\nTenant says: {txt}\n\n📞 Phone: HIDDEN. Click to pay 10 AED to reveal.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👀 See Lead - Pay 10 to Reveal Phone", callback_data=f"lead_{lid}")]]))
        except: pass
        await update.message.reply_text("✅ Interest sent to Agent! Agent sees your Budget/Area. Your phone stays hidden until Agent pays 10 AED.\n\nWait for Agent to call you.", reply_markup=main_menu(role))
        return

    # NEW POST -> GOES TO ADMIN FOR APPROVAL (old logic kept)
    if step=="details":
        post_counter[0]+=1; pid = post_counter[0]
        posts[pid] = {"owner_id": uid, "role": role, "details": txt, "phone": users[uid].get("phone"), "status": "pending"}
        users[uid]["step"]="choose"
        if ADMIN_ID:
            try:
                await context.bot.send_message(ADMIN_ID, f"🆕 NEW POST - {role.upper()} - ID {pid}\nUser: {update.message.from_user.first_name} @{update.message.from_user.username}\nPhone: {users[uid].get('phone')}\nDetails: {txt}\n\nCheck Trakheesi & Approve.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"✅ Approve Post {pid}", callback_data=f"approve_{pid}")]]))
            except: pass
        await update.message.reply_text("✅ Received! Your post is FREE and sent for verification.\nAdmin checks Trakheesi (for agents) in 2 mins.\nOnce approved, it goes LIVE in Channel @dubairentonly.\n\nWant more views? ⭐ Featured 30 AED / 📌 Pinned 50 AED", reply_markup=main_menu(role))
        return

    await update.message.reply_text("Use /start to begin.", reply_markup=main_menu(role) if role else role_keyboard())

# ---------- PHOTO ----------
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📸 Photo received. If this is Trakheesi, admin will check it. If house photos, send Price + Area in next message.\n\nYour post is FREE. Tenants never pay for contacts. Agents pay 10 AED only to reveal Tenant phone.")

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
    if WEBHOOK_URL:
        app.run_webhook(listen="0.0.0.0", port=PORT, url_path=BOT_TOKEN, webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    else:
        app.run_polling()
