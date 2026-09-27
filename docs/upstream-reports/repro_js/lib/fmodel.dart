import 'package:freezed_annotation/freezed_annotation.dart';
part 'fmodel.freezed.dart';
part 'fmodel.g.dart';

@freezed
abstract class FItem with _$FItem {
  const factory FItem({required int id}) = _FItem;
  factory FItem.fromJson(Map<String, dynamic> json) => _$FItemFromJson(json);
}
