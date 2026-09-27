// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'model.dart';

// **************************************************************************
// BuiltValueGenerator
// **************************************************************************

Serializers _$serializers =
    (Serializers().toBuilder()
          ..add(Item.serializer)
          ..add(ItemNoNested.serializer)
          ..addBuilderFactory(
            const FullType(BuiltList, const [const FullType(String)]),
            () => ListBuilder<String>(),
          )
          ..addBuilderFactory(
            const FullType(BuiltList, const [const FullType(String)]),
            () => ListBuilder<String>(),
          ))
        .build();
Serializer<Item> _$itemSerializer = _$ItemSerializer();
Serializer<ItemNoNested> _$itemNoNestedSerializer = _$ItemNoNestedSerializer();

class _$ItemSerializer implements StructuredSerializer<Item> {
  @override
  final Iterable<Type> types = const [Item, _$Item];
  @override
  final String wireName = 'Item';

  @override
  Iterable<Object?> serialize(
    Serializers serializers,
    Item object, {
    FullType specifiedType = FullType.unspecified,
  }) {
    final result = <Object?>[
      'id',
      serializers.serialize(object.id, specifiedType: const FullType(int)),
      'tags',
      serializers.serialize(
        object.tags,
        specifiedType: const FullType(BuiltList, const [
          const FullType(String),
        ]),
      ),
    ];

    return result;
  }

  @override
  Item deserialize(
    Serializers serializers,
    Iterable<Object?> serialized, {
    FullType specifiedType = FullType.unspecified,
  }) {
    final result = ItemBuilder();

    final iterator = serialized.iterator;
    while (iterator.moveNext()) {
      final key = iterator.current! as String;
      iterator.moveNext();
      final Object? value = iterator.current;
      switch (key) {
        case 'id':
          result.id =
              serializers.deserialize(
                    value,
                    specifiedType: const FullType(int),
                  )!
                  as int;
          break;
        case 'tags':
          result.tags.replace(
            serializers.deserialize(
                  value,
                  specifiedType: const FullType(BuiltList, const [
                    const FullType(String),
                  ]),
                )!
                as BuiltList<Object?>,
          );
          break;
      }
    }

    return result.build();
  }
}

class _$ItemNoNestedSerializer implements StructuredSerializer<ItemNoNested> {
  @override
  final Iterable<Type> types = const [ItemNoNested, _$ItemNoNested];
  @override
  final String wireName = 'ItemNoNested';

  @override
  Iterable<Object?> serialize(
    Serializers serializers,
    ItemNoNested object, {
    FullType specifiedType = FullType.unspecified,
  }) {
    final result = <Object?>[
      'id',
      serializers.serialize(object.id, specifiedType: const FullType(int)),
      'tags',
      serializers.serialize(
        object.tags,
        specifiedType: const FullType(BuiltList, const [
          const FullType(String),
        ]),
      ),
    ];

    return result;
  }

  @override
  ItemNoNested deserialize(
    Serializers serializers,
    Iterable<Object?> serialized, {
    FullType specifiedType = FullType.unspecified,
  }) {
    final result = ItemNoNestedBuilder();

    final iterator = serialized.iterator;
    while (iterator.moveNext()) {
      final key = iterator.current! as String;
      iterator.moveNext();
      final Object? value = iterator.current;
      switch (key) {
        case 'id':
          result.id =
              serializers.deserialize(
                    value,
                    specifiedType: const FullType(int),
                  )!
                  as int;
          break;
        case 'tags':
          result.tags =
              serializers.deserialize(
                    value,
                    specifiedType: const FullType(BuiltList, const [
                      const FullType(String),
                    ]),
                  )!
                  as BuiltList<String>;
          break;
      }
    }

    return result.build();
  }
}

class _$Item extends Item {
  @override
  final int id;
  @override
  final BuiltList<String> tags;

  factory _$Item([void Function(ItemBuilder)? updates]) =>
      (ItemBuilder()..update(updates))._build();

  _$Item._({required this.id, required this.tags}) : super._();
  @override
  Item rebuild(void Function(ItemBuilder) updates) =>
      (toBuilder()..update(updates)).build();

  @override
  ItemBuilder toBuilder() => ItemBuilder()..replace(this);

  @override
  bool operator ==(Object other) {
    if (identical(other, this)) return true;
    return other is Item && id == other.id && tags == other.tags;
  }

