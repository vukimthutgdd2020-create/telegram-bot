# -*- coding: utf-8 -*-
import asyncio
import logging
import sqlite3
from datetime import datetime
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

# =========================
# CẤU HÌNH
# =========================
BOT_TOKEN = "8649986734:AAEPEY3qI8OHOzAz7PUKnxDUmoNHxkXwBNc"
ADMIN_ID = 7078570432  # ID Telegram của bạn

DB_NAME = "shop_bot.db"

# Thông tin nhận tiền
BANK_NAME = "MB Bank"
BANK_BIN = "970422"
BANK_ACCOUNT = "07007003005"
ACCOUNT_NAME = "VU VAN CUONG"

# Sản phẩm mẫu
PRODUCTS = {
    "sp1": {
        "ten": "ChatGPT Plus 1 Tháng",
        "gia": 55000,
        "mo_ta": "Giao hàng số tự động sau khi duyệt.",
        "kho_hang": [
            "Mã giao hàng A-001",
            "Mã giao hàng A-002",
            "Mã giao hàng A-003",
        ],
    },
    "sp2": {
        "ten": "Gemini Pro AI 2TB 1 Năm",
        "gia": 155000,
        "mo_ta": "Giao hàng số tự động sau khi duyệt.",
        "kho_hang": [
            "Mã giao hàng B-001",
            "Mã giao hàng B-002",
        ],
    },
    "sp3": {
        "ten": "Adobe Creative Cloud",
        "gia": 195000,
        "mo_ta": "Giao hàng số tự động sau khi duyệt.",
        "kho_hang": [
            "Mã giao hàng C-001",
        ],
    },
}

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()


# =========================
# FSM
# =========================
class BuyFlow(StatesGroup):
    cho_gui_bill = State()


# =========================
# DATABASE
# =========================
def get_conn():
    return sqlite3.connect(DB_NAME)


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            price INTEGER NOT NULL,
            status TEXT NOT NULL,
            payment_proof_file_id TEXT,
            delivered_content TEXT,
            created_at TEXT,
            approved_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            content TEXT NOT NULL,
            is_used INTEGER DEFAULT 0
        )
    """)

    conn.commit()

    for product_id, info in PRODUCTS.items():
        for item in info["kho_hang"]:
            cur.execute(
                "SELECT id FROM stock_items WHERE product_id = ? AND content = ?",
                (product_id, item)
            )
            row = cur.fetchone()
            if not row:
                cur.execute(
                    "INSERT INTO stock_items(product_id, content, is_used) VALUES (?, ?, 0)",
                    (product_id, item)
                )

    conn.commit()
    conn.close()


def save_user(user_id: int, username: str, full_name: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR IGNORE INTO users(user_id, username, full_name, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, username, full_name, now_str())
    )
    conn.commit()
    conn.close()


def create_order(user_id: int, product_id: str, product_name: str, price: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO orders(user_id, product_id, product_name, price, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, product_id, product_name, price, "chờ_thanh_toán", now_str())
    )
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return order_id


def get_order(order_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    row = cur.fetchone()
    conn.close()
    return row


def update_order_status(order_id: int, status: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()


def save_payment_proof(order_id: int, file_id: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE orders SET payment_proof_file_id = ?, status = ? WHERE id = ?",
        (file_id, "chờ_duyệt", order_id)
    )
    conn.commit()
    conn.close()


def get_unused_stock(product_id: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, content FROM stock_items WHERE product_id = ? AND is_used = 0 LIMIT 1",
        (product_id,)
    )
    row = cur.fetchone()
    conn.close()
    return row


def mark_stock_used(stock_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE stock_items SET is_used = 1 WHERE id = ?", (stock_id,))
    conn.commit()
    conn.close()


def save_delivery(order_id: int, delivered_content: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE orders
        SET delivered_content = ?, status = ?, approved_at = ?
        WHERE id = ?
        """,
        (delivered_content, "đã_giao", now_str(), order_id)
    )
    conn.commit()
    conn.close()


