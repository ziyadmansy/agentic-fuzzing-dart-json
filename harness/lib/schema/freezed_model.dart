// Path C: freezed, configured to delegate JSON leaf-decoding to
// json_serializable (its default JSON backend) so that any B-vs-C divergence
// can be attributed to freezed's own contribution (immutability, union
// discrimination) rather than a second, independent JSON decoder
// (docs/dart-oracle-design.md Section 8).

import 'package:freezed_annotation/freezed_annotation.dart';

part 'freezed_model.freezed.dart';
part 'freezed_model.g.dart';

enum FreezedStatus { active, inactive, unknown }

@freezed
abstract class FreezedRecord with _$FreezedRecord {
  const factory FreezedRecord({
    required int id,
    required String amount,
    required String? name,
    required FreezedStatus status,
    required List<String> tags,
    required FreezedRecord? child,
  }) = _FreezedRecord;

  factory FreezedRecord.fromJson(Map<String, Object?> json) =>
      _$FreezedRecordFromJson(json);
}
