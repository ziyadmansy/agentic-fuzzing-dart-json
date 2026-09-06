// Side study (docs/dart-oracle-design.md Section 15). Unlike the main
// Record schema (where freezed delegates every field to json_serializable's
// generated code, so freezed and json_serializable are identical in every
// result), a discriminated union is freezed's own signature feature with
// native JSON dispatch support -- this is the one place freezed's inclusion
// as a distinct target is actually exercised.

import 'package:freezed_annotation/freezed_annotation.dart';

part 'union_freezed.freezed.dart';
part 'union_freezed.g.dart';

@Freezed(unionKey: 'type')
sealed class FreezedPayload with _$FreezedPayload {
  @FreezedUnionValue('text')
  const factory FreezedPayload.text(String value) = FreezedTextPayload;

  @FreezedUnionValue('number')
  const factory FreezedPayload.number(num value) = FreezedNumberPayload;

  factory FreezedPayload.fromJson(Map<String, Object?> json) => _$FreezedPayloadFromJson(json);
}
