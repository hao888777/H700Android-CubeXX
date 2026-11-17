try {
  & "E:\AI\H700Android\work\cubexx-build\read_userdata.ps1" -Disk 2
} catch {
  Set-Content -Path "E:\AI\H700Android\work\cubexx-build\card-diag\udstatus.txt" -Value ("ERROR: " + $_.Exception.Message)
}