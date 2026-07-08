import logging
import sqlite3
import json
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
    filters,
    ConversationHandler
)

# --- الإعدادات الأساسية ---
TOKEN = "8811163076:AAHlcXGmsZcAFQM_Or4jlVD-luIsDo9cxnI"
ADMIN_ID = 8529336745

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- إعداد قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('alex_card.db')
    cursor = conn.cursor()
    
    # جدول المستخدمين
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance_jod REAL DEFAULT 0.0,
        balance_usd REAL DEFAULT 0.0,
        discount_pct REAL DEFAULT 0.0
    )''')
    
    # جدول الأقسام
    cursor.execute('''CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        parent_id INTEGER DEFAULT NULL
    )''')
    
    # جدول المنتجات
    cursor.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        description TEXT,
        price_jod REAL,
        price_usd REAL,
        category_id INTEGER
    )''')
    
    # جدول الطلبات (للشراء والشحن)
    cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT, -- 'purchase' or 'deposit'
        status TEXT DEFAULT 'pending',
        details TEXT,
        product_id INTEGER NULL,
        amount_usd REAL DEFAULT 0.0
    )''')
    
    conn.commit()
    conn.close()

init_db()

# --- حالات المحادثات (Conversation States) ---
(
    WAIT_PRODUCT_INFO, WAIT_DEPOSIT_PROOF, WAIT_DEPOSIT_AMOUNT,
    WAIT_ADMIN_BROADCAST, WAIT_ADMIN_PRIVATE_ID, WAIT_ADMIN_PRIVATE_MSG,
    WAIT_ADMIN_CAT_NAME, WAIT_ADMIN_PROD_NAME, WAIT_ADMIN_PROD_DESC, 
    WAIT_ADMIN_PROD_JOD, WAIT_ADMIN_PROD_USD, WAIT_ADMIN_DISCOUNT_ID, WAIT_ADMIN_DISCOUNT_PCT
) = range(13)

# --- لوحات المفاتيح الرئيسية ---
def get_main_keyboard(user_id):
    if user_id == ADMIN_ID:
        return ReplyKeyboardMarkup([
            ['🛒 المتجر', '👤 حسابي'],
            ['📦 طلباتي', '💰 شحن الرصيد'],
            ['📞 الدعم الفني', '⚙️ لوحة الإدمن']
        ], resize_keyboard=True)
    else:
        return ReplyKeyboardMarkup([
            ['🛒 المتجر', '👤 حسابي'],
            ['📦 طلباتي', '💰 شحن الرصيد'],
            ['📞 الدعم الفني']
        ], resize_keyboard=True)

# --- دالة مساعدة لجلب بيانات المستخدم أو إنشائه ---
def get_or_create_user(user_id, username):
    conn = sqlite3.connect('alex_card.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, balance_jod, balance_usd, discount_pct FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        username_str = f"@{username}" if username else "بلا يوزر"
        cursor.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username_str))
        conn.commit()
        cursor.execute("SELECT user_id, username, balance_jod, balance_usd, discount_pct FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
    conn.close()
    return user

# --- انطلاق البوت ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    get_or_create_user(user_id, username)
    
    await update.message.reply_text(
        "✨ أهلاً بك في بوت **ALEX CARD** ✨\nيسعدنا تقديم أفضل الخدمات لك. استخدم الأزرار أدناه للتنقل.",
        reply_markup=get_main_keyboard(user_id),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# --- قسم حسابي ---
async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_or_create_user(user_id, update.effective_user.username)
    
    text = (
        f"👤 **معلومات حسابك الشخصي:**\n\n"
        f"🆔 الأيدي الخاص بك: `{user[0]}`\n"
        f"📝 الاسم: {update.effective_user.first_name}\n"
        f"💰 رصيدك بالدينار: `{user[2]:.2f} JOD`\n"
        f"💵 رصيدك بالدولار: `{user[3]:.2f} USD`\n"
        f"📉 نسبة الخصم الخاصة بك: `{user[4]}%`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# --- قسم طلباتي تحت المراجعة ---
async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect('alex_card.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, type, details FROM orders WHERE user_id = ? AND status = 'pending'", (user_id,))
    orders = cursor.fetchall()
    conn.close()
    
    if not orders:
        await update.message.reply_text("📦 ليس لديك أي طلبات تحت المراجعة حالياً.")
        return
    
    msg = "📦 **طلباتك القائمة وتحت المراجعة:**\n\n"
    for order in orders:
        o_type = "شراء منتج" if order[1] == 'purchase' else "شحن رصيد"
        msg += f"🔹 **رقم الطلب:** `{order[0]}`\n🔹 **النوع:** {o_type}\n🔹 **التفاصيل:** {order[2]}\n------------------\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

# --- قسم الدعم الفني ---
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📞 **قسم الدعم الفني لمساعدتك:**\n\n"
        "🟢 رقم الواتساب: +962776445110\n"
        "🔵 التليجرام: @htb1b"
    )
    await update.message.reply_text(text)

# --- قسم شحن الرصيد ---
async def deposit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🍊 محفظة أورنج موني", callback_data="dep_orange")],
        [InlineKeyboardButton("🌍 الشحن لجميع الدول العربية والأجنبية", callback_data="dep_global")]
    ]
    await update.message.reply_text("💰 **الرجاء اختيار طريقة شحن الرصيد المناسبة لك:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def deposit_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "dep_orange":
        text = (
            "🍊 **معلومات التحويل عبر أورنج موني:**\n\n"
            "📱 رقم المحفظة: `0776445110`\n"
            "💼 اسم المحفظة: `سلمان نوح سلمان البدارين`\n\n"
            "⚠️ **الخطوة التالية:** يرجى إرسال نص رسالة التحويل بدقة لتأكيد العملية والتحقق من الطلب."
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_dep")]]))
        return WAIT_DEPOSIT_PROOF
        
    elif query.data == "dep_global":
        text = (
            "🌍 **الشحن للدول العربية والأجنبية:**\n\n"
            "نوفر طرق دفع متعددة تناسب بلدك (سواء كنت في سوريا أو مصر أو العراق أو أي دولة أخرى).\n\n"
            "📥 يرجى التواصل مع الإدارة مباشرة وإرسال اسم بلدك ليتم تزويدك بطرق التحويل المتاحة لك فوراً.\n\n"
            "💬 التواصل مع الإدارة:\n"
            "تليجرام : @htb1b"
        )
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_dep")]]))
    
    elif query.data == "back_to_dep":
        keyboard = [
            [InlineKeyboardButton("🍊 محفظة أورنج موني", callback_data="dep_orange")],
            [InlineKeyboardButton("🌍 الشحن لجميع الدول العربية والأجنبية", callback_data="dep_global")]
        ]
        await query.edit_message_text("💰 **الرجاء اختيار طريقة شحن الرصيد المناسبة لك:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return ConversationHandler.END

async def receive_deposit_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    proof_text = update.message.text
    
    conn = sqlite3.connect('alex_card.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO orders (user_id, type, details) VALUES (?, 'deposit', ?)", (user_id, proof_text))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    await update.message.reply_text("✅ تم إرسال إثبات الشحن إلى الإدارة بنجاح. يرجى الانتظار لحين المراجعة.")
    
    # إشعار الإدمن
    admin_buttons = [
        [
            InlineKeyboardButton("✅ قبول", callback_data=f"approve_dep_{order_id}"),
            InlineKeyboardButton("❌ رفض", callback_data=f"deny_dep_{order_id}")
        ]
    ]
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🚨 **طلب شحن رصيد جديد!**\n\n👤 المستخدم: `{user_id}`\n📦 رقم الطلب: `{order_id}`\n📝 نص الحوالة المرسل:\n\n{proof_text}",
        reply_markup=InlineKeyboardMarkup(admin_buttons),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# --- متجر المنتجات والأقسام المتداخلة شجرياً ---
async def store_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # البداية من الأقسام الرئيسية (parent_id IS NULL)
    await send_category_level(update, context, parent_id=None, is_callback=False)

async def send_category_level(update, context, parent_id, is_callback=False):
    conn = sqlite3.connect('alex_card.db')
    cursor = conn.cursor()
    
    # جلب الأقسام الفرعية
    if parent_id is None:
        cursor.execute("SELECT id, name FROM categories WHERE parent_id IS NULL")
    else:
        cursor.execute("SELECT id, name FROM categories WHERE parent_id = ?", (parent_id,))
    categories = cursor.fetchall()
    
    # جلب المنتجات في هذا القسم الحالي
    products = []
    if parent_id is not None:
        cursor.execute("SELECT id, name, price_jod, price_usd FROM products WHERE category_id = ?", (parent_id,))
        products = cursor.fetchall()
        
    conn.close()
    
    keyboard = []
    # أزرار الأقسام
    for cat in categories:
        keyboard.append([InlineKeyboardButton(f"📁 {cat[1]}", callback_data=f"view_cat_{cat[0]}")])
    # أزرار المنتجات
    for prod in products:
        keyboard.append([InlineKeyboardButton(f"🛍️ {prod[1]} ({prod[3]}$ / {prod[2]}د.أ)", callback_data=f"view_prod_{prod[0]}")])
        
    # زر الرجوع للقسم الأعلى
    if parent_id is not None:
        conn = sqlite3.connect('alex_card.db')
        c = conn.cursor()
        c.execute("SELECT parent_id FROM categories WHERE id = ?", (parent_id,))
        grand_parent = c.fetchone()
        conn.close()
        back_data = f"view_cat_{grand_parent[0]}" if (grand_parent and grand_parent[0]) else "store_root"
        keyboard.append([InlineKeyboardButton("🔙 رجوع خلف للخلف", callback_data=back_data)])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg_text = "🛒 **تصفح الأقسام والمنتجات المتاحة لدينا:**"
    
    if is_callback:
        await update.callback_query.edit_message_text(msg_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(msg_text, reply_markup=reply_markup, parse_mode="Markdown")

async def store_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    
    if data == "store_root":
        await send_category_level(update, context, parent_id=None, is_callback=True)
        return ConversationHandler.END
        
    elif data.startswith("view_cat_"):
        cat_id = int(data.split("_")[2])
        await send_category_level(update, context, parent_id=cat_id, is_callback=True)
        return ConversationHandler.END
        
    elif data.startswith("view_prod_"):
        prod_id = int(data.split("_")[2])
        user_id = query.from_user.id
        
        conn = sqlite3.connect('alex_card.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name, description, price_jod, price_usd, category_id FROM products WHERE id = ?", (prod_id,))
        prod = cursor.fetchone()
        user = get_or_create_user(user_id, query.from_user.username)
        conn.close()
        
        if not prod:
            await query.edit_message_text("❌ هذا المنتج لم يعد متوفراً.")
            return ConversationHandler.END
            
        # تطبيق نسبة الخصم الخاصة بالعميل
        discount = user[4]
        final_jod = prod[2] * (1 - discount/100)
        final_usd = prod[3] * (1 - discount/100)
        
        desc_text = (
            f"🛍️ **اسم المنتج:** {prod[0]}\n"
            f"📝 **الوصف:**\n{prod[1]}\n\n"
            f"💰 **السعر الأصلي:** {prod[3]}$ / {prod[2]} د.أ\n"
            f"📉 **سعرك بعد الخصم ({discount}%):** `{final_usd:.2f}$` / `{final_jod:.2f} د.أ`\n\n"
            f"⚠️ لشراء المنتج، يرجى الضغط على زر الشراء وإرسال المعلومات اللازمة المطلوبة منك."
        )
        
        keyboard = [
            [InlineKeyboardButton("💳 شراء الآن", callback_data=f"buy_req_{prod_id}")],
            [InlineKeyboardButton("🔙 رجوع", callback_data=f"view_cat_{prod[4]}")]
        ]
        await query.edit_message_text(desc_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return ConversationHandler.END

    elif data.startswith("buy_req_"):
        prod_id = int(data.split("_")[2])
        context.user_data['buy_prod_id'] = prod_id
        await query.edit_message_text("📥 **يرجى كتابة وإرسال المعلومات اللازمة المطلوبة لإتمام طلبك:**\n(مثال: الحسابات، الأكواد، أو أي تفاصيل مطلوبة)")
        return WAIT_PRODUCT_INFO

async def receive_product_purchase_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    info_text = update.message.text
    prod_id = context.user_data.get('buy_prod_id')
    
    conn = sqlite3.connect('alex_card.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, price_jod, price_usd FROM products WHERE id = ?", (prod_id,))
    prod = cursor.fetchone()
    user = get_or_create_user(user_id, update.effective_user.username)
    
    if not prod:
        await update.message.reply_text("❌ حدث خطأ في النظام، المنتج غير موجود.")
        return ConversationHandler.END
        
    discount = user[4]
    final_jod = prod[1] * (1 - discount/100)
    final_usd = prod[2] * (1 - discount/100)
    
    # التحقق من وجود رصيد كافٍ لدى العميل (بالدولار أو الدينار حسب المتوفر)
    if user[3] < final_usd and user[2] < final_jod:
        await update.message.reply_text("❌ رصيدك غير كافي لشراء هذا المنتج. يرجى الشحن أولاً.")
        return ConversationHandler.END
        
    # تسجيل الطلب في قاعدة البيانات تحت المراجعة
    details = f"المنتج: {prod[0]} | تفاصيل العميل: {info_text}"
    cursor.execute("INSERT INTO orders (user_id, type, details, product_id, amount_usd) VALUES (?, 'purchase', ?, ?, ?)",
                   (user_id, details, prod_id, final_usd))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    await update.message.reply_text("✅ تم إرسال طلب الشراء الخاص بك إلى الإدارة وهو قيد المراجعة الفورية.")
    
    # إخطار لوحة التحكم للإدمن
    admin_buttons = [
        [
            InlineKeyboardButton("✅ قبول البيع", callback_data=f"approve_buy_{order_id}"),
            InlineKeyboardButton("❌ رفض الطلب", callback_data=f"deny_buy_{order_id}")
        ]
    ]
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🚨 **طلب شراء منتج جديد!**\n\n👤 العميل: `{user_id}`\n📦 رقم الطلب: `{order_id}`\n🛍️ المنتج: {prod[0]}\n💵 السعر الصافي للخصم: {final_usd:.2f}$ / {final_jod:.2f} د.أ\n📝 معلومات العميل المرسلة:\n{info_text}",
        reply_markup=InlineKeyboardMarkup(admin_buttons),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# --- معالجة قرارات الإدمن على الطلبات (شراء أو شحن) ---
async def admin_decision_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    
    conn = sqlite3.connect('alex_card.db')
    cursor = conn.cursor()
    
    # 1. قبول طلب الشحن (نطلب من الادمن الرصيد بالدولار)
    if data.startswith("approve_dep_"):
        order_id = int(data.split("_")[2])
        context.user_data['manage_order_id'] = order_id
        await query.edit_message_text(f"✍️ الطلب رقم `{order_id}`: يرجى كتابة وإرسال الرصيد المراد إضافته للزبون بالدولار ($):")
        conn.close()
        return WAIT_DEPOSIT_AMOUNT
        
    # 2. رفض طلب الشحن
    elif data.startswith("deny_dep_"):
        order_id = int(data.split("_")[2])
        cursor.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        if order:
            cursor.execute("UPDATE orders SET status = 'denied' WHERE id = ?", (order_id,))
            conn.commit()
            try:
                await context.bot.send_message(chat_id=order[0], text="❌ تم رفض طلب شحن الرصيد، يرجى الاتصال بالدعم الفني.")
            except: pass
            await query.edit_message_text(f"❌ تم رفض طلب الشحن رقم {order_id} بنجاح.")
        conn.close()
        return ConversationHandler.END

    # 3. قبول طلب شراء منتج خصماً من الرصيد
    elif data.startswith("approve_buy_"):
        order_id = int(data.split("_")[3])
        cursor.execute("SELECT user_id, amount_usd, status FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        
        if order and order[2] == 'pending':
            uid, cost_usd = order[0], order[1]
            cursor.execute("SELECT balance_usd FROM users WHERE user_id = ?", (uid,))
            user_bal = cursor.fetchone()
            
            if user_bal and user_bal[0] >= cost_usd:
                # خصم الرصيد وتحديث الطلب
                cursor.execute("UPDATE users SET balance_usd = balance_usd - ? WHERE user_id = ?", (cost_usd, uid))
                cursor.execute("UPDATE orders SET status = 'approved' WHERE id = ?", (order_id,))
                conn.commit()
                try:
                    await context.bot.send_message(chat_id=uid, text="🎉 تم قبول طلبك بنجاح! وتم خصم قيمة المنتج من رصيدك الحسابي.")
                except: pass
                await query.edit_message_text(f"✅ تم قبول الطلب رقم {order_id} وخصم {cost_usd}$ من رصيد العميل.")
            else:
                await query.edit_message_text(f"⚠️ رصيد العميل غير كافي حالياً لإتمام عملية الخصم.")
        conn.close()
        return ConversationHandler.END
        
    # 4. رفض طلب شراء المنتج
    elif data.startswith("deny_buy_"):
        order_id = int(data.split("_")[2])
        cursor.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        if order:
            cursor.execute("UPDATE orders SET status = 'denied' WHERE id = ?", (order_id,))
            conn.commit()
            try:
                await context.bot.send_message(chat_id=order[0], text="❌ تم رفض طلب الشراء الخاص بك. يرجى التواصل مع الإدارة.")
            except: pass
            await query.edit_message_text(f"❌ تم رفض طلب الشراء رقم {order_id} وإشعار العميل.")
        conn.close()
        return ConversationHandler.END

async def receive_deposit_amount_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    
    try:
        amount_usd = float(update.message.text)
    except ValueError:
        await update.message.reply_text("❌ خطأ، يرجى إدخال قيمة رقمية صحيحة:")
        return WAIT_DEPOSIT_AMOUNT
        
    order_id = context.user_data.get('manage_order_id')
    conn = sqlite3.connect('alex_card.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, status FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    
    if order and order[1] == 'pending':
        uid = order[0]
        # احتساب القيمة الموازية بالدينار الأردني افتراضياً (سعر الصرف التقريبي 0.71)
        amount_jod = amount_usd * 0.71
        
        cursor.execute("UPDATE users SET balance_usd = balance_usd + ?, balance_jod = balance_jod + ? WHERE user_id = ?", (amount_usd, amount_jod, uid))
        cursor.execute("UPDATE orders SET status = 'approved' WHERE id = ?", (order_id,))
        conn.commit()
        
        try:
            await context.bot.send_message(chat_id=uid, text=f"🎉 تم إضافة رصيد لحسابك بنجاح بقيمة: `{amount_usd:.2f}$` ({amount_jod:.2f} د.أ).")
        except: pass
        await update.message.reply_text(f"✅ تم إضافة الرصيد بنجاح إلى حساب العميل `{uid}`.")
    conn.close()
    return ConversationHandler.END

# --- ⚙️ لوحة الإدمن والتحكم الكامل ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    keyboard = [
        [InlineKeyboardButton("📁 إدارة المتجر والأقسام", callback_data="admin_store"), InlineKeyboardButton("👥 قائمة الزبائن", callback_data="admin_users")],
        [InlineKeyboardButton("📢 إرسال إعلان للإعلام", callback_data="admin_broadcast"), InlineKeyboardButton("📉 إدارة الخصومات", callback_data="admin_discounts")]
    ]
    await update.message.reply_text("⚙️ **مرحباً بك في لوحة تحكم الإدمن الأساسية للمنصة:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_panel_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if query.from_user.id != ADMIN_ID: return
    await query.answer()
    
    if data == "admin_panel_main":
        keyboard = [
            [InlineKeyboardButton("📁 إدارة المتجر والأقسام", callback_data="admin_store"), InlineKeyboardButton("👥 قائمة الزبائن", callback_data="admin_users")],
            [InlineKeyboardButton("📢 إرسال إعلان للإعلام", callback_data="admin_broadcast"), InlineKeyboardButton("📉 إدارة الخصومات", callback_data="admin_discounts")]
        ]
        await query.edit_message_text("⚙️ **مرحباً بك في لوحة تحكم الإدمن الأساسية للمنصة:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return ConversationHandler.END

    # قسم قائمة الزبائن
    elif data == "admin_users":
        conn = sqlite3.connect('alex_card.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, balance_usd FROM users")
        users = cursor.fetchall()
        conn.close()
        
        msg = "👥 **قائمة الزبائن المسجلين بالنظام:**\n\n"
        for u in users:
            msg += f"🔹 الاسم واليوزر: {u[1]} | الأيدي: `{u[0]}` | رصيد: `{u[2]}$`\n"
        
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel_main")]]))

    # قسم الإعلانات
    elif data == "admin_broadcast":
        kb = [
            [InlineKeyboardButton("📢 إرسال للجميع", callback_data="bc_all"), InlineKeyboardButton("👤 إرسال لشخص محدد", callback_data="bc_one")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel_main")]
        ]
        await query.edit_message_text("📢 **اختر نوع الإعلان والجمهور المستهدف:**", reply_markup=InlineKeyboardMarkup(kb))
        
    elif data == "bc_all":
        await query.edit_message_text("✍️ أرسل الآن محتوى الرسالة الإعلانية التي تود توجيهها لجميع المستخدمين:")
        return WAIT_ADMIN_BROADCAST
        
    elif data == "bc_one":
        await query.edit_message_text("✍️ يرجى إدخال (أيدي ID) الشخص المستهدف أولاً:")
        return WAIT_ADMIN_PRIVATE_ID

    # قسم إدارة الخصومات الشاملة لعميل محدد
    elif data == "admin_discounts":
        await query.edit_message_text("📉 **إدارة الخصومات:** يرجى إدخال أيدي (ID) الزبون المراد تخصيص نسبة خصم شاملة له:")
        return WAIT_ADMIN_DISCOUNT_ID

    # شجرة متجر الإدمن (إضافة/حذف)
    elif data == "admin_store" or data.startswith("adm_cat_"):
        cat_id = None if (data == "admin_store" or data == "adm_cat_root") else int(data.split("_")[2])
        context.user_data['adm_curr_cat'] = cat_id
        
        conn = sqlite3.connect('alex_card.db')
        cursor = conn.cursor()
        if cat_id is None:
            cursor.execute("SELECT id, name FROM categories WHERE parent_id IS NULL")
        else:
            cursor.execute("SELECT id, name FROM categories WHERE parent_id = ?", (cat_id,))
        sub_cats = cursor.fetchall()
        
        prods = []
        if cat_id is not None:
            cursor.execute("SELECT id, name FROM products WHERE category_id = ?", (cat_id,))
            prods = cursor.fetchall()
        conn.close()
        
        kb = []
        # عرض الأقسام المتوفرة للحذف أو الدخول إليها
        for c in sub_cats:
            kb.append([
                InlineKeyboardButton(f"📁 {c[1]}", callback_data=f"adm_cat_{c[0]}"),
                InlineKeyboardButton("❌ حذف", callback_data=f"del_cat_{c[0]}")
            ])
        # عرض المنتجات المتوفرة للحذف
        for p in prods:
            kb.append([
                InlineKeyboardButton(f"🛍️ {p[1]}", callback_data="none"),
                InlineKeyboardButton("❌ حذف منتج", callback_data=f"del_prod_{p[0]}")
            ])
            
        kb.append([InlineKeyboardButton("➕ إضافة قسم فرعي هنا", callback_data="add_cat")])
        if cat_id is not None:
            kb.append([InlineKeyboardButton("➕ إضافة منتج في هذا القسم", callback_data="add_prod")])
            
        # الرجوع الشجري للوراء
        if cat_id is not None:
            conn = sqlite3.connect('alex_card.db')
            c = conn.cursor()
            c.execute("SELECT parent_id FROM categories WHERE id = ?", (cat_id,))
            gp = c.fetchone()
            conn.close()
            b_data = f"adm_cat_{gp[0]}" if (gp and gp[0]) else "adm_cat_root"
            kb.append([InlineKeyboardButton("🔙 رجوع للخلف", callback_data=b_data)])
        else:
            kb.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="admin_panel_main")])
            
        await query.edit_message_text("📁 **إدارة شجرة الأقسام والمنتجات بدون حدود:**", reply_markup=InlineKeyboardMarkup(kb))

    # عمليات الحذف (إكس) للقسم أو المنتج
    elif data.startswith("del_cat_"):
        cid = int(data.split("_")[2])
        conn = sqlite3.connect('alex_card.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM categories WHERE id = ?", (cid,))
        conn.commit()
        conn.close()
        await query.edit_message_text("✅ تم حذف القسم بنجاح.")
        return ConversationHandler.END
        
    elif data.startswith("del_prod_"):
        pid = int(data.split("_")[2])
        conn = sqlite3.connect('alex_card.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE id = ?", (pid,))
        conn.commit()
        conn.close()
        await query.edit_message_text("✅ تم حذف المنتج بنجاح.")
        return ConversationHandler.END

    # طلبات الإضافة
    elif data == "add_cat":
        await query.edit_message_text("✍️ أدخل اسم القسم الجديد الذي تود إنشائه:")
        return WAIT_ADMIN_CAT_NAME
        
    elif data == "add_prod":
        await query.edit_message_text("✍️ أدخل اسم المنتج الجديد:")
        return WAIT_ADMIN_PROD_NAME

# --- تنفيذ عمليات الاستقبال من الإدمن (إعلانات وخصومات وإضافات للمتجر) ---
async def receive_admin_broadcast_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    msg_text = update.message.text
    
    conn = sqlite3.connect('alex_card.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    
    count = 0
    for u in users:
        try:
            await context.bot.send_message(chat_id=u[0], text=f"📢 **إعلان هام من الإدارة:**\n\n{msg_text}")
            count += 1
        except: pass
        
    await update.message.reply_text(f"✅ تم إرسال الإعلان الشامل بنجاح إلى {count} مستخدم.")
    return ConversationHandler.END

async def receive_admin_private_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    context.user_data['target_user_id'] = update.message.text
    await update.message.reply_text("✍️ ممتاز، أرسل الآن نص الرسالة الموجهة له بشكل خاص:")
    return WAIT_ADMIN_PRIVATE_MSG

async def receive_admin_private_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    target_id = context.user_data.get('target_user_id')
    msg_text = update.message.text
    
    try:
        await context.bot.send_message(chat_id=int(target_id), text=f"📩 **رسالة خاصة من الإدارة:**\n\n{msg_text}")
        await update.message.reply_text("✅ تم إرسال الرسالة الخاصة للمستخدم بنجاح دون أخطاء.")
    except Exception as e:
        await update.message.reply_text(f"❌ تعذر إرسال الرسالة، تأكد من الأيدي الصحيح. تفاصيل: {e}")
        
    return ConversationHandler.END

async def receive_admin_discount_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    context.user_data['discount_user_id'] = update.message.text
    await update.message.reply_text("✍️ أرسل الآن نسبة الخصم المئوية المطلوبة (مثال: اكتب 15 لخصم 15%):")
    return WAIT_ADMIN_DISCOUNT_PCT

async def receive_admin_discount_pct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    try:
        pct = float(update.message.text)
    except:
        await update.message.reply_text("❌ يرجى إدخال قيمة رقمية صحيحة:")
        return WAIT_ADMIN_DISCOUNT_PCT
        
    uid = context.user_data.get('discount_user_id')
    conn = sqlite3.connect('alex_card.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET discount_pct = ? WHERE user_id = ?", (pct, int(uid)))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"📉 تم بنجاح تطبيق نسبة خصم قدرها `{pct}%` على جميع الأسعار للمستخدم `{uid}`.")
    return ConversationHandler.END

# استقبال متطلبات إضافة الأقسام والمنتجات
async def receive_admin_cat_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    name = update.message.text
    parent_id = context.user_data.get('adm_curr_cat')
    
    conn = sqlite3.connect('alex_card.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO categories (name, parent_id) VALUES (?, ?)", (name, parent_id))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ تم إضافة القسم الجديد بنجاح باسم: {name}")
    return ConversationHandler.END

async def receive_admin_prod_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    context.user_data['new_prod_name'] = update.message.text
    await update.message.reply_text("✍️ حسناً، أرسل الآن وصف وتفاصيل هذا المنتج بشكل دقيق:")
    return WAIT_ADMIN_PROD_DESC

async def receive_admin_prod_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    context.user_data['new_prod_desc'] = update.message.text
    await update.message.reply_text("✍️ أرسل سعر المنتج بالدينار الأردني JOD (مثال: 12.50):")
    return WAIT_ADMIN_PROD_JOD

async def receive_admin_prod_jod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    context.user_data['new_prod_jod'] = update.message.text
    await update.message.reply_text("✍️ وأخيراً، أرسل سعر المنتج بالدولار الأمريكي USD (مثال: 18.00):")
    return WAIT_ADMIN_PROD_USD

async def receive_admin_prod_usd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    try:
        price_usd = float(update.message.text)
        price_jod = float(context.user_data.get('new_prod_jod'))
    except:
        await update.message.reply_text("❌ خطأ بالأسعار الرقمية المدخلة، يرجى إعادة الإضافة من جديد.")
        return ConversationHandler.END
        
    name = context.user_data.get('new_prod_name')
    desc = context.user_data.get('new_prod_desc')
    cat_id = context.user_data.get('adm_curr_cat')
    
    conn = sqlite3.connect('alex_card.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO products (name, description, price_jod, price_usd, category_id) VALUES (?, ?, ?, ?, ?)",
                   (name, desc, price_jod, price_usd, cat_id))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ تم إضافة منتج ({name}) بنجاح داخل شجرة المتجر الحالية.")
    return ConversationHandler.END

# --- تشغيل وتطوير التطبيق بالكامل وبدء التشغيل الفعلي ---
def main():
    application = Application.builder().token(TOKEN).build()
    
    # محادثات لوحة التحكم والشراء والشحن المعقدة ذات المراحل المتعددة
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(deposit_callbacks, pattern="^(dep_orange|dep_global|back_to_dep)$"),
            CallbackQueryHandler(store_callbacks, pattern="^(store_root|view_cat_|view_prod_|buy_req_)$"),
            CallbackQueryHandler(admin_panel_callbacks, pattern="^(admin_panel_main|admin_users|admin_broadcast|bc_all|bc_one|admin_discounts|admin_store|adm_cat_|del_cat_|del_prod_|add_cat|add_prod)$"),
            CallbackQueryHandler(admin_decision_callbacks, pattern="^(approve_dep_|deny_dep_|approve_buy_|deny_buy_)")
        ],
        states={
            WAIT_DEPOSIT_PROOF: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_deposit_proof)],
            WAIT_DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_deposit_amount_admin)],
            WAIT_PRODUCT_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_product_purchase_info)],
            WAIT_ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_broadcast_all)],
            WAIT_ADMIN_PRIVATE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_private_id)],
            WAIT_ADMIN_PRIVATE_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_private_msg)],
            WAIT_ADMIN_DISCOUNT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_discount_id)],
            WAIT_ADMIN_DISCOUNT_PCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_discount_pct)],
            WAIT_ADMIN_CAT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_cat_name)],
            WAIT_ADMIN_PROD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_prod_name)],
            WAIT_ADMIN_PROD_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_prod_desc)],
            WAIT_ADMIN_PROD_JOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_prod_jod)],
            WAIT_ADMIN_PROD_USD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_prod_usd)]
        },
        fallbacks=[CommandHandler('start', start)],
        allow_reentry=True
    )
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.Text('🛒 المتجر'), store_menu))
    application.add_handler(MessageHandler(filters.Text('👤 حسابي'), my_account))
    application.add_handler(MessageHandler(filters.Text('📦 طلباتي'), my_orders))
    application.add_handler(MessageHandler(filters.Text('💰 شحن الرصيد'), deposit_menu))
    application.add_handler(MessageHandler(filters.Text('📞 الدعم الفني'), support))
    application.add_handler(MessageHandler(filters.Text('⚙️ لوحة الإدمن'), admin_panel))
    
    application.add_handler(conv_handler)
    
    # بدء تشغيل البوت عبر الـ Polling المستمر
    application.run_polling()

if __name__ == '__main__':
    main()
