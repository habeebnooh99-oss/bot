from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
import asyncio
import os
import json

# التوكنات
bot = Bot(token="8843060512:AAGH3WvLBmK9MgguZia5lpLW3WfJgLAGMRA")
dp = Dispatcher(storage=MemoryStorage())
ADMIN_BOT_TOKEN = "8741135682:AAEW-c-3D9NGPCwtnFsG35BYOz0yZtGjqj0"
admin_bot = Bot(token=ADMIN_BOT_TOKEN)
ADMIN_ID = 8529336745

# حالات البوت
class OrderStates(StatesGroup):
    waiting_for_amount = State()

class CustomerStates(StatesGroup):
    waiting_for_player_id = State()
    buy_path = State()
    buy_price = State()

# --- دوال جلب البيانات ---
def load_tree():
    if not os.path.exists("store_tree.json"): return {"type": "folder", "children": {}}
    with open("store_tree.json", "r", encoding="utf-8") as f: return json.load(f)

def get_node(path):
    data = load_tree()
    if path == "root": return data
    curr = data
    for key in path.split(">"):
        curr = curr["children"].get(key, {"type": "folder", "children": {}})
    return curr

def load_discounts():
    if not os.path.exists("discounts.json"): return {}
    with open("discounts.json", "r", encoding="utf-8") as f: return json.load(f)

# دالة التسجيل التلقائي للزبائن
def register_user(user_id, username, first_name):
    if not os.path.exists("users.txt"):
        open("users.txt", "w").close()
    with open("users.txt", "r") as f:
        users = f.read().splitlines()
    if str(user_id) not in users:
        with open("users.txt", "a") as f:
            f.write(str(user_id) + "\n")
        try:
            admin_bot.send_message(
                ADMIN_ID, 
                f"🆕 زبون جديد في المتجر!\n👤 الاسم: {first_name}\n🆔 الآيدي: <code>{user_id}</code>",
                parse_mode=ParseMode.HTML
            )
        except:
            pass
    
    if not os.path.exists("balances.txt"):
        open("balances.txt", "w").close()
    with open("balances.txt", "r") as f:
        lines = f.read().splitlines()
    if not any(str(user_id) in line for line in lines):
        with open("balances.txt", "a") as f:
            f.write(f"{user_id}:0.0\n")

# دالة جلب الرصيد
def get_balance(user_id):
    if not os.path.exists("balances.txt"):
        return 0.0
    with open("balances.txt", "r") as f:
        for line in f:
            if ":" in line:
                uid, bal = line.strip().split(":")
                if uid == str(user_id):
                    return float(bal)
    return 0.0

# دالة تحديث الرصيد
def update_balance(user_id, amount):
    balances = {}
    if os.path.exists("balances.txt"):
        with open("balances.txt", "r") as f:
            for line in f:
                if ":" in line:
                    uid, bal = line.strip().split(":")
                    balances[uid] = float(bal)
    balances[str(user_id)] = balances.get(str(user_id), 0.0) + float(amount)
    with open("balances.txt", "w") as f:
        for uid, bal in balances.items():
            f.write(f"{uid}:{bal}\n")

# القوائم
def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍️ المتجر", callback_data="open_root")],
        [InlineKeyboardButton(text="💰 شحن الرصيد", callback_data="add_balance")],
        [InlineKeyboardButton(text="🛒 طلباتي", callback_data="my_orders")],
        [InlineKeyboardButton(text="👤 حسابي", callback_data="my_account")],
        [InlineKeyboardButton(text="🎧 الدعم الفني", callback_data="support")]
    ])

@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    register_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer("أهلاً بك في ALEX STORE! اختر ما تحتاجه من القائمة:", reply_markup=get_main_menu())

