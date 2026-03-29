import asyncio
import logging
import sqlite3
import html
import httpx
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

# --- CẤU HÌNH ---
BOT_TOKEN = "8649986734:AAEPEY3qI8OHOzAz7PUKnxDUmoNHxkXwBNc"
ADMIN_ID = 7078570432
CHAYCODE_API_KEY = "8fc8e078133cde11" # API Key từ yêu cầu trước

SUPPORT_USERNAME = "@tai_khoan_xin"
BASE_DIR = Path(__file__).resolve().parent
DB_NAME = str(BASE_DIR / "shop_bot.db")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- LỚP KẾT NỐI API OTP ---
class ChayCodeAPI:
    def __init__(self, api_key):
        self.base_url = "https://chaycodeso3.com/api"
        self.api_key = api_key

    async def _request(self, params):
        params['apik'] = self.api_key
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(self.base_url, params=params, timeout=15)
                return resp.json()
            except Exception as e:
                logging.error(f"Lỗi API OTP: {e}")
                return {"ResponseCode": 1, "Msg": "Lỗi kết nối API"}

api_otp = ChayCodeAPI(CHAYCODE_API_KEY)

# --- DATABASE & UTILS (Giữ nguyên từ code cũ) ---
def db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    cur = conn.cursor()
    # ... (Các lệnh khởi tạo bảng giữ nguyên từ source 7-14)
    conn.commit()
    conn.close()

# --- HANDLERS ---

@dp.message(Command("start"))
async def start(m: Message):
    text = (
        "Chào mừng bạn đến với Shop Bot & Dịch vụ OTP 🤖\n\n"
        "/menu - Mua sản phẩm & Thuê số OTP\n"
        "/donhang - Lịch sử mua hàng\n"
        f"Hỗ trợ: {SUPPORT_USERNAME}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Sản phẩm Shop", callback_data="sp")],
        [InlineKeyboardButton(text="📱 Thuê số OTP (API)", callback_data="otp_menu")],
        [InlineKeyboardButton(text="☎️ Hỗ trợ", callback_data="contact")]
    ])
    await m.answer(text, reply_markup=kb)

# --- PHẦN XỬ LÝ OTP ---

@dp.callback_query(F.data == "otp_menu")
async def show_otp_apps(c: CallbackQuery):
    if c.from_user.id == ADMIN_ID:
        await c.answer("Admin hãy dùng nick khách để test thuê số.", show_alert=True)
        return

    await c.message.edit_text("⏳ Đang tải danh sách ứng dụng từ Server OTP...")
    res = await api_otp._request({'act': 'app'})
    
    if res.get('ResponseCode') == 0:
        btns = []
        # Lấy 10 ứng dụng phổ biến [cite: 16, 20]
        for app in res['Result'][:10]:
            btns.append([InlineKeyboardButton(
                text=f"📲 {app['Name']} | {app['Cost']:,}đ", 
                callback_data=f"otpbuy_{app['Id']}_{app['Name']}"
            )])
        btns.append([InlineKeyboardButton(text="⬅️ Quay lại", callback_data="menu")])
        await c.message.edit_text("<b>Vui lòng chọn ứng dụng cần thuê số:</b>", 
                                reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    else:
        await c.message.edit_text("❌ Không thể lấy danh sách ứng dụng. Vui lòng thử lại sau.", 
                                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                    [InlineKeyboardButton(text="🏠 Menu", callback_data="menu")]
                                ]))

@dp.callback_query(F.data.startswith("otpbuy_"))
async def process_otp_order(c: CallbackQuery):
    _, app_id, app_name = c.data.split("_")
    
    await c.message.edit_text(f"⏳ Đang yêu cầu hệ thống cấp số cho <b>{app_name}</b>...")
    
    # Bước 1: Lấy số điện thoại [cite: 17, 69]
    res = await api_otp._request({'act': 'number', 'appId': app_id})
    
    if res.get('ResponseCode') == 0:
        req_id = res['Result']['Id']
        phone = res['Result']['Number']
        
        await c.message.edit_text(
            f"✅ <b>THUÊ SỐ THÀNH CÔNG</b>\n\n"
            f"📦 Ứng dụng: <b>{app_name}</b>\n"
            f"📞 Số điện thoại: <code>0{phone}</code>\n"
            f"🆔 ID phiên: <code>{req_id}</code>\n\n"
            f"⚠️ <i>Bạn hãy nhập số trên vào ứng dụng. Bot sẽ tự động gửi mã OTP khi nhận được tin nhắn...</i>"
        )
        
        # Bước 2: Vòng lặp chờ mã OTP (Tối đa 5 phút) [cite: 74, 81]
        for _ in range(50): # Check mỗi 6 giây
            await asyncio.sleep(6)
            code_res = await api_otp._request({'act': 'code', 'id': req_id})
            
            if code_res.get('ResponseCode') == 0: # Thành công 
                otp_code = code_res['Result']['Code']
                sms_text = code_res['Result']['SMS']
                
                await c.message.answer(
                    f"🎯 <b>CÓ MÃ OTP MỚI!</b>\n\n"
                    f"🔑 Mã: <code>{otp_code}</code>\n"
                    f"📱 Số: <code>0{phone}</code>\n"
                    f"💬 Nội dung: <i>{html.escape(sms_text)}</i>"
                )
                return
            
            elif code_res.get('ResponseCode') == 2: # Hết hạn/Hủy
                break
                
        await c.message.answer(f"❌ Phiên thuê số <code>0{phone}</code> đã hết thời gian chờ hoặc bị hủy.")
    else:
        # Xử lý lỗi (ví dụ hết tiền) [cite: 73]
        await c.message.answer(f"❌ Lỗi thuê số: {res.get('Msg')}\nKiểm tra lại số dư trên web ChayCodeSo3.")

# --- GIỮ NGUYÊN CÁC PHẦN CÒN LẠI CỦA SHOP BOT ---
@dp.callback_query(F.data == "menu")
async def back_to_menu(c: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Sản phẩm Shop", callback_data="sp")],
        [InlineKeyboardButton(text="📱 Thuê số OTP (API)", callback_data="otp_menu")],
        [InlineKeyboardButton(text="☎️ Hỗ trợ", callback_data="contact")]
    ])
    await c.message.edit_text("🏠 Menu chính:", reply_markup=kb)

# ... (Copy toàn bộ các handler sp, buy, bill, admin commands từ source code gốc của bạn vào đây)

async def main():
    init_db() [cite: 124]
    print("Bot đang chạy...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
