# File: api.py (PHIÊN BẢN CUỐI - TX 30 GIÂY - ĐÃ FIX LỖI)

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import random
import logging
import os
import time
import requests 
from supabase import create_client, Client 
from datetime import datetime 
import threading 

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
CORS(app) 

# === KHỞI TẠO SUPABASE ===
try:
    BOT_TOKEN = os.environ['BOT_TOKEN']
    SUPABASE_URL = os.environ['SUPABASE_URL']
    SUPABASE_KEY = os.environ['SUPABASE_KEY']
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Đã kết nối thành công đến Supabase!")
except KeyError:
    print("Lỗi: SUPABASE_URL, SUPABASE_KEY hoặc BOT_TOKEN chưa được cài đặt trong Replit Secrets!")
    exit()
# ==========================

# === HÀM GỬI TIN NHẮN (Đã sửa lỗi) ===
def send_telegram_message(user_id, message_text):
    if not BOT_TOKEN: return False
    url = f"https{"://"}api.telegram.org/bot{BOT_TOKEN}/sendMessage" 
    payload = {'chat_id': user_id, 'text': message_text, 'parse_mode': 'HTML'}
    try:
        requests.post(url, json=payload, timeout=2); return True
    except Exception: return False
# ==================================

# === CÁC ROUTE GIAO DIỆN ===
@app.route('/')
def serve_index(): return send_from_directory('.', 'index.html') # Game Tài Xỉu 30s
@app.route('/admin_panel')
def serve_admin_panel(): return send_from_directory('.', 'admin.html')
# ========================================

# === HÀM KIỂM TRA ADMIN/BAN ===
def check_is_admin(admin_id_str):
    try:
        admin_id = int(admin_id_str)
        admin = supabase.table('admins').select('telegram_id').eq('telegram_id', admin_id).execute()
        return bool(admin.data)
    except Exception: return False
def check_is_banned(user_id_str):
    try:
        user = supabase.table('users').select('is_banned').eq('telegram_id', int(user_id_str)).single().execute()
        return user.data.get('is_banned', False) if user.data else False
    except Exception: return False
# ==============================
    
# === HÀM CHUNG: XỬ LÝ CƯỢC VÀ LƯU LỊCH SỬ ===
def process_game_bet(user_id_str, change_amount, log_choice_text, result_text, username_in='N/A'):
    try:
        user_id = int(user_id_str)
        update_res = supabase.rpc('mod_balance', {
            'user_id_in': user_id, 
            'amount_in': int(change_amount)
        }).execute()
        
        if not hasattr(update_res, 'data') or update_res.data is None:
             print(f"Lỗi khi gọi RPC mod_balance cho user {user_id}.")
             return None 
             
        new_balance = update_res.data
        if username_in == 'N/A':
             try:
                user = supabase.table('users').select('username').eq('telegram_id', user_id).single().execute()
                username_in = user.data['username'] if user.data else 'N/A'
             except Exception: pass

        supabase.table('bet_history').insert({
            "user_id": user_id, "username": username_in,
            "choice": log_choice_text, "result": result_text,
            "change": int(change_amount), "created_at": datetime.now().isoformat() 
        }).execute()
        return new_balance
    except Exception as e:
        print(f"Lỗi nghiêm trọng trong process_game_bet: {e}")
        return None
# ==========================================

# === API ĐĂNG KÝ (ĐÃ SỬA LỖI 'on_conflict') ===
@app.route('/register', methods=['POST'])
def register_user():
    data = request.json; user_id = int(data.get('telegram_id')); username = data.get('username', data.get('first_name', 'User')); referred_by_id = data.get('referred_by')
    try:
        user_to_insert = {"telegram_id": user_id, "username": username}
        if referred_by_id:
            try:
                ref_user = supabase.table('users').select('telegram_id').eq('telegram_id', int(referred_by_id)).execute()
                if ref_user.data: user_to_insert['referred_by'] = int(referred_by_id)
            except Exception: pass 
        
        insert_response = supabase.table('users').upsert(user_to_insert, on_conflict='telegram_id', ignore_duplicates=True).execute()

        if not insert_response.data:
             return jsonify({"message": "User exists"}), 200
        if referred_by_id and user_to_insert.get('referred_by'):
            supabase.rpc('mod_balance', {'user_id_in': int(referred_by_id), 'amount_in': 5000}).execute()
        return jsonify({"message": "User registered"}), 201
    except Exception as e:
        print(f"LỖI /register: {e}")
        return jsonify({"error": f"Lỗi Supabase: {e}"}), 500

