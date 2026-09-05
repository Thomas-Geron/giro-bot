; Instalador do Giro Bot (Inno Setup 6)
; Gera GiroBot-Setup.exe: instala, cria atalhos e permite desinstalar.
; Instalação POR USUÁRIO (não pede senha de administrador).

#define MeuApp      "Giro Bot"
#ifndef MinhaVersao
  #define MinhaVersao "1.0.0"
#endif
#define MinhaEmpresa "Giro"
#define MeuExe      "GiroBot.exe"

[Setup]
AppId={{9E4B7C2A-5D31-4F0A-9B18-2C7A6D5E1F30}
AppName={#MeuApp}
AppVersion={#MinhaVersao}
AppPublisher={#MinhaEmpresa}
DefaultDirName={autopf}\GiroBot
DefaultGroupName={#MeuApp}
DisableProgramGroupPage=yes
OutputDir=instalador
OutputBaseFilename=GiroBot-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; "lowest" = instala só para o usuário atual, sem pedir admin
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos:"
Name: "startup";    Description: "Abrir o Giro Bot junto com o Windows"; GroupDescription: "Inicialização:"; Flags: unchecked

[Files]
; Conteúdo gerado pelo PyInstaller (pasta dist\GiroBot)
Source: "dist\GiroBot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MeuApp}";           Filename: "{app}\{#MeuExe}"
Name: "{group}\Desinstalar {#MeuApp}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MeuApp}";     Filename: "{app}\{#MeuExe}"; Tasks: desktopicon
Name: "{userstartup}\{#MeuApp}";     Filename: "{app}\{#MeuExe}"; Tasks: startup

[Run]
Filename: "{app}\{#MeuExe}"; Description: "Abrir o {#MeuApp} agora"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Não apaga a configuração do usuário (%APPDATA%\GiroBot) — sessão e token ficam
; preservados caso reinstale. Para limpar tudo, apague essa pasta manualmente.
