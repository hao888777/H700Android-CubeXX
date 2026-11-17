param([int]$Disk = 2, [long]$Offset = 10959716352, [long]$Length = 2147483648,
      [string]$OutPath = "E:\AI\H700Android\work\cubexx-build\card-diag\userdata-card.img")
# READ-ONLY capture of the userdata partition (p7) from the SD card.
$inStream = [System.IO.File]::Open("\\.\PhysicalDrive$Disk", [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
$inStream.Seek($Offset, [System.IO.SeekOrigin]::Begin) | Out-Null
$dest = [System.IO.File]::Create($OutPath)
$chunk = 67108864
$buf = New-Object byte[] $chunk
$remaining = $Length
while ($remaining -gt 0) {
  $want = [int][math]::Min([long]$chunk, [long]$remaining)
  $got = $inStream.Read($buf, 0, $want)
  if ($got -le 0) { break }
  $dest.Write($buf, 0, $got)
  $remaining -= $got
}
$dest.Close(); $inStream.Close()
$msg = "Wrote {0} bytes to {1}" -f ($Length - $remaining), $OutPath
[System.IO.File]::WriteAllText("E:\AI\H700Android\work\cubexx-build\card-diag\udstatus.txt", $msg)
Write-Output $msg