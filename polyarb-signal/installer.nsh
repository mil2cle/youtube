; =====================================================
; PolyArb Signal - NSIS Installer Configuration
; Custom installer settings for Windows
; =====================================================

!macro customHeader
  !system "echo 'Building PolyArb Signal Installer...'"
!macroend

!macro preInit
  ; Set default installation directory
  SetRegView 64
  WriteRegExpandStr HKLM "${INSTALL_REGISTRY_KEY}" InstallLocation "$PROGRAMFILES64\PolyArb Signal"
  WriteRegExpandStr HKCU "${INSTALL_REGISTRY_KEY}" InstallLocation "$LOCALAPPDATA\PolyArb Signal"
!macroend

!macro customInstall
  ; Create Start Menu shortcut
  CreateDirectory "$SMPROGRAMS\PolyArb Signal"
  CreateShortCut "$SMPROGRAMS\PolyArb Signal\PolyArb Signal.lnk" "$INSTDIR\PolyArb Signal.exe"
  CreateShortCut "$SMPROGRAMS\PolyArb Signal\Uninstall.lnk" "$INSTDIR\Uninstall PolyArb Signal.exe"
  
  ; Create Desktop shortcut
  CreateShortCut "$DESKTOP\PolyArb Signal.lnk" "$INSTDIR\PolyArb Signal.exe"
!macroend

!macro customUnInstall
  ; Remove Start Menu shortcuts
  Delete "$SMPROGRAMS\PolyArb Signal\PolyArb Signal.lnk"
  Delete "$SMPROGRAMS\PolyArb Signal\Uninstall.lnk"
  RMDir "$SMPROGRAMS\PolyArb Signal"
  
  ; Remove Desktop shortcut
  Delete "$DESKTOP\PolyArb Signal.lnk"
  
  ; Remove from startup if present
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "PolyArb Signal"
!macroend
