#!/usr/bin/env python3
"""
Xiao Mi Bot - Bot Chấm Công Telegram
Dành cho nhóm công nhân ca kíp
"""

import sqlite3
import logging
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
    MessageHandler, filters
)

# ========== CẤU HÌNH ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7567655803:AAEYCkpZtJfRmxapBbHxdb9-oaPbg3DUTeE")
DB_FILE = "chamcong.db"
MANAGER_ID = 7994864197  # ID quản lý nhận báo cáo 21h
GIO_LEN_CA = 10    # Giờ lên ca chuẩn
GIO_XUONG_CA = 22  # Giờ xuống ca chuẩn

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== DATABASE ==========

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
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
    c.execute("""
        CREATE TABLE IF NOT EXISTS ten_rieng (
            user_id INTEGER PRIMARY KEY,
            ten_hien_thi TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_db():
    return sqlite3.connect(DB_FILE)

def get_ten_hien_thi(user_id, ten_mac_dinh):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT ten_hien_thi FROM ten_rieng WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else ten_mac_dinh

def set_ten_hien_thi(user_id, ten):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO ten_rieng (user_id, ten_hien_thi) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET ten_hien_thi=excluded.ten_hien_thi
    """, (user_id, ten))
    conn.commit()
    conn.close()

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
    return row

def them_ra_ngoai(user_id, phut):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE trang_thai SET tong_ra_ngoai = tong_ra_ngoai + ? WHERE user_id = ?", (phut, user_id))
    conn.commit()
    conn.close()

