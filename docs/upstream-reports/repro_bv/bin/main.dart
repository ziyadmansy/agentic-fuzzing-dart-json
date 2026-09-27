import 'dart:convert';
import 'package:repro_bv/model.dart';

void main() {
  const inputs = [
    '{"id": 1, "tags": ["a"]}',
    '{"id": 1, "tags": []}',
    '{"id": 1}',
    '{"tags": ["a"]}',
    '{"id": 1, "tags": null}',
    '{"id": null, "tags": ["a"]}',
  ];
  for (final input in inputs) {
    final json = jsonDecode(input);
    String run(Object? Function() f) {
      try { return '${f()}'.replaceAll('\n', ' '); } catch (e) { return 'throws ${e.runtimeType}'; }
    }
    print(input.padRight(28) +
        ' default: ${run(() => serializers.deserializeWith(Item.serializer, json))}'.padRight(55) +
        ' nestedBuilders:false: ${run(() => serializers.deserializeWith(ItemNoNested.serializer, json))}');
  }
  // Direct builder, no serialization involved:
  print('Item((b) => b..id = 1) -> ${Item((b) => b..id = 1)}'.replaceAll('\n', ' '));
}
