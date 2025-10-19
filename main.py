import json
import os
import time
import random
import re
from datetime import datetime
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler, ConversationHandler
)

# معلوماتك الخاصة (أفضل تخليها في متغير بيئي على Render بدل التضمين المباشر)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8288095681:AAEhEJifM4owz3yb8MPv7LIoWJqpuuBWvGg")
DEV_ID = os.environ.get("DEV_ID", "7942266627")
GROUP_LINK = "https://t.me/Ma8alatnerl"
GROUP_ID = -1002484191220

DATA_PATH = "data.json"
DATA_CACHE = None  # كاش بالذاكرة

def _default_data():
    return {
        "users": {},
        "banned": [],
        "lists": {},
        "devs": [str(DEV_ID)],
        "top_scores": [],
        "tournaments": [],
        "groups": []  # ← سيتم حفظ القروبات تلقائياً
    }

def load_data():
    global DATA_CACHE
    if DATA_CACHE is None:
        if not os.path.exists(DATA_PATH):
            DATA_CACHE = _default_data()
            with open(DATA_PATH, "w", encoding="utf-8") as f:
                json.dump(DATA_CACHE, f, ensure_ascii=False, indent=2)
        else:
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                try:
                    DATA_CACHE = json.load(f)
                except Exception:
                    DATA_CACHE = _default_data()
    return DATA_CACHE

