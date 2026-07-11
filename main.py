import os
import json
import logging
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, 
    KeyboardButton
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    ContextTypes, 
    filters
)

# إعداد السجلات (Logging) لتتبع الأخطاء
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- الإعدادات الأساسية والثوابت ---
TOKEN = "8811163076:AAHlcXGmsZcAFQM_Or4jlVD-luIsDo9cxnI"
ADMIN_ID = 8529336745
DB_FILE = "database.json"
USD_TO_JOD = 0.71  # سعر الصرف الافتراضي

# --- إدارة قاعدة البيانات (JSON) ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {
        "users": {},        # id: {name, balance_usd, discount}
        "categories": {},   # id: {name, parent_id, sub_categories: [], products: []}
        "products": {},     # id: {name, description, price_usd, parent_id}
        "orders": {},       # id: {user_id, type: 'buy'/'charge', details, status}
        "profit_margin": 0.0 # نسبة الربح العامة (مثال: 0.04 تعني 4%)
    }

def save_db(db_data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db_data, f, ensure_ascii=False, indent=4)

db = load_db()

# مساعدة في تتبع الحالات المؤقتة للمستخدمين أثناء المحادثة (FSM يدوي بسيط)
USER_STATES = {}

# --- دالات مساعدة للحسابات والأسعار ---
def calculate_prices(product_price_usd, user_discount_pct):
    # إضافة نسبة الربح أولاً
    price_with_profit = product_price_usd * (1 + db.get("profit_margin", 0.0))
    # تطبيق خصم الزبون الخاص
    final_usd = price_with_profit * (1 - (user_discount_pct / 100.0))
    final_jod = final_usd * USD_TO_JOD
    return round(final_usd, 2), round(final_jod, 2)

