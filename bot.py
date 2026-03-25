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
    BotCommand,
    Message,
)

# =========================
# CẤU HÌNH
# =========================
BOT_TOKEN = "8649986734:AAEPEY3qI8OHOzAz7PUKnxDUmoNHxkXwBNc"
ADMIN_ID = 7078570432  # đổi thành Telegram ID của bạn

DB_NAME = "shop_bot.db"

SUPPORT_USERNAME = "@tai_khoan_xin"

# Thông tin nhận tiền
BANK_NAME = "MB Bank"
BANK_BIN = "970422"
BANK_ACCOUNT = "07007003005"
ACCOUNT_NAME = "VU VAN CUONG"

# Danh sách sản phẩm
PRODUCTS = {
    "sp1": {
        "ten": "ChatGPT Plus 1 Tháng",
        "gia": 55000,
        "mo_ta": "Tài khoản bản quyền, giao thủ công sau khi admin xác nhận.",
    },
    "sp2": {
        "ten": "Gemini AI Pro 2TB 1 Năm",
        "gia": 195000,
        "mo_ta": "Tài khoản bản quyền, giao thủ công sau khi admin xác nhận.",
    },
    "sp3": {
        "ten": "Adobe Creative Cloud 3 Tháng",
        "gia": 155000,
        "mo_ta": "Tài khoản bản quyền, giao thủ công sau khi admin xác nhận.",
    },
    "sp4": {
        "ten": "Canva Pro 1 Năm",
        "gia": 285000,
        "mo_ta": "Tài khoản bản quyền, giao thủ công sau khi admin xác nhận.",
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


class AdminFlow(StatesGroup):
    cho_nhap_noi_dung_giao = State()


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
        (user_id, product_id, product_name, price, "cho_thanh_toan", now_str())
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
        """
        UPDATE orders
        SET payment_proof_file_id = ?, status = ?
        WHERE id = ?
        """,
        (file_id, "cho_duyet", order_id)
    )
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
        (delivered_content, "da_giao", now_str(), order_id)
    )
    conn.commit()
    conn.close()


