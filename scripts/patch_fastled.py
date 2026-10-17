# FastLED 3.7.6 RMT (idf4) cuts a frame short when a buffer refill comes 1.5x late, but the
# other half of the buffer still has data until 2x. Under Wi-Fi load that dropped the tail of
# long strips every frame (animation "lags" past ~2 m). Patch the threshold to 2x at build time.
Import("env")

OLD = "mMaxCyclesPerFill = mCyclesPerFill + mCyclesPerFill / 2;"
NEW = "mMaxCyclesPerFill = 2 * mCyclesPerFill;"


def patch(node):
    path = node.srcnode().get_abspath()
    with open(path) as f:
        src = f.read()
    if OLD in src:
        with open(path, "w") as f:
            f.write(src.replace(OLD, NEW))
        print("patch_fastled: refill threshold 1.5x -> 2x")
    return node


env.AddBuildMiddleware(patch, "*idf4_rmt_impl.cpp")
