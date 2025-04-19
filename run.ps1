param(
    [string]$CustomPath = "G:\tttt\custom_nodes"  # ��������дcustom nodes�ļ���·��
)

# ������⻷������ű��Ƿ����
$venvActivateScript = Join-Path $PSScriptRoot "venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvActivateScript)) {
    Write-Host "�����Ҳ������⻷������ű���" -ForegroundColor Red
    exit 1
}

# �������⻷��
try {
    & { . $venvActivateScript }
} catch {
    Write-Host "�������⻷��ʧ��: $_" -ForegroundColor Red
    exit 2
}

# ���� Python �ű�
try {
    python "$PSScriptRoot\dependency_resolver.py" $CustomPath
} catch {
    Write-Host "���� Python �ű�ʧ��: $_" -ForegroundColor Red
    exit 3
}

Write-Host "�����ɹ���ɣ�" -ForegroundColor Green