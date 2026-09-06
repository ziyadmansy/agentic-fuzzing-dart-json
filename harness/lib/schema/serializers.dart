// Central built_value Serializers registry (built_value convention: one
// file, one @SerializersFor list, generated once).

import 'package:built_collection/built_collection.dart';
import 'package:built_value/serializer.dart';
import 'package:built_value/standard_json_plugin.dart';

import 'built_value_model.dart';

part 'serializers.g.dart';

@SerializersFor([BvRecord])
final Serializers serializers = (_$serializers.toBuilder()
      ..addPlugin(StandardJsonPlugin()))
    .build();
