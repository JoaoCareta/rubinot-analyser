#ifndef Payload
  #define Payload "build\hunt_launcher.dist"
#endif
#ifndef ReleaseDir
  #define ReleaseDir "saida"
#endif
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{E584A3B6-B9DA-4725-9A16-784C3D6CC012}
AppName=Hunt Analyzer
AppVersion={#AppVersion}
AppPublisher=Hunt Analyzer
DefaultDirName={localappdata}\HuntAnalyzer
DefaultGroupName=Hunt Analyzer
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#ReleaseDir}
OutputBaseFilename=HuntAnalyzer-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\HuntAnalyzer.exe
SetupMutex=HuntAnalyzerSetup
AppMutex=HuntAnalyzerInterfaceDireta
CloseApplications=no
RestartApplications=no
DisableWelcomePage=no
InfoBeforeFile=LEIA-ME-wizard.txt

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "{#Payload}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\Hunt Analyzer"; Filename: "{app}\HuntAnalyzer.exe"; WorkingDir: "{app}"
Name: "{userdesktop}\Hunt Analyzer"; Filename: "{app}\HuntAnalyzer.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\HuntAnalyzer.exe"; Description: "Abrir Hunt Analyzer"; Flags: nowait postinstall skipifsilent unchecked

[Code]
procedure InitializeWizard;
begin
  WizardForm.WelcomeLabel2.Caption :=
    'Este assistente instala o Hunt Analyzer e as dependências necessárias neste computador.' + #13#10#13#10 +
    'Você não precisa instalar Python nem extrair arquivos. Ao abrir pela primeira vez, faça a calibração dos painéis do RubinOT.' + #13#10#13#10 +
    'Feche o Hunt Analyzer antes de instalar uma atualização.';
end;
