import asyncio
import logging
import sqlite3
import html
import httpx  # Cần cài đặt: pip install httpx
from pathlib import Path
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
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter

# --- CẤU HÌNH ---
BOT_TOKEN = "8649986734:AAEPEY3qI8OHOzAz7PUKnxDUmoNHxkXwBNc"
ADMIN_ID = 7078570432

# Cấu hình API OTP 
OTP_API_KEY = "8fc8e078133cde11"
OTP_BASE_URL = "https://chaycodeso3.com/api"

SUPPORT_USERNAME = "@tai_khoan_xin"
BASE_DIR = Path(__file__).resolve().parent
DB_NAME = str(BASE_DIR / "shop_bot.db")

# ... (Các cấu hình ngân hàng giữ nguyên) ...
BANK_NAME = "MB Bank"
BANK_BIN = "970422"
BANK_ACCOUNT = "346641789567"
ACCOUNT_NAME = "VU VAN CUONG"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- LỚP XỬ LÝ API OTP ---
class ChayCodeAPI:
    def __init__(self, api_key):
        self.api_key = api_key

    async def _get(self, params):
        params['apik'] = self.api_key
        async with httpx.AsyncClient() as client:
            try:
                # Sử dụng phương thức GET theo yêu cầu của API 
                response = await client.get(OTP_BASE_URL, params=params, timeout=15)
                return response.json()
            except Exception as e:
                logging.error(f"Lỗi kết nối API OTP: {e}")
                return {"ResponseCode": 1, "Msg": "Lỗi kết nối Server OTP"}

    async def get_apps(self):
        """Lấy danh sách ứng dụng đang chạy """
        return await self._get({'act': 'app'})

    async def request_number(self, app_id):
        """Lấy 1 số sim để nhận code """
        return await self._get({'act': 'number', 'appId': app_id})

    async def get_otp_code(self, request_id):
        """Lấy mã code của số điện thoại đã thuê """
        return await self._get({'act': 'code', 'id': request_id})

otp_api = ChayCodeAPI(OTP_API_KEY)

# --- DATABASE & UTILS (Giữ nguyên các hàm khởi tạo DB của bạn) ---
# ... (Hàm db, init_db, save_user_info giữ nguyên) ...

def db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    # ... (Toàn bộ code init_db của bạn) ...
    conn = db()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, full_name TEXT, username TEXT, is_active INTEGER DEFAULT 1)")
    cur.execute("CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, product TEXT, price INTEGER, status TEXT, quantity INTEGER DEFAULT 1, product_code TEXT, proof TEXT, delivery TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS products(code TEXT PRIMARY KEY, name TEXT, price INTEGER, stock INTEGER, active INTEGER, category TEXT)")
    conn.commit()
    conn.close()

# --- MENU CHỈNH SỬA ĐỂ THÊM DỊCH VỤ OTP ---
def main_menu_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛍 Sản phẩm Shop", callback_data="sp")],
            [InlineKeyboardButton(text="📱 Thuê số OTP (API)", callback_data="otp_list")],
            [InlineKeyboardButton(text="☎️ Hỗ trợ", callback_data="contact")],
        ]
    )

# --- HANDLERS ---

@dp.message(Command("start"))
@dp.message(Command("menu"))
async def show_menu(m: Message):
    # save_user_info(m.from_user)
    await m.answer("🛍 <b>Chào mừng bạn đến với Shop!</b>\nVui lòng chọn dịch vụ bên dưới:", reply_markup=main_menu_keyboard())

# --- XỬ LÝ OTP ---

@dp.callback_query(F.data == "otp_list")
async def otp_list_callback(c: CallbackQuery):
    await c.message.edit_text("⏳ Đang tải danh sách dịch vụ OTP...")
    res = await otp_api.get_apps()
    
    if res.get("ResponseCode") == 0:
        btns = []
        # Lấy tối đa 10 dịch vụ phổ biến 
        for app in res["Result"][:10]:
            btns.append([InlineKeyboardButton(
                text=f"{app['Name']} | {app['Cost']:,}đ", 
                callback_data=f"otpbuy_{app['Id']}_{app['Name']}"
            )])
        btns.append([InlineKeyboardButton(text="⬅️ Quay lại", callback_data="menu")])
        await c.message.edit_text("<b>Vui lòng chọn ứng dụng cần thuê số:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    else:
        await c.message.edit_text(f"❌ Lỗi: {res.get('Msg')}", reply_markup=main_menu_keyboard())

@dp.callback_query(F.data.startswith("otpbuy_"))
async def otp_buy_callback(c: CallbackQuery):
    _, app_id, app_name = c.data.split("_")
    
    await c.message.edit_text(f"⏳ Đang yêu cầu cấp số cho <b>{app_name}</b>...")
    res = await otp_api.request_number(app_id)
    
    if res.get("ResponseCode") == 0:
        req_id = res["Result"]["Id"]
        phone = res["Result"]["Number"] # Số điện thoại không có số 0 ở đầu 
        
        await c.message.edit_text(
            f"✅ <b>THUÊ SỐ THÀNH CÔNG</b>\n\n"
            f"📦 Dịch vụ: <b>{app_name}</b>\n"
            f"📞 Số điện thoại: <code>0{phone}</code>\n"
            f"🆔 ID phiên: <code>{req_id}</code>\n\n"
            f"🕒 <i>Bot đang đợi mã OTP. Bạn hãy nhập số trên vào ứng dụng...</i>"
        )
        
        # Chạy vòng lặp kiểm tra mã OTP trong nền (Background) 
        asyncio.create_task(wait_for_otp(c.from_user.id, req_id, phone, app_name))
    else:
        await c.message.answer(f"❌ Lỗi: {res.get('Msg')}")

async def wait_for_otp(user_id, req_id, phone, app_name):
    # Kiểm tra mã mỗi 6 giây trong tối đa 5 phút 
    for _ in range(50):
        await asyncio.sleep(6)
        res = await otp_api.get_otp_code(req_id)
        
        if res.get("ResponseCode") == 0: # Đã nhận được code 
            otp_code = res["Result"]["Code"]
            sms_text = res["Result"]["SMS"]
            await bot.send_message(
                user_id,
                f"🎯 <b>CÓ MÃ OTP MỚI!</b>\n\n"
                f"📱 Dịch vụ: <b>{app_name}</b>\n"
                f"📞 Số: <code>0{phone}</code>\n"
                f"🔑 Mã OTP: <code>{otp_code}</code>\n"
                f"💬 Nội dung: <i>{sms_text}</i>"
            )
            return
        elif res.get("ResponseCode") == 2: # Không nhận được code (hết thời gian) 
            break
            
    await bot.send_message(user_id, f"❌ Hết thời gian chờ mã OTP cho số <code>0{phone}</code> ({app_name}).")

# --- GIỮ NGUYÊN CÁC HANDLER KHÁC CỦA BẠN ---
@dp.callback_query(F.data == "menu")
async def back_to_menu(c: CallbackQuery):
    await c.message.edit_text("🏠 Menu chính:", reply_markup=main_menu_keyboard())

# ... (Copy tiếp các phần callback_query(F.data == "sp"), handle cat_, buy_... của bạn vào đây) ...

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
