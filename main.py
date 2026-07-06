import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

# إعدادات تسجيل الأخطاء
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- البيانات الأساسية والثوابت ---
TOKEN = "8811163076:AAHlcXGmsZcAFQM_Or4jlVD-luIsDo9cxnI"  # ⚠️ يرجى تغيير هذا التوكن فوراً من BotFather للأمان!
ADMIN_ID = 8529336745  # الآدمن سلمان

# --- قاعدة البيانات المؤقتة في الذاكرة ---
DB = {
    "users": {},       # {user_id: {"name": str, "balance_jod": 0.0, "balance_usd": 0.0, "discount": 0}}
    "categories": {},  # {cat_id: {"name": str, "parent": id/None, "subcats": [], "products": []}}
    "products": {},    # {prod_id: {"name": str, "desc": str, "price_jod": 0.0, "price_usd": 0.0, "cat_id": id}}
    "orders": {},      # {order_id: {"user_id": id, "type": "buy"/"charge", "status": "pending", "details": str, "prod_id": id/None}}
    "cat_counter": 1,
    "prod_counter": 1,
    "order_counter": 1
}

# --- حالات نظام إدارة الحوار (States) ---
(
    # حالات العميل
    CLIENT_WAIT_PROD_INFO, CLIENT_WAIT_CHARGE_TEXT,
    # حالات الآدمن
    ADMIN_WAIT_CAT_NAME, ADMIN_WAIT_PROD_NAME, ADMIN_WAIT_PROD_DESC, ADMIN_WAIT_PROD_JOD, ADMIN_WAIT_PROD_USD,
    ADMIN_WAIT_CHARGE_AMOUNT, ADMIN_WAIT_BROADCAST_ALL, ADMIN_WAIT_BROADCAST_USER_ID, ADMIN_WAIT_BROADCAST_USER_MSG,
    ADMIN_WAIT_DISCOUNT_USER_ID, ADMIN_WAIT_DISCOUNT_PERCENT
) = range(13)

# سياق التنقل للآدمن والعميل لحفظ مؤشرات الأقسام
USER_CONTEXT = {} # {user_id: {"current_cat": id, "current_prod": id, "target_user": id, "target_order": id}}

# --- دالة التحقق وإنشاء حساب العميل الجديد ---
def check_user(user):
    uid = user.id
    if uid not in DB["users"]:
        DB["users"][uid] = {
            "name": user.full_name or "بلا اسم",
            "balance_jod": 0.0,
            "balance_usd": 0.0,
            "discount": 0
        }
    else:
        DB["users"][uid]["name"] = user.full_name or DB["users"][uid]["name"]

