# Quimera no Termux — Guia Rapido

## Instalar
```bash
cd ~/storage/downloads/engine
pkg install python-numpy python-scipy cmake ninja libmd
pip install -r requirements_termux.txt
echo 'export PYTHONPATH="$HOME/storage/downloads/engine:$PYTHONPATH"' >> ~/.bashrc
source ~/.bashrc
```

## Configurar Groq API (para IA de verdade)
1. Crie conta gratis em https://console.groq.com
2. Pegue a API key
3. Rode: python -m quimera assist "cadastra chave groq gsk_..."
   Ou crie .env com: GROQ_API_KEY=gsk_...

## Usar
```bash
python -m quimera assist "analise o agente analista"
python -m quimera assist "busca por sqlalchemy"
python -m quimera assist "cadastra chave gemini AIza..."
python -m quimera assist "o que faz o pipeline.py?"
```
