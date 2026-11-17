try {
  & "E:\AI\H700Android\work\cubexx-build\read_card.ps1" -Disk 2
} catch {
  $d = "E:\AI\H700Android\work\cubexx-build\card-diag"
  New-Item -ItemType Directory -Force -Path $d | Out-Null
  Set-Content -Path "$d\status.txt" -Value ("ERROR: " + $_.Exception.Message)
}