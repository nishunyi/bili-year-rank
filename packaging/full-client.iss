#ifndef BundleDir
  #error BundleDir is required
#endif
#ifndef ReleaseDir
  #error ReleaseDir is required
#endif
#define AppVersion "0.2.0"

[Setup]
AppId={{4171DE73-933F-4A90-A5A5-B5187749EA60}
AppName=哔哩哔哩（年度榜增强版）
AppVersion={#AppVersion}
AppPublisher=bili-year-rank contributors
AppPublisherURL=https://github.com/nishunyi/bili-year-rank
DefaultDirName={localappdata}\Programs\BiliYearRank
DefaultGroupName=哔哩哔哩（年度榜增强版）
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
Compression=lzma2/fast
SolidCompression=yes
OutputDir={#ReleaseDir}
OutputBaseFilename=bili-year-rank-full-setup-v{#AppVersion}-x64
UninstallDisplayIcon={app}\哔哩哔哩.exe
UninstallDisplayName=哔哩哔哩（年度榜增强版）
SetupLogging=yes
CloseApplications=no
InfoBeforeFile={#BundleDir}\使用说明.txt

[Languages]
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; Flags: checkedonce

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\哔哩哔哩（年度榜增强版）"; Filename: "{app}\年度榜增强版.exe"; WorkingDir: "{app}"; IconFilename: "{app}\哔哩哔哩.exe"
Name: "{autodesktop}\哔哩哔哩（年度榜增强版）"; Filename: "{app}\年度榜增强版.exe"; WorkingDir: "{app}"; IconFilename: "{app}\哔哩哔哩.exe"; Tasks: desktopicon
Name: "{group}\卸载年度榜增强版"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\年度榜增强版.exe"; Description: "打开年度榜增强版"; Flags: nowait postinstall skipifsilent
