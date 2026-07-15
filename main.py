import logging
import sqlite3
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
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

# إعداد السجلات (Logs) لمراقبة الأخطاء
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- الثوابت والبيانات الأساسية ---
BOT_TOKEN = "8811163076:AAHlcXGmsZcAFQM_Or4jlVD-luIsDo9cxnI"
ADMIN_ID = 8529336745  # الآيدي الخاص بك كمدير للبوت

# سعر الصرف الثابت (1 دولار = 0.71 دينار أردني تقريباً)
USD_TO_JOD = 0.71

# حالات المحادثات المتعددة (Conversation States)
(
    # حالات إضافة وحذف الأقسام والمنتجات
    ADD_CATEGORY_NAME,
    ADD_PRODUCT_NAME,
    ADD_PRODUCT_DESC,
    ADD_PRODUCT_PRICE_USD,
    ADD_PRODUCT_INFO_REQ,
    
    # حالات شراء المنتج والطلب
    BUY_SEND_INFO,
    
    # حالات الشحن بالصور والنص
    DEPOSIT_SEND_PROOF,
    DEPOSIT_CONFIRM_AMOUNT,
    
    # حالات لوحة التحكم الإدارية
    ADMIN_SEND_AD,
    ADMIN_SEND_AD_SINGLE_ID,
    ADMIN_SEND_AD_SINGLE_TEXT,
    ADMIN_SET_DISCOUNT_ID,
    ADMIN_SET_DISCOUNT_VAL,
    ADMIN_SET_PROFIT
) = range(15)


# =====================================================================
#             إعداد قاعدة البيانات وحفظ كافة العمليات والبيانات
# =====================================================================
def init_db():
    conn = sqlite3.connect("alex_card_store.db")
    cursor = conn.cursor()
    
    # جدول المستخدمين
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance_usd REAL DEFAULT 0.0,
        discount_percent REAL DEFAULT 0.0
    )
    """)
    
    # جدول الأقسام (تدعم الأقسام الفرعية اللانهائية عن طريق parent_id)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        parent_id INTEGER DEFAULT NULL,
        FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE CASCADE
    )
    """)
    
    # جدول المنتجات
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        price_usd REAL NOT NULL,
        info_required TEXT,
        category_id INTEGER,
        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
    )
    """)
    
    # جدول الإعدادات العامة للبوت (مثل نسبة الربح العام)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    
    # وضع قيمة مبدئية لنسبة الربح (0% افتراضياً)
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('profit_percent', '0')")
    
    conn.commit()
    conn.close()

init_db()


# =====================================================================
#                     دوال مساعدة للعمليات والعملات
# =====================================================================
def get_db_connection():
    conn = sqlite3.connect("alex_card_store.db")
    conn.row_factory = sqlite3.Row
    return conn

def register_user(user_id, username):
    """حفظ بيانات الزبون فور دخوله البوت إن لم يكن مسجلاً سابقاً"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return user

def get_profit_percent():
    conn = get_db_connection()
    row = conn.execute("SELECT value FROM settings WHERE key = 'profit_percent'").fetchone()
    conn.close()
    return float(row['value']) if row else 0.0

def calculate_final_price(base_price_usd, user_id):
    """حساب السعر النهائي بعد إضافة نسبة ربح الإدارة وخصم نسبة الزبون الخاصة"""
    profit = get_profit_percent()
    user = get_user_data(user_id)
    discount = user['discount_percent'] if user else 0.0
    
    # إضافة نسبة الربح أولاً
    price_after_profit = base_price_usd * (1 + profit / 100.0)
    # تطبيق خصم الزبون الفردي ثانياً
    final_price_usd = price_after_profit * (1 - discount / 100.0)
    
    final_price_jod = final_price_usd * USD_TO_JOD
    return round(final_price_usd, 2), round(final_price_jod, 2)


# =====================================================================
#                        لوحات المفاتيح والقوائم
# =====================================================================
def get_main_keyboard(user_id):
    """القائمة الرئيسية لزبائن البوت"""
    buttons = [
        [KeyboardButton("🛍️ المتجر"), KeyboardButton("👤 حسابي")],
        [KeyboardButton("📦 طلباتي"), KeyboardButton("💳 شحن الرصيد")],
        [KeyboardButton("📞 الدعم الفني")]
    ]
    # إذا كان المستخدم هو الآدمن تظهر له كبسة لوحة التحكم كزر إضافي منفصل تحت
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton("⚙️ لوحة التحكم الإدارية")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


# =====================================================================
#                       معالجة الأوامر الأساسية
# =====================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.first_name)
    
    welcome_text = (
        f"🙋‍♂️ *أهلاً بك في بوت ALEX CARD*\n\n"
        f"أفضل المنصات لشحن الألعاب والبطاقات الرقمية والخدمات بسرعة وأمان واحترافية عالية.\n\n"
        f"استخدم أزرار التحكم بالأسفل للتنقل بحرية كاملة 👇"
    )
    await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard(user.id), parse_mode="Markdown")
    return ConversationHandler.END


