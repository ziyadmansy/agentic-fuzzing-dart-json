// Side study (docs/dart-oracle-design.md Section 15). built_value has no
// native polymorphic/discriminated-union JSON support either (like
// json_serializable, Section 15's manual dispatch pattern) -- the realistic
// approach is two ordinary Built leaf types plus a hand-written dispatch
// function inspecting the raw map's discriminant before picking a
// serializer, wrapped in a small plain (non-Built) marker type for a
// uniform return type.

import 'package:built_value/built_value.dart';
import 'package:built_value/serializer.dart';

part 'union_built_value.g.dart';

abstract class BvTextPayload implements Built<BvTextPayload, BvTextPayloadBuilder> {
  static Serializer<BvTextPayload> get serializer => _$bvTextPayloadSerializer;
  String get value;
  BvTextPayload._();
  factory BvTextPayload([void Function(BvTextPayloadBuilder) updates]) = _$BvTextPayload;
}

abstract class BvNumberPayload implements Built<BvNumberPayload, BvNumberPayloadBuilder> {
  static Serializer<BvNumberPayload> get serializer => _$bvNumberPayloadSerializer;
  num get value;
  BvNumberPayload._();
  factory BvNumberPayload([void Function(BvNumberPayloadBuilder) updates]) = _$BvNumberPayload;
}
