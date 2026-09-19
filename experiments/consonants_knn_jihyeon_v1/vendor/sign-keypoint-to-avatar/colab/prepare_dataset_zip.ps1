<#
.SYNOPSIS
  외장하드/로컬의 SYN keypoint 원본에서 정면(F) 뷰 파일만 골라 하나의 zip으로
  묶는다. 학습 스크립트(colab/train_hand_motion_denoiser.py)는 F뷰만 쓰므로,
  U/D/L/R 뷰까지 통째로 올리면 용량만 5배 커지고 안 쓰인다.

.PARAMETER SourceRoot
  원본 keypoint 폴더 (예: "D:\all_word_video_make\dataset\all_keypoints\syn_keypoints\수어 영상\2.Validation\[라벨]02_syn_word_keypoint\WORD\keypoint")

.PARAMETER OutZip
  결과 zip 경로 (예: "C:\Users\ESTsoft\Desktop\syn_keypoints_F_only.zip")

.PARAMETER MaxWords
  테스트용으로 일부 단어만 담고 싶으면 지정 (예: 300). 생략하면 전체.

.EXAMPLE
  .\prepare_dataset_zip.ps1 -SourceRoot "D:\all_word_video_make\dataset\all_keypoints\syn_keypoints\수어 영상\2.Validation\[라벨]02_syn_word_keypoint\WORD\keypoint" -OutZip "C:\Users\ESTsoft\Desktop\syn_F_only.zip" -MaxWords 300
#>
param(
    [Parameter(Mandatory=$true)][string]$SourceRoot,
    [Parameter(Mandatory=$true)][string]$OutZip,
    [int]$MaxWords = 0
)

if (-not (Test-Path -LiteralPath $SourceRoot)) {
    Write-Error "SourceRoot를 찾을 수 없습니다: $SourceRoot"
    exit 1
}
if (Test-Path $OutZip) {
    Write-Error "OutZip이 이미 있습니다. 다른 이름을 쓰세요: $OutZip"
    exit 1
}

$stagingRoot = Join-Path $env:TEMP ("syn_f_only_staging_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $stagingRoot | Out-Null
Write-Host "임시 스테이징 폴더: $stagingRoot"

Write-Host "F뷰 keypoint 파일 검색 중... (파일이 많으면 수 분 걸릴 수 있음)"
$files = Get-ChildItem -LiteralPath $SourceRoot -Recurse -Filter "*_F_*_keypoints.json" -File

if ($files.Count -eq 0) {
    Write-Error "F뷰 keypoints.json 파일을 하나도 못 찾았습니다. SourceRoot 경로나 파일명 패턴을 확인하세요."
    Remove-Item -Recurse -Force $stagingRoot
    exit 1
}
Write-Host ("찾은 F뷰 파일: {0}개" -f $files.Count)

# 단어(WORDxxxx)별로 묶어서, 필요하면 MaxWords 개수까지만 사용
$byWord = $files | Group-Object { if ($_.Name -match 'WORD\d{4}') { $matches[0] } else { 'UNKNOWN' } }
Write-Host ("발견된 단어 수: {0}" -f $byWord.Count)

if ($MaxWords -gt 0 -and $byWord.Count -gt $MaxWords) {
    $byWord = $byWord | Select-Object -First $MaxWords
    Write-Host ("-MaxWords 지정으로 {0}개 단어만 포함" -f $MaxWords)
}

$copied = 0
$copyFailed = 0
$firstError = $null
foreach ($group in $byWord) {
    $wordDir = Join-Path $stagingRoot $group.Name
    New-Item -ItemType Directory -Path $wordDir -Force | Out-Null
    foreach ($f in $group.Group) {
        try {
            # -LiteralPath is required: source paths contain "[..]" (e.g. "[라벨]"),
            # which -Path would parse as a wildcard character class and silently
            # match nothing instead of erroring.
            Copy-Item -LiteralPath $f.FullName -Destination (Join-Path $wordDir $f.Name) -ErrorAction Stop
            $copied++
        } catch {
            $copyFailed++
            if (-not $firstError) { $firstError = $_ }
        }
    }
}
Write-Host ("복사 완료: {0}개 파일" -f $copied)
if ($copyFailed -gt 0) {
    Write-Warning ("복사 실패: {0}개 파일. 첫 오류: {1}" -f $copyFailed, $firstError)
}
if ($copied -eq 0) {
    Write-Error "복사된 파일이 0개입니다. 중단합니다."
    Write-Host "스테이징 폴더는 지우지 않았습니다 (확인용): $stagingRoot"
    exit 1
}

Write-Host "압축 중... (파일이 많아 Compress-Archive는 조용히 실패하는 경우가 있어 .NET ZipFile을 직접 사용)"
Add-Type -AssemblyName System.IO.Compression.FileSystem
try {
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $stagingRoot, $OutZip,
        [System.IO.Compression.CompressionLevel]::Optimal, $false)
} catch {
    Write-Error "압축 실패: $_"
    Write-Host "스테이징 폴더는 지우지 않았습니다 (재시도/확인용): $stagingRoot"
    exit 1
}

if (-not (Test-Path -LiteralPath $OutZip)) {
    Write-Error "압축은 에러 없이 끝났는데 zip 파일이 생성되지 않았습니다."
    Write-Host "스테이징 폴더는 지우지 않았습니다 (재시도/확인용): $stagingRoot"
    exit 1
}

Remove-Item -Recurse -Force $stagingRoot

$sizeMB = [math]::Round((Get-Item -LiteralPath $OutZip).Length / 1MB, 1)
Write-Host "완료: $OutZip ($sizeMB MB)"
Write-Host "이 zip 파일을 drive.google.com 웹에서 Drive에 업로드한 뒤,"
Write-Host "Colab에서 마운트하고 압축을 풀어 DATASET_ROOT로 지정하세요."

