param([int]$Disk = -1, [string]$Out = "E:\AI\H700Android\work\cubexx-build\card-diag")
# READ-ONLY raw capture of an SD card's head and tail for offline GPT/boot diagnosis.
if ($Disk -lt 0) { Write-Error "Specify -Disk N"; exit 1 }
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$path = "\\.\PhysicalDrive$Disk"
$fs = [System.IO.File]::Open($path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
$size = $fs.Length
$n = 1048576
$buf = New-Object byte[] $n
$fs.Seek(0, [System.IO.SeekOrigin]::Begin) | Out-Null
$read = $fs.Read($buf, 0, $n)
[System.IO.File]::WriteAllBytes((Join-Path $Out "head.bin"), $buf)
$fs.Seek($size - $n, [System.IO.SeekOrigin]::Begin) | Out-Null
$read2 = $fs.Read($buf, 0, $n)
[System.IO.File]::WriteAllBytes((Join-Path $Out "tail.bin"), $buf)
$fs.Close()
$msg = ("DiskNumber={0} DiskSizeBytes={1} DiskSizeGB={2} HeadRead={3} TailRead={4}" -f $Disk, $size, [math]::Round($size/1GB,3), $read, $read2)
Write-Output $msg
[System.IO.File]::WriteAllText((Join-Path $Out "status.txt"), $msg)