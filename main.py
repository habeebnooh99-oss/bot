import logging
import sqlite3
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    ReplyKeyboardMarkup
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

# --- إعداد قاعدة البيانات وحفظ البيانات تلقائياً ---
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
    
    # جدول الأقسام الشجرية دون حدود
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
    
    # جدول الطلبات لشحن الرصيد والمراجعة
    cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT, 
        status TEXT DEFAULT 'pending',
        details TEXT,
        product_id INTEGER NULL,
        amount_usd REAL DEFAULT 0.0
    )''')
    
    conn.commit()
    conn.close()

init_db()

# --- حالات إدخال البيانات (Conversation States) ---
(
    WAIT_DEPOSIT_PROOF, 
    WAIT_DEPOSIT_AMOUNT,
    WAIT_PRODUCT_INFO, 
    WAIT_ADMIN_BROADCAST, 
    WAIT_ADMIN_PRIVATE_ID, 
    WAIT_ADMIN_PRIVATE_MSG,
    WAIT_ADMIN_CAT_NAME, 
    WAIT_ADMIN_PROD_NAME, 
    WAIT_ADMIN_PROD_DESC, 
    WAIT_ADMIN_PROD_JOD, 
    WAIT_ADMIN_PROD_USD, 
    WAIT_ADMIN_DISCOUNT_ID, 
    WAIT_ADMIN_DISCOUNT_PCT
) = range(13)

# --- لوحات المفاتيح السفلية الرئيسية ---
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

# --- الأوامر العامة والقوائم الثابتة ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    get_or_create_user(user_id, update.effective_user.username)
    await update.message.reply_text(
        "✨ أهلاً بك في بوت **ALEX CARD** ✨\nيرجى استخدام الأزرار في الأسفل للتنقل.",
        reply_markup=get_main_keyboard(user_id),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

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

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📞 **قسم الدعم الفني لمساعدتك:**\n\n🟢 رقم الواتساب: +962776445110\n🔵 التليجرام: @htb1b")

# --- قائمة شحن الرصيد للزبائن ---
async def deposit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🍊 محفظة أورنج موني", callback_data="dep_orange")],
        [InlineKeyboardButton("🌍 الشحن لجميع الدول العربية والأجنبية", callback_data="dep_global")]
    ]
    await update.message.reply_text("💰 **الرجاء اختيار طريقة شحن الرصيد المناسبة لك:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# --- تصفح المتجر للزبائن (شجري بالكامل وبدون قيود) ---
async def store_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_user_category_level(update, context, parent_id=None, is_callback=False)

async def send_user_category_level(update, context, parent_id, is_callback=False):
    conn = sqlite3.connect('alex_card.db')
    cursor = conn.cursor()
    if parent_id is None:
        cursor.execute("SELECT id, name FROM categories WHERE parent_id IS NULL")
    else:
        cursor.execute("SELECT id, name FROM categories WHERE parent_id = ?", (parent_id,))
    categories = cursor.fetchall()
    
    products = []
    if parent_id is not None:
        cursor.execute("SELECT id, name, price_jod, price_usd FROM products WHERE category_id = ?", (parent_id,))
        products = cursor.fetchall()
    conn.close()
    
    keyboard = []
    for cat in categories:
        keyboard.append([InlineKeyboardButton(f"📁 {cat[1]}", callback_data=f"u_cat_{cat[0]}")])
    for prod in products:
        keyboard.append([InlineKeyboardButton(f"🛒 {prod[1]} ({prod[3]}$ / {prod[2]} د.أ)", callback_data=f"u_prod_{prod[0]}")])
        
    if parent_id is not None:
        conn = sqlite3.connect('alex_card.db')
        c = conn.cursor()
        c.execute("SELECT parent_id FROM categories WHERE id = ?", (parent_id,))
        gp = c.fetchone()
        conn.close()
        back_data = f"u_cat_{gp[0]}" if (gp and gp[0]) else "u_root"
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=back_data)])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg_text = "🛒 **تصفح الأقسام والمنتجات المتاحة:**"
    if is_callback:
        await update.callback_query.edit_message_text(msg_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(msg_text, reply_markup=reply_markup, parse_mode="Markdown")

# --- لوحة التحكم للإدمن الشجرية بدون حدود ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await send_admin_main_menu(update, context, is_callback=False)

async def send_admin_main_menu(update, context, is_callback=False):
    keyboard = [
        [InlineKeyboardButton("📁 إدارة المتجر والأقسام", callback_data="adm_cat_root"), InlineKeyboardButton("👥 قائمة الزبائن", callback_data="admin_users")],
        [InlineKeyboardButton("📢 إرسال إعلان للإعلام", callback_data="admin_broadcast"), InlineKeyboardButton("📉 إدارة الخصومات", callback_data="admin_discounts")]
    ]
    text = "⚙️ **مرحباً بك في لوحة تحكم الإدمن الأساسية:**"
    if is_callback:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def send_admin_category_level(update, context, parent_id):
    context.user_data['adm_curr_cat'] = parent_id
    conn = sqlite3.connect('alex_card.db')
    cursor = conn.cursor()
    if parent_id is None:
        cursor.execute("SELECT id, name FROM categories WHERE parent_id IS NULL")
    else:
        cursor.execute("SELECT id, name FROM categories WHERE parent_id = ?", (parent_id,))
    sub_cats = cursor.fetchall()
    
    prods = []
    if parent_id is not None:
        cursor.execute("SELECT id, name FROM products WHERE category_id = ?", (parent_id,))
        prods = cursor.fetchall()
    conn.close()
    
    keyboard = []
    for c in sub_cats:
        keyboard.append([InlineKeyboardButton(f"📁 {c[1]}", callback_data=f"adm_cat_{c[0]}"), InlineKeyboardButton("❌ حذف قسم", callback_data=f"del_cat_{c[0]}")])
    for p in prods:
        keyboard.append([InlineKeyboardButton(f"🛍️ {p[1]}", callback_data="none"), InlineKeyboardButton("❌ حذف منتج", callback_data=f"del_prod_{p[0]}")])
        
    # خيارات الإضافة متوفرة دائماً في الشجرة لإنشاء تداخلات غير محدودة
    keyboard.append([InlineKeyboardButton("➕ إضافة قسم فرعي هنا", callback_data="add_cat")])
    keyboard.append([InlineKeyboardButton("➕ إضافة منتج في هذا القسم", callback_data="add_prod")])
        
    if parent_id is not None:
        conn = sqlite3.connect('alex_card.db')
        c = conn.cursor()
        c.execute("SELECT parent_id FROM categories WHERE id = ?", (parent_id,))
        gp = c.fetchone()
        conn.close()
        b_data = f"adm_cat_{gp[0]}" if (gp and gp[0]) else "adm_cat_root"
        keyboard.append([InlineKeyboardButton("🔙 رجوع للخلف", callback_data=b_data)])
    else:
        keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="admin_panel_main")])
        
    await update.callback_query.edit_message_text("📁 **إدارة شجرة الأقسام والمنتجات دون قيود:**", reply_markup=InlineKeyboardMarkup(keyboard))

# --- المعالج العام لضغطات الأزرار (Callback Queries) ---
async def general_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    await query.answer()
    
    # 1. شحن رصيد العميل
    if data == "back_to_dep":
        keyboard = [[InlineKeyboardButton("🍊 محفظة أورنج موني", callback_data="dep_orange")], [InlineKeyboardButton("🌍 الشحن لجميع الدول العربية والأجنبية", callback_data="dep_global")]]
        await query.edit_message_text("💰 **الرجاء اختيار طريقة شحن الرصيد المناسبة لك:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data == "dep_orange":
        text = "🍊 **معلومات التحويل عبر أورنج موني:**\n\n📱 رقم المحفظة: `0776445110`\n💼 اسم المحفظة: `SALMAN NOUH SALMAN AL-BADAREEN`\n\n⚠️ **الخطوة التالية:** يرجى تصوير إيصال التحويل (لقطة شاشة/Screenshot) وإرسال الصورة هنا لتأكيد طلبك 👇"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_dep")]]))
        return WAIT_DEPOSIT_PROOF
    elif data == "dep_global":
        text = "🌍 **الشحن للدول العربية والأجنبية:**\n\nنوفر طرق دفع متعددة تناسب بلدك.\n📥 يرجى التواصل مع الإدارة مباشرة وإرسال اسم بلدك ليتم تزويدك بطرق التحويل المتاحة لك فوراً.\n\n💬 التواصل مع الإدارة:\nتليجرام : @htb1b"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_to_dep")]]))

    # 2. تصفح العميل للمتجر
    elif data == "u_root":
        await send_user_category_level(update, context, parent_id=None, is_callback=True)
    elif data.startswith("u_cat_"):
        await send_user_category_level(update, context, parent_id=int(data.split("_")[2]), is_callback=True)
    elif data.startswith("u_prod_"):
        prod_id = int(data.split("_")[2])
        conn = sqlite3.connect('alex_card.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name, description, price_jod, price_usd, category_id FROM products WHERE id = ?", (prod_id,))
        prod = cursor.fetchone()
        user = get_or_create_user(user_id, query.from_user.username)
        conn.close()
        
        discount = user[4]
        final_jod = prod[2] * (1 - discount/100)
        final_usd = prod[3] * (1 - discount/100)
        
        desc_text = f"🛍️ **اسم المنتج:** {prod[0]}\n📝 **الوصف:**\n{prod[1]}\n\n💰 **السعر الأصلي:** {prod[3]}$ / {prod[2]} د.أ\n📉 **سعرك بعد الخصم ({discount}%):** `{final_usd:.2f}$` / `{final_jod:.2f} د.أ`\n\n⚠️ أرسل المعلومات اللازمة المطلوبة للشراء بالضغط أدناه."
        keyboard = [[InlineKeyboardButton("💳 شراء الآن", callback_data=f"buy_req_{prod_id}")], [InlineKeyboardButton("🔙 رجوع", callback_data=f"u_cat_{prod[4]}")] ]
        await query.edit_message_text(desc_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data.startswith("buy_req_"):
        context.user_data['buy_prod_id'] = int(data.split("_")[2])
        await query.edit_message_text("📥 **يرجى كتابة وإرسال المعلومات اللازمة المطلوبة لإتمام طلبك:**")
        return WAIT_PRODUCT_INFO

    # 3. لوحة تحكم الإدمن الشجرية
    elif user_id == ADMIN_ID:
        if data == "admin_panel_main":
            await send_admin_main_menu(update, context, is_callback=True)
        elif data == "admin_users":
            conn = sqlite3.connect('alex_card.db')
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username, balance_usd FROM users")
            users = cursor.fetchall()
            conn.close()
            msg = "👥 **قائمة الزبائن المسجلين:**\n\n"
            for u in users: msg += f"🔹 {u[1]} | الأيدي: `{u[0]}` | رصيد: `{u[2]}$`\n"
            await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel_main")]]))
        elif data == "admin_broadcast":
            kb = [[InlineKeyboardButton("📢 للكل", callback_data="bc_all"), InlineKeyboardButton("👤 لشخص معين", callback_data="bc_one")], [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel_main")]]
            await query.edit_message_text("📢 **اختر نوع الإعلان:**", reply_markup=InlineKeyboardMarkup(kb))
        elif data == "bc_all":
            await query.edit_message_text("✍️ أرسل محتوى الرسالة الإعلانية للجميع:")
            return WAIT_ADMIN_BROADCAST
        elif data == "bc_one":
            await query.edit_message_text("✍️ يرجى إدخال أيدي الشخص المستهدف:")
            return WAIT_ADMIN_PRIVATE_ID
        elif data == "admin_discounts":
            await query.edit_message_text("📉 يرجى إدخال أيدي الزبون المراد تحديد خصم له:")
            return WAIT_ADMIN_DISCOUNT_ID
        elif data == "adm_cat_root":
            await send_admin_category_level(update, context, parent_id=None)
        elif data.startswith("adm_cat_"):
            await send_admin_category_level(update, context, parent_id=int(data.split("_")[2]))
        elif data == "add_cat":
            await query.edit_message_text("✍️ أدخل اسم القسم الجديد:")
            return WAIT_ADMIN_CAT_NAME
        elif data == "add_prod":
            await query.edit_message_text("✍️ أدخل اسم المنتج الجديد المراد إضافته:")
            return WAIT_ADMIN_PROD_NAME
        elif data.startswith("del_cat_"):
            conn = sqlite3.connect('alex_card.db')
            cursor = conn.cursor()
            cursor.execute("DELETE FROM categories WHERE id = ?", (int(data.split("_")[2]),))
            conn.commit()
            conn.close()
            await query.edit_message_text("✅ تم حذف القسم بنجاح.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data="adm_cat_root")]]))
        elif data.startswith("del_prod_"):
            conn = sqlite3.connect('alex_card.db')
            cursor = conn.cursor()
            cursor.execute("DELETE FROM products WHERE id = ?", (int(data.split("_")[2]),))
            conn.commit()
            conn.close()
            await query.edit_message_text("✅ تم حذف المنتج بنجاح.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 عودة", callback_data="adm_cat_root")]]))
            
        # معالجة قرارات طلبات الشحن والشراء من الإدمن
        elif data.startswith("approve_dep_"):
            context.user_data['manage_order_id'] = int(data.split("_")[2])
            await query.edit_message_text("✍️ اكتب الرصيد المراد اضافته للزبون بالدولار ($):")
            return WAIT_DEPOSIT_AMOUNT
        elif data.startswith("deny_dep_"):
            order_id = int(data.split("_")[2])
            conn = sqlite3.connect('alex_card.db')
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
            cursor.execute("UPDATE orders SET status = 'denied' WHERE id = ?", (order_id,))
            conn.commit()
            conn.close()
            try: await context.bot.send_message(chat_id=order[0], text="❌ تم الرفض يرجى الاتصال بالدعم الفني")
            except: pass
            await query.edit_message_text("❌ تم رفض طلب الشحن بنجاح.")
        elif data.startswith("approve_buy_"):
            order_id = int(data.split("_")[2])
            conn = sqlite3.connect('alex_card.db')
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, amount_usd, status FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
            if order and order[2] == 'pending':
                uid, cost_usd = order[0], order[1]
                cursor.execute("SELECT balance_usd FROM users WHERE user_id = ?", (uid,))
                user_bal = cursor.fetchone()
                if user_bal and user_bal[0] >= cost_usd:
                    cursor.execute("UPDATE users SET balance_usd = balance_usd - ? WHERE user_id = ?", (cost_usd, uid))
                    cursor.execute("UPDATE orders SET status = 'approved' WHERE id = ?", (order_id,))
                    conn.commit()
                    try: await context.bot.send_message(chat_id=uid, text="🎉 تم قبول الطلب")
                    except: pass
                    await query.edit_message_text("✅ تم قبول الطلب وخصم الرصيد بنجاح.")
                else:
                    await query.edit_message_text("⚠️ رصيد العميل غير كافي لإتمام الخصم.")
            conn.close()
        elif data.startswith("deny_buy_"):
            order_id = int(data.split("_")[2])
            conn = sqlite3.connect('alex_card.db')
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
            cursor.execute("UPDATE orders SET status = 'denied' WHERE id = ?", (order_id,))
            conn.commit()
            conn.close()
            try: await context.bot.send_message(chat_id=order[0], text="تم رفض الطلب يرجى التواصل مع الاداره")
            except: pass
            await query.edit_message_text("❌ تم رفض طلب الشراء.")
            
    return ConversationHandler.END

# --- وظائف استقبال النصوص واستكمال الإدخالات الحساسة ---
async def receive_deposit_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    proof_text = update.message.text
    conn = sqlite3.connect('alex_card.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO orders (user_id, type, details) VALUES (?, 'deposit', ?)", (user_id, proof_text))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ تم إرسال إثبات الشحن إلى الإدارة بنجاح.")
    
    # التأكد أن الزبون أرسل صورة إيصال بالفعل وليس نصاً
    if not update.message.photo:
        await update.message.reply_text("❌ عذراً، يرجى إرسال صورة واضحة للإيصال (لقطة شاشة) لتأكيد طلبك:")
        return WAIT_DEPOSIT_PROOF

    photo_file_id = update.message.photo[-1].file_id

    conn = sqlite3.connect('alex_card.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO orders (user_id, type, details) VALUES (?, 'deposit', ?)", (user_id, f"PHOTO_ID:{photo_file_id}"))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ تم إرسال صورة الإيصال بنجاح إلى الإدارة. يرجى الانتظار لحين المراجعة.")

    admin_buttons = [[InlineKeyboardButton("✅ قبول", callback_data=f"approve_dep_{order_id}"), InlineKeyboardButton("❌ رفض", callback_data=f"deny_dep_{order_id}")]]
    
    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_file_id,
        caption=f"🚨 **طلب شحن رصيد جديد (صورة إيصال)!**\n\n👤 المستخدم: `{user_id}`\n📦 رقم الطلب: `{order_id}`\n💬 يوزر العميل: @{update.effective_user.username}",
        reply_markup=InlineKeyboardMarkup(admin_buttons),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

    order_id = context.user_data.get('manage_order_id')
    conn = sqlite3.connect('alex_card.db')
    order_id = context.user_data.get('manage_order_id')
    conn = sqlite3.connect('alex_card.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    if order:
        uid = order[0]
        amount_jod = amount_usd * 0.71
        cursor.execute("UPDATE users SET balance_usd = balance_usd + ?, balance_jod = balance_jod + ? WHERE user_id = ?", (amount_usd, amount_jod, uid))
        cursor.execute("UPDATE orders SET status = 'approved' WHERE id = ?", (order_id,))
        conn.commit()
        try: await context.bot.send_message(chat_id=uid, text=f"🎉 تم إضافة الرصيد إلى حسابك بنجاح!\n💵 القيمة: {amount_usd}$\n🇯🇴 ما يعادلها: {amount_jod:.2f} د.أ")
        except: pass
        await update.message.reply_text(f"✅ تم إضافة الرصيد للزبون بنجاح واكتملت الحوالة.\n({amount_usd}$ / {amount_jod:.2f} JOD)")
        await update.message.reply_text("✅ تم إضافة الرصيد للزبون بنجاح واكتملت الحوالة.")
    conn.close()
    return ConversationHandler.END

async def receive_product_purchase_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    info_text = update.message.text
    prod_id = context.user_data.get('buy_prod_id')
    
    conn = sqlite3.connect('alex_card.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, price_jod, price_usd FROM products WHERE id = ?", (prod_id,))
    prod = cursor.fetchone()
    user = get_or_create_user(user_id, update.effective_user.username)
    
    discount = user[4]
    final_jod = prod[1] * (1 - discount/100)
    final_usd = prod[2] * (1 - discount/100)
    
    if user[3] < final_usd and user[2] < final_jod:
        await update.message.reply_text("❌ رصيدك غير كافي يرجى الشحن اولا")
        conn.close()
        return ConversationHandler.END
        
    cursor.execute("INSERT INTO orders (user_id, type, details, product_id, amount_usd) VALUES (?, 'purchase', ?, ?, ?)", (user_id, f"المنتج: {prod[0]} | تفاصيل: {info_text}", prod_id, final_usd))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    await update.message.reply_text("✅ تم إرسال طلب الشراء الخاص بك إلى الإدارة وهو قيد المراجعة.")
    admin_buttons = [[InlineKeyboardButton("✅ قبول", callback_data=f"approve_buy_{order_id}"), InlineKeyboardButton("❌ رفض", callback_data=f"deny_buy_{order_id}")]]
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 **طلب شراء منتج!**\n👤 الزبون: `{user_id}`\n🛍️ السعر: {final_usd:.2f}$\n📝 معلوماته:\n{info_text}", reply_markup=InlineKeyboardMarkup(admin_buttons), parse_mode="Markdown")
    return ConversationHandler.END

async def receive_admin_broadcast_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    conn = sqlite3.connect('alex_card.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    for u in users:
        try: await context.bot.send_message(chat_id=u[0], text=f"📢 **إعلان من الإدارة:**\n\n{update.message.text}")
        except: pass
    await update.message.reply_text("✅ تم إرسال الإعلان للكل بنجاح.")
    return ConversationHandler.END

async def receive_admin_private_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    context.user_data['target_user_id'] = update.message.text
    await update.message.reply_text("✍️ أرسل الآن محتوى الرسالة للشخص:")
    return WAIT_ADMIN_PRIVATE_MSG

async def receive_admin_private_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    try:
        await context.bot.send_message(chat_id=int(context.user_data.get('target_user_id')), text=f"📩 **رسالة خاصة من الإدارة:**\n\n{update.message.text}")
        await update.message.reply_text("✅ تم الإرسال الفردي بنجاح.")
    except: await update.message.reply_text("❌ تعذر الإرسال.")
    return ConversationHandler.END

async def receive_admin_discount_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    context.user_data['discount_user_id'] = update.message.text
    await update.message.reply_text("✍️ أرسل نسبة الخصم المئوية (مثال 15 لخصم 15%):")
    return WAIT_ADMIN_DISCOUNT_PCT

async def receive_admin_discount_pct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    try: pct = float(update.message.text)
    except: await update.message.reply_text("❌ قيمة خاطئة"); return WAIT_ADMIN_DISCOUNT_PCT
    conn = sqlite3.connect('alex_card.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET discount_pct = ? WHERE user_id = ?", (pct, int(context.user_data.get('discount_user_id'))))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"📉 تم تطبيق الخصم الشامل للزبون.")
    return ConversationHandler.END

async def receive_admin_cat_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    conn = sqlite3.connect('alex_card.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO categories (name, parent_id) VALUES (?, ?)", (update.message.text, context.user_data.get('adm_curr_cat')))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ تم إضافة القسم بنجاح.")
    return ConversationHandler.END

async def receive_admin_prod_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    context.user_data['new_prod_name'] = update.message.text
    await update.message.reply_text("✍️ أرسل الآن وصف المنتج بالكامل وبدقة:")
    return WAIT_ADMIN_PROD_DESC

async def receive_admin_prod_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    context.user_data['new_prod_desc'] = update.message.text
    await update.message.reply_text("✍️ أرسل سعر المنتج بالدينار الأردني JOD:")
    return WAIT_ADMIN_PROD_JOD

async def receive_admin_prod_jod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    context.user_data['new_prod_jod'] = update.message.text
    await update.message.reply_text("✍️ أرسل سعر المنتج بالدولار الأمريكي USD:")
    return WAIT_ADMIN_PROD_USD

async def receive_admin_prod_usd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return ConversationHandler.END
    try:
        price_usd = float(update.message.text)
        price_jod = float(context.user_data.get('new_prod_jod'))
    except:
        await update.message.reply_text("❌ الأسعار مدخلة بشكل خاطئ، يرجى المحاولة من جديد.")
        return ConversationHandler.END
        
    conn = sqlite3.connect('alex_card.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO products (name, description, price_jod, price_usd, category_id) VALUES (?, ?, ?, ?, ?)", 
                   (context.user_data.get('new_prod_name'), context.user_data.get('new_prod_desc'), price_jod, price_usd, context.user_data.get('adm_curr_cat')))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ تم حفظ وإضافة المنتج بشكل ناجح وكامل بنظام الشجرة.")
    return ConversationHandler.END

# --- مشغل النظام الرئيسي الفعلي وتوزيع المعالجات المستقرة ---
def main():
    application = Application.builder().token(TOKEN).build()
    
    # الـ ConversationHandler تم تخصيصه لإدارة الإدخالات النصية فقط دون التداخل مع أزرار التنقل
    input_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(general_callback_handler)],
        states={
            WAIT_DEPOSIT_PROOF: [MessageHandler(filters.PHOTO & ~filters.COMMAND, receive_deposit_proof)],
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
    
    # المعالجات الأساسية للبوت
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.Text('🛒 المتجر'), store_menu))
    application.add_handler(MessageHandler(filters.Text('👤 حسابي'), my_account))
    application.add_handler(MessageHandler(filters.Text('📦 طلباتي'), my_orders))
    application.add_handler(MessageHandler(filters.Text('💰 شحن الرصيد'), deposit_menu))
    application.add_handler(MessageHandler(filters.Text('📞 الدعم الفني'), support))
    application.add_handler(MessageHandler(filters.Text('⚙️ لوحة الإدمن'), admin_panel))
    
    # معالج الضغطات العامة والإدخالات
    application.add_handler(input_conv)
    application.add_handler(CallbackQueryHandler(general_callback_handler))
    
    application.run_polling()

if __name__ == '__main__':
    main()