@dp.message(Command("list"))
async def show_users(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        if os.path.exists("users.txt"):
            with open("users.txt", "r") as f:
                users = f.read().splitlines()
                await message.answer(f"👥 **قائمة الزبائن ({len(users)}):**\n\n" + "\n".join([f"<code>{u}</code>" for u in users]), parse_mode=ParseMode.HTML)

@dp.message(F.photo | F.document | F.text | F.video)
async def forward_to_admin(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        return
    current_state = await state.get_state()
    if current_state == CustomerStates.waiting_for_player_id.state:
        return
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ قبول", callback_data=f"accept_{message.from_user.id}"),
         InlineKeyboardButton(text="❌ رفض", callback_data=f"reject_{message.from_user.id}")]
    ])
    text = f"🔔 طلب جديد من: {message.from_user.first_name}\n🆔 الآيدي: <code>{message.from_user.id}</code>"
    if message.photo:
        await admin_bot.send_photo(ADMIN_ID, photo=message.photo[-1].file_id, caption=text, reply_markup=kb, parse_mode=ParseMode.HTML)
    elif message.document:
        await admin_bot.send_document(ADMIN_ID, document=message.document.file_id, caption=text, reply_markup=kb, parse_mode=ParseMode.HTML)
    elif message.video:
        await admin_bot.send_video(ADMIN_ID, video=message.video.file_id, caption=text, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        await admin_bot.send_message(ADMIN_ID, f"{text}\n\nالرسالة: {message.text}", reply_markup=kb, parse_mode=ParseMode.HTML)
    await message.answer("✅ تم استلام طلبك وإرساله للإدارة!")

@dp.message(OrderStates.waiting_for_amount)
async def process_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        data = await state.get_data()
        uid = data.get('uid')
        if not uid:
            return
        update_balance(uid, amount)
        await message.answer(f"✅ تمت إضافة {amount}$ للزبون `{uid}`.")
        await bot.send_message(chat_id=int(uid), text=f"🎉 تم قبول طلبك! تمت إضافة {amount}$ لرصيدك.", parse_mode=ParseMode.HTML)
        await state.clear()
    except Exception as e:
        await message.answer(f"⚠️ خطأ: {str(e)}")

@dp.message(CustomerStates.waiting_for_player_id)
async def process_buy_id(message: types.Message, state: FSMContext):
    user_input = message.text
    data = await state.get_data()
    path = data.get('buy_path')
    price = data.get('buy_price')
    input_type = data.get('input_type', 'id')
    user_id = message.from_user.id
    
    # فحص الآيدي للألعاب فقط (من 6 لـ 15 رقم)
    if input_type == "id":
        if not user_input.isdigit() or not (6 <= len(user_input) <= 15):
            await message.answer("⚠️ خطأ: الآيدي يجب أن يكون أرقاماً فقط وطوله بين 6 و 15 رقم.")
            return

    bal = get_balance(user_id)
    if bal < price:
        await message.answer(f"⚠️ رصيدك غير كافي لإتمام العملية.\n💰 السعر المطلوب: {price}$\n💵 رصيدك الحالي: {bal}$", reply_markup=get_main_menu())
        await state.clear()
        return

    update_balance(user_id, -float(price))
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ تم الشحن", callback_data=f"doneorder_{user_id}_{price}"),
         InlineKeyboardButton(text="❌ مرفوض (إرجاع الرصيد)", callback_data=f"failorder_{user_id}_{price}")]
    ])
    admin_msg = (f"🛍️ **طلب شراء جديد!**\n\n"
                 f"👤 الزبون: {message.from_user.first_name} (<code>{user_id}</code>)\n"
                 f"🛒 المنتج: {path.split('>')[-1]}\n"
                 f"💵 السعر المخصوم: {price}$\n"
                 f"🎯 المعلومة المدخلة: <code>{user_input}</code>")
    try:
        await admin_bot.send_message(ADMIN_ID, admin_msg, reply_markup=admin_kb, parse_mode=ParseMode.HTML)
    except: pass
    
    await message.answer(f"✅ تم خصم {price}$ من رصيدك وإرسال طلبك للإدارة.\nسيصلك إشعار فور إتمام الشحن.", reply_markup=get_main_menu())
    await state.clear()

@dp.callback_query(F.data.startswith("open_"))
async def open_tree_node(call: types.CallbackQuery):
    path = call.data.replace("open_", "")
    node = get_node(path)
    kb = []
    
    for name, item in node.get("children", {}).items():
        new_path = f"{path}>{name}" if path != "root" else name
        
        # التعديل هنا: فحص المجلدات أولاً لضمان عدم خلطها مع المنتجات
        if item.get("type") == "folder" or "children" in item:
            kb.append([InlineKeyboardButton(text=f"📁 {name}", callback_data=f"open_{new_path}")])
        elif "price" in item:
            price = item.get('price', 0)
            kb.append([InlineKeyboardButton(text=f"🛒 {name} ({price}$)", callback_data=f"buyprod_{new_path}")])
        else:
            kb.append([InlineKeyboardButton(text=f"🛒 {name}", callback_data=f"buyprod_{new_path}")])
            
    if path == "root":
        kb.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="back_main")])
    else:
        parent_path = ">".join(path.split(">")[:-1]) if ">" in path else "root"
        kb.append([InlineKeyboardButton(text="🔙 رجوع", callback_data=f"open_{parent_path}")])

    text = "🛍️ أقسام المتجر:" if path == "root" else f"📁 قسم: {path.split('>')[-1]}"
    
    if not kb:
        await call.answer("هذا القسم فارغ حالياً", show_alert=True)
    else:
        await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("buyprod_"))