def dem_so_lan(user_id, hanh_dong_key):
    ngay = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM chamcong WHERE user_id=? AND hanh_dong=? AND ngay=?", (user_id, hanh_dong_key, ngay))
    count = c.fetchone()[0]
    conn.close()
    return count

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
            InlineKeyboardButton("🍚 ĂN CƠM 吃饭", callback_data="an_com"),
        ],
        [
            InlineKeyboardButton("🔄 TRỞ LẠI 回来", callback_data="tro_lai"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

# ========== HELPERS ==========

def phut_tu_luc(thoi_gian_str):
    try:
        dt = datetime.strptime(thoi_gian_str, "%Y-%m-%d %H:%M:%S")
        delta = datetime.now() - dt
        return int(delta.total_seconds() / 60)
    except:
        return 0

def format_tg(phut):
    if phut < 60:
        return f"{phut} phút"
    h = phut // 60
    m = phut % 60
    return f"{h}h{m:02d}p"

def mo_ta_trang_thai(tt):
    ma = {
        "len_ca": "🟢 Đang làm việc",
        "xuong_ca": "🔴 Đã xuống ca",
        "hut_thuoc": "🚬 Hút thuốc",
        "wc": "🚽 Đi WC",
        "goi_dien": "📞 Gọi điện",
        "an_com": "🍚 Ăn cơm",
    }
    return ma.get(tt, tt)

def check_dang_lam(trang_thai):
    return trang_thai and trang_thai[3] not in ("xuong_ca", None)

# ========== HANDLERS ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ten = get_ten_hien_thi(user.id, user.full_name or user.username or f"User_{user.id}")
    msg = (
        f"👋 Xin chào *{ten}*!\n\n"
        "🕐 *Xiao Mi Bot - Chấm Công Ca Kíp*\n"
        "Bấm nút bên dưới để ghi nhận hành động.\n\n"
        "📌 /baocao — Xem tổng hợp hôm nay\n"
        "📋 /danhsach — Xem ai đang làm việc\n"
        "👤 /tenme [tên] — Đặt tên hiển thị\n"
        "⚙️ /setca HH MM — Set giờ ca chuẩn"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_keyboard())

async def chamcong_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⏱ *Chọn hành động:*",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

async def ten_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Đặt tên hiển thị riêng"""
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(
            "❌ Dùng: `/tenme Tên của bạn`\nVí dụ: `/tenme Anh Tèo`",
            parse_mode="Markdown"
        )
        return
    ten_moi = " ".join(context.args)
    set_ten_hien_thi(user.id, ten_moi)
    await update.message.reply_text(
        f"✅ Đã đặt tên hiển thị: *{ten_moi}*",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

async def set_ca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set giờ lên ca và xuống ca chuẩn"""
    global GIO_LEN_CA, GIO_XUONG_CA
    if len(context.args) != 2:
        await update.message.reply_text(
            "❌ Dùng: `/setca 10 22`\n(giờ lên ca và xuống ca)",
            parse_mode="Markdown"
        )
        return
    try:
        GIO_LEN_CA = int(context.args[0])
        GIO_XUONG_CA = int(context.args[1])
        await update.message.reply_text(
            f"✅ Đã set ca: *{GIO_LEN_CA}h — {GIO_XUONG_CA}h*",
            parse_mode="Markdown"
        )
    except:
        await update.message.reply_text("❌ Giờ không hợp lệ! Ví dụ: `/setca 10 22`", parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_id = user.id
    ten_mac_dinh = user.full_name or user.username or f"User_{user_id}"
    ten = get_ten_hien_thi(user_id, ten_mac_dinh)
    username = f"@{user.username}" if user.username else ten
    action = query.data
    now = datetime.now()
    now_str = now.strftime("%H:%M %d/%m")

    trang_thai = get_trang_thai(user_id)

    # ===== LÊN CA =====
    if action == "len_ca":
        if trang_thai and trang_thai[3] not in ("xuong_ca", None):
            await query.message.reply_text(
                f"⚠️ {ten} đang trong ca rồi!\nTrạng thái: *{mo_ta_trang_thai(trang_thai[3])}*",
                parse_mode="Markdown"
            )
            return
        set_trang_thai(user_id, ten, username, "len_ca", reset_ra_ngoai=True)
        log_hanh_dong(user_id, ten, username, "LÊN CA")
        tre = now.hour - GIO_LEN_CA
        tre_text = f"\n⚠️ Trễ *{tre} tiếng*!" if tre > 0 else ""
        await query.message.reply_text(
            f"✅ *{ten}* đã LÊN CA lúc *{now_str}*{tre_text}\nChúc bạn làm việc vui vẻ! 💪",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

    # ===== XUỐNG CA =====
    elif action == "xuong_ca":
        if not trang_thai or trang_thai[3] == "xuong_ca":
            await query.message.reply_text(f"⚠️ {ten} chưa lên ca hoặc đã xuống ca rồi!", reply_markup=main_keyboard())
            return
        if trang_thai[3] != "len_ca":
            await query.message.reply_text(
                f"⚠️ {ten} đang *{mo_ta_trang_thai(trang_thai[3])}*!\nHãy bấm *Trở Lại* trước.",
                parse_mode="Markdown", reply_markup=main_keyboard()
            )
            return
        phut_lam = phut_tu_luc(trang_thai[4])
        phut_ra_ngoai = trang_thai[5] or 0
        phut_thuc_te = phut_lam - phut_ra_ngoai
        log_hanh_dong(user_id, ten, username, "XUỐNG CA")
        set_trang_thai(user_id, ten, username, "xuong_ca")
        som = GIO_XUONG_CA - now.hour
        som_text = f"\n⚠️ Về sớm *{som} tiếng*!" if now.hour < GIO_XUONG_CA else ""
        await query.message.reply_text(
            f"🔴 *{ten}* đã XUỐNG CA lúc *{now_str}*{som_text}\n\n"
            f"📊 *Tổng kết ca:*\n"
            f"• Tổng thời gian: {format_tg(phut_lam)}\n"
            f"• Ra ngoài: {format_tg(phut_ra_ngoai)}\n"
            f"• ⏱ Thực tế làm: *{format_tg(phut_thuc_te)}*\n\nNghỉ ngơi nhé! 😊",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

    # ===== CÁC TRẠNG THÁI RA NGOÀI =====
    elif action in ("hut_thuoc", "wc", "goi_dien", "an_com"):
        if not check_dang_lam(trang_thai):
            await query.message.reply_text(f"⚠️ {ten} chưa lên ca!", reply_markup=main_keyboard())
            return
        if trang_thai[3] != "len_ca":
            await query.message.reply_text(
                f"⚠️ {ten} đang *{mo_ta_trang_thai(trang_thai[3])}* rồi!",
                parse_mode="Markdown", reply_markup=main_keyboard()
            )
            return
        ten_hd = mo_ta_trang_thai(action)
        nhac = {
            "hut_thuoc": "⏱ Nhớ bấm *Trở Lại* sau 10 phút!",
            "wc": "⏱ Nhớ bấm *Trở Lại* sau khi xong!",
            "goi_dien": "⏱ Nhớ bấm *Trở Lại* sau khi xong!",
            "an_com": "📌 Nhớ bấm *Trở Lại* khi vào làm lại!",
        }
        set_trang_thai(user_id, ten, username, action)
        hanh_dong_log = {"hut_thuoc": "HÚT THUỐC", "wc": "WC", "goi_dien": "GỌI ĐIỆN", "an_com": "ĂN CƠM"}
        log_hanh_dong(user_id, ten, username, hanh_dong_log[action])
        await query.message.reply_text(
            f"{ten_hd.split()[0]} *{ten}* {ten_hd[2:].lower()} lúc *{now_str}*\n{nhac[action]}",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

    # ===== TRỞ LẠI =====
    elif action == "tro_lai":
        if not trang_thai or trang_thai[3] in ("len_ca", "xuong_ca", None):
            await query.message.reply_text(f"⚠️ {ten} không có gì để trở lại!", reply_markup=main_keyboard())
            return
        trang_thai_cu = trang_thai[3]
        phut_di = phut_tu_luc(trang_thai[4])
        hanh_dong_map = {
            "hut_thuoc": "HÚT THUỐC",
            "wc": "WC",
            "goi_dien": "GỌI ĐIỆN",
            "an_com": "ĂN CƠM",
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

# ========== BÁO CÁO ==========

async def bao_cao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ngay_hom_nay = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT ten, hanh_dong, thoi_gian FROM chamcong
        WHERE ngay = ? ORDER BY ten, thoi_gian
    """, (ngay_hom_nay,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("📋 Hôm nay chưa có ai chấm công!")
        return
    nguoi = {}
    for ten, hanh_dong, thoi_gian in rows:
        if ten not in nguoi:
            nguoi[ten] = []
        nguoi[ten].append(f"  {thoi_gian} — {hanh_dong}")
    msg = f"📊 *BÁO CÁO CHẤM CÔNG*\n📅 {datetime.now().strftime('%d/%m/%Y')}\n\n"
    for ten, logs in nguoi.items():
        msg += f"👤 *{ten}*\n" + "\n".join(logs[-8:]) + "\n\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def danh_sach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, ten, trang_thai, thoi_gian_bat_dau, tong_ra_ngoai FROM trang_thai ORDER BY ten")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("📋 Chưa có ai chấm công hôm nay!")
        return
    msg = f"👥 *DANH SÁCH NHÂN VIÊN*\n🕐 {datetime.now().strftime('%H:%M %d/%m')}\n\n"
    dang_lam, ra_ngoai, xong_ca = [], [], []
    for uid, ten, tt, tg_bat_dau, tong_ra_ngoai in rows:
        ten_hd = get_ten_hien_thi(uid, ten)
        phut = phut_tu_luc(tg_bat_dau) if tg_bat_dau else 0
        if tt == "len_ca":
            dang_lam.append(f"• {ten_hd} — {format_tg(phut - (tong_ra_ngoai or 0))}")
        elif tt == "xuong_ca":
            xong_ca.append(f"• {ten_hd}")
        else:
            ra_ngoai.append(f"• {ten_hd} — {mo_ta_trang_thai(tt)} ({format_tg(phut)})")
    if dang_lam:
        msg += "🟢 *Đang làm việc:*\n" + "\n".join(dang_lam) + "\n\n"
    if ra_ngoai:
        msg += "🟡 *Ra ngoài:*\n" + "\n".join(ra_ngoai) + "\n\n"
    if xong_ca:
        msg += "🔴 *Đã xuống ca:*\n" + "\n".join(xong_ca) + "\n\n"
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_keyboard())

async def ca_nhan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ten = get_ten_hien_thi(user.id, user.full_name or user.username or f"User_{user.id}")
    trang_thai = get_trang_thai(user.id)
    if not trang_thai:
        await update.message.reply_text(
            f"📋 {ten} chưa bắt đầu ca hôm nay!\nBấm *LÊN CA* để bắt đầu.",
            parse_mode="Markdown", reply_markup=main_keyboard()
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
    for member in update.message.new_chat_members:
        if member.is_bot:
            await update.message.reply_text(
                "👋 *Xiao Mi Bot đã sẵn sàng!*\n\nBấm nút bên dưới để chấm công:",
                parse_mode="Markdown", reply_markup=main_keyboard()
            )
        else:
            ten = member.full_name or member.username or f"User_{member.id}"
            await update.message.reply_text(
                f"👋 Chào *{ten}* vào nhóm!\nBấm *LÊN CA* khi bắt đầu làm việc nhé!",
                parse_mode="Markdown", reply_markup=main_keyboard()
            )

# ========== BÁO CÁO TỰ ĐỘNG 21H ==========

async def bao_cao_tu_dong(context):
    """Gửi báo cáo tổng kết cho quản lý lúc 21h"""
    ngay = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    c = conn.cursor()

    # Lấy tất cả nhân viên đã chấm công hôm nay
    c.execute("""
        SELECT DISTINCT user_id, ten FROM chamcong WHERE ngay = ?
    """, (ngay,))
    nhan_vien = c.fetchall()

    if not nhan_vien:
        await context.bot.send_message(
            chat_id=MANAGER_ID,
            text="📋 Hôm nay không có ai chấm công!"
        )
        conn.close()
        return

    msg = f"📊 *BÁO CÁO TỔNG KẾT CA*\n📅 {datetime.now().strftime('%d/%m/%Y')} — 21:00\n"
    msg += f"⏰ Ca chuẩn: {GIO_LEN_CA}h — {GIO_XUONG_CA}h\n\n"

    di_tre = []
    ve_som = []
    chua_xuong = []

    for uid, ten_db in nhan_vien:
        ten = get_ten_hien_thi(uid, ten_db)

        # Lấy thời gian lên ca
        c.execute("""
            SELECT thoi_gian FROM chamcong
            WHERE user_id=? AND hanh_dong='LÊN CA' AND ngay=?
            ORDER BY thoi_gian LIMIT 1
        """, (uid, ngay))
        len_ca_row = c.fetchone()

        # Lấy thời gian xuống ca
        c.execute("""
            SELECT thoi_gian FROM chamcong
            WHERE user_id=? AND hanh_dong='XUỐNG CA' AND ngay=?
            ORDER BY thoi_gian DESC LIMIT 1
        """, (uid, ngay))
        xuong_ca_row = c.fetchone()

        # Tổng ra ngoài
        tt = get_trang_thai(uid)
        tong_ra_ngoai = tt[5] if tt else 0

        len_ca_str = len_ca_row[0] if len_ca_row else "?"
        xuong_ca_str = xuong_ca_row[0] if xuong_ca_row else "Chưa xuống"

        # Kiểm tra trễ/sớm
        if len_ca_row:
            h = int(len_ca_row[0].split(":")[0])
            if h > GIO_LEN_CA:
                di_tre.append(f"  • {ten}: trễ {h - GIO_LEN_CA}h")

        if xuong_ca_row:
            h = int(xuong_ca_row[0].split(":")[0])
            if h < GIO_XUONG_CA:
                ve_som.append(f"  • {ten}: về sớm {GIO_XUONG_CA - h}h")
        else:
            chua_xuong.append(f"  • {ten}")

        msg += (
            f"👤 *{ten}*\n"
            f"  🟢 Lên: {len_ca_str}  🔴 Xuống: {xuong_ca_str}\n"
            f"  🚶 Ra ngoài: {format_tg(tong_ra_ngoai or 0)}\n\n"
        )

    if di_tre:
        msg += "⚠️ *Đi trễ:*\n" + "\n".join(di_tre) + "\n\n"
    if ve_som:
        msg += "⚠️ *Về sớm:*\n" + "\n".join(ve_som) + "\n\n"
    if chua_xuong:
        msg += "❓ *Chưa xuống ca:*\n" + "\n".join(chua_xuong) + "\n\n"

    conn.close()

    await context.bot.send_message(
        chat_id=MANAGER_ID,
        text=msg,
        parse_mode="Markdown"
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
    app.add_handler(CommandHandler("tenme", ten_me))
    app.add_handler(CommandHandler("setca", set_ca))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, thanh_vien_moi))

    # Job gửi báo cáo 21h mỗi ngày (UTC+7 = 14h UTC)
    app.job_queue.run_daily(
        bao_cao_tu_dong,
        time=datetime.strptime("14:00:00", "%H:%M:%S").time(),
        name="baocao_21h"
    )

    print("✅ Xiao Mi Bot đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()
