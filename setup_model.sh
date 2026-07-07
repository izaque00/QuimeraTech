#!/data/data/com.termux/files/usr/bin/bash
# ═══════════════════════════════════════════════
# Quimera — Modelo Local Qwen 2.5 3B + Knowledge
# A55: 8GB+4GB RAM, ~2.2GB modelo, roda offline
# ═══════════════════════════════════════════════

MODEL_DIR="$HOME/storage/downloads/engine/models"
MODEL_FILE="qwen2.5-3b-instruct-q4_k_m.gguf"
MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf"

echo "🧠 Quimera — IA Local Qwen 2.5 3B"
echo "===================================="
echo "   RAM necessária: ~2.5GB (você tem 8GB+4GB ✅)"
echo ""

mkdir -p "$MODEL_DIR"

if [ -f "$MODEL_DIR/$MODEL_FILE" ]; then
    SIZE=$(du -h "$MODEL_DIR/$MODEL_FILE" | cut -f1)
    echo "✅ Modelo 3B já existe: $SIZE"
else
    echo "📥 Baixando Qwen 2.5 3B Instruct Q4_K_M (~2.2GB)..."
    echo "   ⏳ Isso pode levar alguns minutos..."
    echo ""
    if command -v curl &> /dev/null; then
        curl -L -o "$MODEL_DIR/$MODEL_FILE" "$MODEL_URL" --progress-bar
    elif command -v wget &> /dev/null; then
        wget -O "$MODEL_DIR/$MODEL_FILE" "$MODEL_URL" --show-progress
    else
        echo "❌ Instale curl: pkg install curl"
        exit 1
    fi
fi

if [ -f "$MODEL_DIR/$MODEL_FILE" ]; then
    SIZE=$(du -h "$MODEL_DIR/$MODEL_FILE" | cut -f1)
    echo "✅ Modelo 3B: $SIZE"
else
    echo "❌ Falha no download"
    exit 1
fi

# Gera knowledge base
echo ""
echo "📚 Gerando Quimera Knowledge Base..."
cd "$HOME/storage/downloads/engine"
python3 quimera/cognition/knowledge_indexer.py . 2>/dev/null
echo "✅ Knowledge base gerada"

echo ""
echo "══════════════════════════════════════"
echo "  ✅ Setup completo!"
echo "  🧠 Modelo: Qwen 2.5 3B Instruct"
echo "  📚 Knowledge: ${MODEL_DIR}/../quimera/cognition/quimera_knowledge.json"
echo ""
echo "  Execute: quimera"
echo "══════════════════════════════════════"
