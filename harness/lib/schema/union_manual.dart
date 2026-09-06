// Side study (docs/dart-oracle-design.md Section 15): a small discriminated
// union, `Payload = Payload.text(String) | Payload.number(num)`, chosen
// specifically because it is the one schema feature (Section 8 Future Work)
// where `freezed`'s inclusion as a distinct target from `json_serializable`
// is actually exercised -- in the main Record schema, freezed delegates to
// json_serializable for every field, so B and C are identical everywhere.
// This is a deliberately separate schema/harness/oracle, additive only:
// nothing here is imported by or changes `harness/lib/schema/manual.dart`
// or the main Record pipeline.

sealed class ManualPayload {}

class ManualTextPayload extends ManualPayload {
  final String value;
  ManualTextPayload(this.value);
}

class ManualNumberPayload extends ManualPayload {
  final num value;
  ManualNumberPayload(this.value);
}

// Idiomatic-but-naive: a plain if/else dispatch on the discriminant, same
// spirit as harness/lib/schema/manual.dart's naive casts.
ManualPayload manualPayloadFromJson(Map<String, dynamic> json) {
  final type = json['type'];
  if (type == 'text') {
    return ManualTextPayload(json['value'] as String);
  }
  if (type == 'number') {
    return ManualNumberPayload(json['value'] as num);
  }
  throw ArgumentError('unknown payload type: $type');
}
