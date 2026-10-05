# 🎮 PUBG MOBILE UC TOP-UP TELEGRAM BOT

Foydalanuvchilarga PUBG Mobile UC sotish uchun qulay, yengil, tezkor va professional darajadagi Telegram Bot loyihasi.

Ushbu loyiha **Django, Docker, Celery, Redis va PostgreSQL kabi og'ir vositalardan xoli** bo'lib, Windows yoki Linux tizimida to'g'ridan-to'g'ri `python bot.py` orqali bir necha soniyada ishga tushadi.

---

## ⚡ TEXNOLOGIYALAR STEKI

- **Dasturlash tili:** Python 3.12+
- **Telegram Bot Framework:** Aiogram 3.x (Asinxron FSM, zamonaviy Routerlar, Inline tugmalar)
- **Ma'lumotlar bazasi:** MongoDB Atlas (`motor` + `pymongo` - asinxron, bulutli NoSQL ma'lumotlar bazasi)
- **To'lov Webhook Serveri:** FastAPI + Uvicorn (TezCheck to'lovlarini qabul qilish uchun)
- **HTTP Client:** HTTPX (Asinxron HTTP so'rovlar, HMAC-SHA256 imzolar)
- **Konfiguratsiya:** `python-dotenv` orqali xavfsiz `.env` sozlamalari

---

## 📁 LOYIHA TUZILISHI (PROJECT STRUCTURE)

```
pubg_uc_bot/
│
├── .env                  # Maxfiy tokenlar va MongoDB URI sozlamalari
├── .env.example          # Sozlamalar namunasi
├── .gitignore            # Git istisno fayli
├── requirements.txt      # Asosiy kutubxonalar (aiogram, motor, pymongo, ...)
│
├── bot.py                # Asosiy Telegram Bot ishga tushirish fayli
├── api.py                # TezCheck webhook qabul qiluvchi FastAPI server
├── config.py             # Konfiguratsiya va .env sozlamalari
├── database.py           # motor orqali to'liq asinxron MongoDB Atlas qatlami
│
├── handlers/             # Telegram bot handlerlari
│   ├── __init__.py
│   ├── start.py          # /start, bosh menyu, ro'yxatdan o'tish
│   ├── shop.py           # PUBG ID qabul qilish, paket tanlash, buyurtma
│   ├── payment.py        # TezCheck va Karta orqali to'lov, chek qabul qilish
│   ├── orders.py         # Foydalanuvchi buyurtmalar tarixi
│   ├── profile.py        # Balans, yordam va admin bilan aloqa
│   └── admin.py          # Admin paneli (cheklarni tasdiqlash, UC yuborish, narxlar)
│
├── services/             # Tashqi servislar va biznes logika
│   ├── __init__.py
│   ├── tezcheck.py       # TezCheck to'lov tizimi integratsiyasi
│   ├── midasbuy.py       # Midasbuy API / Player validation
│   └── order_service.py  # Buyurtmalarni yakunlash va xabarnomalar
│
├── keyboards/            # Inline klaviaturalar
│   ├── __init__.py
│   ├── user.py           # Foydalanuvchi inline tugmalari
│   └── admin.py          # Admin boshqaruv tugmalari
│
├── states/               # FSM holatlari (Aiogram State)
│   ├── __init__.py
│   └── order.py          # Buyurtma va admin FSM holatlari
│
└── utils/                # Yordamchi vositalar
    ├── __init__.py
    └── helpers.py        # Valyuta formatlash, ID tekshirish, xabarlar
```

---

## 🚀 O'RNATISH VA ISHGA TUSHIRISH (WINDOWS)

### 1-qadam: Repozitoriyaga kirish va Virtual Muhit (venv)

Agar virtual muhit yaratilmagan bo'lsa:
```powershell
python -m venv venv
```

Virtual muhitni faollashtiring:
```powershell
.\venv\Scripts\activate
```

### 2-qadam: Kutubxonalarni o'rnatish

```powershell
pip install -r requirements.txt
```

Kutubxonalar ro'yxati:
```
aiogram>=3.13.0
motor>=3.7.0
pymongo>=4.9.0
python-dotenv>=1.0.1
httpx>=0.27.0
fastapi>=0.110.0
uvicorn>=0.30.0
```

### 3-qadam: `.env` faylini sozlash

`.env.example` dan nusxa olib `.env` yarating:
```powershell
Copy-Item .env.example .env
```

`.env` faylini oching va ma'lumotlarni kiriting:
```ini
# Bot sozlamalari
BOT_TOKEN=your_bot_token_here
BOT_USERNAME=@your_bot_username
ADMIN_IDS=123456789,987654321

# MongoDB Atlas
MONGODB_URI=mongodb://itpark0071_db_user:mgDFmDe8htPYk2Mk@ac-qlduf4i-shard-00-00.8lo77cr.mongodb.net:27017,ac-qlduf4i-shard-00-01.8lo77cr.mongodb.net:27017,ac-qlduf4i-shard-00-02.8lo77cr.mongodb.net:27017/?ssl=true&replicaSet=atlas-571xzs-shard-0&authSource=admin&appName=Cluster0
MONGODB_DB_NAME=pubg_uc_db

# Webhook API sozlamalari
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=8000
WEBHOOK_BASE_URL=https://your-domain.com

# TezCheck to'lov tizimi
TEZCHECK_API_KEY=your_tezcheck_key
TEZCHECK_CASH_DESK_CODE=your_cash_desk_code
TEZCHECK_BASE_URL=https://api.tezcheck.uz
TEZCHECK_SECRET_KEY=your_tezcheck_secret

# Midasbuy API (ixtiyoriy)
MIDASBUY_API_KEY=
MIDASBUY_APP_ID=
MIDASBUY_BASE_URL=https://api.midasbuy.com
```

### 4-qadam: Botni ishga tushirish

Windows terminalida botni oddiy buyruq bilan yoqing:
```powershell
python bot.py
```
> Bot avtomatik tarzda `bot.db` SQLite bazasini, 6 ta asosiy UC paketlarini (60 UC, 325 UC, 660 UC, 1800 UC, 3850 UC, 8100 UC) va birlamchi sozlamalarni kiritadi.

### 5-qadam: TezCheck Webhook serverini ishga tushirish (Alohida oynada)

Avtomatik to'lovlar uchun FastAPI webhook serverini yoqing:
```powershell
python api.py
```
Server `http://localhost:8000` da ishga tushadi. Webhook manzili:
`POST /api/webhooks/tezcheck/`

---

## 💎 FOYDALANUVCHI XARID JARAYONI (FLOW)

1. **/start** bosadi:
   - 🎮 UC sotib olish
   - 📦 Buyurtmalarim
   - 💰 Balansim
   - ℹ️ Yordam
   - 📞 Admin
2. **"🎮 UC sotib olish"** tanlanadi.
3. Bot foydalanuvchidan **PUBG Mobile Player ID** so'raydi (raqamli format tekshiriladi).
4. Player ID va Nickname tasdiqlangach, **UC paketlari** chiqadi:
   - 💎 60 UC — 15 000 so'm
   - 💎 325 UC — 70 000 so'm
   - 💎 660 UC — 135 000 so'm
   - 💎 1800 UC — 350 000 so'm
   - 💎 3850 UC — 700 000 so'm
   - 💎 8100 UC — 1 400 000 so'm
5. Buyurtma shakllanadi: masalan, `PUBG-000001`.
6. To'lov usuli tanlanadi:
   - **⚡ TezCheck (Avtomatik):** To'lov havolasi beriladi, to'langach bir zumda tasdiqlanadi.
   - **💳 Karta orqali (Qo'lda):** Adminning karta raqami ko'rsatiladi, foydalanuvchi to'lov cheki skrinshotini yuboradi.
   - **💰 Ichki balans:** Foydalanuvchining hisobidagi mablag' orqali bir zumda to'lash.

---

## 👨‍💼 ADMIN BOSHQARUV PANELI

Admin botda `/admin` buyrug'ini yuboradi.

### 1. Buyurtmalar boshqaruvi:
- **Kutilayotgan buyurtmalar (`WAITING_PAYMENT` / `MANUAL_REVIEW`):**
  - Foydalanuvchi karta orqali to'lab chek tashlaganda adminga skrinshot va order ma'lumoti keladi.
  - **✅ To'lovni tasdiqlash:** Bosilganda buyurtma `PAID` / `PROCESSING` ga o'tadi.
  - **❌ To'lovni rad etish:** Buyurtma bekor qilinadi, mijozga sababi xabar qilinadi.
  - **🎮 UC yuborildi:** UC hisobga tashlab berilgach adminga bitta tugma orqali buyurtmani `COMPLETED` qilish imkoni beriladi. Mijozga avtomatik "Buyurtmangiz muvaffaqiyatli yetkazildi! ✅" xabari yuboriladi.

### 2. UC Paketlari boshqaruvi:
- ➕ Yangi paket qo'shish (UC miqdori va narxi kiritiladi)
- ✏️ Narxini o'zgartirish
- 🔴/🟢 Aktiv/Deaktiv qilish (Mijozlarga ko'rinmas qilish)
- ❌ Paketni o'chirish

### 3. Tizim sozlamalari:
- 💳 Karta raqami va karta egasi ismini botdan turib o'zgartirish
- 📞 Qo'llab-quvvatlash (@admin username) sozlash
- 🔄 Yetkazib berish rejimini o'zgartirish: `MANUAL` (Qo'lda) yoki `AUTO` (Avtomatik Midasbuy)

### 4. Statistika:
- Jami buyurtmalar, bugungi buyurtmalar soni
- Jami tushum (summa), bugungi tushum
- Ro'yxatdan o'tgan foydalanuvchilar soni

---

## 🔒 XAVFSIZLIK VA IDEMPOTENCY

- **Takroriy to'lov himoyasi:** TezCheck webhooki bir xil tranzaksiya bilan bir necha marta kelsa ham, baza tekshirilib, order faqat bir marta `PAID` qilinadi.
- **HMAC-SHA256 Imzo:** Webhook so'rovlarining haqiqiyligi `X-Signature` sarlavhasi orqali tekshiriladi.
- **Player ID Validatsiya:** Foydalanuvchi xato yoki harf kiritganda ogohlantiriladi va noto'g'ri hisobga UC ketishi oldi olinadi.

---

## 📢 ISBOT KANALI (PROOF CHANNEL) TIZIMI

Kanalda har bir buyurtmaning butun hayotiy sikli bitta postda **EDIT (tahrirlash)** orqali ko'rsatiladi:

```
🛒 BUYURTMA QABUL QILINDI  (Post yuboriladi, message_id saqlanadi)
         ↓
⚙️ BUYURTMA JARAYONDA      (Mavjud post tahrirlanadi)
         ↓
✨ BUYURTMA BAJARILDI      (Aynan o'sha post yakuniy holatga tahrirlanadi)
```

> **Eng muhim xususiyat:** Har bir buyurtma uchun kanalga ortiqcha yangi xabarlar yuborilmaydi. **Bitta buyurtma = Bitta proof post.**

### 🛠 Isbot kanalini sozlash bo'yicha qo'llanma:

1. **Telegramda yangi kanal yarating:** (Masalan: `PUBG UC | Isbotlar`).
2. **Botni kanalga Administrator qilib qo'shing:**
   - Botga **"Post Messages"** (Xabarlar yuborish) va **"Edit Messages"** (Xabarlarni tahrirlash) huquqlarini bering.
3. **Kanal ID raqamini oling:**
   - Masalan, `@userinfobot` yoki `@username_to_id_bot` orqali kanaldan bitta post forward qilib ID oling (Format: `-100xxxxxxxxxx`).
4. **`.env` fayliga sozlamalarni kiriting:**
   ```ini
   # Isbot kanali sozlamalari
   PROOF_CHANNEL_ID=-1001234567890
   PROOF_ENABLED=True
   PROOF_SHOW_PRICE=True
   PROOF_SHOW_PLAYER_ID=True
   PROOF_HASHTAGS=True
   PROOF_AUTO_POST=True
   ```
5. **Botni qayta ishga tushiring:**
   ```powershell
   python bot.py
   ```

### 🔒 Maxfiylik va Xavfsizlik:
- Kanal ommaviy (public) bo'lgani sababli, foydalanuvchining ismi, username, Telegram ID, karta raqami yoki to'lov cheki skrinshoti kanalga **aslo chiqarilmaydi**.
- PUBG Player ID xavfsiz maskalanadi (Masalan: `5123456789` -> `5123****6789`).
- Vaqt mintaqasi avtomatik tarzda Toshkent vaqti (`Asia/Tashkent`) bo'yicha ko'rsatiladi.
- Admin panelida har bir buyurtma uchun `[ 📢 Isbotga yuborish ]` yoki `[ 🔄 Isbot postini yangilash ]` tugmalari mavjud.
