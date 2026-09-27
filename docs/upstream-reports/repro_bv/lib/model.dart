import 'package:built_collection/built_collection.dart';
import 'package:built_value/built_value.dart';
import 'package:built_value/serializer.dart';
import 'package:built_value/standard_json_plugin.dart';
part 'model.g.dart';

abstract class Item implements Built<Item, ItemBuilder> {
  static Serializer<Item> get serializer => _$itemSerializer;
  int get id;
  BuiltList<String> get tags;
  Item._();
  factory Item([void Function(ItemBuilder) updates]) = _$Item;
}

@BuiltValue(nestedBuilders: false)
abstract class ItemNoNested implements Built<ItemNoNested, ItemNoNestedBuilder> {
  static Serializer<ItemNoNested> get serializer => _$itemNoNestedSerializer;
  int get id;
  BuiltList<String> get tags;
  ItemNoNested._();
  factory ItemNoNested([void Function(ItemNoNestedBuilder) updates]) = _$ItemNoNested;
}

@SerializersFor([Item, ItemNoNested])
final Serializers serializers =
    (_$serializers.toBuilder()..addPlugin(StandardJsonPlugin())).build();
