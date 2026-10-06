# 🎮 PUBG MOBILE UC TOP-UP TELEGRAM BOT

Foydalanuvchilarga PUBG Mobile UC sotish uchun qulay, yengil, tezkor va professional darajadagi Telegram Bot loyihasi.

Ushbu loyiha **Django, Docker, Celery, Redis va PostgreSQL kabi og'ir vositalardan xoli** bo'lib, Windows yoki Linux tizimida to'g'ridan-to'g'ri `python bot.py` orqali bir necha soniyada ishga tushadi.

---

## ⚡ TEXNOLOGIYALAR STEKI

- **Dasturlash tili:** Python 3.12+
- **Telegram Bot Framework:** Aiogram 3.x (Asinxron FSM, zamonaviy Routerlar, Inline tugmalar)
- **Ma'lumotlar bazasi:** MongoDB Atlas (`motor` + `pymongo` - asinxron, bulutli NoSQL ma'lumotlar bazasi)
- **Avtomatik to'lovlar:** TezCheck hisoblari holatini `bot.py` ichidagi fon vazifasi tekshiradi; webhook serveri talab qilinmaydi.
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
│   ├── payment_monitor.py # Kutilayotgan to'lovlarni bot ichida tekshirish
│   ├── liogames.py       # LioGames signed API / player validation / delivery
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
MONGODB_URI=mongodb+srv://<db_username>:<db_password>@<cluster-host>/?retryWrites=true&w=majority
MONGODB_DB_NAME=pubg_uc_db

# TezCheck to'lov tizimi
TEZCHECK_API_KEY=your_tezcheck_key
TEZCHECK_CASH_DESK_CODE=your_cash_desk_code
TEZCHECK_BASE_URL=https://api.tezcheck.uz

# LioGames (maxfiy qiymatlarni faqat Render Environment yoki .env da saqlang)
LIOGAMES_MEMBER_CODE=your_member_code
LIOGAMES_SECRET=your_private_secret
LIOGAMES_AUTO_DELIVERY=false
LIOGAMES_PRICE_TIER=GOLD
LIOGAMES_VARIATIONS={"60":{"product_id":66719,"variation_id":533766}}
MAX_PROFIT_PERCENT=200
USD_RATE_URL=https://cbu.uz/uz/arkhiv-kursov-valyut/json/USD/
BACKUP_DIR=backups
```

### 4-qadam: Botni ishga tushirish

Windows terminalida botni oddiy buyruq bilan yoqing:
```powershell
python bot.py
```
> Bot MongoDB Atlas'ga ulanadi, kerakli kolleksiyalarni va standart UC paketlarini yaratadi.

TezCheck API kaliti va kassa kodi Render'dagi Environment Variables bo'limida ham kiritilgan bo'lishi kerak. `python bot.py` ishlayotgan paytda bot kutilayotgan to'lovlarni davriy tekshiradi; alohida webhook process yoki ommaviy webhook URL kerak emas.

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
7. **Balansni to'ldirish:** `Balansim` → `Balansni to'ldirish` ni tanlab, masalan `10000` yuboriladi. TezCheck to'lovni tasdiqlagach, summa avtomatik balansga qo'shiladi.

---

## 👨‍💼 ADMIN BOSHQARUV PANELI

Admin botda `/admin` buyrug'ini yuboradi.

### 1. Buyurtmalar boshqaruvi:
- **Kutilayotgan buyurtmalar (`WAITING_PAYMENT` / `MANUAL_REVIEW`):**
  - Foydalanuvchi karta orqali to'lab chek tashlaganda adminga skrinshot va order ma'lumoti keladi.
  - **✅ To'lovni tasdiqlash:** Bosilganda buyurtma `PAID` / `PROCESSING` ga o'tadi.
  - **❌ To'lovni rad etish:** Buyurtma bekor qilinadi, mijozga sababi xabar qilinadi.
  - **🎮 UC yuborildi:** Qo'lda yetkazilgandan keyin admin tasdiqlaydi. Avtomatik rejimda esa LioGames yakuniy muvaffaqiyat statusini qaytargandan keyingina buyurtma `COMPLETED` bo'ladi va isbot kanaliga yuboriladi.

### 2. UC Paketlari boshqaruvi:
- ➕ Yangi paket qo'shish (UC miqdori va narxi kiritiladi)
- ✏️ Narxini o'zgartirish
- 🔴/🟢 Aktiv/Deaktiv qilish (Mijozlarga ko'rinmas qilish)
- ❌ Paketni o'chirish

### 3. Tizim sozlamalari:
- **Narxlash manbasi:** `MANUAL` rejimida paket narxini admin qo'lda kiritadi; LioGames o'chiriladi, Player ID faqat format bo'yicha tekshiriladi va to'lovli buyurtma operatorga yuboriladi. `LIOGAMES` rejimida narx LioGames matritsasidan olinadi.
- 💳 Karta raqami va karta egasi ismini botdan turib o'zgartirish
- 📞 Qo'llab-quvvatlash (@admin username) sozlash
- 🔄 Yetkazib berish rejimini o'zgartirish: `MANUAL` (Qo'lda) yoki `AUTO` (LioGames; credentials va paket mapping'i sozlangan bo'lishi kerak)

### 4. Statistika:
- Jami buyurtmalar, bugungi buyurtmalar soni
- Jami tushum (summa), bugungi tushum
- Ro'yxatdan o'tgan foydalanuvchilar soni

---

## 🔒 XAVFSIZLIK VA IDEMPOTENCY

- **To'lovni tasdiqlash:** Bot TezCheck hisobining holatini o'zi so'raydi; faqat aynan kutilgan summa bilan jonli, muvaffaqiyatli to'lov tasdiqlanadi.
- **Takroriy to'lov himoyasi:** Bitta hisob qayta-qayta tekshirilsa ham balansga faqat bir marta qo'shiladi.
- **HMAC-SHA256 Imzo:** TezCheck API so'rovlari imzolanadi.
- **Player ID Validatsiya:** Foydalanuvchi xato yoki harf kiritganda ogohlantiriladi va noto'g'ri hisobga UC ketishi oldi olinadi.

---

## 📢 ISBOT KANALI (PROOF CHANNEL) TIZIMI

Kanalga faqat haqiqatan yetkazib berilishi yakunlangan buyurtma post qilinadi. To'lov tasdiqlanishi yoki yetkazish jarayoni isbot sifatida e'lon qilinmaydi:

```
✨ BUYURTMA BAJARILDI      (LioGames yoki admin yetkazilganini tasdiqlagach)
```

Buyurtma faqat `delivery_status=COMPLETED` bo'lsa yuboriladi. To'lovning o'zi UC yetkazildi degani emas.

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
