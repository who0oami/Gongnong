$path = Join-Path $PSScriptRoot "models\ksl_avatar.glb"
$stream = [System.IO.File]::OpenRead($path)
$reader = [System.IO.BinaryReader]::new($stream)
try {
    $magic = $reader.ReadUInt32()
    $version = $reader.ReadUInt32()
    $length = $reader.ReadUInt32()
    $chunkLength = $reader.ReadUInt32()
    $chunkType = $reader.ReadUInt32()
    if ($magic -ne 0x46546C67 -or $chunkType -ne 0x4E4F534A) {
        throw "GLB 2.0 JSON chunk를 읽을 수 없습니다."
    }
    $jsonText = [Text.Encoding]::UTF8.GetString($reader.ReadBytes($chunkLength)).TrimEnd([char]0, ' ')
    $gltf = $jsonText | ConvertFrom-Json

    "GLB version: $version / bytes: $length"
    "Nodes: $($gltf.nodes.Count), skins: $($gltf.skins.Count), meshes: $($gltf.meshes.Count), animations: $($gltf.animations.Count)"
    "--- Nodes ---"
    $gltf.nodes | ForEach-Object { $_.name } | Where-Object { $_ }
    "--- Morph targets ---"
    foreach ($mesh in $gltf.meshes) {
        if ($mesh.extras.targetNames) {
            "[$($mesh.name)] $($mesh.extras.targetNames -join ', ')"
        }
    }
    "--- Animations ---"
    $gltf.animations | ForEach-Object { $_.name }
}
finally {
    $reader.Dispose()
    $stream.Dispose()
}
