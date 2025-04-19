param(
    [string]$CustomPath = "G:\tttt\custom_nodes"  # 在这里填写custom nodes文件夹路径
)

# 检查虚拟环境激活脚本是否存在
$venvActivateScript = Join-Path $PSScriptRoot "venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvActivateScript)) {
    Write-Host "错误：找不到虚拟环境激活脚本！" -ForegroundColor Red
    exit 1
}

# 激活虚拟环境
try {
    & { . $venvActivateScript }
} catch {
    Write-Host "激活虚拟环境失败: $_" -ForegroundColor Red
    exit 2
}

# 运行 Python 脚本
try {
    python "$PSScriptRoot\dependency_resolver.py" $CustomPath
} catch {
    Write-Host "运行 Python 脚本失败: $_" -ForegroundColor Red
    exit 3
}

Write-Host "操作成功完成！" -ForegroundColor Green