//+------------------------------------------------------------------+
//|                                           TrendFollowGrid.mq5    |
//|                        Expert Advisor: Trend-follow Grid          |
//|                        สำหรับ BTCUSD (Hedging Account)             |
//+------------------------------------------------------------------+
//| วิธีใช้งาน:                                                        |
//|   1. คัดลอกไฟล์นี้ไปที่ MQL5/Experts/                               |
//|   2. Compile ใน MetaEditor (MQL5 เท่านั้น)                          |
//|   3. แนบ EA กับ chart BTCUSD (หรือ symbol ที่ต้องการ)                |
//|   4. ตรวจสอบว่าบัญชีเป็น Hedging account                            |
//|   5. เปิด Allow Algo Trading                                       |
//|                                                                    |
//| Inputs สำคัญ:                                                      |
//|   - TradeMode: AUTO_TREND ใช้ EMA200 H1 กำหนดทิศทาง                |
//|   - BaseLot: ล็อตเริ่มต้น (0.01)                                    |
//|   - MaxExposureLots: ล็อตรวมสูงสุดต่อฝั่ง                           |
//|   - BasketTPPercent/BasketTPUSD: เป้าหมายกำไร Basket                |
//|   - EnablePartialClose: ระบบถอนเสียง (Unwind)                       |
//|   - DDStopPercent: หยุดเมื่อ Equity DD ถึงเกณฑ์                     |
//|                                                                    |
//| วิธี Backtest:                                                     |
//|   - ใช้ Strategy Tester, เลือก "Every tick based on real ticks"     |
//|   - เลือก Hedging mode                                             |
//|   - Symbol: BTCUSD, Period: Any (EA ใช้ multi-timeframe)            |
//|   - ตั้ง Deposit เริ่มต้นตามต้องการ                                  |
//|                                                                    |
//| Placeholder/Optional:                                              |
//|   - UseLotScaling / LotScaleMode / LotScaleFactor (phase 2)        |
//|   - UnwindOnlyWhenPriceNearVWAPPoints (optional enhancement)        |
//|                                                                    |
//| v1.01 Changes:                                                     |
//|   - EMA/ATR ใช้ shift=1 (แท่งที่ปิดแล้ว) กันเทรนด์ repaint         |
//|   - Pending maintenance: tolerance + modify cooldown               |
//|   - ClampVolume() ทุกจุดที่ส่งคำสั่ง                                |
//+------------------------------------------------------------------+
#property copyright "One More Time (OMT)"
#property link      ""
#property version   "1.01"
#property strict

#include <Trade\Trade.mqh>

//+------------------------------------------------------------------+
//| Enumerations                                                      |
//+------------------------------------------------------------------+
enum ENUM_TRADE_MODE
{
   AUTO_TREND = 0,   // AUTO_TREND - ใช้ EMA กำหนดทิศทาง
   BUY_ONLY   = 1,   // BUY_ONLY - เปิดเฉพาะ BUY
   SELL_ONLY  = 2    // SELL_ONLY - เปิดเฉพาะ SELL
};

enum ENUM_ENTRY_TYPE
{
   ENTRY_MARKET        = 0,  // MARKET - เปิดตลาดทันที
   ENTRY_PENDING_FIRST = 1   // PENDING_FIRST - วาง pending ก่อน
};

enum ENUM_LOT_SCALE_MODE
{
   LOT_FIXED  = 0,  // FIXED (placeholder)
   LOT_LINEAR = 1,  // LINEAR (placeholder)
   LOT_FIBO   = 2   // FIBO (placeholder)
};

enum ENUM_DD_STOP_MODE
{
   PAUSE_NEW_ONLY    = 0,  // PAUSE_NEW_ONLY - หยุดเปิดใหม่เท่านั้น
   CLEAR_PENDINGS    = 1,  // CLEAR_PENDINGS - ลบ pending + หยุดเปิดใหม่
   EMERGENCY_REDUCE  = 2   // EMERGENCY_REDUCE - ลบ pending + ปิดบางส่วน
};

enum ENUM_BASKET_TP_MODE
{
   PERCENT_EQUITY = 0,  // PERCENT_EQUITY - % ของ Equity
   FIXED_USD      = 1   // FIXED_USD - จำนวนเงินคงที่
};

enum ENUM_UNWIND_SELECTION
{
   LARGEST_VOLUME_FIRST    = 0,  // LargestVolumeFirst
   HIGHEST_PROFIT_FIRST    = 1,  // HighestProfitFirst
   FARTHEST_FROM_VWAP_FIRST = 2  // FarthestFromVWAPFirst
};

enum ENUM_TREND_DIRECTION
{
   TREND_UP      = 1,
   TREND_DOWN    = -1,
   TREND_NEUTRAL = 0
};

//+------------------------------------------------------------------+
//| Input Parameters                                                  |
//+------------------------------------------------------------------+
// ==================== General ====================
input group "=== General ==="
input bool               EnableEA            = true;           // Enable EA
input int                MagicNumber         = 123456;         // Magic Number
input string             SymbolFilter        = "";             // Symbol Filter (ว่าง = ใช้ chart symbol)
input ENUM_TRADE_MODE    TradeMode           = AUTO_TREND;     // Trade Mode
input bool               AllowFlip           = false;          // Allow Flip (ห้ามเปิดฝั่งตรงข้ามถ้ายังมีฝั่งเดิม)
input int                CooldownSec         = 10;             // Cooldown Seconds
input int                MaxOrdersPerCycle   = 1;              // Max Orders Per Cycle (กันยิงถี่)