# === API LẤY SỐ DƯ ===
@app.route('/user/<int:telegram_id>/balance', methods=['GET'])
def get_user_balance(telegram_id):
    try:
        user = supabase.table('users').select('*').eq('telegram_id', telegram_id).single().execute()
        if user.data: return jsonify(user.data)
        else: return jsonify({"error": "User not found."}), 404
    except Exception:
        return jsonify({"error": "User not found."}), 404 

# === CÁC API USER CŨ (Giữ nguyên, ẩn cho gọn) ===
@app.route('/user/referral_info/<int:telegram_id>', methods=['GET'])
def get_referral_info(telegram_id):
    try:
        count_data = supabase.table('users').select('telegram_id', count='exact').eq('referred_by', telegram_id).execute()
        return jsonify({"referral_count": count_data.count})
    except Exception as e: return jsonify({"error": str(e)}), 500
@app.route('/redeem_giftcode', methods=['POST'])
def redeem_giftcode():
    data = request.json; user_id_str = str(data.get('telegram_id')); code = str(data.get('code')).upper()
    if check_is_banned(user_id_str): return jsonify({"error": "Tài khoản của bạn đã bị khóa."}), 403
    try:
        code_res = supabase.table('giftcodes').select('*').eq('code', code).single().execute()
        if not code_res.data: return jsonify({"error": "Giftcode không tồn tại."}), 400
        code_info = code_res.data; used_by_list = code_info.get('used_by', [])
        if len(used_by_list) >= code_info['limit_count']: return jsonify({"error": "Code này đã hết lượt sử dụng."}), 400
        if user_id_str in [str(uid) for uid in used_by_list]: return jsonify({"error": "Bạn đã sử dụng code này rồi."}), 400
        amount = code_info['amount']; new_balance = supabase.rpc('mod_balance', {'user_id_in': int(user_id_str), 'amount_in': amount}).execute().data
        used_by_list.append(int(user_id_str)); supabase.table('giftcodes').update({'used_by': used_by_list}).eq('code', code).execute()
        return jsonify({"message": f"Thành công! Bạn đã nhận {amount:,.0f} đ.", "new_balance": new_balance})
    except Exception as e: return jsonify({"error": f"Lỗi Supabase: {e}"}), 500
@app.route('/user/request_withdrawal', methods=['POST'])
def request_withdrawal():
    data = request.json; user_id_str = str(data.get('telegram_id')); bank_info = data.get('bank_info')
    if check_is_banned(user_id_str): return jsonify({"error": "Tài khoản của bạn đã bị khóa."}), 403
    try: amount = int(data.get('amount'))
    except Exception: return jsonify({"error": "Số tiền không hợp lệ."}), 400
    if not bank_info or amount <= 0: return jsonify({"error": "Vui lòng nhập số tiền và thông tin bank."}), 400
    try:
        user_data = supabase.table('users').select('balance, username').eq('telegram_id', int(user_id_str)).single().execute()
        if user_data.data['balance'] < amount: return jsonify({"error": "Số dư không đủ."}), 400
        supabase.table('withdrawals').insert({"user_id": int(user_id_str), "username": user_data.data['username'], "amount": amount, "bank_info": bank_info, "status": "pending"}).execute()
        return jsonify({"message": f"Yêu cầu rút {amount:,.0f} đ đã được gửi."})
    except Exception as e: return jsonify({"error": f"Lỗi Supabase: {e}"}), 500
@app.route('/user/history/bets/<int:telegram_id>', methods=['GET'])
def get_bet_history(telegram_id): 
    data = supabase.table('tx_bets').select('choice, amount, payout, created_at, session_id').eq('user_id', telegram_id).order('created_at', desc=True).limit(5).execute()
    history = []
    for bet in data.data:
        change = bet['payout'] - bet['amount'] if bet['payout'] > 0 else -bet['amount']
        history.append({"choice": f"#{bet['session_id']} ({bet['choice'].upper()})", "result": "Thắng" if bet['payout'] > 0 else "Thua", "change": change, "created_at": bet['created_at']})
    return jsonify(history) 
