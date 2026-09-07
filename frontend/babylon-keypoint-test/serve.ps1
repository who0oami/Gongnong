$root = [IO.Path]::GetFullPath($PSScriptRoot)
$server = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 8080)
$server.Start()
Write-Host "KSL demo: http://localhost:8080/  (Ctrl+C to stop)"
Write-Host "Keep this window open, then refresh the browser page."
$mime = @{ '.html'='text/html; charset=utf-8'; '.js'='text/javascript; charset=utf-8'; '.css'='text/css; charset=utf-8'; '.json'='application/json; charset=utf-8'; '.glb'='model/gltf-binary'; '.mp4'='video/mp4' }
try {
  while ($true) {
    $client=$server.AcceptTcpClient(); $stream=$client.GetStream(); $reader=[IO.StreamReader]::new($stream,[Text.Encoding]::ASCII,$false,1024,$true)
    $request=$reader.ReadLine(); $range=$null
    while (($line=$reader.ReadLine()) -ne '') { if ($line -match '^Range:\s*bytes=(\d+)-') { $range=[long]$Matches[1] } }
    $url=if($request -match '^GET\s+([^\s]+)'){$Matches[1].Split('?')[0]}else{'/'}
    $relative=[Uri]::UnescapeDataString($url.TrimStart('/')); if(-not $relative){$relative='index.html'}
    $file=[IO.Path]::GetFullPath((Join-Path $root $relative.Replace('/',[IO.Path]::DirectorySeparatorChar)))
    if(-not $file.StartsWith($root,[StringComparison]::OrdinalIgnoreCase) -or -not [IO.File]::Exists($file)){
      $header=[Text.Encoding]::ASCII.GetBytes("HTTP/1.1 404 Not Found`r`nContent-Length: 0`r`nConnection: close`r`n`r`n");$stream.Write($header,0,$header.Length)
    } else {
      $info=[IO.FileInfo]::new($file);$start=if($null-ne $range){$range}else{0};$length=$info.Length-$start;$ext=$info.Extension.ToLowerInvariant();$type=if($mime[$ext]){$mime[$ext]}else{'application/octet-stream'}
      $status=if($start){'206 Partial Content'}else{'200 OK'};$extra=if($start){"Content-Range: bytes $start-$($info.Length-1)/$($info.Length)`r`n"}else{''}
      $header=[Text.Encoding]::ASCII.GetBytes("HTTP/1.1 $status`r`nContent-Type: $type`r`nContent-Length: $length`r`nAccept-Ranges: bytes`r`n${extra}Connection: close`r`n`r`n");$stream.Write($header,0,$header.Length)
      $fs=[IO.File]::OpenRead($file);$fs.Position=$start;$fs.CopyTo($stream);$fs.Dispose()
    }
    $reader.Dispose();$stream.Dispose();$client.Dispose()
  }
} finally {$server.Stop()}