# --- أزرار الكيبورد الرئيسية ---
def get_main_keyboard(user_id):
    keyboard = [
        [KeyboardButton("🏪 المتجر"), KeyboardButton("👤 حسابي")],
        [KeyboardButton("📦 طلباتي"), KeyboardButton("💰 شحن الرصيد")],
        [KeyboardButton("📞 الدعم الفني")]
    ]
    if user_id == ADMIN_ID:
        keyboard.append([KeyboardButton("👑 لوحة التحكم للآدمن")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- بدء تشغيل البوت ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u_id = str(user.id)
    
    # تسجيل الزبون إن لم يكن مسجلاً
    if u_id not in db["users"]:
        db["users"][u_id] = {
            "name": user.full_name,
            "balance_usd": 0.0,
            "discount": 0.0
        }
        save_db(db)
        
    await update.message.reply_text(
        f"👋 أهلاً بك في بوت *ALEX CARD* المتميز.\nيسعدنا خدمتك! اختر قسماً من القائمة بالأسفل.",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(user.id)
    )

# --- معالجة الرسائل النصية وقوائم الأزرار التفاعلية ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    u_id = str(user_id)
    
    # تأمين تسجيل الزبون
    if u_id not in db["users"]:
        db["users"][u_id] = {"name": update.effective_user.full_name, "balance_usd": 0.0, "discount": 0.0}
        save_db(db)

    # 1. قائمة المتجر للزبون
    if text == "🏪 المتجر":
        USER_STATES[user_id] = {}
        await show_store_category(update, context, "root")
        return

    # 2. حسابي
    elif text == "👤 حسابي":
        u_data = db["users"][u_id]
        bal_usd = u_data["balance_usd"]
        bal_jod = round(bal_usd * USD_TO_JOD, 2)
        disc = u_data["discount"]
        msg = (
            f"👤 *معلومات حسابك الخاص:*\n\n"
            f"🆔 الآيدي الخاص بك: `{u_id}`\n"
            f"👤 الاسم: *{u_data['name']}*\n"
            f"💰 الرصيد بالدولار: `${bal_usd}`\n"
            f"🇯🇴 الرصيد بالدينار: `{bal_jod} JOD`\n"
            f"📉 نسبة خصمك الخاصة: %{disc}"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    # 3. طلباتي
    elif text == "📦 طلباتي":
        user_orders = [o_id for o_id, o in db["orders"].items() if str(o["user_id"]) == u_id and o["status"] == "pending"]
        if not user_orders:
            await update.message.reply_text("📭 ليس لديك أي طلبات قيد المراجعة حالياً.")
        else:
            msg = "⏳ *طلباتك قيد المراجعة والتدقيق:*\n\n"
            for o_id in user_orders:
                o = db["orders"][o_id]
                msg += f"📋 رقم الطلب: `{o_id}`\n🔹 التفاصيل: {o['details']}\n-------------------------\n"
            await update.message.reply_text(msg, parse_mode="Markdown")
        return

    # 4. شحن الرصيد
    elif text == "💰 شحن الرصيد":
        keyboard = [
            [InlineKeyboardButton("🇯🇴 أورنج موني (الأردن)", callback_data="charge_orange")],
            [InlineKeyboardButton("🌍 شحن لجميع الدول العربية والأجنبية", callback_data="charge_global")]
        ]
        await update.message.reply_text("⚡️ يرجى اختيار وسيلة الشحن المناسبة لك:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # 5. الدعم الفني
    elif text == "📞 الدعم الفني":
        msg = (
            "📌 *قسم الدعم الفني وخدمة العملاء:*\n\n"
            "🟢 واتساب: +962776445110\n"
            "🔵 تليجرام: @htb1b\n\n"
            "تواصل معنا في أي وقت، نحن هنا لمساعدتك!"
        )
        await update.message.reply_text(msg)
        return

    # 6. لوحة تحكم الآدمن
    elif text == "👑 لوحة التحكم للآدمن" and user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("🏪 إدارة أقسام ومتجر البوت", callback_data="admin_store_root")],
            [InlineKeyboardButton("👥 قائمة ومراقبة الزبائن", callback_data="admin_users")],
            [InlineKeyboardButton("📢 إرسال إعلان (جماعي / خاص)", callback_data="admin_broadcast")],
            [InlineKeyboardButton("📉 إدارة الخصومات المخصصة", callback_data="admin_discounts")],
            [InlineKeyboardButton("📈 تعيين نسبة الربح العامة", callback_data="admin_profit")]
        ]
        await update.message.reply_text("⚙️ *مرحباً بك في لوحة تحكم الآدمن الحصرية:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # --- معالجة المدخلات النصية التشعبية (انتظار ردود مستخدم أو آدمن) ---
    state = USER_STATES.get(user_id, {})
    action = state.get("action")

    if action == "wait_info_buy":
        p_id = state["prod_id"]
        prod = db["products"][p_id]
        u_disc = db["users"][u_id]["discount"]
        final_usd, final_jod = calculate_prices(prod["price_usd"], u_disc)
        
        # التأكد من الرصيد أولاً
        if db["users"][u_id]["balance_usd"] < final_usd:
            await update.message.reply_text("❌ رصيدك الحالي غير كافي لإتمام هذه العملية! يرجى شحن حسابك أولاً.")
            USER_STATES[user_id] = {}
            return
            
        o_id = str(len(db["orders"]) + 1001)
        db["orders"][o_id] = {
            "user_id": user_id,
            "type": "buy",
            "prod_id": p_id,
            "details": f"شراء منتج: {prod['name']} | معلومات العميل: {text}",
            "status": "pending",
            "cost_usd": final_usd
        }
        save_db(db)
        
        # إرسال إشعار للآدمن
        admin_keyboard = [
            [InlineKeyboardButton("✅ قبول الطلب", callback_data=f"approve_buy_{o_id}"),
             InlineKeyboardButton("❌ رفض الطلب", callback_data=f"reject_buy_{o_id}")]
        ]
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🛒 *طلب شراء جديد مروّس برقم* (`{o_id}`):\n\n"
                 f"👤 العميل: *{update.effective_user.full_name}* (`{u_id}`)\n"
                 f"📦 المنتج: {prod['name']}\n"
                 f"💰 السعر النهائي: `${final_usd}` | `{final_jod} JOD`\n"
                 f"📝 البيانات المرسلة: {text}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(admin_keyboard)
        )
        await update.message.reply_text("⏳ تم إرسال طلبك ومستنداتك بنجاح إلى الإدارة. الطلب الآن تحت المراجعة الفورية.")
        USER_STATES[user_id] = {}

    elif action == "wait_orange_text":
        # طلب شحن الرصيد نصياً
        o_id = str(len(db["orders"]) + 1001)
        db["orders"][o_id] = {
            "user_id": user_id,
            "type": "charge_text",
            "details": f"طلب شحن محفظة أورنج موني، نص التحويل: {text}",
            "status": "pending"
        }
        save_db(db)
        
        admin_keyboard = [
            [InlineKeyboardButton("✅ قبول وإدخال الرصيد", callback_data=f"approve_charge_{o_id}"),
             InlineKeyboardButton("❌ رفض التحويل", callback_data=f"reject_charge_{o_id}")]
        ]
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"💰 *طلب شحن رصيد جديد (نصي)* (`{o_id}`):\n\n"
                 f"👤 العميل: *{update.effective_user.full_name}* (`{u_id}`)\n"
                 f"📄 نص الحوالة المستلم:\n{text}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(admin_keyboard)
        )
        await update.message.reply_text("📥 تم استلام نص الحوالة. يرجى إرسال صورة الحوالة الآن لإكمال الطلب.")
        USER_STATES[user_id] = {"action": "wait_orange_photo", "order_id": o_id}

    elif action == "admin_wait_cat_name":
        p_id = state.get("parent_id", "root")
        c_id = str(len(db["categories"]) + 500)
        db["categories"][c_id] = {"name": text, "parent_id": p_id, "sub_categories": [], "products": []}
        if p_id != "root":
            db["categories"][p_id]["sub_categories"].append(c_id)
        save_db(db)
        await update.message.reply_text(f"✅ تم إضافة القسم الجديد بنجاح: *{text}*", parse_mode="Markdown")
        USER_STATES[user_id] = {}

    elif action == "admin_wait_prod_name":
        c_id = state["cat_id"]
        USER_STATES[user_id] = {"action": "admin_wait_prod_desc", "cat_id": c_id, "name": text}
        await update.message.reply_text("📝 ممتاز، الآن أرسل وصفاً تفصيلياً كاملاً للمنتج:")

    elif action == "admin_wait_prod_desc":
        c_id = state["cat_id"]
        p_name = state["name"]
        USER_STATES[user_id] = {"action": "admin_wait_prod_price", "cat_id": c_id, "name": p_name, "desc": text}
        await update.message.reply_text("💵 حسناً، أرسل سعر المنتج بالدولار الأمريكي كمثال الرقم (10.5):")

    elif action == "admin_wait_prod_price":
        try:
            price = float(text)
        except:
            await update.message.reply_text("❌ عذراً، يرجى إدخال رقم صحيح وصالح (مثال: 15 أو 20.5):")
            return
        c_id = state["cat_id"]
        p_id = str(len(db["products"]) + 700)
        db["products"][p_id] = {
            "name": state["name"],
            "description": state["desc"],
            "price_usd": price,
            "parent_id": c_id
        }
        db["categories"][c_id]["products"].append(p_id)
        save_db(db)
        await update.message.reply_text("✅ تم إنشاء المنتج وإضافته للقسم بنجاح تام!")
        USER_STATES[user_id] = {}

    elif action == "admin_wait_bc_all":
        count = 0
        for uid in db["users"].keys():
            try:
                await context.bot.send_message(chat_id=int(uid), text=f"📢 *إعلان عام من الإدارة:*\n\n{text}", parse_mode="Markdown")
                count += 1
            except:
                pass
        await update.message.reply_text(f"📢 تم إرسال الإعلان بنجاح إلى ({count}) مستخدم.")
        USER_STATES[user_id] = {}

    elif action == "admin_wait_bc_spec_id":
        if text not in db["users"]:
            await update.message.reply_text("❌ هذا الآيدي غير مسجل في البوت إطلاقاً!")
            return
        USER_STATES[user_id] = {"action": "admin_wait_bc_spec_msg", "target_id": text}
        await update.message.reply_text("📝 الآن اكتب رسالة الإعلان الموجهة له حصراً:")

    elif action == "admin_wait_bc_spec_msg":
        t_id = state["target_id"]
        try:
            await context.bot.send_message(chat_id=int(t_id), text=f"🔔 *رسالة خاصة من الإدارة:*\n\n{text}", parse_mode="Markdown")
            await update.message.reply_text("✅ تم إرسال الرسالة الخاصة بنجاح.")
        except Exception as e:
            await update.message.reply_text(f"❌ فشل الإرسال بسبب: {e}")
        USER_STATES[user_id] = {}

    elif action == "admin_wait_disc_id":
        if text not in db["users"]:
            await update.message.reply_text("❌ آيدي الزبون خاطئ أو غير متوفر.")
            return
        USER_STATES[user_id] = {"action": "admin_wait_disc_val", "target_id": text}
        await update.message.reply_text("📉 أدخل نسبة الخصم المئوية المخصصة له (مثال: 5 لـ 5%):")

    elif action == "admin_wait_disc_val":
        try:
            val = float(text)
        except:
            await update.message.reply_text("❌ يرجى إدخال رقم صحيح:")
            return
        t_id = state["target_id"]
        db["users"][t_id]["discount"] = val
        save_db(db)
        await update.message.reply_text(f"✅ تم تطبيق خصم ثابت بنسبة %{val} للزبون رقم `{t_id}`.")
        USER_STATES[user_id] = {}

    elif action == "admin_wait_profit":
        try:
            val = float(text)
        except:
            await update.message.reply_text("❌ أدخل رقم صحيح لنسبة الربح:")
            return
        db["profit_margin"] = val / 100.0
        save_db(db)
        await update.message.reply_text(f"✅ تم تعديل نسبة الربح العامة لتصبح %{val} على جميع منتجات المتجر تلقائياً.")
        USER_STATES[user_id] = {}

    elif action == "admin_wait_charge_amount":
        try:
            amount = float(text)
        except:
            await update.message.reply_text("❌ أدخل قيمة رصيد صحيحة بالرقم:")
            return
        o_id = state["order_id"]
        o = db["orders"][o_id]
        t_uid = str(o["user_id"])
        
        db["users"][t_uid]["balance_usd"] += amount
        o["status"] = "approved"
        save_db(db)
        
        # إشعار العميل
        amount_jod = round(amount * USD_TO_JOD, 2)
        try:
            await context.bot.send_message(
                chat_id=int(t_uid),
                text=f"✅ *تمت الموافقة على شحن رصيدك بنجاح!*\n\n"
                     f"📥 الرصيد المضاف: `${amount}` | `{amount_jod} JOD`\n"
                     f"💰 رصيدك الكلي الحالي: `${db['users'][t_uid]['balance_usd']}`",
                parse_mode="Markdown"
            )
        except:
            pass
        await update.message.reply_text("✅ تم إضافة الرصيد إلى محفظة الزبون وإخطاره في الحين.")
        USER_STATES[user_id] = {}

# --- معالجة الصور المرسلة لشحن الرصيد ---
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = USER_STATES.get(user_id, {})
    
    if state.get("action") == "wait_orange_photo":
        o_id = state["order_id"]
        photo_id = update.message.photo[-1].file_id
        
        # إعادة توجيه الصورة للآدمن
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo_id,
            caption=f"📸 *صورة إيصال التحويل التابعة للطلب رقم:* (`{o_id}`)",
            parse_mode="Markdown"
        )
        await update.message.reply_text("✅ تم إرسال الصورة للإدارة للتحقق الجنائي والمالي من التحويل والموافقة.")
        USER_STATES[user_id] = {}

