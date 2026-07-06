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

# --- دالة جلب البيانات المباشرة ---
def get_node(path):
    if not os.path.exists("store_tree.json"): 
        return {"type": "folder", "children": {}}
    
    with open("store_tree.json", "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except:
            return {"type": "folder", "children": {}}
    
    if path == "root" or not path: return data
    
    curr = data
    for key in path.split(">"):
        children = curr.get("children", {})
        curr = children.get(key, {"type": "folder", "children": {}})
    return curr

def load_discounts():
    if not os.path.exists("discounts.json"): return {}
    with open("discounts.json", "r", encoding="utf-8") as f: return json.load(f)

# دالة التسجيل التلقائي
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
                f"🆕 زبون جديد!\n👤 الاسم: {first_name}\n🆔 الآيدي: <code>{user_id}</code>",
                parse_mode=ParseMode.HTML
            )
        except: pass
    
    if not os.path.exists("balances.txt"):
        open("balances.txt", "w").close()
    with open("balances.txt", "r") as f:
        lines = f.read().splitlines()
    if not any(str(user_id) in line for line in lines):
        with open("balances.txt", "a") as f:
            f.write(f"{user_id}:0.0\n")

def get_balance(user_id):
    if not os.path.exists("balances.txt"): return 0.0
    with open("balances.txt", "r") as f:
        for line in f:
            if ":" in line:
                uid, bal = line.strip().split(":")
                if uid == str(user_id): return float(bal)
    return 0.0

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
    await message.answer("أهلاً بك في ALEX STORE! اختر ما تحتاجه:", reply_markup=get_main_menu())

@dp.message(F.photo | F.document | F.text | F.video)
async def forward_to_admin(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/"): return
    if await state.get_state() == CustomerStates.waiting_for_player_id.state: return
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ قبول", callback_data=f"accept_{message.from_user.id}"),
         InlineKeyboardButton(text="❌ رفض", callback_data=f"reject_{message.from_user.id}")]
    ])
    text = f"🔔 طلب جديد من: {message.from_user.first_name}\n🆔 الآيدي: <code>{message.from_user.id}</code>"
    if message.photo: await admin_bot.send_photo(ADMIN_ID, photo=message.photo[-1].file_id, caption=text, reply_markup=kb, parse_mode=ParseMode.HTML)
    elif message.document: await admin_bot.send_document(ADMIN_ID, document=message.document.file_id, caption=text, reply_markup=kb, parse_mode=ParseMode.HTML)
    elif message.video: await admin_bot.send_video(ADMIN_ID, video=message.video.file_id, caption=text, reply_markup=kb, parse_mode=ParseMode.HTML)
    else: await admin_bot.send_message(ADMIN_ID, f"{text}\n\nالرسالة: {message.text}", reply_markup=kb, parse_mode=ParseMode.HTML)
    await message.answer("✅ تم استلام طلبك وإرساله للإدارة!")

@dp.message(OrderStates.waiting_for_amount)
async def process_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        data = await state.get_data()
        uid = data.get('uid')
        update_balance(uid, amount)
        await message.answer(f"✅ تمت إضافة {amount}$ للزبون `{uid}`.")
        await bot.send_message(chat_id=int(uid), text=f"🎉 تم قبول طلبك! تمت إضافة {amount}$ لرصيدك.")
        await state.clear()
    except: await message.answer("⚠️ خطأ في القيمة، أرسل رقماً فقط.")

# --- التعديل الجوهري هنا ---
@dp.message(CustomerStates.waiting_for_player_id)
async def process_buy_id(message: types.Message, state: FSMContext):
    user_input = message.text
    data = await state.get_data()
    path = data.get('buy_path')
    price = data.get('buy_price')
    user_id = message.from_user.id
    
    bal = get_balance(user_id)
    if bal < price:
        await message.answer(f"⚠️ رصيدك غير كافي.\n💰 السعر: {price}$\n💵 رصيدك: {bal}$", reply_markup=get_main_menu())
        await state.clear()
        return

    update_balance(user_id, -float(price))
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ تم التنفيذ", callback_data=f"doneorder_{user_id}_{price}"),
         InlineKeyboardButton(text="❌ رفض (إرجاع المبلغ)", callback_data=f"failorder_{user_id}_{price}")]
    ])
    admin_msg = (f"🛍️ **طلب شراء جديد (أي منتج)!**\n\n"
                 f"👤 الزبون: {message.from_user.first_name} (<code>{user_id}</code>)\n"
                 f"🛒 المنتج: {path.split('>')[-1]}\n"
                 f"💵 المبلغ المخصوم: {price}$\n"
                 f"🎯 **بيانات الزبون:**\n<code>{user_input}</code>")
    
    await admin_bot.send_message(ADMIN_ID, admin_msg, reply_markup=admin_kb, parse_mode=ParseMode.HTML)
    await message.answer(f"✅ تم خصم {price}$ وإرسال بياناتك للإدارة.\nسيصلك إشعار عند التنفيذ.", reply_markup=get_main_menu())
    await state.clear()

