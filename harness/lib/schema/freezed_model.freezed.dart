// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint, type=warning, deprecated_member_use, deprecated_member_use_from_same_package
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'freezed_model.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// dart format off
T _$identity<T>(T value) => value;

/// @nodoc
mixin _$FreezedRecord {

 int get id; String get amount; String? get name; FreezedStatus get status; List<String> get tags; FreezedRecord? get child;
/// Create a copy of FreezedRecord
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$FreezedRecordCopyWith<FreezedRecord> get copyWith => _$FreezedRecordCopyWithImpl<FreezedRecord>(this as FreezedRecord, _$identity);

  /// Serializes this FreezedRecord to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  final _this = this as FreezedRecord;
  return identical(this, other) || (other.runtimeType == runtimeType&&other is FreezedRecord&&(identical(other.id, _this.id) || other.id == _this.id)&&(identical(other.amount, _this.amount) || other.amount == _this.amount)&&(identical(other.name, _this.name) || other.name == _this.name)&&(identical(other.status, _this.status) || other.status == _this.status)&&const DeepCollectionEquality().equals(other.tags, _this.tags)&&(identical(other.child, _this.child) || other.child == _this.child));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode {
  final _this = this as FreezedRecord;
  return Object.hash(runtimeType,_this.id,_this.amount,_this.name,_this.status,const DeepCollectionEquality().hash(_this.tags),_this.child);
}

@override
String toString() {
  final _this = this as FreezedRecord;
  return 'FreezedRecord(id: ${_this.id}, amount: ${_this.amount}, name: ${_this.name}, status: ${_this.status}, tags: ${_this.tags}, child: ${_this.child})';
}


}

/// @nodoc
abstract mixin class $FreezedRecordCopyWith<$Res>  {
  factory $FreezedRecordCopyWith(FreezedRecord value, $Res Function(FreezedRecord) _then) = _$FreezedRecordCopyWithImpl;
@useResult
$Res call({
 int id, String amount, String? name, FreezedStatus status, List<String> tags, FreezedRecord? child
});


$FreezedRecordCopyWith<$Res>? get child;

}
/// @nodoc
class _$FreezedRecordCopyWithImpl<$Res>
    implements $FreezedRecordCopyWith<$Res> {
  _$FreezedRecordCopyWithImpl(this._self, this._then);

  final FreezedRecord _self;
  final $Res Function(FreezedRecord) _then;

/// Create a copy of FreezedRecord
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') @override $Res call({Object? id = null,Object? amount = null,Object? name = freezed,Object? status = null,Object? tags = null,Object? child = freezed,}) {
  return _then(FreezedRecord(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as int,amount: null == amount ? _self.amount : amount // ignore: cast_nullable_to_non_nullable
as String,name: freezed == name ? _self.name : name // ignore: cast_nullable_to_non_nullable
as String?,status: null == status ? _self.status : status // ignore: cast_nullable_to_non_nullable
as FreezedStatus,tags: null == tags ? _self.tags : tags // ignore: cast_nullable_to_non_nullable
as List<String>,child: freezed == child ? _self.child : child // ignore: cast_nullable_to_non_nullable
as FreezedRecord?,
  ));
}
/// Create a copy of FreezedRecord
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$FreezedRecordCopyWith<$Res>? get child {
    if (_self.child == null) {
    return null;
  }

  return $FreezedRecordCopyWith<$Res>(_self.child!, (value) {
    return _then(_self.copyWith(child: value));
  });
}
}