# =====================================================================
#                القسم الثاني: حسابي والبيانات والخصومات
# =====================================================================
async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_data(user_id)
    
    if not user:
        register_user(user_id, update.effective_user.first_name)
        user = get_user_data(user_id)
        
    balance_usd = user['balance_usd']
    balance_jod = round(balance_usd * USD_TO_JOD, 2)
    discount = user['discount_percent']
    
    acc_text = (
        f"👤 *معلومات حسابك الشخصي*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 معرف الحساب (ID): `{user_id}`\n"
        f"👤 الاسم: {update.effective_user.first_name}\n\n"
        f"💰 *الرصيد المتاح:*\n"
        f"💵 بالدولار: `{balance_usd:.2f}$`\n"
        f"🇯🇴 بالدينار الأردني: `{balance_jod:.2f} JOD`\n\n"
        f"📉 نسبة خصمك الخاصة: %{discount:.1f}\n"
        f"*(الخصم مطبق تلقائياً عند استعراض السلع)*"
    )
    await update.message.reply_text(acc_text, parse_mode="Markdown")


# =====================================================================
#                القسم الخامس: الدعم الفني المباشر
# =====================================================================
async def support_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    support_text = (
        f"📞 *قسم الدعم الفني والمساعدة*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"يسعدنا تواصلكم والرد على كافة استفساراتكم بكل سرور عبر قنواتنا:\n\n"
        f"💬 تليجرام: @htb1b\n"
        f"📱 واتساب: +962776445110\n\n"
        f"اضغط على المعرف أو الرقم مباشرة للتواصل السريع مع الإدارة."
    )
    await update.message.reply_text(support_text, parse_mode="Markdown")


# =====================================================================
#            القسم الأول والآدمن: شجرة الأقسام والمنتجات اللانهائية
# =====================================================================
async def store_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الأقسام الرئيسية (الأولى)"""
    conn = get_db_connection()
    categories = conn.execute("SELECT * FROM categories WHERE parent_id IS NULL").fetchall()
    conn.close()
    
    text = "🛍️ *قائمة الأقسام الرئيسية في المتجر:*\nالرجاء اختيار القسم المطلوب لتصفحه:"
    keyboard = []
    
    for cat in categories:
        keyboard.append([InlineKeyboardButton(f"📁 {cat['name']}", callback_id=f"cat_{cat['id']}")])
        
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    # التفكيك ومعرفة المعرف
    cat_id = int(data.split("_")[1])
    user_id = query.from_user.id
    
    conn = get_db_connection()
    # جلب القسم الحالي لمعرفة الوالد للرجوع
    current_cat = conn.execute("SELECT * FROM categories WHERE id = ?", (cat_id,)).fetchone()
    # جلب الأقسام الفرعية داخل هذا القسم
    subcategories = conn.execute("SELECT * FROM categories WHERE parent_id = ?", (cat_id,)).fetchall()
    # جلب المنتجات الموجودة داخل هذا القسم مباشرة
    products = conn.execute("SELECT * FROM products WHERE category_id = ?", (cat_id,)).fetchall()
    conn.close()
    
    keyboard = []
    
    # 1. عرض الأقسام الفرعية
    for sub in subcategories:
        keyboard.append([InlineKeyboardButton(f"📁 {sub['name']}", callback_id=f"cat_{sub['id']}")])
        
    # 2. عرض المنتجات الموجودة
    for prod in products:
        f_usd, f_jod = calculate_final_price(prod['price_usd'], user_id)
        keyboard.append([InlineKeyboardButton(f"🎁 {prod['name']} ({f_usd}$ / {f_jod}د.أ)", callback_id=f"prod_{prod['id']}")])
        
    # 3. إدراج زر الرجوع الذكي وزر الحذف للآدمن
    back_button = None
    if current_cat['parent_id'] is None:
        back_button = InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_id="store_main")
    else:
        back_button = InlineKeyboardButton("🔙 رجوع للخلف", callback_id=f"cat_{current_cat['parent_id']}")
        
    control_row = [back_button]
    
    # كبسة الحذف تظهر حصراً للآدمن لسهولة التعديل بوضع علامة الحذف
    if user_id == ADMIN_ID:
        control_row.append(InlineKeyboardButton("❌ حذف هذا القسم", callback_id=f"delcat_{cat_id}"))
        
    keyboard.append(control_row)
    
    text = f"📁 *القسم:* {current_cat['name']}\n\nتصفح الخيارات المتاحة في الأسفل:"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def store_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الرجوع إلى الواجهة الرئيسية للأقسام عبر الأزرار المضمنة"""
    query = update.callback_query
    await query.answer()
    
    conn = get_db_connection()
    categories = conn.execute("SELECT * FROM categories WHERE parent_id IS NULL").fetchall()
    conn.close()
    
    text = "🛍️ *قائمة الأقسام الرئيسية في المتجر:*\nالرجاء اختيار القسم المطلوب لتصفحه:"
    keyboard = []
    
    for cat in categories:
        keyboard.append([InlineKeyboardButton(f"📁 {cat['name']}", callback_id=f"cat_{cat['id']}")])
        
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


