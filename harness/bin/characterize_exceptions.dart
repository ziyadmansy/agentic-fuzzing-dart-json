// Hand-picked malformed documents run through all four paths, to build the
// known-answer set docs/dart-oracle-design.md Section 8 "Next up" calls for
// before any automated classifier exists. Also verifies a structural
// assumption the design doc's Section 6.2 needs to state precisely: since all
// four schema `fromJson`/deserialize entry points take an already-parsed
// Dart object (Map/List/etc.), not raw text, JSON *syntax* validity is a
// single shared gate (dart:convert.jsonDecode) upstream of all four paths --
// divergence between paths can only happen at the *schema* level, never at
// the JSON-syntax level.

import 'dart:convert';

import '../lib/schema/manual.dart';
import '../lib/schema/json_serializable_model.dart';
import '../lib/schema/freezed_model.dart';
import '../lib/schema/built_value_model.dart';
import '../lib/schema/serializers.dart';

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
  Object? decoded;
  try {
    decoded = jsonDecode(json);
  } catch (e) {
    print('  [shared syntax gate] ${e.runtimeType} -- $e');
    print('  (no path reached -- confirms syntax rejection is shared, not per-path)');
    print('');
    return;
  }
  final map = decoded as Map<String, dynamic>;
  tryPath('A manual            ', () => ManualRecord.fromJson(map));
  tryPath('B json_serializable ', () => JsRecord.fromJson(map));
  tryPath('C freezed           ', () => FreezedRecord.fromJson(map));
  tryPath('D built_value       ',
      () => serializers.deserializeWith(BvRecord.serializer, map));
  print('');
}

void main() {
  runCase('valid baseline', '''
    {"id": 42, "amount": "19.99", "name": "sample", "status": "active", "tags": ["a"], "child": null}
  ''');

  runCase('syntactically invalid JSON (trailing comma)', '''
    {"id": 42, "amount": "19.99",}
  ''');

  runCase('id as string instead of int', '''
    {"id": "42", "amount": "19.99", "name": "sample", "status": "active", "tags": ["a"], "child": null}
  ''');

  runCase('unrecognized enum value for status', '''
    {"id": 42, "amount": "19.99", "name": "sample", "status": "archived", "tags": ["a"], "child": null}
  ''');

  runCase('missing required field (tags)', '''
    {"id": 42, "amount": "19.99", "name": "sample", "status": "active", "child": null}
  ''');

  runCase('name is a number instead of string/null', '''
    {"id": 42, "amount": "19.99", "name": 7, "status": "active", "tags": ["a"], "child": null}
  ''');

  runCase('tags contains a non-string element', '''
    {"id": 42, "amount": "19.99", "name": "sample", "status": "active", "tags": [1, 2], "child": null}
  ''');

  runCase('extra unknown top-level field', '''
    {"id": 42, "amount": "19.99", "name": "sample", "status": "active", "tags": ["a"], "child": null, "extra": true}
  ''');

  runCase('null for a required non-nullable field (id)', '''
    {"id": null, "amount": "19.99", "name": "sample", "status": "active", "tags": ["a"], "child": null}
  ''');

  runCase('missing required field (status)', '''
    {"id": 42, "amount": "19.99", "name": "sample", "tags": ["a"], "child": null}
  ''');

  runCase('missing required field (id)', '''
    {"amount": "19.99", "name": "sample", "status": "active", "tags": ["a"], "child": null}
  ''');

  runCase('missing required field (amount)', '''
    {"id": 42, "name": "sample", "status": "active", "tags": ["a"], "child": null}
  ''');

  runCase('missing optional field (name) -- should NOT diverge, name is nullable', '''
    {"id": 42, "amount": "19.99", "status": "active", "tags": ["a"], "child": null}
  ''');

  runCase('missing field entirely absent (child) -- should NOT diverge, child is nullable', '''
    {"id": 42, "amount": "19.99", "name": "sample", "status": "active", "tags": ["a"]}
  ''');
}
