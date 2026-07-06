import telebot
import json
import os
from telebot import types

TOKEN = "8811163076:AAHlcXGmsZcAFQM_Or4jlVD-luIsDo9cxnI"
ADMIN_ID = 8529336745
bot = telebot.TeleBot(TOKEN)
DB_FILE = "alex_data.json"

def load():
    if not os.path.exists(DB_FILE): return {"users": {}, "store": {}, "orders": []}
    with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)

def save(data):
    with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)

@bot.message_handler(commands=['start'])
def start(message):
    data = load()
    if str(message.chat.id) not in data['users']:
        data['users'][str(message.chat.id)] = {"name": message.from_user.first_name, "balance": 0.0, "discount": 0}
        save(data)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🛍️ المتجر", "📦 طلباتي", "👤 حسابي", "💳 شحن الرصيد", "🎧 الدعم الفني")
    if message.chat.id == ADMIN_ID: markup.add("🛠️ لوحة الإدارة")
    bot.send_message(message.chat.id, "أهلاً بك في ALEX CARD", reply_markup=markup)

# --- نظام الطلبات التفاعلي (الأزرار تحت الرسالة) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    data = load()
    action, user_id = call.data.split("_")
    
    if action == "accept":
        # خصم الرصيد أو إضافة الرصيد حسب نوع الطلب
        bot.answer_callback_query(call.id, "تم القبول")
        bot.send_message(user_id, "✅ تم قبول طلبك!")
    elif action == "reject":
        bot.answer_callback_query(call.id, "تم الرفض")
        bot.send_message(user_id, "❌ تم رفض طلبك، يرجى التواصل مع الإدارة.")

# --- قسم شحن الرصيد مع الأزرار ---
@bot.message_handler(func=lambda m: m.text == "💳 شحن الرصيد")
def charge(message):
    msg = "لشحن الرصيد حول لـ 0776445110 أرسل نص الحوالة:"
    bot.send_message(message.chat.id, msg)
    bot.register_next_step_handler(message, lambda m: send_charge_to_admin(m))

def send_charge_to_admin(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ قبول", callback_data=f"accept_{message.chat.id}"),
               types.InlineKeyboardButton("❌ رفض", callback_data=f"reject_{message.chat.id}"))
    bot.send_message(ADMIN_ID, f"طلب شحن من {message.from_user.first_name}:\n{message.text}", reply_markup=markup)

# --- قسم حسابي مع الخصم ---
@bot.message_handler(func=lambda m: m.text == "👤 حسابي")
def account(message):
    data = load()
    u = data['users'].get(str(message.chat.id), {"balance": 0, "discount": 0})
    text = (f"👤 الاسم: `{message.from_user.first_name}`\n"
            f"🆔 الآيدي: `{message.chat.id}`\n\n"
            f"💰 الرصيد: `{u['balance']}` $\n"
            f"📉 نسبة الخصم: `{u['discount']}%`")
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# --- لوحة الإدارة ---
@bot.message_handler(func=lambda m: m.text == "🛠️ لوحة الإدارة")
def admin_panel(message):
    if message.chat.id != ADMIN_ID: return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("👥 الزبائن", "📢 إرسال إعلان", "📉 إدارة الخصومات", "🔙 رجوع")
    bot.send_message(message.chat.id, "لوحة التحكم:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "👥 الزبائن")
def list_users(message):
    data = load()
    text = "\n".join([f"{u['name']} | ID: `{uid}`" for uid, u in data['users'].items()])
    bot.send_message(ADMIN_ID, text or "لا يوجد زبائن", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📢 إرسال إعلان")
def broadcast(message):
    msg = bot.send_message(ADMIN_ID, "أرسل نص الإعلان:")
    bot.register_next_step_handler(msg, lambda m: [bot.send_message(uid, m.text) for uid in load()['users']])

bot.infinity_polling()