@app.route('/user/history/deposits/<int:telegram_id>', methods=['GET'])
def get_deposit_history(telegram_id): 
    data = supabase.table('deposit_history').select('*').eq('user_id', telegram_id).order('created_at', desc=True).limit(5).execute()
    return jsonify(data.data)
@app.route('/user/history/withdrawals/<int:telegram_id>', methods=['GET'])
def get_withdrawal_history(telegram_id):
    data = supabase.table('withdrawals').select('*').eq('user_id', telegram_id).order('created_at', desc=True).limit(5).execute()
    return jsonify(data.data)

# === API ADMIN (Giữ nguyên) ===
@app.route('/admin/all_users', methods=['GET'])
def get_all_users():
    admin_id_str = str(request.args.get('admin_id'))
    if not check_is_admin(admin_id_str): return jsonify({"error": "Unauthorized"}), 403 
    users_data = supabase.table('users').select('*').order('created_at', desc=True).execute()
    users_dict = {user['telegram_id']: user for user in users_data.data}
    return jsonify(users_dict)
@app.route('/admin/modify_balance', methods=['POST'])
def modify_balance():
    data = request.json; admin_id_str = str(data.get('admin_id')); target_user_id = int(data.get('target_user_id')); amount = int(data.get('amount'))
    if not check_is_admin(admin_id_str): return jsonify({"error": "Unauthorized"}), 403 
    try:
        new_balance = supabase.rpc('mod_balance', {'user_id_in': target_user_id, 'amount_in': amount}).execute().data
        return jsonify({"message": f"Đã cập nhật số dư.", "new_balance": new_balance})
    except Exception as e: return jsonify({"error": f"Lỗi Supabase: {e}"}), 500
@app.route('/admin/pending_withdrawals', methods=['GET'])
def get_pending_withdrawals():
    admin_id_str = str(request.args.get('admin_id'))
    if not check_is_admin(admin_id_str): return jsonify({"error": "Unauthorized"}), 403 
    data = supabase.table('withdrawals').select('*').eq('status', 'pending').order('created_at', desc=True).execute()
    return jsonify(data.data)
@app.route('/admin/process_withdrawal', methods=['POST'])
def process_withdrawal():
    data = request.json; admin_id_str = str(data.get('admin_id')); withdrawal_id = str(data.get('withdrawal_id')); action = data.get('action'); note = data.get('note', 'Không có lý do cụ thể.') 
    if not check_is_admin(admin_id_str): return jsonify({"error": "Unauthorized"}), 403 
    try:
        req_res = supabase.table('withdrawals').select('*').eq('id', withdrawal_id).single().execute()
        if not req_res.data: return jsonify({"error": "Yêu cầu không tồn tại."}), 404
        req = req_res.data; user_id = int(req['user_id']); amount = req['amount']
        if req['status'] != 'pending': return jsonify({"error": "Yêu cầu này đã được xử lý."}), 400
        if action == 'approve':
            user_res = supabase.table('users').select('balance, username').eq('telegram_id', user_id).single().execute()
            if not user_res.data:
                supabase.table('withdrawals').update({'status': 'denied'}).eq('id', withdrawal_id).execute(); return jsonify({"error": "User không còn tồn tại."}), 400
            if user_res.data['balance'] < amount:
                supabase.table('withdrawals').update({'status': 'denied'}).eq('id', withdrawal_id).execute()
                send_telegram_message(user_id, f"❌ Yêu cầu rút {amount:,.0f} đ đã bị TỪ CHỐI.\n<b>Lý do:</b> Không đủ số dư.")
                return jsonify({"error": "User không đủ số dư."}), 400
            supabase.rpc('mod_balance', {'user_id_in': user_id, 'amount_in': -amount}).execute()
            supabase.table('withdrawals').update({'status': 'approved'}).eq('id', withdrawal_id).execute()
            send_telegram_message(user_id, f"✅ Yêu cầu rút <b>{amount:,.0f} đ</b> đã được <b>DUYỆT</b>.")
            return jsonify({"message": f"Đã duyệt rút {amount:,.0f} đ cho {user_res.data['username']}."})
        elif action == 'deny':
            supabase.table('withdrawals').update({'status': 'denied'}).eq('id', withdrawal_id).execute()
            send_telegram_message(user_id, f"❌ Yêu cầu rút <b>{amount:,.0f} đ</b> đã bị <b>TỪ CHỐI</b>.\n<b>Lý do:</b> {note}")
            return jsonify({"message": f"Đã từ chối yêu cầu."})
    except Exception as e: return jsonify({"error": f"Lỗi Supabase: {e}"}), 500
