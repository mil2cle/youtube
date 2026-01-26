#!/usr/bin/env node

/**
 * PolyArb Signal - Windows Build Script
 * สร้าง Windows installer (.exe)
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT_DIR = path.join(__dirname, '..');

console.log('🔨 Building PolyArb Signal for Windows...\n');

// Step 1: Install dependencies
console.log('📦 Installing dependencies...');
execSync('npm install', { cwd: ROOT_DIR, stdio: 'inherit' });

// Step 2: Build TypeScript
console.log('\n📝 Compiling TypeScript...');
execSync('npm run build', { cwd: ROOT_DIR, stdio: 'inherit' });

// Step 3: Create assets directory if not exists
const assetsDir = path.join(ROOT_DIR, 'assets');
if (!fs.existsSync(assetsDir)) {
  fs.mkdirSync(assetsDir, { recursive: true });
}

// Step 4: Create placeholder icons if not exists
const iconPath = path.join(assetsDir, 'icon.png');
const trayIconPath = path.join(assetsDir, 'tray-icon.png');

if (!fs.existsSync(iconPath)) {
  console.log('\n⚠️  Warning: assets/icon.png not found. Using placeholder.');
  // Create a simple placeholder (1x1 transparent PNG)
  const placeholderPng = Buffer.from([
    0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
    0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52,
    0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
    0x08, 0x06, 0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4,
    0x89, 0x00, 0x00, 0x00, 0x0a, 0x49, 0x44, 0x41,
    0x54, 0x78, 0x9c, 0x63, 0x00, 0x01, 0x00, 0x00,
    0x05, 0x00, 0x01, 0x0d, 0x0a, 0x2d, 0xb4, 0x00,
    0x00, 0x00, 0x00, 0x49, 0x45, 0x4e, 0x44, 0xae,
    0x42, 0x60, 0x82
  ]);
  fs.writeFileSync(iconPath, placeholderPng);
  fs.writeFileSync(trayIconPath, placeholderPng);
}

// Step 5: Package with electron-builder
console.log('\n📦 Packaging for Windows...');
execSync('npm run package:win', { cwd: ROOT_DIR, stdio: 'inherit' });

console.log('\n✅ Build complete!');
console.log('📁 Output: release/');