// ==================== Lot & Exposure ====================
input group "=== Lot & Exposure ==="
input double             BaseLot             = 0.01;           // Base Lot
input double             MaxExposureLots     = 0.05;           // Max Exposure Lots (ต่อฝั่ง)
input int                MaxPositionsPerSide = 10;             // Max Positions Per Side
input bool               UseLotScaling       = false;          // Use Lot Scaling (placeholder)
input ENUM_LOT_SCALE_MODE LotScaleMode       = LOT_FIXED;     // Lot Scale Mode (placeholder)
input double             LotScaleFactor      = 1.2;            // Lot Scale Factor (placeholder)

// ==================== Trend Filter ====================
input group "=== Trend Filter ==="
input ENUM_TIMEFRAMES    TrendTF             = PERIOD_H1;      // Trend Timeframe
input int                TrendEMA            = 200;            // Trend EMA Period
input double             NeutralBufferPercent = 0.0010;        // Neutral Buffer (0.10%)

// ==================== Grid Distance ====================
input group "=== Grid Distance ==="
input ENUM_TIMEFRAMES    ATR_TF              = PERIOD_M15;     // ATR Timeframe
input int                ATR_Period          = 14;             // ATR Period
input double             ATR_Multiplier      = 1.2;            // ATR Multiplier
input double             MinGridPercent      = 0.0015;         // Min Grid Percent (0.15%)
input double             MinGridPoints       = 0;              // Min Grid Points (0=ปิด)

// ==================== Entry ====================
input group "=== Entry ==="
input ENUM_ENTRY_TYPE    EntryType           = ENTRY_MARKET;   // Entry Type
input int                FirstPendingDistancePoints = 300;     // First Pending Distance (points)

// ==================== Spread Gate ====================
input group "=== Spread Gate ==="
input int                MaxSpreadPoints     = 50;             // Max Spread Points

// ==================== Volatility Pause ====================
input group "=== Volatility Pause ==="
input bool               EnableVolatilityPause = true;         // Enable Volatility Pause
input ENUM_TIMEFRAMES    ATRPauseTF          = PERIOD_M15;     // ATR Pause Timeframe
input int                ATRPausePeriod      = 14;             // ATR Pause Period
input double             ATRPauseThresholdDollar = 0;          // ATR Pause Threshold $ (0=ปิด)

// ==================== Equity / DD Stop ====================
input group "=== Equity / DD Stop ==="
input bool               EnableDDStop        = true;           // Enable DD Stop
input double             DDStopPercent       = 0.12;           // DD Stop Percent (12%)
input ENUM_DD_STOP_MODE  DDStopMode          = CLEAR_PENDINGS; // DD Stop Mode

// ==================== Exit - Basket TP ====================
input group "=== Exit - Basket TP ==="
input ENUM_BASKET_TP_MODE BasketTPMode       = PERCENT_EQUITY; // Basket TP Mode
input double             BasketTPPercent     = 0.0025;         // Basket TP Percent (0.25%)
input double             BasketTPUSD         = 30;             // Basket TP USD (ใช้ถ้า FIXED_USD)

// ==================== Partial Close / Unwind ====================
input group "=== Partial Close / Unwind ==="
input bool               EnablePartialClose  = true;           // Enable Partial Close
input double             KeepMinLotPerPosition = 0.01;         // Keep Min Lot Per Position
input double             UnwindStepLot       = 0.01;           // Unwind Step Lot (0=ปิดทีเดียว)
input double             StartUnwindAtBasketProfitUSD = 0;     // Start Unwind At Basket Profit USD
input bool               CloseOnlyIfPositionProfitPositive = true; // Close Only If Position Profit > 0
input bool               AllowCloseAtSmallLossIfBasketProfitPositive = false; // Allow Close At Small Loss
input int                MaxPartialClosesPerCycle = 1;         // Max Partial Closes Per Cycle
input ENUM_UNWIND_SELECTION UnwindSelectionMode = LARGEST_VOLUME_FIRST; // Unwind Selection Mode
input int                UnwindOnlyWhenPriceNearVWAPPoints = 0; // Unwind Near VWAP Points (0=ปิด)

// ==================== Pending Maintenance ====================
input group "=== Pending Maintenance ==="
input int                PendingTolerancePoints = 50;          // Pending Tolerance Points (ไม่ modify ถ้าต่างน้อยกว่านี้)
input int                PendingModifyCooldownSec = 5;         // Pending Modify Cooldown Seconds

//+------------------------------------------------------------------+
//| Global Variables                                                  |
//+------------------------------------------------------------------+
CTrade         trade;
string         g_symbol;
datetime       g_lastTradeTime;
datetime       g_lastPartialCloseTime;
datetime       g_lastPendingModifyTime;    // v1.01: cooldown สำหรับ pending modify
double         g_peakEquity;
bool           g_ddStopTriggered;
int            g_emaHandle;
int            g_atrHandle;
int            g_atrPauseHandle;