@app.route('/admin/confirm_deposit', methods=['POST'])
def confirm_deposit():
    data = request.json; admin_id_str = str(data.get('admin_id')); target_user_id = int(data.get('target_user_id')); amount = int(data.get('amount'))
    if not check_is_admin(admin_id_str): return jsonify({"error": "Unauthorized"}), 403 
    if amount <= 0: return jsonify({"error": "Số tiền nạp phải lớn hơn 0"}), 400
    try:
        new_balance = supabase.rpc('mod_balance', {'user_id_in': target_user_id, 'amount_in': amount}).execute().data
        supabase.table('deposit_history').insert({"user_id": target_user_id, "amount": amount, "admin_id": int(admin_id_str), "created_at": datetime.now().isoformat()}).execute()
        send_telegram_message(target_user_id, f"✅ Tài khoản của bạn đã được nạp thành công <b>{amount:,.0f} đ</b>.")
        return jsonify({"message": f"Đã nạp {amount:,.0f} đ. Số dư mới: {new_balance:,.0f} đ."})
    except Exception as e: return jsonify({"error": f"Lỗi Supabase (User không tồn tại?): {e}"}), 500
@app.route('/admin/toggle_ban', methods=['POST'])
def toggle_ban():
    data = request.json; admin_id_str = str(data.get('admin_id')); target_user_id = int(data.get('target_user_id'))
    if not check_is_admin(admin_id_str): return jsonify({"error": "Unauthorized"}), 403 
    try:
        user = supabase.table('users').select('is_banned, username').eq('telegram_id', target_user_id).single().execute()
        if not user.data: return jsonify({"error": "User không tồn tại"}), 404
        new_status = not user.data['is_banned']; supabase.table('users').update({'is_banned': new_status}).eq('telegram_id', target_user_id).execute()
        action = "KHÓA" if new_status else "MỞ KHÓA"; send_telegram_message(target_user_id, f"⚠️ Tài khoản của bạn đã bị <b>{action}</b> bởi Admin.")
        return jsonify({"message": f"Đã {action} tài khoản {user.data['username']}."})
    except Exception as e: return jsonify({"error": f"Lỗi Supabase: {e}"}), 500
@app.route('/admin/broadcast', methods=['POST'])
def broadcast_message():
    data = request.json; admin_id_str = str(data.get('admin_id')); message = data.get('message')
    if not check_is_admin(admin_id_str): return jsonify({"error": "Unauthorized"}), 403 
    if not message: return jsonify({"error": "Nội dung tin nhắn không thể để trống"}), 400
    try:
        users = supabase.table('users').select('telegram_id').execute(); count = 0
        for user in users.data:
            if send_telegram_message(user['telegram_id'], message): count += 1; time.sleep(0.1) 
        return jsonify({"message": f"Đã gửi thông báo cho {count} người dùng."})
    except Exception as e: return jsonify({"error": f"Lỗi Supabase: {e}"}), 500
@app.route('/admin/create_giftcode', methods=['POST'])
def create_giftcode():
    data = request.json; admin_id_str = str(data.get('admin_id')); code = str(data.get('code')).upper()
    try: amount = int(data.get('amount')); limit = int(data.get('limit'))
    except Exception: return jsonify({"error": "Số tiền hoặc số lượt không hợp lệ"}), 400
    if not check_is_admin(admin_id_str): return jsonify({"error": "Unauthorized"}), 403 
    if not code or amount <= 0 or limit <= 0: return jsonify({"error": "Code, số tiền, hoặc số lượt dùng không hợp lệ"}), 400
    try:
        supabase.table('giftcodes').insert({"code": code, "amount": amount, "limit_count": limit, "used_by": []}).execute()
        return jsonify({"message": f"Đã tạo code {code} (trị giá {amount:,.0f} đ, {limit} lượt dùng)."}), 200
    except Exception: return jsonify({"error": "Code này đã tồn tại"}), 400
