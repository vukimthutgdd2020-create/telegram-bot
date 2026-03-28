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
BANK_ACCOUNT = "346641789567"
ACCOUNT_NAME = "VU VAN CUONG"

SUPPORT_USERNAME = "@tai_khoan_xin"
DB_NAME = "shop_bot.db"

PRODUCTS = {
    "sp1": {"ten": "CapCut Pro 35d_BHF", "gia": 45000, "sl": 5},
    "sp2": {"ten": "CapCut Pro 14 Ngày_BHF", "gia": 25000, "sl": 7},
    "sp3": {"ten": "CapCut Pro 1 Năm_BHF", "gia": 450000, "sl": 5},
    "sp4": {"ten": "ChatGPT Plus 1 Tháng", "gia": 99000, "sl": 9},
    "sp5": {"ten": "Gemini 2TB AI PRO 12 tháng", "gia": 199000, "sl": 2},
    "sp6": {"ten": "Adobe Creative Cloud 3 Tháng", "gia": 159000, "sl": 5},
    "sp7": {"ten": "Canva Edu 1 Năm", "gia": 149000, "sl": 5},
    "sp8": {"ten": "Canva Pro 1 Năm", "gia": 289000, "sl": 5},
    "sp9": {"ten": "Youtube Premium 1 Tháng", "gia": 55000, "sl": 5},
    "sp10": {"ten": "Youtube 3 Tháng", "gia": 159000, "sl": 5},
    "sp11": {"ten": "Acc Shoppe Ngâm 5 Tháng Voucher 80k - 100k", "gia": 29000, "sl": 5},
    "sp12": {"ten": "Đặt Đơn Shopee Giảm 100k", "gia": 59000, "sl": 5},
}

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product TEXT,
            price INTEGER,
            status TEXT,
            proof TEXT,
            delivery TEXT
        )
    """)
    conn.commit()
    conn.close()


def tao_qr(order_id, amount):
    noi_dung = f"DH{order_id}"
    return (
        f"https://img.vietqr.io/image/"
        f"{BANK_BIN}-{BANK_ACCOUNT}-compact2.png"
        f"?amount={amount}&addInfo={quote(noi_dung)}&accountName={quote(ACCOUNT_NAME)}"
    )


def menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛍 Xem sản phẩm", callback_data="sp")],
            [InlineKeyboardButton(text="☎️ Hỗ trợ", callback_data="contact")],
        ]
    )


def list_sp():
    rows = []
    i = 1
    for k, v in PRODUCTS.items():
        rows.append([
            InlineKeyboardButton(
                text=f"[{i}] {v['ten']} | {v['gia'] // 1000}k",
                callback_data=f"buy_{k}"
            )
        ])
        i += 1

    rows.append([InlineKeyboardButton(text="🏠 Menu", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.message(Command("start"))
async def start(m: Message):
    text = (
        "Chào bạn 👋\n\n"
        "Chọn mục bên dưới để mua hàng.\n"
        f"Nếu cần hỗ trợ, nhắn {SUPPORT_USERNAME}"
    )
    await m.answer(text, reply_markup=menu())


@dp.callback_query(F.data == "menu")
async def back(c: CallbackQuery):
    await c.message.edit_text("🏠 Menu chính:", reply_markup=menu())
    await c.answer()


@dp.callback_query(F.data == "sp")
async def sp(c: CallbackQuery):
    await c.message.edit_text("🛍 Danh sách sản phẩm:", reply_markup=list_sp())
    await c.answer()


@dp.callback_query(F.data == "contact")
async def contact(c: CallbackQuery):
    await c.message.edit_text(
        f"☎️ Hỗ trợ: {SUPPORT_USERNAME}",
        reply_markup=menu()
    )
    await c.answer()


@dp.callback_query(F.data.startswith("buy_"))
async def buy(c: CallbackQuery, state: FSMContext):
    pid = c.data.split("_", 1)[1]
    p = PRODUCTS[pid]

    conn = db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO orders(user_id, product, price, status) VALUES(?,?,?,?)",
        (c.from_user.id, p["ten"], p["gia"], "pay")
    )
    oid = cur.lastrowid
    conn.commit()
    conn.close()

    await state.set_state(BuyFlow.cho_bill)
    await state.update_data(oid=oid)

    qr = tao_qr(oid, p["gia"])

    try:
        await c.message.delete()
    except Exception:
        pass

    caption = (
        f"<b>Đơn #{oid}</b>\n"
        f"📦 Sản phẩm: <b>{html.escape(p['ten'])}</b>\n"
        f"💰 Số tiền: <b>{p['gia']:,}đ</b>\n\n"
        f"🏦 Ngân hàng: <b>{BANK_NAME}</b>\n"
        f"👤 Chủ tài khoản: <b>{html.escape(ACCOUNT_NAME)}</b>\n"
        f"🔢 Số tài khoản: <b>{BANK_ACCOUNT}</b>\n"
        f"📌 Nội dung chuyển khoản: <code>DH{oid}</code>\n\n"
        "Chuyển khoản xong vui lòng gửi bill vào khung chat này."
    )

    await bot.send_photo(c.from_user.id, qr, caption=caption)
    await c.answer()


@dp.message(BuyFlow.cho_bill, F.photo)
async def bill(m: Message, state: FSMContext):
    data = await state.get_data()
    oid = data["oid"]
    file_id = m.photo[-1].file_id

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE orders SET proof=?, status='check' WHERE id=?",
        (file_id, oid)
    )
    conn.commit()

    cur.execute("SELECT product, price FROM orders WHERE id=?", (oid,))
    row = cur.fetchone()
    conn.close()

    if not row:
        await m.answer("Không tìm thấy đơn hàng.", reply_markup=menu())
        await state.clear()
        return

    product_name, price = row

    user = m.from_user
    username = f"@{user.username}" if user.username else "Không có"
    full_name = html.escape(user.full_name)

    caption_admin = (
        f"🧾 <b>Đơn #{oid}</b>\n"
        f"📦 Sản phẩm: <b>{html.escape(product_name)}</b>\n"
        f"💰 Giá tiền: <b>{price:,}đ</b>\n\n"
        f"👤 Tên: <b>{full_name}</b>\n"
        f"🔗 Username: <b>{html.escape(username)}</b>\n"
        f"🆔 ID: <code>{user.id}</code>\n\n"
        "Vui lòng chọn thao tác:"
    )

    await bot.send_photo(
        ADMIN_ID,
        file_id,
        caption=caption_admin,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="DUYỆT", callback_data=f"ok_{oid}")],
                [InlineKeyboardButton(text="HUỶ", callback_data=f"no_{oid}")]
            ]
        )
    )

    await m.answer("✅ Đã gửi bill, vui lòng chờ admin duyệt.", reply_markup=menu())
    await state.clear()


@dp.message(BuyFlow.cho_bill)
async def nhac_gui_bill(m: Message):
    await m.answer("Vui lòng gửi <b>ảnh bill</b> để xác nhận thanh toán.")


@dp.callback_query(F.data.startswith("ok_"))
async def ok(c: CallbackQuery):
    oid = int(c.data.split("_")[1])

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT user_id, product, price FROM orders WHERE id=?", (oid,))
    row = cur.fetchone()

    if not row:
        conn.close()
        await c.answer("Không tìm thấy đơn.", show_alert=True)
        return

    uid, product_name, price = row

    cur.execute("UPDATE orders SET status='approved' WHERE id=?", (oid,))
    conn.commit()
    conn.close()

    await c.message.answer(
        f"✅ Đã duyệt đơn #{oid}\n"
        f"📦 Sản phẩm: <b>{html.escape(product_name)}</b>\n"
        f"💰 Giá tiền: <b>{price:,}đ</b>\n\n"
        f"Để giao đúng đơn này, hãy dùng lệnh:\n"
        f"<code>/gui {oid}</code>"
    )

    await bot.send_message(
        uid,
        f"✅ Đơn #{oid} đã được duyệt\n"
        f"📦 Sản phẩm: <b>{html.escape(product_name)}</b>\n"
        f"💰 Giá tiền: <b>{price:,}đ</b>\n\n"
        "Admin đang chuẩn bị giao hàng cho bạn."
    )

    await c.answer("Đã duyệt đơn.")


@dp.message(Command("gui"))
async def chon_don_gui(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        await m.answer("Bạn không có quyền dùng lệnh này.")
        return

    parts = m.text.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        await m.answer("Cách dùng đúng: <code>/gui 12</code>")
        return

    oid = int(parts[1])

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT user_id, product, price, status FROM orders WHERE id=?", (oid,))
    row = cur.fetchone()
    conn.close()

    if not row:
        await m.answer("Không tìm thấy đơn hàng.")
        return

    uid, product_name, price, status = row

    if status not in ("approved", "done"):
        await m.answer(
            "Đơn này chưa ở trạng thái được giao.\n"
            "Hãy bấm DUYỆT trước rồi mới dùng /gui."
        )
        return

    await state.set_state(AdminFlow.nhap_noi_dung)
    await state.update_data(oid=oid)

    await m.answer(
        f"📌 Đã chọn đơn #{oid}\n"
        f"📦 Sản phẩm: <b>{html.escape(product_name)}</b>\n"
        f"💰 Giá tiền: <b>{price:,}đ</b>\n\n"
        "Bây giờ bạn nhập nội dung giao hàng dạng text."
    )


@dp.message(AdminFlow.nhap_noi_dung)
async def deliver(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return

    data = await state.get_data()
    oid = data.get("oid")

    if not oid:
        await m.answer("Chưa chọn đơn để giao. Dùng <code>/gui mã_đơn</code> trước.")
        await state.clear()
        return

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT user_id, product FROM orders WHERE id=?", (oid,))
    row = cur.fetchone()

    if not row:
        conn.close()
        await m.answer("Không tìm thấy đơn hàng.")
        await state.clear()
        return

    uid, product_name = row

    raw_text = m.text.strip() if m.text else ""
    if not raw_text:
        await m.answer("Bạn hãy nhập nội dung giao hàng dạng text.")
        conn.close()
        return

    safe_text = html.escape(raw_text)
    safe_product = html.escape(product_name)

    cur.execute(
        "UPDATE orders SET delivery=?, status='done' WHERE id=?",
        (raw_text, oid)
    )
    conn.commit()
    conn.close()

    await bot.send_message(
        uid,
        f"🎉 <b>Đã giao hàng thành công</b>\n\n"
        f"🧾 Mã đơn: <b>#{oid}</b>\n"
        f"📦 Sản phẩm: <b>{safe_product}</b>\n\n"
        f"📌 Nội dung nhận hàng:\n<code>{safe_text}</code>\n\n"
        "Nhấn giữ vào phần trong khung để sao chép nhanh."
    )

    await m.answer(
        f"✅ Đã giao đơn #{oid}\n"
        f"📦 Sản phẩm: <b>{safe_product}</b>"
    )

    await state.clear()


@dp.callback_query(F.data.startswith("no_"))
async def no(c: CallbackQuery):
    oid = int(c.data.split("_")[1])

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT user_id, product, price FROM orders WHERE id=?", (oid,))
    row = cur.fetchone()

    if not row:
        conn.close()
        await c.answer("Không tìm thấy đơn.", show_alert=True)
        return

    uid, product_name, price = row

    cur.execute("UPDATE orders SET status='reject' WHERE id=?", (oid,))
    conn.commit()
    conn.close()

    await bot.send_message(
        uid,
        f"❌ Đơn #{oid} đã bị từ chối\n"
        f"📦 Sản phẩm: <b>{html.escape(product_name)}</b>\n"
        f"💰 Giá tiền: <b>{price:,}đ</b>\n\n"
        f"Nếu cần hỗ trợ, vui lòng liên hệ {SUPPORT_USERNAME}"
    )

    await c.answer("Đã huỷ đơn.")


async def main():
    init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