//+------------------------------------------------------------------+
//| Expert initialization function                                    |
//+------------------------------------------------------------------+
int OnInit()
{
   // --- Parse symbol ---
   g_symbol = ParseSymbol();
   
   // --- Validate hedging account ---
   if(AccountInfoInteger(ACCOUNT_MARGIN_MODE) != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
   {
      Print("ERROR: This EA requires a Hedging account!");
      return(INIT_FAILED);
   }
   
   // --- Setup CTrade ---
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(50);
   trade.SetTypeFilling(ORDER_FILLING_IOC);
   
   // --- Create indicator handles ---
   g_emaHandle = iMA(g_symbol, TrendTF, TrendEMA, 0, MODE_EMA, PRICE_CLOSE);
   if(g_emaHandle == INVALID_HANDLE)
   {
      Print("ERROR: Failed to create EMA indicator handle");
      return(INIT_FAILED);
   }
   
   g_atrHandle = iATR(g_symbol, ATR_TF, ATR_Period);
   if(g_atrHandle == INVALID_HANDLE)
   {
      Print("ERROR: Failed to create ATR indicator handle");
      return(INIT_FAILED);
   }
   
   g_atrPauseHandle = iATR(g_symbol, ATRPauseTF, ATRPausePeriod);
   if(g_atrPauseHandle == INVALID_HANDLE)
   {
      Print("ERROR: Failed to create ATR Pause indicator handle");
      return(INIT_FAILED);
   }
   
   // --- Initialize globals ---
   g_lastTradeTime = 0;
   g_lastPartialCloseTime = 0;
   g_lastPendingModifyTime = 0;
   g_peakEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   g_ddStopTriggered = false;
   
   Print("TrendFollowGrid EA v1.01 initialized on ", g_symbol, " | Magic: ", MagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                  |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_emaHandle != INVALID_HANDLE) IndicatorRelease(g_emaHandle);
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
   if(g_atrPauseHandle != INVALID_HANDLE) IndicatorRelease(g_atrPauseHandle);
   Print("TrendFollowGrid EA deinitialized. Reason: ", reason);
}

//+------------------------------------------------------------------+
//| Expert tick function                                              |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!EnableEA) return;
   
   // --- Update peak equity for DD tracking ---
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity > g_peakEquity) g_peakEquity = equity;
   
   // --- Check DD Stop ---
   bool ddTriggered = false;
   if(EnableDDStop)
   {
      double ddPercent = (g_peakEquity > 0) ? (g_peakEquity - equity) / g_peakEquity : 0;
      if(ddPercent >= DDStopPercent)
      {
         ddTriggered = true;
         if(!g_ddStopTriggered)
         {
            Print("DD STOP TRIGGERED! DD=", DoubleToString(ddPercent*100,2), "%");
            g_ddStopTriggered = true;
            HandleDDStop();
         }
      }
      else
      {
         g_ddStopTriggered = false;
      }
   }
   
   // --- Get trend direction (shift=1, แท่งที่ปิดแล้ว) ---
   ENUM_TREND_DIRECTION trend = GetTrendDirection();
   
   // --- Basket TP check (always runs, even during DD stop) ---
   CheckBasketTP(POSITION_TYPE_BUY);
   CheckBasketTP(POSITION_TYPE_SELL);
   
   // --- Partial Close / Unwind (always runs, even during DD stop) ---
   if(EnablePartialClose)
   {
      ProcessPartialClose(POSITION_TYPE_BUY);
      ProcessPartialClose(POSITION_TYPE_SELL);
   }
   
   // --- If DD stop triggered, skip new entries/grid ---
   if(ddTriggered && DDStopMode != PAUSE_NEW_ONLY)
      return;
   if(ddTriggered && DDStopMode == PAUSE_NEW_ONLY)
   {
      // Still allow basket TP and partial close (already done above)
      return;
   }
   
   // --- Check spread gate ---
   if(!SpreadOK())
      return;
   
   // --- Check volatility pause ---
   if(VolatilityPaused())
      return;
   
   // --- Cooldown check ---
   if(!CooldownOK())
      return;
   
   // --- Determine which sides to trade ---
   bool allowBuy  = false;
   bool allowSell = false;
   
   switch(TradeMode)
   {
      case AUTO_TREND:
         if(trend == TREND_UP)   allowBuy = true;
         if(trend == TREND_DOWN) allowSell = true;
         break;
      case BUY_ONLY:
         allowBuy = true;
         break;
      case SELL_ONLY:
         allowSell = true;
         break;
   }
   
   // --- Flip rule ---
   if(!AllowFlip)
   {
      int buyCount  = CountPositionsByType(POSITION_TYPE_BUY);
      int sellCount = CountPositionsByType(POSITION_TYPE_SELL);
      if(buyCount > 0)  allowSell = false;
      if(sellCount > 0) allowBuy  = false;
   }
   
   // --- Process BUY side ---
   if(allowBuy)
   {
      ProcessBuySide();
   }
   
   // --- Process SELL side ---
   if(allowSell)
   {
      ProcessSellSide();
   }
}

//+------------------------------------------------------------------+
//| HELPER: Parse/Select Symbol                                       |
//+------------------------------------------------------------------+
string ParseSymbol()
{
   if(SymbolFilter != "" && SymbolFilter != " ")
      return SymbolFilter;
   return _Symbol;
}

//+------------------------------------------------------------------+
//| HELPER: Spread Check                                              |
//+------------------------------------------------------------------+
bool SpreadOK()
{
   long spread = SymbolInfoInteger(g_symbol, SYMBOL_SPREAD);
   return (spread <= MaxSpreadPoints);
}

int SpreadPoints()
{
   return (int)SymbolInfoInteger(g_symbol, SYMBOL_SPREAD);
}

//+------------------------------------------------------------------+
//| HELPER: Cooldown Check                                            |
//+------------------------------------------------------------------+
bool CooldownOK()
{
   if(CooldownSec <= 0) return true;
   return (TimeCurrent() - g_lastTradeTime >= CooldownSec);
}

//+------------------------------------------------------------------+
//| HELPER: Pending Modify Cooldown Check                             |
//+------------------------------------------------------------------+
bool PendingModifyCooldownOK()
{
   if(PendingModifyCooldownSec <= 0) return true;
   return (TimeCurrent() - g_lastPendingModifyTime >= PendingModifyCooldownSec);
}

