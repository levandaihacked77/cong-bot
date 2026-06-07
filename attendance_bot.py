#!/usr/bin/env python3
"""
Bot Chấm Công Telegram
Dành cho nhóm công nhân ca kíp
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
)

# ========== CẤU HÌNH ==========
import os
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7567655803:AAEYCkpZtJfRmxapBbHxdb9-oaPbg3DUTeE")
DB_FILE = "chamcong.db"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== DATABASE ==========

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Bảng chấm công chính
    c.execute("""
        CREATE TABLE IF NOT EXISTS chamcong (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            ten TEXT,
            username TEXT,
            hanh_dong TEXT,
            thoi_gian TEXT,
            ngay TEXT
        )
    """)
    
    # Bảng trạng thái hiện tại của mỗi người
    c.execute("""
        CREATE TABLE IF NOT EXISTS trang_thai (
            user_id INTEGER PRIMARY KEY,
            ten TEXT,
            username TEXT,
            trang_thai TEXT,
            thoi_gian_bat_dau TEXT,
            tong_ra_ngoai INTEGER DEFAULT 0
        )
    """)
    
    conn.commit()
    conn.close()

def get_db():
    return sqlite3.connect(DB_FILE)

def log_hanh_dong(user_id, ten, username, hanh_dong):
    now = datetime.now()
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO chamcong (user_id, ten, username, hanh_dong, thoi_gian, ngay)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, ten, username, hanh_dong, now.strftime("%H:%M:%S"), now.strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()

def set_trang_thai(user_id, ten, username, trang_thai, reset_ra_ngoai=False):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    c = conn.cursor()
    
    if reset_ra_ngoai:
        c.execute("""
            INSERT INTO trang_thai (user_id, ten, username, trang_thai, thoi_gian_bat_dau, tong_ra_ngoai)
            VALUES (?, ?, ?, ?, ?, 0)
            ON CONFLICT(user_id) DO UPDATE SET
                ten=excluded.ten, username=excluded.username,
                trang_thai=excluded.trang_thai,
                thoi_gian_bat_dau=excluded.thoi_gian_bat_dau,
                tong_ra_ngoai=0
        """, (user_id, ten, username, trang_thai, now))
    else:
        c.execute("""
            INSERT INTO trang_thai (user_id, ten, username, trang_thai, thoi_gian_bat_dau)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                ten=excluded.ten, username=excluded.username,
                trang_thai=excluded.trang_thai,
                thoi_gian_bat_dau=excluded.thoi_gian_bat_dau
        """, (user_id, ten, username, trang_thai, now))
    
    conn.commit()
    conn.close()

def get_trang_thai(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM trang_thai WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row  # (user_id, ten, username, trang_thai, thoi_gian_bat_dau, tong_ra_ngoai)

def them_ra_ngoai(user_id, phut):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE trang_thai SET tong_ra_ngoai = tong_ra_ngoai + ? WHERE user_id = ?", (phut, user_id))
    conn.commit()
    conn.close()

def xoa_trang_thai(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM trang_thai WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# ========== KEYBOARD ==========

def main_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🟢 LÊN CA 上班", callback_data="len_ca"),
            InlineKeyboardButton("🔴 XUỐNG CA 下班", callback_data="xuong_ca"),
        ],
        [
            InlineKeyboardButton("🚬 HÚT THUỐC 抽烟", callback_data="hut_thuoc"),
            InlineKeyboardButton("🚽 WC 厕所", callback_data="wc"),
        ],
        [
            InlineKeyboardButton("📞 GỌI ĐIỆN 打电话", callback_data="goi_dien"),
            InlineKeyboardButton("🌙 NGHỈ CHIỀU 休休", callback_data="nghi_chieu"),
        ],
        [
            InlineKeyboardButton("🔄 TRỞ LẠI 回来", callback_data="tro_lai"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

# ========== HELPERS ==========

def format_ten(update: Update) -> str:
    user = update.effective_user
    return user.full_name or user.username or f"User_{user.id}"

def phut_tu_luc(thoi_gian_str: str) -> int:
    """Tính số phút từ thời điểm đã lưu đến bây giờ"""
    try:
        dt = datetime.strptime(thoi_gian_str, "%Y-%m-%d %H:%M:%S")
        delta = datetime.now() - dt
        return int(delta.total_seconds() / 60)
    except:
        return 0

def format_tg(phut: int) -> str:
    if phut < 60:
        return f"{phut} phút"
    h = phut // 60
    m = phut % 60
    return f"{h}h{m:02d}p"

# ========== HANDLERS ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ten = format_ten(update)
    msg = (
        f"👋 Xin chào *{ten}*!\n\n"
        "🕐 *Bot Chấm Công Ca Kíp*\n"
        "Bấm nút bên dưới để ghi nhận hành động của bạn.\n\n"
        "📌 Dùng /baocao để xem tổng hợp hôm nay\n"
        "📋 Dùng /danhsach để xem ai đang làm việc"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_keyboard())

async def chamcong_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiện menu chấm công"""
    await update.message.reply_text(
        "⏱ *Chọn hành động:*",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_id = user.id
    ten = user.full_name or user.username or f"User_{user_id}"
    username = f"@{user.username}" if user.username else ten
    action = query.data
    now = datetime.now()
    now_str = now.strftime("%H:%M %d/%m")
    
    trang_thai = get_trang_thai(user_id)
    
    # ===== LÊN CA =====
    if action == "len_ca":
        if trang_thai and trang_thai[3] not in ("xuong_ca", None):
            await query.message.reply_text(
                f"⚠️ {ten} đang trong ca rồi!\n"
                f"Trạng thái hiện tại: *{mo_ta_trang_thai(trang_thai[3])}*",
                parse_mode="Markdown"
            )
            return
        
        set_trang_thai(user_id, ten, username, "len_ca", reset_ra_ngoai=True)
        log_hanh_dong(user_id, ten, username, "LÊN CA")
        
        await query.message.reply_text(
            f"✅ *{ten}* đã LÊN CA lúc *{now_str}*\n"
            f"Chúc bạn làm việc vui vẻ! 💪",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
    
    # ===== XUỐNG CA =====
    elif action == "xuong_ca":
        if not trang_thai or trang_thai[3] == "xuong_ca":
            await query.message.reply_text(
                f"⚠️ {ten} chưa lên ca hoặc đã xuống ca rồi!",
                reply_markup=main_keyboard()
            )
            return
        
        if trang_thai[3] != "len_ca":
            await query.message.reply_text(
                f"⚠️ {ten} đang *{mo_ta_trang_thai(trang_thai[3])}*!\n"
                f"Hãy bấm *Trở Lại* trước khi xuống ca.",
                parse_mode="Markdown",
                reply_markup=main_keyboard()
            )
            return
        
        # Tính tổng giờ làm
        phut_lam = phut_tu_luc(trang_thai[4])
        phut_ra_ngoai = trang_thai[5] or 0
        phut_thuc_te = phut_lam - phut_ra_ngoai
        
        log_hanh_dong(user_id, ten, username, "XUỐNG CA")
        set_trang_thai(user_id, ten, username, "xuong_ca")
        
        await query.message.reply_text(
            f"🔴 *{ten}* đã XUỐNG CA lúc *{now_str}*\n\n"
            f"📊 *Tổng kết ca:*\n"
            f"• Tổng thời gian: {format_tg(phut_lam)}\n"
            f"• Ra ngoài: {format_tg(phut_ra_ngoai)}\n"
            f"• ⏱ Thực tế làm: *{format_tg(phut_thuc_te)}*\n\n"
            f"Nghỉ ngơi nhé! 😊",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
    
    # ===== HÚT THUỐC =====
    elif action == "hut_thuoc":
        if not check_dang_lam(trang_thai):
            await query.message.reply_text(
                f"⚠️ {ten} chưa lên ca!", reply_markup=main_keyboard()
            )
            return
        if trang_thai[3] != "len_ca":
            await query.message.reply_text(
                f"⚠️ {ten} đang *{mo_ta_trang_thai(trang_thai[3])}* rồi!",
                parse_mode="Markdown", reply_markup=main_keyboard()
            )
            return
        
        set_trang_thai(user_id, ten, username, "hut_thuoc")
        log_hanh_dong(user_id, ten, username, "HÚT THUỐC")
        
        await query.message.reply_text(
            f"🚬 *{ten}* đi hút thuốc lúc *{now_str}*\n"
            f"⏱ Nhớ bấm *Trở Lại* sau 10 phút nhé!",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
    
    # ===== WC =====
    elif action == "wc":
        if not check_dang_lam(trang_thai):
            await query.message.reply_text(
                f"⚠️ {ten} chưa lên ca!", reply_markup=main_keyboard()
            )
            return
        if trang_thai[3] != "len_ca":
            await query.message.reply_text(
                f"⚠️ {ten} đang *{mo_ta_trang_thai(trang_thai[3])}* rồi!",
                parse_mode="Markdown", reply_markup=main_keyboard()
            )
            return
        
        set_trang_thai(user_id, ten, username, "wc")
        log_hanh_dong(user_id, ten, username, "WC")
        
        await query.message.reply_text(
            f"🚽 *{ten}* đi WC lúc *{now_str}*\n"
            f"⏱ Nhớ bấm *Trở Lại* sau khi xong nhé!",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
    
    # ===== GỌI ĐIỆN =====
    elif action == "goi_dien":
        if not check_dang_lam(trang_thai):
            await query.message.reply_text(
                f"⚠️ {ten} chưa lên ca!", reply_markup=main_keyboard()
            )
            return
        if trang_thai[3] != "len_ca":
            await query.message.reply_text(
                f"⚠️ {ten} đang *{mo_ta_trang_thai(trang_thai[3])}* rồi!",
                parse_mode="Markdown", reply_markup=main_keyboard()
            )
            return
        
        set_trang_thai(user_id, ten, username, "goi_dien")
        log_hanh_dong(user_id, ten, username, "GỌI ĐIỆN")
        
        await query.message.reply_text(
            f"📞 *{ten}* đi gọi điện lúc *{now_str}*\n"
            f"⏱ Nhớ bấm *Trở Lại* sau khi xong!",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
    
    # ===== NGHỈ CHIỀU =====
    elif action == "nghi_chieu":
        if not check_dang_lam(trang_thai):
            await query.message.reply_text(
                f"⚠️ {ten} chưa lên ca!", reply_markup=main_keyboard()
            )
            return
        if trang_thai[3] != "len_ca":
            await query.message.reply_text(
                f"⚠️ {ten} đang *{mo_ta_trang_thai(trang_thai[3])}* rồi!",
                parse_mode="Markdown", reply_markup=main_keyboard()
            )
            return
        
        set_trang_thai(user_id, ten, username, "nghi_chieu")
        log_hanh_dong(user_id, ten, username, "NGHỈ CHIỀU")
        
        await query.message.reply_text(
            f"🌙 *{ten}* nghỉ chiều lúc *{now_str}*\n"
            f"📌 Nhớ vào làm lúc 18h và bấm *Trở Lại*!",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
    
    # ===== TRỞ LẠI =====
    elif action == "tro_lai":
        if not trang_thai or trang_thai[3] in ("len_ca", "xuong_ca", None):
            await query.message.reply_text(
                f"⚠️ {ten} không có gì để trở lại!",
                reply_markup=main_keyboard()
            )
            return
        
        trang_thai_cu = trang_thai[3]
        phut_di = phut_tu_luc(trang_thai[4])
        
        hanh_dong_map = {
            "hut_thuoc": "HÚT THUỐC",
            "wc": "WC",
            "goi_dien": "GỌI ĐIỆN",
            "nghi_chieu": "NGHỈ CHIỀU",
        }
        hanh_dong_key = hanh_dong_map.get(trang_thai_cu, "")
        
        them_ra_ngoai(user_id, phut_di)
        log_hanh_dong(user_id, ten, username, f"TRỞ LẠI (sau {mo_ta_trang_thai(trang_thai_cu)})")
        set_trang_thai(user_id, ten, username, "len_ca")
        
        so_lan = dem_so_lan(user_id, hanh_dong_key) if hanh_dong_key else 0
        so_lan_text = f"• Số lần hôm nay: *{so_lan} lần*\n" if so_lan > 0 else ""
        
        await query.message.reply_text(
            f"🔄 *{ten}* đã trở lại lúc *{now_str}*\n"
            f"• Vừa: {mo_ta_trang_thai(trang_thai_cu)}\n"
            f"• Thời gian vừa đi: *{format_tg(phut_di)}*\n"
            f"{so_lan_text}\n"
            f"💪 Làm việc tiếp nào!",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

def dem_so_lan(user_id, hanh_dong_key):
    ngay = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM chamcong WHERE user_id=? AND hanh_dong=? AND ngay=?", (user_id, hanh_dong_key, ngay))
    count = c.fetchone()[0]
    conn.close()
    return count

def check_dang_lam(trang_thai) -> bool:
    return trang_thai and trang_thai[3] not in ("xuong_ca", None)

def mo_ta_trang_thai(tt: str) -> str:
    ma = {
        "len_ca": "🟢 Đang làm việc",
        "xuong_ca": "🔴 Đã xuống ca",
        "hut_thuoc": "🚬 Hút thuốc",
        "wc": "🚽 Đi WC",
        "goi_dien": "📞 Gọi điện",
        "nghi_chieu": "🌙 Nghỉ chiều",
    }
    return ma.get(tt, tt)

# ========== BÁO CÁO ==========

async def bao_cao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Báo cáo tổng hợp hôm nay"""
    ngay_hom_nay = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""
        SELECT ten, hanh_dong, thoi_gian
        FROM chamcong
        WHERE ngay = ?
        ORDER BY ten, thoi_gian
    """, (ngay_hom_nay,))
    
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        await update.message.reply_text("📋 Hôm nay chưa có ai chấm công!")
        return
    
    # Nhóm theo người
    nguoi = {}
    for ten, hanh_dong, thoi_gian in rows:
        if ten not in nguoi:
            nguoi[ten] = []
        nguoi[ten].append(f"  {thoi_gian} — {hanh_dong}")
    
    msg = f"📊 *BÁO CÁO CHẤM CÔNG*\n📅 Ngày {datetime.now().strftime('%d/%m/%Y')}\n\n"
    
    for ten, logs in nguoi.items():
        msg += f"👤 *{ten}*\n"
        msg += "\n".join(logs[-8:])  # Giới hạn 8 log cuối mỗi người
        msg += "\n\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def danh_sach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xem ai đang làm việc hiện tại"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT ten, trang_thai, thoi_gian_bat_dau, tong_ra_ngoai FROM trang_thai ORDER BY ten")
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        await update.message.reply_text("📋 Chưa có ai chấm công hôm nay!")
        return
    
    msg = f"👥 *DANH SÁCH NHÂN VIÊN*\n🕐 {datetime.now().strftime('%H:%M %d/%m')}\n\n"
    
    dang_lam = []
    ra_ngoai = []
    xong_ca = []
    
    for ten, tt, tg_bat_dau, tong_ra_ngoai in rows:
        phut = phut_tu_luc(tg_bat_dau) if tg_bat_dau else 0
        if tt == "len_ca":
            dang_lam.append(f"• {ten} — {format_tg(phut - (tong_ra_ngoai or 0))}")
        elif tt == "xuong_ca":
            xong_ca.append(f"• {ten}")
        else:
            ra_ngoai.append(f"• {ten} — {mo_ta_trang_thai(tt)} ({format_tg(phut)})")
    
    if dang_lam:
        msg += "🟢 *Đang làm việc:*\n" + "\n".join(dang_lam) + "\n\n"
    if ra_ngoai:
        msg += "🟡 *Ra ngoài:*\n" + "\n".join(ra_ngoai) + "\n\n"
    if xong_ca:
        msg += "🔴 *Đã xuống ca:*\n" + "\n".join(xong_ca) + "\n\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_keyboard())

async def ca_nhan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xem thông tin ca làm của bản thân"""
    user = update.effective_user
    user_id = user.id
    ten = user.full_name or user.username or f"User_{user_id}"
    
    trang_thai = get_trang_thai(user_id)
    
    if not trang_thai:
        await update.message.reply_text(
            f"📋 {ten} chưa bắt đầu ca hôm nay!\nBấm *LÊN CA* để bắt đầu.",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
        return
    
    _, _, _, tt, tg_bat_dau, tong_ra_ngoai = trang_thai
    phut_tong = phut_tu_luc(tg_bat_dau)
    phut_thuc = phut_tong - (tong_ra_ngoai or 0)
    
    msg = (
        f"👤 *{ten}*\n"
        f"📌 Trạng thái: {mo_ta_trang_thai(tt)}\n"
        f"⏱ Tổng ca: {format_tg(phut_tong)}\n"
        f"🚶 Ra ngoài: {format_tg(tong_ra_ngoai or 0)}\n"
        f"✅ Thực tế: *{format_tg(phut_thuc)}*"
    )
    
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_keyboard())

async def thanh_vien_moi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tự động gửi menu khi có người mới vào nhóm"""
    for member in update.message.new_chat_members:
        if member.is_bot:
            # Bot vừa được thêm vào nhóm → gửi menu chào
            await update.message.reply_text(
                "👋 *Bot Chấm Công đã sẵn sàng!*\n\n"
                "Bấm nút bên dưới để chấm công:",
                parse_mode="Markdown",
                reply_markup=main_keyboard()
            )
        else:
            ten = member.full_name or member.username or f"User_{member.id}"
            await update.message.reply_text(
                f"👋 Chào *{ten}* vào nhóm!\n"
                f"Bấm *LÊN CA* khi bắt đầu làm việc nhé!",
                parse_mode="Markdown",
                reply_markup=main_keyboard()
            )

# ========== MAIN ==========

def main():
    init_db()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", chamcong_menu))
    app.add_handler(CommandHandler("baocao", bao_cao))
    app.add_handler(CommandHandler("danhsach", danh_sach))
    app.add_handler(CommandHandler("ca", ca_nhan))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, thanh_vien_moi))
    
    print("✅ Bot Chấm Công đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
