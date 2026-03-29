import asyncio
import logging
import sqlite3
import html
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

BOT_TOKEN = "8649986734:AAEPEY3qI8OHOzAz7PUKnxDUmoNHxkXwBNc"
ADMIN_ID = 7078570432

BANK_NAME = "MB Bank"
BANK_BIN = "970422"
BANK_ACCOUNT = "346641789567"
ACCOUNT_NAME = "VU VAN CUONG"

SUPPORT_USERNAME = "@tai_khoan_xin"
BASE_DIR = Path(__file__).resolve().parent
DB_NAME = str(BASE_DIR / "shop_bot.db")

# Chỉ dùng để tạo dữ liệu ban đầu vào database
DEFAULT_PRODUCTS = {
    "sp1": {"ten": "Adobe Creative Cloud 3 Tháng", "gia": 159000, "sl": 5, "nhom": "Adobe"},

    "sp2": {"ten": "Acc Shoppe Ngâm 5 Tháng Voucher 80k - 100k", "gia": 29000, "sl": 5, "nhom": "Shopee"},
    "sp3": {"ten": "Đặt Đơn Shopee Giảm 100k", "gia": 59000, "sl": 5, "nhom": "Shopee"},

    "sp4": {"ten": "Canva Edu 1 Năm", "gia": 149000, "sl": 5, "nhom": "Canva"},
    "sp5": {"ten": "Canva Pro 1 Năm", "gia": 289000, "sl": 5, "nhom": "Canva"},

    "sp6": {"ten": "CapCut Pro 14 Ngày_BHF", "gia": 25000, "sl": 7, "nhom": "CapCut"},
    "sp7": {"ten": "CapCut Pro 35d_BHF", "gia": 45000, "sl": 5, "nhom": "CapCut"},
    "sp8": {"ten": "CapCut Pro 1 Năm_BHF", "gia": 450000, "sl": 5, "nhom": "CapCut"},

    "sp9": {"ten": "ChatGPT Plus 1 Tháng", "gia": 99000, "sl": 9, "nhom": "ChatGPT + Gemini"},
    "sp10": {"ten": "Gemini 2TB AI PRO 12 tháng", "gia": 199000, "sl": 2, "nhom": "ChatGPT + Gemini"},

    "sp11": {"ten": "Youtube Premium 1 Tháng", "gia": 55000, "sl": 5, "nhom": "Youtube"},
    "sp12": {"ten": "Youtube 3 Tháng", "gia": 159000, "sl": 5, "nhom": "Youtube"},

    "sp13": {"ten": "Mã Highlands Coffee Nước Free", "gia": 15000, "sl": 5, "nhom": "Highlands Coffee Free"},
}

CATEGORY_ORDER = [
    "Adobe",
    "Shopee",
    "Canva",
    "CapCut",
    "ChatGPT + Gemini",
    "Youtube",
    "Highlands Coffee Free",
]

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()


class BuyFlow(StatesGroup):
    cho_so_luong = State()
    cho_bill = State()


class AdminFlow(StatesGroup):
    nhap_noi_dung = State()
    update_so_luong = State()


def db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_code TEXT,
            product TEXT,
            price INTEGER,
            quantity INTEGER DEFAULT 1,
            status TEXT,
            proof TEXT,
            delivery TEXT
        )
    """)

    cur.execute("PRAGMA table_info(orders)")
    cols = [row["name"] for row in cur.fetchall()]

    if "quantity" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN quantity INTEGER DEFAULT 1")

    if "product_code" not in cols:
        cur.execute("ALTER TABLE orders ADD COLUMN product_code TEXT")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products(
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            category TEXT NOT NULL DEFAULT 'Highlands Coffee Free'
        )
    """)

    cur.execute("PRAGMA table_info(products)")
    product_cols = [row["name"] for row in cur.fetchall()]

    if "category" not in product_cols:
        cur.execute("ALTER TABLE products ADD COLUMN category TEXT NOT NULL DEFAULT 'Highlands Coffee Free'")

    for code, info in DEFAULT_PRODUCTS.items():
        cur.execute("SELECT code FROM products WHERE code=?", (code,))
        row = cur.fetchone()

        if row is None:
            active = 1 if info["sl"] > 0 else 0
            cur.execute("""
                INSERT INTO products(code, name, price, stock, active, category)
                VALUES(?,?,?,?,?,?)
            """, (code, info["ten"], info["gia"], info["sl"], active, info.get("nhom", "Highlands Coffee Free")))
        else:
            cur.execute("""
                UPDATE products
                SET name=?, price=?, category=?
                WHERE code=?
            """, (info["ten"], info["gia"], info.get("nhom", "Highlands Coffee Free"), code))

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
            [InlineKeyboardButton(text="🛍 Xem nhóm sản phẩm", callback_data="sp")],
            [InlineKeyboardButton(text="☎️ Hỗ trợ", callback_data="contact")],
        ]
    )