//+------------------------------------------------------------------+
//| HELPER: Clamp Volume to broker limits                             |
//| ใช้ทุกครั้งก่อนส่งคำสั่ง เพื่อให้ volume ถูกต้องตาม                  |
//| SYMBOL_VOLUME_MIN / SYMBOL_VOLUME_MAX / SYMBOL_VOLUME_STEP        |
//+------------------------------------------------------------------+
double ClampVolume(double vol)
{
   double minLot  = SymbolInfoDouble(g_symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(g_symbol, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(g_symbol, SYMBOL_VOLUME_STEP);
   
   if(stepLot > 0)
      vol = MathFloor(vol / stepLot) * stepLot;
   
   vol = MathMax(vol, minLot);
   vol = MathMin(vol, maxLot);
   
   return NormalizeDouble(vol, 8);
}

//+------------------------------------------------------------------+
//| HELPER: Check if volume is valid (>= min lot)                     |
//+------------------------------------------------------------------+
bool IsVolumeValid(double vol)
{
   double minLot = SymbolInfoDouble(g_symbol, SYMBOL_VOLUME_MIN);
   return (vol >= minLot);
}

//+------------------------------------------------------------------+
//| HELPER: Count Positions By Type                                   |
//+------------------------------------------------------------------+
int CountPositionsByType(ENUM_POSITION_TYPE posType)
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != g_symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == posType)
         count++;
   }
   return count;
}

//+------------------------------------------------------------------+
//| HELPER: Sum Volume By Type                                        |
//+------------------------------------------------------------------+
double SumVolumeByType(ENUM_POSITION_TYPE posType)
{
   double vol = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != g_symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == posType)
         vol += PositionGetDouble(POSITION_VOLUME);
   }
   return vol;
}

//+------------------------------------------------------------------+
//| HELPER: Floating Profit By Type (profit+swap+commission)          |
//+------------------------------------------------------------------+
double FloatingProfitByType(ENUM_POSITION_TYPE posType)
{
   double profit = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != g_symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == posType)
      {
         profit += PositionGetDouble(POSITION_PROFIT)
                 + PositionGetDouble(POSITION_SWAP)
                 + (2.0 * PositionGetDouble(POSITION_COMMISSION));
      }
   }
   return profit;
}

//+------------------------------------------------------------------+
//| HELPER: Get EMA value (shift=1, แท่งที่ปิดแล้ว)                    |
//+------------------------------------------------------------------+
double GetEMA()
{
   double buf[1];
   if(CopyBuffer(g_emaHandle, 0, 1, 1, buf) <= 0)  // shift=1
   {
      Print("WARNING: Failed to get EMA value");
      return 0;
   }
   return buf[0];
}

//+------------------------------------------------------------------+
//| HELPER: Get ATR value for grid (shift=1, แท่งที่ปิดแล้ว)           |
//+------------------------------------------------------------------+
double GetATR()
{
   double buf[1];
   if(CopyBuffer(g_atrHandle, 0, 1, 1, buf) <= 0)  // shift=1
   {
      Print("WARNING: Failed to get ATR value");
      return 0;
   }
   return buf[0];
}

//+------------------------------------------------------------------+
//| HELPER: Get ATR Pause value (shift=1, แท่งที่ปิดแล้ว)              |
//+------------------------------------------------------------------+
double GetATRPause()
{
   double buf[1];
   if(CopyBuffer(g_atrPauseHandle, 0, 1, 1, buf) <= 0)  // shift=1
   {
      Print("WARNING: Failed to get ATR Pause value");
      return 0;
   }
   return buf[0];
}

//+------------------------------------------------------------------+
//| HELPER: Compute Grid Points                                       |
//+------------------------------------------------------------------+
double ComputeGridPoints()
{
   double atr = GetATR();
   double price = SymbolInfoDouble(g_symbol, SYMBOL_BID);
   double point = SymbolInfoDouble(g_symbol, SYMBOL_POINT);
   
   if(point == 0) return 0;
   
   double gridDollar = MathMax(atr * ATR_Multiplier, price * MinGridPercent);
   double gridPoints = gridDollar / point;
   
   if(MinGridPoints > 0)
      gridPoints = MathMax(gridPoints, MinGridPoints);
   
   return gridPoints;
}

//+------------------------------------------------------------------+
//| HELPER: Extreme Open Price (lowest for BUY, highest for SELL)     |
//+------------------------------------------------------------------+
double ExtremeOpenPrice(ENUM_POSITION_TYPE posType)
{
   double extreme = 0;
   bool first = true;
   
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != g_symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) != posType) continue;
      
      double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      if(first)
      {
         extreme = openPrice;
         first = false;
      }
      else
      {
         if(posType == POSITION_TYPE_BUY)
            extreme = MathMin(extreme, openPrice);
         else
            extreme = MathMax(extreme, openPrice);
      }
   }
   return extreme;
}

//+------------------------------------------------------------------+
//| HELPER: Get VWAP By Side                                          |
//+------------------------------------------------------------------+
double GetVWAPBySide(ENUM_POSITION_TYPE posType)
{
   double sumPriceVol = 0;
   double sumVol = 0;
   
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != g_symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) != posType) continue;
      
      double vol = PositionGetDouble(POSITION_VOLUME);
      double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      sumPriceVol += openPrice * vol;
      sumVol += vol;
   }
   
   if(sumVol == 0) return 0;
   return sumPriceVol / sumVol;
}

//+------------------------------------------------------------------+
//| HELPER: Delete Pendings By Side                                   |
//+------------------------------------------------------------------+
void DeletePendingsBySide(ENUM_POSITION_TYPE posType)
{
   ENUM_ORDER_TYPE limitType = (posType == POSITION_TYPE_BUY) ? ORDER_TYPE_BUY_LIMIT : ORDER_TYPE_SELL_LIMIT;
   
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0) continue;
      if(OrderGetString(ORDER_SYMBOL) != g_symbol) continue;
      if(OrderGetInteger(ORDER_MAGIC) != MagicNumber) continue;
      if((ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE) == limitType)
      {
         trade.OrderDelete(ticket);
      }
   }
}

