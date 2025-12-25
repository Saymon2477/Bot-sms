import telebot
import time
import requests
import os
import shutil
import threading
from flask import Flask
from telebot import types

# --- কনফিগারেশন ---
API_TOKEN = '8463139658:AAECrUe1JeoVV7MoQgyG3Pj452RsfoYV0E8'
FIREBASE_URL = 'https://otp-bot-611a8-default-rtdb.firebaseio.com' 
ADMIN_PASSWORD = '1122'
ADMIN_URL = 'https://t.me/ftcaiw24'
GROUP_URL = 'https://t.me/ftc_sms_chat'
CHANNEL_URL = 'https://t.me/ftc_sms'
NUMBERS_DIR = 'numbers/'

bot = telebot.TeleBot(API_TOKEN)

# --- ১. রেন্ডার কিপ-এলাইভ (Flask Server) ---
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is Running!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

threading.Thread(target=run_flask).start()

# --- ২. ফায়ারবেজ হেল্পার ফাংশন ---
def db_save(path, data):
    requests.put(f"{FIREBASE_URL}/{path}.json", json=data)

def db_get(path):
    try:
        res = requests.get(f"{FIREBASE_URL}/{path}.json")
        return res.json()
    except:
        return None

def db_delete(path):
    requests.delete(f"{FIREBASE_URL}/{path}.json")

# --- ৩. মেইন মেনু ---
def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("🚀 Get Number", callback_data="select_server"))
    markup.add(types.InlineKeyboardButton("👨‍💻 Admin", url=ADMIN_URL),
               types.InlineKeyboardButton("👥 Group", url=GROUP_URL))
    markup.add(types.InlineKeyboardButton("📢 Channel", url=CHANNEL_URL))
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "🔐 *Online OTP System Active* ✅\n\nনাম্বার নিতে নিচের বাটন চাপুন।", 
                     parse_mode="Markdown", reply_markup=main_menu())