@app.route('/admin/all_bet_history', methods=['GET'])
def get_all_bet_history():
    admin_id_str = str(request.args.get('admin_id'))
    if not check_is_admin(admin_id_str): return jsonify({"error": "Unauthorized"}), 403 
    data = supabase.table('bet_history').select('*').order('created_at', desc=True).limit(50).execute()
    return jsonify(data.data)
@app.route('/admin/set_result', methods=['POST'])
def set_result():
    data = request.json; admin_id_str = str(data.get('admin_id')); session_id = int(data.get('session_id')); dice_string = data.get('dice') 
    if not check_is_admin(admin_id_str): return jsonify({"error": "Unauthorized"}), 403
    if not dice_string or len(dice_string) != 3 or not dice_string.isdigit():
        return jsonify({"error": "Kết quả phải là 3 chữ số (ví dụ: 123, 662)"}), 400
    try:
        dice = [int(d) for d in dice_string]
        if not all(1 <= d <= 6 for d in dice):
            return jsonify({"error": "Các số phải từ 1 đến 6"}), 400
        total = sum(dice); result_type = "bo_ba" if dice[0] == dice[1] == dice[2] else ("xiu" if 4 <= total <= 10 else "tai")
    except Exception:
        return jsonify({"error": "Định dạng số không hợp lệ"}), 400
    try:
        session = supabase.table('tx_sessions').select('*').eq('id', session_id).eq('status', 'pending').single().execute()
        if not session.data: return jsonify({"error": "Không tìm thấy phiên đang cược."}), 404
        supabase.table('tx_sessions').update({"result_dice": dice, "result_total": total, "result_type": result_type, "admin_override": True}).eq('id', session_id).execute()
        return jsonify({"message": f"Đã chỉnh kết quả phiên #{session_id} thành {dice_string} ({result_type.upper()})"})
    except Exception as e: return jsonify({"error": f"Lỗi Supabase: {e}"}), 500
@app.route('/admin/bets_for_session', methods=['GET'])
def get_bets_for_session():
    admin_id_str = str(request.args.get('admin_id')); session_id = int(request.args.get('session_id'))
    if not check_is_admin(admin_id_str): return jsonify({"error": "Unauthorized"}), 403
    if not session_id: return jsonify({"error": "Thiếu session_id"}), 400
    try:
        bets_data = supabase.table('tx_bets').select('username, choice, amount').eq('session_id', session_id).order('created_at', desc=True).execute()
        return jsonify(bets_data.data)
    except Exception as e: return jsonify({"error": f"Lỗi Supabase: {e}"}), 500

# === LOGIC GAME TÀI XỈU 30 GIÂY ===
current_session = {"id": 0, "end_time": 0, "status": "finished"} 
SESSION_DURATION = 30 
SPIN_DURATION = 5 
PAY_DURATION = 5 

def session_manager():
    global current_session
    while True:
        try:
            # 1. TẠO PHIÊN MỚI
            session_id = int(time.time())
            end_time = session_id + SESSION_DURATION
            current_session = {"id": session_id, "end_time": end_time, "status": "pending"}
            supabase.table('tx_sessions').insert({"id": session_id, "status": "pending"}).execute()
            print(f"--- ĐÃ MỞ PHIÊN MỚI #{session_id} (Cược trong {SESSION_DURATION}s) ---")
            
            # 2. CHỜ HẾT 30 GIÂY
            time.sleep(SESSION_DURATION)
            
            # 3. ĐÓNG CƯỢC & QUAY SỐ (5 giây)
            current_session['status'] = 'spinning' 
            print(f"--- ĐÃ ĐÓNG CƯỢC PHIÊN #{session_id} (Quay trong {SPIN_DURATION}s) ---")
            session = supabase.table('tx_sessions').select('*').eq('id', session_id).single().execute()
            
            if session.data and session.data.get('admin_override') == True:
                dice = session.data['result_dice']; total = session.data['result_total']; result_type = session.data['result_type']
                print(f"Phiên #{session_id} dùng kết quả của ADMIN: {result_type}")
            else:
                die1, die2, die3 = random.randint(1, 6), random.randint(1, 6), random.randint(1, 6)
                dice = [die1, die2, die3]; total = sum(dice)
                if die1 == die2 == die3: result_type = "bo_ba"
                elif 4 <= total <= 10: result_type = "xiu"
                else: result_type = "tai"
            
            supabase.table('tx_sessions').update({"result_dice": dice, "result_total": total, "result_type": result_type, "status": "finished"}).execute()
            time.sleep(SPIN_DURATION) 
            
            # 4. CHỜ TRẢ THƯỞNG (5 giây)
            current_session['status'] = 'finished' 
            print(f"--- ĐANG TRẢ THƯỞNG PHIÊN #{session_id} (Chờ {PAY_DURATION}s) ---")
            result = supabase.rpc('process_tx_session', {'session_id_in': session_id}).execute()
            print(f"Trả thưởng xong: {result.data}")
            
            time.sleep(PAY_DURATION) 
            
        except Exception as e:
            print(f"Lỗi nghiêm trọng trong session_manager: {e}")
            time.sleep(10) 

