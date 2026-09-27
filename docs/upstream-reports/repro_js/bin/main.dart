import 'dart:convert';
import 'package:repro_js/model.dart';
import 'package:repro_js/fmodel.dart';

void main() {
  const inputs = [
    '{"id": 42}',
    '{"id": 42.0}',
    '{"id": 1.9}',
    '{"id": -1.9}',
    '{"id": 99999999999999999999999999}',
    '{"id": -99999999999999999999999999}',
    '{"id": 1e300}',
  ];
  for (final input in inputs) {
    final json = jsonDecode(input) as Map<String, dynamic>;
    String run(Object Function() f) {
      try { return '${f()}'; } catch (e) { return 'throws ${e.runtimeType}'; }
    }
    print('$input'.padRight(40) +
        ' json_serializable: ${run(() => Item.fromJson(json).id)}'.padRight(45) +
        ' freezed: ${run(() => FItem.fromJson(json).id)}'.padRight(36) +
        ' manual `as int`: ${run(() => json['id'] as int)}');
  }
}