def get_categories():
    return CATEGORY_ORDER


def category_sort_key(cat_name: str):
    try:
        return CATEGORY_ORDER.index(cat_name)
    except ValueError:
        return 999


def get_product_by_code(pid: str):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT code, name, price, stock, active, category
        FROM products
        WHERE code=?
    """, (pid,))
    row = cur.fetchone()
    conn.close()
    return row


def get_all_products():
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT code, name, price, stock, active, category
        FROM products
    """)
    rows = cur.fetchall()
    conn.close()

    rows = sorted(rows, key=lambda p: (category_sort_key(p["category"]), p["name"].lower()))
    return rows


def category_menu():
    rows = []

    for cat in get_categories():
        rows.append([
            InlineKeyboardButton(
                text=f"📂 {cat}",
                callback_data=f"cat_{cat}"
            )
        ])

    rows.append([InlineKeyboardButton(text="🏠 Menu", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def list_sp_by_category(category_name: str):
    rows = []
    products = [p for p in get_all_products() if p["category"] == category_name]

    for i, p in enumerate(products, start=1):
        stock = p["stock"]
        active = p["active"]

        if active == 1 and stock > 0:
            label = f"[{i}] {p['name']} | {p['price'] // 1000}k | Còn: {stock}"
        else:
            label = f"[{i}] {p['name']} | {p['price'] // 1000}k | Hết hàng"

        rows.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"buy_{p['code']}"
            )
        ])

    if not products:
        rows.append([
            InlineKeyboardButton(
                text="Không có sản phẩm trong nhóm này",
                callback_data="none"
            )
        ])

    rows.append([InlineKeyboardButton(text="⬅️ Quay lại nhóm", callback_data="sp")])
    rows.append([InlineKeyboardButton(text="🏠 Menu", callback_data="menu")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.message(Command("start"))
async def start(m: Message):
    text = (
        "Chào bạn 👋\n\n"
        "Các lệnh có thể dùng:\n"
        "/start - Bắt đầu\n"
        "/menu - Xem nhóm sản phẩm\n"
        "/help - Hỗ trợ\n"
        "/donhang - Đơn hàng đã mua\n\n"
        f"Nếu cần hỗ trợ thêm, nhắn {SUPPORT_USERNAME}"
    )
    await m.answer(text, reply_markup=menu())


@dp.message(Command("menu"))
async def menu_command(m: Message):
    await m.answer("🛍 Chọn nhóm sản phẩm:", reply_markup=category_menu())


@dp.message(Command("help"))
async def help_command(m: Message):
    text = (
        "<b>Hỗ trợ sử dụng bot</b>\n\n"
        "/start - Bắt đầu\n"
        "/menu - Xem nhóm sản phẩm\n"
        "/help - Hỗ trợ\n"
        "/donhang - Xem đơn hàng đã mua\n"
        "/update - Cập nhật số lượng sản phẩm (chỉ admin)\n"
        "/tonkho - Xem tồn kho nhanh (chỉ admin)\n\n"
        f"Liên hệ hỗ trợ: {SUPPORT_USERNAME}"
    )
    await m.answer(text)


@dp.message(Command("donhang"))
async def donhang_command(m: Message):
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, product, price, quantity, status
        FROM orders
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 10
    """, (m.from_user.id,))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await m.answer("Bạn chưa có đơn hàng nào.", reply_markup=menu())
        return

    trang_thai_map = {
        "pay": "Chờ thanh toán",
        "check": "Chờ admin duyệt",
        "approved": "Đã duyệt",
        "done": "Đã giao hàng",
        "reject": "Đã từ chối",
    }

    text = "<b>🧾 Đơn hàng của bạn:</b>\n\n"
    for row in rows:
        text += (
            f"🆔 Đơn <b>#{row['id']}</b>\n"
            f"📦 Sản phẩm: <b>{html.escape(row['product'])}</b>\n"
            f"🔢 Số lượng: <b>{row['quantity']}</b>\n"
            f"💰 Tổng tiền: <b>{row['price']:,}đ</b>\n"
            f"📌 Trạng thái: <b>{trang_thai_map.get(row['status'], row['status'])}</b>\n\n"
        )

    await m.answer(text, reply_markup=menu())


@dp.message(Command("tonkho"))
async def tonkho_command(m: Message):
    if m.from_user.id != ADMIN_ID:
        await m.answer("Bạn không có quyền dùng lệnh này.")
        return

    products = get_all_products()

    if not products:
        await m.answer("Chưa có sản phẩm nào trong kho.")
        return

    text = "<b>📦 TỒN KHO HIỆN TẠI</b>\n\n"
    for i, p in enumerate(products, start=1):
        trang_thai = "Đang bán" if p["active"] == 1 and p["stock"] > 0 else "Hết hàng / Đang khóa"
        text += (
            f"{i}. <b>{html.escape(p['name'])}</b>\n"
            f"📂 Nhóm: <b>{html.escape(p['category'])}</b>\n"
            f"💰 Giá: <b>{p['price']:,}đ</b>\n"
            f"📦 Tồn kho: <b>{p['stock']}</b>\n"
            f"📌 Trạng thái: <b>{trang_thai}</b>\n\n"
        )

    await m.answer(text)


@dp.callback_query(F.data == "menu")
async def back(c: CallbackQuery):
    await c.message.edit_text("🏠 Menu chính:", reply_markup=menu())
    await c.answer()


@dp.callback_query(F.data == "sp")
async def sp(c: CallbackQuery):
    await c.message.edit_text("🛍 Chọn nhóm sản phẩm:", reply_markup=category_menu())
    await c.answer()


@dp.callback_query(F.data == "contact")
async def contact(c: CallbackQuery):
    await c.message.edit_text(
        f"☎️ Hỗ trợ: {SUPPORT_USERNAME}",
        reply_markup=menu()
    )
    await c.answer()


@dp.callback_query(F.data == "none")
async def none_callback(c: CallbackQuery):
    await c.answer()


@dp.callback_query(F.data.startswith("cat_"))
async def show_category(c: CallbackQuery):
    category_name = c.data.split("_", 1)[1]
    await c.message.edit_text(
        f"🛍 Nhóm sản phẩm: <b>{html.escape(category_name)}</b>",
        reply_markup=list_sp_by_category(category_name)
    )
    await c.answer()


@dp.callback_query(F.data.startswith("buy_"))
async def buy(c: CallbackQuery, state: FSMContext):
    if c.from_user.id == ADMIN_ID:
        await c.answer(
            "Admin không thể mua hàng bằng bot này. Hãy dùng tài khoản Telegram khác để test như khách.",
            show_alert=True
        )
        return

    pid = c.data.split("_", 1)[1]
    p = get_product_by_code(pid)

    if not p:
        await c.answer("Không tìm thấy sản phẩm.", show_alert=True)
        return

    if p["active"] != 1 or p["stock"] <= 0:
        await c.answer("❌ Sản phẩm này hiện đã hết hàng. Chờ admin cập nhật lại số lượng.", show_alert=True)
        return

    await state.set_state(BuyFlow.cho_so_luong)
    await state.update_data(pid=pid)

    await c.message.answer(
        f"📦 Sản phẩm: <b>{html.escape(p['name'])}</b>\n"
        f"📂 Nhóm: <b>{html.escape(p['category'])}</b>\n"
        f"💰 Đơn giá: <b>{p['price']:,}đ</b>\n"
        f"📦 Còn lại: <b>{p['stock']}</b>\n\n"
        "Vui lòng nhập số lượng muốn mua:\nVí dụ: 1 - 2 - 3 - 4"
    )
    await c.answer()


@dp.message(BuyFlow.cho_so_luong)
async def chon_so_luong(m: Message, state: FSMContext):
    if m.from_user.id == ADMIN_ID:
        await m.answer("Admin không thể mua hàng bằng bot này. Hãy dùng tài khoản Telegram khác để test như khách.")
        await state.clear()
        return

    text = m.text.strip() if m.text else ""

    if not text.isdigit():
        await m.answer("Vui lòng nhập số lượng bằng số. Ví dụ: <code>2</code>")
        return

    so_luong = int(text)

    if so_luong <= 0:
        await m.answer("Số lượng phải lớn hơn 0.")
        return

    data = await state.get_data()
    pid = data.get("pid")

    if not pid:
        await m.answer("Không tìm thấy sản phẩm. Vui lòng chọn lại từ menu.")
        await state.clear()
        return

    p = get_product_by_code(pid)

    if not p:
        await m.answer("Không tìm thấy sản phẩm. Vui lòng chọn lại từ menu.")
        await state.clear()
        return

    if p["active"] != 1 or p["stock"] <= 0:
        await m.answer("❌ Sản phẩm này hiện đã hết hàng. Chờ admin cập nhật lại số lượng.")
        await state.clear()
        return

    if so_luong > p["stock"]:
        await m.answer(
            f"❌ Số lượng vượt quá tồn kho.\n"
            f"Hiện chỉ còn: <b>{p['stock']}</b>"
        )
        return

    tong_tien = p["price"] * so_luong

    conn = db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO orders(user_id, product_code, product, price, quantity, status)
        VALUES(?,?,?,?,?,?)
    """, (m.from_user.id, pid, p["name"], tong_tien, so_luong, "pay"))
    oid = cur.lastrowid
    conn.commit()
    conn.close()

    await state.set_state(BuyFlow.cho_bill)
    await state.update_data(oid=oid)

    qr = tao_qr(oid, tong_tien)

    caption = (
        f"<b>Đơn #{oid}</b>\n"
        f"📦 Sản phẩm: <b>{html.escape(p['name'])}</b>\n"
        f"📂 Nhóm: <b>{html.escape(p['category'])}</b>\n"
        f"🔢 Số lượng: <b>{so_luong}</b>\n"
        f"💰 Đơn giá: <b>{p['price']:,}đ</b>\n"
        f"💵 Tổng tiền: <b>{tong_tien:,}đ</b>\n\n"
        f"🏦 Ngân hàng: <b>{BANK_NAME}</b>\n"
        f"👤 Chủ tài khoản: <b>{html.escape(ACCOUNT_NAME)}</b>\n"
        f"🔢 Số tài khoản: <b>{BANK_ACCOUNT}</b>\n"
        f"📌 Nội dung chuyển khoản: <code>DH{oid}</code>\n\n"
        "Chuyển khoản xong vui lòng gửi bill vào khung chat này."
    )

    await bot.send_photo(m.from_user.id, qr, caption=caption)


@dp.message(BuyFlow.cho_bill, F.photo)
async def bill(m: Message, state: FSMContext):
    if m.from_user.id == ADMIN_ID:
        await m.answer("Admin không thể gửi bill như khách hàng. Hãy dùng tài khoản Telegram khác để test.")
        await state.clear()
        return

    data = await state.get_data()
    oid = data.get("oid")

    if not oid:
        await m.answer("Không tìm thấy đơn hàng đang chờ bill. Vui lòng đặt lại đơn.")
        await state.clear()
        return

    file_id = m.photo[-1].file_id

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT id, product, price, quantity, status FROM orders WHERE id=?", (oid,))
    order_row = cur.fetchone()

    if not order_row:
        conn.close()
        await m.answer("Không tìm thấy đơn hàng.", reply_markup=menu())
        await state.clear()
        return

    if order_row["status"] != "pay":
        conn.close()
        await m.answer("Đơn này không còn ở trạng thái chờ bill.", reply_markup=menu())
        await state.clear()
        return

    cur.execute(
        "UPDATE orders SET proof=?, status='check' WHERE id=?",
        (file_id, oid)
    )
    conn.commit()
    conn.close()

    user = m.from_user
    username = f"@{user.username}" if user.username else "Không có"
    full_name = html.escape(user.full_name)

    caption_admin = (
        f"🧾 <b>Đơn #{oid}</b>\n"
        f"📦 Sản phẩm: <b>{html.escape(order_row['product'])}</b>\n"
        f"🔢 Số lượng: <b>{order_row['quantity']}</b>\n"
        f"💰 Tổng tiền: <b>{order_row['price']:,}đ</b>\n\n"
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

    try:
        cur.execute("BEGIN IMMEDIATE")

        cur.execute("""
            SELECT id, user_id, product_code, product, price, quantity, status
            FROM orders
            WHERE id=?
        """, (oid,))
        order_row = cur.fetchone()

        if not order_row:
            conn.rollback()
            conn.close()
            await c.answer("Không tìm thấy đơn.", show_alert=True)
            return

        if order_row["status"] != "check":
            conn.rollback()
            conn.close()
            await c.answer("Đơn này đã được xử lý trước đó.", show_alert=True)
            return

        cur.execute("""
            SELECT code, name, price, stock, active, category
            FROM products
            WHERE code=?
        """, (order_row["product_code"],))
        product_row = cur.fetchone()

        if not product_row:
            conn.rollback()
            conn.close()
            await c.answer("❌ Không tìm thấy sản phẩm trong kho.", show_alert=True)
            return

        if product_row["active"] != 1 or product_row["stock"] <= 0:
            conn.rollback()
            conn.close()
            await c.answer("❌ Sản phẩm đang hết hàng. Chỉ khi admin update lại số lượng mới bán tiếp được.", show_alert=True)
            return

        if product_row["stock"] < order_row["quantity"]:
            conn.rollback()
            conn.close()
            await c.answer("❌ Không đủ tồn kho để duyệt đơn này.", show_alert=True)
            return

        stock_moi = product_row["stock"] - order_row["quantity"]
        active_moi = 1 if stock_moi > 0 else 0

        cur.execute("""
            UPDATE products
            SET stock=?, active=?
            WHERE code=?
        """, (stock_moi, active_moi, product_row["code"]))

        cur.execute("""
            UPDATE orders
            SET status='approved'
            WHERE id=?
        """, (oid,))

        conn.commit()

        uid = order_row["user_id"]
        product_name = order_row["product"]
        price = order_row["price"]
        quantity = order_row["quantity"]

    except Exception:
        conn.rollback()
        conn.close()
        await c.answer("Có lỗi khi duyệt đơn.", show_alert=True)
        return

    conn.close()

    msg_admin = (
        f"✅ Đã duyệt đơn #{oid}\n"
        f"📦 Sản phẩm: <b>{html.escape(product_name)}</b>\n"
        f"🔢 Số lượng: <b>{quantity}</b>\n"
        f"💰 Tổng tiền: <b>{price:,}đ</b>\n"
    )

    if stock_moi > 0:
        msg_admin += f"📦 Tồn kho còn lại: <b>{stock_moi}</b>\n\n"
    else:
        msg_admin += "📦 Tồn kho còn lại: <b>0</b>\n⚠️ Sản phẩm này đã hết hàng và bị khóa bán cho tới khi admin /update lại.\n\n"

    msg_admin += (
        "Để giao đúng đơn này, hãy dùng lệnh:\n"
        f"<code>/gui {oid}</code>"
    )

    await c.message.answer(msg_admin)

    msg_user = (
        f"✅ Đơn #{oid} đã được duyệt\n"
        f"📦 Sản phẩm: <b>{html.escape(product_name)}</b>\n"
        f"🔢 Số lượng: <b>{quantity}</b>\n"
        f"💰 Tổng tiền: <b>{price:,}đ</b>\n\n"
        "Admin đang chuẩn bị giao hàng cho bạn."
    )

    await bot.send_message(uid, msg_user)
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
    cur.execute("""
        SELECT user_id, product, price, quantity, status
        FROM orders
        WHERE id=?
    """, (oid,))
    row = cur.fetchone()
    conn.close()

    if not row:
        await m.answer(
            f"Không tìm thấy đơn hàng #{oid}.\n"
            f"Bot đang dùng database: <code>{html.escape(DB_NAME)}</code>"
        )
        return

    if row["status"] not in ("approved", "done"):
        await m.answer(
            "Đơn này chưa ở trạng thái được giao.\n"
            "Hãy bấm DUYỆT trước rồi mới dùng /gui."
        )
        return

    await state.set_state(AdminFlow.nhap_noi_dung)
    await state.update_data(oid=oid)

    await m.answer(
        f"📌 Đã chọn đơn #{oid}\n"
        f"📦 Sản phẩm: <b>{html.escape(row['product'])}</b>\n"
        f"🔢 Số lượng: <b>{row['quantity']}</b>\n"
        f"💰 Tổng tiền: <b>{row['price']:,}đ</b>\n\n"
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
    cur.execute("""
        SELECT user_id, product, quantity
        FROM orders
        WHERE id=?
    """, (oid,))
    row = cur.fetchone()

    if not row:
        conn.close()
        await m.answer("Không tìm thấy đơn hàng.")
        await state.clear()
        return

    uid = row["user_id"]
    product_name = row["product"]
    quantity = row["quantity"]

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
        f"📦 Sản phẩm: <b>{safe_product}</b>\n"
        f"🔢 Số lượng: <b>{quantity}</b>\n\n"
        f"📌 Nội dung nhận hàng:\n<code>{safe_text}</code>\n\n"
        "Nhấn giữ vào phần trong khung để sao chép nhanh."
    )

    await m.answer(
        f"✅ Đã giao đơn #{oid}\n"
        f"📦 Sản phẩm: <b>{safe_product}</b>\n"
        f"🔢 Số lượng: <b>{quantity}</b>"
    )

    await state.clear()


@dp.callback_query(F.data.startswith("no_"))
async def no(c: CallbackQuery):
    oid = int(c.data.split("_")[1])

    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, product, price, quantity, status
        FROM orders
        WHERE id=?
    """, (oid,))
    row = cur.fetchone()

    if not row:
        conn.close()
        await c.answer("Không tìm thấy đơn.", show_alert=True)
        return

    if row["status"] not in ("check", "pay"):
        conn.close()
        await c.answer("Đơn này đã được xử lý trước đó.", show_alert=True)
        return

    cur.execute("UPDATE orders SET status='reject' WHERE id=?", (oid,))
    conn.commit()
    conn.close()

    await bot.send_message(
        row["user_id"],
        f"❌ Đơn #{oid} đã bị từ chối\n"
        f"📦 Sản phẩm: <b>{html.escape(row['product'])}</b>\n"
        f"🔢 Số lượng: <b>{row['quantity']}</b>\n"
        f"💰 Tổng tiền: <b>{row['price']:,}đ</b>\n\n"
        f"Nếu cần hỗ trợ, vui lòng liên hệ {SUPPORT_USERNAME}"
    )

    await c.answer("Đã huỷ đơn.")


@dp.message(Command("update"))
async def update_stock_menu(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        await m.answer("Bạn không có quyền dùng lệnh này.")
        return

    products = get_all_products()

    text = "<b>Danh sách sản phẩm:</b>\n\n"
    for i, p in enumerate(products, start=1):
        trang_thai = "Đang bán" if p["active"] == 1 and p["stock"] > 0 else "Hết hàng / Đang khóa"
        text += (
            f"{i}. {html.escape(p['name'])} | "
            f"Nhóm: {html.escape(p['category'])} | "
            f"Còn: {p['stock']} | "
            f"Trạng thái: {trang_thai}\n"
        )

    text += (
        "\nNhập theo mẫu:\n"
        "<code>1 5</code>\n"
        "Nghĩa là: sản phẩm số 1 cập nhật còn 5.\n"
        "Nếu nhập 0 thì sản phẩm sẽ bị khóa bán.\n\n"
        "Muốn thoát thì nhập: <code>huy</code>"
    )

    await state.set_state(AdminFlow.update_so_luong)
    await m.answer(text)


@dp.message(AdminFlow.update_so_luong)
async def update_stock_save(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return

    text = m.text.strip() if m.text else ""

    if text.lower() == "huy":
        await state.clear()
        await m.answer("Đã huỷ cập nhật số lượng.")
        return

    parts = text.split()
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        await m.answer(
            "Sai định dạng.\n"
            "Nhập theo mẫu: <code>1 5</code>\n"
            "Nghĩa là sản phẩm số 1 còn 5."
        )
        return

    stt = int(parts[0])
    so_luong_moi = int(parts[1])

    products = get_all_products()

    if stt <= 0 or stt > len(products):
        await m.answer("Số thứ tự sản phẩm không hợp lệ.")
        return

    p = products[stt - 1]
    active_moi = 1 if so_luong_moi > 0 else 0

    conn = db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE products
        SET stock=?, active=?
        WHERE code=?
    """, (so_luong_moi, active_moi, p["code"]))
    conn.commit()
    conn.close()

    trang_thai = "Đang bán" if active_moi == 1 else "Hết hàng / Đang khóa"

    await m.answer(
        f"✅ Đã cập nhật:\n"
        f"📦 Sản phẩm: <b>{html.escape(p['name'])}</b>\n"
        f"📂 Nhóm: <b>{html.escape(p['category'])}</b>\n"
        f"📌 Số lượng mới: <b>{so_luong_moi}</b>\n"
        f"📌 Trạng thái mới: <b>{trang_thai}</b>\n\n"
        "Tiếp tục nhập theo mẫu <code>stt số_lượng</code> nếu muốn sửa thêm,\n"
        "hoặc nhập <code>huy</code> để thoát."
    )


async def main():
    init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
