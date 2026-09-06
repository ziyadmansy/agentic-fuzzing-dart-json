// Hand-picked malformed union documents (docs/dart-oracle-design.md Section
// 15), mirroring bin/characterize_exceptions.dart's role for the main
// schema: characterize behavior before building automated oracle/harness
// infrastructure, and specifically check whether freezed (native union
// dispatch) ever diverges from json_serializable (manual dispatch) now that
// there is a feature freezed provides and json_serializable does not.

import 'dart:convert';

import '../lib/schema/union_manual.dart';
import '../lib/schema/union_json_serializable.dart';
import '../lib/schema/union_freezed.dart';
import '../lib/schema/union_built_value_dispatch.dart';

void tryPath(String label, Object? Function() decode) {
  try {
    final result = decode();
    print('  $label: accepted -> $result');
  } catch (e) {
    print('  $label: ${e.runtimeType} -- $e');
  }
}

void runCase(String name, String json) {
  print('=== $name ===');
  print('  input: $json');
  final map = jsonDecode(json) as Map<String, dynamic>;
  tryPath('A manual            ', () => manualPayloadFromJson(map));
  tryPath('B json_serializable ', () => jsPayloadFromJson(map));
  tryPath('C freezed           ', () => FreezedPayload.fromJson(map));
  tryPath('D built_value       ', () => bvPayloadFromJson(map));
  print('');
}

void main() {
  runCase('valid text', '{"type": "text", "value": "hello"}');
  runCase('valid number', '{"type": "number", "value": 42}');
  runCase('unknown discriminant', '{"type": "boolean", "value": true}');
  runCase('missing discriminant', '{"value": "hello"}');
  runCase('null discriminant', '{"type": null, "value": "hello"}');
  runCase('wrong-type discriminant (number instead of string)', '{"type": 1, "value": "hello"}');
  runCase('text variant, wrong-type value (number instead of string)', '{"type": "text", "value": 42}');
  runCase('number variant, wrong-type value (string instead of number)', '{"type": "number", "value": "42"}');
  runCase('text variant, missing value', '{"type": "text"}');
  runCase('text variant, null value', '{"type": "text", "value": null}');
  runCase('extra unknown field', '{"type": "text", "value": "hello", "extra": true}');
  runCase('discriminant with different case', '{"type": "Text", "value": "hello"}');
  runCase('empty object', '{}');
}
