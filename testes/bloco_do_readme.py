"""Imprime o bloco de instalação de um sistema exatamente como está no README. A CI instala rodando isso."""
import re
import sys
from pathlib import Path

texto = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
m = re.search(r"^### " + re.escape(sys.argv[1]) + r".*?^```\n(.*?)^```", texto, re.S | re.M)
if not m:
    sys.exit(f"bloco de instalação {sys.argv[1]!r} não achado no README")
print(m.group(1), end="")