# --- لوحة التحكم الرئيسية للعميل والآدمن ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    check_user(user)
    USER_CONTEXT[user.id] = {"current_cat": None, "current_prod": None}
    
    keyboard = [
        [InlineKeyboardButton("🏪 المتجر", callback_data="client_shop"), InlineKeyboardButton("👤 حسابي", callback_data="client_profile")],
        [InlineKeyboardButton("📦 طلباتي", callback_data="client_orders"), InlineKeyboardButton("🔋 شحن الرصيد", callback_data="client_charge")],
        [InlineKeyboardButton("📞 الدعم الفني", callback_data="client_support")]
    ]
    
    if user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("⚙️ لوحة التحكم (الآدمن)", callback_data="admin_panel")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg_text = f"👋 أهلاً بك في متجر **ALEX CARD**\nيرجى اختيار أحد الأقسام من الأسفل للتنقل الشامل والمريح👇:"
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(msg_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(msg_text, reply_markup=reply_markup, parse_mode="Markdown")
        
    return ConversationHandler.END

# =====================================================================
#                          [ 👤 قسم العميل ]
# =====================================================================

async def client_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    check_user(query.from_user)
    
    if user_id not in USER_CONTEXT:
        USER_CONTEXT[user_id] = {"current_cat": None, "current_prod": None}

    if data == "main_menu":
        USER_CONTEXT[user_id] = {"current_cat": None, "current_prod": None}
        keyboard = [
            [InlineKeyboardButton("🏪 المتجر", callback_data="client_shop"), InlineKeyboardButton("👤 حسابي", callback_data="client_profile")],
            [InlineKeyboardButton("📦 طلباتي", callback_data="client_orders"), InlineKeyboardButton("🔋 شحن الرصيد", callback_data="client_charge")],
            [InlineKeyboardButton("📞 الدعم الفني", callback_data="client_support")]
        ]
        if user_id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("⚙️ لوحة التحكم (الآدمن)", callback_data="admin_panel")])
        await query.edit_message_text(f"👋 أهلاً بك في متجر **ALEX CARD**\nيرجى اختيار أحد الأقسام من الأسفل للتنقل الشامل والمريح👇:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "client_profile":
        u = DB["users"][user_id]
        txt = (
            f"👤 **معلومات حسابك الشخصي:**\n\n"
            f"🆔 الآيدي الخاص بك: `{user_id}`\n"
            f"📝 الاسم: {u['name']}\n"
            f"🇯🇴 رصيدك بالدينار: `{u['balance_jod']:.2f} JOD`\n"
            f"💵 رصيدك بالدولار: `{u['balance_usd']:.2f} USD`\n"
            f"📉 نسبة خصمك الخاصة: %{u['discount']}"
        )
        kbd = [[InlineKeyboardButton("⬅️ رجوع", callback_data="main_menu")]]
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

    elif data == "client_support":
        txt = (
            f"📞 **قنوات الدعم الفني المباشر لموقع ALEX CARD:**\n\n"
            f"🟢 رقم الواتساب: +962776445110\n"
            f"🔵 التليجرام الرسمي: @htb1b\n\n"
            f"تواصل معنا في أي وقت، نحن هنا لخدمتك!"
        )
        kbd = [[InlineKeyboardButton("⬅️ رجوع", callback_data="main_menu")]]
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kbd))

    elif data == "client_orders":
        txt = "📦 **طلباتك الحالية القائمة وتحت المراجعة:**\n\n"
        found = False
        for oid, o in DB["orders"].items():
            if o["user_id"] == user_id and o["status"] == "pending":
                found = True
                t_type = "شراء منتج" if o["type"] == "buy" else "شحن رصيد"
                txt += f"🔹 طلب رقم: `{oid}` | النوع: *{t_type}*\n📝 تفاصيل: {o['details']}\n------------------------\n"
        if not found:
            txt += "لا توجد لديك أي طلبات تحت المراجعه حالياً."
        kbd = [[InlineKeyboardButton("⬅️ رجوع", callback_data="main_menu")]]
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

    elif data == "client_charge":
        txt = "🔋 **أقسام وطرق الشحن المتوفرة:**\n\nيرجى اختيار وسيلة الشحن المناسبة لك:"
        kbd = [
            [InlineKeyboardButton("📱 أورنج موني (Orange Money)", callback_data="charge_orange")],
            [InlineKeyboardButton("⬅️ رجوع", callback_data="main_menu")]
        ]
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kbd))

    elif data == "charge_orange":
        txt = (
            f"📱 **تعليمات الشحن عبر محفظة أورنج موني:**\n\n"
            f"🔸 رقم المحفظة المحول إليها: `0776445110`\n"
            f"🔸 اسم صاحب المحفظة: Salman Noah Salman Al-Badarin\n"
            f"----------------------------------------\n"
            f"⚠️ **مهم جداً:** بعد إتمام عملية التحويل المالي، يرجى كتابة وإرسال نص رسالة التحويل بالكامل (أو كتابة تفاصيل الحوالة) هنا بالأسفل ليتم تدقيقها يدوياً من الإدارة."
        )
        kbd = [[InlineKeyboardButton("⬅️ رجوع", callback_data="client_charge")]]
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")
        return CLIENT_WAIT_CHARGE_TEXT

    elif data == "client_shop" or data.startswith("browse_cat_"):
        cat_id = None
        if data.startswith("browse_cat_"):
            cat_id = int(data.split("_")[2])
        
        USER_CONTEXT[user_id]["current_cat"] = cat_id
        
        subcats = [cid for cid, c in DB["categories"].items() if c["parent"] == cat_id]
        prods = [pid for pid, p in DB["products"].items() if p["cat_id"] == cat_id]
        
        txt = "🏪 **تصفح أقسام ومنتجات المتجر المتوفرة:**\n\n"
        if cat_id:
            txt = f"📂 القسم الحالي: **{DB['categories'][cat_id]['name']}**\n\nاختر قسماً فرعياً أو منتجاً لمعاينته:"
            
        kbd = []
        for scid in subcats:
            kbd.append([InlineKeyboardButton(f"📂 {DB['categories'][scid]['name']}", callback_data=f"browse_cat_{scid}")])
        for pid in prods:
            kbd.append([InlineKeyboardButton(f"💎 {DB['products'][pid]['name']}", callback_data=f"view_prod_{pid}")])
            
        back_kbd = []
        if cat_id:
            parent = DB["categories"][cat_id]["parent"]
            back_data = f"browse_cat_{parent}" if parent else "client_shop"
            back_kbd.append(InlineKeyboardButton("⬅️ خلف", callback_data=back_data))
        back_kbd.append(InlineKeyboardButton("🔝 القائمة الرئيسية", callback_data="main_menu"))
        kbd.append(back_kbd)
        
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

    elif data.startswith("view_prod_"):
        pid = int(data.split("_")[2])
        USER_CONTEXT[user_id]["current_prod"] = pid
        p = DB["products"][pid]
        u = DB["users"][user_id]
        
        disc = u["discount"]
        final_jod = p["price_jod"] * (1 - disc/100)
        final_usd = p["price_usd"] * (1 - disc/100)
        
        txt = (
            f"📦 **اسم المنتج:** {p['name']}\n\n"
            f"📝 **الوصف:**\n{p['desc']}\n\n"
            f"💰 **السعر الأصلي:** {p['price_jod']:.2f} JOD / {p['price_usd']:.2f} USD\n"
            f"📉 **سعرك بعد الخصم (%{disc}):** `{final_jod:.2f} JOD` | `{final_usd:.2f} USD`"
        )
        
        kbd = [
            [InlineKeyboardButton("🛒 شراء المنتج الآن", callback_data=f"buy_prod_now")],
            [InlineKeyboardButton("⬅️ رجوع للأقسام", callback_data=f"browse_cat_{p['cat_id'] if p['cat_id'] else ''}")]
        ]
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

    elif data == "buy_prod_now":
        pid = USER_CONTEXT[user_id]["current_prod"]
        p = DB["products"][pid]
        u = DB["users"][user_id]
        final_jod = p["price_jod"] * (1 - u["discount"]/100)
        
        if u["balance_jod"] < final_jod:
            await query.edit_message_text(
                f"❌ رصيدك الحالي غير كافي لإتمام هذه العملية!\n\n"
                f"💵 سعر المنتج: `{final_jod:.2f} JOD` \n"
                f"💳 رصيدك الحالي: `{u['balance_jod']:.2f} JOD`\n\n"
                f"يرجى شحن حسابك أولاً بالذهاب إلى قسم الشحن ثم معاودة المحاولة.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع للمنتج", callback_data=f"view_prod_{pid}")]])
            )
            return ConversationHandler.END
            
        await query.edit_message_text(
            f"📝 **يرجى إرسال المعلومات والبيانات اللازمة المطلوبة لتنفيذ هذا المنتج:**\n"
            f"(مثال: الآيدي الخاص بك في اللعبة، الحساب، الإيميل... إلخ)"
        )
        return CLIENT_WAIT_PROD_INFO

    return ConversationHandler.END

