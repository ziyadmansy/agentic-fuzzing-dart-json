<!-- File at: https://github.com/google/built_value.dart/issues/new -->
<!-- Title: -->
# Deserializing a missing or `null` non-nullable `BuiltList` field silently produces an empty list

With default settings, a non-nullable `BuiltList<String>` field that is **missing** from the JSON, or **explicitly `null`**, deserializes to an empty list without an error. A non-nullable scalar field in the same class is correctly rejected in both cases:

| JSON input | Default | `@BuiltValue(nestedBuilders: false)` |
|---|---|---|
| `{"id": 1, "tags": ["a"]}` | `id=1, tags=[a]` | `id=1, tags=[a]` |
| `{"id": 1}` (tags missing) | `id=1, tags=[]` ⚠️ | throws `DeserializationError` |
| `{"id": 1, "tags": null}` | `id=1, tags=[]` ⚠️ | throws `DeserializationError` |
| `{"tags": ["a"]}` (id missing) | throws `DeserializationError` | throws `DeserializationError` |
| `{"id": null, "tags": ["a"]}` | throws `DeserializationError` | throws `DeserializationError` |

I understand where this comes from: nested builders are auto-created, so `ItemBuilder.tags` is never null, and `Item((b) => b..id = 1)` also builds with `tags=[]`. That makes sense for the builder API. For deserialization, though, the practical result is that a payload which clearly violates the declared type (`tags` is non-nullable and required) is accepted, and it's indistinguishable from a real empty list. For example, a backend that stops sending `tags`, or sends `null`, looks exactly like "no tags" to the app. It's also inconsistent with how the same class treats a missing or `null` `int`.

## Reproduction

Versions: Dart SDK 3.13.2 (macOS arm64), `built_value` 8.13.0, `built_value_generator` 8.13.0, `StandardJsonPlugin`.

```dart
abstract class Item implements Built<Item, ItemBuilder> {
  static Serializer<Item> get serializer => _$itemSerializer;
  int get id;
  BuiltList<String> get tags;
  Item._();
  factory Item([void Function(ItemBuilder) updates]) = _$Item;
}

@SerializersFor([Item])
final Serializers serializers =
    (_$serializers.toBuilder()..addPlugin(StandardJsonPlugin())).build();

void main() {
  print(serializers.deserializeWith(Item.serializer, jsonDecode('{"id": 1}')));
  // Item { id=1, tags=[], }   -- no error
  print(serializers.deserializeWith(Item.serializer, jsonDecode('{"id": 1, "tags": null}')));
  // Item { id=1, tags=[], }   -- no error
}
```

## Question / suggestion

Is this intended for deserialization? If so, it would help to document it, since serialization is where people expect missing/`null` required fields to be rejected, and the `nestedBuilders: false` workaround isn't obvious. If not, possible options:

1. The generated serializer could track whether each non-nullable nested-builder field was actually present (and non-null) in the input, and throw `DeserializationError` if not. Fields marked with a `@BuiltValueField` default/nullable would be exempt.
2. Alternatively, keep the default but reject an explicit `null` for a non-nullable collection field. This is the less ambiguous of the two cases, and it currently behaves differently from a scalar field.

## How this was found

This came up while differential-testing four Dart JSON deserialization approaches against each other (hand-written `dart:convert`, `json_serializable`, `freezed`, `built_value`). In a schema-aware fuzzing campaign, `built_value` was the only one that accepted documents with the list field removed. Write-up and data: https://doi.org/10.5281/zenodo.22555795

Happy to help with a PR if there's a preferred direction.
