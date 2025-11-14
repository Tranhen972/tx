# File: bot.py (Cập nhật: Chỉ còn 1 game TX 30s)

import logging
import requests
import os 
from datetime import datetime
from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, Update, 
    WebAppInfo
)
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler, 
    CallbackContext, Filters 
)
from supabase import create_client, Client

# === KHỞI TẠO SUPABASE (CHO BOT) ===
try:
    BOT_TOKEN = os.environ['BOT_TOKEN']
    SUPABASE_URL = os.environ['SUPABASE_URL']
    SUPABASE_KEY = os.environ['SUPABASE_KEY']
    # === SỬA LỖI: Lấy API_URL từ Secrets ===
    API_URL = os.environ['API_URL']
    
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Bot đã kết nối thành công đến Supabase!")
except KeyError:
    raise Exception("Lỗi: BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY, hoặc API_URL chưa được cài đặt!")

# === TẢI DANH SÁCH ADMIN TỪ SUPABASE ===
def get_admin_ids():
    try:
        admin_data = supabase.table('admins').select('telegram_id').execute()
        admin_ids = [item['telegram_id'] for item in admin_data.data]
        print(f"Đã tải {len(admin_ids)} Admin IDs từ Supabase: {admin_ids}")
        return admin_ids
    except Exception as e:
        print(f"Lỗi khi tải Admin IDs: {e}")
        return []

ADMIN_ID_INTS = get_admin_ids() 
# ======================================

REFERRAL_BONUS = 5000 

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# === HÀM FORMAT THỜI GIAN (Giữ nguyên) ===
def format_time(iso_timestamp):
    if not iso_timestamp: return "Không rõ"
    try:
        dt = datetime.fromisoformat(iso_timestamp); return dt.strftime("%d-%m %H:%M:%S")
    except Exception:
        try:
            dt = datetime.strptime(iso_timestamp, "%Y-%m-%dT%H:%M:%S"); return dt.strftime("%d-%m %H:%M:%S")
        except Exception: return iso_timestamp.split('T')[0] 
# ================================

