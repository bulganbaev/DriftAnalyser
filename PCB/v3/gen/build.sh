#!/usr/bin/env bash
# Regenerate the whole board from the model: schematic, PCB, routing, checks.
set -euo pipefail
cd "$(dirname "$0")/.."
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3

python3 -c 'from gen import sch_writer; sch_writer.write_all()'
"$KPY" -m gen.pcb_builder
"$KPY" -m gen.route
DA2_HEAVY=${DA2_HEAVY:-1} "$KPY" -m gen.export
python3 -m pytest gen/tests -q