def get_recent_orders(limit=10):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, product_name, price, status, created_at
        FROM orders
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_stock_summary():
    conn = get_conn()
    cur = conn.cursor()
    result = []

    for product_id, info in PRODUCTS.items():
        cur.execute(
            "SELECT COUNT(*) FROM stock_items WHERE product_id = ? AND is_used = 0",
            (product_id,)
        )
        remaining = cur.fetchone()[0]
        result.append((product_id, info["ten"], remaining))

    conn.close()
    return result


# =========================
# TIỆN ÍCH
# =========================
def format_currency(number: int):
    return f"{number:,}".replace(",", ".") + "đ"


def tao_noi_dung_ck(order_id: int):
    return f"DH{order_id}"


def tao_url_qr(order_id: int, amount: int):
    noi_dung = tao_noi_dung_ck(order_id)
    account_name_encoded = quote(ACCOUNT_NAME)
    return (
        f"https://img.vietqr.io/image/"
        f"{BANK_BIN}-{BANK_ACCOUNT}-compact2.png"
        f"?amount={amount}&addInfo={noi_dung}&accountName={account_name_encoded}"
    )


def is_admin(user_id: int):
    return user_id == ADMIN_ID


# =========================
# BÀN PHÍM
# =========================
def kb_main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛍 Xem sản phẩm", callback_data="xem_san_pham")],
            [InlineKeyboardButton(text="📖 Hướng dẫn mua", callback_data="huong_dan_mua")],
        ]
    )


def kb_products():
    rows = []
    for product_id, info in PRODUCTS.items():
        rows.append([
            InlineKeyboardButton(
                text=f"{info['ten']} - {format_currency(info['gia'])}",
                callback_data=f"product_{product_id}"
            )
        ])
    rows.append([InlineKeyboardButton(text="⬅️ Về menu", callback_data="ve_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_buy_product(product_id: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Mua ngay", callback_data=f"buy_{product_id}")],
            [InlineKeyboardButton(text="⬅️ Về danh sách", callback_data="xem_san_pham")],
        ]
    )


def kb_admin_order(order_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Duyệt đơn", callback_data=f"admin_duyet_{order_id}"),
                InlineKeyboardButton(text="❌ Từ chối", callback_data=f"admin_tuchoi_{order_id}"),
            ]
        ]
    )


# =========================
# HANDLERS
# =========================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
    save_user(
        user_id=user.id,
        username=user.username or "",
        full_name=user.full_name
    )

    text = (
        f"Xin chào <b>{user.full_name}</b>!\n\n"
        "Đây là bot bán hàng tự động.\n"
        "Bạn có thể xem sản phẩm, tạo đơn hàng, quét QR thanh toán và gửi bill để chờ duyệt.\n\n"
        "Vui lòng chọn mục bên dưới:"
    )
    await message.answer(text, reply_markup=kb_main_menu())


