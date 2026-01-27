# Changelog

All notable changes to PolyArb Signal will be documented in this file.

## [1.0.1] - 2026-01-27

### Fixed
- **Start Scanning button hanging**: IPC handler now properly returns response on error
- Added 30-second timeout for Gamma API requests to prevent indefinite waiting
- Added max pages limit (10) to prevent infinite loops when fetching markets

### Improved
- Dashboard now displays error messages when scanning fails
- Added step-by-step logging for easier debugging
- Changed build target to portable directory format

---

## [1.0.0] - 2026-01-26

### Added
- Initial release of PolyArb Signal
- Arbitrage detection for Polymarket binary markets (YES/NO)
- Two-tier scanning system (Tier A: 3s, Tier B: 30s)
- Telegram notification integration
- System tray support with minimize-to-tray
- Dashboard with real-time statistics
- Signal logging and export (JSON)
- Market management (pin, blacklist)
- Configurable thresholds and filters
- WebSocket support for real-time updates (with REST fallback)
- Windows installer (NSIS)

### Technical Details
- Built with Electron + React + TypeScript
- Uses Polymarket Gamma API for market discovery
- Uses Polymarket CLOB API for orderbook data
- Persistent settings with electron-store
- Rate limiting and exponential backoff

### Known Limitations
- Windows only
- Signals are informational only, not investment advice
- Requires internet connection