def save_data(data):
    global DATA_CACHE
    DATA_CACHE = data
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def normalize_text(text):
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    replacements = {
        'أ': 'ا', 'إ': 'ا', 'آ': 'ا',
        'ؤ': 'و',
        'ى': 'ي',
        'ة': 'ه'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.lower()

def expand_text(text):
    pattern = r'(\S+)\s*\((\d+)\)'
    def replacer(match):
        word = match.group(1)
        count = int(match.group(2))
        return ' '.join([word] * count)
    result = re.sub(pattern, replacer, text)
    return result

def expand_d_text(text):
    words = text.strip().split()
    return ' '.join([w for w in words for _ in range(2)])

def is_dev(user_id, data):
    return str(user_id) == str(DEV_ID) or str(user_id) in [str(dev) for dev in data.get('devs', [str(DEV_ID)])]

def add_dev(user_id, data):
    user_id = str(user_id)
    devs = [str(dev) for dev in data.setdefault('devs', [str(DEV_ID)])]
    if user_id not in devs and user_id != str(DEV_ID):
        devs.append(user_id)
        data['devs'] = devs
        save_data(data)
        return True
    return False

def remove_dev(user_id, data):
    user_id = str(user_id)
    devs = [str(dev) for dev in data.setdefault('devs', [str(DEV_ID)])]
    if user_id in devs and user_id != str(DEV_ID):
        devs.remove(user_id)
        data['devs'] = devs
        save_data(data)
        return True
    return False

def is_banned(user_id, data):
    return str(user_id) in [str(b) for b in data.get('banned', [])]

def ban_user_logic(user_id, data):
    user_id = str(user_id)
    banned = [str(b) for b in data.get('banned',[])]
    if user_id not in banned:
        banned.append(user_id)
        data['banned'] = banned
        save_data(data)
        return True
    return False

def unban_user_logic(user_id, data):
    user_id = str(user_id)
    banned = [str(b) for b in data.get('banned',[])]
    if user_id in banned:
        banned.remove(user_id)
        data['banned'] = banned
        save_data(data)
        return True
    return False

# ---- أوامر المطورين والحظر ----
async def promote_dev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    actor_id = update.effective_user.id
    if str(actor_id) != str(DEV_ID):
        return
    if update.message.reply_to_message:
        t_id = update.message.reply_to_message.from_user.id
        if add_dev(t_id, data):
            await update.message.reply_text("تم رفع المستخدم Dev ")
        else:
            await update.message.reply_text("هو بالفعل Dev.")

async def demote_dev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    actor_id = update.effective_user.id
    if str(actor_id) != str(DEV_ID):
        return
    if update.message.reply_to_message:
        t_id = update.message.reply_to_message.from_user.id
        if str(t_id) == str(DEV_ID):
            await update.message.reply_text("لا يمكن تنزيل مؤسس البوت.")
            return
        if remove_dev(t_id, data):
            await update.message.reply_text("تم تنزيل المستخدم من Dev ")
        else:
            await update.message.reply_text("هو ليس Dev.")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    actor_id = update.effective_user.id
    if not is_dev(actor_id, data):
        return
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        if ban_user_logic(target_id, data):
            await update.message.reply_text("تم منع المستخدم ")
        else:
            await update.message.reply_text("المستخدم ممنوع بالفعل.")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    actor_id = update.effective_user.id
    if not is_dev(actor_id, data):
        return
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        if unban_user_logic(target_id, data):
            await update.message.reply_text("تم فتح المستخدم ")
        else:
            await update.message.reply_text("المستخدم ليس محظور.")

async def unban_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    actor_id = update.effective_user.id
    if not is_dev(actor_id, data):
        return
    data['banned'] = []
    save_data(data)
    await update.message.reply_text("تم فتح جميع المستخدمين ")

# ---- إدارة القوائم ----
ADD_LIST_NAME, ADD_LIST_TEXTS, ADD_TXT_LIST_NAME, ADD_TXT_LIST_TEXTS, DELETE_LIST, DELETE_TEXT = range(6)

async def add_list_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if not is_dev(update.effective_user.id, data):
        return ConversationHandler.END
    await update.message.reply_text("ارسل اسم القائمه الي تبيها")
    return ADD_LIST_NAME

async def add_list_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    list_name = update.message.text.strip()
    if not list_name:
        await update.message.reply_text("اسم القائمه غير صالح.")
        return ConversationHandler.END
    if 'lists' not in data:
        data['lists'] = {}
    if list_name in data['lists']:
        await update.message.reply_text("القائمه موجوده مسبقا")
        return ConversationHandler.END
    data['lists'][list_name] = []
    save_data(data)
    context.user_data['add_list'] = list_name
    await update.message.reply_text("ارسل النصوص الي تبي تضيفها\n(ارسل كل نص لحاله، واذا خلصت اكتب تم)")
    return ADD_LIST_TEXTS

async def add_list_texts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    list_name = context.user_data.get('add_list')
    text = update.message.text.strip()
    if text == "تم":
        await update.message.reply_text("تم قفل الاضافه ")
        return ConversationHandler.END
    if list_name and text:
        data['lists'][list_name].append(text)
        save_data(data)
        await update.message.reply_text("تمت اضافة النص.")
    return ADD_LIST_TEXTS

async def add_txt_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if not is_dev(update.effective_user.id, data):
        return ConversationHandler.END
    await update.message.reply_text("ارسل اسم القائمه")
    return ADD_TXT_LIST_NAME

async def add_txt_list_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    list_name = update.message.text.strip()
    if list_name not in data.get('lists', {}):
        await update.message.reply_text("القائمه غير موجوده")
        return ConversationHandler.END
    context.user_data['add_txt_list'] = list_name
    await update.message.reply_text("ارسل النصوص الي تبي تضيفها\n(ارسل كل نص لحاله، واذا خلصت اكتب تم)")
    return ADD_TXT_LIST_TEXTS

async def add_txt_list_texts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    list_name = context.user_data.get('add_txt_list')
    text = update.message.text.strip()
    if text == "تم":
        await update.message.reply_text("تم قفل الاضافه ")
        return ConversationHandler.END
    if list_name and text:
        data['lists'][list_name].append(text)
        save_data(data)
        await update.message.reply_text("تمت اضافة النص.")
    return ADD_TXT_LIST_TEXTS

async def delete_text_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if not is_dev(update.effective_user.id, data):
        return
    await update.message.reply_text("ارسل اسم القائمه")
    return DELETE_LIST

async def delete_text_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    list_name = update.message.text.strip()
    context.user_data['delete_list'] = list_name
    if list_name not in data.get('lists', {}):
        await update.message.reply_text("القائمه غير موجودة.")
        return ConversationHandler.END
    await update.message.reply_text("ارسل النص المراد حذفه")
    return DELETE_TEXT

async def delete_text_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    list_name = context.user_data.get('delete_list')
    text = update.message.text.strip()
    if list_name in data['lists'] and text in data['lists'][list_name]:
        data['lists'][list_name].remove(text)
        save_data(data)
        await update.message.reply_text("تم حذف النص ")
    else:
        await update.message.reply_text("النص غير موجود.")
    return ConversationHandler.END

async def delete_text_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم الالغاء.")
    return ConversationHandler.END

# ---- الاشتراك ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = load_data()
    if is_banned(user_id, data):
        return
    welcome_message = """ارحب بهالبوت الجبار القهار
انا اسمي بوت nerl للمقالات
مهمتي اخليك اقوى واسرع من اي احد

اكتب كر للتكرار وصد للمقالات العاديه
كل اسبوع فيه مسابقه بقروب النشاما

بالتوفيق حبي"""
    keyboard = [
        [InlineKeyboardButton("Ma8alatnerl", url=GROUP_LINK)],
        [InlineKeyboardButton("التحقق من الاشتراك", callback_data="check_subscription")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = load_data()
    try:
        member = await context.bot.get_chat_member(GROUP_ID, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            name = query.from_user.first_name
            if str(user_id) not in data['users']:
                data['users'][str(user_id)] = {
                    'points': 0,
                    'games': [],
                    'subscribed': True,
                    'name': name
                }
            else:
                data['users'][str(user_id)]['subscribed'] = True
                data['users'][str(user_id)]['name'] = name
            save_data(data)
            await query.answer("تم التحقق بنجاح! يمكنك استخدام البوت الآن")
        else:
            await query.answer("خش القروب اول عشان تلعب بالبوت", show_alert=True)
    except:
        await query.answer("خش القروب اول عشان تلعب بالبوت", show_alert=True)

# ---- جولات وتحديات ----
async def start_tournament(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user_id = update.effective_user.id
    if is_banned(user_id, data):
        return
    await update.message.reply_text("من كم نقطه تبيها؟ ")
    context.user_data['waiting_for'] = 'tournament_target'

async def handle_tournament_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target = int(update.message.text)
        if 1 <= target <= 1000:
            context.bot_data['tournament'] = {
                'target': target,
                'scores': {},
            }
            context.user_data['waiting_for'] = None
            await update.message.reply_text(f"تم انشاء الجوله بعدد نقاط: {target}")
        else:
            await update.message.reply_text("الرقم لازم يكون بين 1 و 1000")
    except:
        await update.message.reply_text("ارسل رقم فقط")

async def handle_list_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = load_data()
    if is_banned(user_id, data):
        return
    if str(user_id) not in data.get('users', {}) or not data['users'][str(user_id)].get('subscribed'):
        await update.message.reply_text("خش القروب اول عشان تلعب بالبوت")
        return
    text = update.message.text.strip()
    if text in data.get('lists', {}):
        texts = data['lists'][text]
        if texts:
            selected_text = random.choice(texts)
            # هنا ميزة د فقط
            if text == "د":
                expanded_text = expand_d_text(selected_text)
                d_mode = True
            else:
                expanded_text = expand_text(selected_text)
                d_mode = False
            challenge = {
                "original_text": selected_text,
                "expanded_text": expanded_text,
                "start_time": time.time(),
                "word_count": len(expanded_text.split()),
                "requested_by": user_id,
                "winner_id": None,
                "d_mode": d_mode,
                "list_name": text
            }
            context.bot_data["current_challenge"] = challenge
            await update.message.reply_text(selected_text)
        else:
            await update.message.reply_text("القائمه فاضيه، ما فيها نصوص.")
    else:
        await update.message.reply_text("مافي قائمه بهذا الاسم.")

async def handle_text_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = load_data()
    if is_banned(user_id, data):
        return
    challenge = context.bot_data.get("current_challenge")
    if not challenge or challenge.get("winner_id"):
        return
    submitted_text = update.message.text
    expected_text = challenge["expanded_text"]
    user_id_str = str(user_id)
    user_name = update.effective_user.first_name

    def send_result(time_taken, wpm):
        response = (
            f"صح!\n"
            f"الوقت: {time_taken} ثانية\n"
            f"السرعة: {wpm} WPM"
        )
        return response

    # ميزة د فقط لازم يكتب كل كلمة مرتين
    if challenge.get("d_mode", False):
        if normalize_text(submitted_text) != normalize_text(expected_text):
            return
    # باقي القوائم تحقق عادي
    else:
        if normalize_text(submitted_text) != normalize_text(expected_text):
            return

    time_taken = round(time.time() - challenge["start_time"], 2)
    word_count = challenge["word_count"]
    wpm = round((word_count / time_taken) * 60) if time_taken > 0 else word_count * 60

    # حفظ اللعبة في سجل المستخدم (دزاتي)
    if str(user_id) not in data['users']:
        data['users'][str(user_id)] = {
            'points': 0,
            'games': [],
            'subscribed': True,
            'name': user_name
        }
    user_obj = data['users'][str(user_id)]
    user_obj['games'].append({
        'time': time_taken,
        'wpm': wpm,
        'words': word_count,
        'date': datetime.now().isoformat()
    })
    save_data(data)

    # الجولات فقط!
    if 'tournament' in context.bot_data:
        tournament = context.bot_data['tournament']
        points = tournament['scores'].get(user_id_str, 0) + 1
        tournament['scores'][user_id_str] = points
        user_obj['points'] += 1
        save_data(data)
        await update.message.reply_text(send_result(time_taken, wpm))
        await update.message.reply_text(f"نقاطك بالجوله: {points}")
        if points >= tournament['target']:
            del context.bot_data['tournament']
            winner_announce = f"🏆 مبروك [{user_name}](tg://user?id={user_id}) هو الفائز بالجوله!\n\n"
            rank = sorted(tournament['scores'].items(), key=lambda kv: kv[1], reverse=True)
            for i, (uid, pts) in enumerate(rank, 1):
                pname = data['users'].get(uid, {}).get('name', f"ID:{uid}")
                winner_announce += f"{i}. [{pname}](tg://user?id={uid}) — {pts} نقطة\n"
            await update.message.reply_text(winner_announce, parse_mode='Markdown')
        challenge["winner_id"] = user_id
        context.bot_data["current_challenge"] = challenge
        return
    else:
        await update.message.reply_text(send_result(time_taken, wpm))
        challenge["winner_id"] = user_id
        context.bot_data["current_challenge"] = challenge

# ---- دزاتي ----
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user_id = str(update.effective_user.id)
    user_data = data['users'].get(user_id, {})
    if user_data.get('games'):
        last = user_data['games'][-1]
        await update.message.reply_text(
            f"اخر نص:\n"
            f"الوقت: {last['time']} ثانية\n"
            f"سرعتك: {last['wpm']} WPM\n"
            f"عدد الكلمات: {last['words']}"
        )
    else:
        await update.message.reply_text("ما لعبت اي مقاله بعد")

# ---- توب عشره ----
async def show_top10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    leaderboard = []
    for uid, udata in data['users'].items():
        if udata.get('games'):
            best_game = max(udata['games'], key=lambda x: x['wpm'])
            leaderboard.append({
                'uid': uid,
                'wpm': best_game['wpm'],
                'words': best_game['words'],
                'time': best_game['time'],
                'name': udata.get('name', None)
            })
    leaderboard = sorted(leaderboard, key=lambda x: x['wpm'], reverse=True)[:10]
    if leaderboard:
        msg = "توب 10 اسرع لاعبين:\n\n"
        for i, entry in enumerate(leaderboard, 1):
            user_name = entry['name'] or f"ID:{entry['uid']}"
            msg += f"{i}. [{user_name}](tg://user?id={entry['uid']}) — {entry['wpm']} WPM | {entry['words']} كلمة | {entry['time']}ث\n"
        await update.message.reply_text(msg, parse_mode='Markdown')
    else:
        await update.message.reply_text("لا توجد نتائج بعد.")

# ---- ميزة الإذاعة ----
async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user_id = update.effective_user.id
    devs = [str(d) for d in data.get('devs', [])]
    if str(user_id) not in devs:
        await update.message.reply_text("أنت مو مطور وما تقدر تسوي إذاعة.")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("رد على رسالة عشان تبثها.")
        return
    msg_text = update.message.reply_to_message.text
    user_ids = [int(uid) for uid in data.get('users', {})]
    group_ids = data.get('groups', [])
    success = 0
    fail = 0
    # أرسل لكل مستخدم
    for uid in user_ids:
        try:
            await context.bot.send_message(uid, msg_text)
            success += 1
        except:
            fail += 1
    # أرسل لكل قروب مسجل تلقائياً
    for gid in group_ids:
        try:
            await context.bot.send_message(gid, msg_text)
            success += 1
        except:
            fail += 1
    await update.message.reply_text(f"تم إرسال الإذاعة بنجاح إلى {success} من المستخدمين والقروبات\nفشل الإرسال إلى {fail} مستخدم/قروب")

# ---- الرسائل ----
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    data = load_data()
    user_id = update.effective_user.id
    if is_banned(user_id, data):
        return

    # حفظ آيدي القروب تلقائياً إذا استقبل منه أي رسالة
    if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
        group_id = update.effective_chat.id
        groups = data.setdefault("groups", [])
        if group_id not in groups:
            groups.append(group_id)
            save_data(data)

    text = update.message.text.strip()
    waiting_for = context.user_data.get('waiting_for')
    if waiting_for == 'tournament_target':
        await handle_tournament_target(update, context)
        return

    if text == "اذاعة" and update.message.reply_to_message:
        await broadcast_message(update, context)
        return

    if text == "حذف نص":
        await delete_text_start(update, context)
        return

    if text == "اضافه قائمه":
        await add_list_start(update, context)
        return

    if text == "اضف نص":
        await add_txt_start(update, context)
        return

    if text == "جوله":
        await start_tournament(update, context)
        return

    if text == "دزاتي":
        await show_stats(update, context)
        return

    if text == "توب عشره":
        await show_top10(update, context)
        return

    if text == "رفع" and update.message.reply_to_message:
        await promote_dev(update, context)
        return
    if text == "تنزيل" and update.message.reply_to_message:
        await demote_dev(update, context)
        return
    if text == "منع" and update.message.reply_to_message:
        await ban_user(update, context)
        return
    if text == "فتح" and update.message.reply_to_message:
        await unban_user(update, context)
        return
    if text == "فتح الكل":
        await unban_all(update, context)
        return

    if text in data.get('lists', {}):
        context.bot_data.pop("current_challenge", None)
        await handle_list_request(update, context)
        return

    challenge = context.bot_data.get("current_challenge")
    if challenge and not challenge.get("winner_id"):
        await handle_text_submission(update, context)
        return

# -----------------------
# Simple keep-alive HTTP server so Render (or other PaaS) detects an open port.
# This uses the built-in http.server to avoid extra deps.
# -----------------------
class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write("OK".encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    # silence logs
    def log_message(self, format, *args):
        return

def start_keepalive_server():
    try:
        port = int(os.environ.get("PORT", "3000"))
    except:
        port = 3000
    server = HTTPServer(('0.0.0.0', port), KeepAliveHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Keepalive HTTP server listening on 0.0.0.0:{port}")

def main():
    # Start keepalive HTTP server first so Render detects an open port quickly
    start_keepalive_server()

    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & filters.Regex("^حذف نص$"), delete_text_start),
            MessageHandler(filters.TEXT & filters.Regex("^اضافه قائمه$"), add_list_start),
            MessageHandler(filters.TEXT & filters.Regex("^اضف نص$"), add_txt_start)
        ],
        states={
            DELETE_LIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_text_list)],
            DELETE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_text_done)],
            ADD_LIST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_list_name)],
            ADD_LIST_TEXTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_list_texts)],
            ADD_TXT_LIST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_txt_list_name)],
            ADD_TXT_LIST_TEXTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_txt_list_texts)],
        },
        fallbacks=[MessageHandler(filters.COMMAND, delete_text_cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(check_subscription, pattern="check_subscription"))
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # start polling (this will block)
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()