async def client_get_charge_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    txt = update.message.text
    
    oid = DB["order_counter"]
    DB["orders"][oid] = {
        "user_id": user.id,
        "type": "charge",
        "status": "pending",
        "details": txt,
        "prod_id": None
    }
    DB["order_counter"] += 1
    
    await update.message.reply_text("✅ تم إرسال نص وتفاصيل الحوالة للآدمن بنجاح للتأكيد والمراجعة اليدوية.")
    
    admin_txt = (
        f"🚨 **طلب شحن رصيد جديد (قيد المراجعة)!**\n\n"
        f"👤 اسم العميل: {user.full_name}\n"
        f"🆔 آيدي العميل: `{user.id}`\n\n"
        f"📄 **نص الحوالة المرسل:**\n{txt}"
    )
    kbd = [
        [InlineKeyboardButton("✅ قبول والشحن", callback_data=f"adm_order_accept_{oid}"),
         InlineKeyboardButton("❌ رفض الطلب", callback_data=f"adm_order_reject_{oid}")]
    ]
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")
    
    USER_CONTEXT[user.id] = {"current_cat": None, "current_prod": None}
    return ConversationHandler.END

async def client_get_prod_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    info_text = update.message.text
    pid = USER_CONTEXT[user.id]["current_prod"]
    p = DB["products"][pid]
    
    oid = DB["order_counter"]
    DB["orders"][oid] = {
        "user_id": user.id,
        "type": "buy",
        "status": "pending",
        "details": f"منتج: {p['name']} | بيانات العميل: {info_text}",
        "prod_id": pid
    }
    DB["order_counter"] += 1
    
    await update.message.reply_text("✅ تم إرسال طلب الشراء وبياناتك بنجاح. طلبك الآن تحت المراجعة من الإدارة.")
    
    admin_txt = (
        f"🛒 **طلب شراء منتج جديد!**\n\n"
        f"👤 العميل: {user.full_name}\n"
        f"🆔 آيدي العميل: `{user.id}`\n"
        f"📦 المنتج المطلوب: *{p['name']}*\n\n"
        f"📝 **المعلومات والبيانات المرفقة:**\n{info_text}"
    )
    kbd = [
        [InlineKeyboardButton("✅ قبول الطلب", callback_data=f"adm_order_accept_{oid}"),
         InlineKeyboardButton("❌ رفض الطلب", callback_data=f"adm_order_reject_{oid}")]
    ]
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")
    
    return ConversationHandler.END


