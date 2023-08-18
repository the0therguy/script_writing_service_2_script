from .models import *
from rest_framework import serializers

from .utils import token_validator


class ScriptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Script
        fields = '__all__'
        # read_only_fields = ['script_uuid', 'created_by', 'updated_on', 'created_on']


class StoryDocsSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoryDocs
        fields = '__all__'


class StoryDocsUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoryDocs
        exclude = ('story_docs_uuid', 'script',)


class ContributorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contributor
        fields = '__all__'
        # exclude = ('contributor_uuid', 'script',)


class ContributorUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contributor
        exclude = ('contributor_uuid', 'script',)


class SubStorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SubStory
        fields = '__all__'


class SubStoryUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubStory
        exclude = ('sub_story_uuid', 'story_docs')


class ActSerializer(serializers.ModelSerializer):
    class Meta:
        model = Act
        fields = '__all__'


class ActUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Act
        exclude = ('act_uuid', 'script')


class SceneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scene
        fields = '__all__'


class SceneUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scene
        exclude = ('scene_uuid', 'act')


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = '__all__'


class LocationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        exclude = ('location_uuid', 'scene', 'location_type')


class ArcheTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArcheType
        fields = '__all__'


class ArcheTypeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArcheType
        fields = ['title', 'slug']
