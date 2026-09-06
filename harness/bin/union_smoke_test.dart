// Sanity check for the discriminated-union side study
// (docs/dart-oracle-design.md Section 15), matching the discipline used for
// the main Record schema (bin/smoke_test.dart): one valid document per
// variant, decoded by all four paths, before anything else is built.

import 'dart:convert';
import 'dart:io';

import '../lib/schema/union_manual.dart';
import '../lib/schema/union_json_serializable.dart';
import '../lib/schema/union_freezed.dart';
import '../lib/schema/union_built_value_dispatch.dart';

void expect(String label, Object? actual, Object? expected) {
  if (actual != expected) {
    stderr.writeln('FAIL $label: expected $expected, got $actual');
    exitCode = 1;
  } else {
    print('ok   $label: $actual');
  }
}

void main() {
  final textJson = jsonDecode('{"type": "text", "value": "hello"}') as Map<String, dynamic>;
  final numberJson = jsonDecode('{"type": "number", "value": 42}') as Map<String, dynamic>;

  final aText = manualPayloadFromJson(textJson) as ManualTextPayload;
  expect('A.text.value', aText.value, 'hello');
  final aNumber = manualPayloadFromJson(numberJson) as ManualNumberPayload;
  expect('A.number.value', aNumber.value, 42);

  final bText = jsPayloadFromJson(textJson) as JsTextPayload;
  expect('B.text.value', bText.value, 'hello');
  final bNumber = jsPayloadFromJson(numberJson) as JsNumberPayload;
  expect('B.number.value', bNumber.value, 42);

  final cText = FreezedPayload.fromJson(textJson) as FreezedTextPayload;
  expect('C.text.value', cText.value, 'hello');
  final cNumber = FreezedPayload.fromJson(numberJson) as FreezedNumberPayload;
  expect('C.number.value', cNumber.value, 42);

  final dText = bvPayloadFromJson(textJson) as BvTextPayloadVariant;
  expect('D.text.value', dText.payload.value, 'hello');
  final dNumber = bvPayloadFromJson(numberJson) as BvNumberPayloadVariant;
  expect('D.number.value', dNumber.payload.value, 42);

  if (exitCode == 0) {
    print('\nAll four paths agree on both variants.');
  }
}
