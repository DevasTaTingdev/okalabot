import os
import logging
import asyncio
import random
import string
import re
import uuid
import time
import json
import jwt
import sqlite3
import aiohttp
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# تنظیمات اصلی
BOT_TOKEN = os.getenv("BOT_TOKEN", "7566499749:AAEjqt6B3bdonZtWzO_WyOLvqZpilqrsVZc")
ADMIN_IDS = [5847378706]  # شناسه ادمین‌ها
OWNER_ID = 5847378706  # شناسه مالک ربات
DB_FILE = "okala_bot.db"
LOG_FILE = "bot_errors.log"
BOT_ENABLED = True

# ایموجی‌ها
EMOJI = {
    "main_menu": "🏠",
    "start_process": "🚀",
    "support": "🛟",
    "phone": "📱",
    "password": "🔑",
    "success": "✅",
    "error": "❌",
    "discount": "🎁",
    "warning": "⚠️",
    "clock": "⏱️",
    "back": "↩️",
    "cancel": "❌",
    "check": "🔍",
    "token": "🔑",
    "list": "📋",
    "process": "⚙️",
    "result": "📊",
    "vip": "⭐",
    "stats": "📈",
    "admin": "👑",
    "on": "🟢",
    "off": "🔴",
    "register": "📝",
    "basket": "🛒",
    "otp": "🔢",
    "profile": "👤",
    "city": "🏙️",
    "resend": "🔄",
    "stop": "⏹️"
}

# نام‌ها و نام‌های خانوادگی فارسی
PERSIAN_FIRST_NAMES = [
    "محمد", "علی", "رضا", "حسن", "حسین", "فاطمه", "زهرا", "مریم", 
    "سجاد", "امیر", "پارسا", "کیانا", "سارا", "نازنین", "امیرحسین",
    "محمدحسین", "ابوالفضل", "مهدی", "احمد", "عباس"
]

PERSIAN_LAST_NAMES = [
    "محمدی", "حسینی", "رضایی", "کریمی", "موسوی", "جعفری", "قاسمی",
    "اکبری", "امیری", "کاظمی", "زارع", "مرادی", "رحیمی", "سلطانی",
    "نوری", "احمدی", "فتحی", "اشرفی", "نجفی", "پوراحمد"
]

# دامنه‌های ایمیل
EMAIL_DOMAINS = [
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", 
    "protonmail.com", "icloud.com", "mail.com"
]

# شهرها و فروشگاه‌ها
CITIES = {
    "تبریز": {"id": 131, "store_id": 3876, "store_name": "فروشگاه تبریز"},
    "مشهد": {"id": 56, "store_id": 4521, "store_name": "فروشگاه مشهد"},
    "تهران": {"id": 129, "store_id": 10007, "store_name": "دستغیب"},
    "کرج": {"id": 200, "store_id": 4150, "store_name": "فروشگاه کرج"},
    "قم": {"id": 126, "store_id": 3987, "store_name": "فروشگاه قم"},
    "اصفهان": {"id": 97, "store_id": 4265, "store_name": "فروشگاه اصفهان"},
    "شیراز": {"id": 140, "store_id": 4372, "store_name": "فروشگاه شیراز"},
    "همه": {"id": 0, "store_id": 10007, "store_name": "دستغیب"}
}

# تنظیمات لاگ
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# حالت‌های FSM
class Form(StatesGroup):
    waiting_for_phones = State()
    waiting_for_password = State()
    waiting_for_next_list = State()
    waiting_for_next_password = State()
    waiting_for_token_file = State()
    waiting_for_vip_user_id = State()
    waiting_for_stats_user_id = State()

class RegisterState(StatesGroup):
    waiting_for_phone = State()
    waiting_for_otp = State()
    waiting_for_password = State()
    waiting_for_next_action = State()

class BasketState(StatesGroup):
    waiting_for_city = State()
    waiting_for_phones = State()
    waiting_for_password = State()
    waiting_for_next_list = State()
    waiting_for_next_password = State()
    waiting_for_process = State()

