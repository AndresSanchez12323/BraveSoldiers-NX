#!/usr/bin/env python3
"""Verifica una copia de Saint Seiya: Brave Soldiers (PS3) sin modificarla.

Acepta la carpeta PS3_GAME, la carpeta raiz del disco (la que contiene PS3_GAME)
o una imagen .iso (ISO 9660). Solo lee: no copia, extrae ni escribe nada salvo
el manifiesto opcional de --json.

Uso:
    python tools/check_game.py RUTA
    python tools/check_game.py RUTA --json local/manifest.json
    python tools/check_game.py RUTA/EBOOT.ELF          (un ELF descifrado suelto)
"""

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

KNOWN_TITLE_IDS = {
    "BLES01936": "Europa",
    "BLJS10236": "Japon",
}
EXECUTABLE_SUFFIXES = (".bin", ".self", ".sprx", ".elf", ".prx")
SECTOR = 2048
CHUNK = 1 << 20

# Nombres de modulo de sistema que aparecen como texto en la tabla de importaciones
# de un ELF descifrado (cellSpursJq, cellGcmSys, sysPrxForUser...).
MODULE_RE = re.compile(rb"(?<![A-Za-z0-9_])(cell[A-Z][A-Za-z0-9]{2,31}|sys[A-Z][A-Za-z0-9]{2,31}|sceNp[A-Za-z0-9]{0,31})\x00")


# --- Fuentes: carpeta o ISO -------------------------------------------------

class FolderSource:
    def __init__(self, root):
        self.root = root

    def files(self):
        for p in sorted(self.root.rglob("*")):
            if p.is_file():
                yield p.relative_to(self.root).as_posix(), p.stat().st_size

    def read(self, rel, length=None):
        with open(self.root / rel, "rb") as f:
            return f.read() if length is None else f.read(length)

    def chunks(self, rel):
        with open(self.root / rel, "rb") as f:
            while block := f.read(CHUNK):
                yield block


