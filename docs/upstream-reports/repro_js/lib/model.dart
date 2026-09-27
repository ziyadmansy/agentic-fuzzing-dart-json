import 'package:json_annotation/json_annotation.dart';
part 'model.g.dart';

@JsonSerializable(createToJson: false)
class Item {
  final int id;
  Item({required this.id});
  factory Item.fromJson(Map<String, dynamic> json) => _$ItemFromJson(json);
}