# === BÀN PHÍM TÀI KHOẢN (Giữ nguyên) ===
def account_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 Lịch sử cược", callback_data='acc_bet_history'), InlineKeyboardButton("💰 Lịch sử nạp", callback_data='acc_deposit_history')],
        [InlineKeyboardButton("💸 Lịch sử rút", callback_data='acc_withdraw_history'), InlineKeyboardButton("🔙 Quay lại", callback_data='menu_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

# === Menu chính (Giữ nguyên) ===
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎲 Chơi Game", callback_data='menu_games'), InlineKeyboardButton("👤 Tài Khoản", callback_data='menu_account')],
        [InlineKeyboardButton("💰 Nạp Tiền", callback_data='menu_deposit'), InlineKeyboardButton("💸 Rút Tiền", callback_data='menu_withdraw')],
        [InlineKeyboardButton("👥 Giới Thiệu", callback_data='menu_refer'), InlineKeyboardButton("🎁 Giftcode", callback_data='menu_giftcode')],
        [InlineKeyboardButton("🌹 Bonus", callback_data='menu_bonus'), InlineKeyboardButton("💬 Hỗ trợ", callback_data='menu_support')],
    ]
    return InlineKeyboardMarkup(keyboard)

# === Menu game (CẬP NHẬT: Chỉ còn 1 game) ===
def game_menu_keyboard():
    taixiu_url = API_URL # Link / là game Tài Xỉu 30s
    
    keyboard = [[
        InlineKeyboardButton("🎲 XÚC XẮC 30 GIÂY (Mở App)", web_app=WebAppInfo(url=taixiu_url)),
    ], [
        InlineKeyboardButton("🔙 Quay lại", callback_data='menu_main'),
    ]]
    return InlineKeyboardMarkup(keyboard)
# ========================================

# === CÁC LỆNH (Giữ nguyên) ===
def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user; referred_by_id = context.args[0] if context.args else None
    try:
        user_data = {"telegram_id": user.id, "username": user.username, "first_name": user.first_name, "referred_by": referred_by_id}
        requests.post(f"{API_URL}/register", json=user_data) 
    except requests.ConnectionError: logger.error("Lỗi: Không thể kết nối API để đăng ký.")
    update.message.reply_html(f"Chào mừng {user.mention_html()}!", reply_markup=main_menu_keyboard())
def admin_panel_command(update: Update, context: CallbackContext) -> None:
    admin_url = f"{API_URL}/admin_panel" 
    keyboard = [[InlineKeyboardButton("Mở Bảng Admin 👑", web_app=WebAppInfo(url=admin_url))]]
    update.message.reply_text("Đây là link Bảng Điều khiển Admin:", reply_markup=InlineKeyboardMarkup(keyboard))
def giftcode_handler(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    if not context.args: update.message.reply_text("Sử dụng: /giftcode [MÃ_CODE]"); return
    code = context.args[0]
    try:
        response = requests.post(f"{API_URL}/redeem_giftcode", json={"telegram_id": user.id, "code": code})
        data = response.json()
        if response.status_code == 200: update.message.reply_text(f"✅ {data['message']}")
        else: update.message.reply_text(f"❌ {data['error']}")
    except requests.ConnectionError: update.message.reply_text("Lỗi: Không thể kết nối máy chủ.")
def withdraw_handler(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    if len(context.args) < 2:
        update.message.reply_text("Sử dụng: /rut [SỐ TIỀN] [BANK]\nVí dụ: /rut 50000 MB 0123456789")
        return
    try:
        amount = int(context.args[0]); bank_info = " ".join(context.args[1:]) 
        response = requests.post(f"{API_URL}/user/request_withdrawal", json={"telegram_id": user.id, "amount": amount, "bank_info": bank_info})
        data = response.json()
        if response.status_code == 200: update.message.reply_text(f"✅ {data['message']}")
        else: update.message.reply_text(f"❌ {data['error']}")
    except ValueError: update.message.reply_text("❌ Lỗi: Số tiền phải là một con số.")
    except requests.ConnectionError: update.message.reply_text("❌ Lỗi: Không thể kết nối máy chủ.")

# === HÀM XỬ LÝ NÚT (Giữ nguyên) ===
def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query; query.answer()
    telegram_id = query.from_user.id; data = query.data
    try:
        if data == 'menu_main':
            query.edit_message_text("Đây là menu chính:", reply_markup=main_menu_keyboard())
        elif data == 'menu_account':
            response = requests.get(f"{API_URL}/user/{telegram_id}/balance")
            if response.status_code == 200:
                user_data = response.json()
                text = (f"<b>👤 Tài khoản của bạn:</b>\n"
                        f"Tên: {user_data.get('username', 'N/A')}\n" 
                        f"Số dư: <b>{user_data.get('balance', 0):,.0f} đ</b>")
                query.edit_message_text(text, parse_mode='HTML', reply_markup=account_menu_keyboard())
            else: query.edit_message_text("Lỗi: Không tìm thấy tài khoản.", reply_markup=main_menu_keyboard())
        elif data == 'acc_bet_history':
            response = requests.get(f"{API_URL}/user/history/bets/{telegram_id}"); history = response.json()
            text = "<b>📊 5 Lịch sử cược gần nhất:</b>\n\n";
            if not history: text += "Bạn chưa cược phiên nào."
            else:
                for log in history: 
                    change = log.get('change', 0); icon = "🟢" if change > 0 else "🔴"
                    text += f"{icon} <b>{log.get('choice', '?')}</b> (KQ: {log.get('result', '?')})\n"
                    text += f"   Biến động: {change:,.0f} đ\n   <pre>{format_time(log.get('created_at'))}</pre>\n"
            query.edit_message_text(text, parse_mode='HTML', reply_markup=account_menu_keyboard())
        elif data == 'acc_deposit_history':
            response = requests.get(f"{API_URL}/user/history/deposits/{telegram_id}"); history = response.json()
            text = "<b>💰 5 Lịch sử nạp gần nhất:</b>\n\n";
            if not history: text += "Bạn chưa có lịch sử nạp tiền."
            else:
                for log in history: text += f"🟢 <b>+{log.get('amount', 0):,.0f} đ</b>\n   <pre>{format_time(log.get('created_at'))}</pre>\n"
            query.edit_message_text(text, parse_mode='HTML', reply_markup=account_menu_keyboard())
        elif data == 'acc_withdraw_history':
            response = requests.get(f"{API_URL}/user/history/withdrawals/{telegram_id}"); history = response.json()
            text = "<b>💸 5 Lịch sử rút gần nhất:</b>\n\n";
            if not history: text += "Bạn chưa có lịch sử rút tiền."
            else:
                for req in history: 
                    status = req.get('status', 'N/A')
                    if status == 'approved': icon = "✅"
                    elif status == 'denied': icon = "❌"
                    else: icon = "⏳" 
                    text += f"{icon} <b>{req.get('amount', 0):,.0f} đ</b> (Trạng thái: {status})\n"
                    text += f"   Bank: {req.get('bank_info', '?')}\n   <pre>{format_time(req.get('created_at'))}</pre>\n"
            query.edit_message_text(text, parse_mode='HTML', reply_markup=account_menu_keyboard())
        elif data == 'menu_games':
            query.edit_message_text("Hãy chọn game mà muốn chơi 👇👇", reply_markup=game_menu_keyboard())
        elif data == 'menu_deposit':
            query.edit_message_text(f"💰 <b>Nạp Tiền</b> 💰\nNội dung: <code>NAP {telegram_id}</code>", parse_mode='HTML', reply_markup=main_menu_keyboard())
        elif data == 'menu_withdraw':
            query.edit_message_text("💸 <b>Rút Tiền</b> 💸\nSử dụng lệnh: <code>/rut [SỐ TIỀN] [BANK]</code>", parse_mode='HTML', reply_markup=main_menu_keyboard())
        elif data == 'menu_bonus':
            query.edit_message_text("🌹 <b>Bonus</b> 🌹\nChưa có chương trình bonus nào.", parse_mode='HTML', reply_markup=main_menu_keyboard())
        elif data == 'menu_support':
            query.edit_message_text("💬 <b>Hỗ trợ</b> 💬\nLiên hệ Admin: @ten_admin_cua_ban", parse_mode='HTML', reply_markup=main_menu_keyboard())
        elif data == 'menu_refer':
            bot_username = context.bot.username; referral_link = f"httpss://t.me/{bot_username}?start={telegram_id}"; response = requests.get(f"{API_URL}/user/referral_info/{telegram_id}"); count = response.json().get('referral_count', 0)
            text = (f"<b>👥 Giới Thiệu Bạn Bè</b> 👥\n\n"
                    f"Mời bạn bè và nhận <b>{REFERRAL_BONUS:,.0f} đ</b> cho mỗi lượt!\n\n"
                    f"<b>Link của bạn:</b> <code>{referral_link}</code>\n"
                    f"<b>Số người đã mời:</b> {count} người")
            query.edit_message_text(text, parse_mode='HTML', reply_markup=main_menu_keyboard())
        elif data == 'menu_giftcode':
            text = ("🎁 <b>Giftcode</b> 🎁\n\nNhập code bằng lệnh:\n<code>/giftcode MÃ_CỦA_BẠN</code>")
            query.edit_message_text(text, parse_mode='HTML', reply_markup=main_menu_keyboard())
    except requests.ConnectionError:
        try: query.edit_message_text("❌ Lỗi: Không thể kết nối đến máy chủ API.", reply_markup=main_menu_keyboard())
        except Exception: pass
    except Exception as e:
        logger.error(f"Lỗi button_handler: {e}")
        try: query.edit_message_text("❌ Đã có lỗi xảy ra.", reply_markup=main_menu_keyboard())
        except Exception: pass

# === HÀM MAIN ===
def main() -> None:
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher
    
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("admin", admin_panel_command, filters=Filters.user(user_id=ADMIN_ID_INTS)))
    dispatcher.add_handler(CommandHandler("giftcode", giftcode_handler))
    dispatcher.add_handler(CommandHandler("rut", withdraw_handler))
    dispatcher.add_handler(CallbackQueryHandler(button_handler))
    
    # BẮT ĐẦU POLLING (Chạy 24/7)
    updater.start_polling()
    logger.info(f"Bot đã khởi động (Kết nối Supabase)...")
    updater.idle()
if __name__ == '__main__':
    main()
