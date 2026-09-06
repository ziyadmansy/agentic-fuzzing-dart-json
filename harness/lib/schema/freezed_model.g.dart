// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'freezed_model.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_FreezedRecord _$FreezedRecordFromJson(Map<String, dynamic> json) =>
    _FreezedRecord(
      id: (json['id'] as num).toInt(),
      amount: json['amount'] as String,
      name: json['name'] as String?,
      status: $enumDecode(_$FreezedStatusEnumMap, json['status']),
      tags: (json['tags'] as List<dynamic>).map((e) => e as String).toList(),
      child: json['child'] == null
          ? null
          : FreezedRecord.fromJson(json['child'] as Map<String, dynamic>),
    );

Map<String, dynamic> _$FreezedRecordToJson(_FreezedRecord instance) =>
    <String, dynamic>{
      'id': instance.id,
      'amount': instance.amount,
      'name': instance.name,
      'status': _$FreezedStatusEnumMap[instance.status]!,
      'tags': instance.tags,
      'child': instance.child,
    };

const _$FreezedStatusEnumMap = {
  FreezedStatus.active: 'active',
  FreezedStatus.inactive: 'inactive',
  FreezedStatus.unknown: 'unknown',
};
