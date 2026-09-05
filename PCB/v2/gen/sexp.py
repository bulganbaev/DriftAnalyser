"""Minimal S-expression reader/writer for KiCad files."""

class Str(str):
    """A quoted string atom."""

class Sym(str):
    """A bare atom."""

def parse(text):
    i, n = 0, len(text)
    stack = [[]]
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c == '(':
            stack.append([]); i += 1
        elif c == ')':
            node = stack.pop(); stack[-1].append(node); i += 1
        elif c == '"':
            j = i + 1; buf = []
            while text[j] != '"':
                if text[j] == '\\':
                    j += 1
                buf.append(text[j]); j += 1
            stack[-1].append(Str(''.join(buf))); i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '()':
                j += 1
            stack[-1].append(Sym(text[i:j])); i = j
    return stack[0]

def _atom(a):
    if isinstance(a, Str):
        return '"' + a.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return str(a)

def dumps(node, indent=0):
    if not isinstance(node, list):
        return _atom(node)
    pad = '  ' * indent
    if all(not isinstance(x, list) for x in node):
        return pad + '(' + ' '.join(_atom(x) for x in node) + ')'
    head = [ _atom(x) for x in node if not isinstance(x, list) ]
    kids = [ x for x in node if isinstance(x, list) ]
    out = pad + '(' + ' '.join(head) + '\n'
    out += '\n'.join(dumps(k, indent + 1) for k in kids)
    return out + '\n' + pad + ')'

def find(node, tag):
    return [x for x in node if isinstance(x, list) and x and x[0] == tag]

def find1(node, tag):
    hits = find(node, tag)
    return hits[0] if hits else None