# ===========================================
# پایگاه داده SQLite
# ===========================================
class Database:
    def __init__(self, db_file):
        self.db_file = db_file
        self.conn = None
        self._initialize_db()

    def _initialize_db(self):
        """ایجاد جداول مورد نیاز در پایگاه داده"""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            
            # جدول کاربران ویژه
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vip_users (
                    user_id INTEGER PRIMARY KEY
                )
            ''')
            
            # جدول آمار کاربران
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_stats (
                    user_id INTEGER PRIMARY KEY,
                    total_checked INTEGER DEFAULT 0,
                    success INTEGER DEFAULT 0,
                    failed INTEGER DEFAULT 0
                )
            ''')
            
            # جدول اطلاعات ثبت نام
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS registration_data (
                    user_id INTEGER,
                    phone TEXT,
                    password TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    email TEXT,
                    PRIMARY KEY (user_id, phone)
                )
            ''')
            
            # جدول اطلاعات سبد خرید
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS basket_data (
                    user_id INTEGER,
                    city_id INTEGER,
                    list_index INTEGER,
                    phone TEXT,
                    password TEXT,
                    PRIMARY KEY (user_id, list_index, phone)
                )
            ''')
            
            # جدول توکن‌ها
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tokens (
                    phone TEXT PRIMARY KEY,
                    token TEXT,
                    refresh_token TEXT,
                    expires_at REAL
                )
            ''')
            
            conn.commit()

    def get_vip_users(self):
        """دریافت لیست کاربران ویژه"""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM vip_users")
            return {row[0] for row in cursor.fetchall()}

    def add_vip_user(self, user_id):
        """افزودن کاربر ویژه"""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT OR IGNORE INTO vip_users (user_id) VALUES (?)", (user_id,))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def remove_vip_user(self, user_id):
        """حذف کاربر ویژه"""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM vip_users WHERE user_id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_user_stats(self, user_id):
        """دریافت آمار کاربر"""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT total_checked, success, failed FROM user_stats WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    'total_checked': row[0],
                    'success': row[1],
                    'failed': row[2]
                }
            return None

    def update_user_stats(self, user_id, success):
        """به‌روزرسانی آمار کاربر"""
        stats = self.get_user_stats(user_id) or {
            'total_checked': 0,
            'success': 0,
            'failed': 0
        }
        
        stats['total_checked'] += 1
        if success:
            stats['success'] += 1
        else:
            stats['failed'] += 1
        
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_stats 
                (user_id, total_checked, success, failed) 
                VALUES (?, ?, ?, ?)
            ''', (user_id, stats['total_checked'], stats['success'], stats['failed']))
            conn.commit()

    def save_registration_phones(self, user_id, phones_data):
        """ذخیره شماره‌های ثبت نام شده"""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            # حذف داده‌های قبلی
            cursor.execute("DELETE FROM registration_data WHERE user_id = ?", (user_id,))
            
            # ذخیره داده‌های جدید
            for data in phones_data:
                cursor.execute('''
                    INSERT INTO registration_data 
                    (user_id, phone, password, first_name, last_name, email)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    data['phone'],
                    data['password'],
                    data['first_name'],
                    data['last_name'],
                    data['email']
                ))
            conn.commit()

    def get_registration_phones(self, user_id):
        """دریافت شماره‌های ثبت نام شده"""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT phone, password, first_name, last_name, email "
                "FROM registration_data WHERE user_id = ?",
                (user_id,)
            )
            return [
                {
                    'phone': row[0],
                    'password': row[1],
                    'first_name': row[2],
                    'last_name': row[3],
                    'email': row[4]
                }
                for row in cursor.fetchall()
            ]

    def save_basket_data(self, user_id, city_id, lists):
        """ذخیره اطلاعات سبد خرید"""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            # حذف داده‌های قبلی
            cursor.execute("DELETE FROM basket_data WHERE user_id = ?", (user_id,))
            
            # ذخیره داده‌های جدید
            for list_index, (phones, password) in enumerate(lists):
                for phone in phones:
                    cursor.execute('''
                        INSERT INTO basket_data 
                        (user_id, city_id, list_index, phone, password)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (user_id, city_id, list_index, phone, password))
            conn.commit()

    def get_basket_data(self, user_id):
        """دریافت اطلاعات سبد خرید"""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            
            # دریافت city_id
            cursor.execute(
                "SELECT DISTINCT city_id FROM basket_data WHERE user_id = ?",
                (user_id,)
            )
            city_row = cursor.fetchone()
            if not city_row:
                return None, []
            
            city_id = city_row[0]
            
            # دریافت لیست‌ها
            cursor.execute(
                "SELECT list_index, phone, password "
                "FROM basket_data WHERE user_id = ? "
                "ORDER BY list_index",
                (user_id,)
            )
            
            lists_dict = {}
            for row in cursor.fetchall():
                list_index, phone, password = row
                if list_index not in lists_dict:
                    lists_dict[list_index] = ([], password)
                lists_dict[list_index][0].append(phone)
            
            # تبدیل به لیست مرتب
            lists = [lists_dict[i] for i in sorted(lists_dict.keys())]
            
            return city_id, lists

    def save_token(self, phone, token, refresh_token=None, expires_at=None):
        """ذخیره توکن در پایگاه داده"""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO tokens (phone, token, refresh_token, expires_at)
                VALUES (?, ?, ?, ?)
            ''', (phone, token, refresh_token, expires_at))
            conn.commit()

    def get_token(self, phone):
        """دریافت توکن از پایگاه داده"""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT token, refresh_token, expires_at FROM tokens WHERE phone = ?",
                (phone,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    'token': row[0],
                    'refresh_token': row[1],
                    'expires_at': row[2]
                }
            return None

    def get_all_tokens(self):
        """دریافت تمام توکن‌ها"""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT phone, token, refresh_token, expires_at FROM tokens")
            return {
                row[0]: {
                    'token': row[1],
                    'refresh_token': row[2],
                    'expires_at': row[3]
                }
                for row in cursor.fetchall()
            }

# ایجاد نمونه پایگاه داده
db = Database(DB_FILE)

# ===========================================
# توابع کمکی
# ===========================================
def get_user_role(user_id):
    if user_id == OWNER_ID:
        return "مالک"
    elif user_id in ADMIN_IDS:
        return "ادمین"
    elif user_id in db.get_vip_users():
        return "ویژه"
    else:
        return "معمولی"

def is_user_allowed(user_id):
    if not BOT_ENABLED and user_id not in ADMIN_IDS and user_id != OWNER_ID:
        return False
    return user_id in db.get_vip_users() or user_id in ADMIN_IDS or user_id == OWNER_ID

def generate_random_name():
    return random.choice(PERSIAN_FIRST_NAMES)

def generate_random_lastname():
    return random.choice(PERSIAN_LAST_NAMES)

def generate_random_email():
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    domain = random.choice(EMAIL_DOMAINS)
    return f"{username}@{domain}"

def generate_random_birthdate():
    # تولد بین 18 تا 60 سال قبل
    start_date = datetime.now() - timedelta(days=60*365)
    end_date = datetime.now() - timedelta(days=18*365)
    random_date = start_date + (end_date - start_date) * random.random()
    return int(random_date.timestamp())

def validate_phone(phone):
    pattern = r'^09\d{9}$'
    return re.match(pattern, phone) is not None

def validate_password(password):
    if len(password) < 8:
        return False, "رمز عبور باید حداقل 8 کاراکتر داشته باشد"
    if not re.search(r'[A-Z]', password):
        return False, "رمز عبور باید حداقل یک حرف بزرگ انگلیسی داشته باشد"
    if not re.search(r'[a-z]', password):
        return False, "رمز عبور باید حداقل یک حرف کوچک انگلیسی داشته باشد"
    if not re.search(r'\d', password):
        return False, "رمز عبور باید حداقل یک عدد داشته باشد"
    return True, ""

def is_token_expired(expires_at):
    if not expires_at:
        return True
    return time.time() > expires_at

# ===========================================
# توابع API با استفاده از aiohttp
# ===========================================
async def send_otp(phone):
    headers = {
        "Host": "apigateway.okala.com",
        "sec-ch-ua-platform": "Android",
        "x-correlation-id": str(uuid.uuid4()),
        "sec-ch-ua": '"Not?A_Brand";v="99", "Samsung Internet";v="28.0", "Chromium";v="130"',
        "sec-ch-ua-mobile": "?1",
        "ui-version": "2.0",
        "idfa": "undefined",
        "source": "okala",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/28.0 Chrome/130.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "metrix_user_id": "undefined",
        "session-id": str(uuid.uuid4()),
        "Origin": "https://www.okala.com",
        "Referer": "https://www.okala.com/",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        "Priority": "u=1, i"
    }
    
    payload = {
        "mobile": phone,
        "confirmTerms": True,
        "notRobot": False,
        "ValidationCodeCreateReason": 5,
        "OtpApp": 0,
        "deviceTypeCode": 7,
        "IsAppOnly": False
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://apigateway.okala.com/api/voyager/C/CustomerAccount/OTPRegister",
                json=payload,
                headers=headers,
                timeout=30
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("success", False)
                return False
    except Exception as e:
        logger.error(f"خطا در ارسال OTP: {str(e)}")
        return False

async def verify_otp(phone, otp_code):
    headers = {
        "Host": "apigateway.okala.com",
        "sec-ch-ua-platform": "Android",
        "x-correlation-id": str(uuid.uuid4()),
        "sec-ch-ua": '"Not?A_Brand";v="99", "Samsung Internet";v="28.0", "Chromium";v="130"',
        "sec-ch-ua-mobile": "?1",
        "ui-version": "2.0",
        "idfa": "undefined",
        "source": "okala",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/28.0 Chrome/130.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded",
        "metrix_user_id": "undefined",
        "session-id": str(uuid.uuid4()),
        "Origin": "https://www.okala.com",
        "Referer": "https://www.okala.com/",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        "Priority": "u=1, i"
    }
    
    data = {
        "mobile_number": phone,
        "otp_code": otp_code,
        "grant_type": "customer_grant_type",
        "client_id": "customer_client_id",
        "client_secret": "u_M{'57j!%LI21#",
        "client_name": "customer_client_name",
        "device_type_code": "7",
        "loginDuration": "12027"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://apigateway.okala.com/api/v1/accounts/tokens",
                data=data,
                headers=headers,
                timeout=30
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return True, data.get("access_token"), data.get("refresh_token")
                return False, "خطا در احراز هویت", None
    except Exception as e:
        logger.error(f"خطا در تایید OTP: {str(e)}")
        return False, "خطای شبکه", None

async def set_password(access_token, password):
    headers = {
        "Host": "apigateway.okala.com",
        "sec-ch-ua-platform": "Android",
        "authorization": f"Bearer {access_token}",
        "x-correlation-id": str(uuid.uuid4()),
        "sec-ch-ua": '"Not?A_Brand";v="99", "Samsung Internet";v="28.0", "Chromium";v="130"',
        "sec-ch-ua-mobile": "?1",
        "ui-version": "2.0",
        "idfa": "undefined",
        "source": "okala",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/28.0 Chrome/130.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "metrix_user_id": "undefined",
        "session-id": str(uuid.uuid4()),
        "Origin": "https://www.okala.com",
        "Referer": "https://www.okala.com/",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        "Priority": "u=1, i"
    }
    
    payload = {
        "password": password,
        "reEnterPassword": password,
        "otp": None
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://apigateway.okala.com/api/voyager/C/CustomerAccount/SetPassword",
                json=payload,
                headers=headers,
                timeout=30
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("success", False)
                return False
    except Exception as e:
        logger.error(f"خطا در تنظیم رمز عبور: {str(e)}")
        return False

async def check_has_password(access_token, phone):
    url = f"https://apigateway.okala.com/api/voyager/C/CustomerAccount/CheckHasPassword?mobile={phone}"
    
    headers = {
        "Host": "apigateway.okala.com",
        "sec-ch-ua-platform": "Android",
        "authorization": f"Bearer {access_token}",
        "x-correlation-id": str(uuid.uuid4()),
        "sec-ch-ua": '"Not?A_Brand";v="99", "Samsung Internet";v="28.0", "Chromium";v="130"',
        "sec-ch-ua-mobile": "?1",
        "ui-version": "2.0",
        "idfa": "undefined",
        "source": "okala",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/28.0 Chrome/130.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded",
        "metrix_user_id": "undefined",
        "session-id": str(uuid.uuid4()),
        "Origin": "https://www.okala.com",
        "Referer": "https://www.okala.com/",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        "Priority": "u=1, i"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success") and data.get("data"):
                        return data["data"].get("hasPassword", False)
                return False
    except Exception as e:
        logger.error(f"خطا در بررسی وجود رمز: {str(e)}")
        return False

async def update_customer_profile(access_token, phone, first_name, last_name, email, birth_date_epoch):
    headers = {
        "Host": "apigateway.okala.com",
        "sec-ch-ua-platform": "Android",
        "authorization": f"Bearer {access_token}",
        "x-correlation-id": str(uuid.uuid4()),
        "sec-ch-ua": '"Not?A_Brand";v="99", "Samsung Internet";v="28.0", "Chromium";v="130"',
        "sec-ch-ua-mobile": "?1",
        "ui-version": "2.0",
        "idfa": "undefined",
        "source": "okala",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/28.0 Chrome/130.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "metrix_user_id": "undefined",
        "session-id": str(uuid.uuid4()),
        "Origin": "https://www.okala.com",
        "Referer": "https://www.okala.com/",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        "Priority": "u=1, i"
    }
    
    payload = {
        "birthDate": "",
        "birthDateEpoch": birth_date_epoch,
        "customerType": 0,
        "emailAddress": email,
        "firstName": first_name,
        "genderCode": 1,
        "genderTitle": "مذکر",
        "lastName": last_name,
        "gender": "male",
        "userName": phone,
        "mobilePhone": phone
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://apigateway.okala.com/api/voyager/C/CustomerAccount/UpdateCustomer",
                json=payload,
                headers=headers,
                timeout=30
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("success", False)
                return False
    except Exception as e:
        logger.error(f"خطا در به‌روزرسانی پروفایل: {str(e)}")
        return False

async def check_has_password_api(phone):
    """بررسی ثبت نام شماره در سامانه اکالا"""
    url = f"https://apigateway.okala.com/api/voyager/C/CustomerAccount/CheckHasPassword?mobile={phone}"
    
    headers = {
        "Host": "apigateway.okala.com",
        "sec-ch-ua-platform": "Android",
        "sec-ch-ua": '"Not?A_Brand";v="99", "Samsung Internet";v="28.0", "Chromium";v="130"',
        "sec-ch-ua-mobile": "?1",
        "ui-version": "2.0",
        "idfa": "undefined",
        "source": "okala",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/28.0 Chrome/130.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded",
        "metrix_user_id": "undefined",
        "x-correlation-id": str(uuid.uuid4()),
        "session-id": str(uuid.uuid4()),
        "Origin": "https://www.okala.com",
        "Referer": "https://www.okala.com/",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        "Priority": "u=1, i"
    }
    
    MAX_RETRIES = 2
    for attempt in range(MAX_RETRIES):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("success") and data.get("data") is not None:
                            return True, data["data"].get("hasPassword", False), None
                        else:
                            return False, False, f"پاسخ نامعتبر: {data}"
                    return False, False, f"کد خطا: {response.status}"
        except Exception as e:
            error_msg = f"خطای شبکه: {str(e)}"
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(0.5)
    return False, False, error_msg

async def login_okala(phone, password):
    """ورود به سیستم اکالا با شماره و رمز"""
    session_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    
    headers = {
        "Host": "apigateway.okala.com",
        "sec-ch-ua-platform": "Android",
        "sec-ch-ua": '"Not?A_Brand";v="99", "Samsung Internet";v="28.0", "Chromium";v="130"',
        "sec-ch-ua-mobile": "?1",
        "ui-version": "2.0",
        "idfa": "undefined",
        "source": "okala",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/28.0 Chrome/130.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded",
        "metrix_user_id": "undefined",
        "Origin": "https://www.okala.com",
        "Referer": "https://www.okala.com/",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        "Priority": "u=1, i",
        "x-correlation-id": correlation_id,
        "session-id": session_id
    }
    
    data = {
        "grant_type": "customer_password_grant_type",
        "client_id": "customer_client_id",
        "client_secret": "u_M{'57j!%LI21#",
        "client_name": "customer_client_name",
        "device_type_code": "7",
        "loginDuration": "21364",
        "mobile_number": phone,
        "password": password
    }
    
    MAX_RETRIES = 2
    for attempt in range(MAX_RETRIES):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://apigateway.okala.com/api/v1/accounts/tokens",
                    data=data,
                    headers=headers,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        access_token = data.get("access_token")
                        refresh_token = data.get("refresh_token")
                        
                        # محاسبه زمان انقضا (60 دقیقه)
                        expires_at = time.time() + 3600
                        
                        return True, access_token, refresh_token, expires_at
                    
                    # پردازش خطاها
                    if response.text:
                        try:
                            error_data = await response.json()
                            error_code = error_data.get("error", "")
                            error_desc = error_data.get("error_description", "").lower()
                            
                            if error_code == "invalid_grant":
                                if "user name or password is incorrect" in error_desc:
                                    return False, "رمز عبور اشتباه است", None, None
                                elif "password" in error_desc:
                                    return False, "رمز عبور اشتباه است", None, None
                                elif "mobile" in error_desc or "number" in error_desc:
                                    return False, "شماره تلفن اشتباه است", None, None
                                else:
                                    return False, f"خطای اعتبارسنجی: {error_desc}", None, None
                            else:
                                return False, f"{error_code}: {error_desc}", None, None
                        except:
                            text = await response.text()
                            return False, f"کد خطا: {response.status} - پاسخ: {text[:100]}", None, None
                    return False, f"کد خطا: {response.status}", None, None
        
        except Exception as e:
            error_msg = f"خطای شبکه: {str(e)}"
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(0.5)
    
    return False, error_msg, None, None

async def refresh_token(refresh_token):
    """تمدید توکن دسترسی با استفاده از توکن تمدید"""
    session_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    
    headers = {
        "Host": "apigateway.okala.com",
        "sec-ch-ua-platform": "Android",
        "sec-ch-ua": '"Not?A_Brand";v="99", "Samsung Internet";v="28.0", "Chromium";v="130"',
        "sec-ch-ua-mobile": "?1",
        "ui-version": "2.0",
        "idfa": "undefined",
        "source": "okala",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/28.0 Chrome/130.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded",
        "metrix_user_id": "undefined",
        "x-correlation-id": correlation_id,
        "session-id": session_id,
        "Origin": "https://www.okala.com",
        "Referer": "https://www.okala.com/",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        "Priority": "u=1, i"
    }
    
    data = {
        "grant_type": "refresh_token",
        "client_id": "customer_client_id",
        "client_secret": "u_M{'57j!%LI21#",
        "refresh_token": refresh_token
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://apigateway.okala.com/api/v1/accounts/tokens",
                data=data,
                headers=headers,
                timeout=30
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    access_token = data.get("access_token")
                    new_refresh_token = data.get("refresh_token")
                    
                    # محاسبه زمان انقضا (60 دقیقه)
                    expires_at = time.time() + 3600
                    
                    return True, access_token, new_refresh_token, expires_at
                return False, "خطا در تمدید توکن", None, None
    except Exception as e:
        logger.error(f"خطا در تمدید توکن: {str(e)}")
        return False, f"خطای شبکه: {str(e)}", None, None

async def add_address(access_token, city_id, session_id, correlation_id):
    """افزودن آدرس جدید"""
    headers = {
        "Host": "apigateway.okala.com",
        "sec-ch-ua-platform": "Android",
        "authorization": f"Bearer {access_token}",
        "x-correlation-id": correlation_id,
        "sec-ch-ua": '"Not?A_Brand";v="99", "Samsung Internet";v="28.0", "Chromium";v="130"',
        "sec-ch-ua-mobile": "?1",
        "ui-version": "2.0",
        "idfa": "undefined",
        "source": "okala",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/28.0 Chrome/130.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "metrix_user_id": "undefined",
        "session-id": session_id,
        "Origin": "https://www.okala.com",
        "Referer": "https://www.okala.com/",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        "Priority": "u=1, i"
    }
    
    # مختصات مرکز شهر
    city_coordinates = {
        129: (35.701150029027964, 51.34254455566406),  # تهران
        200: (35.82731318274767, 50.97953688121074),   # کرج
        97: (32.655982553833184, 51.67502373749757),   # اصفهان
        140: (29.55689049, 52.5291214),                # شیراز
        56: (36.31043243, 59.57567215),                # مشهد
        131: (38.0792923, 46.28915024),                # تبریز
        126: (34.59394836, 50.87429047)                # قم
    }
    
    lat, lng = city_coordinates.get(city_id, (35.701150029027964, 51.34254455566406))
    
    # شناسه‌های نوع آدرس
    address_types = {
        "home": 1,
        "work": 2,
        "other": 3
    }
    
    payload = {
        "id": 0,
        "customerId": 0,
        "mobilePhone": "09300000000",
        "ShoppingSectorPartId": "0",
        "shoppingSectorId": "0",
        "plaque": "۱۰",
        "unit": "۲",
        "lat": lat,
        "lng": lng,
        "title": "آدرس اصلی",
        "addressTypeId": address_types["home"],
        "oprationDuration": 28048,
        "address": "مرکز شهر",
        "mapPlatform": "ParsiMap",
        "postalCode": "1234567890"
    }
    
    MAX_RETRIES = 2
    for attempt in range(MAX_RETRIES):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"https://apigateway.okala.com/api/voyager/C/CustomerAccount/AddAddress/",
                    json=payload,
                    headers=headers,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("success", False):
                            return True, data.get("data")
                        else:
                            error_msg = data.get("message", "خطای نامشخص از سرور")
                            logger.error(f"خطا در افزودن آدرس: {error_msg}")
                            return False, error_msg
                    elif response.status == 401 and attempt < MAX_RETRIES - 1:
                        logger.warning(f"خطای 401 در افزودن آدرس، تلاش مجدد: {attempt+1}")
                        await asyncio.sleep(1)
                        continue
                    return False, f"کد خطا: {response.status}"
        except Exception as e:
            logger.error(f"خطا در افزودن آدرس: {str(e)}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(1)
    return False, "خطا در افزودن آدرس پس از چندین تلاش"

async def add_to_cart(access_token, session_id, correlation_id, store_id, product_id, quantity=1):
    """افزودن محصول به سبد خرید"""
    headers = {
        "Host": "apigateway.okala.com",
        "sec-ch-ua-platform": "Android",
        "authorization": f"Bearer {access_token}",
        "x-correlation-id": correlation_id,
        "sec-ch-ua": '"Not?A_Brand";v="99", "Samsung Internet";v="28.0", "Chromium";v="130"',
        "sec-ch-ua-mobile": "?1",
        "ui-version": "2.0",
        "idfa": "undefined",
        "source": "okala",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/28.0 Chrome/130.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "metrix_user_id": "undefined",
        "session-id": session_id,
        "Origin": "https://www.okala.com",
        "Referer": "https://www.okala.com/",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        "Priority": "u=1, i"
    }
    
    payload = {
        "storeId": store_id,
        "productId": product_id,
        "quantity": quantity,
        "isSupplier": False,
        "replaceItemMethodCode": -1,
        "sectorId": "0",
        "sectorPartId": "0",
        "productStoreId": "0",
        "queryId": None
    }
    
    MAX_RETRIES = 2
    for attempt in range(MAX_RETRIES):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://apigateway.okala.com/api/Basket/v2/ShoppingCart/AddToShoppingCart",
                    json=payload,
                    headers=headers,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        return True
                    elif response.status == 401 and attempt < MAX_RETRIES - 1:
                        logger.warning(f"خطای 401 در افزودن به سبد، تلاش مجدد: {attempt+1}")
                        await asyncio.sleep(0.2)
                        continue
                    logger.error(f"خطا در افزودن به سبد خرید: کد وضعیت {response.status}, پاسخ: {response.text[:200]}")
                    return False
        except Exception as e:
            logger.error(f"خطا در افزودن به سبد خرید: {str(e)}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(0.2)
    return False

async def get_discounts(token, cerberus_id):
    if not cerberus_id:
        return None
        
    url = f"https://apigateway.okala.com/api/discount/v1/discounts/customer/{cerberus_id}"
    
    headers = {
        "Host": "apigateway.okala.com",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/28.0 Chrome/130.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.okala.com",
        "Referer": "https://www.okala.com/",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        "authorization": f"Bearer {token}",
        "x-correlation-id": str(uuid.uuid4()),
        "session-id": str(uuid.uuid4())
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    return await response.json()
                return None
    except Exception as e:
        logger.error(f"{EMOJI['error']} خطا در دریافت تخفیف‌ها: {str(e)}")
        return None

def format_discount_info(discounts):
    if not discounts or not discounts.get("success") or not discounts.get("data"):
        return f"{EMOJI['error']} ندارد"
    
    active_discounts = [d for d in discounts["data"] if d.get("isActive") and not d.get("isUsed")]
    
    if not active_discounts:
        return f"{EMOJI['error']} ندارد"
    
    discount_info = []
    for d in active_discounts:
        code = d.get("code", "نامشخص")
        amount = f"{d.get('discountAmount', 0):,}".replace(",", ",")
        min_amount = f"{d.get('minimumFactoreAmount', 0):,}".replace(",", ",")
        
        # استخراج زمان انقضای تخفیف
        expiry_text = ""
        expiration_date = d.get("expirationDate")
        if expiration_date:
            try:
                # تبدیل رشته تاریخ به شیء datetime
                expiry_dt = datetime.fromisoformat(expiration_date.replace('Z', '+00:00'))
                
                # تنظیم تایم‌زون به UTC
                if expiry_dt.tzinfo is None:
                    expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
                
                # محاسبه زمان باقی‌مانده تا انقضا
                now = datetime.now(timezone.utc)
                time_left = expiry_dt - now
                
                if time_left.total_seconds() <= 0:
                    expiry_text = "منقضی شده"
                else:
                    days = time_left.days
                    hours, remainder = divmod(time_left.seconds, 3600)
                    minutes = remainder // 60
                    
                    if days > 0:
                        expiry_text = f"{days} روز و {hours} ساعت"
                    elif hours > 0:
                        expiry_text = f"{hours} ساعت و {minutes} دقیقه"
                    else:
                        expiry_text = f"{minutes} دقیقه"
            except Exception as e:
                logger.error(f"خطا در محاسبه زمان انقضا: {str(e)}")
                expiry_text = "نامشخص"
        else:
            expiry_text = "نامحدود"
        
        discount_info.append(f"{code} (مبلغ: {amount} ریال | حداقل: {min_amount} ریال | انقضا: {expiry_text})")
    
    return f"{EMOJI['discount']} دارد ({' - '.join(discount_info)})"

def check_token_validity(token):
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        exp_time = payload.get("exp", 0)
        remaining_time = exp_time - time.time()
        return remaining_time > 0, payload
    except Exception as e:
        return False, None

# ترافیک شهرها با نام محصولات
CITY_TRAFFIC = {
    # تهران
    129: [
        {"store_id": 10007, "product_id": 658033, "quantity": 1, "name": "اسپاگتی قطر 1.2 زرماکارون 700 گرمی"},
        {"store_id": 10007, "product_id": 15976, "quantity": 1, "name": "اسپاگتی 1.2 رشته‌ای 700 گرمی مانا"},
        {"store_id": 10007, "product_id": 644227, "quantity": 1, "name": "رب گوجه فرنگی رعنا 800 گرمی"},
        {"store_id": 10007, "product_id": 661450, "quantity": 1, "name": "ماكارونی فرمي پيكولی زرماکارون 500 گرمی"},
        {"store_id": 10007, "product_id": 17674, "quantity": 1, "name": "رب گوجه فرنگی چین چین 700 گرمی"},
        {"store_id": 10007, "product_id": 6018, "quantity": 1, "name": "اسپاگتی قطر 1.2 زرماکارون 700 گرمی"},
        {"store_id": 10007, "product_id": 15975, "quantity": 1, "name": "ماکارونی فرمی سیم تلفنی 500 گرمی مانا"},
        {"store_id": 10007, "product_id": 15556, "quantity": 1, "name": "اسپاگتی مدل 1/2 زرماكارون 500 گرمی"},
        {"store_id": 10007, "product_id": 16542, "quantity": 1, "name": "ماکارونی فرمی بریده 500 گرمی مانا"},
        {"store_id": 10007, "product_id": 389, "quantity": 1, "name": "ماکارونی فرمی شلز زر ماکارون 500 گرمی"}
    ],
    # مشهد
    56: [
        {"store_id": 4521, "product_id": 18765, "quantity": 1, "name": "روغن نباتی جامد صالحین 900 گرمی"},
        {"store_id": 4521, "product_id": 19872, "quantity": 1, "name": "چای گلستان ممتاز 450 گرمی"},
        {"store_id": 4521, "product_id": 20543, "quantity": 1, "name": "پنیر پیتزا پگاه 200 گرمی"},
        {"store_id": 4521, "product_id": 21321, "quantity": 1, "name": "ماست میهن 1 کیلویی"},
        {"store_id": 4521, "product_id": 22109, "quantity": 1, "name": "پنیر لیقوان آلا 400 گرمی"}
    ],
    # تبریز
    131: [
        {"store_id": 3876, "product_id": 15432, "quantity": 1, "name": "آجیل مخلوط تبریزی 500 گرمی"},
        {"store_id": 3876, "product_id": 16218, "quantity": 1, "name": "حلوای کنجدی شاد گل 500 گرمی"},
        {"store_id": 3876, "product_id": 17005, "quantity": 1, "name": "کیک یزدی نونوش 6 عددی"},
        {"store_id": 3876, "product_id": 17891, "quantity": 1, "name": "سوهان عسلی قم 400 گرمی"},
        {"store_id": 3876, "product_id": 18677, "quantity": 1, "name": "نبات چوبی زعفرانی 500 گرمی"}
    ],
    # کرج
    200: [
        {"store_id": 4150, "product_id": 13245, "quantity": 1, "name": "پفک نمکی مزمز 150 گرمی"},
        {"store_id": 4150, "product_id": 14132, "quantity": 1, "name": "چیپس سیب زمینی چی توز 150 گرمی"},
        {"store_id": 4150, "product_id": 15019, "quantity": 1, "name": "آب معدنی دماوند 1.5 لیتری"},
        {"store_id": 4150, "product_id": 15906, "quantity": 1, "name": "نوشابه زمزم پرتقالی 1.5 لیتری"},
        {"store_id": 4150, "product_id": 16793, "quantity": 1, "name": "دوغ عالیس بدون گاز 1 لیتری"}
    ],
    # قم
    126: [
        {"store_id": 3987, "product_id": 17654, "quantity": 1, "name": "سوهان عسلی قم 400 گرمی"},
        {"store_id": 3987, "product_id": 18541, "quantity": 1, "name": "حلوای ارده کنجد 500 گرمی"},
        {"store_id": 3987, "product_id": 19428, "quantity": 1, "name": "نبات چوبی زعفرانی 300 گرمی"},
        {"store_id": 3987, "product_id": 20315, "quantity": 1, "name": "سوهان عسلی رژیمی 250 گرمی"},
        {"store_id": 3987, "product_id": 21202, "quantity": 1, "name": "کیک یزدی نونوش 6 عددی"}
    ],
    # اصفهان
    97: [
        {"store_id": 4265, "product_id": 14321, "quantity": 1, "name": "گز اصفهان سوهان 400 گرمی"},
        {"store_id": 4265, "product_id": 15208, "quantity": 1, "name": "پولکی نعنایی 200 گرمی"},
        {"store_id": 4265, "product_id": 16095, "quantity": 1, "name": "سوهان عسلی اصفهانی 350 گرمی"},
        {"store_id": 4265, "product_id": 16982, "quantity": 1, "name": "حلوای کنجدی شاد گل 500 گرمی"},
        {"store_id": 4265, "product_id": 17869, "quantity": 1, "name": "نبات چوبی زعفرانی 400 گرمی"}
    ],
    # شیراز
    140: [
        {"store_id": 4372, "product_id": 16543, "quantity": 1, "name": "حلوا شکری شیرازی 500 گرمی"},
        {"store_id": 4372, "product_id": 17430, "quantity": 1, "name": "مسقطی شیرازی 400 گرمی"},
        {"store_id": 4372, "product_id": 18317, "quantity": 1, "name": "کلوچه شیرازی 500 گرمی"},
        {"store_id": 4372, "product_id": 19204, "quantity": 1, "name": "نقل بیدمشکی 300 گرمی"},
        {"store_id": 4372, "product_id": 20091, "quantity": 1, "name": "حلوا ارده کنجدی 450 گرمی"}
    ],
    # همه شهرها (پیش‌فرض تهران)
    0: [
        {"store_id": 10007, "product_id": 658033, "quantity": 1, "name": "اسپاگتی قطر 1.2 زرماکارون 700 گرمی"},
        {"store_id": 10007, "product_id": 15976, "quantity": 1, "name": "اسپاگتی 1.2 رشته‌ای 700 گرمی مانا"},
        {"store_id": 10007, "product_id": 644227, "quantity": 1, "name": "رب گوجه فرنگی رعنا 800 گرمی"},
        {"store_id": 10007, "product_id": 661450, "quantity": 1, "name": "ماكارونی فرمي پيكولی زرماکارون 500 گرمی"},
        {"store_id": 10007, "product_id": 17674, "quantity": 1, "name": "رب گوجه فرنگی چین چین 700 گرمی"}
    ]
}

# توابع جدید برای سبد خرید
async def get_store_products(access_token, session_id, correlation_id, store_id):
    """دریافت محصولات فروشگاه"""
    headers = {
        "Host": "apigateway.okala.com",
        "sec-ch-ua-platform": "Android",
        "authorization": f"Bearer {access_token}",
        "x-correlation-id": correlation_id,
        "sec-ch-ua": '"Not?A_Brand";v="99", "Samsung Internet";v="28.0", "Chromium";v="130"',
        "sec-ch-ua-mobile": "?1",
        "ui-version": "2.0",
        "idfa": "undefined",
        "source": "okala",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/28.0 Chrome/130.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "metrix_user_id": "undefined",
        "session-id": session_id,
        "Origin": "https://www.okala.com",
        "Referer": "https://www.okala.com/",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        "Priority": "u=1, i"
    }
    
    url = f"https://apigateway.okala.com/api/Promotion/v2/Carousel/GetCarouselOfferSingleStore?CarouselId=110335&HasQuantity=true&Page=1&Take=50&storeId={store_id}&excludeShoppingCard=true"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("entities", [])
                return []
    except Exception as e:
        logger.error(f"خطا در دریافت محصولات فروشگاه: {str(e)}")
        return []

async def add_random_products_to_cart(access_token, session_id, correlation_id, store_id, min_total_price=2000000):
    """افزودن محصولات تصادفی به سبد خرید تا رسیدن به حداقل مبلغ"""
    products = await get_store_products(access_token, session_id, correlation_id, store_id)
    if not products:
        return 0, 0, [], []
    
    # مخلوط کردن لیست محصولات
    random.shuffle(products)
    added_products = []
    failed_products = []
    total_price = 0
    
    for product in products:
        if total_price >= min_total_price:
            break
            
        product_id = product["id"]
        quantity = 1
        
        # افزودن محصول به سبد خرید
        success = await add_to_cart(access_token, session_id, correlation_id, store_id, product_id, quantity)
        if success:
            price = product.get("okPrice", product.get("price", 0))
            total_price += price
            added_products.append({
                "id": product_id,
                "name": product.get("name", "نامشخص"),
                "price": price
            })
        else:
            failed_products.append({
                "id": product_id,
                "name": product.get("name", "نامشخص"),
                "price": product.get("okPrice", product.get("price", 0))
            })
        await asyncio.sleep(0.2)  # تاخیر کمتر برای افزایش سرعت
    
    return len(added_products), total_price, added_products, failed_products

async def set_active_store(access_token, session_id, correlation_id, store_id):
    """تنظیم فروشگاه فعال"""
    headers = {
        "Host": "apigateway.okala.com",
        "sec-ch-ua-platform": "Android",
        "authorization": f"Bearer {access_token}",
        "x-correlation-id": correlation_id,
        "sec-ch-ua": '"Not?A_Brand";v="99", "Samsung Internet";v="28.0", "Chromium";v="130"',
        "sec-ch-ua-mobile": "?1",
        "ui-version": "2.0",
        "idfa": "undefined",
        "source": "okala",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/28.0 Chrome/130.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "metrix_user_id": "undefined",
        "session-id": session_id,
        "Origin": "https://www.okala.com",
        "Referer": "https://www.okala.com/",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        "Priority": "u=1, i"
    }
    
    payload = {
        "storeId": store_id
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://apigateway.okala.com/api/Basket/v2/ShoppingCart/SetActiveStore",
                json=payload,
                headers=headers,
                timeout=30
            ) as response:
                return response.status == 200
    except Exception as e:
        logger.error(f"خطا در تنظیم فروشگاه فعال: {str(e)}")
        return False

async def verify_basket(access_token, session_id, correlation_id, store_id):
    """بررسی وجود سبد خرید"""
    headers = {
        "Host": "apigateway.okala.com",
        "sec-ch-ua-platform": "Android",
        "authorization": f"Bearer {access_token}",
        "x-correlation-id": correlation_id,
        "sec-ch-ua": '"Not?A_Brand";v="99", "Samsung Internet";v="28.0", "Chromium";v="130"',
        "sec-ch-ua-mobile": "?1",
        "ui-version": "2.0",
        "idfa": "undefined",
        "source": "okala",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/28.0 Chrome/130.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "metrix_user_id": "undefined",
        "session-id": session_id,
        "Origin": "https://www.okala.com",
        "Referer": "https://www.okala.com/",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        "Priority": "u=1, i"
    }
    
    url = f"https://apigateway.okala.com/api/Basket/v2/ShoppingCart/GetActiveShoppingCart?storeId={store_id}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data") and len(data["data"].get("items", [])) > 0
                return False
    except Exception as e:
        logger.error(f"خطا در بررسی سبد خرید: {str(e)}")
        return False

# کیبوردها
def main_menu_keyboard(user_id):
    builder = ReplyKeyboardBuilder()
    builder.button(text=f"{EMOJI['start_process']} چک کردن خط اکالا")
    builder.button(text=f"{EMOJI['register']} ثبت نام")
    builder.button(text=f"{EMOJI['basket']} تشکیل سبد خرید")
    builder.button(text=f"{EMOJI['support']} ارتباط با پشتیبانی")
    
    # نمایش لیست شماره‌ها فقط در صورت وجود داده
    reg_phones = db.get_registration_phones(user_id)
    city_id, basket_lists = db.get_basket_data(user_id)
    if reg_phones or basket_lists:
        builder.button(text=f"{EMOJI['list']} دریافت لیست شماره‌ها")
    
    if user_id in ADMIN_IDS or user_id == OWNER_ID:
        builder.button(text=f"{EMOJI['admin']} تنظیمات")
        
    builder.button(text=f"{EMOJI['main_menu']} منوی اصلی")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup(resize_keyboard=True)

def start_process_keyboard(user_id):
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{EMOJI['check']} چک کردن با رمز", callback_data="check_with_password")
    
    # نمایش گزینه توکن فقط برای ادمین‌ها و مالک
    if user_id in ADMIN_IDS or user_id == OWNER_ID:
        builder.button(text=f"{EMOJI['token']} چک کردن با توکن (مخصوص ادمین)", callback_data="check_with_token")
    
    builder.button(text=f"{EMOJI['cancel']} انصراف", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()

def cancel_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{EMOJI['cancel']} انصراف", callback_data="cancel")
    return builder.as_markup()

def otp_resend_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{EMOJI['resend']} ارسال مجدد کد", callback_data="resend_otp")
    builder.button(text=f"{EMOJI['cancel']} انصراف", callback_data="cancel_register")
    builder.adjust(1)
    return builder.as_markup()

def after_list_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{EMOJI['success']} تایید", callback_data="confirm_lists")
    builder.button(text=f"{EMOJI['list']} ادامه", callback_data="add_another_list")
    builder.button(text=f"{EMOJI['cancel']} انصراف", callback_data="cancel")
    builder.adjust(2, 1)
    return builder.as_markup()

def start_check_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{EMOJI['process']} شروع", callback_data="start_checking")
    builder.button(text=f"{EMOJI['cancel']} انصراف", callback_data="cancel")
    return builder.as_markup()

def admin_settings_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{EMOJI['on']} وضعیت ربات", callback_data="bot_status")
    builder.button(text=f"{EMOJI['vip']} مدیریت کاربران ویژه", callback_data="manage_vip")
    builder.button(text=f"{EMOJI['stats']} آمار کاربران", callback_data="user_stats_menu")
    builder.button(text=f"{EMOJI['back']} بازگشت", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

def vip_management_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{EMOJI['vip']} افزودن کاربر ویژه", callback_data="add_vip")
    builder.button(text=f"{EMOJI['error']} حذف کاربر ویژه", callback_data="remove_vip")
    builder.button(text=f"{EMOJI['list']} لیست کاربران ویژه", callback_data="list_vip")
    builder.button(text=f"{EMOJI['back']} بازگشت", callback_data="back_to_admin")
    builder.adjust(2)
    return builder.as_markup()

def register_actions_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{EMOJI['success']} ادامه ثبت نام", callback_data="continue_register")
    builder.button(text=f"{EMOJI['list']} دریافت لیست شماره‌ها", callback_data="get_phones_list")
    builder.button(text=f"{EMOJI['stop']} توقف", callback_data="stop_register")
    builder.adjust(1)
    return builder.as_markup()

def password_options_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{EMOJI['password']} استفاده از رمز قبلی", callback_data="use_previous_password")
    builder.button(text=f"{EMOJI['password']} رمز جدید", callback_data="new_password")
    builder.button(text=f"{EMOJI['cancel']} انصراف", callback_data="cancel_register")
    builder.adjust(1)
    return builder.as_markup()

def city_selection_keyboard():
    builder = InlineKeyboardBuilder()
    for city_name in CITIES:
        builder.button(text=city_name, callback_data=f"city_{city_name}")
    builder.button(text=f"{EMOJI['cancel']} انصراف", callback_data="cancel")
    builder.adjust(2, 2, 2, 2, 1)
    return builder.as_markup()

def basket_list_actions_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{EMOJI['password']} اصلاح رمز", callback_data="modify_password")
    builder.button(text=f"{EMOJI['list']} لیست جدید", callback_data="new_list")
    builder.button(text=f"{EMOJI['process']} توقف و شروع عملیات", callback_data="start_basket")
    builder.button(text=f"{EMOJI['cancel']} انصراف", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()

def register_cancel_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{EMOJI['stop']} پایان عملیات", callback_data="cancel_register")
    return builder.as_markup()

# ===========================================
# هندلرهای اصلی
# ===========================================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    if not is_user_allowed(user_id):
        await message.answer(
            "⛔ دسترسی محدود!\n\n"
            "شما مجوز استفاده از این ربات را ندارید.\n"
            "برای کسب اطلاعات بیشتر با پشتیبانی تماس بگیرید."
        )
        return
        
    role = get_user_role(user_id)
    await message.answer(
        f"👋 به ربات اکالا خوش آمدید!\n"
        f"👤 نقش شما: {role}\n\n"
        f"امکانات ربات:\n"
        f"{EMOJI['check']} بررسی حساب‌های اکالا\n"
        f"{EMOJI['register']} ثبت نام جدید\n"
        f"{EMOJI['basket']} تشکیل سبد خرید\n\n"
        f"لطفا یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=main_menu_keyboard(user_id)
    )

@dp.message(F.text == f"{EMOJI['main_menu']} منوی اصلی")
async def main_menu(message: types.Message):
    user_id = message.from_user.id
    if not is_user_allowed(user_id):
        return
        
    role = get_user_role(user_id)
    await message.answer(
        f"{EMOJI['main_menu']} <b>منوی اصلی</b>\n"
        f"👤 نقش شما: {role}",
        reply_markup=main_menu_keyboard(user_id),
        parse_mode="HTML"
    )

@dp.message(F.text == f"{EMOJI['support']} ارتباط با پشتیبانی")
async def support(message: types.Message):
    user_id = message.from_user.id
    if not is_user_allowed(user_id):
        return
        
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{EMOJI['support']} ارتباط با پشتیبانی", url="tg://openmessage?user_id=5847378706")
    await message.answer(
        f"🛟 برای ارتباط با پشتیبانی روی دکمه زیر کلیک کنید:",
        reply_markup=builder.as_markup()
    )

@dp.message(F.text == f"{EMOJI['start_process']} چک کردن خط اکالا")
async def start_process(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_user_allowed(user_id):
        return
        
    await message.answer(
        f"{EMOJI['process']} <b>روش چک را انتخاب کنید:</b>",
        reply_markup=start_process_keyboard(user_id),
        parse_mode="HTML"
    )

@dp.message(F.text == f"{EMOJI['admin']} تنظیمات")
async def admin_settings(message: types.Message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS and user_id != OWNER_ID:
        await message.answer("⛔ فقط ادمین‌ها و مالک به این بخش دسترسی دارند!")
        return
        
    status = f"{EMOJI['on']} فعال" if BOT_ENABLED else f"{EMOJI['off']} غیرفعال"
    vip_users = db.get_vip_users()
    user_stats_count = len([uid for uid in db.get_user_stats(uid) for uid in [user_id]])  # Simplified
    
    await message.answer(
        f"⚙️ <b>پنل مدیریت ربات</b>\n\n"
        f"• وضعیت ربات: {status}\n"
        f"• تعداد کاربران ویژه: {len(vip_users)}\n"
        f"• تعداد کاربران ثبت شده: {user_stats_count}\n\n"
        f"لطفا یکی از گزینه‌ها را انتخاب کنید:",
        reply_markup=admin_settings_keyboard(),
        parse_mode="HTML"
    )

@dp.message(F.text == f"{EMOJI['register']} ثبت نام")
async def start_register(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_user_allowed(user_id):
        return
    
    # ذخیره داده‌های جلسه
    await state.update_data({
        "current_phone": "",
        "access_token": "",
        "passwords": []
    })
    
    await message.answer(
        f"{EMOJI['phone']} <b>لطفا شماره تلفن را ارسال کنید:</b>\n\n"
        f"• فرمت: 09xxxxxxxxx\n"
        f"• مثال: 09123456789\n\n"
        f"برای انصراف از دکمه زیر استفاده کنید:",
        reply_markup=register_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(RegisterState.waiting_for_phone)

@dp.message(RegisterState.waiting_for_phone)
async def process_register_phone(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    phone = message.text.strip()
    
    if not validate_phone(phone):
        await message.answer(
            f"{EMOJI['error']} <b>شماره تلفن نامعتبر است!</b>\n\n"
            f"• فرمت صحیح: 09xxxxxxxxx\n"
            f"• مثال: 09123456789\n\n"
            f"لطفا شماره را دوباره ارسال کنید:",
            reply_markup=register_cancel_keyboard(),
            parse_mode="HTML"
        )
        return
    
    # ذخیره شماره در حالت
    await state.update_data(current_phone=phone)
    
    # ارسال OTP
    if await send_otp(phone):
        await message.answer(
            f"{EMOJI['success']} <b>کد ورود با موفقیت ارسال شد</b>\n\n"
            f"لطفا کد دریافتی را ارسال کنید:",
            reply_markup=otp_resend_keyboard(),
            parse_mode="HTML"
        )
        await state.set_state(RegisterState.waiting_for_otp)
    else:
        await message.answer(
            f"{EMOJI['error']} <b>خطا در ارسال کد ورود!</b>\n\n"
            f"لطفا دقایقی دیگر مجددا تلاش کنید.",
            reply_markup=otp_resend_keyboard(),
            parse_mode="HTML"
        )

@dp.callback_query(F.data == "resend_otp", RegisterState.waiting_for_otp)
async def resend_otp_handler(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    phone = data.get("current_phone", "")
    
    if await send_otp(phone):
        await callback.message.answer(f"{EMOJI['success']} کد ورود مجددا ارسال شد. لطفا کد را وارد کنید:")
    else:
        await callback.message.answer(f"{EMOJI['error']} خطا در ارسال مجدد کد. لطفا دوباره تلاش کنید.")
    
    await callback.answer()

@dp.message(RegisterState.waiting_for_otp)
async def process_register_otp(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    otp_code = message.text.strip()
    data = await state.get_data()
    phone = data.get("current_phone", "")
    
    if len(otp_code) != 5 or not otp_code.isdigit():
        await message.answer(
            f"{EMOJI['error']} <b>کد وارد شده نامعتبر است!</b>\n\n"
            f"کد باید 5 رقمی و فقط شامل اعداد باشد.\n"
            f"لطفا مجددا کد را ارسال کنید:",
            reply_markup=otp_resend_keyboard(),
            parse_mode="HTML"
        )
        return
    
    success, access_token, refresh_token = await verify_otp(phone, otp_code)
    
    if success:
        await state.update_data(access_token=access_token)
        
        # بررسی وجود رمز عبور
        if await check_has_password(access_token, phone):
            await message.answer(
                f"{EMOJI['warning']} <b>این حساب از قبل رمز عبور دارد!</b>\n\n"
                f"شماره {phone} قبلا در سیستم اکالا ثبت نام کرده است.",
                reply_markup=register_cancel_keyboard(),
                parse_mode="HTML"
            )
            await state.set_state(RegisterState.waiting_for_phone)
            return
        
        # درخواست رمز عبور
        passwords = data.get("passwords", [])
        if passwords:
            await message.answer(
                f"{EMOJI['password']} <b>لطفا رمز عبور را وارد کنید:</b>\n\n"
                f"• حداقل 8 کاراکتر\n"
                f"• شامل حروف بزرگ و کوچک انگلیسی\n"
                f"• شامل حداقل یک عدد\n\n"
                f"یا از گزینه‌های زیر استفاده کنید:",
                reply_markup=password_options_keyboard(),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"{EMOJI['password']} <b>لطفا رمز عبور را وارد کنید:</b>\n\n"
                f"• حداقل 8 کاراکتر\n"
                f"• شامل حروف بزرگ و کوچک انگلیسی\n"
                f"• شامل حداقل یک عدد",
                reply_markup=register_cancel_keyboard(),
                parse_mode="HTML"
            )
        
        await state.set_state(RegisterState.waiting_for_password)
    else:
        await message.answer(
            f"{EMOJI['error']} <b>کد وارد شده نامعتبر یا منقضی شده است!</b>\n\n"
            f"لطفا مجددا کد را ارسال کنید:",
            reply_markup=otp_resend_keyboard(),
            parse_mode="HTML"
        )

@dp.callback_query(F.data == "use_previous_password")
async def use_previous_password(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    passwords = data.get("passwords", [])
    
    if not passwords:
        await callback.answer("هیچ رمز قبلی وجود ندارد!", show_alert=True)
        return
    
    # استفاده از آخرین رمز
    password = passwords[-1]
    await process_password_setting(user_id, password, callback, state)

@dp.message(RegisterState.waiting_for_password)
async def process_register_password(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    password = message.text.strip()
    
    # اعتبارسنجی رمز عبور
    is_valid, error_msg = validate_password(password)
    if not is_valid:
        await message.answer(
            f"{EMOJI['error']} <b>{error_msg}</b>\n\n"
            f"لطفا رمز عبور معتبر وارد کنید:",
            reply_markup=register_cancel_keyboard(),
            parse_mode="HTML"
        )
        return
    
    await process_password_setting(user_id, password, message, state)

async def process_password_setting(user_id, password, source, state):
    data = await state.get_data()
    phone = data.get("current_phone", "")
    access_token = data.get("access_token", "")
    passwords = data.get("passwords", [])
    
    # افزودن رمز به تاریخچه
    if password not in passwords:
        passwords.append(password)
        await state.update_data(passwords=passwords)
    
    # تنظیم رمز عبور
    if await set_password(access_token, password):
        # تولید اطلاعات تصادفی
        first_name = generate_random_name()
        last_name = generate_random_lastname()
        email = generate_random_email()
        birth_date = generate_random_birthdate()
        
        # به‌روزرسانی پروفایل
        if await update_customer_profile(access_token, phone, first_name, last_name, email, birth_date):
            # ذخیره اطلاعات در پایگاه داده
            existing_phones = db.get_registration_phones(user_id)
            existing_phones.append({
                "phone": phone,
                "password": password,
                "first_name": first_name,
                "last_name": last_name,
                "email": email
            })
            db.save_registration_phones(user_id, existing_phones)
            
            if isinstance(source, types.Message):
                await source.answer(
                    f"{EMOJI['success']} <b>عملیات با موفقیت انجام شد!</b>\n\n"
                    f"• شماره: {phone}\n"
                    f"• رمز: {password}\n"
                    f"• نام: {first_name} {last_name}\n"
                    f"• ایمیل: {email}\n\n"
                    f"لطفا یکی از گزینه‌های زیر را انتخاب کنید:",
                    reply_markup=register_actions_keyboard(),
                    parse_mode="HTML"
                )
            else:
                await source.message.edit_text(
                    f"{EMOJI['success']} <b>عملیات با موفقیت انجام شد!</b>\n\n"
                    f"• شماره: {phone}\n"
                    f"• رمز: {password}\n"
                    f"• نام: {first_name} {last_name}\n"
                    f"• ایمیل: {email}\n\n"
                    f"لطفا یکی از گزینه‌های زیر را انتخاب کنید:",
                    reply_markup=register_actions_keyboard()
                )
                await source.answer()
            
            await state.set_state(RegisterState.waiting_for_next_action)
        else:
            error_msg = "خطا در تکمیل پروفایل"
            logger.error(f"خطا در تکمیل پروفایل برای {phone}: {error_msg}")
            if isinstance(source, types.Message):
                await source.answer(
                    f"{EMOJI['error']} <b>{error_msg}</b>\n\n"
                    f"لطفا دقایقی دیگر مجددا تلاش کنید.",
                    reply_markup=register_actions_keyboard(),
                    parse_mode="HTML"
                )
            else:
                await source.message.edit_text(
                    f"{EMOJI['error']} <b>{error_msg}</b>",
                    reply_markup=None
                )
                await source.message.answer(
                    "لطفا دقایقی دیگر مجددا تلاش کنید.",
                    reply_markup=register_actions_keyboard()
                )
                await source.answer()
            
            await state.set_state(RegisterState.waiting_for_next_action)
    else:
        error_msg = "خطا در تنظیم رمز عبور"
        logger.error(f"خطا در تنظیم رمز برای {phone}: {error_msg}")
        if isinstance(source, types.Message):
            await source.answer(
                f"{EMOJI['error']} <b>{error_msg}</b>\n\n"
                f"لطفا رمز دیگری انتخاب کنید:",
                reply_markup=password_options_keyboard(),
                parse_mode="HTML"
            )
        else:
            await source.message.edit_text(
                f"{EMOJI['error']} <b>{error_msg}</b>",
                reply_markup=None
            )
            await source.message.answer(
                "لطفا رمز دیگری انتخاب کنید:",
                reply_markup=password_options_keyboard()
            )
            await source.answer()

@dp.callback_query(F.data == "continue_register")
async def continue_register(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        f"{EMOJI['phone']} <b>لطفا شماره تلفن بعدی را ارسال کنید:</b>\n\n"
        f"• فرمت: 09xxxxxxxxx\n"
        f"• مثال: 09123456789",
        reply_markup=register_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(RegisterState.waiting_for_phone)
    await callback.answer()

@dp.callback_query(F.data == "get_phones_list")
async def get_phones_list(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    phones_data = db.get_registration_phones(user_id)
    
    if not phones_data:
        await callback.message.edit_text(
            f"{EMOJI['warning']} <b>هیچ شماره‌ای ثبت نشده است!</b>",
            reply_markup=register_actions_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    response = [f"{EMOJI['list']} <b>لیست شماره‌های ثبت شده:</b>\n"]
    for idx, data in enumerate(phones_data, 1):
        response.append(
            f"\n{idx}. {data['phone']}\n"
            f"   رمز: {data['password']}\n"
            f"   نام: {data['first_name']} {data['last_name']}\n"
            f"   ایمیل: {data['email']}"
        )
    
    response.append(f"\n\n{EMOJI['success']} <b>تعداد کل: {len(phones_data)}</b>")
    
    await callback.message.edit_text(
        "\n".join(response),
        reply_markup=register_actions_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "stop_register")
async def stop_register(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await callback.message.edit_text(
        f"{EMOJI['success']} <b>فرآیند ثبت نام متوقف شد.</b>",
        reply_markup=None
    )
    await callback.message.answer(
        f"{EMOJI['main_menu']} <b>منوی اصلی</b>",
        reply_markup=main_menu_keyboard(user_id),
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer()

# هندلرهای چک کردن خط اکالا
@dp.callback_query(F.data == "check_with_password")
async def check_with_password(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not is_user_allowed(user_id):
        await callback.answer("⛔ دسترسی محدود! شما مجاز به استفاده از این قابلیت نیستید.", show_alert=True)
        return
        
    await state.set_state(Form.waiting_for_phones)
    await callback.message.edit_text(
        f"{EMOJI['list']} <b>لطفا لیست اول خط‌های خود را ارسال کنید:</b>\n\n"
        f"• هر شماره در یک خط\n"
        f"• فقط شماره‌های معتبر\n"
        f"• مثال:\n09330986627\n09330986615",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(Form.waiting_for_phones)
async def process_phone_list(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    phones = message.text.split("\n")
    
    # اعتبارسنجی شماره‌ها
    valid_phones = []
    invalid_phones = []
    
    for phone in phones:
        phone = phone.strip()
        if len(phone) == 11 and phone.isdigit():
            valid_phones.append(phone)
        else:
            invalid_phones.append(phone)
    
    if not valid_phones:
        await message.answer(
            f"{EMOJI['error']} هیچ شماره معتبری پیدا نشد!\n"
            f"لطفا لیست شماره‌ها را دوباره ارسال کنید:",
            reply_markup=cancel_keyboard()
        )
        return
    
    # ذخیره لیست اول
    await state.update_data(lists=[(valid_phones, None)])
    
    # نمایش نتایج اعتبارسنجی
    response = f"{EMOJI['success']} <b>لیست اول دریافت شد!</b>\n"
    response += f"• تعداد شماره‌های معتبر: {len(valid_phones)}\n"
    
    if invalid_phones:
        response += f"• شماره‌های نامعتبر ({len(invalid_phones)}):\n"
        response += "\n".join(invalid_phones) + "\n\n"
    
    response += f"\n{EMOJI['password']} <b>لطفا رمز عبور مشترک را ارسال کنید:</b>"
    
    await message.answer(response, parse_mode="HTML")
    await state.set_state(Form.waiting_for_password)

@dp.message(Form.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
    password = message.text.strip()
    
    # اعتبارسنجی رمز عبور
    if len(password) < 4:
        await message.answer(
            f"{EMOJI['error']} رمز عبور باید حداقل ۴ کاراکتر باشد!\n"
            f"لطفا رمز عبور را دوباره ارسال کنید:",
            reply_markup=cancel_keyboard()
        )
        return
    
    # ذخیره رمز عبور برای لیست اول
    data = await state.get_data()
    first_list = data["lists"][0]
    data["lists"][0] = (first_list[0], password)
    await state.update_data(lists=data["lists"])
    
    await message.answer(
        f"{EMOJI['success']} <b>رمز عبور دریافت شد!</b>\n\n"
        f"آیا می‌خواهید لیست دیگری اضافه کنید؟",
        reply_markup=after_list_keyboard()
    )

@dp.callback_query(F.data == "add_another_list")
async def add_another_list(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        f"{EMOJI['list']} <b>لطفا لیست بعدی خط‌های خود را ارسال کنید:</b>\n\n"
        f"• هر شماره در یک خط\n"
        f"• فقط شماره‌های معتبر\n"
        f"• مثال:\n09330986627\n09330986615",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(Form.waiting_for_next_list)
    await callback.answer()

@dp.message(Form.waiting_for_next_list)
async def process_next_list(message: types.Message, state: FSMContext):
    phones = message.text.split("\n")
    
    # اعتبارسنجی شماره‌ها
    valid_phones = []
    invalid_phones = []
    
    for phone in phones:
        phone = phone.strip()
        if len(phone) == 11 and phone.isdigit():
            valid_phones.append(phone)
        else:
            invalid_phones.append(phone)
    
    if not valid_phones:
        await message.answer(
            f"{EMOJI['error']} هیچ شماره معتبری پیدا نشد!\n"
            f"لطفا لیست شماره‌ها را دوباره ارسال کنید:",
            reply_markup=cancel_keyboard()
        )
        return
    
    # ذخیره لیست جدید (بدون رمز)
    data = await state.get_data()
    data["lists"].append((valid_phones, None))
    await state.update_data(lists=data["lists"])
    
    # نمایش نتایج اعتبارسنجی
    response = f"{EMOJI['success']} <b>لیست جدید دریافت شد!</b>\n"
    response += f"• تعداد شماره‌های معتبر: {len(valid_phones)}\n"
    
    if invalid_phones:
        response += f"• شماره‌های نامعتبر ({len(invalid_phones)}):\n"
        response += "\n".join(invalid_phones) + "\n\n"
    
    response += f"\n{EMOJI['password']} <b>لطفا رمز عبور این لیست را ارسال کنید:</b>"
    
    await message.answer(response, parse_mode="HTML")
    await state.set_state(Form.waiting_for_next_password)

@dp.message(Form.waiting_for_next_password)
async def process_next_password(message: types.Message, state: FSMContext):
    password = message.text.strip()
    
    # اعتبارسنجی رمز عبور
    if len(password) < 4:
        await message.answer(
            f"{EMOJI['error']} رمز عبور باید حداقل ۴ کاراکتر باشد!\n"
            f"لطفا رمز عبور را دوباره ارسال کنید:",
            reply_markup=cancel_keyboard()
        )
        return
    
    # ذخیره رمز عبور برای آخرین لیست
    data = await state.get_data()
    last_list = data["lists"][-1]
    data["lists"][-1] = (last_list[0], password)
    await state.update_data(lists=data["lists"])
    
    # نمایش خلاصه
    total_numbers = sum(len(lst[0]) for lst in data["lists"])
    
    await message.answer(
        f"{EMOJI['success']} <b>لیست جدید با موفقیت اضافه شد!</b>\n\n"
        f"• تعداد لیست‌ها: {len(data['lists'])}\n"
        f"• تعداد کل شماره‌ها: {total_numbers}\n\n"
        f"آیا می‌خواهید لیست دیگری اضافه کنید؟",
        reply_markup=after_list_keyboard()
    )

@dp.callback_query(F.data == "confirm_lists")
async def confirm_lists(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    total_numbers = sum(len(lst[0]) for lst in data["lists"])
    
    await callback.message.edit_text(
        f"{EMOJI['success']} <b>اطلاعات کامل شد!</b>\n\n"
        f"• تعداد لیست‌ها: {len(data['lists'])}\n"
        f"• تعداد کل شماره‌ها: {total_numbers}\n\n"
        f"برای شروع بررسی دکمه شروع را بزنید:",
        reply_markup=start_check_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "start_checking")
async def start_checking(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not is_user_allowed(user_id):
        await callback.answer("⛔ دسترسی محدود! شما مجاز به استفاده از این قابلیت نیستید.", show_alert=True)
        return
        
    # دریافت داده‌ها از state
    data = await state.get_data()
    user_lists = data.get("lists", [])
    
    if not user_lists:
        await callback.answer(f"{EMOJI['error']} خطا: داده‌ای یافت نشد!", show_alert=True)
        return
    
    total_numbers = sum(len(lst[0]) for lst in user_lists)
    
    # ارسال پیام شروع
    msg = await callback.message.answer(
        f"{EMOJI['process']} <b>ربات شروع به فعالیت کرد!</b>\n"
        f"• در حال بررسی {total_numbers} شماره...\n"
        f"{EMOJI['clock']} لطفا چند دقیقه صبر کنید",
        parse_mode="HTML"
    )
    
    # پردازش واقعی شماره‌ها
    results = [f"{EMOJI['result']} <b>نتایج بررسی:</b>"]
    processed = 0
    success_count = 0
    fail_count = 0
    
    for list_idx, (phones, password) in enumerate(user_lists):
        for phone in phones:
            processed += 1
            # به روزرسانی وضعیت
            if processed % 3 == 0:
                await msg.edit_text(
                    f"{EMOJI['process']} <b>در حال پردازش...</b>\n"
                    f"• پیشرفت: {processed}/{total_numbers} ({processed/total_numbers*100:.1f}%)\n"
                    f"• آخرین شماره: {phone}",
                    parse_mode="HTML"
                )
            
            # بررسی ثبت نام شماره
            check_success, has_password, check_error = await check_has_password_api(phone)
            
            if not check_success:
                # اگر بررسی ناموفق بود، از لاگین استفاده می‌کنیم
                success, token_or_error, refresh_token, expires_at = await login_okala(phone, password)
                
                if success:
                    success_count += 1
                    # استخراج اطلاعات از توکن
                    is_valid, payload = check_token_validity(token_or_error)
                    cerberus_id = payload.get("cerberusId") if is_valid else None
                    
                    # دریافت تخفیف‌ها
                    discounts = await get_discounts(token_or_error, cerberus_id) if cerberus_id else None
                    discount_status = format_discount_info(discounts)
                    
                    results.append(
                        f"\n{EMOJI['phone']} <b>شماره:</b> {phone}\n"
                        f"{EMOJI['success']} <b>وضعیت ورود:</b> موفق\n"
                        f"{EMOJI['discount']} <b>کد تخفیف:</b> {discount_status}"
                    )
                    
                    # ذخیره توکن در پایگاه داده
                    db.save_token(phone, token_or_error, refresh_token, expires_at)
                    
                else:
                    fail_count += 1
                    results.append(
                        f"\n{EMOJI['phone']} <b>شماره:</b> {phone}\n"
                        f"{EMOJI['error']} <b>وضعیت ورود:</b> ناموفق\n"
                        f"{EMOJI['error']} <b>خطا:</b> {token_or_error}"
                    )
            
            else:
                if has_password:
                    # شماره ثبت نام کرده، لاگین را بررسی می‌کنیم
                    success, token_or_error, refresh_token, expires_at = await login_okala(phone, password)
                    
                    if success:
                        success_count += 1
                        # استخراج اطلاعات از توکن
                        is_valid, payload = check_token_validity(token_or_error)
                        cerberus_id = payload.get("cerberusId") if is_valid else None
                        
                        # دریافت تخفیف‌ها
                        discounts = await get_discounts(token_or_error, cerberus_id) if cerberus_id else None
                        discount_status = format_discount_info(discounts)
                        
                        results.append(
                            f"\n{EMOJI['phone']} <b>شماره:</b> {phone}\n"
                            f"{EMOJI['success']} <b>وضعیت ورود:</b> موفق\n"
                            f"{EMOJI['discount']} <b>کد تخفیف:</b> {discount_status}"
                        )
                        
                        # ذخیره توکن در پایگاه داده
                        db.save_token(phone, token_or_error, refresh_token, expires_at)
                        
                    else:
                        fail_count += 1
                        results.append(
                            f"\n{EMOJI['phone']} <b>شماره:</b> {phone}\n"
                            f"{EMOJI['error']} <b>وضعیت ورود:</b> ناموفق\n"
                            f"{EMOJI['error']} <b>خطا:</b> رمز عبور اشتباه است"
                        )
                else:
                    # شماره ثبت نام نکرده
                    fail_count += 1
                    results.append(
                        f"\n{EMOJI['phone']} <b>شماره:</b> {phone}\n"
                        f"{EMOJI['error']} <b>وضعیت ورود:</b> ناموفق\n"
                        f"{EMOJI['error']} <b>خطا:</b> این شماره در سامانه ثبت نام نکرده است"
                    )
            
            # تاخیر برای جلوگیری از محدودیت سرور
            await asyncio.sleep(0.5)  # کاهش تاخیر برای افزایش سرعت
    
    # به روزرسانی آمار کاربر
    db.update_user_stats(user_id, success_count > 0)
    
    # ارسال نتایج نهایی
    await msg.delete()
    await callback.message.answer(
        f"{EMOJI['success']} <b>عملیات با موفقیت انجام شد!</b>\n" + "\n".join(results),
        parse_mode="HTML"
    )
    
    # برگشت به منوی اصلی
    await callback.message.answer(
        f"{EMOJI['main_menu']} <b>منوی اصلی</b>",
        reply_markup=main_menu_keyboard(user_id),
        parse_mode="HTML"
    )
    
    await state.clear()
    await callback.answer()

# هندلرهای سبد خرید
@dp.message(F.text == f"{EMOJI['basket']} تشکیل سبد خرید")
async def start_basket(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_user_allowed(user_id):
        return
        
    await message.answer(
        f"{EMOJI['city']} <b>لطفا شهر مد نظر را انتخاب کنید:</b>",
        reply_markup=city_selection_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(BasketState.waiting_for_city)

@dp.callback_query(F.data.startswith("city_"), BasketState.waiting_for_city)
async def process_basket_city(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    city_name = callback.data.split("_")[1]
    city_info = CITIES.get(city_name)
    
    if not city_info:
        await callback.answer("خطا: شهر نامعتبر است!", show_alert=True)
        return
    
    # ذخیره اطلاعات شهر
    await state.update_data(city_id=city_info["id"], store_id=city_info["store_id"], lists=[])
    
    await callback.message.edit_text(
        f"{EMOJI['success']} <b>شهر با موفقیت انتخاب شد!</b>\n\n"
        f"• شهر: {city_name}\n"
        f"• فروشگاه: {city_info['store_name']}\n\n"
        f"لطفا لیست اول خط‌های خود را ارسال کنید:\n\n"
        f"• هر شماره در یک خط\n"
        f"• فقط شماره‌های معتبر\n"
        f"• مثال:\n09330986627\n09330986615",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(BasketState.waiting_for_phones)
    await callback.answer()

@dp.message(BasketState.waiting_for_phones)
async def process_basket_phones(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    phones = message.text.split("\n")
    
    # اعتبارسنجی شماره‌ها
    valid_phones = []
    invalid_phones = []
    
    for phone in phones:
        phone = phone.strip()
        if len(phone) == 11 and phone.isdigit():
            valid_phones.append(phone)
        else:
            invalid_phones.append(phone)
    
    if not valid_phones:
        await message.answer(
            f"{EMOJI['error']} هیچ شماره معتبری پیدا نشد!\n"
            f"لطفا لیست شماره‌ها را دوباره ارسال کنید:",
            reply_markup=cancel_keyboard()
        )
        return
    
    # ذخیره لیست اول
    await state.update_data(lists=[(valid_phones, None)])
    
    # نمایش نتایج اعتبارسنجی
    response = f"{EMOJI['success']} <b>لیست اول دریافت شد!</b>\n"
    response += f"• تعداد شماره‌های معتبر: {len(valid_phones)}\n"
    
    if invalid_phones:
        response += f"• شماره‌های نامعتبر ({len(invalid_phones)}):\n"
        response += "\n".join(invalid_phones) + "\n\n"
    
    response += f"\n{EMOJI['password']} <b>لطفا رمز عبور مشترک را ارسال کنید:</b>"
    
    await message.answer(response, parse_mode="HTML")
    await state.set_state(BasketState.waiting_for_password)

@dp.message(BasketState.waiting_for_password)
async def process_basket_password(message: types.Message, state: FSMContext):
    password = message.text.strip()
    
    # اعتبارسنجی رمز عبور
    if len(password) < 4:
        await message.answer(
            f"{EMOJI['error']} رمز عبور باید حداقل ۴ کاراکتر باشد!\n"
            f"لطفا رمز عبور را دوباره ارسال کنید:",
            reply_markup=cancel_keyboard()
        )
        return
    
    # ذخیره رمز عبور برای لیست اول
    data = await state.get_data()
    first_list = data["lists"][0]
    data["lists"][0] = (first_list[0], password)
    await state.update_data(lists=data["lists"])
    
    await message.answer(
        f"{EMOJI['success']} <b>رمز عبور دریافت شد!</b>\n\n"
        f"آیا می‌خواهید لیست دیگری اضافه کنید؟",
        reply_markup=basket_list_actions_keyboard()
    )

@dp.callback_query(F.data == "new_list")
async def add_another_basket_list(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        f"{EMOJI['list']} <b>لطفا لیست بعدی خط‌های خود را ارسال کنید:</b>\n\n"
        f"• هر شماره در یک خط\n"
        f"• فقط شماره‌های معتبر\n"
        f"• مثال:\n09330986627\n09330986615",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(BasketState.waiting_for_next_list)
    await callback.answer()

@dp.message(BasketState.waiting_for_next_list)
async def process_next_basket_list(message: types.Message, state: FSMContext):
    phones = message.text.split("\n")
    
    # اعتبارسنجی شماره‌ها
    valid_phones = []
    invalid_phones = []
    
    for phone in phones:
        phone = phone.strip()
        if len(phone) == 11 and phone.isdigit():
            valid_phones.append(phone)
        else:
            invalid_phones.append(phone)
    
    if not valid_phones:
        await message.answer(
            f"{EMOJI['error']} هیچ شماره معتبری پیدا نشد!\n"
            f"لطفا لیست شماره‌ها را دوباره ارسال کنید:",
            reply_markup=cancel_keyboard()
        )
        return
    
    # ذخیره لیست جدید (بدون رمز)
    data = await state.get_data()
    data["lists"].append((valid_phones, None))
    await state.update_data(lists=data["lists"])
    
    # نمایش نتایج اعتبارسنجی
    response = f"{EMOJI['success']} <b>لیست جدید دریافت شد!</b>\n"
    response += f"• تعداد شماره‌های معتبر: {len(valid_phones)}\n"
    
    if invalid_phones:
        response += f"• شماره‌های نامعتبر ({len(invalid_phones)}):\n"
        response += "\n".join(invalid_phones) + "\n\n"
    
    response += f"\n{EMOJI['password']} <b>لطفا رمز عبور این لیست را ارسال کنید:</b>"
    
    await message.answer(response, parse_mode="HTML")
    await state.set_state(BasketState.waiting_for_next_password)

@dp.message(BasketState.waiting_for_next_password)
async def process_next_basket_password(message: types.Message, state: FSMContext):
    password = message.text.strip()
    
    # اعتبارسنجی رمز عبور
    if len(password) < 4:
        await message.answer(
            f"{EMOJI['error']} رمز عبور باید حداقل ۴ کاراکتر باشد!\n"
            f"لطفا رمز عبور را دوباره ارسال کنید:",
            reply_markup=cancel_keyboard()
        )
        return
    
    # ذخیره رمز عبور برای آخرین لیست
    data = await state.get_data()
    last_list = data["lists"][-1]
    data["lists"][-1] = (last_list[0], password)
    await state.update_data(lists=data["lists"])
    
    # نمایش خلاصه
    total_numbers = sum(len(lst[0]) for lst in data["lists"])
    
    await message.answer(
        f"{EMOJI['success']} <b>لیست جدید با موفقیت اضافه شد!</b>\n\n"
        f"• تعداد لیست‌ها: {len(data['lists'])}\n"
        f"• تعداد کل شماره‌ها: {total_numbers}\n\n"
        f"آیا می‌خواهید لیست دیگری اضافه کنید؟",
        reply_markup=basket_list_actions_keyboard()
    )

@dp.callback_query(F.data == "start_basket")
async def start_basket_processing(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    city_id = data.get("city_id")
    store_id = data.get("store_id")
    user_lists = data.get("lists", [])
    
    if not user_lists or not city_id or not store_id:
        await callback.answer("خطا: داده‌ای برای پردازش یافت نشد!", show_alert=True)
        return
    
    total_numbers = sum(len(lst[0]) for lst in user_lists)
    
    # ذخیره داده‌ها در پایگاه داده
    db.save_basket_data(user_id, city_id, user_lists)
    
    # ارسال پیام شروع
    msg = await callback.message.answer(
        f"{EMOJI['process']} <b>تشکیل سبد خرید شروع شد!</b>\n"
        f"• در حال پردازش {total_numbers} شماره...\n"
        f"{EMOJI['clock']} لطفا چند دقیقه صبر کنید",
        parse_mode="HTML"
    )
    
    # پردازش واقعی شماره‌ها
    results = [f"{EMOJI['result']} <b>نتایج تشکیل سبد خرید:</b>"]
    processed = 0
    success_count = 0
    fail_count = 0
    fail_reasons = {}
    
    for list_idx, (phones, password) in enumerate(user_lists):
        for phone in phones:
            processed += 1
            # به روزرسانی وضعیت
            if processed % 3 == 0:
                await msg.edit_text(
                    f"{EMOJI['process']} <b>در حال پردازش...</b>\n"
                    f"• پیشرفت: {processed}/{total_numbers} ({processed/total_numbers*100:.1f}%)\n"
                    f"• آخرین شماره: {phone}",
                    parse_mode="HTML"
                )
            
            try:
                # ورود به سیستم
                session_id = str(uuid.uuid4())
                correlation_id = str(uuid.uuid4())
                
                success, access_token, refresh_token, expires_at = await login_okala(phone, password)
                
                if not success:
                    fail_count += 1
                    results.append(f"\n{EMOJI['phone']} <b>شماره:</b> {phone}\n{EMOJI['error']} <b>خطا:</b> {access_token}")
                    fail_reasons[access_token] = fail_reasons.get(access_token, 0) + 1
                    continue
                
                # افزودن آدرس
                address_success, address_data = await add_address(access_token, city_id, session_id, correlation_id)
                
                if not address_success:
                    fail_count += 1
                    error_msg = address_data if isinstance(address_data, str) else "افزودن آدرس ناموفق"
                    results.append(f"\n{EMOJI['phone']} <b>شماره:</b> {phone}\n{EMOJI['error']} <b>خطا:</b> {error_msg}")
                    fail_reasons[error_msg] = fail_reasons.get(error_msg, 0) + 1
                    continue
                
                # تنظیم فروشگاه فعال
                store_set = await set_active_store(access_token, session_id, correlation_id, store_id)
                if not store_set:
                    logger.warning(f"خطا در تنظیم فروشگاه فعال برای شماره {phone}")
                
                # افزودن محصولات به سبد خرید
                if city_id == 129:  # تهران
                    # استفاده از محصولات تصادفی
                    added_count, total_price, added_products, failed_products = await add_random_products_to_cart(
                        access_token,
                        session_id,
                        correlation_id,
                        store_id=store_id,
                        min_total_price=2000000
                    )
                    
                    if added_count > 0:
                        # گزارش محصولات اضافه شده
                        product_info = [f"🛒 <b>فروشگاه:</b> دستغیب (کد: {store_id})"]
                        product_info.append(f"📦 <b>تعداد محصولات اضافه شده:</b> {added_count}")
                        product_info.append(f"💰 <b>مبلغ کل سبد:</b> {total_price:,} ریال")
                        
                        if added_products:
                            product_info.append("\n📋 <b>لیست محصولات:</b>")
                            for product in added_products[:5]:  # نمایش حداکثر 5 محصول
                                product_info.append(f"  - {product['name']} ({product['price']:,} ریال)")
                            if len(added_products) > 5:
                                product_info.append(f"  ... و {len(added_products)-5} محصول دیگر")
                        
                        if failed_products:
                            product_info.append(f"\n⚠️ <b>تعداد محصولات ناموفق:</b> {len(failed_products)}")
                        
                        product_info_str = "\n".join(product_info)
                        
                        # تایید وجود سبد خرید
                        basket_verified = await verify_basket(access_token, session_id, correlation_id, store_id)
                        basket_status = "✅ سبد خرید تایید شد" if basket_verified else "⚠️ سبد خرید در پس‌زمینه است"
                        
                        if total_price >= 2000000:
                            success_count += 1
                            results.append(
                                f"\n{EMOJI['phone']} <b>شماره:</b> {phone}\n"
                                f"{EMOJI['success']} <b>وضعیت:</b> موفق\n"
                                f"{basket_status}\n"
                                f"{product_info_str}"
                            )
                        else:
                            fail_count += 1
                            results.append(
                                f"\n{EMOJI['phone']} <b>شماره:</b> {phone}\n"
                                f"{EMOJI['error']} <b>وضعیت:</b> ناموفق (مبلغ سبد ناکافی)\n"
                                f"{basket_status}\n"
                                f"{product_info_str}"
                            )
                    else:
                        fail_count += 1
                        results.append(
                            f"\n{EMOJI['phone']} <b>شماره:</b> {phone}\n"
                            f"{EMOJI['error']} <b>وضعیت:</b> ناموفق\n"
                            f"❌ هیچ محصولی به سبد اضافه نشد"
                        )
                else:
                    # برای سایر شهرها از لیست ثابت استفاده می‌کنیم
                    products = CITY_TRAFFIC.get(city_id, CITY_TRAFFIC[0])
                    added_products = []
                    failed_products = []
                    
                    for product in products:
                        success = await add_to_cart(
                            access_token,
                            session_id,
                            correlation_id,
                            product["store_id"], 
                            product["product_id"], 
                            product["quantity"]
                        )
                        if success:
                            added_products.append(product)
                        else:
                            failed_products.append(product)
                        await asyncio.sleep(0.2)  # کاهش تاخیر برای افزایش سرعت
                    
                    if added_products:
                        # گزارش محصولات اضافه شده
                        city_name = next((k for k, v in CITIES.items() if v["id"] == city_id), "نامشخص")
                        product_info = [f"🏬 <b>شهر:</b> {city_name} | <b>فروشگاه:</b> {CITIES[city_name]['store_name']}"]
                        product_info.append(f"📦 <b>تعداد محصولات اضافه شده:</b> {len(added_products)}")
                        
                        product_info.append("\n📋 <b>لیست محصولات:</b>")
                        for product in added_products[:5]:  # نمایش حداکثر 5 محصول
                            product_info.append(f"  - {product['name']}")
                        if len(added_products) > 5:
                            product_info.append(f"  ... و {len(added_products)-5} محصول دیگر")
                        
                        if failed_products:
                            product_info.append(f"\n⚠️ <b>تعداد محصولات ناموفق:</b> {len(failed_products)}")
                        
                        product_info_str = "\n".join(product_info)
                        
                        # تایید وجود سبد خرید
                        basket_verified = await verify_basket(access_token, session_id, correlation_id, store_id)
                        basket_status = "✅ سبد خرید تایید شد" if basket_verified else "⚠️ سبد خرید در پس‌زمینه است"
                        
                        success_count += 1
                        results.append(
                            f"\n{EMOJI['phone']} <b>شماره:</b> {phone}\n"
                            f"{EMOJI['success']} <b>وضعیت:</b> موفق\n"
                            f"{basket_status}\n"
                            f"{product_info_str}"
                        )
                    else:
                        fail_count += 1
                        results.append(
                            f"\n{EMOJI['phone']} <b>شماره:</b> {phone}\n"
                            f"{EMOJI['error']} <b>وضعیت:</b> ناموفق\n"
                            f"❌ هیچ محصولی به سبد اضافه نشد"
                        )
                
            except Exception as e:
                logger.error(f"خطا در پردازش سبد خرید برای {phone}: {str(e)}")
                fail_count += 1
                results.append(f"\n{EMOJI['phone']} <b>شماره:</b> {phone}\n{EMOJI['error']} <b>خطا:</b> خطای سیستمی")
                fail_reasons["خطای سیستمی"] = fail_reasons.get("خطای سیستمی", 0) + 1
            
            # تاخیر برای جلوگیری از محدودیت سرور
            await asyncio.sleep(0.5)  # کاهش تاخیر برای افزایش سرعت
    
    # خلاصه نتایج
    summary = f"\n\n{EMOJI['result']} <b>خلاصه نتایج:</b>\n"
    summary += f"• تعداد کل خطوط: {total_numbers}\n"
    summary += f"• موفق: {success_count}\n"
    summary += f"• ناموفق: {fail_count}\n\n"
    
    if fail_reasons:
        summary += f"{EMOJI['warning']} <b>دلایل خطاها:</b>\n"
        for reason, count in fail_reasons.items():
            summary += f"• {reason}: {count} مورد\n"
    
    # ارسال نتایج نهایی
    await msg.delete()
    await callback.message.answer(
        f"{EMOJI['success']} <b>عملیات با موفقیت انجام شد!</b>\n" + summary + "\n".join(results),
        parse_mode="HTML"
    )
    
    # پاکسازی داده‌های کاربر
    await state.clear()
    await callback.answer()

# هندلرهای مدیریت ادمین
@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    await callback.message.edit_text(
        f"{EMOJI['main_menu']} <b>منوی اصلی</b>\n"
        f"👤 نقش شما: {get_user_role(user_id)}",
        reply_markup=None
    )
    await callback.message.answer(
        "منوی اصلی:",
        reply_markup=main_menu_keyboard(user_id)
    )
    await callback.answer()

@dp.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: types.CallbackQuery):
    status = f"{EMOJI['on']} فعال" if BOT_ENABLED else f"{EMOJI['off']} غیرفعال"
    vip_users = db.get_vip_users()
    user_stats_count = len([uid for uid in db.get_user_stats(uid) for uid in [user_id]])  # Simplified
    
    await callback.message.edit_text(
        f"⚙️ <b>پنل مدیریت ربات</b>\n\n"
        f"• وضعیت ربات: {status}\n"
        f"• تعداد کاربران ویژه: {len(vip_users)}\n"
        f"• تعداد کاربران ثبت شده: {user_stats_count}\n\n"
        f"لطفا یکی از گزینه‌ها را انتخاب کنید:",
        reply_markup=admin_settings_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "bot_status")
async def toggle_bot_status(callback: types.CallbackQuery):
    global BOT_ENABLED
    BOT_ENABLED = not BOT_ENABLED
    status = f"{EMOJI['on']} فعال" if BOT_ENABLED else f"{EMOJI['off']} غیرفعال"
    await callback.message.edit_text(
        f"✅ <b>وضعیت ربات تغییر کرد!</b>\n\n"
        f"وضعیت جدید: {status}\n\n"
        f"<i>توجه: در حالت غیرفعال، فقط ادمین‌ها می‌توانند از ربات استفاده کنند.</i>",
        reply_markup=admin_settings_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "manage_vip")
async def manage_vip(callback: types.CallbackQuery):
    await callback.message.edit_text(
        f"⭐ <b>مدیریت کاربران ویژه</b>\n\n"
        f"از گزینه‌های زیر برای مدیریت کاربران ویژه استفاده کنید:",
        reply_markup=vip_management_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "user_stats_menu")
async def user_stats_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        f"📊 <b>مشاهده آمار کاربر</b>\n\n"
        f"لطفا شناسه عددی کاربر را ارسال کنید:",
        parse_mode="HTML"
    )
    await state.set_state(Form.waiting_for_stats_user_id)
    await callback.answer()

@dp.message(Form.waiting_for_stats_user_id)
async def process_stats_user_id(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text)
    except ValueError:
        await message.answer("⛔ شناسه کاربر باید یک عدد باشد. لطفا مجددا وارد کنید.")
        return
        
    stats = db.get_user_stats(user_id)
    if not stats:
        await message.answer(f"ℹ️ آمار کاربر {user_id} یافت نشد.")
        await state.clear()
        return
        
    role = get_user_role(user_id)
    success_rate = (stats['success'] / stats['total_checked']) * 100 if stats['total_checked'] > 0 else 0
    
    await message.answer(
        f"📊 <b>آمار کاربر {user_id}</b>\n"
        f"👤 نقش: {role}\n\n"
        f"• تعداد کل خطوط بررسی شده: {stats['total_checked']}\n"
        f"• ورودهای موفق: {stats['success']}\n"
        f"• ورودهای ناموفق: {stats['failed']}\n"
        f"• نرخ موفقیت: {success_rate:.1f}%\n\n"
        f"<i>آخرین به‌روزرسانی: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>",
        parse_mode="HTML"
    )
    await state.clear()

@dp.callback_query(F.data == "add_vip")
async def add_vip(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        f"⭐ <b>افزودن کاربر ویژه</b>\n\n"
        f"لطفا شناسه عددی کاربر را ارسال کنید:",
        parse_mode="HTML"
    )
    # ذخیره نوع عملیات در state
    await state.update_data(operation="add")
    await state.set_state(Form.waiting_for_vip_user_id)
    await callback.answer()

@dp.callback_query(F.data == "remove_vip")
async def remove_vip(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        f"❌ <b>حذف کاربر ویژه</b>\n\n"
        f"لطفا شناسه عددی کاربر را ارسال کنید:",
        parse_mode="HTML"
    )
    # ذخیره نوع عملیات در state
    await state.update_data(operation="remove")
    await state.set_state(Form.waiting_for_vip_user_id)
    await callback.answer()

@dp.callback_query(F.data == "list_vip")
async def list_vip(callback: types.CallbackQuery):
    vip_users = db.get_vip_users()
    if not vip_users:
        await callback.message.edit_text(
            "ℹ️ هیچ کاربر ویژه‌ای ثبت نشده است.",
            reply_markup=vip_management_keyboard()
        )
        return
        
    vip_list = "\n".join([f"• {user_id}" for user_id in vip_users])
    await callback.message.edit_text(
        f"⭐ <b>لیست کاربران ویژه</b>\n\n"
        f"{vip_list}\n\n"
        f"تعداد کل: {len(vip_users)}",
        reply_markup=vip_management_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(Form.waiting_for_vip_user_id)
async def process_vip_user_id(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text)
    except ValueError:
        await message.answer("⛔ شناسه کاربر باید یک عدد باشد. لطفا مجددا وارد کنید.")
        return
        
    # دریافت نوع عملیات از state
    state_data = await state.get_data()
    operation = state_data.get("operation", "")
    
    if operation == "add":
        if db.add_vip_user(user_id):
            await message.answer(f"✅ کاربر {user_id} با موفقیت به لیست ویژه اضافه شد.")
        else:
            await message.answer(f"ℹ️ کاربر {user_id} قبلاً در لیست ویژه وجود دارد.")
            
    elif operation == "remove":
        if db.remove_vip_user(user_id):
            await message.answer(f"✅ کاربر {user_id} با موفقیت از لیست ویژه حذف شد.")
        else:
            await message.answer(f"ℹ️ کاربر {user_id} در لیست ویژه وجود ندارد.")
    else:
        await message.answer("⛔ عملیات نامعتبر است.")
            
    await state.clear()

# هندلرهای توکن ادمین
@dp.callback_query(F.data == "check_with_token")
async def check_with_token(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS and user_id != OWNER_ID:
        await callback.answer("⛔ فقط ادمین‌ها و مالک می‌توانند از این قابلیت استفاده کنند!", show_alert=True)
        return
        
    await callback.message.edit_text(
        f"{EMOJI['token']} <b>لطفا فایل حاوی توکن‌ها را ارسال کنید:</b>\n\n"
        f"• فرمت: هر خط شامل شماره|توکن\n"
        f"• مثال:\n09123456789|eyJhbGciOi...\n09123456788|eyJhbGciOi...",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(Form.waiting_for_token_file)
    await callback.answer()

@dp.message(Form.waiting_for_token_file, F.document)
async def handle_token_file(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        # دریافت فایل
        file = await bot.get_file(message.document.file_id)
        file_path = f"tokens_{user_id}.txt"
        await bot.download_file(file.file_path, file_path)
        
        # خواندن توکن‌ها
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) >= 2:
                    phone = parts[0].strip()
                    token = parts[1].strip()
                    db.save_token(phone, token)
        
        await message.answer(
            f"{EMOJI['success']} <b>فایل توکن با موفقیت دریافت و پردازش شد!</b>\n"
            f"• تعداد توکن‌های ذخیره شده: {len(open(file_path).readlines())}\n\n"
            f"برای شروع بررسی دکمه شروع را بزنید:",
            reply_markup=start_check_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"خطا در پردازش فایل توکن: {str(e)}")
        await message.answer(
            f"{EMOJI['error']} <b>خطا در پردازش فایل توکن!</b>\n\n"
            f"لطفا فایل معتبر ارسال کنید.",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )

# هندلرهای عمومی
@dp.callback_query(F.data == "cancel")
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    current_state = await state.get_state()
    
    # Only clear registration data if in registration flow
    if current_state and "RegisterState" in current_state:
        await state.update_data({
            "current_phone": "",
            "access_token": ""
        })
    
    await state.clear()
    await callback.message.edit_text(f"{EMOJI['cancel']} <b>عملیات لغو شد.</b>", parse_mode="HTML")
    await callback.message.answer(
        f"{EMOJI['main_menu']} <b>منوی اصلی</b>",
        reply_markup=main_menu_keyboard(user_id),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "cancel_register")
async def cancel_register_handler(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await state.update_data({
        "current_phone": "",
        "access_token": ""
    })
    
    await state.clear()
    await callback.message.edit_text(f"{EMOJI['cancel']} <b>عملیات لغو شد.</b>", parse_mode="HTML")
    await callback.message.answer(
        f"{EMOJI['main_menu']} <b>منوی اصلی</b>",
        reply_markup=main_menu_keyboard(user_id),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(F.text == f"{EMOJI['list']} دریافت لیست شماره‌ها")
async def get_all_phones_list(message: types.Message):
    user_id = message.from_user.id
    
    # لیست شماره‌های ثبت نام
    reg_phones = db.get_registration_phones(user_id)
    reg_response = []
    if reg_phones:
        reg_response.append(f"{EMOJI['register']} <b>لیست شماره‌های ثبت نام شده:</b>")
        for idx, data in enumerate(reg_phones, 1):
            reg_response.append(
                f"\n{idx}. {data['phone']}\n"
                f"   رمز: {data['password']}\n"
                f"   نام: {data['first_name']} {data['last_name']}\n"
                f"   ایمیل: {data['email']}"
            )
        reg_response.append(f"\n\n{EMOJI['success']} <b>تعداد کل: {len(reg_phones)}</b>")
    else:
        reg_response.append(f"{EMOJI['warning']} هیچ شماره ثبت نام شده‌ای وجود ندارد.")
    
    # لیست شماره‌های سبد خرید
    city_id, basket_lists = db.get_basket_data(user_id)
    basket_response = []
    if basket_lists:
        basket_response.append(f"\n{EMOJI['basket']} <b>لیست شماره‌های سبد خرید:</b>")
        for list_idx, (phones, password) in enumerate(basket_lists, 1):
            basket_response.append(f"\nلیست {list_idx} (رمز: {password}):")
            for phone in phones:
                basket_response.append(f"• {phone}")
    else:
        basket_response.append(f"\n{EMOJI['warning']} هیچ شماره سبد خریدی وجود ندارد.")
    
    # ارسال پاسخ
    response = "\n".join(reg_response) + "\n" + "\n".join(basket_response)
    await message.answer(response, parse_mode="HTML")

# اجرای ربات
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))