# =====================================================================
#                   عرض تفاصيل السلعة وعملية الشراء
# =====================================================================
async def product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    prod_id = int(query.data.split("_")[1])
    
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (prod_id,)).fetchone()
    conn.close()
    
    if not product:
        await query.edit_message_text("❌ هذا المنتج لم يعد متوفراً حالياً.")
        return
        
    final_usd, final_jod = calculate_final_price(product['price_usd'], user_id)
    
    desc_text = (
        f"🎁 *تفاصيل المنتج:* {product['name']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📝 *الوصف:*\n{product['description']}\n\n"
        f"💵 *السعر بالدولار:* `{final_usd:.2f}$`\n"
        f"🇯🇴 *السعر بالدينار:* `{final_jod:.2f} JOD`\n\n"
        f"💡 لطلب هذا المنتج، يرجى الضغط على زر الشراء أدناه واستكمال البيانات."
    )
    
    keyboard = [
        [InlineKeyboardButton("🛒 شراء الآن", callback_id=f"buy_{prod_id}")],
        [InlineKeyboardButton("🔙 رجوع", callback_id=f"cat_{product['category_id']}")]
    ]
    
    if user_id == ADMIN_ID:
        keyboard[0].append(InlineKeyboardButton("❌ حذف المنتج", callback_id=f"delprod_{prod_id}"))
        
    await query.edit_message_text(desc_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


# =====================================================================
#             شراء المنتج وتقديم الطلبات ونظام الحفظ المعلق
# =====================================================================
async def start_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    prod_id = int(query.data.split("_")[1])
    
    # حفظ المعرف الخاص بالمنتج الجاري شراؤه داخل سياق الجلسة
    context.user_data['buying_prod_id'] = prod_id
    
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (prod_id,)).fetchone()
    conn.close()
    
    # فحص كفاية الرصيد قبل البدء بالمعاملة
    final_usd, _ = calculate_final_price(product['price_usd'], user_id)
    user = get_user_data(user_id)
    
    if user['balance_usd'] < final_usd:
        await query.message.reply_text("❌ رصيدك الحالي غير كافي لإتمام هذه العملية! يرجى شحن حسابك أولاً بالانتقال إلى قسم الشحن.")
        return ConversationHandler.END
        
    await query.message.reply_text(
        f"✍️ *طلب الشراء:*\n\n"
        f"البيانات المطلوبة لتسليم المنتج:\n👉 `{product['info_required']}`\n\n"
        f"الرجاء كتابة وإرسال كافة البيانات المطلوبة الآن بشكل دقيق في رسالة واحدة:"
    )
    return BUY_SEND_INFO

async def handle_buy_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_info = update.message.text
    prod_id = context.user_data.get('buying_prod_id')
    
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (prod_id,)).fetchone()
    conn.close()
    
    final_usd, final_jod = calculate_final_price(product['price_usd'], user_id)
    
    # إشعار الزبون بتقديم طلبه بنجاح بانتظار الموافقة
    await update.message.reply_text(
        "✅ *تم إرسال طلبك بنجاح!*\n"
        "الطلب الآن تحت المراجعة من قبل الإدارة وسوف يتم إشعارك فوراً بالرد والقبول أو الرفض.",
        reply_markup=get_main_keyboard(user_id),
        parse_mode="Markdown"
    )
    
    # إرسال إشعار فوري للآدمن للموافقة أو الرفض بكبسات تليجرام المضمنة
    admin_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ قبول الطلب", callback_data=f"aprovebuy_{user_id}_{prod_id}_{final_usd:.2f}"),
            InlineKeyboardButton("❌ رفض الطلب", callback_data=f"rejectbuy_{user_id}_{prod_id}")
        ]
    ])
    
    admin_msg = (
        f"🔔 *طلب شراء جديد معلق*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 الزبون: {update.effective_user.first_name} (`{user_id}`)\n"
        f"🎁 المنتج المطلوب: {product['name']}\n"
        f"💵 التكلفة المطلوبة: `{final_usd:.2f}$` ({final_jod:.2f} JOD)\n"
        f"📝 بيانات التحويل والطلب المرسلة:\n"
        f"`{user_info}`"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, reply_markup=admin_markup, parse_mode="Markdown")
    return ConversationHandler.END


