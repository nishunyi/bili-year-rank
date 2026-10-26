param([ValidateSet('Create','Remove')][string]$Action='Create')
$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$statePath=Join-Path $taskRoot 'data\client_patch.json'
$state=Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
$desktopPath=[Environment]::GetFolderPath('Desktop')
$shortcutPath=Join-Path $desktopPath '哔哩哔哩（年度榜增强版）.lnk'
$shell=New-Object -ComObject WScript.Shell
if($Action -eq 'Create') {
    if(Test-Path -LiteralPath $shortcutPath) {
        $existing=$shell.CreateShortcut($shortcutPath)
        if($existing.TargetPath -ne $state.executable) { throw '同名快捷方式不属于本工具，拒绝覆盖。' }
    }
    $shortcut=$shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath=$state.executable
    $shortcut.WorkingDirectory=Split-Path -Parent $state.executable
    $shortcut.IconLocation=$state.original_executable+',0'
    $shortcut.Description='哔哩哔哩原生客户端 + 年度候选榜（本机增强）'
    $shortcut.Save()
    $state.shortcut=$shortcutPath
    [IO.File]::WriteAllText($statePath,($state | ConvertTo-Json -Depth 8),(New-Object Text.UTF8Encoding($false)))
    Write-Output ('桌面入口已创建：'+$shortcutPath)
} else {
    if(Test-Path -LiteralPath $shortcutPath) {
        $existing=$shell.CreateShortcut($shortcutPath)
        if($existing.TargetPath -ne $state.executable) { throw '快捷方式已被修改，拒绝删除。' }
        $resolved=[IO.Path]::GetFullPath($shortcutPath)
        if([IO.Path]::GetDirectoryName($resolved) -ne [IO.Path]::GetFullPath($desktopPath)) { throw '快捷方式不在预期桌面目录。' }
        Remove-Item -LiteralPath $resolved
    }
    Write-Output '已移除本工具创建的增强入口，原版桌面图标保留。'
}
