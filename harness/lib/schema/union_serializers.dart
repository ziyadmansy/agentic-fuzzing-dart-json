// Side study (docs/dart-oracle-design.md Section 15). A separate Serializers
// registry from `serializers.dart` (which serves the main Record schema) so
// this side study never risks the validated main pipeline.

import 'package:built_value/serializer.dart';
import 'package:built_value/standard_json_plugin.dart';

import 'union_built_value.dart';

part 'union_serializers.g.dart';

@SerializersFor([BvTextPayload, BvNumberPayload])
final Serializers unionSerializers = (_$unionSerializers.toBuilder()
      ..addPlugin(StandardJsonPlugin()))
    .build();