# معالجة استجابة المدير لطلب الشراء (قبول / رفض)
async def admin_decision_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    parts = data.split("_")
    action = parts[0]
    user_id = int(parts[1])
    prod_id = int(parts[2])
    
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (prod_id,)).fetchone()
    
    if action == "aprovebuy":
        cost_usd = float(parts[3])
        # فحص مجدد لرصيد الزبون
        user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        
        if user['balance_usd'] < cost_usd:
            await query.edit_message_text(f"❌ تعذر القبول! رصيد الزبون غير كافٍ الآن للخصم تلقائياً.")
            await context.bot.send_message(chat_id=user_id, text="❌ تم إلغاء طلبك لعدم كفاية الرصيد الكافي حالياً.")
            conn.close()
            return
            
        # الخصم من الرصيد وحفظ العملية
        new_balance = user['balance_usd'] - cost_usd
        conn.execute("UPDATE users SET balance_usd = ? WHERE user_id = ?", (new_balance, user_id))
        conn.commit()
        
        # إشعار الزبون بالقبول والسرور
        user_msg = (
            f"🎉 *تهانينا، تم قبول طلب الشراء بنجاح!*\n"
            f"🎁 المنتج: *{product['name']}*\n"
            f"💸 تم خصم: `{cost_usd:.2f}$` ({round(cost_usd * USD_TO_JOD, 2)} JOD) من رصيدك.\n"
            f"رصيدك الحالي المتبقي: `{new_balance:.2f}$`"
        )
        await context.bot.send_message(chat_id=user_id, text=user_msg, parse_mode="Markdown")
        await query.edit_message_text(f"✅ تم قبول طلب الزبون بنجاح وخصم `{cost_usd}$` من حسابه.")
        
    elif action == "rejectbuy":
        # إشعار الزبون بالرفض المنسق
        user_msg = (
            f"❌ *عذراً، تم رفض طلب الشراء الخاص بك لمنتج:*\n"
            f"*{product['name']}*\n\n"
            f"📞 يرجى التواصل مع الإدارة والتحقق من التفاصيل لمساعدتك فوراً."
        )
        await context.bot.send_message(chat_id=user_id, text=user_msg, parse_mode="Markdown")
        await query.edit_message_text("❌ تم رفض طلب الشراء وإرسال إشعار للزبون بالرفض.")
        
    conn.close()


# =====================================================================
#             حذف الأقسام والمنتجات مباشرة من البوت للآدمن
# =====================================================================
async def admin_delete_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.split("_")[1])
    
    conn = get_db_connection()
    conn.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
    conn.commit()
    conn.close()
    
    await query.edit_message_text("✅ تم حذف القسم وجميع تفاصيله ومنتجاته التابعة بنجاح.")

async def admin_delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[1])
    
    conn = get_db_connection()
    conn.execute("DELETE FROM products WHERE id = ?", (prod_id,))
    conn.commit()
    conn.close()
    
    await query.edit_message_text("✅ تم حذف المنتج المحدد بنجاح من قاعدة البيانات.")


# =====================================================================
#               القسم الثالث: طلباتي (الطلبات المعلقة)
# =====================================================================
async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # نستخدم الواجهة البسيطة لعرض الأقسام حالياً، ويمكن توسيعها بقاعدة بيانات الطلبات المتكاملة
    await update.message.reply_text("📦 *قسم طلباتي الجارية والسابقة:*\nلا توجد طلبات قديمة معلقة حالياً لحسابك.")


# =====================================================================
#              القسم الرابع: شحن الرصيد الفوري ببطاقات الصور والتحقق
# =====================================================================
async def deposit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📱 أورنج موني (الأردن)", callback_data="dep_orange")],
        [InlineKeyboardButton("🌍 شحن لجميع الدول العربية والأجنبية", callback_data="dep_global")]
    ]
    text = (
        f"💳 *بوابة شحن الرصيد التلقائي واليدوي*\n\n"
        f"الرجاء اختيار وسيلة الشحن التي تناسبك من الأسفل لتزويدك بالتفاصيل:"
    )
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def deposit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "dep_orange":
        text = (
            f"📱 *طريقة شحن أورنج موني Jordan*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"الرجاء التحويل المباشر إلى المحفظة الرسمية التالية بالبيانات الدقيقة:\n\n"
            f"📞 رقم المحفظة: `0776445110`\n"
            f"💼 نوع المحفظة: أورنج موني (Orange Money)\n"
            f"👤 صاحب المحفظة: سلمان نوح سلمان البدارين\n\n"
            f"⚠️ *خطوة هامة جداً لتوثيق التحويل:*\n"
            f"يرجى إرسال صورة التحويل الواضحة أو نص التحويل المستلم من محفظتك لتوثيق الدفع:"
        )
        await query.message.reply_text(text, parse_mode="Markdown")
        return DEPOSIT_SEND_PROOF
        
    elif data == "dep_global":
        text = (
            f" نوفر طرق دفع متعدده تناسب بلدك ( سواء كنت في سوريا او مصر أو العراق أو أي دولة أخرى) \n"
            f"يرجى التواصل مع الادارة مباشرة وإرسال اسم بلدك ليتم تزويدك بطرق التحويل المتاحة لك فورا \n\n"
            f"التواصل مع الإدارة \n"
            f"تليجرام : @htb1b"
        )
        await query.message.reply_text(text)
        return ConversationHandler.END