class IsoSource:
    """Lector minimo de ISO 9660 (solo lectura). Soporta archivos multi-extent (>4 GB).

    Usa el arbol Joliet si existe (nombres largos); si no, el primario (nombres 8.3).
    """

    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        pvd = self._sector(16)
        if pvd[1:6] != b"CD001" or pvd[0] != 1:
            raise ValueError("no es una imagen ISO 9660 (falta el descriptor primario)")
        self.joliet = False
        root = pvd[156:190]
        for lba in range(17, 32):
            vd = self._sector(lba)
            if vd[1:6] != b"CD001" or vd[0] == 255:
                break
            if vd[0] == 2 and vd[88:91] in (b"%/@", b"%/C", b"%/E"):
                self.joliet = True
                root = vd[156:190]
                break
        self.entries = {}
        self._walk(struct.unpack_from("<I", root, 2)[0], struct.unpack_from("<I", root, 10)[0], "", set())

    def _sector(self, lba, count=1):
        self.f.seek(lba * SECTOR)
        return self.f.read(SECTOR * count)

    def _walk(self, lba, size, prefix, seen):
        if lba in seen:
            return
        seen.add(lba)
        data = self._sector(lba, (size + SECTOR - 1) // SECTOR)
        pos = 0
        while pos < size:
            rec_len = data[pos]
            if rec_len == 0:  # el resto del sector esta vacio
                pos = (pos // SECTOR + 1) * SECTOR
                continue
            rec = data[pos:pos + rec_len]
            pos += rec_len
            name_len = rec[32]
            raw = rec[33:33 + name_len]
            if raw in (b"\x00", b"\x01"):
                continue
            name = raw.decode("utf-16-be" if self.joliet else "ascii", "replace").split(";")[0]
            extent = struct.unpack_from("<I", rec, 2)[0]
            length = struct.unpack_from("<I", rec, 10)[0]
            flags = rec[25]
            rel = f"{prefix}{name}"
            if flags & 0x02:
                self._walk(extent, length, rel + "/", seen)
            else:
                self.entries.setdefault(rel, []).append((extent, length))

    def files(self):
        for rel in sorted(self.entries):
            yield rel, sum(length for _, length in self.entries[rel])

    def chunks(self, rel):
        for extent, length in self.entries[rel]:
            self.f.seek(extent * SECTOR)
            left = length
            while left > 0:
                block = self.f.read(min(CHUNK, left))
                if not block:
                    raise IOError(f"ISO truncada leyendo {rel}")
                left -= len(block)
                yield block

    def read(self, rel, length=None):
        out = bytearray()
        for block in self.chunks(rel):
            out += block
            if length is not None and len(out) >= length:
                return bytes(out[:length])
        return bytes(out)


class SingleFileSource:
    def __init__(self, path):
        self.path = path

    def files(self):
        yield self.path.name, self.path.stat().st_size

    def read(self, rel, length=None):
        with open(self.path, "rb") as f:
            return f.read() if length is None else f.read(length)

    def chunks(self, rel):
        with open(self.path, "rb") as f:
            while block := f.read(CHUNK):
                yield block


def open_source(path):
    if path.is_dir():
        if (path / "PS3_GAME").is_dir():
            return FolderSource(path), "PS3_GAME/"
        return FolderSource(path), ""
    if path.suffix.lower() == ".iso":
        return IsoSource(path), None
    return SingleFileSource(path), ""


# --- Formatos ---------------------------------------------------------------

def parse_sfo(data):
    if data[:4] != b"\x00PSF":
        raise ValueError("PARAM.SFO sin firma PSF")
    key_table, data_table, count = struct.unpack_from("<III", data, 8)
    out = {}
    for i in range(count):
        key_off, fmt, length, _max_len, data_off = struct.unpack_from("<HHIII", data, 20 + i * 16)
        key_end = data.index(b"\x00", key_table + key_off)
        key = data[key_table + key_off:key_end].decode("ascii")
        raw = data[data_table + data_off:data_table + data_off + length]
        if fmt == 0x0404:
            out[key] = struct.unpack("<I", raw[:4])[0]
        else:
            out[key] = raw.rstrip(b"\x00").decode("utf-8", "replace")
    return out


def classify(head):
    """Devuelve (tipo, detalle) a partir de los primeros bytes."""
    if head[:4] == b"SCE\x00":
        header_type = struct.unpack_from(">H", head, 10)[0] if len(head) >= 12 else 0
        return "SELF", "cifrado" if header_type == 1 else f"cabecera SCE tipo {header_type}"
    if head[:4] == b"\x7fELF" and len(head) >= 20:
        bits = 64 if head[4] == 2 else 32
        machine = struct.unpack_from(">H", head, 18)[0]
        arch = {0x15: "PPU (PPC64)", 0x17: "SPU"}.get(machine, f"maquina 0x{machine:X}")
        return "ELF", f"descifrado, {bits} bits, {arch}"
    return "otro", ""


def parse_imports(data):
    """Lee la tabla de importaciones (sys_process_prx_info) de un ELF PPU de 64 bits.

    Devuelve {modulo: numero de funciones} o None si el ELF no tiene esa tabla.
    """
    if data[4] != 2:
        return None
    phoff = struct.unpack_from(">Q", data, 0x20)[0]
    phnum = struct.unpack_from(">H", data, 0x38)[0]
    loads, prx = [], None
    for i in range(phnum):
        p_type, _flags, off, vaddr, _paddr, filesz = struct.unpack_from(">IIQQQQ", data, phoff + i * 56)
        if p_type == 1 and filesz:
            loads.append((vaddr, off, filesz))
        elif p_type == 0x60000002:
            prx = off
    if prx is None:
        return None

    def to_offset(va):
        for vaddr, off, filesz in loads:
            if vaddr <= va < vaddr + filesz:
                return off + va - vaddr
        raise ValueError(f"direccion fuera de los segmentos: 0x{va:X}")

    _size, magic, _ver, _sdk, _le_s, _le_e, stub, stub_end = struct.unpack_from(">8I", data, prx)
    if magic != 0x1B434CEC:
        return None
    out = {}
    while stub < stub_end:
        o = to_offset(stub)
        entry_size, num_func, name_ptr = data[o], struct.unpack_from(">H", data, o + 6)[0], struct.unpack_from(">I", data, o + 16)[0]
        n = to_offset(name_ptr)
        out[data[n:data.index(b"\x00", n)].decode()] = num_func
        stub += entry_size
    return out


def scan_elf(data):
    """Programas SPU incrustados y modulos de sistema importados en un ELF descifrado."""
    spu = 0
    for m in re.finditer(rb"\x7fELF\x01\x02\x01", data):
        off = m.start()
        if off and data[off + 18:off + 20] == b"\x00\x17":
            spu += 1
    modules = parse_imports(data)
    if modules is None:  # sin tabla: aproximacion por texto
        modules = {m.group(1).decode(): None for m in MODULE_RE.finditer(data)}
    return spu, dict(sorted(modules.items()))


def sha256_of(source, rel):
    h = hashlib.sha256()
    for block in source.chunks(rel):
        h.update(block)
    return h.hexdigest().upper()


# --- Programa ---------------------------------------------------------------

def find_prefix(names):
    """Localiza el prefijo de PS3_GAME dentro de la lista de archivos."""
    for rel in names:
        idx = rel.upper().find("PS3_GAME/PARAM.SFO")
        if idx >= 0:
            return rel[:idx] + rel[idx:idx + len("PS3_GAME/")]
        if rel.upper() == "PARAM.SFO":
            return ""
    return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", type=Path)
    ap.add_argument("--json", type=Path, help="escribe un manifiesto local con tamanos y hashes")
    args = ap.parse_args()

    if not args.path.exists():
        sys.exit(f"No existe: {args.path}")
    source, prefix = open_source(args.path)
    files = dict(source.files())
    if prefix is None:
        prefix = find_prefix(files)
    elif prefix == "" and not any(r.upper() == "PARAM.SFO" for r in files):
        prefix = find_prefix(files)

    report = {"source": str(args.path), "total_files": len(files), "total_bytes": sum(files.values())}
    print(f"Origen: {args.path}")
    print(f"Archivos: {len(files)}  Tamano total: {report['total_bytes'] / 2**30:.2f} GiB")

    lookup = {r.upper(): r for r in files}
    sfo_rel = lookup.get((prefix + "PARAM.SFO").upper())
    if sfo_rel:
        sfo = parse_sfo(source.read(sfo_rel))
        report["param_sfo"] = sfo
        tid = sfo.get("TITLE_ID", "?")
        print(f"\nPARAM.SFO: {sfo.get('TITLE', '?')}")
        print(f"  TITLE_ID {tid}  APP_VER {sfo.get('APP_VER', '?')}  VERSION {sfo.get('VERSION', '?')}  "
              f"CATEGORY {sfo.get('CATEGORY', '?')}  PS3_SYSTEM_VER {sfo.get('PS3_SYSTEM_VER', '?')}")
        if tid in KNOWN_TITLE_IDS:
            print(f"  Reconocido: Brave Soldiers ({KNOWN_TITLE_IDS[tid]})")
        else:
            print("  AVISO: TITLE_ID no esta en la lista conocida de Brave Soldiers (anotalo en baserom.md)")
    else:
        print("\nAVISO: no se encontro PARAM.SFO")

    executables = [r for r in files if r.lower().endswith(EXECUTABLE_SUFFIXES)
                   and (r.upper().endswith("EBOOT.BIN") or not r.lower().endswith(".bin"))]
    report["executables"] = []
    print(f"\nEjecutables y modulos ({len(executables)}):")
    for rel in sorted(executables):
        kind, detail = classify(source.read(rel, 64))
        entry = {"path": rel, "size": files[rel], "type": kind, "detail": detail, "sha256": sha256_of(source, rel)}
        if kind == "ELF":
            spu, modules = scan_elf(source.read(rel))
            entry["embedded_spu_elfs"] = spu
            entry["imported_modules"] = modules
        report["executables"].append(entry)
        print(f"  {rel}  {files[rel]:,} B  {kind} {detail}")
        print(f"    SHA-256 {entry['sha256']}")
        if kind == "ELF":
            print(f"    SPU incrustados: {entry['embedded_spu_elfs']}")
            mods = entry["imported_modules"]
            if mods:
                known = [n for n in mods.values() if n is not None]
                total = f", {sum(known)} funciones" if known else ""
                print(f"    Modulos importados ({len(mods)}{total}):")
                for name, count in mods.items():
                    print(f"      {name:24s} {'' if count is None else count}")
    if any(e["type"] == "SELF" for e in report["executables"]):
        print("\nHay binarios cifrados (SELF). Descifralos con RPCS3 (Utilities > Decrypt PS3 Binaries)"
              "\ny vuelve a ejecutar este script sobre los .elf para ver SPU y modulos.")

    biggest = sorted(files.items(), key=lambda kv: kv[1], reverse=True)[:10]
    print("\nArchivos mas grandes:")
    for rel, size in biggest:
        print(f"  {size / 2**20:9.1f} MiB  {rel}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nManifiesto escrito en {args.json}")


if __name__ == "__main__":
    main()
