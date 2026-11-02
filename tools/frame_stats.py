"""Brillo medio de los volcados CELLMARK_DUMP (frame_*.bmp) de una carpeta.

Uso: python -I tools/frame_stats.py local/recomp/prueba1
0 = negro, 255 = blanco. Sirve para ver de un vistazo si hay contenido o parpadeo
(valores que alternan entre ~0 y otro valor en volcados consecutivos).
"""
import glob
import os
import struct
import sys

folder = sys.argv[1] if len(sys.argv) > 1 else "."
for f in sorted(glob.glob(os.path.join(folder, "frame_*.bmp"))):
    d = open(f, "rb").read()
    px = d[struct.unpack("<I", d[10:14])[0]:][::97]
    print(os.path.basename(f), round(sum(px) / max(len(px), 1), 1))