async def handle_deposit_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # فحص إذا قام الزبون بإرسال صورة أو نص للحوالة للتحقق منها
    photo = update.message.photo
    caption = update.message.caption or ""
    text_info = update.message.text or ""
    
    await update.message.reply_text(
        "⌛ *تم استلام تفاصيل الحوالة بنجاح!*\n"
        "طلبك معلق الآن للتدقيق وسيتلقى المدير الصورة والنص للمطابقة وتفعيل الرصيد.",
        reply_markup=get_main_keyboard(user_id),
        parse_mode="Markdown"
    )
    
    # إرسال البيانات فوراً للآدمن للتحقق اليدوي والموافقة بكبسة زر مرنة
    admin_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ قبول وإدخال الرصيد", callback_data=f"ap_dep_{user_id}"),
            InlineKeyboardButton("❌ رفض طلب الشحن", callback_data=f"rj_dep_{user_id}")
        ]
    ])
    
    admin_msg = (
        f"💰 *طلب شحن رصيد جديد معلق*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 الزبون: {update.effective_user.first_name} (`{user_id}`)\n"
        f"📝 نص الحوالة والبيانات: {text_info if text_info else caption}"
    )
    
    if photo:
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo[-1].file_id,
            caption=admin_msg,
            reply_markup=admin_markup,
            parse_mode="Markdown"
        )
    else:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_msg,
            reply_markup=admin_markup,
            parse_mode="Markdown"
        )
    return ConversationHandler.END


# معالجة طلب الآدمن لإضافة القيمة للرصيد
async def admin_deposit_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    parts = data.split("_")
    action = parts[0]
    target_user_id = int(parts[2])
    
    if action == "ap":
        # لحفظ الآيدي المستهدف للشحن وسؤال الآدمن كم يريد شحن القيمة له
        context.user_data['deposit_target_user'] = target_user_id
        await query.message.reply_text(
            f"💵 *إضافة الرصيد الحقيقي للمستخدم:* `{target_user_id}`\n\n"
            f"يرجى إرسال القيمة بالدولار الأمريكي المراد إضافتها لحساب الزبون الآن:"
        )
        return DEPOSIT_CONFIRM_AMOUNT
    elif action == "rj":
        user_msg = "❌ *تم رفض طلب شحن الرصيد الخاص بك!*\nيرجى التواصل مع الدعم الفني لحل المشكلة فوراً."
        await context.bot.send_message(chat_id=target_user_id, text=user_msg, parse_mode="Markdown")
        await query.edit_message_text("❌ تم رفض طلب شحن الرصيد وتنبيه الزبون بذلك.")
        return ConversationHandler.END

async def admin_deposit_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount_str = update.message.text
    target_user_id = context.user_data.get('deposit_target_user')
    
    try:
        amount_usd = float(amount_str)
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال رقم صحيح وعشري فقط كالقيمة بالدولار:")
        return DEPOSIT_CONFIRM_AMOUNT
        
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (target_user_id,)).fetchone()
    
    if not user:
        await update.message.reply_text("❌ فشل العثور على هذا المستخدم بقاعدة البيانات للأسف.")
        conn.close()
        return ConversationHandler.END
        
    new_balance = user['balance_usd'] + amount_usd
    conn.execute("UPDATE users SET balance_usd = ? WHERE user_id = ?", (new_balance, target_user_id))
    conn.commit()
    conn.close()
    
    amount_jod = round(amount_usd * USD_TO_JOD, 2)
    new_balance_jod = round(new_balance * USD_TO_JOD, 2)
    
    # إرسال رسالة منسقة وفاخرة للزبون تفيد بنجاح الشحن
    user_msg = (
        f"🎉 *تم إضافة الرصيد بنجاح لحسابك!*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💵 الرصيد المضاف: `{amount_usd:.2f}$` ({amount_jod:.2f} JOD)\n"
        f"💰 رصيدك الكلي الحالي أصبح: `{new_balance:.2f}$` ({new_balance_jod:.2f} JOD)"
    )
    await context.bot.send_message(chat_id=target_user_id, text=user_msg, parse_mode="Markdown")
    await update.message.reply_text(f"✅ تم بنجاح إضافة `{amount_usd}$` إلى رصيد المستخدم: `{target_user_id}`.")
    return ConversationHandler.END


