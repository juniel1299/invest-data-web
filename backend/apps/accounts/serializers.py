from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "password", "display_currency"]

    def validate(self, attrs):
        validate_password(attrs["password"], User(email=attrs["email"]))
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "display_currency",
            "ntfy_topic",
            "notify_follow",
            "notify_overlap",
            "notify_insider",
            "daily_email",
            "date_joined",
        ]
        read_only_fields = ["id", "email", "date_joined"]
