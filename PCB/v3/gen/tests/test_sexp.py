from gen import sexp

SAMPLE = '(symbol "Device:R" (pin passive line (at 0 3.81 270) (length 1.27) (name "~" (effects (font (size 1.27 1.27))))))'

def test_roundtrip_preserves_quotes():
    node = sexp.parse(SAMPLE)[0]
    out = sexp.dumps(node)
    assert '"Device:R"' in out and '(at 0 3.81 270)' in out
    assert sexp.parse(out) == sexp.parse(SAMPLE)

def test_find():
    node = sexp.parse(SAMPLE)[0]
    pin = sexp.find1(node, "pin")
    assert sexp.find1(pin, "at")[1:] == ["0", "3.81", "270"]

def test_escapes():
    node = sexp.parse(r'(property "Value" "10k \"pull\"")')[0]
    assert node[2] == '10k "pull"'
    assert sexp.parse(sexp.dumps(node)) == [node]