# =====================================================================
#                لوحة التحكم الإدارية الخاصة بالمدير فقط
# =====================================================================
async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ عذراً، لا تمتلك الصلاحيات الكافية للوصول للوحة التحكم الإدارية.")
        return
        
    text = (
        f"⚙️ *مرحباً بك في لوحة تحكم الإدارة (ALEX CARD)*\n\n"
        f"قم باختيار الخيار المطلوب لتعديله مباشرة وبسهولة تامة بالأسفل:"
    )
    keyboard = [
        [InlineKeyboardButton("➕ إضافة قسم", callback_data="adm_addcat"), InlineKeyboardButton("➕ إضافة منتج", callback_data="adm_addprod")],
        [InlineKeyboardButton("👥 قائمة الزبائن والعملاء", callback_data="adm_listusers")],
        [InlineKeyboardButton("📢 إرسال إعلان ترويجي", callback_data="adm_ad")],
        [InlineKeyboardButton("📉 إدارة الخصومات", callback_data="adm_disc"), InlineKeyboardButton("📈 نسبة الربح", callback_data="adm_profit")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_dashboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "adm_addcat":
        # جلب الأقسام المتوفرة لوضع خيار جعل القسم الجديد فرعياً أو رئيساً
        conn = get_db_connection()
        cats = conn.execute("SELECT * FROM categories").fetchall()
        conn.close()
        
        keyboard = [[InlineKeyboardButton("📁 قسم رئيسي جديد", callback_data="addcat_parent_null")]]
        for cat in cats:
            keyboard.append([InlineKeyboardButton(f"📁 فرعي من: {cat['name']}", callback_data=f"addcat_parent_{cat['id']}")])
            
        await query.message.reply_text("اختر أين تود إدراج هذا القسم الجديد:", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data == "adm_addprod":
        # اختيار القسم الذي يتبع له المنتج الجديد
        conn = get_db_connection()
        cats = conn.execute("SELECT * FROM categories").fetchall()
        conn.close()
        
        if not cats:
            await query.message.reply_text("❌ يرجى إضافة قسم واحد على الأقل أولاً قبل البدء بإضافة المنتجات!")
            return
            
        keyboard = []
        for cat in cats:
            keyboard.append([InlineKeyboardButton(cat['name'], callback_data=f"addprod_cat_{cat['id']}")])
            
        await query.message.reply_text("اختر القسم الذي ينتمي إليه المنتج الجديد:", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data == "adm_listusers":
        conn = get_db_connection()
        users = conn.execute("SELECT * FROM users").fetchall()
        conn.close()
        
        if not users:
            await query.message.reply_text("❌ لا يوجد زبائن مسجلين حالياً في البوت.")
            return
            
        text = f"👥 *قائمة زبائن البوت المسجلين ({len(users)} زبائن):*\n━━━━━━━━━━━━━━━━━━━\n"
        for user in users:
            jod = round(user['balance_usd'] * USD_TO_JOD, 2)
            text += f"👤 الاسم: {user['username']}\n🆔 المعرف: `{user['user_id']}`\n💰 الرصيد: `{user['balance_usd']:.2f}$` ({jod} JOD)\n📉 خصم خاص: %{user['discount_percent']}\n\n"
            
        await query.message.reply_text(text, parse_mode="Markdown")
        
    elif data == "adm_ad":
        keyboard = [
            [InlineKeyboardButton("📢 إرسال إعلان للجميع", callback_data="ad_all")],
            [InlineKeyboardButton("👤 إرسال إعلان لشخص محدد", callback_data="ad_one")]
        ]
        await query.message.reply_text("اختر نوع الإعلان والجمهور المستهدف حالياً:", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data == "adm_disc":
        await query.message.reply_text("📥 يرجى إدخال ومعرف (ID) الزبون الذي تود تعديل نسبة خصمه الفردية:")
        return ADMIN_SET_DISCOUNT_ID
        
    elif data == "adm_profit":
        curr = get_profit_percent()
        await query.message.reply_text(
            f"📈 *نسبة ربح الإدارة الحالية هي:* %{curr}\n\n"
            f"الرجاء كتابة وإرسال نسبة الربح الجديدة بالنسبة المئوية (بدون رمز %، مثال: 4):"
        )
        return ADMIN_SET_PROFIT


# =====================================================================
#                 تابع: إدارة إضافة الأقسام والمنتجات
# =====================================================================
async def admin_addcat_parent_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    parent_part = data.split("_")[2]
    parent_id = None if parent_part == "null" else int(parent_part)
    
    context.user_data['new_cat_parent_id'] = parent_id
    await query.message.reply_text("✍️ أرسل الآن اسم القسم الجديد الذي تود إضافته:")
    return ADD_CATEGORY_NAME

async def admin_addcat_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    parent_id = context.user_data.get('new_cat_parent_id')
    
    conn = get_db_connection()
    conn.execute("INSERT INTO categories (name, parent_id) VALUES (?, ?)", (name, parent_id))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ تم إضافة قسم *{name}* بنجاح ومزامنته في البوت والظهور الفوري.", parse_mode="Markdown")
    return ConversationHandler.END

# تابع: إضافة منتج
async def admin_addprod_cat_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.split("_")[2])
    
    context.user_data['new_prod_cat_id'] = cat_id
    await query.message.reply_text("✍️ يرجى إدخال اسم المنتج الجديد:")
    return ADD_PRODUCT_NAME

async def admin_addprod_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_prod_name'] = update.message.text
    await update.message.reply_text("✍️ أرسل وصف المنتج وتفاصيله الفنية:")
    return ADD_PRODUCT_DESC

async def admin_addprod_desc_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_prod_desc'] = update.message.text
    await update.message.reply_text("✍️ أرسل سعر المنتج بالدولار الأمريكي (رقم عشري فقط):")
    return ADD_PRODUCT_PRICE_USD

async def admin_addprod_price_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price_str = update.message.text
    try:
        price_usd = float(price_str)
    except ValueError:
        await update.message.reply_text("❌ القيمة المدخلة ليست رقماً صحيحاً، يرجى إعادة إرسال السعر بالدولار:")
        return ADD_PRODUCT_PRICE_USD
        
    context.user_data['new_prod_price_usd'] = price_usd
    await update.message.reply_text("✍️ يرجى تحديد البيانات المطلوبة من الزبون عند الشراء (مثال: 'أرسل كود البطاقة والاسم الكود'):")
    return ADD_PRODUCT_INFO_REQ

async def admin_addprod_info_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info_req = update.message.text
    cat_id = context.user_data.get('new_prod_cat_id')
    name = context.user_data.get('new_prod_name')
    desc = context.user_data.get('new_prod_desc')
    price_usd = context.user_data.get('new_prod_price_usd')
    
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO products (name, description, price_usd, info_required, category_id) VALUES (?, ?, ?, ?, ?)",
        (name, desc, price_usd, info_req, cat_id)
    )
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ تم بنجاح إضافة منتج *{name}* للقسم وإتاحته للزبائن للتداول.", parse_mode="Markdown")
    return ConversationHandler.END


# =====================================================================
#                تابع: لوحة الإعلانات ونسب الأرباح والخصومات
# =====================================================================
async def admin_ad_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "ad_all":
        await query.message.reply_text("✍️ أرسل محتوى نص الإعلان المراد إرساله لجميع الزبائن حالياً:")
        return ADMIN_SEND_AD
    elif data == "ad_one":
        await query.message.reply_text("🆔 يرجى إدخال معرف (ID) الزبون المستهدف بالإعلان:")
        return ADMIN_SEND_AD_SINGLE_ID

async def admin_ad_all_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    conn = get_db_connection()
    users = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    
    success = 0
    for user in users:
        try:
            await context.bot.send_message(chat_id=user['user_id'], text=f"📢 *إعلان هام من الإدارة:*\n\n{text}", parse_mode="Markdown")
            success += 1
        except Exception:
            pass
            
    await update.message.reply_text(f"✅ تم إرسال الإعلان لجميع الزبائن بنجاح (عدد الزبائن الكلي: {success}).")
    return ConversationHandler.END

async def admin_ad_single_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(update.message.text)
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال ID رقمي صحيح للزبون:")
        return ADMIN_SEND_AD_SINGLE_ID
        
    context.user_data['ad_single_user_id'] = user_id
    await update.message.reply_text("✍️ أرسل الآن محتوى الرسالة الترويجية للشخص المحدد:")
    return ADMIN_SEND_AD_SINGLE_TEXT

async def admin_ad_single_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = context.user_data.get('ad_single_user_id')
    
    try:
        await context.bot.send_message(chat_id=user_id, text=f"💬 *رسالة خاصة من الإدارة:*\n\n{text}", parse_mode="Markdown")
        await update.message.reply_text("✅ تم إرسال الرسالة إلى الشخص المحدد بنجاح.")
    except Exception as e:
        await update.message.reply_text(f"❌ تعذر الإرسال بسبب: {str(e)}")
        
    return ConversationHandler.END

# الخصومات الفردية للزبون
async def admin_set_discount_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(update.message.text)
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال ID رقمي صحيح للزبون:")
        return ADMIN_SET_DISCOUNT_ID
        
    context.user_data['discount_target_user_id'] = user_id
    await update.message.reply_text("📉 أدخل نسبة الخصم المراد تفعيلها له (أرقام فقط، مثال: 10 للخصم 10%):")
    return ADMIN_SET_DISCOUNT_VAL

async def admin_set_discount_val_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        discount = float(update.message.text)
    except ValueError:
        await update.message.reply_text("❌ أدخل رقماً مئوياً صحيحاً:")
        return ADMIN_SET_DISCOUNT_VAL
        
    user_id = context.user_data.get('discount_target_user_id')
    
    conn = get_db_connection()
    conn.execute("UPDATE users SET discount_percent = ? WHERE user_id = ?", (discount, user_id))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ تم تعديل نسبة خصم الزبون `{user_id}` لتصبح %{discount} على كافة السلع المعروضة تلقائياً.")
    return ConversationHandler.END

# نسبة الربح العام المطبق على جميع الأسعار تلقائياً
async def admin_set_profit_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        profit = float(update.message.text)
    except ValueError:
        await update.message.reply_text("❌ يرجى إدخال نسبة ربح رقمية صحيحة:")
        return ADMIN_SET_PROFIT
        
    conn = get_db_connection()
    conn.execute("UPDATE settings SET value = ? WHERE key = 'profit_percent'", (str(profit),))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ تم تطبيق النسبة الجديدة للأرباح %{profit} وتطبيقها على كافة أسعار المنتجات في المتجر بنجاح.")
    return ConversationHandler.END


# =====================================================================
#             تجميع البوت وتوصيل المعالجات (Main Loop)
# =====================================================================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # محادثة شراء منتج معلق
    buy_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_buy, pattern="^buy_")],
        states={
            BUY_SEND_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buy_info)]
        },
        fallbacks=[CommandHandler("start", start)]
    )
    
    # محادثة شحن الرصيد
    deposit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(deposit_callback, pattern="^dep_")],
        states={
            DEPOSIT_SEND_PROOF: [MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, handle_deposit_proof)],
            DEPOSIT_CONFIRM_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_deposit_amount_received)]
        },
        fallbacks=[CommandHandler("start", start)]
    )
    
    # محادثة الآدمن لإضافة قسم أو منتج
    admin_add_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_dashboard_callback, pattern="^adm_"),
            CallbackQueryHandler(admin_addcat_parent_selected, pattern="^addcat_parent_"),
            CallbackQueryHandler(admin_addprod_cat_selected, pattern="^addprod_cat_")
        ],
        states={
            ADD_CATEGORY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_addcat_name_received)],
            ADD_PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_addprod_name_received)],
            ADD_PRODUCT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_addprod_desc_received)],
            ADD_PRODUCT_PRICE_USD: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_addprod_price_received)],
            ADD_PRODUCT_INFO_REQ: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_addprod_info_received)],
            
            ADMIN_SEND_AD: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_ad_all_received)],
            ADMIN_SEND_AD_SINGLE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_ad_single_id_received)],
            ADMIN_SEND_AD_SINGLE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_ad_single_text_received)],
            
            ADMIN_SET_DISCOUNT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_discount_id_received)],
            ADMIN_SET_DISCOUNT_VAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_discount_val_received)],
            
            ADMIN_SET_PROFIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_profit_received)]
        },
        fallbacks=[CommandHandler("start", start)]
    )
    
    # الأوامر وقراءة القوائم الأساسية
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^🛍️ المتجر$"), store_menu))
    app.add_handler(MessageHandler(filters.Regex("^👤 حسابي$"), my_account))
    app.add_handler(MessageHandler(filters.Regex("^📦 طلباتي$"), my_orders))
    app.add_handler(MessageHandler(filters.Regex("^💳 شحن الرصيد$"), deposit_menu))
    app.add_handler(MessageHandler(filters.Regex("^📞 الدعم الفني$"), support_info))
    app.add_handler(MessageHandler(filters.Regex("^⚙️ لوحة التحكم الإدارية$"), admin_dashboard))
    
    # معالجة القنوات المضمنة (Callbacks)
    app.add_handler(buy_conv)
    app.add_handler(deposit_conv)
    app.add_handler(admin_add_conv)
    
    app.add_handler(CallbackQueryHandler(admin_ad_callback, pattern="^ad_"))
    app.add_handler(CallbackQueryHandler(store_main_callback, pattern="^store_main$"))
    app.add_handler(CallbackQueryHandler(category_callback, pattern="^cat_"))
    app.add_handler(CallbackQueryHandler(product_callback, pattern="^prod_"))
    app.add_handler(CallbackQueryHandler(admin_delete_category, pattern="^delcat_"))
    app.add_handler(CallbackQueryHandler(admin_delete_product, pattern="^delprod_"))
    app.add_handler(CallbackQueryHandler(admin_decision_buy, pattern="^(aprovebuy|rejectbuy)_"))
    app.add_handler(CallbackQueryHandler(admin_deposit_decision, pattern="^(ap|rj)_dep_"))
    
    # تشغيل البوت للتلقي الفوري والتفاعل (Long Polling)
    logger.info("تم تفعيل وتشغيل بوت المتجر بنجاح!")
    app.run_polling()

if __name__ == "__main__":
    main()