  @override
  int get hashCode {
    var _$hash = 0;
    _$hash = $jc(_$hash, id.hashCode);
    _$hash = $jc(_$hash, tags.hashCode);
    _$hash = $jf(_$hash);
    return _$hash;
  }

  @override
  String toString() {
    return (newBuiltValueToStringHelper(r'Item')
          ..add('id', id)
          ..add('tags', tags))
        .toString();
  }
}

class ItemBuilder implements Builder<Item, ItemBuilder> {
  _$Item? _$v;

  int? _id;
  int? get id => _$this._id;
  set id(int? id) => _$this._id = id;

  ListBuilder<String>? _tags;
  ListBuilder<String> get tags => _$this._tags ??= ListBuilder<String>();
  set tags(ListBuilder<String>? tags) => _$this._tags = tags;

  ItemBuilder();

  ItemBuilder get _$this {
    final $v = _$v;
    if ($v != null) {
      _id = $v.id;
      _tags = $v.tags.toBuilder();
      _$v = null;
    }
    return this;
  }

  @override
  void replace(Item other) {
    _$v = other as _$Item;
  }

  @override
  void update(void Function(ItemBuilder)? updates) {
    if (updates != null) updates(this);
  }

  @override
  Item build() => _build();

  _$Item _build() {
    _$Item _$result;
    try {
      _$result =
          _$v ??
          _$Item._(
            id: BuiltValueNullFieldError.checkNotNull(id, r'Item', 'id'),
            tags: tags.build(),
          );
    } catch (_) {
      late String _$failedField;
      try {
        _$failedField = 'tags';
        tags.build();
      } catch (e) {
        throw BuiltValueNestedFieldError(r'Item', _$failedField, e.toString());
      }
      rethrow;
    }
    replace(_$result);
    return _$result;
  }
}

class _$ItemNoNested extends ItemNoNested {
  @override
  final int id;
  @override
  final BuiltList<String> tags;

  factory _$ItemNoNested([void Function(ItemNoNestedBuilder)? updates]) =>
      (ItemNoNestedBuilder()..update(updates))._build();

  _$ItemNoNested._({required this.id, required this.tags}) : super._();
  @override
  ItemNoNested rebuild(void Function(ItemNoNestedBuilder) updates) =>
      (toBuilder()..update(updates)).build();

  @override
  ItemNoNestedBuilder toBuilder() => ItemNoNestedBuilder()..replace(this);

  @override
  bool operator ==(Object other) {
    if (identical(other, this)) return true;
    return other is ItemNoNested && id == other.id && tags == other.tags;
  }

  @override
  int get hashCode {
    var _$hash = 0;
    _$hash = $jc(_$hash, id.hashCode);
    _$hash = $jc(_$hash, tags.hashCode);
    _$hash = $jf(_$hash);
    return _$hash;
  }

  @override
  String toString() {
    return (newBuiltValueToStringHelper(r'ItemNoNested')
          ..add('id', id)
          ..add('tags', tags))
        .toString();
  }
}

class ItemNoNestedBuilder
    implements Builder<ItemNoNested, ItemNoNestedBuilder> {
  _$ItemNoNested? _$v;

  int? _id;
  int? get id => _$this._id;
  set id(int? id) => _$this._id = id;

  BuiltList<String>? _tags;
  BuiltList<String>? get tags => _$this._tags;
  set tags(BuiltList<String>? tags) => _$this._tags = tags;

  ItemNoNestedBuilder();

  ItemNoNestedBuilder get _$this {
    final $v = _$v;
    if ($v != null) {
      _id = $v.id;
      _tags = $v.tags;
      _$v = null;
    }
    return this;
  }

  @override
  void replace(ItemNoNested other) {
    _$v = other as _$ItemNoNested;
  }

  @override
  void update(void Function(ItemNoNestedBuilder)? updates) {
    if (updates != null) updates(this);
  }

  @override
  ItemNoNested build() => _build();

  _$ItemNoNested _build() {
    final _$result =
        _$v ??
        _$ItemNoNested._(
          id: BuiltValueNullFieldError.checkNotNull(id, r'ItemNoNested', 'id'),
          tags: BuiltValueNullFieldError.checkNotNull(
            tags,
            r'ItemNoNested',
            'tags',
          ),
        );
    replace(_$result);
    return _$result;
  }
}

// ignore_for_file: deprecated_member_use_from_same_package,type=lint
