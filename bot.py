import asyncio
import logging
import sqlite3
import html
import httpx
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
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
ADMIN_ID = 7078570432
CHAYCODE_API_KEY = "8fc8e078133cde11"

SUPPORT_USERNAME = "@tai_khoan_xin"
BASE_DIR = Path(__file__).resolve().parent
DB_NAME = str(BASE_DIR / "shop_bot.db")

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# cache tên app để khỏi nhét app_name vào callback_data
OTP_APP_CACHE = {}


# =========================
# API OTP
# =========================
class ChayCodeAPI:
    def __init__(self, api_key: str):
        self.base_url = "https://chaycodeso3.com/api"
        self.api_key = api_key

    async def _request(self, params: dict):
        params = dict(params)
        params["apik"] = self.api_key

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(self.base_url, params=params, timeout=15)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                logging.exception("Lỗi API OTP: %s", e)
                return {"ResponseCode": 1, "Msg": f"Lỗi kết nối API: {e}"}


api_otp = ChayCodeAPI(CHAYCODE_API_KEY)


# =========================
# DATABASE
# =========================
def db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()

    # user đã từng nhắn bot
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # lưu lịch sử thuê OTP
    cur.execute("""
        CREATE TABLE IF NOT EXISTS otp_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            app_id TEXT,
            app_name TEXT,
            request_id TEXT,
            phone TEXT,
            otp_code TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def save_user(user_id: int, username: str | None, full_name: str):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (user_id, username, full_name)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            full_name = excluded.full_name
    """, (user_id, username, full_name))
    conn.commit()
    conn.close()


def create_otp_order(user_id: int, app_id: str, app_name: str, request_id: str, phone: str):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO otp_orders (user_id, app_id, app_name, request_id, phone, status)
        VALUES (?, ?, ?, ?, ?, 'waiting_code')
    """, (user_id, app_id, app_name, request_id, phone))
    conn.commit()
    conn.close()


def update_otp_code(request_id: str, otp_code: str, status: str):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE otp_orders
        SET otp_code = ?, status = ?
        WHERE request_id = ?
    """, (otp_code, status, request_id))
    conn.commit()
    conn.close()