@dp.message(Command("huy"))
async def cmd_huy(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Đã hủy thao tác hiện tại.")
    await message.answer("Menu chính:", reply_markup=kb_main_menu())


@dp.message(Command("orders"))
async def cmd_orders(message: Message):
    if not is_admin(message.from_user.id):
        return

    rows = get_recent_orders(10)
    if not rows:
        await message.answer("Chưa có đơn hàng nào.")
        return

    text = "<b>10 đơn gần nhất</b>\n\n"
    for row in rows:
        text += (
            f"#{row[0]} | {row[1]} | {format_currency(row[2])}\n"
            f"Trạng thái: {row[3]} | {row[4]}\n\n"
        )

    await message.answer(text)


@dp.message(Command("stock"))
async def cmd_stock(message: Message):
    if not is_admin(message.from_user.id):
        return

    rows = get_stock_summary()
    text = "<b>Tồn kho hiện tại</b>\n\n"
    for product_id, ten, remaining in rows:
        text += f"{product_id} | {ten}\nCòn lại: <b>{remaining}</b>\n\n"

    await message.answer(text)


@dp.callback_query(F.data == "ve_menu")
async def cb_ve_menu(callback: CallbackQuery):
    await callback.message.edit_text("Menu chính:", reply_markup=kb_main_menu())
    await callback.answer()


@dp.callback_query(F.data == "huong_dan_mua")
async def cb_huong_dan_mua(callback: CallbackQuery):
    text = (
        "<b>Hướng dẫn mua hàng</b>\n\n"
        "1. Bấm <b>Xem sản phẩm</b>\n"
        "2. Chọn gói cần mua\n"
        "3. Bấm <b>Mua ngay</b>\n"
        "4. Quét QR hoặc chuyển khoản đúng nội dung\n"
        "5. Gửi ảnh bill cho bot\n"
        "6. Admin duyệt và bot tự động giao hàng\n\n"
        "Lưu ý:\n"
        "- Chuyển khoản đúng nội dung để dễ đối soát\n"
        "- Nếu cần hủy thao tác, gõ <code>/huy</code>"
    )
    await callback.message.edit_text(text, reply_markup=kb_main_menu())
    await callback.answer()


@dp.callback_query(F.data == "xem_san_pham")
async def cb_xem_san_pham(callback: CallbackQuery):
    await callback.message.edit_text(
        "<b>Danh sách sản phẩm</b>\nChọn sản phẩm bạn muốn mua:",
        reply_markup=kb_products()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("product_"))
async def cb_xem_chi_tiet_sp(callback: CallbackQuery):
    product_id = callback.data.replace("product_", "")
    if product_id not in PRODUCTS:
        await callback.answer("Sản phẩm không tồn tại.", show_alert=True)
        return

    info = PRODUCTS[product_id]
    text = (
        f"<b>{info['ten']}</b>\n"
        f"Giá: <b>{format_currency(info['gia'])}</b>\n"
        f"Mô tả: {info['mo_ta']}\n"
    )
    await callback.message.edit_text(text, reply_markup=kb_buy_product(product_id))
    await callback.answer()


@dp.callback_query(F.data.startswith("buy_"))
async def cb_mua_hang(callback: CallbackQuery, state: FSMContext):
    product_id = callback.data.replace("buy_", "")
    if product_id not in PRODUCTS:
        await callback.answer("Sản phẩm không tồn tại.", show_alert=True)
        return

    info = PRODUCTS[product_id]

    order_id = create_order(
        user_id=callback.from_user.id,
        product_id=product_id,
        product_name=info["ten"],
        price=info["gia"]
    )

    await state.set_state(BuyFlow.cho_gui_bill)
    await state.update_data(order_id=order_id)

    noi_dung_ck = tao_noi_dung_ck(order_id)
    qr_url = tao_url_qr(order_id, info["gia"])

    text = (
        f"<b>Đã tạo đơn hàng #{order_id}</b>\n\n"
        f"Sản phẩm: <b>{info['ten']}</b>\n"
        f"Giá: <b>{format_currency(info['gia'])}</b>\n\n"
        f"<b>Thông tin thanh toán</b>\n"
        f"- Ngân hàng: {BANK_NAME}\n"
        f"- Số tài khoản: <code>{BANK_ACCOUNT}</code>\n"
        f"- Chủ tài khoản: <b>{ACCOUNT_NAME}</b>\n"
        f"- Số tiền: <b>{format_currency(info['gia'])}</b>\n"
        f"- Nội dung CK: <code>{noi_dung_ck}</code>\n\n"
        "Hãy quét mã QR bên dưới hoặc chuyển khoản thủ công.\n"
        "Sau khi thanh toán xong, vui lòng gửi <b>ảnh bill</b> ngay trong khung chat này."
    )

    try:
        await callback.message.delete()
    except Exception:
        pass

    try:
        await bot.send_photo(
            chat_id=callback.from_user.id,
            photo=qr_url,
            caption=text
        )
    except Exception:
        await bot.send_message(chat_id=callback.from_user.id, text=text)

    await callback.answer("Đã tạo đơn hàng.")


@dp.message(BuyFlow.cho_gui_bill, F.photo)
async def xu_ly_gui_bill(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")

    if not order_id:
        await message.answer("Không tìm thấy đơn hàng. Vui lòng tạo đơn mới.")
        await state.clear()
        await message.answer("Menu chính:", reply_markup=kb_main_menu())
        return

    largest_photo = message.photo[-1]
    file_id = largest_photo.file_id

    save_payment_proof(order_id, file_id)

    order = get_order(order_id)
    user = message.from_user

    text_admin = (
        f"<b>Đơn hàng mới cần duyệt</b>\n\n"
        f"Mã đơn: <b>#{order_id}</b>\n"
        f"Khách: {user.full_name}\n"
        f"User ID: <code>{user.id}</code>\n"
        f"Username: @{user.username if user.username else 'không có'}\n"
        f"Sản phẩm: <b>{order[3]}</b>\n"
        f"Giá: <b>{format_currency(order[4])}</b>\n"
        f"Trạng thái: <b>Chờ duyệt</b>"
    )

    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=file_id,
        caption=text_admin,
        reply_markup=kb_admin_order(order_id)
    )

    await message.answer(
        f"Bot đã nhận bill cho đơn <b>#{order_id}</b>.\n"
        "Vui lòng chờ admin xác nhận.",
        reply_markup=kb_main_menu()
    )
    await state.clear()


@dp.message(BuyFlow.cho_gui_bill)
async def nhac_gui_anh_bill(message: Message):
    await message.answer(
        "Vui lòng gửi <b>ảnh bill thanh toán</b> để xác nhận đơn hàng.",
        reply_markup=kb_main_menu()
    )


@dp.callback_query(F.data.startswith("admin_duyet_"))
async def admin_duyet(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Bạn không có quyền.", show_alert=True)
        return

    order_id = int(callback.data.replace("admin_duyet_", ""))
    order = get_order(order_id)

    if not order:
        await callback.answer("Không tìm thấy đơn hàng.", show_alert=True)
        return

    if order[5] == "đã_giao":
        await callback.answer("Đơn này đã giao rồi.")
        return

    stock = get_unused_stock(order[2])
    if not stock:
        update_order_status(order_id, "hết_hàng")
        await bot.send_message(
            chat_id=order[1],
            text=(
                f"Đơn <b>#{order_id}</b> tạm thời chưa thể giao vì sản phẩm đang hết hàng.\n"
                "Vui lòng liên hệ admin để được hỗ trợ.\n\n"
                "Bạn có thể quay lại menu để tạo đơn mới."
            ),
            reply_markup=kb_main_menu()
        )
        try:
            await callback.message.edit_caption(
                caption=(callback.message.caption or "") + "\n\n<b>Kết quả:</b> Hết hàng"
            )
        except Exception:
            pass

        await callback.answer("Sản phẩm đã hết hàng.")
        return

    stock_id, stock_content = stock
    mark_stock_used(stock_id)
    save_delivery(order_id, stock_content)

    text_user = (
        f"<b>Đơn hàng #{order_id} đã được duyệt</b>\n\n"
        f"Sản phẩm: <b>{order[3]}</b>\n"
        f"Nội dung giao hàng:\n<code>{stock_content}</code>\n\n"
        "Cảm ơn bạn đã mua hàng!\n\n"
        "Bạn có thể tiếp tục mua hàng ở menu bên dưới."
    )

    await bot.send_message(
        chat_id=order[1],
        text=text_user,
        reply_markup=kb_main_menu()
    )

    try:
        await callback.message.edit_caption(
            caption=(callback.message.caption or "") + "\n\n<b>Kết quả:</b> Đã duyệt và giao hàng"
        )
    except Exception:
        pass

    await callback.answer("Đã duyệt đơn.")


@dp.callback_query(F.data.startswith("admin_tuchoi_"))
async def admin_tu_choi(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Bạn không có quyền.", show_alert=True)
        return

    order_id = int(callback.data.replace("admin_tuchoi_", ""))
    order = get_order(order_id)

    if not order:
        await callback.answer("Không tìm thấy đơn hàng.", show_alert=True)
        return

    update_order_status(order_id, "từ_chối")

    await bot.send_message(
        chat_id=order[1],
        text=(
            f"Đơn <b>#{order_id}</b> đã bị từ chối.\n"
            "Nếu bạn đã thanh toán, vui lòng liên hệ admin để được hỗ trợ.\n\n"
            "Bạn có thể quay lại menu để tạo đơn mới."
        ),
        reply_markup=kb_main_menu()
    )

    try:
        await callback.message.edit_caption(
            caption=(callback.message.caption or "") + "\n\n<b>Kết quả:</b> Đã từ chối"
        )
    except Exception:
        pass

    await callback.answer("Đã từ chối đơn.")


async def main():
    init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
