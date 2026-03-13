$dir = "C:\Users\Daniel\Documents\Python\IFJN\Book-Studio\Band_Stoffwechselgesundheit\content\required"
$out = Join-Path $dir ("_merged_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".md")

$files = Get-ChildItem -LiteralPath $dir -File -Filter *.md |
    Where-Object { $_.Name -notlike "_merged_*.md" } |
    Sort-Object Name

"" | Set-Content -LiteralPath $out -Encoding UTF8

foreach ($file in $files) {
    $raw = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8
    $title = "Ohne Titel"
    $body = $raw

    if ($raw -match '(?s)^\uFEFF?---\r?\n(.*?)\r?\n---\r?\n?') {
        $front = $matches[1]
        if ($front -match '(?m)^title:\s*["'']?(.*?)["'']?\s*$') {
            $title = $matches[1].Trim()
        }
        $body = $raw -replace '(?s)^\uFEFF?---\r?\n.*?\r?\n---\r?\n?', ''
    }

    $meta = [ordered]@{
        title = $title
        path  = "content/required/$($file.Name)"
    } | ConvertTo-Json -Depth 3

    Add-Content -LiteralPath $out -Encoding UTF8 -Value $meta
    Add-Content -LiteralPath $out -Encoding UTF8 -Value ""
    Add-Content -LiteralPath $out -Encoding UTF8 -Value $body
    Add-Content -LiteralPath $out -Encoding UTF8 -Value "`r`n`r`n---`r`n"
}

Write-Output ("OUT=" + $out)
Write-Output ("FILES=" + $files.Count)
Write-Output ("SIZE=" + (Get-Item -LiteralPath $out).Length)
