# PolyArb Signal

โปรแกรม Windows สำหรับตรวจจับโอกาส Arbitrage บน Polymarket พร้อมส่งแจ้งเตือนผ่าน Telegram

## คุณสมบัติหลัก

- **ตรวจจับ Arbitrage อัตโนมัติ** - สแกนตลาด Binary (YES/NO) บน Polymarket เพื่อหาโอกาสที่ `YES_ask + NO_ask < 1`
- **ระบบ Tiering อัจฉริยะ** - จัดลำดับความสำคัญของตลาดตาม volume, liquidity และประวัติ signal
- **แจ้งเตือน Telegram** - ส่ง signal ไปยัง Telegram Bot ทันทีเมื่อพบโอกาส
- **System Tray** - ทำงานเบื้องหลังและแจ้งเตือนผ่าน notification
- **Dashboard** - แสดงสถิติและ signal แบบ real-time

## การติดตั้ง

### วิธีที่ 1: ดาวน์โหลด Installer

1. ดาวน์โหลด `PolyArb-Signal-Setup.exe` จาก [Releases](../../releases)
2. รัน installer และทำตามขั้นตอน
3. เปิดโปรแกรมจาก Start Menu หรือ Desktop

### วิธีที่ 2: Build จาก Source

```bash
# Clone repository
git clone https://github.com/mil2cle/youtube.git
cd youtube/polyarb-signal

# ติดตั้ง dependencies
npm install

# รันในโหมด development
npm run dev

# Build สำหรับ Windows
npm run package:win
```

## การตั้งค่า

### 1. ตั้งค่า Telegram Bot

1. เปิด Telegram และค้นหา [@BotFather](https://t.me/BotFather)
2. ส่งคำสั่ง `/newbot` และทำตามขั้นตอน
3. คัดลอก **Bot Token** ที่ได้รับ
4. ค้นหา [@userinfobot](https://t.me/userinfobot) เพื่อดู **Chat ID** ของคุณ
5. กรอก Bot Token และ Chat ID ในหน้า Settings ของโปรแกรม

### 2. ตั้งค่าการสแกน

| พารามิเตอร์ | ค่าเริ่มต้น | คำอธิบาย |
|------------|-----------|---------|
| Threshold | 1% | ส่ง signal เมื่อ effective edge ≥ ค่านี้ |
| Fee Buffer | 0.2% | หักค่าธรรมเนียมโดยประมาณ |
| Cooldown | 5 นาที | รอก่อนส่ง signal ซ้ำสำหรับตลาดเดียวกัน |
| Debounce | 500ms | รอยืนยันก่อนส่ง signal |

### 3. ตั้งค่า Tiering

| พารามิเตอร์ | ค่าเริ่มต้น | คำอธิบาย |
|------------|-----------|---------|
| Tier A Max | 50 | จำนวนตลาดสูงสุดใน Tier A |
| Tier A Interval | 3 วินาที | ความถี่ในการสแกน Tier A |
| Tier B Interval | 30 วินาที | ความถี่ในการสแกน Tier B |
| Burst Mode | 10 นาที | ระยะเวลาที่ตลาดอยู่ใน Tier A หลังพบ near-arb |

## วิธีใช้งาน

1. **เริ่มสแกน** - กดปุ่ม "เริ่มสแกน" ในหน้า Dashboard
2. **ดู Signal** - Signal ที่พบจะแสดงในหน้า Dashboard และบันทึกในหน้า Logs
3. **จัดการตลาด** - Pin ตลาดที่สนใจให้อยู่ Tier A หรือ Blacklist ตลาดที่ไม่ต้องการ
4. **รับแจ้งเตือน** - Signal จะถูกส่งไปยัง Telegram Bot ที่ตั้งค่าไว้

## สูตรการคำนวณ

```
implied_total = best_ask_yes + best_ask_no
effective_edge = 1 - implied_total - fee_buffer

ถ้า effective_edge >= threshold → ส่ง Signal
```

**ตัวอย่าง:**
- YES Ask: 45¢
- NO Ask: 52¢
- Fee Buffer: 0.2%
- implied_total = 0.45 + 0.52 = 0.97
- effective_edge = 1 - 0.97 - 0.002 = 0.028 (2.8%)
- ถ้า threshold = 1% → ส่ง Signal!

## โครงสร้างโปรเจค

```
polyarb-signal/
├── src/
│   ├── main/                 # Electron main process
│   │   ├── services/         # Core services
│   │   │   ├── gammaClient.ts    # Gamma API client
│   │   │   ├── clobClient.ts     # CLOB API client
│   │   │   ├── wsClient.ts       # WebSocket client
│   │   │   ├── signalEngine.ts   # Signal detection engine
│   │   │   ├── telegramNotifier.ts
│   │   │   └── tieringSystem.ts
│   │   ├── utils/            # Utilities
│   │   │   ├── logger.ts
│   │   │   ├── settingsStore.ts
│   │   │   └── autoLaunch.ts
│   │   ├── index.ts          # Main entry point
│   │   └── preload.ts        # IPC bridge
│   ├── renderer/             # React UI
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Settings.tsx
│   │   │   ├── Logs.tsx
│   │   │   └── Markets.tsx
│   │   ├── App.tsx
│   │   └── main.tsx
│   └── shared/               # Shared types & constants
│       ├── types/
│       └── constants/
├── assets/                   # Icons & images
├── package.json
└── README.md
```

## API ที่ใช้

| API | Base URL | การใช้งาน |
|-----|----------|----------|
| Gamma API | `https://gamma-api.polymarket.com` | Market discovery, metadata |
| CLOB API | `https://clob.polymarket.com` | Orderbook, prices |
| WebSocket | `wss://ws-subscriptions-clob.polymarket.com/ws/` | Real-time updates |

## Rate Limits

- Gamma /markets: 300 requests / 10s
- CLOB (General): 9000 requests / 10s
- โปรแกรมมีระบบ rate limiting และ exponential backoff ในตัว

## ข้อจำกัด

- รองรับเฉพาะ Windows
- ต้องมีการเชื่อมต่ออินเทอร์เน็ต
- Signal เป็นข้อมูลอ้างอิงเท่านั้น ไม่ใช่คำแนะนำในการลงทุน
- ผู้ใช้ต้องตรวจสอบและตัดสินใจเองก่อนทำธุรกรรม

## License

MIT License

## Disclaimer

โปรแกรมนี้เป็นเครื่องมือสำหรับการตรวจจับโอกาส arbitrage เท่านั้น ไม่ใช่คำแนะนำในการลงทุน ผู้ใช้ต้องรับผิดชอบต่อการตัดสินใจและความเสี่ยงของตนเอง ทีมพัฒนาไม่รับผิดชอบต่อความเสียหายใดๆ ที่อาจเกิดขึ้นจากการใช้งานโปรแกรม
