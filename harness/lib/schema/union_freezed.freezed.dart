// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint, type=warning, deprecated_member_use, deprecated_member_use_from_same_package
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'union_freezed.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// GENERATED CODE - DO NOT MODIFY BY HAND
// dart format off
T _$identity<T>(T value) => value;
FreezedPayload _$FreezedPayloadFromJson(
  Map<String, dynamic> json
) {
        switch (json['type']) {
                  case 'text':
          return FreezedTextPayload.fromJson(
            json
          );
                case 'number':
          return FreezedNumberPayload.fromJson(
            json
          );
        
          default:
            throw CheckedFromJsonException(
  json,
  'type',
  'FreezedPayload',
  'Invalid union type "${json['type']}"!'
);
        }
      
}

/// @nodoc
mixin _$FreezedPayload {

 Object get value;

  /// Serializes this FreezedPayload to a JSON map.
  Map<String, dynamic> toJson();


@override
bool operator ==(Object other) {
  final _this = this as FreezedPayload;
  return identical(this, other) || (other.runtimeType == runtimeType&&other is FreezedPayload&&const DeepCollectionEquality().equals(other.value, _this.value));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode {
  final _this = this as FreezedPayload;
  return Object.hash(runtimeType,const DeepCollectionEquality().hash(_this.value));
}

@override
String toString() {
  final _this = this as FreezedPayload;
  return 'FreezedPayload(value: ${_this.value})';
}


}

/// @nodoc
class $FreezedPayloadCopyWith<$Res>  {
$FreezedPayloadCopyWith(FreezedPayload _, $Res Function(FreezedPayload) __);
}


/// Adds pattern-matching-related methods to [FreezedPayload].
extension FreezedPayloadPatterns on FreezedPayload {
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

@optionalTypeArgs TResult maybeMap<TResult extends Object?>({TResult Function( FreezedTextPayload value)?  text,TResult Function( FreezedNumberPayload value)?  number,required TResult orElse(),}){
final _that = this;
switch (_that) {
case FreezedTextPayload() when text != null:
return text(_that);case FreezedNumberPayload() when number != null:
return number(_that);case _:
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

@optionalTypeArgs TResult map<TResult extends Object?>({required TResult Function( FreezedTextPayload value)  text,required TResult Function( FreezedNumberPayload value)  number,}){
final _that = this;
switch (_that) {
case FreezedTextPayload():
return text(_that);case FreezedNumberPayload():
return number(_that);}
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

@optionalTypeArgs TResult? mapOrNull<TResult extends Object?>({TResult? Function( FreezedTextPayload value)?  text,TResult? Function( FreezedNumberPayload value)?  number,}){
final _that = this;
switch (_that) {
case FreezedTextPayload() when text != null:
return text(_that);case FreezedNumberPayload() when number != null:
return number(_that);case _:
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

@optionalTypeArgs TResult maybeWhen<TResult extends Object?>({TResult Function( String value)?  text,TResult Function( num value)?  number,required TResult orElse(),}) {final _that = this;
switch (_that) {
case FreezedTextPayload() when text != null:
return text(_that.value);case FreezedNumberPayload() when number != null:
return number(_that.value);case _:
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

@optionalTypeArgs TResult when<TResult extends Object?>({required TResult Function( String value)  text,required TResult Function( num value)  number,}) {final _that = this;
switch (_that) {
case FreezedTextPayload():
return text(_that.value);case FreezedNumberPayload():
return number(_that.value);}
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

@optionalTypeArgs TResult? whenOrNull<TResult extends Object?>({TResult? Function( String value)?  text,TResult? Function( num value)?  number,}) {final _that = this;
switch (_that) {
case FreezedTextPayload() when text != null:
return text(_that.value);case FreezedNumberPayload() when number != null:
return number(_that.value);case _:
  return null;

}
}

}

/// @nodoc
@JsonSerializable()

class FreezedTextPayload implements FreezedPayload {
  const FreezedTextPayload(this.value, { String? $type}): $type = $type ?? 'text';
  factory FreezedTextPayload.fromJson(Map<String, dynamic> json) => _$FreezedTextPayloadFromJson(json);

@override final  String value;

@JsonKey(name: 'type')
final String $type;


/// Create a copy of FreezedPayload
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$FreezedTextPayloadCopyWith<FreezedTextPayload> get copyWith => _$FreezedTextPayloadCopyWithImpl<FreezedTextPayload>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$FreezedTextPayloadToJson(this, );
}

@override
bool operator ==(Object other) {
    return identical(this, other) || (other.runtimeType == runtimeType&&other is FreezedTextPayload&&(identical(other.value, value) || other.value == value));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode {
    return Object.hash(runtimeType,value);
}

@override
String toString() {
    return 'FreezedPayload.text(value: $value)';
}


}

/// @nodoc
abstract mixin class $FreezedTextPayloadCopyWith<$Res> implements $FreezedPayloadCopyWith<$Res> {
  factory $FreezedTextPayloadCopyWith(FreezedTextPayload value, $Res Function(FreezedTextPayload) _then) = _$FreezedTextPayloadCopyWithImpl;
@useResult
$Res call({
 String value
});




}
/// @nodoc
class _$FreezedTextPayloadCopyWithImpl<$Res>
    implements $FreezedTextPayloadCopyWith<$Res> {
  _$FreezedTextPayloadCopyWithImpl(this._self, this._then);

  final FreezedTextPayload _self;
  final $Res Function(FreezedTextPayload) _then;

/// Create a copy of FreezedPayload
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') $Res call({Object? value = null,}) {
  return _then(FreezedTextPayload(
null == value ? _self.value : value // ignore: cast_nullable_to_non_nullable
as String,
  ));
}


}

/// @nodoc
@JsonSerializable()

class FreezedNumberPayload implements FreezedPayload {
  const FreezedNumberPayload(this.value, { String? $type}): $type = $type ?? 'number';
  factory FreezedNumberPayload.fromJson(Map<String, dynamic> json) => _$FreezedNumberPayloadFromJson(json);

@override final  num value;

@JsonKey(name: 'type')
final String $type;


/// Create a copy of FreezedPayload
/// with the given fields replaced by the non-null parameter values.
@JsonKey(includeFromJson: false, includeToJson: false)
@pragma('vm:prefer-inline')
$FreezedNumberPayloadCopyWith<FreezedNumberPayload> get copyWith => _$FreezedNumberPayloadCopyWithImpl<FreezedNumberPayload>(this, _$identity);

@override
Map<String, dynamic> toJson() {
  return _$FreezedNumberPayloadToJson(this, );
}

@override
bool operator ==(Object other) {
    return identical(this, other) || (other.runtimeType == runtimeType&&other is FreezedNumberPayload&&(identical(other.value, value) || other.value == value));
}

@JsonKey(includeFromJson: false, includeToJson: false)
@override
int get hashCode {
    return Object.hash(runtimeType,value);
}

@override
String toString() {
    return 'FreezedPayload.number(value: $value)';
}


}

/// @nodoc
abstract mixin class $FreezedNumberPayloadCopyWith<$Res> implements $FreezedPayloadCopyWith<$Res> {
  factory $FreezedNumberPayloadCopyWith(FreezedNumberPayload value, $Res Function(FreezedNumberPayload) _then) = _$FreezedNumberPayloadCopyWithImpl;
@useResult
$Res call({
 num value
});




}
/// @nodoc
class _$FreezedNumberPayloadCopyWithImpl<$Res>
    implements $FreezedNumberPayloadCopyWith<$Res> {
  _$FreezedNumberPayloadCopyWithImpl(this._self, this._then);

  final FreezedNumberPayload _self;
  final $Res Function(FreezedNumberPayload) _then;

/// Create a copy of FreezedPayload
/// with the given fields replaced by the non-null parameter values.
@pragma('vm:prefer-inline') $Res call({Object? value = null,}) {
  return _then(FreezedNumberPayload(
null == value ? _self.value : value // ignore: cast_nullable_to_non_nullable
as num,
  ));
}


}

// dart format on
