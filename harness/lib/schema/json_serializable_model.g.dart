// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'json_serializable_model.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

JsRecord _$JsRecordFromJson(Map<String, dynamic> json) => JsRecord(
  id: (json['id'] as num).toInt(),
  amount: json['amount'] as String,
  name: json['name'] as String?,
  status: $enumDecode(_$JsStatusEnumMap, json['status']),
  tags: (json['tags'] as List<dynamic>).map((e) => e as String).toList(),
  child: json['child'] == null
      ? null
      : JsRecord.fromJson(json['child'] as Map<String, dynamic>),
);

Map<String, dynamic> _$JsRecordToJson(JsRecord instance) => <String, dynamic>{
  'id': instance.id,
  'amount': instance.amount,
  'name': instance.name,
  'status': _$JsStatusEnumMap[instance.status]!,
  'tags': instance.tags,
  'child': instance.child,
};

const _$JsStatusEnumMap = {
  JsStatus.active: 'active',
  JsStatus.inactive: 'inactive',
  JsStatus.unknown: 'unknown',
};
