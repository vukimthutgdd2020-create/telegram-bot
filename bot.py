import asyncio
import logging
import sqlite3
import html
from urllib.parse import quote

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

BOT_TOKEN = "8649986734:AAEPEY3qI8OHOzAz7PUKnxDUmoNHxkXwBNc"
ADMIN_ID = 7078570432

BANK_NAME = "MB Bank"
BANK_BIN = "970422"
BANK_ACCOUNT = "07007003005"
ACCOUNT_NAME = "VU VAN CUONG"

SUPPORT_USERNAME = "@tai_khoan_xin"
DB_NAME = "shop_bot.db"

PRODUCTS = {
    "sp1": {"ten": "CapCut Pro 35d_BHF", "gia": 35000},
    "sp2": {"ten": "CapCut Pro 14 Ngày_BHF", "gia": 25000},
    "sp3": {"ten": "CapCut Pro 1 Năm_BHF", "gia": 450000},
    "sp4": {"ten": "ChatGPT Plus 1 Tháng", "gia": 79000},
    "sp5": {"ten": "Gemini 2TB AI PRO 12 tháng", "gia": 199000},
    "sp6": {"ten": "Adobe Creative Cloud 3 Tháng", "gia": 155000},
    "sp7": {"ten": "Canva Edu 1 Năm", "gia": 149000},
    "sp8": {"ten": "Canva Pro 1 Năm", "gia": 285000},
    "sp9": {"ten": "Youtube Premium 1 Tháng", "gia": 55000},
    "sp10": {"ten": "Youtube 3 Tháng", "gia": 150000},
}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

class BuyFlow(StatesGroup):
    cho_bill = State()

class AdminFlow(StatesGroup):
    nhap_noi_dung = State()

def db():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = db()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product TEXT,
        price INTEGER,
        status TEXT,
        proof TEXT,
        delivery TEXT
    )""")
    conn.commit()
    conn.close()

def tao_qr(order_id, amount):
    noi_dung = f"DH{order_id}"
    return f"https://img.vietqr.io/image/{BANK_BIN}-{BANK_ACCOUNT}-compact2.png?amount={amount}&addInfo={quote(noi_dung)}&accountName={quote(ACCOUNT_NAME)}"

def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Xem sản phẩm", callback_data="sp")],
        [InlineKeyboardButton(text="☎️ Hỗ trợ", callback_data="contact")]
    ])

def list_sp():
    rows = []
    i = 1
    for k,v in PRODUCTS.items():
        rows.append([InlineKeyboardButton(text=f"[{i}] {v['ten']} | {v['gia']//1000}k", callback_data=f"buy_{k}")])
        i+=1
    rows.append([InlineKeyboardButton(text="🏠 Menu", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@dp.message(Command("start"))
async def start(m:Message):
    await m.answer("Chào bạn 👋", reply_markup=menu())

@dp.callback_query(F.data=="menu")
async def back(c:CallbackQuery):
    await c.message.edit_text("Menu:", reply_markup=menu())

@dp.callback_query(F.data=="sp")
async def sp(c:CallbackQuery):
    await c.message.edit_text("Danh sách:", reply_markup=list_sp())

@dp.callback_query(F.data.startswith("buy_"))
async def buy(c:CallbackQuery, state:FSMContext):
    pid = c.data.split("_")[1]
    p = PRODUCTS[pid]

    conn=db(); cur=conn.cursor()
    cur.execute("INSERT INTO orders(user_id,product,price,status) VALUES(?,?,?,?)",(c.from_user.id,p["ten"],p["gia"],"pay"))
    oid=cur.lastrowid
    conn.commit(); conn.close()

    await state.set_state(BuyFlow.cho_bill)
    await state.update_data(oid=oid)

    qr = tao_qr(oid,p["gia"])

    await c.message.delete()
    await bot.send_photo(c.from_user.id, qr, caption=f"""
<b>Đơn #{oid}</b>
Sản phẩm: {p['ten']}
Số tiền: {p['gia']:,}đ

Chuyển khoản xong gửi bill.
""")

@dp.message(BuyFlow.cho_bill, F.photo)
async def bill(m:Message, state:FSMContext):
    data = await state.get_data()
    oid = data["oid"]
    file_id = m.photo[-1].file_id

    conn=db(); cur=conn.cursor()
    cur.execute("UPDATE orders SET proof=?,status='check' WHERE id=?",(file_id,oid))
    conn.commit(); conn.close()

    await bot.send_photo(ADMIN_ID,file_id,caption=f"Đơn #{oid}",reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="DUYỆT",callback_data=f"ok_{oid}")],
        [InlineKeyboardButton(text="HUỶ",callback_data=f"no_{oid}")]
    ]))

    await m.answer("Đã gửi bill chờ duyệt.", reply_markup=menu())
    await state.clear()

@dp.callback_query(F.data.startswith("ok_"))
async def ok(c: CallbackQuery, state: FSMContext):
    oid = int(c.data.split("_")[1])

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT user_id, product FROM orders WHERE id=?", (oid,))
    uid, product_name = cur.fetchone()

    cur.execute("UPDATE orders SET status='approved' WHERE id=?", (oid,))
    conn.commit()
    conn.close()

    await state.set_state(AdminFlow.nhap_noi_dung)
    await state.update_data(oid=oid)

    await c.message.answer(
        f"✅ Đã duyệt đơn #{oid}\n"
        f"📦 Sản phẩm: <b>{html.escape(product_name)}</b>\n\n"
        "Nhập nội dung giao hàng:"
    )

    await bot.send_message(
        uid,
        f"✅ Đơn #{oid} đã được duyệt\n"
        f"📦 Sản phẩm: <b>{html.escape(product_name)}</b>\n"
        "Admin đang chuẩn bị giao."
    )

@dp.message(AdminFlow.nhap_noi_dung)
async def deliver(m: Message, state: FSMContext):
    data = await state.get_data()
    oid = data["oid"]

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT user_id, product FROM orders WHERE id=?", (oid,))
    uid, product_name = cur.fetchone()

    text = html.escape(m.text.strip())

    cur.execute("UPDATE orders SET delivery=?,status='done' WHERE id=?", (text, oid))
    conn.commit()
    conn.close()

    await bot.send_message(
        uid,
        f"🎉 Đã giao hàng\n\n"
        f"📦 Sản phẩm: <b>{html.escape(product_name)}</b>\n"
        f"📌 Nội dung:\n<code>{text}</code>\n\n"
        "Nhấn giữ để copy."
    )

    await m.answer("Đã giao")
    await state.clear()

@dp.callback_query(F.data.startswith("no_"))
async def no(c:CallbackQuery):
    oid=int(c.data.split("_")[1])
    conn=db(); cur=conn.cursor()
    cur.execute("SELECT user_id FROM orders WHERE id=?", (oid,))
    uid=cur.fetchone()[0]
    cur.execute("UPDATE orders SET status='reject' WHERE id=?", (oid,))
    conn.commit(); conn.close()

    await bot.send_message(uid,f"Đơn #{oid} bị từ chối")
    await c.answer("Đã huỷ")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())
