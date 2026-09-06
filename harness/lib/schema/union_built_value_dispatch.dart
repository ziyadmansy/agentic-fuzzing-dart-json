// Side study (docs/dart-oracle-design.md Section 15). Separate from
// union_built_value.dart (which only defines the two leaf Built types) to
// avoid a circular import with union_serializers.dart: this file imports
// both.

import 'union_built_value.dart';
import 'union_serializers.dart';

sealed class BvPayload {}

class BvTextPayloadVariant extends BvPayload {
  final BvTextPayload payload;
  BvTextPayloadVariant(this.payload);
}

class BvNumberPayloadVariant extends BvPayload {
  final BvNumberPayload payload;
  BvNumberPayloadVariant(this.payload);
}

BvPayload bvPayloadFromJson(Map<String, dynamic> json) {
  switch (json['type']) {
    case 'text':
      return BvTextPayloadVariant(
          unionSerializers.deserializeWith(BvTextPayload.serializer, json)!);
    case 'number':
      return BvNumberPayloadVariant(
          unionSerializers.deserializeWith(BvNumberPayload.serializer, json)!);
    default:
      throw ArgumentError('unknown payload type: ${json['type']}');
  }
}