# =====================================================================
#                  [ ⚙️ لوحة التحكم للآدمن ]
# =====================================================================

async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("❌ عذراً، لا تمتلك الصلاحيات الكافية لفتح لوحة الآدمن.")
        return ConversationHandler.END
        
    txt = "⚙️ **مرحباً بك سلمان في لوحة التحكم الإدارية:**\n\nيرجى اختيار القسم المراد إدارته والتحكم به:"
    kbd = [
        [InlineKeyboardButton("📂 إدارة المتجر والأقسام", callback_data="adm_manage_shop")],
        [InlineKeyboardButton("👥 قائمة الزبائن والعملاء", callback_data="adm_list_users")],
        [InlineKeyboardButton("📢 إرسال إعلان / برودكاست", callback_data="adm_broadcast_menu")],
        [InlineKeyboardButton("📉 إدارة الخصومات للزبائن", callback_data="adm_discounts_menu")],
        [InlineKeyboardButton("🔝 القائمة الرئيسية للمستخدم", callback_data="main_menu")]
    ]
    await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")
    return ConversationHandler.END

async def admin_callback_dispatcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if query.from_user.id != ADMIN_ID:
        return ConversationHandler.END

    if data.startswith("adm_order_accept_"):
        oid = int(data.split("_")[3])
        if oid not in DB["orders"] or DB["orders"][oid]["status"] != "pending":
            await query.edit_message_text("⚠️ هذا الطلب تم معالجته مسبقاً أو غير موجود.")
            return ConversationHandler.END
            
        order = DB["orders"][oid]
        if ADMIN_ID not in USER_CONTEXT:
            USER_CONTEXT[ADMIN_ID] = {}
        USER_CONTEXT[ADMIN_ID]["target_order"] = oid
        
        if order["type"] == "buy":
            pid = order["prod_id"]
            p = DB["products"][pid]
            uid = order["user_id"]
            u = DB["users"][uid]
            
            final_jod = p["price_jod"] * (1 - u["discount"]/100)
            final_usd = p["price_usd"] * (1 - u["discount"]/100)
            
            if u["balance_jod"] >= final_jod:
                u["balance_jod"] -= final_jod
                u["balance_usd"] -= final_usd
                order["status"] = "accepted"
                
                await query.edit_message_text(f"✅ تم قبول طلب الشراء رقم `{oid}` وخصم السعر بنجاح.")
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"🎉 **تم قبول طلبك لشراء ({p['name']}) بنجاح!**\nتم خصم القيمة من رصيدك، شكراً لتعاملك معنا."
                )
            else:
                await query.edit_message_text("❌ فشل القبول بسبب عدم توفر رصيد كافي فجائي لدى الزبون.")
        
        elif order["type"] == "charge":
            await query.edit_message_text("💵 **يرجى كتابة وإرسال قيمة الرصيد المراد إضافته للزبون بالدولار ($):**")
            return ADMIN_WAIT_CHARGE_AMOUNT

    elif data.startswith("adm_order_reject_"):
        oid = int(data.split("_")[3])
        if oid not in DB["orders"] or DB["orders"][oid]["status"] != "pending":
            await query.edit_message_text("⚠️ هذا الطلب تم معالجته مسبقاً.")
            return ConversationHandler.END
            
        order = DB["orders"][oid]
        order["status"] = "rejected"
        uid = order["user_id"]
        
        await query.edit_message_text(f"❌ تم رفض الطلب رقم `{oid}` بنجاح وإشعار المستخدم.")
        
        if order["type"] == "buy":
            await context.bot.send_message(chat_id=uid, text="❌ **تم رفض طلب الشراء الخاص بك.** يرجى التواصل مع الإدارة الفنية لمعرفة السبب.")
        else:
            await context.bot.send_message(chat_id=uid, text="❌ **تم رفض طلب شحن الرصيد الخاص بك.** يرجى الاتصال بالدعم الفني.")
            
        return ConversationHandler.END

    elif data == "adm_manage_shop" or data.startswith("adm_browse_"):
        cat_id = None
        if data.startswith("adm_browse_"):
            cat_id = int(data.split("_")[2])
            
        if ADMIN_ID not in USER_CONTEXT:
            USER_CONTEXT[ADMIN_ID] = {}
        USER_CONTEXT[ADMIN_ID]["current_cat"] = cat_id
        
        subcats = [cid for cid, c in DB["categories"].items() if c["parent"] == cat_id]
        prods = [pid for pid, p in DB["products"].items() if p["cat_id"] == cat_id]
        
        txt = "📂 **إدارة أقسام المتجر الحالية:**\n\n"
        if cat_id:
            txt += f"القسم الحالي المفتوح: **{DB['categories'][cat_id]['name']}**\n\n"
        txt += "يمكنك إضافة أقسام فرعية أو منتجات داخل القسم المفتوح بلا حدود، أو الحذف بالضغط على زر الحذف الخارجي (❌):"
        
        kbd = []
        for scid in subcats:
            kbd.append([
                InlineKeyboardButton(f"📂 {DB['categories'][scid]['name']}", callback_data=f"adm_browse_{scid}"),
                InlineKeyboardButton("❌ حذف القسم", callback_data=f"adm_del_cat_{scid}")
            ])
        for pid in prods:
            kbd.append([
                InlineKeyboardButton(f"💎 {DB['products'][pid]['name']}", callback_data=f"adm_noop_{pid}"),
                InlineKeyboardButton("❌ حذف المنتج", callback_data=f"adm_del_prod_{pid}")
            ])
            
        kbd.append([InlineKeyboardButton("➕ إضافة قسم جديد هنا", callback_data="adm_add_cat")])
        kbd.append([InlineKeyboardButton("➕ إضافة منتج داخل هذا القسم", callback_data="adm_add_prod")])
            
        back_kbd = []
        if cat_id:
            parent = DB["categories"][cat_id]["parent"]
            back_data = f"adm_browse_{parent}" if parent else "adm_manage_shop"
            back_kbd.append(InlineKeyboardButton("⬅️ خلف", callback_data=back_data))
        back_kbd.append(InlineKeyboardButton("⚙️ لوحة الآدمن", callback_data="admin_panel"))
        kbd.append(back_kbd)
        
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

    elif data == "adm_add_cat":
        await query.edit_message_text("📝 **يرجى كتابة وإرسال اسم القسم الجديد المراد إنشاؤه:**")
        return ADMIN_WAIT_CAT_NAME

    elif data == "adm_add_prod":
        await query.edit_message_text("📝 **يرجى إرسال اسم المنتج الجديد:**")
        return ADMIN_WAIT_PROD_NAME

    elif data.startswith("adm_del_cat_"):
        cid = int(data.split("_")[3])
        DB["categories"].pop(cid, None)
        to_del = [pid for pid, p in DB["products"].items() if p["cat_id"] == cid]
        for p_id in to_del: DB["products"].pop(p_id, None)
        
        await query.edit_message_text("✅ تم حذف القسم وجميع محتوياته المباشرة بنجاح. اضغط /start للتحديث.")
        return ConversationHandler.END

    elif data.startswith("adm_del_prod_"):
        pid = int(data.split("_")[3])
        DB["products"].pop(pid, None)
        await query.edit_message_text("✅ تم حذف المنتج من القسم بنجاح. اضغط /start للتحديث.")
        return ConversationHandler.END

    elif data == "adm_list_users":
        txt = "👥 **قائمة العملاء والزبائن المسجلين في البوت حالياً:**\n\n"
        for uid, u in DB["users"].items():
            txt += f"👤 الاسم: {u['name']} | آيدي الحساب: `{uid}`\n💰 رصيد: `{u['balance_jod']:.2f} JOD` | `% {u['discount']}` خصم\n-----------------------\n"
        kbd = [[InlineKeyboardButton("⬅️ رجوع للوحة التحكم", callback_data="admin_panel")]]
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kbd), parse_mode="Markdown")

    elif data == "adm_broadcast_menu":
        txt = "📢 **قسم إرسال الإعلانات والرسائل الترويجية:**\n\nيرجى تحديد فئة الاستشاف المرادة:"
        kbd = [
            [InlineKeyboardButton("🌍 إرسال إعلان شامل للكل", callback_data="adm_bc_all")],
            [InlineKeyboardButton("👤 إرسال إعلان لشخص معين", callback_data="adm_bc_user")],
            [InlineKeyboardButton("⬅️ رجوع للوحة التحكم", callback_data="admin_panel")]
        ]
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kbd))

    elif data == "adm_bc_all":
        await query.edit_message_text("📢 **يرجى كتابة نص الإعلان العام المراد إرساله لجميع مستخدمين البوت دفعة واحدة:**")
        return ADMIN_WAIT_BROADCAST_ALL

    elif data == "adm_bc_user":
        await query.edit_message_text("🆔 **يرجى إرسال آيدي (ID) العميل المستهدف أولاً لتوجيه الرسالة له:**")
        return ADMIN_WAIT_BROADCAST_USER_ID

    elif data == "adm_discounts_menu":
        await query.edit_message_text("📉 **إدارة الخصومات الاستثنائية للزبائن:**\n\nيرجى إرسال آيدي (ID) الزبون المراد تعديل خصمه الخاص:")
        return ADMIN_WAIT_DISCOUNT_USER_ID

    return ConversationHandler.END


