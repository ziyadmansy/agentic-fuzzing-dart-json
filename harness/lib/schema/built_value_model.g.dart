// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'built_value_model.dart';

// **************************************************************************
// BuiltValueGenerator
// **************************************************************************

const BvStatus _$active = const BvStatus._('active');
const BvStatus _$inactive = const BvStatus._('inactive');
const BvStatus _$unknown = const BvStatus._('unknown');

BvStatus _$bvStatusValueOf(String name) {
  switch (name) {
    case 'active':
      return _$active;
    case 'inactive':
      return _$inactive;
    case 'unknown':
      return _$unknown;
    default:
      throw ArgumentError(name);
  }
}

final BuiltSet<BvStatus> _$bvStatusValues = BuiltSet<BvStatus>(const <BvStatus>[
  _$active,
  _$inactive,
  _$unknown,
]);

Serializer<BvStatus> _$bvStatusSerializer = _$BvStatusSerializer();
Serializer<BvRecord> _$bvRecordSerializer = _$BvRecordSerializer();

class _$BvStatusSerializer implements PrimitiveSerializer<BvStatus> {
  @override
  final Iterable<Type> types = const <Type>[BvStatus];
  @override
  final String wireName = 'BvStatus';

  @override
  Object serialize(
    Serializers serializers,
    BvStatus object, {
    FullType specifiedType = FullType.unspecified,
  }) => object.name;

  @override
  BvStatus deserialize(
    Serializers serializers,
    Object serialized, {
    FullType specifiedType = FullType.unspecified,
  }) => BvStatus.valueOf(serialized as String);
}

class _$BvRecordSerializer implements StructuredSerializer<BvRecord> {
  @override
  final Iterable<Type> types = const [BvRecord, _$BvRecord];
  @override
  final String wireName = 'BvRecord';

  @override
  Iterable<Object?> serialize(
    Serializers serializers,
    BvRecord object, {
    FullType specifiedType = FullType.unspecified,
  }) {
    final result = <Object?>[
      'id',
      serializers.serialize(object.id, specifiedType: const FullType(int)),
      'amount',
      serializers.serialize(
        object.amount,
        specifiedType: const FullType(String),
      ),
      'status',
      serializers.serialize(
        object.status,
        specifiedType: const FullType(BvStatus),
      ),
      'tags',
      serializers.serialize(
        object.tags,
        specifiedType: const FullType(BuiltList, const [
          const FullType(String),
        ]),
      ),
    ];
    Object? value;
    value = object.name;
    if (value != null) {
      result
        ..add('name')
        ..add(
          serializers.serialize(value, specifiedType: const FullType(String)),
        );
    }
    value = object.child;
    if (value != null) {
      result
        ..add('child')
        ..add(
          serializers.serialize(value, specifiedType: const FullType(BvRecord)),
        );
    }
    return result;
  }

  @override
  BvRecord deserialize(
    Serializers serializers,
    Iterable<Object?> serialized, {
    FullType specifiedType = FullType.unspecified,
  }) {
    final result = BvRecordBuilder();

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
        case 'amount':
          result.amount =
              serializers.deserialize(
                    value,
                    specifiedType: const FullType(String),
                  )!
                  as String;
          break;
        case 'name':
          result.name =
              serializers.deserialize(
                    value,
                    specifiedType: const FullType(String),
                  )
                  as String?;
          break;
        case 'status':
          result.status =
              serializers.deserialize(
                    value,
                    specifiedType: const FullType(BvStatus),
                  )!
                  as BvStatus;
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
        case 'child':
          result.child.replace(
            serializers.deserialize(
                  value,
                  specifiedType: const FullType(BvRecord),
                )!
                as BvRecord,
          );
          break;
      }
    }

    return result.build();
  }
}

class _$BvRecord extends BvRecord {
  @override
  final int id;
  @override
  final String amount;
  @override
  final String? name;
  @override
  final BvStatus status;
  @override
  final BuiltList<String> tags;
  @override
  final BvRecord? child;

