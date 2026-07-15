import logging
import sqlite3
import json
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler
)

# إعدادات التسجيل ومستوى الأخطاء
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- الثوابت الأساسية ---
BOT_TOKEN = "8811163076:AAHlcXGmsZcAFQM_Or4jlVD-luIsDo9cxnI"
ADMIN_ID = 8529336745
EXCHANGE_RATE = 0.71  # سعر صرف الدولار مقابل الدينار الأردني (1 دولار = 0.71 دينار)

# --- حالات المحادثات (Conversation States) ---
(
    # حالات الأدمن
    A_ADD_CAT, A_ADD_PROD_NAME, A_ADD_PROD_PRICE, A_ADD_PROD_DESC,
    A_BROADCAST_ALL, A_BROADCAST_USER_ID, A_BROADCAST_USER_MSG,
    A_SET_DISCOUNT_ID, A_SET_DISCOUNT_VAL, A_SET_PROFIT,
    A_DEPOSIT_AMOUNT,
    # حالات الزبون
    U_PROD_INFO, U_SUBMIT_DEPOSIT_PROOF
) = range(14)

# --- إعداد قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    # جدول المستخدمين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance_usd REAL DEFAULT 0.0,
            discount_percent REAL DEFAULT 0.0
        )
    ''')
    
    # جدول الأقسام (تسمح بنظام شجري غير محدود عن طريق parent_id)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER DEFAULT NULL
        )
    ''')
    
    # جدول المنتجات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price_usd REAL NOT NULL,
            description TEXT,
            category_id INTEGER,
            FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
        )
    ''')
    
    # جدول إعدادات البوت العامة (مثل نسبة الربح)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # وضع القيمة الافتراضية لنسبة الربح إذا لم تكن موجودة
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('global_profit_percent', '0.0')")
    
    conn.commit()
    conn.close()

init_db()

# --- دالات مساعدة لقاعدة البيانات ---
def get_db():
    return sqlite3.connect('bot_database.db')

def get_profit_percent():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key='global_profit_percent'")
    res = cursor.fetchone()
    conn.close()
    return float(res[0]) if res else 0.0

def calculate_prices(base_price_usd, user_discount_percent):
    """حساب السعر النهائي بالدولار والدينار بعد إضافة نسبة ربح الإدارة وتطبيق خصم الزبون المخصص"""
    profit_pct = get_profit_percent()
    # إضافة ربح الأدمن أولاً
    price_after_profit = base_price_usd * (1 + (profit_pct / 100.0))
    # تطبيق خصم الزبون الخاص
    final_usd = price_after_profit * (1 - (user_discount_percent / 100.0))
    final_jod = final_usd * EXCHANGE_RATE
    return round(final_usd, 2), round(final_jod, 2)

# --- الكيبوردات الرئيسية ---
def get_user_main_keyboard():
    keyboard = [
        [KeyboardButton("🏪 المتجر"), KeyboardButton("👤 حسابي")],
        [KeyboardButton("📦 طلباتي"), KeyboardButton("💰 شحن الرصيد")],
        [KeyboardButton("🛠️ الدعم الفني")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_main_keyboard():
    keyboard = [
        [KeyboardButton("📁 إدارة المتجر"), KeyboardButton("👥 قائمة الزبائن")],
        [KeyboardButton("📢 إرسال إعلان"), KeyboardButton("🎯 إدارة الخصومات")],
        [KeyboardButton("📈 نسبة الربح"), KeyboardButton("🏪 واجهة الزبون")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- نقطة البداية /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db()
    cursor = conn.cursor()
    # تسجيل الزبون إن لم يكن مسجلاً
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, balance_usd, discount_percent) VALUES (?, ?, 0.0, 0.0)", 
                   (user.id, user.full_name))
    conn.commit()
    conn.close()
    
    context.user_data.clear() # تنظيف البيانات المؤقتة
    
    if user.id == ADMIN_ID:
        await update.message.reply_text(
            f"👋 أهلاً بك يا مدير الـ لوحة التحكم مفعّلة بالكامل لك.",
            reply_markup=get_admin_main_keyboard()
        )
    else:
        await update.message.reply_text(
            f"✨ أهلاً بك في بوت **ALEX CARD** الرسمي.\nيسعدنا خدمتك! اختر من القائمة أدناه لبدء التصفح.",
            reply_markup=get_user_main_keyboard(),
            parse_mode="Markdown"
        )
    return ConversationHandler.END

# ==========================================
#          قسم الزبون (USER SIDE)
# ==========================================

async def user_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT balance_usd, discount_percent FROM users WHERE user_id=?", (user_id,))
    user_data = cursor.fetchone()
    if not user_data:
        cursor.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, update.effective_user.full_name))
        conn.commit()
        user_data = (0.0, 0.0)
    conn.close()
    
    bal_usd, disc_pct = user_data
    bal_jod = bal_usd * EXCHANGE_RATE

    if text == "🏪 المتجر" or text == "🔙 العودة للمتجر":
        # عرض الأقسام الرئيسية (التي ليس لها أب)
        return await show_user_categories(update, context, parent_id=None)
        
    elif text == "👤 حسابي":
        msg = (
            f"👤 **معلومات حسابك الشخصي:**\n\n"
            f"🆔 الآيدي الخاص بك: `{user_id}`\n"
            f"✏️ الاسم الموثق: **{update.effective_user.full_name}**\n"
            f"💰 رصيدك الحالي بالدولار: `{bal_usd:.2f} $`\n"
            f"💰 رصيدك الحالي بالدينار: `{bal_jod:.2f} JOD`\n"
            f"🎯 نسبة الخصم الدائم لك: `% {disc_pct}`\n\n"
            f"💡 _ملاحظة: الأرقام محاطة بخلفية رمادية لسهولة نسخها بنقرة واحدة._"
        )
        await update.message.reply_text(msg, reply_markup=get_user_main_keyboard(), parse_mode="Markdown")
        
    elif text == "📦 طلباتي":
        # يمكن توسيع هذا النظام لعرض سجل كامل، حالياً يظهر رسالة إرشادية منظمة
        await update.message.reply_text("📦 **قسم طلباتي المفتوحة:**\n\nلا توجد طلبات معلقة حالياً تحت المراجعة. جميع طلباتك السابقة مكتملة.", parse_mode="Markdown")
        
    elif text == "💰 شحن الرصيد":
        keyboard = [
            [InlineKeyboardButton("🍊 محفظة أورنج موني (الأردن)", callback_data="charge_orange")],
            [InlineKeyboardButton("🌍 شحن لجميع الدول العربية والأجنبية", callback_data="charge_global")]
        ]
        await update.message.reply_text("💰 **اختر طريقة شحن الرصيد المناسبة لك:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    elif text == "🛠️ الدعم الفني":
        msg = (
            f"🛠️ **قسم الدعم الفني والمساعدة:**\n\n"
            f"📞 رقم الواتساب المباشر:\n+962776445110\n\n"
            f"✈️ حساب التليجرام الرسمي:\n@htb1b\n\n"
            f"تواصل معنا في أي وقت، نحن هنا لخدمتك!"
        )
        await update.message.reply_text(msg, reply_markup=get_user_main_keyboard())
        
    elif text == "🏪 واجهة الزبون" and user_id == ADMIN_ID:
        await update.message.reply_text("🔄 تحويل إلى واجهة الزبائن...", reply_markup=get_user_main_keyboard())

# --- معالجة أقسام المتجر للزبون ---
async def show_user_categories(update: Update, context: ContextTypes.DEFAULT_TYPE, parent_id=None):
    conn = get_db()
    cursor = conn.cursor()
    
    if parent_id is None:
        cursor.execute("SELECT id, name FROM categories WHERE parent_id IS NULL")
        title = "🏪 **الأقسام الرئيسية للمتجر:**\nاختر القسم الذي تريد تصفحه:"
    else:
        cursor.execute("SELECT name FROM categories WHERE id=?", (parent_id,))
        p_name = cursor.fetchone()[0]
        cursor.execute("SELECT id, name FROM categories WHERE parent_id=?", (parent_id,))
        title = f"📁 **قسم {p_name}:**\nاختر قسم فرعي أو تصفح المنتجات المتوفرة:"
        
    cats = cursor.fetchall()
    
    # جلب المنتجات في هذا القسم إن وجدت
    products = []
    if parent_id is not None:
        cursor.execute("SELECT id, name FROM products WHERE category_id=?", (parent_id,))
        products = cursor.fetchall()
        
    conn.close()
    
    buttons = []
    # إضافة الأقسام
    for cid, cname in cats:
        buttons.append([InlineKeyboardButton(f"📁 {cname}", callback_data=f"ucat_{cid}")])
    # إضافة المنتجات
    for pid, pname in products:
        buttons.append([InlineKeyboardButton(f"💎 {pname}", callback_data=f"uprod_{pid}")])
        
    # زر الرجوع للخلف
    if parent_id is not None:
        buttons.append([InlineKeyboardButton("🔙 العودة للخلف", callback_data="uback_to_root")])
        
    reply_markup = InlineKeyboardMarkup(buttons)
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(title, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(title, reply_markup=reply_markup, parse_mode="Markdown")

# معالجة كبسات التصفح والشراء للزبون
async def user_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    await query.answer()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT discount_percent FROM users WHERE user_id=?", (user_id,))
    user_discount = cursor.fetchone()[0]
    conn.close()
    
    if data.startswith("ucat_"):
        cat_id = int(data.split("_")[1])
        context.user_data['current_user_cat'] = cat_id
        await show_user_categories(update, context, parent_id=cat_id)
        
    elif data == "uback_to_root":
        await show_user_categories(update, context, parent_id=None)
        
    elif data.startswith("uprod_"):
        prod_id = int(data.split("_")[1])
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name, price_usd, description, category_id FROM products WHERE id=?", (prod_id,))
        prod = cursor.fetchone()
        conn.close()
        
        if prod:
            name, price_usd, desc, cat_id = prod
            final_usd, final_jod = calculate_prices(price_usd, user_discount)
            
            msg = (
                f"💎 **المنتج:** {name}\n"
                f"📝 **الوصف:**\n{desc}\n\n"
                f"💵 **السعر بالدولار:** `{final_usd:.2f} $`\n"
                f"🇯🇴 **السعر بالدينار الأردني:** `{final_jod:.2f} JOD`\n\n"
                f"📥 لشراء هذا المنتج، يرجى كتابة وإرسال المعلومات والمستندات المطلوبة واللازمة لتنفيذ الطلب فوراً:"
            )
            context.user_data['buy_prod_id'] = prod_id
            context.user_data['buy_prod_final_usd'] = final_usd
            
            # تحويل الحالة لانتظار معلومات الشراء من الزبون
            await query.message.reply_text(msg, parse_mode="Markdown")
            return U_PROD_INFO

    elif data == "charge_orange":
        msg = (
            f"🍊 **تحويل عبر محفظة أورنج موني:**\n\n"
            f"📱 رقم المحفظة: `0776445110`\n"
            f"💼 نوع المحفظة: **أورنج موني**\n"
            f"👤 اسم صاحب المحفظة الكامل:\n**سلمان نوح سلمان البدارين**\n\n"
            f"📸 **يرجى إرسال صورة الحوالة أو نص التحويل البنكي حالاً لتأكيد العملية:**"
        )
        await query.message.reply_text(msg, parse_mode="Markdown")
        return U_SUBMIT_DEPOSIT_PROOF
        
    elif data == "charge_global":
        msg = (
            f"🌍 **الشحن لجميع الدول العربية والأجنبية:**\n\n"
            f"نوفر طرق دفع متعددة تناسب بلدك (سواء كنت في سوريا، مصر، العراق، أو أي دولة أخرى).\n\n"
            f"📬 يرجى التواصل مع الإدارة مباشرة وإرسال اسم بلدك ليتم تزويدك بطرق التحويل المتاحة لك فوراً.\n\n"
            f"✉️ **التواصل مع الإدارة:**\n"
            f"تليجرام : @htb1b"
        )
        await query.message.reply_text(msg, parse_mode="Markdown")

# استقبال بيانات الشراء من الزبون وإرسالها للأدمن
async def user_submit_prod_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_info = update.message.text
    prod_id = context.user_data.get('buy_prod_id')
    final_usd = context.user_data.get('buy_prod_final_usd')
    user = update.effective_user
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM products WHERE id=?", (prod_id,))
    prod_name = cursor.fetchone()[0]
    conn.close()
    
    # إرسال الطلب للأدمن للموافقة أو الرفض
    admin_msg = (
        f"🛍️ **طلب شراء جديد وارد!**\n\n"
        f"👤 **الزبون:** {user.full_name} (`{user.id}`)\n"
        f"💎 **المنتج:** {prod_name}\n"
        f"💵 **السعر النهائي المخصوم:** `{final_usd:.2f} $`\n"
        f"📝 **بيانات الزبون المرسلة:**\n{user_info}"
    )
    
    kb = [
        [InlineKeyboardButton("✅ قبول الطلب", callback_data=f"ap_accept_{user.id}_{prod_id}_{final_usd}")],
        [InlineKeyboardButton("❌ رفض الطلب", callback_data=f"ap_reject_{user.id}")]
    ]
    
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    await update.message.reply_text("✅ تم إرسال معلوماتك للإدارة بنجاح، وطلبك الآن تحت المراجعة في قسم (طلباتي).", reply_markup=get_user_main_keyboard())
    return ConversationHandler.END

# استقبال إثبات شحن الرصيد من الزبون (صورة أو نص)
async def user_submit_deposit_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    admin_msg = f"💰 **طلب شحن رصيد جديد!**\n\n👤 **الزبون:** {user.full_name} (`{user.id}`)\n"
    
    kb = [
        [InlineKeyboardButton("✅ قبول وشحن", callback_data=f"ad_accept_{user.id}")],
        [InlineKeyboardButton("❌ رفض الشحن", callback_data=f"ad_reject_{user.id}")]
    ]
    
    if update.message.photo:
        photo_id = update.message.photo[-1].file_id
        admin_msg += "📸 أرسل صورة كإثبات للحوالة (مرفقة أدناه):"
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo_id, caption=admin_msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    else:
        proof_text = update.message.text
        admin_msg += f"📝 **نص الحوالة المرسل:**\n{proof_text}"
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
        
    await update.message.reply_text("✅ تم إرسال إثبات التحويل للإدارة بنجاح. سيتم مراجعته وإضافة الرصيد لك فوراً.", reply_markup=get_user_main_keyboard())
    return ConversationHandler.END


# ==========================================
#          قسم الأدمن (ADMIN SIDE)
# ==========================================

async def admin_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    text = update.message.text
    
    if text == "📁 إدارة المتجر":
        await show_admin_categories(update, context, parent_id=None)
        
    elif text == "👥 قائمة الزبائن":
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, balance_usd FROM users")
        users = cursor.fetchall()
        conn.close()
        
        msg = "👥 **قائمة الزبائن المسجلين في النظام:**\n\n"
        for uid, name, bal_usd in users:
            bal_jod = bal_usd * EXCHANGE_RATE
            msg += f"👤 الاسم: {name}\n🆔 الآيدي: `{uid}`\n💰 الرصيد: `{bal_usd:.2f} $` | `{bal_jod:.2f} JOD`\n------------------------\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
        
    elif text == "📢 إرسال إعلان":
        kb = [
            [InlineKeyboardButton("🔊 إعلان للجميع", callback_data="bc_all")],
            [InlineKeyboardButton("👤 إعلان لشخص معين", callback_data="bc_user")]
        ]
        await update.message.reply_text("📣 **اختر نوع الإعلان المراد إرساله:**", reply_markup=InlineKeyboardMarkup(kb))
        
    elif text == "🎯 إدارة الخصومات":
        await update.message.reply_text("🎯 **إدارة الخصومات:**\nيرجى إرسال **آيدي (ID) الزبون** المراد تطبيق الخصم العام له:")
        return A_SET_DISCOUNT_ID
        
    elif text == "📈 نسبة الربح":
        current_profit = get_profit_percent()
        await update.message.reply_text(f"📈 **إعدادات نسبة الربح:**\nالنسبة المطبقة حالياً هي: `%{current_profit}`\n\nأرسل النسبة المئوية الجديدة للربح ليتم تطبيقها تلقائياً على كل السيرفر (مثال: 4):", parse_mode="Markdown")
        return A_SET_PROFIT

# --- عرض الأقسام للأدمن مع خيارات التحكم ---
async def show_admin_categories(update: Update, context: ContextTypes.DEFAULT_TYPE, parent_id=None):
    conn = get_db()
    cursor = conn.cursor()
    
    if parent_id is None:
        cursor.execute("SELECT id, name FROM categories WHERE parent_id IS NULL")
        title = "📁 **لوحة إدارة الأقسام الرئيسية:**"
    else:
        cursor.execute("SELECT name FROM categories WHERE id=?", (parent_id,))
        p_name = cursor.fetchone()[0]
        cursor.execute("SELECT id, name FROM categories WHERE parent_id=?", (parent_id,))
        title = f"📁 **إدارة قسم {p_name}:**"
        
    cats = cursor.fetchall()
    
    products = []
    if parent_id is not None:
        cursor.execute("SELECT id, name FROM products WHERE category_id=?", (parent_id,))
        products = cursor.fetchall()
    conn.close()
    
    buttons = []
    # سرد الأقسام المتفرعة مع زر الحذف X لكل قسم
    for cid, cname in cats:
        buttons.append([
            InlineKeyboardButton(f"📁 {cname}", callback_data=f"acat_{cid}"),
            InlineKeyboardButton("❌ حذف", callback_data=f"delcat_{cid}")
        ])
    # سرد المنتجات مع زر حذف X
    for pid, pname in products:
        buttons.append([
            InlineKeyboardButton(f"💎 {pname}", callback_data=f"aprodinf_{pid}"),
            InlineKeyboardButton("❌ حذف", callback_data=f"delprod_{pid}")
        ])
        
    # أزرار الإضافة والتحكم
    control_buttons = []
    if parent_id is None:
        control_buttons.append(InlineKeyboardButton("➕ إضافة قسم رئيسي", callback_data="addcat_root"))
    else:
        control_buttons.append(InlineKeyboardButton("➕ إضافة قسم فرعي", callback_data=f"addcat_{parent_id}"))
        control_buttons.append(InlineKeyboardButton("➕ إضافة منتج هنا", callback_data=f"addprod_{parent_id}"))
        
    buttons.append(control_buttons)
    
    if parent_id is not None:
        buttons.append([InlineKeyboardButton("🔙 العودة للخلف", callback_data="aback_to_root")])
        
    reply_markup = InlineKeyboardMarkup(buttons)
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(title, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(title, reply_markup=reply_markup, parse_mode="Markdown")

# معالجة كبسات التحكم والإدارة للأدمن
async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    
    if data.startswith("acat_"):
        cat_id = int(data.split("_")[1])
        await show_admin_categories(update, context, parent_id=cat_id)
        
    elif data == "aback_to_root":
        await show_admin_categories(update, context, parent_id=None)
        
    elif data.startswith("addcat_"):
        pid_str = data.split("_")[1]
        context.user_data['add_cat_parent'] = None if pid_str == "root" else int(pid_str)
        await query.message.reply_text("📝 حسناً، أرسل اسم القسم الجديد المراد إنشاؤه:")
        return A_ADD_CAT
        
    elif data.startswith("addprod_"):
        cat_id = int(data.split("_")[1])
        context.user_data['add_prod_cat_id'] = cat_id
        await query.message.reply_text("📝 أرسل اسم المنتج الجديد:")
        return A_ADD_PROD_NAME
        
    elif data.startswith("delcat_"):
        cat_id = int(data.split("_")[1])
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        conn.commit()
        conn.close()
        await query.message.reply_text("✅ تم حذف القسم وجميع محتوياته بنجاح.")
        await show_admin_categories(update, context, parent_id=None)
        
    elif data.startswith("delprod_"):
        prod_id = int(data.split("_")[1])
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE id=?", (prod_id,))
        conn.commit()
        conn.close()
        await query.message.reply_text("✅ تم حذف المنتج بنجاح.")
        await show_admin_categories(update, context, parent_id=None)

    # --- معالجة طلبات شراء الزبائن ---
    elif data.startswith("ap_accept_"):
        parts = data.split("_")
        uid, pid, price = int(parts[2]), int(parts[3]), float(parts[4])
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT balance_usd FROM users WHERE user_id=?", (uid,))
        res = cursor.fetchone()
        
        if res and res[0] >= price:
            cursor.execute("UPDATE users SET balance_usd = balance_usd - ? WHERE user_id=?", (price, uid))
            conn.commit()
            conn.close()
            await query.message.edit_text("✅ تم قبول الطلب وخصم المبلغ من رصيد العميل بنجاح.")
            await context.bot.send_message(chat_id=uid, text="🎉 تم قبول طلبك من قبل الإدارة وتسليمه بنجاح! شكراً لتعاملك معنا.")
        else:
            conn.close()
            await query.message.edit_text("❌ رصيد الزبون غير كافٍ لإتمام عملية الشراء وتحتاج للرفض.")
            await context.bot.send_message(chat_id=uid, text="❌ رصيدك غير كافي لشراء المنتج، يرجى الشحن أولاً.")
            
    elif data.startswith("ap_reject_"):
        uid = int(data.split("_")[2])
        await query.message.edit_text("❌ تم رفض طلب الشراء.")
        await context.bot.send_message(chat_id=uid, text="❌ تم رفض طلبك من قبل الإدارة، يرجى التواصل مع الإدارة.")

    # --- معالجة طلبات شحن الأرصدة ---
    elif data.startswith("ad_accept_"):
        uid = int(data.split("_")[2])
        context.user_data['deposit_user_id'] = uid
        await query.message.reply_text("💵 أرسل الرصيد المراد إضافته للزبون **بالدولار** حالاً:")
        return A_DEPOSIT_AMOUNT
        
    elif data.startswith("ad_reject_"):
        uid = int(data.split("_")[2])
        await query.message.edit_text("❌ تم رفض عملية شحن الرصيد.")
        await context.bot.send_message(chat_id=uid, text="❌ تم رفض طلب شحن الرصيد الخاص بك، يرجى الاتصال بالدعم الفني.")

    # --- معالجة أزرار الإعلانات ---
    elif data == "bc_all":
        await query.message.reply_text("📢 ممتاز، أرسل الآن محتوى الرسالة الإعلانية لإرسالها للجميع:")
        return A_BROADCAST_ALL
    elif data == "bc_user":
        await query.message.reply_text("👤 أرسل الآن آيدي (ID) الشخص المستهدف بالإعلان:")
        return A_BROADCAST_USER_ID

# تتابع إضافة قسم جديد
async def admin_add_cat_proc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    parent_id = context.user_data.get('add_cat_parent')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO categories (name, parent_id) VALUES (?, ?)", (name, parent_id))
    conn.commit()
    conn.close()
    
    await update.message.reply_text("✅ تم إضافة القسم بنجاح.", reply_markup=get_admin_main_keyboard())
    return ConversationHandler.END

# تتابع إضافة منتج جديد
async def admin_add_prod_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_prod_name'] = update.message.text
    await update.message.reply_text("💵 الآن أرسل سعر المنتج بالدولار الافتراضي (رقم فقط دون رموز، مثال: 12.5):")
    return A_ADD_PROD_PRICE

async def admin_add_prod_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text)
        context.user_data['new_prod_price'] = price
        await update.message.reply_text("📝 الآن أرسل الوصف الخاص بالمنتج:")
        return A_ADD_PROD_DESC
    except ValueError:
        await update.message.reply_text("❌ عذراً، الرجاء إدخال رقم صحيح للسعر:")
        return A_ADD_PROD_PRICE

async def admin_add_prod_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text
    name = context.user_data.get('new_prod_name')
    price = context.user_data.get('new_prod_price')
    cat_id = context.user_data.get('add_prod_cat_id')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO products (name, price_usd, description, category_id) VALUES (?, ?, ?, ?)",
                   (name, price, desc, cat_id))
    conn.commit()
    conn.close()
    
    await update.message.reply_text("✅ تم حفظ المنتج الجديد وإتاحته للعملاء في المتجر بنجاح.", reply_markup=get_admin_main_keyboard())
    return ConversationHandler.END

# تتابع عملية شحن وإيداع الرصيد الفعلي
async def admin_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount_usd = float(update.message.text)
        uid = context.user_data.get('deposit_user_id')
        amount_jod = amount_usd * EXCHANGE_RATE
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance_usd = balance_usd + ? WHERE user_id=?", (amount_usd, uid))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ تم بنجاح شحن الحساب للزبون بمقدار:\n`{amount_usd:.2f} $` | `{amount_jod:.2f} JOD`", reply_markup=get_admin_main_keyboard(), parse_mode="Markdown")
        
        # إشعار العميل المنسق باللغتين
        user_msg = (
            f"🎉 **تهانينا! تم إضافة رصيد جديد إلى حسابك بنجاح**\n\n"
            f"📥 القيمة المضافة بالدولار: `{amount_usd:.2f} $`\n"
            f"🇯🇴 القيمة المضافة بالدينار: `{amount_jod:.2f} JOD`\n\n"
            f"تفقد رصيدك الآن من خانة (حسابي)."
        )
        await context.bot.send_message(chat_id=uid, text=user_msg, parse_mode="Markdown")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ الرجاء كتابة رقم صحيح لعملة الدولار (رقم فقط):")
        return A_DEPOSIT_AMOUNT

# تتابع الإعلانات البث للكل
async def admin_broadcast_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    
    count = 0
    for u in users:
        try:
            await context.bot.send_message(chat_id=u[0], text=f"📢 **إعلان من الإدارة:**\n\n{msg}", parse_mode="Markdown")
            count += 1
        except:
            continue
    await update.message.reply_text(f"✅ تم بث الإعلان بنجاح إلى {count} مستخدم.", reply_markup=get_admin_main_keyboard())
    return ConversationHandler.END

# بث لشخص معين
async def admin_broadcast_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(update.message.text)
        context.user_data['target_bc_id'] = target_id
        await update.message.reply_text("📥 أرسل الآن نص الرسالة الموجهة له:")
        return A_BROADCAST_USER_MSG
    except ValueError:
        await update.message.reply_text("❌ آيدي غير صحيح، أرسل رقم فقط:")
        return A_BROADCAST_USER_ID

async def admin_broadcast_user_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    target_id = context.user_data.get('target_bc_id')
    try:
        await context.bot.send_message(chat_id=target_id, text=f"🔔 **رسالة خاصة من الإدارة:**\n\n{msg}", parse_mode="Markdown")
        await update.message.reply_text("✅ تم إرسال الرسالة بنجاح للشخص المحدد.", reply_markup=get_admin_main_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ تعذر الإرسال، سبب الخطأ: {e}", reply_markup=get_admin_main_keyboard())
    return ConversationHandler.END

# تتابع إدارة الخصومات
async def admin_set_discount_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text)
        context.user_data['discount_target_id'] = uid
        await update.message.reply_text("🎯 الآن أرسل النسبة المئوية للخصم (رقم فقط من 0 لـ 100، مثال: 10):")
        return A_SET_DISCOUNT_VAL
    except ValueError:
        await update.message.reply_text("❌ أرسل آيدي صحيح:")
        return A_SET_DISCOUNT_ID

async def admin_set_discount_val(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = float(update.message.text)
        uid = context.user_data.get('discount_target_id')
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET discount_percent=? WHERE user_id=?", (val, uid))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ تم تعيين خصم بمقدار %{val} لجميع أسعار المستخدم `{uid}`.", reply_markup=get_admin_main_keyboard(), parse_mode="Markdown")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ أرسل نسبة صحيحة:")
        return A_SET_DISCOUNT_VAL

# تتابع إعدادات الأرباح
async def admin_set_profit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = float(update.message.text)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE settings SET value=? WHERE key='global_profit_percent'", (str(val),))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ تم تعديل نسبة ربح البوت العامة لتصبح %{val} وتطبيقها على جميع الأسعار تلقائياً.", reply_markup=get_admin_main_keyboard())
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ أرسل نسبة صحيحة للربح:")
        return A_SET_PROFIT


# --- دالة إلغاء أو كبسة العودة العامة ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)
    return ConversationHandler.END


# --- الدالة الأساسية لتشغيل البوت ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # بناء الـ Conversation للتعامل مع الإدخالات دون تداخل أو أخطاء
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^(📁 إدارة المتجر|👥 قائمة الزبائن|📢 إرسال إعلان|🎯 إدارة الخصومات|📈 نسبة الربح)$'), admin_menu_handler),
            CallbackQueryHandler(admin_callback_handler, pattern='^(acat_|aback_to_root|addcat_|addprod_|delcat_|delprod_|ap_|ad_|bc_)'),
            CallbackQueryHandler(user_callback_handler, pattern='^(ucat_|uback_to_root|uprod_|charge_)'),
            MessageHandler(filters.Regex('^(🏪 المتجر|👤 حسابي|📦 طلباتي|💰 شحن الرصيد|🛠️ الدعم الفني|🏪 واجهة الزبون|🔙 العودة للمتجر)$'), user_menu_handler),
        ],
        states={
            A_ADD_CAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_cat_proc)],
            A_ADD_PROD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_prod_name)],
            A_ADD_PROD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_prod_price)],
            A_ADD_PROD_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_prod_desc)],
            A_DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_deposit_amount)],
            A_BROADCAST_ALL: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_all)],
            A_BROADCAST_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_user_id)],
            A_BROADCAST_USER_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_user_msg)],
            A_SET_DISCOUNT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_discount_id)],
            A_SET_DISCOUNT_VAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_discount_val)],
            A_SET_PROFIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_profit)],
            U_PROD_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, user_submit_prod_info)],
            U_SUBMIT_DEPOSIT_PROOF: [MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, user_submit_deposit_proof)],
        },
        fallbacks=[
            CommandHandler('start', start),
            MessageHandler(filters.Regex('🔙 العودة للخلف'), cancel)
        ],
        allow_reentry=True
    )
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv_handler)
    
    # معالجات الأزرار المباشرة خارج المحادثات
    app.add_handler(MessageHandler(filters.TEXT, user_menu_handler))
    
    print("🚀 البوت يعمل الآن بنجاح وبشكل متكامل...")
    app.run_polling()

if __name__ == '__main__':
    main()