# =====================================================================
#                      [ استكمال عمليات الإدخال الفنية للآدمن ]
# =====================================================================

async def adm_get_cat_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    parent = USER_CONTEXT.get(ADMIN_ID, {}).get("current_cat")
    cid = DB["cat_counter"]
    
    DB["categories"][cid] = {"name": name, "parent": parent, "subcats": [], "products": []}
    DB["cat_counter"] += 1
    
    await update.message.reply_text(f"✅ تم إضافة القسم الجديد بنجاح باسم: {name}\nاضغط /start لتحديث الواجهة.")
    return ConversationHandler.END

async def adm_get_prod_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_ID not in USER_CONTEXT: USER_CONTEXT[ADMIN_ID] = {}
    USER_CONTEXT[ADMIN_ID]["new_prod_name"] = update.message.text
    await update.message.reply_text("📝 **الآن، يرجى إرسال تفاصيل ووصف هذا المنتج:**")
    return ADMIN_WAIT_PROD_DESC

async def adm_get_prod_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USER_CONTEXT[ADMIN_ID]["new_prod_desc"] = update.message.text
    await update.message.reply_text("🇯🇴 **الآن، يرجى إدخال سعر المنتج بالدينار الأردني (رقم فقط):**")
    return ADMIN_WAIT_PROD_JOD

