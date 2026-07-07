#!/bin/bash
# Baixa o modelo Qwen2.5-0.5B (468MB) — IA local em português
# Roda até no Samsung A71 (~2GB RAM livre)

MODEL_DIR="$(dirname "$0")/models"
mkdir -p "$MODEL_DIR"

MODEL_FILE="$MODEL_DIR/qwen2.5-0.5b-instruct-q4_k_m.gguf"

if [ -f "$MODEL_FILE" ]; then
    echo "✅ Modelo já existe: $MODEL_FILE"
    ls -lh "$MODEL_FILE"
else
    echo "📥 Baixando Qwen2.5-0.5B-Instruct (468MB)..."
    echo "   Modelo multilíngue otimizado — entende português"
    curl -L -o "$MODEL_FILE" \
        "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"
    echo "✅ Pronto!"
    ls -lh "$MODEL_FILE"
fi
