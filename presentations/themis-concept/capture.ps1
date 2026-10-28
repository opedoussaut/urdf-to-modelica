# Captures of the real studio for the THEMIS concept deck (headless Microsoft Edge, software WebGL so the 3D renders).
# Usage: powershell -File capture.ps1 [-Only name1,name2]   (the studio must run on http://127.0.0.1:8010)
param([string[]]$Only = @())
$base = "http://127.0.0.1:8010"
$run = "themis-261028-011359"
$out = Join-Path $PSScriptRoot "public\shots"
New-Item -ItemType Directory -Force $out | Out-Null
$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$shots = @(
  @{ n = "01_start";        h = 1250; u = "/?page=repair" },
  @{ n = "03_input";        h = 1100; u = "/?page=repair&run=$run&stage=input" },
  @{ n = "04_compliance";   h = 1500; u = "/?page=repair&run=$run&stage=compliance&notes=open" },
  @{ n = "05_convert";      h = 1300; u = "/?page=repair&run=$run&stage=convert" },
  @{ n = "06_check";        h = 1700; u = "/?page=repair&run=$run&stage=check&notes=open" },
  @{ n = "07_repair_start"; h = 1000; u = "/?page=repair&run=$run&stage=repair" },
  @{ n = "08_repair_result"; h = 1900; u = "/?page=repair&run=$run--qwen3-30b&stage=repair&notes=open" },
  @{ n = "10_guide";        h = 2400; u = "/?page=guide" },
  @{ n = "11_explore_3d";   h = 1700; u = "/?page=convert" }
)
foreach ($s in $shots) {
  if ($Only.Count -and -not ($Only -contains $s.n)) { continue }
  $file = Join-Path $out ($s.n + ".png")
  $a = @("--headless=new", "--disable-gpu-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
         "--user-data-dir=$env:TEMP\kkh-edge-capture", "--hide-scrollbars", "--window-size=1440,$($s.h)",
         "--virtual-time-budget=25000", "--screenshot=$file", ($base + $s.u))
  Start-Process -FilePath $edge -ArgumentList $a -Wait -WindowStyle Hidden
  "{0,-18} {1,8} bytes" -f $s.n, (Get-Item $file).Length
}
