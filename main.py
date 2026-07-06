import telebot
import json
import os
from telebot import types

TOKEN = "8811163076:AAHlcXGmsZcAFQM_Or4jlVD-luIsDo9cxnI"
ADMIN_ID = 8529336745
bot = telebot.TeleBot(TOKEN)
DB_FILE = "alex_data.json"
EXCHANGE_RATE = 0.71 # 1 دولار = 0.71 دينار (يمكنك تعديلها)

def load():
    if not os.path.exists(DB_FILE): return {"users": {}, "store": {}, "orders": []}
    with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)

def save(data):
    with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)

# --- كيبوردات التحكم ---
def main_kb(user_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🛍️ المتجر", "📦 طلباتي", "👤 حسابي", "💳 شحن الرصيد", "🎧 الدعم الفني")
    if user_id == ADMIN_ID: kb.add("🛠️ لوحة الإدارة")
    return kb

@bot.message_handler(commands=['start'])
def start(message):
    data = load()
    if str(message.chat.id) not in data['users']:
        data['users'][str(message.chat.id)] = {"name": message.from_user.first_name, "balance": 0.0, "discount": 0}
        save(data)
    bot.send_message(message.chat.id, "أهلاً بك في ALEX CARD", reply_markup=main_kb(message.chat.id))

# --- قسم حسابي ---
@bot.message_handler(func=lambda m: m.text == "👤 حسابي")
def account(message):
    data = load()
    u = data['users'].get(str(message.chat.id), {"balance": 0, "discount": 0})
    b_usd = u['balance']
    b_jod = b_usd * EXCHANGE_RATE
    text = (f"👤 الاسم: `{message.from_user.first_name}`\n"
            f"🆔 الآيدي: `{message.chat.id}`\n\n"
            f"💰 الرصيد: `{b_usd}$` | `{b_jod:.2f} JOD`\n"
            f"📉 الخصم: `{u['discount']}%`")
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# --- قسم شحن الرصيد ---
@bot.message_handler(func=lambda m: m.text == "💳 شحن الرصيد")
def charge(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True).add("🟧 أورنج موني", "🔙 رجوع")
    bot.send_message(message.chat.id, "اختر وسيلة الشحن:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🟧 أورنج موني")
def orange_info(message):
    text = ("معلومات التحويل:\n"
            "المحفظة: `0776445110`\n"
            "الاسم: `سلمان نوح سلمان البدارين`\n"
            "أورنج موني\n\n"
            "الآن، أرسل نص الحوالة هنا:")
    msg = bot.send_message(message.chat.id, text, parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_charge)

def process_charge(message):
    data = load()
    order_id = len(data['orders']) + 1
    data['orders'].append({"id": order_id, "user": message.chat.id, "text": message.text, "type": "charge"})
    save(data)
    markup = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("✅ قبول", callback_data=f"accept_{order_id}"),
        types.InlineKeyboardButton("❌ رفض", callback_data=f"reject_{order_id}")
    )
    bot.send_message(ADMIN_ID, f"🔔 طلب شحن جديد ({order_id})\nمن: {message.from_user.first_name}\nنص الحوالة: {message.text}", reply_markup=markup)
    bot.send_message(message.chat.id, "تم إرسال الطلب للإدارة.")

# --- لوحة الأدمن ---
@bot.message_handler(func=lambda m: m.text == "🛠️ لوحة الإدارة")
def admin_panel(message):
    if message.chat.id != ADMIN_ID: return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True).add("📦 طلبات الزبائن", "👥 الزبائن", "📉 إدارة الخصومات", "🔙 رجوع")
    bot.send_message(message.chat.id, "أهلاً أدمن:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    data = load()
    action, oid = call.data.split("_")
    order = next((o for o in data['orders'] if o['id'] == int(oid)), None)
    
    if action == "accept" and order:
        if order['type'] == "charge":
            # هنا نضيف الرصيد (بإمكانك إضافة خطوة إدخال المبلغ)
            data['users'][str(order['user'])]['balance'] += 10 # تجريبي
            save(data)
            bot.send_message(order['user'], "تم إضافة الرصيد بنجاح!")
            bot.edit_message_text("✅ تم القبول", ADMIN_ID, call.message.message_id)
    elif action == "reject":
        bot.send_message(order['user'], "❌ تم الرفض، يرجى التواصل مع الإدارة.")
        bot.edit_message_text("❌ تم الرفض", ADMIN_ID, call.message.message_id)

bot.infinity_polling()