//+------------------------------------------------------------------+
//| HELPER: Count Pending Orders By Side                              |
//+------------------------------------------------------------------+
int CountPendingsBySide(ENUM_POSITION_TYPE posType)
{
   ENUM_ORDER_TYPE limitType = (posType == POSITION_TYPE_BUY) ? ORDER_TYPE_BUY_LIMIT : ORDER_TYPE_SELL_LIMIT;
   int count = 0;
   
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0) continue;
      if(OrderGetString(ORDER_SYMBOL) != g_symbol) continue;
      if(OrderGetInteger(ORDER_MAGIC) != MagicNumber) continue;
      if((ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE) == limitType)
         count++;
   }
   return count;
}

//+------------------------------------------------------------------+
//| HELPER: Maintain One Pending By Side (v1.01 - smart tolerance)    |
//|                                                                    |
//| Logic:                                                             |
//|   1. วนหา pending ที่ตรง type ของ EA (magic+symbol)                |
//|   2. ถ้ามีมากกว่า 1 => ลบตัวเกินให้เหลือ 1                         |
//|   3. ถ้ามี 1 ตัว:                                                   |
//|      - ถ้าราคาต่างจากเป้า < PendingTolerancePoints => ไม่ทำอะไร    |
//|      - ถ้าต่างมากกว่า => modify (ถ้า cooldown ผ่าน)                 |
//|   4. ถ้าไม่มีเลย => วาง pending ใหม่                               |
//+------------------------------------------------------------------+
void MaintainOnePendingBySide(ENUM_POSITION_TYPE posType, double targetPrice, double lot)
{
   ENUM_ORDER_TYPE limitType = (posType == POSITION_TYPE_BUY) ? ORDER_TYPE_BUY_LIMIT : ORDER_TYPE_SELL_LIMIT;
   double point = SymbolInfoDouble(g_symbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(g_symbol, SYMBOL_DIGITS);
   
   targetPrice = NormalizeDouble(targetPrice, digits);
   lot = ClampVolume(lot);
   
   // --- Collect all our pending tickets of this type ---
   ulong  foundTickets[];
   double foundPrices[];
   int    foundCount = 0;
   
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0) continue;
      if(OrderGetString(ORDER_SYMBOL) != g_symbol) continue;
      if(OrderGetInteger(ORDER_MAGIC) != MagicNumber) continue;
      if((ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE) == limitType)
      {
         ArrayResize(foundTickets, foundCount + 1);
         ArrayResize(foundPrices, foundCount + 1);
         foundTickets[foundCount] = ticket;
         foundPrices[foundCount]  = NormalizeDouble(OrderGetDouble(ORDER_PRICE_OPEN), digits);
         foundCount++;
      }
   }
   
   // --- Case: no pending exists => place new ---
   if(foundCount == 0)
   {
      if(!PendingModifyCooldownOK()) return;
      
      if(posType == POSITION_TYPE_BUY)
         trade.BuyLimit(lot, targetPrice, g_symbol, 0, 0, ORDER_TIME_GTC, 0, "TFG_BuyGrid");
      else
         trade.SellLimit(lot, targetPrice, g_symbol, 0, 0, ORDER_TIME_GTC, 0, "TFG_SellGrid");
      
      g_lastPendingModifyTime = TimeCurrent();
      return;
   }
   
   // --- Case: more than 1 pending => keep first, delete rest ---
   if(foundCount > 1)
   {
      for(int i = 1; i < foundCount; i++)
         trade.OrderDelete(foundTickets[i]);
   }
   
   // --- Case: exactly 1 pending => check tolerance ---
   ulong  existingTicket = foundTickets[0];
   double existingPrice  = foundPrices[0];
   double diffPoints     = MathAbs(existingPrice - targetPrice) / point;
   
   // ถ้าต่างน้อยกว่า tolerance => ไม่ต้อง modify
   if(diffPoints < PendingTolerancePoints)
      return;
   
   // ต่างมากกว่า tolerance => modify (ถ้า cooldown ผ่าน)
   if(!PendingModifyCooldownOK()) return;
   
   // Modify pending order to new price
   if(trade.OrderModify(existingTicket, targetPrice, 0, 0, ORDER_TIME_GTC, 0))
   {
      g_lastPendingModifyTime = TimeCurrent();
   }
   else
   {
      // ถ้า modify fail => ลบแล้ววางใหม่
      Print("OrderModify failed (err=", GetLastError(), "), delete+replace");
      trade.OrderDelete(existingTicket);
      
      if(posType == POSITION_TYPE_BUY)
         trade.BuyLimit(lot, targetPrice, g_symbol, 0, 0, ORDER_TIME_GTC, 0, "TFG_BuyGrid");
      else
         trade.SellLimit(lot, targetPrice, g_symbol, 0, 0, ORDER_TIME_GTC, 0, "TFG_SellGrid");
      
      g_lastPendingModifyTime = TimeCurrent();
   }
}

//+------------------------------------------------------------------+
//| HELPER: Get Trend Direction (shift=1, แท่งที่ปิดแล้ว)              |
//+------------------------------------------------------------------+
ENUM_TREND_DIRECTION GetTrendDirection()
{
   double ema = GetEMA();  // shift=1 inside
   if(ema == 0) return TREND_NEUTRAL;
   
   // Get close price on TrendTF, shift=1 (แท่งที่ปิดแล้ว)
   double close[];
   if(CopyClose(g_symbol, TrendTF, 1, 1, close) <= 0)  // shift=1
      return TREND_NEUTRAL;
   
   double upperBand = ema * (1.0 + NeutralBufferPercent);
   double lowerBand = ema * (1.0 - NeutralBufferPercent);
   
   if(close[0] > upperBand)
      return TREND_UP;
   if(close[0] < lowerBand)
      return TREND_DOWN;
   
   return TREND_NEUTRAL;
}