# --- عرض أقسام المتجر للزبائن ---
async def show_store_category(update: Update, context: ContextTypes.DEFAULT_TYPE, cat_id: str, query=None):
    u_id = str(update.effective_user.id)
    u_disc = db["users"][u_id]["discount"]
    
    buttons = []
    
    # جلب الأقسام الفرعية التابعة للقسم الحالي
    sub_cats = [c_id for c_id, c in db["categories"].items() if c["parent_id"] == cat_id]
    for sc_id in sub_cats:
        buttons.append([InlineKeyboardButton(f"📁 {db['categories'][sc_id]['name']}", callback_data=f"view_cat_{sc_id}")])
        
    # جلب المنتجات التابعة للقسم الحالي
    prods = [p_id for p_id, p in db["products"].items() if p["parent_id"] == cat_id]
    for p_id in prods:
        p = db["products"][p_id]
        f_usd, f_jod = calculate_prices(p["price_usd"], u_disc)
        buttons.append([InlineKeyboardButton(f"🛍️ {p['name']} - (${f_usd} / {f_jod} JOD)", callback_data=f"view_prod_{p_id}")])
        
    # إضافة زر الرجوع السلس
    if cat_id != "root":
        p_id = db["categories"][cat_id]["parent_id"]
        buttons.append([InlineKeyboardButton("🔙 العودة للخلف", callback_data=f"view_cat_{p_id}")])
        
    text = "🏪 *قائمة المتجر - تصفح الأقسام المتاحة:*"
    if cat_id != "root":
        text = f"📁 القسم: *{db['categories'][cat_id]['name']}*"
        
    if query:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