/// Adds pattern-matching-related methods to [FreezedRecord].
extension FreezedRecordPatterns on FreezedRecord {
/// A variant of `map` that fallback to returning `orElse`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeMap<TResult extends Object?>(TResult Function( _FreezedRecord value)?  $default,{required TResult orElse(),}){
final _that = this;
switch (_that) {
case _FreezedRecord() when $default != null:
return $default(_that);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// Callbacks receives the raw object, upcasted.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case final Subclass2 value:
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult map<TResult extends Object?>(TResult Function( _FreezedRecord value)  $default,){
final _that = this;
switch (_that) {
case _FreezedRecord():
return $default(_that);case _:
  throw StateError('Unexpected subclass');

}
}
/// A variant of `map` that fallback to returning `null`.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case final Subclass value:
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>(TResult? Function( _FreezedRecord value)?  $default,){
final _that = this;
switch (_that) {
case _FreezedRecord() when $default != null:
return $default(_that);case _:
  return null;

}
}
/// A variant of `when` that fallback to an `orElse` callback.
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return orElse();
/// }
/// ```

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>(TResult Function( int id,  String amount,  String? name,  FreezedStatus status,  List<String> tags,  FreezedRecord? child)?  $default,{required TResult orElse(),}) {final _that = this;
switch (_that) {
case _FreezedRecord() when $default != null:
return $default(_that.id,_that.amount,_that.name,_that.status,_that.tags,_that.child);case _:
  return orElse();

}
}
/// A `switch`-like method, using callbacks.
///
/// As opposed to `map`, this offers destructuring.
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case Subclass2(:final field2):
///     return ...;
/// }
/// ```

@optionalTypeArgs TResult when<TResult extends Object?>(TResult Function( int id,  String amount,  String? name,  FreezedStatus status,  List<String> tags,  FreezedRecord? child)  $default,) {final _that = this;
switch (_that) {
case _FreezedRecord():
return $default(_that.id,_that.amount,_that.name,_that.status,_that.tags,_that.child);case _:
  throw StateError('Unexpected subclass');

}
}
/// A variant of `when` that fallback to returning `null`
///
/// It is equivalent to doing:
/// ```dart
/// switch (sealedClass) {
///   case Subclass(:final field):
///     return ...;
///   case _:
///     return null;
/// }
/// ```

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>(TResult? Function( int id,  String amount,  String? name,  FreezedStatus status,  List<String> tags,  FreezedRecord? child)?  $default,) {final _that = this;
switch (_that) {
case _FreezedRecord() when $default != null:
return $default(_that.id,_that.amount,_that.name,_that.status,_that.tags,_that.child);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class _FreezedRecord implements FreezedRecord {
  const _FreezedRecord({required this.id, required this.amount, required this.name, required this.status, required  List<String> tags, required this.child}): _tags = tags;
  factory _FreezedRecord.fromJson(Map<String, dynamic> json) => _$FreezedRecordFromJson(json);

@override final  int id;
@override final  String amount;
@override final  String? name;
@override final  FreezedStatus status;
 final  List<String> _tags;
@override List<String> get tags {
  if (_tags is EqualUnmodifiableListView) return _tags;
  // ignore: implicit_dynamic_type
  return EqualUnmodifiableListView(_tags);
}

@override final  FreezedRecord? child;

/// Create a copy of FreezedRecord
/// with the given fields replaced by the non-null parameter values.
@override @JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
_$FreezedRecordCopyWith<_FreezedRecord> get copyWith => __$FreezedRecordCopyWithImpl<_FreezedRecord>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$FreezedRecordToJson(this, );
}

@override
bool operator ==(Object other) {
    return identical(this, other) || (other.runtimeType == runtimeType&&other is _FreezedRecord&&(identical(other.id, id) || other.id == id)&&(identical(other.amount, amount) || other.amount == amount)&&(identical(other.name, name) || other.name == name)&&(identical(other.status, status) || other.status == status)&&const DeepCollectionEquality().equals(other.tags, _tags)&&(identical(other.child, child) || other.child == child));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode {
    return Object.hash(runtimeType,id,amount,name,status,const DeepCollectionEquality().hash(_tags),child);
}

@override
String toString() {
    return 'FreezedRecord(id: $id, amount: $amount, name: $name, status: $status, tags: $tags, child: $child)';
}


}

/// @nodoc
abstract mixin class _$FreezedRecordCopyWith<$Res> implements $FreezedRecordCopyWith<$Res> {
  factory _$FreezedRecordCopyWith(_FreezedRecord value, $Res Function(_FreezedRecord) _then) = __$FreezedRecordCopyWithImpl;
@override @useResult
$Res call({
 int id, String amount, String? name, FreezedStatus status, List<String> tags, FreezedRecord? child
});


@override $FreezedRecordCopyWith<$Res>? get child;

}
/// @nodoc
class __$FreezedRecordCopyWithImpl<$Res>
    implements _$FreezedRecordCopyWith<$Res> {
  __$FreezedRecordCopyWithImpl(this._self, this._then);

  final _FreezedRecord _self;
  final $Res Function(_FreezedRecord) _then;

/// Create a copy of FreezedRecord
/// with the given fields replaced by the non-null parameter values.
@override @pragma('vm:prefer-inline') $Res call({Object? id = null,Object? amount = null,Object? name = freezed,Object? status = null,Object? tags = null,Object? child = freezed,}) {
  return _then(_FreezedRecord(
id: null == id ? _self.id : id // ignore: cast_nullable_to_non_nullable
as int,amount: null == amount ? _self.amount : amount // ignore: cast_nullable_to_non_nullable
as String,name: freezed == name ? _self.name : name // ignore: cast_nullable_to_non_nullable
as String?,status: null == status ? _self.status : status // ignore: cast_nullable_to_non_nullable
as FreezedStatus,tags: null == tags ? _self._tags : tags // ignore: cast_nullable_to_non_nullable
as List<String>,child: freezed == child ? _self.child : child // ignore: cast_nullable_to_non_nullable
as FreezedRecord?,
  ));
}

/// Create a copy of FreezedRecord
/// with the given fields replaced by the non-null parameter values.
@override
@pragma('vm:prefer-inline')
$FreezedRecordCopyWith<$Res>? get child {
    if (_self.child == null) {
    return null;
  }

  return $FreezedRecordCopyWith<$Res>(_self.child!, (value) {
    return _then(_self.copyWith(child: value));
  });
}
}

// dart format on