//+------------------------------------------------------------------+
//| HELPER: Volatility Paused (shift=1)                               |
//+------------------------------------------------------------------+
bool VolatilityPaused()
{
   if(!EnableVolatilityPause) return false;
   if(ATRPauseThresholdDollar <= 0) return false;
   
   double atr = GetATRPause();  // shift=1 inside
   return (atr > ATRPauseThresholdDollar);
}

//+------------------------------------------------------------------+
//| HELPER: Get Lot (with placeholder for scaling + ClampVolume)      |
//+------------------------------------------------------------------+
double GetLot(int positionCount)
{
   double lot = BaseLot;
   
   // Placeholder for lot scaling (phase 2)
   if(UseLotScaling)
   {
      switch(LotScaleMode)
      {
         case LOT_LINEAR:
            lot = BaseLot * (1.0 + LotScaleFactor * positionCount);
            break;
         case LOT_FIBO:
            lot = BaseLot * MathPow(LotScaleFactor, positionCount);
            break;
         default: // LOT_FIXED
            lot = BaseLot;
            break;
      }
   }
   
   return ClampVolume(lot);
}

//+------------------------------------------------------------------+
//| Process BUY Side                                                  |
//+------------------------------------------------------------------+
void ProcessBuySide()
{
   int buyCount = CountPositionsByType(POSITION_TYPE_BUY);
   double buyVolume = SumVolumeByType(POSITION_TYPE_BUY);
   double lot = GetLot(buyCount);
   
   // --- No BUY positions: open initial ---
   if(buyCount == 0)
   {
      // Check exposure
      if(buyVolume + lot > MaxExposureLots) return;
      
      if(EntryType == ENTRY_MARKET)
      {
         double ask = SymbolInfoDouble(g_symbol, SYMBOL_ASK);
         if(trade.Buy(lot, g_symbol, ask, 0, 0, "TFG_BuyInit"))
         {
            g_lastTradeTime = TimeCurrent();
            Print("Opened initial BUY: ", lot, " lots at ", ask);
         }
      }
      else // PENDING_FIRST
      {
         double ask = SymbolInfoDouble(g_symbol, SYMBOL_ASK);
         double point = SymbolInfoDouble(g_symbol, SYMBOL_POINT);
         double pendingPrice = ask - FirstPendingDistancePoints * point;
         int digits = (int)SymbolInfoInteger(g_symbol, SYMBOL_DIGITS);
         pendingPrice = NormalizeDouble(pendingPrice, digits);
         
         if(CountPendingsBySide(POSITION_TYPE_BUY) == 0)
         {
            trade.BuyLimit(lot, pendingPrice, g_symbol, 0, 0, ORDER_TIME_GTC, 0, "TFG_BuyPendInit");
            g_lastTradeTime = TimeCurrent();
            Print("Placed initial BUY LIMIT: ", lot, " lots at ", pendingPrice);
         }
      }
      return;
   }
   
   // --- Has BUY positions: maintain grid ---
   // Check limits
   if(buyCount >= MaxPositionsPerSide) 
   {
      DeletePendingsBySide(POSITION_TYPE_BUY);
      return;
   }
   if(buyVolume + lot > MaxExposureLots)
   {
      DeletePendingsBySide(POSITION_TYPE_BUY);
      return;
   }
   
   // Compute grid price
   double lowestOpen = ExtremeOpenPrice(POSITION_TYPE_BUY);
   double gridPoints = ComputeGridPoints();
   double point = SymbolInfoDouble(g_symbol, SYMBOL_POINT);
   double gridPrice = lowestOpen - gridPoints * point;
   int digits = (int)SymbolInfoInteger(g_symbol, SYMBOL_DIGITS);
   gridPrice = NormalizeDouble(gridPrice, digits);
   
   // Validate price
   if(gridPrice <= 0) return;
   
   // Maintain one pending (smart tolerance + cooldown)
   MaintainOnePendingBySide(POSITION_TYPE_BUY, gridPrice, lot);
}

//+------------------------------------------------------------------+
//| Process SELL Side                                                  |
//+------------------------------------------------------------------+
void ProcessSellSide()
{
   int sellCount = CountPositionsByType(POSITION_TYPE_SELL);
   double sellVolume = SumVolumeByType(POSITION_TYPE_SELL);
   double lot = GetLot(sellCount);
   
   // --- No SELL positions: open initial ---
   if(sellCount == 0)
   {
      // Check exposure
      if(sellVolume + lot > MaxExposureLots) return;
      
      if(EntryType == ENTRY_MARKET)
      {
         double bid = SymbolInfoDouble(g_symbol, SYMBOL_BID);
         if(trade.Sell(lot, g_symbol, bid, 0, 0, "TFG_SellInit"))
         {
            g_lastTradeTime = TimeCurrent();
            Print("Opened initial SELL: ", lot, " lots at ", bid);
         }
      }
      else // PENDING_FIRST
      {
         double bid = SymbolInfoDouble(g_symbol, SYMBOL_BID);
         double point = SymbolInfoDouble(g_symbol, SYMBOL_POINT);
         double pendingPrice = bid + FirstPendingDistancePoints * point;
         int digits = (int)SymbolInfoInteger(g_symbol, SYMBOL_DIGITS);
         pendingPrice = NormalizeDouble(pendingPrice, digits);
         
         if(CountPendingsBySide(POSITION_TYPE_SELL) == 0)
         {
            trade.SellLimit(lot, pendingPrice, g_symbol, 0, 0, ORDER_TIME_GTC, 0, "TFG_SellPendInit");
            g_lastTradeTime = TimeCurrent();
            Print("Placed initial SELL LIMIT: ", lot, " lots at ", pendingPrice);
         }
      }
      return;
   }
   
   // --- Has SELL positions: maintain grid ---
   if(sellCount >= MaxPositionsPerSide)
   {
      DeletePendingsBySide(POSITION_TYPE_SELL);
      return;
   }
   if(sellVolume + lot > MaxExposureLots)
   {
      DeletePendingsBySide(POSITION_TYPE_SELL);
      return;
   }
   
   // Compute grid price
   double highestOpen = ExtremeOpenPrice(POSITION_TYPE_SELL);
   double gridPoints = ComputeGridPoints();
   double point = SymbolInfoDouble(g_symbol, SYMBOL_POINT);
   double gridPrice = highestOpen + gridPoints * point;
   int digits = (int)SymbolInfoInteger(g_symbol, SYMBOL_DIGITS);
   gridPrice = NormalizeDouble(gridPrice, digits);
   
   // Maintain one pending (smart tolerance + cooldown)
   MaintainOnePendingBySide(POSITION_TYPE_SELL, gridPrice, lot);
}

