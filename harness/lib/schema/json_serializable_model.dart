// Path B: json_serializable codegen. Left at its own defaults deliberately
// (no `unknownEnumValue`, no custom converters) since the point of RQ2 is to
// compare how these frameworks behave *out of the box*, matching how most
// real Flutter codebases actually use them.

import 'package:json_annotation/json_annotation.dart';

part 'json_serializable_model.g.dart';

enum JsStatus { active, inactive, unknown }

@JsonSerializable()
class JsRecord {
  final int id;
  final String amount;
  final String? name;
  final JsStatus status;
  final List<String> tags;
  final JsRecord? child;

  JsRecord({
    required this.id,
    required this.amount,
    required this.name,
    required this.status,
    required this.tags,
    required this.child,
  });

  factory JsRecord.fromJson(Map<String, dynamic> json) =>
      _$JsRecordFromJson(json);

  Map<String, dynamic> toJson() => _$JsRecordToJson(this);
}