# --- معالجة الضغط على الأزرار المضمنة (Callback Query) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    u_id = str(user_id)
    
    # تصفح الأقسام والمنتجات للزبون
    if data.startswith("view_cat_"):
        cid = data.replace("view_cat_", "")
        await show_store_category(update, context, cid, query=query)
        
    elif data.startswith("view_prod_"):
        pid = data.replace("view_prod_", "")
        prod = db["products"][pid]
        u_disc = db["users"][u_id]["discount"]
        f_usd, f_jod = calculate_prices(prod["price_usd"], u_disc)
        
        msg = (
            f"📦 *اسم المنتج:* {prod['name']}\n\n"
            f"📝 *وصف المنتج:*\n{prod['description']}\n\n"
            f"💰 *السعر النهائي بالدولار:* `${f_usd}`\n"
            f"🇯🇴 *السعر النهائي بالدينار:* `{f_jod} JOD`\n\n"
            f"⚠️ لشراء المنتج، اضغط على زر الشراء بالأسفل لتأكيد المعطيات."
        )
        buttons = [
            [InlineKeyboardButton("🛒 شراء المنتج الآن", callback_data=f"buy_now_{pid}")],
            [InlineKeyboardButton("🔙 رجوع", callback_data=f"view_cat_{prod['parent_id']}")]
        ]
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
        
    elif data.startswith("buy_now_"):
        pid = data.replace("buy_now_", "")
        USER_STATES[user_id] = {"action": "wait_info_buy", "prod_id": pid}
        await context.bot.send_message(chat_id=user_id, text="📝 * (أقراء الوصف لمعرفة ماذا ترسل ) يرجى كتابة وإرسال المعلومات اللازمة المطلوبة لتسليمك المنتج فوراً:*")

    # نظام الشحن للزبون
    elif data == "charge_orange":
        msg = (
            f"🇯🇴 *معلومات تحويل محفظة أورنج موني:*\n\n"
            f"📱 رقم المحفظة: `0776445110`\n"
            f"💼 نوع المحفظة: أورنج موني\n"
            f"👤 اسم صاحب المحفظة: *SALMAN NOUH SALMAN AL-BADAREEN*\n\n"
            f"📥 بعد قيامك بالتحويل، يرجى كتابة وإرسال *الاسم الرباعي او الثلاثي لصاحب المحفظة ومبلغ الذي حولته بنفس الرسالة* ، بالرد على هذه الرسالة مباشرة:"
        )
        USER_STATES[user_id] = {"action": "wait_orange_text"}
        await query.edit_message_text(msg, parse_mode="Markdown")
        
    elif data == "charge_global":
        msg = (
            "🌍 *شحن الرصيد لجميع الدول العربية والأجنبية:*\n\n"
            "نوفر طرق دفع متعددة ومتنوعة تناسب بلدك المقيم به (سواء كنت في سوريا، مصر، العراق، أو أي دولة أخرى).\n\n"
            "💬 يرجى التواصل مع الإدارة مباشرة وإرسال اسم بلدك ليتم تزويدك بطرق التحويل المتاحة لك فوراً:\n"
            "✈️ تليجرام الإدارة: @htb1b"
        )
        await query.edit_message_text(msg)
