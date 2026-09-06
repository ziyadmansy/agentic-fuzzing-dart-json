// Sanity check per docs/dart-oracle-design.md Section 8: one hand-written,
// unambiguous valid JSON document, decoded identically by all four paths.
// This is the Dart equivalent of the original project's
// `printf '{}' | ./build/cjson_harness` check -- it validates the toolchain
// and the four schema implementations agree before any fuzzing/generation
// code is written.

import 'dart:convert';
import 'dart:io';

import '../lib/schema/manual.dart';
import '../lib/schema/json_serializable_model.dart';
import '../lib/schema/freezed_model.dart';
import '../lib/schema/built_value_model.dart';
import '../lib/schema/serializers.dart';

const sampleJson = '''
{
  "id": 42,
  "amount": "19.99",
  "name": "sample",
  "status": "active",
  "tags": ["a", "b"],
  "child": null
}
''';

void expect(String label, Object? actual, Object? expected) {
  if (actual != expected) {
    stderr.writeln('FAIL $label: expected $expected, got $actual');
    exitCode = 1;
  } else {
    print('ok   $label: $actual');
  }
}

void main() {
  final map = jsonDecode(sampleJson) as Map<String, dynamic>;

  final a = ManualRecord.fromJson(map);
  expect('A.id', a.id, 42);
  expect('A.amount', a.amount, '19.99');
  expect('A.name', a.name, 'sample');
  expect('A.status', a.status, ManualStatus.active);
  expect('A.tags', a.tags.join(','), 'a,b');
  expect('A.child', a.child, null);

  final b = JsRecord.fromJson(map);
  expect('B.id', b.id, 42);
  expect('B.amount', b.amount, '19.99');
  expect('B.name', b.name, 'sample');
  expect('B.status', b.status, JsStatus.active);
  expect('B.tags', b.tags.join(','), 'a,b');
  expect('B.child', b.child, null);

  final c = FreezedRecord.fromJson(map);
  expect('C.id', c.id, 42);
  expect('C.amount', c.amount, '19.99');
  expect('C.name', c.name, 'sample');
  expect('C.status', c.status, FreezedStatus.active);
  expect('C.tags', c.tags.join(','), 'a,b');
  expect('C.child', c.child, null);

  final d = serializers.deserializeWith(BvRecord.serializer, map)!;
  expect('D.id', d.id, 42);
  expect('D.amount', d.amount, '19.99');
  expect('D.name', d.name, 'sample');
  expect('D.status', d.status, BvStatus.active);
  expect('D.tags', d.tags.join(','), 'a,b');
  expect('D.child', d.child, null);

  if (exitCode == 0) {
    print('\nAll four paths agree on the sample document.');
  }
}
