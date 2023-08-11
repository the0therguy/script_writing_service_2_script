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