//+------------------------------------------------------------------+
//| Check Basket TP                                                   |
//+------------------------------------------------------------------+
void CheckBasketTP(ENUM_POSITION_TYPE posType)
{
   double sideProfit = FloatingProfitByType(posType);
   double target = 0;
   
   if(BasketTPMode == PERCENT_EQUITY)
   {
      target = AccountInfoDouble(ACCOUNT_EQUITY) * BasketTPPercent;
   }
   else // FIXED_USD
   {
      target = BasketTPUSD;
   }
   
   if(sideProfit >= target && target > 0)
   {
      string sideStr = (posType == POSITION_TYPE_BUY) ? "BUY" : "SELL";
      Print("BASKET TP HIT for ", sideStr, " side! Profit=", DoubleToString(sideProfit,2), " Target=", DoubleToString(target,2));
      
      // Close all positions of this side
      CloseAllPositionsBySide(posType);
      
      // Delete all pendings of this side
      DeletePendingsBySide(posType);
      
      // Reset peak equity
      g_peakEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   }
}

//+------------------------------------------------------------------+
//| Close All Positions By Side                                       |
//+------------------------------------------------------------------+
void CloseAllPositionsBySide(ENUM_POSITION_TYPE posType)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != g_symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) == posType)
      {
         trade.PositionClose(ticket);
      }
   }
}

//+------------------------------------------------------------------+
//| Handle DD Stop                                                    |
//+------------------------------------------------------------------+
void HandleDDStop()
{
   switch(DDStopMode)
   {
      case PAUSE_NEW_ONLY:
         Print("DD Stop: PAUSE_NEW_ONLY - blocking new entries");
         break;
         
      case CLEAR_PENDINGS:
         Print("DD Stop: CLEAR_PENDINGS - deleting all pendings");
         DeletePendingsBySide(POSITION_TYPE_BUY);
         DeletePendingsBySide(POSITION_TYPE_SELL);
         break;
         
      case EMERGENCY_REDUCE:
         Print("DD Stop: EMERGENCY_REDUCE - deleting pendings + partial close largest");
         DeletePendingsBySide(POSITION_TYPE_BUY);
         DeletePendingsBySide(POSITION_TYPE_SELL);
         EmergencyReduceLargest();
         break;
   }
}

//+------------------------------------------------------------------+
//| Emergency Reduce: close partial of largest position               |
//+------------------------------------------------------------------+
void EmergencyReduceLargest()
{
   ulong largestTicket = 0;
   double largestVol = 0;
   
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != g_symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      
      double vol = PositionGetDouble(POSITION_VOLUME);
      if(vol > largestVol)
      {
         largestVol = vol;
         largestTicket = ticket;
      }
   }
   
   if(largestTicket > 0)
   {
      double minLot = SymbolInfoDouble(g_symbol, SYMBOL_VOLUME_MIN);
      if(largestVol <= minLot) return;  // ปิดไม่ได้อีกแล้ว
      
      double closeVol = largestVol - minLot;
      closeVol = ClampVolume(closeVol);
      
      if(IsVolumeValid(closeVol))
      {
         if(trade.PositionClosePartial(largestTicket, closeVol))
            Print("Emergency partial close: ticket=", largestTicket, " closed=", DoubleToString(closeVol,8));
      }
   }
}