def reject_order(order_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE orders
        SET status = ?, approved_at = ?
        WHERE id = ?
        """,
        ("tu_choi", now_str(), order_id)
    )
    conn.commit()
    conn.close()


def get_user_orders(user_id: int, limit: int = 10):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, product_name, price, status, created_at
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (user_id, limit)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


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
    add_info_encoded = quote(noi_dung)
    return (
        f"https://img.vietqr.io/image/"
        f"{BANK_BIN}-{BANK_ACCOUNT}-compact2.png"
        f"?amount={amount}&addInfo={add_info_encoded}&accountName={account_name_encoded}"
    )


def is_admin(user_id: int):
    return user_id == ADMIN_ID


def text_status(status: str):
    mapping = {
        "cho_thanh_toan": "Chờ thanh toán",
        "cho_duyet": "Chờ duyệt",
        "da_duyet_cho_nhap": "Đã duyệt, chờ admin nhập hàng",
        "da_giao": "Đã giao",
        "tu_choi": "Từ chối",
    }
    return mapping.get(status, status)


# =========================
# BÀN PHÍM
# =========================
def kb_main_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛍 Xem sản phẩm", callback_data="xem_san_pham")],
            [InlineKeyboardButton(text="📦 Đơn hàng của tôi", callback_data="my_orders")],
            [InlineKeyboardButton(text="📖 Hướng dẫn mua", callback_data="huong_dan_mua")],
            [InlineKeyboardButton(text="☎️ Hỗ trợ / Liên hệ", callback_data="contact")],
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
    rows.append([InlineKeyboardButton(text="🏠 Về menu", callback_data="ve_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_buy_product(product_id: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Mua ngay", callback_data=f"buy_{product_id}")],
            [InlineKeyboardButton(text="🔙 Về danh sách", callback_data="xem_san_pham")],
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
# COMMAND MENU TELEGRAM
# =========================
async def set_bot_commands():
    commands = [
        BotCommand(command="start", description="Danh sách sản phẩm"),
        BotCommand(command="myorders", description="Đơn hàng của tôi"),
        BotCommand(command="contact", description="Hỗ trợ / Liên hệ"),
        BotCommand(command="help", description="Hướng dẫn sử dụng"),
    ]
    await bot.set_my_commands(commands)


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
        "Đây là bot bán hàng.\n"
        "Bạn có thể xem sản phẩm, tạo đơn, thanh toán, gửi bill và chờ admin giao hàng thủ công.\n\n"
        "Chọn mục bên dưới:"
    )
    await message.answer(text, reply_markup=kb_main_menu())


@dp.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "<b>Hướng dẫn sử dụng</b>\n\n"
        "1. Bấm <b>Xem sản phẩm</b>\n"
        "2. Chọn gói cần mua\n"
        "3. Bấm <b>Mua ngay</b>\n"
        "4. Chuyển khoản theo QR và nội dung chuyển khoản\n"
        "5. Gửi ảnh bill cho bot\n"
        "6. Chờ admin duyệt\n"
        "7. Sau khi admin nhập nội dung giao hàng, bot sẽ gửi cho bạn\n\n"
        f"Nếu cần hỗ trợ, nhắn {SUPPORT_USERNAME}"
    )
    await message.answer(text, reply_markup=kb_main_menu())


@dp.message(Command("contact"))
async def cmd_contact(message: Message):
    await message.answer(
        f"☎️ Hỗ trợ / Liên hệ: {SUPPORT_USERNAME}",
        reply_markup=kb_main_menu()
    )


@dp.message(Command("myorders"))
async def cmd_myorders(message: Message):
    rows = get_user_orders(message.from_user.id)
    if not rows:
        await message.answer("Bạn chưa có đơn hàng nào.", reply_markup=kb_main_menu())
        return

    text = "<b>Đơn hàng của bạn:</b>\n\n"
    for order_id, product_name, price, status, created_at in rows:
        text += (
            f"• <b>#{order_id}</b> - {product_name}\n"
            f"  Giá: {format_currency(price)}\n"
            f"  Trạng thái: <b>{text_status(status)}</b>\n"
            f"  Thời gian: {created_at}\n\n"
        )

    await message.answer(text, reply_markup=kb_main_menu())


@dp.callback_query(F.data == "ve_menu")
async def cb_ve_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "🏠 Menu chính:",
        reply_markup=kb_main_menu()
    )
    await callback.answer()


@dp.callback_query(F.data == "xem_san_pham")
async def cb_xem_san_pham(callback: CallbackQuery):
    await callback.message.edit_text(
        "🛍 Danh sách sản phẩm:",
        reply_markup=kb_products()
    )
    await callback.answer()


@dp.callback_query(F.data == "my_orders")
async def cb_my_orders(callback: CallbackQuery):
    rows = get_user_orders(callback.from_user.id)
    if not rows:
        await callback.message.edit_text(
            "Bạn chưa có đơn hàng nào.",
            reply_markup=kb_main_menu()
        )
        await callback.answer()
        return

    text = "<b>Đơn hàng của bạn:</b>\n\n"
    for order_id, product_name, price, status, created_at in rows:
        text += (
            f"• <b>#{order_id}</b> - {product_name}\n"
            f"  Giá: {format_currency(price)}\n"
            f"  Trạng thái: <b>{text_status(status)}</b>\n"
            f"  Thời gian: {created_at}\n\n"
        )

    await callback.message.edit_text(text, reply_markup=kb_main_menu())
    await callback.answer()


@dp.callback_query(F.data == "huong_dan_mua")
async def cb_huong_dan_mua(callback: CallbackQuery):
    text = (
        "<b>Hướng dẫn mua hàng</b>\n\n"
        "1. Bấm <b>Xem sản phẩm</b>\n"
        "2. Chọn gói cần mua\n"
        "3. Bấm <b>Mua ngay</b>\n"
        "4. Chuyển khoản theo đúng QR / nội dung chuyển khoản\n"
        "5. Gửi ảnh bill cho bot\n"
        "6. Chờ admin xác nhận\n"
        "7. Admin nhập thủ công nội dung giao hàng và bot sẽ gửi cho bạn"
    )
    await callback.message.edit_text(text, reply_markup=kb_main_menu())
    await callback.answer()


@dp.callback_query(F.data == "contact")
async def cb_contact(callback: CallbackQuery):
    await callback.message.edit_text(
        f"☎️ Hỗ trợ / Liên hệ: {SUPPORT_USERNAME}",
        reply_markup=kb_main_menu()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("product_"))
async def cb_product_detail(callback: CallbackQuery):
    product_id = callback.data.replace("product_", "")
    product = PRODUCTS.get(product_id)

    if not product:
        await callback.answer("Không tìm thấy sản phẩm.", show_alert=True)
        return

    text = (
        f"<b>{product['ten']}</b>\n\n"
        f"💰 Giá: <b>{format_currency(product['gia'])}</b>\n"
        f"📝 Mô tả: {product['mo_ta']}\n\n"
        "Bấm <b>Mua ngay</b> để tạo đơn hàng."
    )
    await callback.message.edit_text(text, reply_markup=kb_buy_product(product_id))
    await callback.answer()


@dp.callback_query(F.data.startswith("buy_"))
async def cb_buy_product(callback: CallbackQuery, state: FSMContext):
    product_id = callback.data.replace("buy_", "")
    product = PRODUCTS.get(product_id)

    if not product:
        await callback.answer("Không tìm thấy sản phẩm.", show_alert=True)
        return

    order_id = create_order(
        user_id=callback.from_user.id,
        product_id=product_id,
        product_name=product["ten"],
        price=product["gia"]
    )

    await state.set_state(BuyFlow.cho_gui_bill)
    await state.update_data(order_id=order_id)

    qr_url = tao_url_qr(order_id, product["gia"])
    noi_dung_ck = tao_noi_dung_ck(order_id)

    text = (
        f"<b>Tạo đơn thành công</b>\n\n"
        f"Mã đơn: <b>#{order_id}</b>\n"
        f"Sản phẩm: <b>{product['ten']}</b>\n"
        f"Số tiền: <b>{format_currency(product['gia'])}</b>\n\n"
        f"🏦 Ngân hàng: <b>{BANK_NAME}</b>\n"
        f"👤 Chủ tài khoản: <b>{ACCOUNT_NAME}</b>\n"
        f"🔢 Số tài khoản: <b>{BANK_ACCOUNT}</b>\n"
        f"📌 Nội dung chuyển khoản: <code>{noi_dung_ck}</code>\n\n"
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
        await message.answer("🏠 Menu chính:", reply_markup=kb_main_menu())
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
async def admin_duyet(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Bạn không có quyền.", show_alert=True)
        return

    order_id = int(callback.data.replace("admin_duyet_", ""))
    order = get_order(order_id)

    if not order:
        await callback.answer("Không tìm thấy đơn hàng.", show_alert=True)
        return

    if order[5] == "da_giao":
        await callback.answer("Đơn này đã giao rồi.")
        return

    update_order_status(order_id, "da_duyet_cho_nhap")
    await state.set_state(AdminFlow.cho_nhap_noi_dung_giao)
    await state.update_data(order_id=order_id)

    await callback.message.answer(
        f"✅ Đã duyệt đơn <b>#{order_id}</b>.\n\n"
        "Bây giờ bạn hãy <b>nhập thủ công nội dung giao hàng</b>.\n\n"
        "Ví dụ:\n"
        "<code>Email: abc@gmail.com\n"
        "Pass: 123456\n"
        "2FA: xxxx\n"
        "Ghi chú: đổi pass sau khi nhận</code>"
    )

    try:
        await callback.message.edit_caption(
            caption=(callback.message.caption or "") + "\n\n<b>Kết quả:</b> Đã duyệt, chờ admin nhập nội dung giao hàng"
        )
    except Exception:
        pass

    await callback.answer("Đã duyệt đơn, chờ nhập nội dung giao hàng.")


@dp.message(AdminFlow.cho_nhap_noi_dung_giao)
async def admin_nhap_noi_dung_giao(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    order_id = data.get("order_id")

    if not order_id:
        await message.answer("Không tìm thấy đơn hàng cần giao.")
        await state.clear()
        return

    order = get_order(order_id)
    if not order:
        await message.answer("Đơn hàng không tồn tại.")
        await state.clear()
        return

    delivered_content = message.text.strip()

    if not delivered_content:
        await message.answer("Bạn hãy nhập nội dung giao hàng.")
        return

    save_delivery(order_id, delivered_content)

    text_user = (
        f"<b>Đơn hàng #{order_id} đã được duyệt</b>\n\n"
        f"Sản phẩm: <b>{order[3]}</b>\n"
        f"Nội dung giao hàng:\n<code>{delivered_content}</code>\n\n"
        "Cảm ơn bạn đã mua hàng!\n"
        "Bạn có thể tiếp tục mua thêm ở menu bên dưới."
    )

    await bot.send_message(
        chat_id=order[1],
        text=text_user,
        reply_markup=kb_main_menu()
    )

    await message.answer(
        f"✅ Đã giao hàng thủ công cho đơn <b>#{order_id}</b>."
    )
    await state.clear()


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

    reject_order(order_id)

    await bot.send_message(
        chat_id=order[1],
        text=(
            f"❌ Đơn hàng <b>#{order_id}</b> của bạn đã bị từ chối.\n"
            "Nếu bạn đã thanh toán, vui lòng liên hệ admin để được hỗ trợ.\n\n"
            f"Hỗ trợ: {SUPPORT_USERNAME}"
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


# =========================
# MAIN
# =========================
async def main():
    init_db()
    await set_bot_commands()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
