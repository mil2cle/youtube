# WebSocket Notes - PolyArb Signal

## Polymarket WebSocket Endpoints

### Public Market Channel
- **URL**: `wss://ws-subscriptions-clob.polymarket.com/ws/market`
- **ไม่ต้อง authentication**
- ใช้สำหรับรับ real-time orderbook updates

### User Channel (ไม่ได้ใช้ในแอปนี้)
- **URL**: `wss://ws-subscriptions-clob.polymarket.com/ws/user`
- **ต้อง authentication**

## Subscribe Protocol

### Initial Subscribe
```json
{
  "assets_ids": ["<tokenId1>", "<tokenId2>"],
  "type": "market"
}
```

### Subscribe เพิ่ม
```json
{
  "assets_ids": ["<tokenId>"],
  "operation": "subscribe"
}
```

### Unsubscribe
```json
{
  "assets_ids": ["<tokenId>"],
  "operation": "unsubscribe"
}
```

## Features ที่ implement แล้ว

1. **Auto Reconnect** - เชื่อมต่อใหม่อัตโนมัติเมื่อหลุด
2. **Exponential Backoff** - รอนานขึ้นทุกครั้งที่ reconnect ล้มเหลว (1s, 2s, 4s, ... max 30s)
3. **Jitter** - เพิ่ม random delay เพื่อป้องกัน thundering herd
4. **Heartbeat** - ส่ง ping ทุก 30 วินาที ตรวจจับ stale connection ที่ 60 วินาที
5. **Batching** - รวม subscribe/unsubscribe requests เพื่อลด rate limit
6. **Degraded Mode** - fallback ไปใช้ REST polling เมื่อ WebSocket ล้มเหลว

## Status ที่แสดงใน UI

| Status | ความหมาย |
|--------|----------|
| 🟢 connected | เชื่อมต่อ WebSocket สำเร็จ |
| 🟡 connecting | กำลังเชื่อมต่อ... |
| 🟡 reconnecting | กำลังเชื่อมต่อใหม่... |
| 🟠 degraded | ใช้ REST polling แทน (WS ล้มเหลว) |
| 🔴 error | เกิดข้อผิดพลาด |
| ⚪ disconnected | ยังไม่ได้เชื่อมต่อ |

## ทดสอบ WebSocket

ไปที่หน้า **ตั้งค่า** แล้วกดปุ่ม **Test WebSocket** เพื่อทดสอบการเชื่อมต่อ
- จะเชื่อมต่อและ subscribe 1-2 tokens
- รอรับ messages 10 วินาที
- แสดงผลว่าได้รับ messages กี่ข้อความ
