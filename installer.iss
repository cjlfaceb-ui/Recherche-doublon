; ============================================================
;  Script d'installation Inno Setup pour "Recherche de Doublons"
;  Prerequis : compiler d'abord dist\RechercheDoublons.exe
;  avec build_exe.bat, puis compiler ce script avec Inno Setup
;  (https://jrsoftware.org/isdl.php) via "Compile".
; ============================================================

[Setup]
AppName=Recherche de Doublons
AppVersion=1.0
AppPublisher=Recherche de Doublons
DefaultDirName={autopf}\RechercheDoublons
DefaultGroupName=Recherche de Doublons
OutputDir=installateur
OutputBaseFilename=Installer-RechercheDoublons-1.0
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\RechercheDoublons.exe

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le bureau"; \
    GroupDescription: "Raccourcis :"

[Files]
Source: "dist\RechercheDoublons.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Recherche de Doublons"; Filename: "{app}\RechercheDoublons.exe"
Name: "{autodesktop}\Recherche de Doublons"; Filename: "{app}\RechercheDoublons.exe"; \
    Tasks: desktopicon

[Run]
Filename: "{app}\RechercheDoublons.exe"; Description: "Lancer Recherche de Doublons"; \
    Flags: nowait postinstall skipifsilent
