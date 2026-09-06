// Path D: built_value. An independently-designed serialization model
// (typed `Serializers`/`FullType`, not annotation+`Map`-based like B/C) --
// the path most likely to diverge for genuinely independent-implementation
// reasons rather than shared-backend reasons (docs/dart-oracle-design.md
// Section 2).

import 'package:built_collection/built_collection.dart';
import 'package:built_value/built_value.dart';
import 'package:built_value/serializer.dart';

part 'built_value_model.g.dart';

class BvStatus extends EnumClass {
  static const BvStatus active = _$active;
  static const BvStatus inactive = _$inactive;
  static const BvStatus unknown = _$unknown;

  const BvStatus._(String name) : super(name);

  static BuiltSet<BvStatus> get values => _$bvStatusValues;
  static BvStatus valueOf(String name) => _$bvStatusValueOf(name);
  static Serializer<BvStatus> get serializer => _$bvStatusSerializer;
}

abstract class BvRecord implements Built<BvRecord, BvRecordBuilder> {
  static Serializer<BvRecord> get serializer => _$bvRecordSerializer;

  int get id;
  String get amount;
  String? get name;
  BvStatus get status;
  BuiltList<String> get tags;
  BvRecord? get child;

  BvRecord._();
  factory BvRecord([void Function(BvRecordBuilder) updates]) = _$BvRecord;
}
