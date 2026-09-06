#!/bin/sh
# Dart equivalent of the original project's build_target.sh (handoff Section
# 4.2, gap 10): there is no sanitizer-instrumented build here -- Dart is
# memory-safe, so the "oracle" is the four-way differential/tier classifier
# (docs/dart-oracle-design.md), not a compiler flag. This script's only job is
# to produce one AOT-compiled executable honoring the NDJSON stdin/stdout
# contract (design doc Section 9) that the rest of the pipeline depends on.
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mkdir -p "$root/build"

(cd "$root/harness" && dart pub get)
dart compile exe "$root/harness/bin/dart_json_harness.dart" -o "$root/build/dart_json_harness"

printf 'sanity check (expect status=schema_evaluated, all four paths accepted):\n'
printf '{"input_b64":"%s"}\n' "$(printf '{"id":1,"amount":"1","name":null,"status":"active","tags":[],"child":null}' | base64)" \
    | "$root/build/dart_json_harness"