//+------------------------------------------------------------------+
//| Process Partial Close / Unwind on Retrace                         |
//+------------------------------------------------------------------+
void ProcessPartialClose(ENUM_POSITION_TYPE posType)
{
   // Cooldown check for partial close
   if(CooldownSec > 0 && TimeCurrent() - g_lastPartialCloseTime < CooldownSec)
      return;
   
   // 1) Compute basket profit for this side
   double basketProfit = FloatingProfitByType(posType);
   
   // 2) Check if basket profit meets threshold
   if(basketProfit < StartUnwindAtBasketProfitUSD)
      return;
   
   // 3) Optional: check price near VWAP
   if(UnwindOnlyWhenPriceNearVWAPPoints > 0)
   {
      double vwap = GetVWAPBySide(posType);
      if(vwap > 0)
      {
         double currentPrice = (posType == POSITION_TYPE_BUY) ? 
                               SymbolInfoDouble(g_symbol, SYMBOL_BID) : 
                               SymbolInfoDouble(g_symbol, SYMBOL_ASK);
         double point = SymbolInfoDouble(g_symbol, SYMBOL_POINT);
         double distPoints = MathAbs(currentPrice - vwap) / point;
         
         if(distPoints > UnwindOnlyWhenPriceNearVWAPPoints)
            return; // Price too far from VWAP
      }
   }
   
   // 4) Collect eligible positions (volume > KeepMinLotPerPosition)
   int totalPos = PositionsTotal();
   ulong  tickets[];
   double volumes[];
   double profits[];
   double openPrices[];
   int    eligibleCount = 0;
   
   // First pass: count eligible
   for(int i = 0; i < totalPos; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != g_symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) != posType) continue;
      
      double vol = PositionGetDouble(POSITION_VOLUME);
      if(vol <= KeepMinLotPerPosition) continue; // Already at minimum
      
      eligibleCount++;
   }
   
   if(eligibleCount == 0) return;
   
   ArrayResize(tickets, eligibleCount);
   ArrayResize(volumes, eligibleCount);
   ArrayResize(profits, eligibleCount);
   ArrayResize(openPrices, eligibleCount);
   
   int idx = 0;
   for(int i = 0; i < totalPos; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != g_symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if((ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE) != posType) continue;
      
      double vol = PositionGetDouble(POSITION_VOLUME);
      if(vol <= KeepMinLotPerPosition) continue;
      
      tickets[idx]    = ticket;
      volumes[idx]    = vol;
      profits[idx]    = PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP) + (2.0 * PositionGetDouble(POSITION_COMMISSION));
      openPrices[idx] = PositionGetDouble(POSITION_PRICE_OPEN);
      idx++;
   }
   
   // 5) Sort by UnwindSelectionMode
   SortUnwindCandidates(tickets, volumes, profits, openPrices, eligibleCount, posType);
   
   // 6) Process partial closes
   int closedCount = 0;
   
   for(int i = 0; i < eligibleCount && closedCount < MaxPartialClosesPerCycle; i++)
   {
      // Check profit condition
      if(CloseOnlyIfPositionProfitPositive && profits[i] < 0)
      {
         if(!AllowCloseAtSmallLossIfBasketProfitPositive || basketProfit <= 0)
            continue;
      }
      
      // Calculate volume to close
      double volumeToClose = 0;
      if(UnwindStepLot <= 0)
      {
         // Close all except KeepMinLot
         volumeToClose = volumes[i] - KeepMinLotPerPosition;
      }
      else
      {
         volumeToClose = UnwindStepLot;
         // Don't close below KeepMinLot
         if(volumes[i] - volumeToClose < KeepMinLotPerPosition)
            volumeToClose = volumes[i] - KeepMinLotPerPosition;
      }
      
      // Clamp volume to broker limits
      volumeToClose = ClampVolume(volumeToClose);
      
      // Validate: ถ้า clamp แล้ว volume เหลือน้อยกว่า min lot => skip
      if(!IsVolumeValid(volumeToClose)) continue;
      
      // Safety check: ปิดแล้วต้องไม่เหลือน้อยกว่า min lot (ถ้าไม่ปิดหมด)
      double remaining = volumes[i] - volumeToClose;
      double minLot = SymbolInfoDouble(g_symbol, SYMBOL_VOLUME_MIN);
      if(remaining > 0 && remaining < minLot)
      {
         // ปรับ volumeToClose ลงเพื่อให้เหลืออย่างน้อย minLot
         volumeToClose = volumes[i] - minLot;
         volumeToClose = ClampVolume(volumeToClose);
         if(!IsVolumeValid(volumeToClose)) continue;
      }
      
      // Execute partial close
      if(trade.PositionClosePartial(tickets[i], volumeToClose))
      {
         closedCount++;
         g_lastPartialCloseTime = TimeCurrent();
         Print("Partial close: ticket=", tickets[i], " closed=", DoubleToString(volumeToClose,8),
               " remaining=", DoubleToString(volumes[i] - volumeToClose, 8));
      }
   }
}

//+------------------------------------------------------------------+
//| Sort Unwind Candidates                                            |
//+------------------------------------------------------------------+
void SortUnwindCandidates(ulong &tickets[], double &volumes[], double &profits[], 
                          double &openPrices[], int count, ENUM_POSITION_TYPE posType)
{
   // Pre-compute VWAP once for FARTHEST_FROM_VWAP_FIRST mode
   double vwap = 0;
   if(UnwindSelectionMode == FARTHEST_FROM_VWAP_FIRST)
      vwap = GetVWAPBySide(posType);
   
   // Simple bubble sort (small arrays)
   for(int i = 0; i < count - 1; i++)
   {
      for(int j = 0; j < count - i - 1; j++)
      {
         bool doSwap = false;
         
         switch(UnwindSelectionMode)
         {
            case LARGEST_VOLUME_FIRST:
               doSwap = (volumes[j] < volumes[j+1]);
               break;
               
            case HIGHEST_PROFIT_FIRST:
               doSwap = (profits[j] < profits[j+1]);
               break;
               
            case FARTHEST_FROM_VWAP_FIRST:
            {
               double dist1 = MathAbs(openPrices[j] - vwap);
               double dist2 = MathAbs(openPrices[j+1] - vwap);
               doSwap = (dist1 < dist2);
               break;
            }
         }
         
         if(doSwap)
         {
            // Swap all arrays
            ulong  tmpTicket = tickets[j];
            double tmpVol    = volumes[j];
            double tmpProfit = profits[j];
            double tmpPrice  = openPrices[j];
            
            tickets[j]    = tickets[j+1];
            volumes[j]    = volumes[j+1];
            profits[j]    = profits[j+1];
            openPrices[j] = openPrices[j+1];
            
            tickets[j+1]    = tmpTicket;
            volumes[j+1]    = tmpVol;
            profits[j+1]    = tmpProfit;
            openPrices[j+1] = tmpPrice;
         }
      }
   }
}
//+------------------------------------------------------------------+