# --- ৪. ইউজার সেকশন (সার্ভার ও নাম্বার) ---
@bot.callback_query_handler(func=lambda call: call.data == "select_server")
def select_server(call):
    markup = types.InlineKeyboardMarkup()
    if not os.path.exists(NUMBERS_DIR): os.makedirs(NUMBERS_DIR)
    
    files = [f.replace('.txt', '') for f in os.listdir(NUMBERS_DIR) if f.endswith('.txt')]
    
    if not files:
        markup.add(types.InlineKeyboardButton("⬅️ Back to Home", callback_data="back_home"))
        bot.edit_message_text("❌ কোনো সার্ভার বা নাম্বার লোড করা নেই!", call.message.chat.id, call.message.message_id, reply_markup=markup)
        return

    for s in files:
        markup.add(types.InlineKeyboardButton(f"🔹 {s.upper()}", callback_data=f"srv_{s}"))
    
    markup.add(types.InlineKeyboardButton("⬅️ Back to Home", callback_data="back_home"))
    bot.edit_message_text("একটি সার্ভার সিলেক্ট করুন:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("srv_"))
def handle_number(call):
    server = call.data.split("_")[1]
    user_id = str(call.from_user.id)
    
    file_path = os.path.join(NUMBERS_DIR, f"{server}.txt")
    if not os.path.exists(file_path):
        bot.answer_callback_query(call.id, "ফাইলটি পাওয়া যায়নি!", show_alert=True)
        return

    with open(file_path, 'r') as f:
        numbers = [line.strip() for line in f.readlines() if line.strip()]

    progress = db_get(f"user_progress/{user_id}")
    index = (progress['index'] + 1) if (progress and progress.get('server') == server) else 0

    if index < len(numbers):
        phone = numbers[index]
        db_save(f"user_progress/{user_id}", {"index": index, "server": server})
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("🔄 Get Next", callback_data=f"srv_{server}"),
                   types.InlineKeyboardButton("📩 Get SMS", callback_data=f"check_{phone}"))
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="select_server"))
        
        bot.edit_message_text(f"🌍 *Server:* {server.upper()}\n🔢 *Serial:* {index + 1}\n☎️ *Number:* `{phone}`", 
                              call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
    else:
        bot.answer_callback_query(call.id, "এই সার্ভারে আর নাম্বার নেই!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("check_"))
def check_sms(call):
    phone = call.data.split("_")[1]
    now = int(time.time())
    data = db_get(f"sms_logs/{phone}")
    
    if data and abs(now - data['timestamp']) <= 60:
        bot.send_message(call.message.chat.id, f"🔐 *OTP Received* ✅\n\n☎️ `{phone}`\n💬 `{data['message']}`", parse_mode="Markdown")
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("👥 Join Group", url=GROUP_URL))
        bot.send_message(call.message.chat.id, "❌ মেসেজ এখনো আসেনি।", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "back_home")
def back_home(call):
    bot.edit_message_text("🔐 *Online OTP System Active* ✅", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=main_menu())

# --- ৫. কনসোল থেকে ডাটাবেজ আপডেট ---
@bot.message_handler(func=lambda m: m.text and m.text.startswith("DB_ADD:"))
def remote_db_add(message):
    try:
        raw = message.text.replace("DB_ADD:", "").split("|")
        phone, msg = raw[0].strip(), raw[1].strip()
        db_save(f"sms_logs/{phone}", {"message": msg, "timestamp": int(time.time())})
        bot.reply_to(message, f"✅ DB Updated: {phone}")
    except: pass

# ==========================================
#              ৬. এডমিন প্যানেল (New)
# ==========================================

@bot.message_handler(commands=['admin'])
def admin_login(message):
    msg = bot.reply_to(message, "🔐 *Admin Login*\nদয়া করে পাসওয়ার্ড দিন:", parse_mode="Markdown")
    bot.register_next_step_handler(msg, verify_password)

def verify_password(message):
    if message.text == ADMIN_PASSWORD:
        show_admin_panel(message.chat.id)
    else:
        bot.reply_to(message, "❌ ভুল পাসওয়ার্ড!")

def show_admin_panel(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("➕ Add New Server / Numbers", callback_data="adm_add_srv"))
    markup.add(types.InlineKeyboardButton("🧹 Clean Old OTPs (1 Hour)", callback_data="adm_clean_otp"))
    markup.add(types.InlineKeyboardButton("🗑️ Delete Specific Server", callback_data="adm_del_srv"))
    markup.add(types.InlineKeyboardButton("⚠️ Delete ALL Servers", callback_data="adm_del_all"))
    markup.add(types.InlineKeyboardButton("🚪 Logout", callback_data="back_home"))
    bot.send_message(chat_id, "⚙️ *Admin Dashboard*\nঅপশন সিলেক্ট করুন:", parse_mode="Markdown", reply_markup=markup)

# --- Clean OTP Logic ---
@bot.callback_query_handler(func=lambda call: call.data == "adm_clean_otp")
def clean_old_otps(call):
    bot.answer_callback_query(call.id, "Checking database...")
    logs = db_get("sms_logs")
    if not logs:
        bot.send_message(call.message.chat.id, "❌ ডাটাবেজ খালি!")
        return

    count = 0
    now = int(time.time())
    for phone, data in logs.items():
        # ১ ঘন্টা (৩৬০০ সেকেন্ড) এর পুরনো ডাটা ডিলিট
        if now - data['timestamp'] > 3600:
            db_delete(f"sms_logs/{phone}")
            count += 1
    
    bot.send_message(call.message.chat.id, f"✅ ক্লিন সম্পন্ন!\n🗑️ মোট {count} টি পুরনো ওটিপি ডিলিট করা হয়েছে।")
    show_admin_panel(call.message.chat.id)

# --- Add Server Logic ---
@bot.callback_query_handler(func=lambda call: call.data == "adm_add_srv")
def adm_ask_name(call):
    msg = bot.send_message(call.message.chat.id, "📝 সার্ভারের নাম লিখুন (উদা: facebook, whatsapp):")
    bot.register_next_step_handler(msg, adm_get_name)

def adm_get_name(message):
    server_name = message.text.lower().strip()
    msg = bot.send_message(message.chat.id, f"📦 *{server_name.upper()}* এর জন্য নাম্বার লিস্ট পেস্ট করুন:\n(প্রতি লাইনে একটি করে নাম্বার)", parse_mode="Markdown")
    bot.register_next_step_handler(msg, lambda m: adm_save_numbers(m, server_name))

def adm_save_numbers(message, server_name):
    numbers = message.text.strip()
    if not numbers:
        bot.send_message(message.chat.id, "❌ কোনো নাম্বার পাওয়া যায়নি।")
        return

    if not os.path.exists(NUMBERS_DIR): os.makedirs(NUMBERS_DIR)
    
    # নতুন ফাইল তৈরি হবে অথবা আগের ফাইলে নাম্বার যোগ হবে (Append Mode)
    file_path = os.path.join(NUMBERS_DIR, f"{server_name}.txt")
    with open(file_path, 'a') as f:
        f.write(numbers + "\n")
    
    line_count = len(numbers.split('\n'))
    bot.send_message(message.chat.id, f"✅ *{server_name.upper()}* সার্ভারে {line_count} টি নাম্বার সেভ হয়েছে!", parse_mode="Markdown")
    show_admin_panel(message.chat.id)

# --- Delete Specific Server ---
@bot.callback_query_handler(func=lambda call: call.data == "adm_del_srv")
def adm_show_del_list(call):
    markup = types.InlineKeyboardMarkup()
    if not os.path.exists(NUMBERS_DIR): os.makedirs(NUMBERS_DIR)
    files = [f.replace('.txt', '') for f in os.listdir(NUMBERS_DIR) if f.endswith('.txt')]
    
    if not files:
        bot.answer_callback_query(call.id, "কোনো সার্ভার নেই!", show_alert=True)
        return

    for s in files:
        markup.add(types.InlineKeyboardButton(f"🗑️ Delete {s.upper()}", callback_data=f"del_confirm_{s}"))
    markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back_admin"))
    bot.edit_message_text("কোন সার্ভারটি ডিলিট করতে চান?", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_confirm_"))
def adm_del_process(call):
    server = call.data.split("_")[2]
    try:
        os.remove(os.path.join(NUMBERS_DIR, f"{server}.txt"))
        bot.answer_callback_query(call.id, "Deleted!", show_alert=True)
        bot.send_message(call.message.chat.id, f"✅ {server} সার্ভারটি ডিলিট করা হয়েছে।")
    except:
        bot.send_message(call.message.chat.id, "❌ ডিলিট করতে সমস্যা হয়েছে।")
    show_admin_panel(call.message.chat.id)

# --- Delete ALL Servers ---
@bot.callback_query_handler(func=lambda call: call.data == "adm_del_all")
def adm_del_all_confirm(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⚠️ YES, DELETE ALL", callback_data="adm_nuke_yes"))
    markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="back_admin"))
    bot.edit_message_text("⚠️ আপনি কি নিশ্চিত সব সার্ভার ও নাম্বার ডিলিট করতে চান?", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "adm_nuke_yes")
def adm_nuke(call):
    if os.path.exists(NUMBERS_DIR):
        shutil.rmtree(NUMBERS_DIR) # পুরো ফোল্ডার ডিলিট
        os.makedirs(NUMBERS_DIR)   # আবার খালি ফোল্ডার তৈরি
    bot.send_message(call.message.chat.id, "💥 সব সার্ভার ও নাম্বার ডিলিট করা হয়েছে!")
    show_admin_panel(call.message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "back_admin")
def back_admin(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    show_admin_panel(call.message.chat.id)

if __name__ == "__main__":
    if not os.path.exists(NUMBERS_DIR): os.makedirs(NUMBERS_DIR)
    print("🤖 Bot is Running with Advanced Admin Panel...")
    bot.polling(none_stop=True)
