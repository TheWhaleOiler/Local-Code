# Local Code. A Claude code alternative using locally ran LLMs
Currently building out all the action functions your LLMs can use outside of it's own sandbox. This project is mostly for fun and for people to play around with themselves.


## Ensure Vulcan is enabled in powershell:
$env:OLLAMA_VULKAN="1"\
$env:OLLAMA_HOST="0.0.0.0:11434"\
ollama serve

## To Run Ministral model
ollama run ministral-3:14b

## kill Ollama:
taskkill /F /IM ollama.exe\
Get-Process *ollama* | Stop-Process -Force