async def add_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # التأكد من هوية الأدمن
    if update.effective_user.id != ADMIN_ID:
        return

    # التحقق من المدخلات
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("⚠️ الصيغة الصحيحة: /add_balance [ID] [المبلغ]")
        return

    try:
        target_uid = str(context.args[0]) # ID الزبون
        amount_usd = float(context.args[1]) # المبلغ
        
        # التأكد أن المستخدم مسجل في قاعدة بيانات JSON
        if target_uid not in db["users"]:
            await update.message.reply_text("❌ هذا المستخدم غير مسجل في البوت!")
            return
            
        # إضافة الرصيد إلى ملف الـ JSON
        db["users"][target_uid]["balance_usd"] += amount_usd
        save_db(db) # حفظ التغييرات فوراً
        
        # إشعار الأدمن
        await update.message.reply_text(f"✅ تمت إضافة {amount_usd}$ للزبون {target_uid} بنجاح.")
        
        # إشعار الزبون
        try:
            await context.bot.send_message(chat_id=int(target_uid), text=f"💰 تم شحن رصيدك بمبلغ {amount_usd}$.")
        except:
            pass 
            
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")

    # --- عمليات لوحة تحكم الآدمن ---
elif user_id == ADMIN_ID:
        if data.startswith("admin_store_"):
            cat_id = data.replace("admin_store_", "")
            buttons = [
                [InlineKeyboardButton("➕ إضافة قسم فرعي هنا", callback_data=f"ad_add_cat_{cat_id}")],
                [InlineKeyboardButton("➕ إضافة منتج داخل هذا القسم", callback_data=f"ad_add_prod_{cat_id}")]
            ]
            
            sub_cats = [c_id for c_id, c in db["categories"].items() if c["parent_id"] == cat_id]
            for sc_id in sub_cats:
                buttons.append([
                    InlineKeyboardButton(f"📁 {db['categories'][sc_id]['name']}", callback_data=f"admin_store_{sc_id}"),
                    InlineKeyboardButton("❌ حذف", callback_data=f"ad_del_cat_{sc_id}")
                ])
                
            prods = [p_id for p_id, p in db["products"].items() if p["parent_id"] == cat_id]
            for p_id in prods:
                buttons.append([
                    InlineKeyboardButton(f"🛍️ {db['products'][p_id]['name']}", callback_data="none"),
                    InlineKeyboardButton("❌ حذف", callback_data=f"ad_del_prod_{p_id}")
                ])
                
            if cat_id != "root":
                p_id = db["categories"][cat_id]["parent_id"]
                buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"admin_store_{p_id}")])
                
            await query.edit_message_text(f"⚙️ إدارة الأقسام والمنتجات للقسم الحالي: ({cat_id})", reply_markup=InlineKeyboardMarkup(buttons))
            
        elif data.startswith("ad_add_cat_"):
            pid = data.replace("ad_add_cat_", "")
            USER_STATES[user_id] = {"action": "admin_wait_cat_name", "parent_id": pid}
            await context.bot.send_message(chat_id=ADMIN_ID, text="📝 أرسل اسم القسم الجديد المراد إنشاؤه:")
            
        elif data.startswith("ad_add_prod_"):
            cid = data.replace("ad_add_prod_", "")
            USER_STATES[user_id] = {"action": "admin_wait_prod_name", "cat_id": cid}
            await context.bot.send_message(chat_id=ADMIN_ID, text="📝 أرسل اسم المنتج الجديد:")
            
        elif data.startswith("ad_del_cat_"):
            cid = data.replace("ad_del_cat_", "")
            p_id = db["categories"][cid]["parent_id"]
            # حذف من الأب
            if p_id != "root":
                db["categories"][p_id]["sub_categories"].remove(cid)
            db["categories"].pop(cid, None)
            save_db(db)
            await query.edit_message_text("✅ تم حذف القسم بالكامل نجاح.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 تحديث", callback_data=f"admin_store_{p_id}")]]))
            
        elif data.startswith("ad_del_prod_"):
            pid = data.replace("ad_del_prod_", "")
            c_id = db["products"][pid]["parent_id"]
            db["categories"][c_id]["products"].remove(pid)
            db["products"].pop(pid, None)
            save_db(db)
            await query.edit_message_text("✅ تم حذف المنتج بنجاح من المتجر.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 تحديث", callback_data=f"admin_store_{c_id}")]]))

        elif data == "admin_users":
            msg = "👥 *قائمة جميع المشتركين والزبائن في البوت:*\n\n"
            for uid, u in db["users"].items():
                b_usd = u["balance_usd"]
                b_jod = round(b_usd * USD_TO_JOD, 2)
                msg += f"👤 الاسم: {u['name']}\n🆔 الآيدي: `{uid}`\n💰 الرصيد: `${b_usd}` / `{b_jod} JOD`\n-------------------------\n"
            await context.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode="Markdown")

        elif data == "admin_broadcast":
            keyboard = [
                [InlineKeyboardButton("📢 إرسال للجميع", callback_data="bc_all")],
                [InlineKeyboardButton("👤 إرسال لشخص محدد", callback_data="bc_spec")]
            ]
            await query.edit_message_text("📢 حدد نوع الإعلان المطلوب:", reply_markup=InlineKeyboardMarkup(keyboard))
            
        elif data == "bc_all":
            USER_STATES[user_id] = {"action": "admin_wait_bc_all"}
            await context.bot.send_message(chat_id=ADMIN_ID, text="📝 اكتب الآن رسالة الإعلان الجماعي ليتم بثها فوراً:")
            
        elif data == "bc_spec":
            USER_STATES[user_id] = {"action": "admin_wait_bc_spec_id"}
            await context.bot.send_message(chat_id=ADMIN_ID, text="🆔 أرسل آيدي الشخص (Telegram ID) المراد مراسلته بدقة:")

        elif data == "admin_discounts":
            USER_STATES[user_id] = {"action": "admin_wait_disc_id"}
            await context.bot.send_message(chat_id=ADMIN_ID, text="🆔 أدخل معرف آيدي الزبون المراد عمل خصم مخصص ومستدام له:")

        elif data == "admin_profit":
            USER_STATES[user_id] = {"action": "admin_wait_profit"}
            await context.bot.send_message(chat_id=ADMIN_ID, text="📈 أدخل نسبة الربح العامة كأرقام فقط (مثال: ادخل 4 لنسبة 4%):")

        # معالجة قرارات الشراء والشحن من الآدمن للطلبات
        elif data.startswith("approve_buy_"):
            oid = data.replace("approve_buy_", "")
            o = db["orders"][oid]
            t_uid = str(o["user_id"])
            cost = o["cost_usd"]
            
            if db["users"][t_uid]["balance_usd"] >= cost:
                db["users"][t_uid]["balance_usd"] -= cost
                o["status"] = "approved"
                save_db(db)
                try:
                    await context.bot.send_message(chat_id=int(t_uid), text=f"🎉 *تم قبول طلب الشراء رقم* (`{oid}`) *بنجاح!*\nتم تسليم طلبك وخصم القيمة المالية من رصيدك الحالي.", parse_mode="Markdown")
                except: pass
                await query.edit_message_text(f"✅ تم قبول طلب الشراء رقم {oid} وتم الخصم من حسابه بنجاح.")
            else:
                await query.edit_message_text("❌ رصيد الزبون أصبح غير كافٍ الآن لإتمام العملية!")

        elif data.startswith("reject_buy_"):
            oid = data.replace("reject_buy_", "")
            o = db["orders"][oid]
            o["status"] = "rejected"
            save_db(db)
            try:
                await context.bot.send_message(chat_id=o["user_id"], text="❌ *للأسف، تم رفض طلب الشراء الخاص بك.*\nيرجى التواصل الفوري مع الإدارة لحل المشكلة.")
            except: pass
            await query.edit_message_text(f"❌ تم رفض الطلب رقم {oid} وإبلاغ الزبون.")

        elif data.startswith("approve_charge_"):
            oid = data.replace("approve_charge_", "")
            USER_STATES[user_id] = {"action": "admin_wait_charge_amount", "order_id": oid}
            await context.bot.send_message(chat_id=ADMIN_ID, text="💵 أرسل قيمة الرصيد المطلوب إضافته إلى حساب العميل بالدولار الأمريكي ($):")

        elif data.startswith("reject_charge_"):
            oid = data.replace("reject_charge_", "")
            o = db["orders"][oid]
            o["status"] = "rejected"
            save_db(db)
            try:
                await context.bot.send_message(chat_id=o["user_id"], text="❌ *تم رفض طلب شحن الرصيد والتحويل.*\nيرجى الاتصال بالدعم الفني والإدارة للتحقق من العملية.")
            except: pass
            await query.edit_message_text(f"❌ تم رفض شحن الحوالة للطلب {oid}.")

# --- تشغيل البوت الهيكلي ---
def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(CommandHandler("add_balance", add_balance_command))

    # تشغيل مستمر دون انقطاع
    application.run_polling()

if __name__ == "__main__":
    main()