@dp.callback_query(F.data.startswith("open_"))
async def open_tree_node(call: types.CallbackQuery):
    path = call.data.replace("open_", "")
    node = get_node(path)
    kb = []
    children = node.get("children", {})
    if not children:
        await call.answer("هذا القسم فارغ", show_alert=True)
        return
    for name, item in children.items():
        new_path = f"{path}>{name}" if path != "root" else name
        if item.get("type") == "folder": kb.append([InlineKeyboardButton(text=f"📁 {name}", callback_data=f"open_{new_path}")])
        else: kb.append([InlineKeyboardButton(text=f"🛒 {name} ({item.get('price', 0)}$)", callback_data=f"buyprod_{new_path}")])
    kb.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="back_main" if path == "root" else f"open_{'>'.join(path.split('>')[:-1]) if '>' in path else 'root'}")])
    await call.message.edit_text("🛍️ أقسام المتجر:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("buyprod_"))
async def start_buy_product(call: types.CallbackQuery, state: FSMContext):
    path = call.data.replace("buyprod_", "")
    node = get_node(path)
    price_usd = float(node.get("price", 0))
    discounts = load_discounts()
    user_discount = float(discounts.get(str(call.from_user.id), 0))
    final_price_usd = price_usd - (price_usd * (user_discount / 100))
    
    msg = (f"🛒 **المنتج:** {path.split('>')[-1]}\n💰 **السعر:** {final_price_usd:.2f} $\n\n"
           f"✍️ **الرجاء إرسال تفاصيل الطلب هنا (آيدي، رابط، أو معلومات الحساب):**")
           
    await state.update_data(buy_path=path, buy_price=final_price_usd)
    await state.set_state(CustomerStates.waiting_for_player_id)
    await call.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ إلغاء", callback_data="open_root")]]))

@dp.callback_query(F.data.startswith(("doneorder_", "failorder_")))
async def admin_process_order(call: types.CallbackQuery):
    action, uid, price = call.data.split("_")
    if action == "doneorder":
        await call.message.edit_text(call.message.text + "\n\n✅ **تم التنفيذ بنجاح**")
        await bot.send_message(int(uid), "🎉 تم تنفيذ طلبك بنجاح!")
    else:
        update_balance(uid, float(price))
        await call.message.edit_text(call.message.text + "\n\n❌ **تم الرفض وإرجاع الرصيد**")
        await bot.send_message(int(uid), f"❌ تم رفض طلبك، تم إرجاع {price}$ لرصيدك.")
    await call.answer()

@dp.callback_query()
async def callback_handler(call: types.CallbackQuery, state: FSMContext):
    if call.data.startswith("accept_"):
        uid = call.data.split("_")[1]
        await state.update_data(uid=uid)
        await state.set_state(OrderStates.waiting_for_amount)
        await call.message.edit_text(f"✅ تم القبول لـ {uid}. اكتب المبلغ:")
    elif call.data == "back_main":
        await call.message.edit_text("أهلاً بك في ALEX STORE! اختر ما تحتاجه:", reply_markup=get_main_menu())
    elif call.data == "my_account":
        bal = get_balance(call.from_user.id)
        await call.message.edit_text(f"👤 رصيدك الحالي: {bal:.2f} $", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="back_main")]]))
    elif call.data == "add_balance":
        await call.message.edit_text("💰 تواصل مع الإدارة لإتمام الشحن.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="back_main")]]))
    await call.answer()

if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
