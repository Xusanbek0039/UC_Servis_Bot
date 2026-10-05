# 🎮 PUBG MOBILE UC TOP-UP TELEGRAM BOT & BACKEND

Professional darajadagi, to'liq avtomatlashtirilgan va Clean Architecture asosida qurilgan **PUBG Mobile UC Top-Up Telegram Bot** va boshqaruv tizimi.

Ushbu platforma foydalanuvchilarga PUBG Mobile UC xarid qilish, onlayn to'lov (TezCheck) yoki karta orqali qo'lda to'lash, ichki balansdan foydalanish, promo kodlar va referral tizimi orqali chegirmalar olish imkonini beradi. UC yetkazib berish avtomatik (Midasbuy API / Mock) yoki admin orqali qo'lda (Manual) amalga oshiriladi.

---

## 📑 MUNDARIJA

1. [Texnologiyalar Steki](#-texnologiyalar-steki)
2. [Tizim Arxitekturasi](#-tizim-arxitekturasi)
3. [Loyiha Tuzilishi (Structure)](#-loyiha-tuzilishi)
4. [O'rnatish va Ishga Tushirish (Mahalliy)](#-ornatish-va-ishga-tushirish-mahalliy)
   - [1. Python o'rnatish](#1-python-ornatish)
   - [2. PostgreSQL va Redis](#2-postgresql-va-redis)
   - [3. .env Konfiguratsiyasi](#3-env-konfiguratsiyasi)
   - [4. Telegram BotFather](#4-telegram-botfather)
   - [5. TezCheck API Konfiguratsiyasi](#5-tezcheck-api-konfiguratsiyasi)
   - [6. Midasbuy API Konfiguratsiyasi](#6-midasbuy-api-konfiguratsiyasi)
   - [7. Ma'lumotlar bazasi migratsiyasi](#7-malumotlar-bazasi-migratsiyasi)
   - [8. Admin yaratish](#8-admin-yaratish)
   - [9. Bot va Webhookni ishga tushirish](#9-bot-va-webhookni-ishga-tushirish)
5. [Docker va Docker Compose orqali ishga tushirish](#-docker-va-docker-compose-orqali-ishga-tushirish)
6. [Asosiy Funksionallar va Jarayonlar (Flows)](#-asosiy-funksionallar-va-jarayonlar)
7. [Xavfsizlik va Idempotency](#-xavfsizlik-va-idempotency)
8. [Testlarni Ishga Tushirish (Pytest)](#-testlarni-ishga-tushirish-pytest)
9. [Production Deployment](#-production-deployment)

---

## 🚀 TEXNOLOGIYALAR STEKI

- **Til:** Python 3.12+
- **Telegram Bot Framework:** Aiogram 3.x (Async, FSM, Middlewares)
- **Veb Framework & ORM:** Django 5.x + Django REST Framework (DRF)
- **Ma'lumotlar Bazasi:** PostgreSQL 16 (DecimalField pullar uchun, relational normalization)
- **Kesh & Xabarlar Navbati (Broker):** Redis 7
- **Asinxron Vazifalar:** Celery 5.x + Celery Beat (retries, timeouts, cron)
- **Konteynerizatsiya:** Docker & Docker Compose
- **Testlash:** Pytest, pytest-django, pytest-asyncio (100% test qamrovi)
- **HTTP Client:** HTTPX / Aiohttp (Async REST clients with HMAC-SHA256 signatures)

---

## 🏛 TIZIM ARXITEKTURASI

Platforma **Service Layer** va **Provider Pattern** tamoyillariga asoslangan:

```
[ Telegram Foydalanuvchi ]
           │
           ▼
[ Aiogram 3.x Bot ] ── (FSM States, Throttling, User Middleware)
           │
           ▼
   [ Service Layer ]  <─── (UserService, OrderService, PaymentService, PromoService)
           │
     ┌─────┴───────────────────────────────────┐
     ▼                                         ▼
[ Payment Providers ]                 [ Topup Providers ]
  ├── TezCheckProvider                  ├── MidasbuyProvider (Official API)
  └── ManualCardProvider (Fallback)     ├── MockTopupProvider (Dev/Test simulation)
                                        └── ManualTopupProvider (Admin handoff)
     │                                         │
     └─────────────────┬───────────────────────┘
                       ▼
           [ PostgreSQL 16 & Redis ]
           [ Celery Async Workers & Beat ]
```

---

## 📁 LOYIHA TUZILISHI

```
UC_Servis_Bot/
│
├── manage.py
├── requirements.txt
├── .env.example
├── .env
├── pytest.ini
├── Dockerfile
├── docker-compose.yml
├── README.md
│
├── config/                  # Django asosiy konfiguratsiyasi
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   ├── asgi.py
│   ├── wsgi.py
│   └── celery.py            # Celery app va Beat jadvallari
│
├── apps/                    # Django modullari
│   ├── users/               # TelegramUser, BalanceLedger, Player
│   ├── products/            # UC paketlari (Product)
│   ├── orders/              # Order modeli va xizmatlari
│   ├── payments/            # Payment, ManualPayment (Cheklar), Webhooklar
│   ├── promo/               # PromoCode, PromoCodeUsage
│   ├── referrals/           # Referral tizimi va mukofotlar
│   ├── audit/               # AdminAction (Audit Logs)
│   ├── settings/            # BotSettings (Singleton sozlamalar)
│   ├── notifications/       # Xabarnomalar tizimi
│   └── providers/           # Provider tranzaksiyalari logi
│
├── bot/                     # Aiogram 3.x Telegram Bot
│   ├── loader.py            # Bot va Dispatcher initsializatsiyasi
│   ├── main.py              # Bot entrypoint (Polling runner)
│   ├── states/              # FSM holatlari (BuyUC, Balance, Admin)
│   ├── middlewares/         # Throttling, User sync, Admin security
│   ├── keyboards/           # Reply va Inline tugmalar
│   └── handlers/
│       ├── user/            # Start, Buy UC, Balans, Buyurtmalar, Yordam, Bekor qilish
│       └── admin/           # Boshqaruv paneli, buyurtmalar, chek tekshirish, statistika
│
├── providers/               # Mustaqil tashqi provayderlar
│   ├── base.py              # PaymentProvider & TopupProvider abstrakt interfeyslari
│   ├── factory.py           # Provider tanlash zavodi (Factory pattern)
│   ├── tezcheck/            # TezCheck to'lov integratsiyasi (API, Webhook, HMAC)
│   ├── midasbuy/            # Midasbuy API integratsiyasi (HMAC-SHA256, Player Check)
│   └── mock/                # MockTopupProvider (Lokal testlash uchun to'liq simulyatsiya)
│
├── templates/               # Django Admin maxsus dizayni (Dashboard kartalari)
└── tests/                   # Pytest to'liq test to'plami (22 ta test)
```

---

## 🛠 O'RNATISH VA ISHGA TUSHIRISH (MAHALLIY)

### 1. Python o'rnatish

Python **3.12+** talab qilinadi:

```bash
# Versiyani tekshiring:
python --version  # Kamida 3.12 bo'lishi kerak
```

Virtual muhit (venv) yarating va faollashtiring:

```bash
# Windows:
python -m venv venv
.\venv\Scripts\activate

# Linux / MacOS:
python3 -m venv venv
source venv/bin/activate
```

Kutubxonalarni o'rnating:

```bash
pip install -r requirements.txt
```

---

### 2. PostgreSQL va Redis

Agar kompyuteringizda PostgreSQL va Redis o'rnatilgan bo'lsa:
1. PostgreSQL da yangi baza oching:
   ```sql
   CREATE DATABASE pubg_uc_db;
   CREATE USER pubg_user WITH PASSWORD 'pubg_secure_pass';
   GRANT ALL PRIVILEGES ON DATABASE pubg_uc_db TO pubg_user;
   ```
2. Redis xizmatini yoqing (`redis-server`).

> **Eslatma:** Dastur PostgreSQL ulanmasa yoki `DATABASE_URL` bo'sh qoldirilsa, avtomatik tarzda `db.sqlite3` ga fallback qiladi. Bu esa darhol test qilishni juda osonlashtiradi.

---

### 3. .env Konfiguratsiyasi

`.env.example` faylidan nusxa olib `.env` yarating:

```bash
cp .env.example .env
```

Quyidagi o'zgaruvchilarni to'ldiring:

```ini
DEBUG=True
SECRET_KEY=your_django_secret_key_here
DJANGO_SETTINGS_MODULE=config.settings.development

# Ma'lumotlar bazasi
DATABASE_URL=postgresql://pubg_user:pubg_secure_pass@localhost:5432/pubg_uc_db
REDIS_URL=redis://localhost:6379/0

# Telegram Bot
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
BOT_USERNAME=PubgUcServisBot
ADMIN_IDS=123456789,987654321

# Yetkazib berish rejimi (AUTO yoki MANUAL)
DELIVERY_MODE=MANUAL
DEFAULT_TOPUP_PROVIDER=MOCK

# TezCheck to'lov tizimi
TEZCHECK_BASE_URL=https://api.tezcheck.uz
TEZCHECK_API_KEY=your_tezcheck_api_key
TEZCHECK_CASH_DESK_CODE=your_cash_desk_code
TEZCHECK_SECRET_KEY=your_tezcheck_webhook_secret

# Midasbuy API
MIDASBUY_BASE_URL=https://api.midasbuy.com
MIDASBUY_API_KEY=your_midasbuy_key
MIDASBUY_SECRET=your_midasbuy_secret
MIDASBUY_APP_ID=your_midasbuy_app_id
```

---

### 4. Telegram BotFather

1. Telegramda [@BotFather](https://t.me/BotFather) ga kiring.
2. `/newbot` buyrug'i orqali yangi bot yarating.
3. Bot username va tokenini oling.
4. Bot tokenni `.env` dagi `BOT_TOKEN` parametriga yozing.
5. Bot buyruqlarini sozlang:
   - `start` — Botni ishga tushirish
   - `buy` — PUBG UC xarid qilish
   - `balance` — Balansni tekshirish
   - `orders` — Buyurtmalarim
   - `help` — Yordam
   - `admin` — Admin panel

---

### 5. TezCheck API Konfiguratsiyasi

1. TezCheck to'lov tizimidan hisob oching va API kalitlarni oling:
   - `TEZCHECK_API_KEY`
   - `TEZCHECK_CASH_DESK_CODE`
   - `TEZCHECK_SECRET_KEY`
2. TezCheck kabinetida Webhook URL manzilini ko'rsating:
   `https://sizningdomeningiz.uz/api/webhooks/tezcheck/`
3. Tizim webhook xabarlarini avtomatik HMAC-SHA256 imzosi orqali tekshiradi va dublikat so'rovlarni bir necha bor bajarilishidan himoyalaydi (Idempotency).

---

### 6. Midasbuy API Konfiguratsiyasi

Midasbuy rasmiy hamkorlik shartnomasi bo'yicha berilgan ma'lumotlarni kiriting:
- `MIDASBUY_API_KEY`
- `MIDASBUY_SECRET`
- `MIDASBUY_APP_ID`
- `MIDASBUY_BASE_URL`

Agar Midasbuy API hisobingiz hali tayyor bo'lmasa, hech qanday xavotir olmang:
- `DELIVERY_MODE=MANUAL` yoki `DEFAULT_TOPUP_PROVIDER=MOCK` qilib qo'yishingiz mumkin.
- `MockTopupProvider` barcha Player ID tekshiruvlarini va yetkazib berish jarayonlarini 100% haqiqiydek simulyatsiya qilib beradi!

---

### 7. Ma'lumotlar Bazasi Migratsiyasi

```bash
python manage.py makemigrations
python manage.py migrate
```

---

### 8. Admin Yaratish

Maxsus yaratilgan `init_admin` buyrug'i orqali Django superuser, asosiy bot sozlamalari va birlamchi UC paketlarini 1 soniyada yarating:

```bash
python manage.py init_admin --username admin --password admin123 --email admin@example.com
```

Natijada:
- Superuser yaratiladi (Login: `admin`, Parol: `admin123`)
- `BotSettings` initsializatsiya qilinadi
- 6 ta standart UC paketlari (60 UC, 325 UC, 660 UC, 1800 UC, 3850 UC, 8100 UC) avtomatik bazaga qo'shiladi!

---

### 9. Bot va Webhookni Ishga Tushirish

Alohida 3 ta terminalda quyidagilarni ishga tushiring:

1. **Django Webhook & Admin Server:**
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```
   Admin panelga kiring: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

2. **Aiogram Telegram Bot (Polling):**
   ```bash
   python bot/main.py
   ```

3. **Celery Worker & Beat (Asinxron yetkazish va vazifalar uchun):**
   ```bash
   celery -A config worker --loglevel=info
   celery -A config beat --loglevel=info
   ```

---

## 🐳 DOCKER VA DOCKER COMPOSE ORQALI ISHGA TUSHIRISH

Loyiha to'liq Docker muhitida 1 ta buyruq bilan ishga tushadi:

```bash
docker compose up -d --build
```

Konteynerlar:
- `pubg_postgres`: PostgreSQL 16 ma'lumotlar bazasi
- `pubg_redis`: Redis 7 kesh va navbat brokeri
- `pubg_web`: Django REST API + Webhook server (Gunicorn 3 ta worker bilan)
- `pubg_bot`: Aiogram 3 bot xizmati
- `pubg_celery_worker`: Asinxron yetkazib berish workerlari
- `pubg_celery_beat`: Periodik vazifalar (muddati o'tgan buyurtmalarni bekor qilish, retry)

Konteynerlar holatini tekshirish:
```bash
docker compose ps
docker compose logs -f bot
```

---

## 🔄 ASOSIY FUNKSIONALLAR VA JARAYONLAR (FLOWS)

### 1. UC Xarid Qilish (User Flow)
```
1. Foydalanuvchi "🎮 PUBG UC" tugmasini bosadi.
2. Bot: "PUBG Mobile Player ID'ingizni kiriting"
3. Foydalanuvchi ID kiritadi (masalan: 5123456789).
4. Bot Player ID'ni tekshiradi:
   👤 Player: UZB_Sniper_PRO
   🆔 ID: 5123456789
   Shu akkauntga UC yuborilsinmi?
5. Tasdiqlangach, faol UC paketlar ro'yxati chiqadi.
6. Paket tanlanadi -> Promo kod kiritish yoki o'tkazib yuborish so'raladi.
7. To'lov usuli tanlanadi:
   a) TezCheck — Avtomatik to'lov havolasi beriladi
   b) Karta orqali qo'lda — Karta rekvizitlari beriladi, chek skrinshoti kutiladi
   c) Ichki balans — Yetarli mablag' bo'lsa, bir zumda yechiladi
8. To'lov tasdiqlangach, buyurtma statusi yangilanadi va foydalanuvchiga kvitansiya yuboriladi.
```

### 2. Manual Card Payment & Admin Review
```
Foydalanuvchi chek yuboradi
        │
        ▼
ManualPayment yaratiladi (Status: PENDING)
        │
        ▼
Adminlarga Telegram va Django Admin orqali rasm va ma'lumot yuboriladi
        │
     ┌──┴─────────────────────────┐
     ▼                            ▼
[ ✅ Tasdiqlash ]           [ ❌ Rad etish ]
     │                            │
     ▼                            ▼
Payment → PAID               Payment → FAILED
Order → PROCESSING           Order → FAILED (Sababi bilan)
UC yetkazishga yuboriladi    Foydalanuvchiga xabar boradi
Audit log yoziladi           Audit log yoziladi
```

### 3. Ichki Balans va Ledger Tizimi
- Balans hech qachon to'g'ridan-to'g'ri o'zgartirilmaydi.
- Har bir operatsiya `transaction.atomic()` va `select_for_update()` himoyasi ostida `BalanceLedger` jadvalida saqlanadi (`DEPOSIT`, `WITHDRAW`, `ORDER_PAYMENT`, `ORDER_REFUND`, `REFERRAL_BONUS`, `ADMIN_ADJUSTMENT`).

### 4. Referral Tizimi
- Har bir foydalanuvchiga shaxsiy havola: `https://t.me/BotUsername?start=ref_12345678`
- Taklif qilingan do'st birinchi buyurtmani bajarganda, taklif qiluvchining balansiga avtomatik `referral_bonus` tushadi va Telegram orqali xabarnoma yuboriladi.

---

## 🔒 XAVFSIZLIK VA IDEMPOTENCY

- **API Kalitlar:** Kod ichida hech qanday maxfiy kalit mavjud emas. Barchasi `.env` orqali boshqariladi.
- **Idempotency:** Webhooklar va yetkazib berish harakatlari unique `idempotency_key` va `order_id` orqali himoyalangan. Bir xil to'lov xabari bir necha marta kelsa ham, mablag' ikki marta yechilmaydi yoki UC ikki marta yuborilmaydi.
- **Webhook Imzosi:** TezCheck webhooklari HMAC-SHA256 imzosi orqali haqiqiyligi tekshiriladi. Brauzer redirecti hech qachon to'lov tasdig'i deb qabul qilinmaydi.
- **Throttling:** Botga spam yuborishning oldini oluvchi rate-limit middleware mavjud.
- **Admin Xavfsizligi:** Admin komandalariga faqat `ADMIN_IDS` yoki `is_admin=True` bo'lgan xodimlar kira oladi.

---

## 🧪 TESTLARNI ISHGA TUSHIRISH (PYTEST)

Platformada 22 ta to'liq unit va integratsion testlar mavjud:

```bash
pytest -v
```

Testlar ro'yxati:
- Foydalanuvchi ro'yxatdan o'tishi va profil yangilanishi
- Referral havola orqali bog'lanish
- Balans tranzaksiyalari va Ledger yaxlitligi
- Manfiy balansga yo'l qo'ymaslik tekshiruvi
- PUBG player profilini saqlash
- Mahsulotlar tannarxi va sof foyda hisobi
- Promo kodlar (foizli va aniq summali chegirmalar)
- Promo kod muddati va limitlari tekshiruvi
- Promo koddan bir foydalanuvchi ikki marta foydalana olmasligi
- Unikal buyurtma raqamlari (`PUBG-YYYYMMDD-000001`) ketma-ketligi
- Ichki balans orqali to'lov qilish
- Buyurtmani bekor qilish va balansga avtomatik refund
- Admin tomonidan qo'lda UC yetkazildi deb tasdiqlash
- TezCheck webhook imzosi tekshiruvi (HMAC-SHA256)
- TezCheck webhookni qayta ishlash va **Idempotency (dublikat xabarni zararsiz qaytarish)**
- Qo'lda karta orqali to'lov chekini yuborish
- Admin tomonidan chekni tasdiqlash va rad etish
- MockTopupProvider player ID tekshiruvi (to'g'ri, noto'g'ri format, xato ID)
- MockTopupProvider muvaffaqiyatli va muvaffaqiyatsiz yetkazish simulyatsiyasi
- Provider Factory ishlashi

---

## 🚢 PRODUCTION DEPLOYMENT

Production serverda (Ubuntu 22.04 / 24.04):

1. Repozitoriyni klon qiling:
   ```bash
   git clone <repo_url> /opt/pubg_uc_bot
   cd /opt/pubg_uc_bot
   ```
2. `.env` faylini production qiymatlari bilan to'ldiring:
   - `DEBUG=False`
   - `ALLOWED_HOSTS=sizningdomeningiz.uz`
   - Kuchli `SECRET_KEY`
   - Haqiqiy `TEZCHECK_*` va `MIDASBUY_*` kalitlari
3. Docker orqali ishga tushiring:
   ```bash
   docker compose up -d --build
   ```
4. Nginx orqali SSL (Certbot) o'rnating va `http://127.0.0.1:8000` ga proxy qiling:
   ```nginx
   server {
       server_name sizningdomeningiz.uz;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }

       location /static/ {
           alias /opt/pubg_uc_bot/staticfiles/;
       }

       location /media/ {
           alias /opt/pubg_uc_bot/media/;
       }
   }
   ```
5. Bot va tizim 24/7 rejimda xavfsiz va ishonchli ishlaydi!
