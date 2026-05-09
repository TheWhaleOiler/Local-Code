# Ensure Vulcan is enabled in powershell:
$env:OLLAMA_VULKAN="1"
$env:OLLAMA_HOST="0.0.0.0:11434"
ollama serve


## To Run Ministral model
ollama run ministral-3:14b

## kill Ollama:
taskkill /F /IM ollama.exe
Get-Process *ollama* | Stop-Process -Force