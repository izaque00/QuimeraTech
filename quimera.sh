#!/data/data/com.termux/files/usr/bin/bash
# ═══════════════════════════════════════════
#  Quimera — Launcher Interativo
#  Uso: quimera [comando]
#  Ex:  quimera              → shell interativo
#       quimera assist "..."  → comando único
# ═══════════════════════════════════════════
QUIMERA_HOME="${QUIMERA_HOME:-$HOME/storage/downloads/engine}"
if [ -d "$QUIMERA_HOME" ]; then
    cd "$QUIMERA_HOME"
    if [ $# -eq 0 ]; then
        exec python -m quimera shell "$@"
    else
        exec python -m quimera "$@"
    fi
else
    echo "❌ Quimera não encontrado em $QUIMERA_HOME"
    echo "   Defina QUIMERA_HOME ou instale em ~/storage/downloads/engine"
    exit 1
fi
