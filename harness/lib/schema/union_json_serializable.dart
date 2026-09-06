// Side study (docs/dart-oracle-design.md Section 15). json_serializable has
// no native polymorphic/discriminated-union JSON support, so the realistic
// pattern -- what a real json_serializable user actually does for
// polymorphic JSON -- is a manual top-level dispatch function combined with
// @JsonSerializable() on each leaf variant. This is genuine practice, not a
// contrived weak point.

import 'package:json_annotation/json_annotation.dart';

part 'union_json_serializable.g.dart';

sealed class JsPayload {}

@JsonSerializable()
class JsTextPayload extends JsPayload {
  final String value;
  JsTextPayload(this.value);
  factory JsTextPayload.fromJson(Map<String, dynamic> json) => _$JsTextPayloadFromJson(json);
  Map<String, dynamic> toJson() => _$JsTextPayloadToJson(this);
}

@JsonSerializable()
class JsNumberPayload extends JsPayload {
  final num value;
  JsNumberPayload(this.value);
  factory JsNumberPayload.fromJson(Map<String, dynamic> json) => _$JsNumberPayloadFromJson(json);
  Map<String, dynamic> toJson() => _$JsNumberPayloadToJson(this);
}

JsPayload jsPayloadFromJson(Map<String, dynamic> json) {
  switch (json['type']) {
    case 'text':
      return JsTextPayload.fromJson(json);
    case 'number':
      return JsNumberPayload.fromJson(json);
    default:
      throw ArgumentError('unknown payload type: ${json['type']}');
  }
}