def update_otp_status(request_id: str, status: str):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE otp_orders
        SET status = ?
        WHERE request_id = ?
    """, (status, request_id))
    conn.commit()
    conn.close()


# =========================
# KEYBOARD
# =========================
def main_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Sản phẩm Shop", callback_data="sp")],
        [InlineKeyboardButton(text="📱 Thuê số OTP (API)", callback_data="otp_menu")],
        [InlineKeyboardButton(text="☎️ Hỗ trợ", callback_data="contact")]
    ])


# =========================
# HANDLERS
# =========================
@dp.message(Command("start"))
async def start(m: Message):
    save_user(
        user_id=m.from_user.id,
        username=m.from_user.username,
        full_name=m.from_user.full_name
    )

    text = (
        "Chào mừng bạn đến với Shop Bot & Dịch vụ OTP 🤖\n\n"
        "/menu - Mua sản phẩm & Thuê số OTP\n"
        "/donhang - Lịch sử mua hàng\n"
        f"Hỗ trợ: {SUPPORT_USERNAME}"
    )
    await m.answer(text, reply_markup=main_menu_keyboard())


@dp.message(Command("menu"))
async def menu_cmd(m: Message):
    await m.answer("🏠 Menu chính:", reply_markup=main_menu_keyboard())


@dp.callback_query(F.data == "menu")
async def back_to_menu(c: CallbackQuery):
    await c.message.edit_text("🏠 Menu chính:", reply_markup=main_menu_keyboard())
    await c.answer()


@dp.callback_query(F.data == "contact")
async def contact_handler(c: CallbackQuery):
    await c.message.edit_text(
        f"☎️ Hỗ trợ khách hàng: {SUPPORT_USERNAME}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Quay lại", callback_data="menu")]
        ])
    )
    await c.answer()


@dp.callback_query(F.data == "sp")
async def sp_handler(c: CallbackQuery):
    await c.message.edit_text(
        "🛍 Phần sản phẩm shop của bạn hãy gắn lại code cũ vào đây.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Quay lại", callback_data="menu")]
        ])
    )
    await c.answer()


# =========================
# PHẦN OTP
# =========================
@dp.callback_query(F.data == "otp_menu")
async def show_otp_apps(c: CallbackQuery):
    if c.from_user.id == ADMIN_ID:
        await c.answer("Admin hãy dùng nick khách để test thuê số.", show_alert=True)
        return

    await c.message.edit_text("⏳ Đang tải danh sách ứng dụng từ Server OTP...")

    res = await api_otp._request({"act": "app"})

    if res.get("ResponseCode") != 0:
        await c.message.edit_text(
            f"❌ Không thể lấy danh sách ứng dụng.\n{html.escape(str(res.get('Msg', 'Lỗi không xác định')))}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Menu", callback_data="menu")]
            ])
        )
        await c.answer()
        return

    result = res.get("Result", [])
    if not isinstance(result, list) or not result:
        await c.message.edit_text(
            "❌ Danh sách ứng dụng đang trống.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Menu", callback_data="menu")]
            ])
        )
        await c.answer()
        return

    OTP_APP_CACHE.clear()
    buttons = []

    for app in result[:10]:
        app_id = str(app.get("Id", ""))
        app_name = str(app.get("Name", "Không rõ"))
        app_cost = app.get("Cost", 0)

        OTP_APP_CACHE[app_id] = {
            "name": app_name,
            "cost": app_cost,
        }

        buttons.append([
            InlineKeyboardButton(
                text=f"📲 {app_name} | {int(app_cost):,}đ" if str(app_cost).isdigit() else f"📲 {app_name} | {app_cost}",
                callback_data=f"otpbuy:{app_id}"
            )
        ])

    buttons.append([InlineKeyboardButton(text="⬅️ Quay lại", callback_data="menu")])

    await c.message.edit_text(
        "<b>Vui lòng chọn ứng dụng cần thuê số:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await c.answer()


@dp.callback_query(F.data.startswith("otpbuy:"))
async def process_otp_order(c: CallbackQuery):
    if c.from_user.id == ADMIN_ID:
        await c.answer("Admin hãy dùng nick khách để test thuê số.", show_alert=True)
        return

    app_id = c.data.split(":", 1)[1]
    app_info = OTP_APP_CACHE.get(app_id, {})
    app_name = app_info.get("name", f"App {app_id}")

    await c.message.edit_text(f"⏳ Đang yêu cầu hệ thống cấp số cho <b>{html.escape(app_name)}</b>...")

    res = await api_otp._request({"act": "number", "appId": app_id})

    if res.get("ResponseCode") != 0:
        await c.message.edit_text(
            f"❌ Lỗi thuê số: {html.escape(str(res.get('Msg', 'Không rõ lỗi')))}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Quay lại", callback_data="otp_menu")],
                [InlineKeyboardButton(text="🏠 Menu", callback_data="menu")]
            ])
        )
        await c.answer()
        return

    result = res.get("Result", {})
    req_id = str(result.get("Id", ""))
    phone = str(result.get("Number", ""))

    if not req_id or not phone:
        await c.message.edit_text(
            "❌ API trả dữ liệu không hợp lệ, thiếu ID phiên hoặc số điện thoại.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Quay lại", callback_data="otp_menu")]
            ])
        )
        await c.answer()
        return

    full_phone = phone if phone.startswith("0") else f"0{phone}"

    create_otp_order(
        user_id=c.from_user.id,
        app_id=app_id,
        app_name=app_name,
        request_id=req_id,
        phone=full_phone
    )

    await c.message.edit_text(
        f"✅ <b>THUÊ SỐ THÀNH CÔNG</b>\n\n"
        f"📦 Ứng dụng: <b>{html.escape(app_name)}</b>\n"
        f"📞 Số điện thoại: <code>{html.escape(full_phone)}</code>\n"
        f"🆔 ID phiên: <code>{html.escape(req_id)}</code>\n\n"
        f"⚠️ <i>Bạn hãy nhập số trên vào ứng dụng. Bot sẽ tự động gửi mã OTP khi nhận được tin nhắn...</i>"
    )
    await c.answer()

    # chờ OTP tối đa 5 phút
    for _ in range(50):
        await asyncio.sleep(6)

        code_res = await api_otp._request({"act": "code", "id": req_id})
        response_code = code_res.get("ResponseCode")

        if response_code == 0:
            code_data = code_res.get("Result", {})
            otp_code = str(code_data.get("Code", ""))
            sms_text = str(code_data.get("SMS", ""))

            update_otp_code(req_id, otp_code, "done")

            await c.message.answer(
                f"🎯 <b>CÓ MÃ OTP MỚI!</b>\n\n"
                f"🔑 Mã: <code>{html.escape(otp_code)}</code>\n"
                f"📱 Số: <code>{html.escape(full_phone)}</code>\n"
                f"💬 Nội dung: <i>{html.escape(sms_text)}</i>"
            )
            return

        elif response_code == 2:
            update_otp_status(req_id, "expired")
            await c.message.answer(
                f"❌ Phiên thuê số <code>{html.escape(full_phone)}</code> đã hết hạn hoặc bị hủy."
            )
            return

    update_otp_status(req_id, "timeout")
    await c.message.answer(
        f"❌ Phiên thuê số <code>{html.escape(full_phone)}</code> đã hết thời gian chờ OTP."
    )


@dp.message(Command("donhang"))
async def donhang_handler(m: Message):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT app_name, phone, otp_code, status, created_at
        FROM otp_orders
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 10
    """, (m.from_user.id,))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await m.answer("Bạn chưa có đơn OTP nào.")
        return

    text = ["<b>📜 10 đơn OTP gần nhất:</b>\n"]
    for i, row in enumerate(rows, start=1):
        text.append(
            f"{i}. <b>{html.escape(row['app_name'] or '-')}</b>\n"
            f"   Số: <code>{html.escape(row['phone'] or '-')}</code>\n"
            f"   OTP: <code>{html.escape(row['otp_code'] or 'Chưa có')}</code>\n"
            f"   Trạng thái: <b>{html.escape(row['status'] or '-')}</b>\n"
            f"   Thời gian: {html.escape(str(row['created_at']))}\n"
        )

    await m.answer("\n".join(text))


# =========================
# MAIN
# =========================
async def main():
    init_db()
    print("Bot đang chạy...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