async def adm_get_prod_jod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text)
        USER_CONTEXT[ADMIN_ID]["new_prod_jod"] = price
        await update.message.reply_text("💵 **الآن، يرجى إدخال سعر المنتج بالدولار الأمريكي (رقم فقط):**")
        return ADMIN_WAIT_PROD_USD
    except ValueError:
        await update.message.reply_text("⚠️ يرجى إدخال قيمة رقمية صحيحة للسعر (مثال: 5 أو 10.50):")
        return ADMIN_WAIT_PROD_JOD

async def adm_get_prod_usd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price_usd = float(update.message.text)
        pid = DB["prod_counter"]
        cat_id = USER_CONTEXT.get(ADMIN_ID, {}).get("current_cat")
        
        DB["products"][pid] = {
            "name": USER_CONTEXT[ADMIN_ID]["new_prod_name"],
            "desc": USER_CONTEXT[ADMIN_ID]["new_prod_desc"],
            "price_jod": USER_CONTEXT[ADMIN_ID]["new_prod_jod"],
            "price_usd": price_usd,
            "cat_id": cat_id
        }
        DB["prod_counter"] += 1
        
        await update.message.reply_text(f"✅ تم إنشاء وحفظ المنتج الإعلاني بنجاح كامل ومتاح للزبائن.\nاضغط /start للتحديث.")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("⚠️ يرجى إدخال قيمة رقمية صحيحة للسعر بالدولار:")
        return ADMIN_WAIT_PROD_USD