async def start_buy_product(call: types.CallbackQuery, state: FSMContext):
    path = call.data.replace("buyprod_", "")
    node = get_node(path)
    price_usd = float(node.get("price", 0))
    input_type = node.get("input_type", "id")
    
    discounts = load_discounts()
    user_discount = float(discounts.get(str(call.from_user.id), 0))
    final_price_usd = price_usd - (price_usd * (user_discount / 100))
    price_jod = final_price_usd * 0.71
    
    if input_type == "id":
        instr = "🆔 الرجاء إرسال (آيدي اللعبة - من 6 إلى 15 رقم):"
    elif input_type == "username":
        instr = "👤 الرجاء إرسال (يوزر الحساب):"
    elif input_type == "link":
        instr = "🔗 الرجاء إرسال (الرابط المطلوب):"
    else:
        instr = "الرجاء إرسال البيانات المطلوبة:"
    
    msg = (f"🛒 **المنتج:** {path.split('>')[-1]}\n"
           f"💰 **السعر النهائي (دولار):** {final_price_usd:.2f} $\n"
           f"🇯🇴 **السعر النهائي (دينار):** {price_jod:.2f} JOD\n"
           f"🏷️ **نسبة خصمك:** {user_discount}%\n\n"
           f"{instr}")
           
    await state.update_data(buy_path=path, buy_price=final_price_usd, input_type=input_type)
    await state.set_state(CustomerStates.waiting_for_player_id)
    
    parent_path = ">".join(path.split(">")[:-1]) if ">" in path else "root"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ إلغاء الشراء", callback_data=f"open_{parent_path}")]])
    await call.message.edit_text(msg, reply_markup=kb, parse_mode=ParseMode.HTML)

@dp.callback_query(F.data.startswith("doneorder_"))
async def admin_done_order(call: types.CallbackQuery):
    _, uid, price = call.data.split("_", 2)
    await call.message.edit_text(call.message.text + "\n\n✅ **تم الشحن بنجاح**")
    try:
        await bot.send_message(chat_id=int(uid), text=f"🎉 تم شحن طلبك بنجاح!", parse_mode=ParseMode.HTML)
    except: pass
    await call.answer()

@dp.callback_query(F.data.startswith("failorder_"))
async def admin_fail_order(call: types.CallbackQuery):
    _, uid, price = call.data.split("_", 2)
    update_balance(uid, float(price))
    await call.message.edit_text(call.message.text + "\n\n❌ **تم الرفض وتم إرجاع الرصيد للزبون**")
    try:
        await bot.send_message(chat_id=int(uid), text=f"❌ نعتذر، تم رفض طلب الشحن الخاص بك.\n💰 تم إرجاع المبلغ ({price}$) إلى رصيدك التلقائي.", parse_mode=ParseMode.HTML)
    except: pass
    await call.answer()

@dp.callback_query()
async def callback_handler(call: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state == CustomerStates.waiting_for_player_id.state:
        await state.clear()

    if call.data.startswith("accept_"):
        uid = call.data.split("_")[1]
        await state.update_data(uid=uid)
        await state.set_state(OrderStates.waiting_for_amount)
        await call.message.edit_text(f"✅ تم القبول لآيدي `{uid}`. اكتب المبلغ:")
        return
    elif call.data.startswith("reject_"):
        uid = call.data.split("_")[1]
        await call.message.edit_text(f"❌ تم رفض الآيدي: `{uid}`")
        await bot.send_message(chat_id=int(uid), text="❌ تم رفض طلب شحن الرصيد الخاص بك.")
        return

    back_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 رجوع", callback_data="back_main")]])
    
    if call.data == "back_main":
        await call.message.edit_text("أهلاً بك في ALEX STORE! اختر ما تحتاجه من القائمة:", reply_markup=get_main_menu())
    elif call.data == "my_account":
        bal = get_balance(call.from_user.id)
        text = (f"👤 **بيانات حسابك:**\n"
                f"👤 الاسم: {call.from_user.first_name}\n"
                f"🆔 الآيدي: <code>{call.from_user.id}</code>\n"
                f"💰 رصيدك: {bal:.1f} $\n"
                f"💵 رصيدك بالدينار: {bal*0.71:.2f} JOD")
        await call.message.edit_text(text, reply_markup=back_kb, parse_mode=ParseMode.HTML)
    elif call.data == "add_balance":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="أورنج موني", callback_data="pay_orange"), 
             InlineKeyboardButton(text="باينانس", callback_data="pay_binance")], 
            [InlineKeyboardButton(text="🔙 رجوع", callback_data="back_main")]
        ])
        await call.message.edit_text("💰 اختر وسيلة الدفع:", reply_markup=kb)
    elif call.data == "pay_orange":
        await call.message.edit_text("💰 **محفظة أورنج موني:**\nالاسم: سلمان نوح سلمان\nالرقم: <code>0776445110</code>\n\nيرجى إرسال وصل التحويل هنا لتأكيد الطلب.", reply_markup=back_kb, parse_mode=ParseMode.HTML)
    elif call.data == "support":
        text = ("🎧 **للدعم الفني:**\n\n"
                "📞 <a href='tel:+962776445110'>اتصال: 0776445110</a>\n"
                "💬 <a href='https://wa.me/962776445110'>واتساب</a>\n"
                "✈️ <a href='https://t.me/htb1b'>تليجرام الإدارة: @htb1b</a>")
        await call.message.edit_text(text, reply_markup=back_kb, parse_mode=ParseMode.HTML)
    elif call.data == "my_orders":
        await call.message.edit_text("🛒 طلباتك الحالية:\nلا توجد طلبات معلقة.", reply_markup=back_kb)
        
    await call.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
