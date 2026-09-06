// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'union_built_value.dart';

// **************************************************************************
// BuiltValueGenerator
// **************************************************************************

Serializer<BvTextPayload> _$bvTextPayloadSerializer =
    _$BvTextPayloadSerializer();
Serializer<BvNumberPayload> _$bvNumberPayloadSerializer =
    _$BvNumberPayloadSerializer();

class _$BvTextPayloadSerializer implements StructuredSerializer<BvTextPayload> {
  @override
  final Iterable<Type> types = const [BvTextPayload, _$BvTextPayload];
  @override
  final String wireName = 'BvTextPayload';

  @override
  Iterable<Object?> serialize(
    Serializers serializers,
    BvTextPayload object, {
    FullType specifiedType = FullType.unspecified,
  }) {
    final result = <Object?>[
      'value',
      serializers.serialize(
        object.value,
        specifiedType: const FullType(String),
      ),
    ];

    return result;
  }

  @override
  BvTextPayload deserialize(
    Serializers serializers,
    Iterable<Object?> serialized, {
    FullType specifiedType = FullType.unspecified,
  }) {
    final result = BvTextPayloadBuilder();

    final iterator = serialized.iterator;
    while (iterator.moveNext()) {
      final key = iterator.current! as String;
      iterator.moveNext();
      final Object? value = iterator.current;
      switch (key) {
        case 'value':
          result.value =
              serializers.deserialize(
                    value,
                    specifiedType: const FullType(String),
                  )!
                  as String;
          break;
      }
    }

    return result.build();
  }
}

class _$BvNumberPayloadSerializer
    implements StructuredSerializer<BvNumberPayload> {
  @override
  final Iterable<Type> types = const [BvNumberPayload, _$BvNumberPayload];
  @override
  final String wireName = 'BvNumberPayload';

  @override
  Iterable<Object?> serialize(
    Serializers serializers,
    BvNumberPayload object, {
    FullType specifiedType = FullType.unspecified,
  }) {
    final result = <Object?>[
      'value',
      serializers.serialize(object.value, specifiedType: const FullType(num)),
    ];

    return result;
  }

  @override
  BvNumberPayload deserialize(
    Serializers serializers,
    Iterable<Object?> serialized, {
    FullType specifiedType = FullType.unspecified,
  }) {
    final result = BvNumberPayloadBuilder();

    final iterator = serialized.iterator;
    while (iterator.moveNext()) {
      final key = iterator.current! as String;
      iterator.moveNext();
      final Object? value = iterator.current;
      switch (key) {
        case 'value':
          result.value =
              serializers.deserialize(
                    value,
                    specifiedType: const FullType(num),
                  )!
                  as num;
          break;
      }
    }

    return result.build();
  }
}

class _$BvTextPayload extends BvTextPayload {
  @override
  final String value;

  factory _$BvTextPayload([void Function(BvTextPayloadBuilder)? updates]) =>
      (BvTextPayloadBuilder()..update(updates))._build();

  _$BvTextPayload._({required this.value}) : super._();
  @override
  BvTextPayload rebuild(void Function(BvTextPayloadBuilder) updates) =>
      (toBuilder()..update(updates)).build();

  @override
  BvTextPayloadBuilder toBuilder() => BvTextPayloadBuilder()..replace(this);

  @override
  bool operator ==(Object other) {
    if (identical(other, this)) return true;
    return other is BvTextPayload && value == other.value;
  }

  @override
  int get hashCode {
    var _$hash = 0;
    _$hash = $jc(_$hash, value.hashCode);
    _$hash = $jf(_$hash);
    return _$hash;
  }

  @override
  String toString() {
    return (newBuiltValueToStringHelper(
      r'BvTextPayload',
    )..add('value', value)).toString();
  }
}

class BvTextPayloadBuilder
    implements Builder<BvTextPayload, BvTextPayloadBuilder> {
  _$BvTextPayload? _$v;

  String? _value;
  String? get value => _$this._value;
  set value(String? value) => _$this._value = value;

  BvTextPayloadBuilder();

  BvTextPayloadBuilder get _$this {
    final $v = _$v;
    if ($v != null) {
      _value = $v.value;
      _$v = null;
    }
    return this;
  }

  @override
  void replace(BvTextPayload other) {
    _$v = other as _$BvTextPayload;
  }

  @override
  void update(void Function(BvTextPayloadBuilder)? updates) {
    if (updates != null) updates(this);
  }

  @override
  BvTextPayload build() => _build();

  _$BvTextPayload _build() {
    final _$result =
        _$v ??
        _$BvTextPayload._(
          value: BuiltValueNullFieldError.checkNotNull(
            value,
            r'BvTextPayload',
            'value',
          ),
        );
    replace(_$result);
    return _$result;
  }
}

class _$BvNumberPayload extends BvNumberPayload {
  @override
  final num value;

  factory _$BvNumberPayload([void Function(BvNumberPayloadBuilder)? updates]) =>
      (BvNumberPayloadBuilder()..update(updates))._build();

  _$BvNumberPayload._({required this.value}) : super._();
  @override
  BvNumberPayload rebuild(void Function(BvNumberPayloadBuilder) updates) =>
      (toBuilder()..update(updates)).build();

  @override
  BvNumberPayloadBuilder toBuilder() => BvNumberPayloadBuilder()..replace(this);

  @override
  bool operator ==(Object other) {
    if (identical(other, this)) return true;
    return other is BvNumberPayload && value == other.value;
  }

  @override
  int get hashCode {
    var _$hash = 0;
    _$hash = $jc(_$hash, value.hashCode);
    _$hash = $jf(_$hash);
    return _$hash;
  }

  @override
  String toString() {
    return (newBuiltValueToStringHelper(
      r'BvNumberPayload',
    )..add('value', value)).toString();
  }
}

class BvNumberPayloadBuilder
    implements Builder<BvNumberPayload, BvNumberPayloadBuilder> {
  _$BvNumberPayload? _$v;

  num? _value;
  num? get value => _$this._value;
  set value(num? value) => _$this._value = value;

  BvNumberPayloadBuilder();

  BvNumberPayloadBuilder get _$this {
    final $v = _$v;
    if ($v != null) {
      _value = $v.value;
      _$v = null;
    }
    return this;
  }

  @override
  void replace(BvNumberPayload other) {
    _$v = other as _$BvNumberPayload;
  }

  @override
  void update(void Function(BvNumberPayloadBuilder)? updates) {
    if (updates != null) updates(this);
  }

  @override
  BvNumberPayload build() => _build();

  _$BvNumberPayload _build() {
    final _$result =
        _$v ??
        _$BvNumberPayload._(
          value: BuiltValueNullFieldError.checkNotNull(
            value,
            r'BvNumberPayload',
            'value',
          ),
        );
    replace(_$result);
    return _$result;
  }
}

// ignore_for_file: deprecated_member_use_from_same_package,type=lint
