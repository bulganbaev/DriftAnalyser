"""Resolve symbols/footprints from the KiCad install and the project's own da3 library."""
import os, functools
from gen import env, sexp, model


@functools.lru_cache(None)
def _lib(libname):
    path = env.CUSTOM_SYM if libname == "da3" else os.path.join(env.SYMBOL_DIR, libname + ".kicad_sym")
    with open(path) as f:
        return sexp.parse(f.read())[0]


def _raw_symbol(libname, name):
    for node in sexp.find(_lib(libname), "symbol"):
        if node[1] == name:
            return node
    raise KeyError(f"{libname}:{name}")


def _subunits(node, old, new):
    """Rename the "<name>_<unit>_<style>" sub-unit prefix of every child symbol."""
    out = []
    for x in node:
        if isinstance(x, list) and x and x[0] == "symbol":
            x = list(x)
            x[1] = sexp.Str(x[1].replace(old, new, 1))
        out.append(x)
    return out


def symbol_def(lib_id):
    """Return the symbol node renamed to lib_id, following 'extends' one level."""
    libname, name = lib_id.split(":", 1)
    node = _raw_symbol(libname, name)
    ext = sexp.find1(node, "extends")
    if ext:
        base = _subunits(_raw_symbol(libname, ext[1]), ext[1], name)
        own_props = {p[1] for p in sexp.find(node, "property")}
        own_units = sexp.find(node, "symbol")
        drop = ("extends", "property") + (("symbol",) if own_units else ())
        merged = [x for x in base
                  if not (isinstance(x, list) and x[0] in drop and
                          (x[0] != "property" or x[1] in own_props))]
        merged += [x for x in node if isinstance(x, list) and x[0] == "property"]
        merged += own_units
        merged[1] = sexp.Str(name)
        node = merged
    out = _subunits(node, name, lib_id)
    out[1] = sexp.Str(lib_id)
    return out


def symbol_pins(lib_id):
    """{pin number: (x_mm, y_mm, angle_deg, name, etype)}"""
    node = symbol_def(lib_id)
    pins = {}

    def walk(n):
        for x in n:
            if isinstance(x, list):
                if x and x[0] == "pin":
                    at = sexp.find1(x, "at")
                    num = sexp.find1(x, "number")[1]
                    nm = sexp.find1(x, "name")[1]
                    pins[num] = (float(at[1]), float(at[2]),
                                 float(at[3]) if len(at) > 3 else 0.0, nm, x[1])
                walk(x)

    walk(node)
    return pins


def footprint_path(fp_id):
    libname, name = fp_id.split(":", 1)
    d = env.CUSTOM_FP if libname == "da3" else os.path.join(env.FOOTPRINT_DIR, libname + ".pretty")
    return d, name


def all_symbols_resolve():
    bad = []
    for p in model.PARTS:
        try:
            symbol_def(p.symbol)
        except (KeyError, FileNotFoundError):
            bad.append(p.symbol)
    return bad


def symbol_exists(lib_id):
    try:
        symbol_def(lib_id)
        return True
    except (KeyError, FileNotFoundError):
        return False


def _footprint_text(fp_id):
    d, name = footprint_path(fp_id)
    with open(os.path.join(d, name + ".kicad_mod")) as f:
        return f.read()


def footprint_exists(fp_id):
    d, name = footprint_path(fp_id)
    return os.path.exists(os.path.join(d, name + ".kicad_mod"))


def footprint_pad_names(fp_id):
    """Non-empty pad names of a footprint."""
    root = sexp.parse(_footprint_text(fp_id))[0]
    return {p[1] for p in sexp.find(root, "pad") if p[1]}


def symbol_pin_names(lib_id):
    """{pin number: pin name}"""
    return {n: v[3] for n, v in symbol_pins(lib_id).items()}


def custom_symbol_footprints():
    """(lib_id, Footprint property) for every symbol in the da3 library."""
    out = []
    for node in sexp.find(_lib("da3"), "symbol"):
        for p in sexp.find(node, "property"):
            if p[1] == "Footprint" and p[2]:
                out.append((node[1], p[2]))
    return out