  factory _$BvRecord([void Function(BvRecordBuilder)? updates]) =>
      (BvRecordBuilder()..update(updates))._build();

  _$BvRecord._({
    required this.id,
    required this.amount,
    this.name,
    required this.status,
    required this.tags,
    this.child,
  }) : super._();
  @override
  BvRecord rebuild(void Function(BvRecordBuilder) updates) =>
      (toBuilder()..update(updates)).build();

  @override
  BvRecordBuilder toBuilder() => BvRecordBuilder()..replace(this);

  @override
  bool operator ==(Object other) {
    if (identical(other, this)) return true;
    return other is BvRecord &&
        id == other.id &&
        amount == other.amount &&
        name == other.name &&
        status == other.status &&
        tags == other.tags &&
        child == other.child;
  }

  @override
  int get hashCode {
    var _$hash = 0;
    _$hash = $jc(_$hash, id.hashCode);
    _$hash = $jc(_$hash, amount.hashCode);
    _$hash = $jc(_$hash, name.hashCode);
    _$hash = $jc(_$hash, status.hashCode);
    _$hash = $jc(_$hash, tags.hashCode);
    _$hash = $jc(_$hash, child.hashCode);
    _$hash = $jf(_$hash);
    return _$hash;
  }

  @override
  String toString() {
    return (newBuiltValueToStringHelper(r'BvRecord')
          ..add('id', id)
          ..add('amount', amount)
          ..add('name', name)
          ..add('status', status)
          ..add('tags', tags)
          ..add('child', child))
        .toString();
  }
}

class BvRecordBuilder implements Builder<BvRecord, BvRecordBuilder> {
  _$BvRecord? _$v;

  int? _id;
  int? get id => _$this._id;
  set id(int? id) => _$this._id = id;

  String? _amount;
  String? get amount => _$this._amount;
  set amount(String? amount) => _$this._amount = amount;

  String? _name;
  String? get name => _$this._name;
  set name(String? name) => _$this._name = name;

  BvStatus? _status;
  BvStatus? get status => _$this._status;
  set status(BvStatus? status) => _$this._status = status;

  ListBuilder<String>? _tags;
  ListBuilder<String> get tags => _$this._tags ??= ListBuilder<String>();
  set tags(ListBuilder<String>? tags) => _$this._tags = tags;

  BvRecordBuilder? _child;
  BvRecordBuilder get child => _$this._child ??= BvRecordBuilder();
  set child(BvRecordBuilder? child) => _$this._child = child;

  BvRecordBuilder();

  BvRecordBuilder get _$this {
    final $v = _$v;
    if ($v != null) {
      _id = $v.id;
      _amount = $v.amount;
      _name = $v.name;
      _status = $v.status;
      _tags = $v.tags.toBuilder();
      _child = $v.child?.toBuilder();
      _$v = null;
    }
    return this;
  }

  @override
  void replace(BvRecord other) {
    _$v = other as _$BvRecord;
  }

  @override
  void update(void Function(BvRecordBuilder)? updates) {
    if (updates != null) updates(this);
  }

  @override
  BvRecord build() => _build();

  _$BvRecord _build() {
    _$BvRecord _$result;
    try {
      _$result =
          _$v ??
          _$BvRecord._(
            id: BuiltValueNullFieldError.checkNotNull(id, r'BvRecord', 'id'),
            amount: BuiltValueNullFieldError.checkNotNull(
              amount,
              r'BvRecord',
              'amount',
            ),
            name: name,
            status: BuiltValueNullFieldError.checkNotNull(
              status,
              r'BvRecord',
              'status',
            ),
            tags: tags.build(),
            child: _child?.build(),
          );
    } catch (_) {
      late String _$failedField;
      try {
        _$failedField = 'tags';
        tags.build();
        _$failedField = 'child';
        _child?.build();
      } catch (e) {
        throw BuiltValueNestedFieldError(
          r'BvRecord',
          _$failedField,
          e.toString(),
        );
      }
      rethrow;
    }
    replace(_$result);
    return _$result;
  }
}

// ignore_for_file: deprecated_member_use_from_same_package,type=lint