async def adm_get_charge_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount_usd = float(update.message.text)
        amount_jod = amount_usd * 0.71
        
        oid = USER_CONTEXT.get(ADMIN_ID, {}).get("target_order")
        order = DB["orders"][oid]
        uid = order["user_id"]
        
        DB["users"][uid]["balance_usd"] += amount_usd
        DB["users"][uid]["balance_jod"] += amount_jod
        order["status"] = "accepted"
        
        await update.message.reply_text(f"✅ تم بنجاح إضافة الرصيد للزبون تلقائياً بقيمة `{amount_usd:.2f} USD` ما يعادل `{amount_jod:.2f} JOD`.")
        await context.bot.send_message(
            chat_id=uid,
            text=f"🎉 **تم إضافة وشحن الرصيد إلى محفظتك بنجاح!**\n💰 القيمة المضافة: `{amount_usd:.2f} USD` / `{amount_jod:.2f} JOD`."
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("⚠️ يرجى إدخال قيمة مالية رقمية صحيحة للشحن:")
        return ADMIN_WAIT_CHARGE_AMOUNT

async def adm_bc_all_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    count = 0
    for uid in DB["users"].keys():
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 **إعلان هام من الإدارة:**\n\n{msg}")
            count += 1
        except Exception:
            continue
    await update.message.reply_text(f"📢 تمت عملية الإرسال الجماعي بنجاح، استلمها {count} عميل حالي.")
    return ConversationHandler.END

async def adm_bc_user_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(update.message.text)
        if target_id not in DB["users"]:
            await update.message.reply_text("⚠️ هذا المستخدم لم يقم بتسجيل الدخول للبوت من قبل، يرجى التحقق من الآيدي:")
            return ADMIN_WAIT_BROADCAST_USER_ID
        if ADMIN_ID not in USER_CONTEXT: USER_CONTEXT[ADMIN_ID] = {}
        USER_CONTEXT[ADMIN_ID]["target_user"] = target_id
        await update.message.reply_text("📝 **الآن، أرسل محتوى ومضمون الرسالة الموجهة لهذا العميل:**")
        return ADMIN_WAIT_BROADCAST_USER_MSG
    except ValueError:
        await update.message.reply_text("⚠️ يرجى إدخال آيدي رقمي صحيح:")
        return ADMIN_WAIT_BROADCAST_USER_ID

async def adm_bc_user_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    target_id = USER_CONTEXT[ADMIN_ID]["target_user"]
    try:
        await context.bot.send_message(chat_id=target_id, text=f"📩 **رسالة خاصة من الإدارة:**\n\n{msg}")
        await update.message.reply_text("✅ تم إرسال الرسالة الخاصة للعميل بنجاح.")
    except Exception as e:
        await update.message.reply_text(f"❌ تعذر الإرسال بسبب حظر العميل للبوت أو خطأ تقني: {e}")
    return ConversationHandler.END

async def adm_discount_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(update.message.text)
        if target_id not in DB["users"]:
            await update.message.reply_text("⚠️ المستخدم غير مسجل، تأكد من الآيدي الصحيح:")
            return ADMIN_WAIT_DISCOUNT_USER_ID
        if ADMIN_ID not in USER_CONTEXT: USER_CONTEXT[ADMIN_ID] = {}
        USER_CONTEXT[ADMIN_ID]["target_user"] = target_id
        await update.message.reply_text("📉 **الآن، أرسل نسبة الخصم المئوية المطلوبة للزبون (رقم من 0 إلى 100 فقط):**")
        return ADMIN_WAIT_DISCOUNT_PERCENT
    except ValueError:
        await update.message.reply_text("⚠️ يرجى إدخال آيدي رقمي صحيح:")
        return ADMIN_WAIT_DISCOUNT_USER_ID

async def adm_discount_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        pct = int(update.message.text)
        if not (0 <= pct <= 100):
            await update.message.reply_text("⚠️ يجب أن تكون النسبة بين 0 و 100:")
            return ADMIN_WAIT_DISCOUNT_PERCENT
            
        target_id = USER_CONTEXT[ADMIN_ID]["target_user"]
        DB["users"][target_id]["discount"] = pct
        await update.message.reply_text(f"📉 تم بنجاح تطبيق خصم دائم بنسبة %{pct} على كافة الأسعار للعميل صاحب الآيدي `{target_id}`.")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("⚠️ يرجى إدخال رقم صحيح لنسبة الخصم:")
        return ADMIN_WAIT_DISCOUNT_PERCENT


# =====================================================================
#                          [ نظام التشغيل والربط ]
# =====================================================================

def main():
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(client_handler, pattern="^(charge_orange|buy_prod_now)$"),
            CallbackQueryHandler(admin_callback_dispatcher, pattern="^(adm_order_accept_|adm_add_cat|adm_add_prod|adm_bc_all|adm_bc_user|adm_discounts_menu)$")
        ],
        states={
            CLIENT_WAIT_CHARGE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, client_get_charge_text)],
            CLIENT_WAIT_PROD_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, client_get_prod_info)],
            ADMIN_WAIT_CAT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_get_cat_name)],
            ADMIN_WAIT_PROD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_get_prod_name)],
            ADMIN_WAIT_PROD_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_get_prod_desc)],
            ADMIN_WAIT_PROD_JOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_get_prod_jod)],
            ADMIN_WAIT_PROD_USD: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_get_prod_usd)],
            ADMIN_WAIT_CHARGE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_get_charge_amount)],
            ADMIN_WAIT_BROADCAST_ALL: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_bc_all_send)],
            ADMIN_WAIT_BROADCAST_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_bc_user_get_id)],
            ADMIN_WAIT_BROADCAST_USER_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_bc_user_send)],
            ADMIN_WAIT_DISCOUNT_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_discount_get_id)],
            ADMIN_WAIT_DISCOUNT_PERCENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_discount_set)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )

    # إضافة الـ ConversationHandler أولاً لحفظ ترتيب حالات الإدخال النصية
    application.add_handler(conv_handler)
    
    # إضافة CommandHandler للأمر start بشكل أساسي
    application.add_handler(CommandHandler("start", start))
    
    # إضافة الـ Callbacks العامة لكل الأزرار العادية التي لا تحتاج انتظار نصوص
    application.add_handler(CallbackQueryHandler(admin_panel_handler, pattern="^admin_panel$"))
    application.add_handler(CallbackQueryHandler(admin_callback_dispatcher, pattern="^(adm_manage_shop|adm_browse_|adm_del_cat_|adm_del_prod_|adm_list_users|adm_broadcast_menu|adm_bc_all|adm_bc_user|adm_order_reject_)"))
    application.add_handler(CallbackQueryHandler(client_handler, pattern="^(client_shop|browse_cat_|view_prod_|main_menu|client_profile|client_support|client_orders|client_charge)$"))

    # تشغيل البوت بسلاسة
    application.run_polling()

if __name__ == "__main__":
    main()