# API LẤY TRẠNG THÁI PHIÊN
@app.route('/game/tx30/status', methods=['GET'])
def get_tx30_status():
    global current_session
    time_left = max(0, current_session['end_time'] - int(time.time()))
    try:
        latest_session_res = supabase.table('tx_sessions').select('*').order('created_at', desc=True).limit(1).execute()
        latest_session = latest_session_res.data[0] if latest_session_res.data else None
        history_res = supabase.table('tx_sessions').select('id, result_type, result_total').eq('status', 'finished').order('created_at', desc=True).limit(10).execute()
        
        return jsonify({
            "session_id": current_session['id'],
            "time_left": time_left,
            "status": current_session['status'], 
            "latest_session_result": latest_session, 
            "history": history_res.data
        })
        
    except Exception as e:
        print(f"Lỗi lấy cầu: {e}"); 
        return jsonify({"session_id": 0, "time_left": 0, "history": [], "status": "error"})

# API ĐẶT CƯỢC (ĐÃ SỬA LỖI: Cho cược nhiều lần CÙNG MỘT CỬA)
@app.route('/game/tx30/bet', methods=['POST'])
def place_tx30_bet():
    data = request.json; user_id_str = str(data.get('telegram_id')); session_id = int(data.get('session_id')); choice = data.get('choice'); amount = int(data.get('amount', 0))
    if check_is_banned(user_id_str): return jsonify({"error": "Tài khoản của bạn đã bị khóa."}), 403
    if session_id != current_session['id']: return jsonify({"error": "Phiên cược đã hết hạn."}), 400
    if current_session['status'] != 'pending' or (current_session['end_time'] - int(time.time()) < 3):
        return jsonify({"error": "Đã hết thời gian cược."}), 400
    if amount <= 0 or choice not in ['tai', 'xiu']: return jsonify({"error": "Thông tin cược không hợp lệ"}), 400
        
    try:
        user_id = int(user_id_str)
        user = supabase.table('users').select('balance, username').eq('telegram_id', user_id).single().execute()
        if not user.data: return jsonify({"error": "User không tồn tại."}), 404
        if user.data['balance'] < amount: return jsonify({"error": "Không đủ số dư."}), 400
            
        existing_bets = supabase.table('tx_bets').select('choice').eq('user_id', user_id).eq('session_id', session_id).limit(1).execute()
        if existing_bets.data:
            existing_choice = existing_bets.data[0]['choice']
            if existing_choice != choice:
                return jsonify({"error": f"Bạn đã cược {existing_choice.upper()} rồi, không thể cược thêm {choice.upper()}."}), 400
            
        new_balance = supabase.rpc('mod_balance', {'user_id_in': user_id, 'amount_in': -amount}).execute().data
        
        supabase.table('tx_bets').insert({
            "session_id": session_id, "user_id": user_id,
            "username": user.data['username'], "choice": choice, "amount": amount,
            "created_at": datetime.now().isoformat()
        }).execute()
        
        return jsonify({"message": f"Cược {choice.upper()} {amount:,.0f}đ thành công!", "new_balance": new_balance})
    except Exception as e:
        print(f"Lỗi /game/tx30/bet: {e}")
        return jsonify({"error": "Lỗi máy chủ khi đặt cược."}), 500

# === CHẠY SERVER ===
if __name__ == '__main__':
    threading.Thread(target=session_manager, daemon=True).start()
    print("Khởi động API server (Tài Xỉu 30 Giây)...")
    # Lấy PORT từ môi trường (cho Koyeb) hoặc 5000 (cho Replit)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
