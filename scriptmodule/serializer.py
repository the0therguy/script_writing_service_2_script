from .models import *
from rest_framework import serializers

from .utils import token_validator


class ScriptFolderSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScriptFolder
        fields = "__all__"


class ScriptFolderUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScriptFolder
        fields = ['title']


class ScriptSerializer(serializers.ModelSerializer):
    script_folder_name = serializers.CharField(source='script_folder.title', read_only=True)

    class Meta:
        model = Script
        fields = '__all__'
        # read_only_fields = ['script_uuid', 'created_by', 'updated_on', 'created_on']


class ScriptUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Script
        fields = '__all__'
        read_only_fields = ('created_by', 'script_uuid', 'created_on', 'script_folder', 'updated_on', 'parent')


class StoryDocsSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoryDocs
        fields = '__all__'


class StoryDocsUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoryDocs
        fields = '__all__'
        read_only_fields = ('story_docs_uuid', 'script',)


class ContributorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contributor
        fields = '__all__'
        # exclude = ('contributor_uuid', 'script',)


class ContributorUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contributor
        fields = '__all__'
        read_only_fields = ('contributor_uuid', 'script', 'contributor', 'contributor_email')


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = "__all__"


class CommentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = '__all__'
        read_only_fields = ("comment_uuid", 'created_on', 'created_by', 'script')


class SubStorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SubStory
        fields = '__all__'


class SubStoryUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubStory
        fields = '__all__'
        read_only_fields = ('sub_story_uuid', 'story_docs', 'sub_story_no')


class ActSerializer(serializers.ModelSerializer):
    class Meta:
        model = Act
        fields = '__all__'


class ActUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Act
        fields = '__all__'
        read_only_fields = ('act_uuid', 'script', 'page_no')


class SceneSerializer(serializers.ModelSerializer):
    comment = CommentSerializer(required=False, read_only=True)

    class Meta:
        model = Scene
        fields = '__all__'


class SceneUpdateSerializer(serializers.ModelSerializer):
    comment = CommentSerializer(required=False, read_only=True)

    class Meta:
        model = Scene
        fields = '__all__'
        read_only_fields = ('scene_uuid', 'act')


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = '__all__'


class LocationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = '__all__'
        read_only_fields = ('location_uuid', 'script')


class ArcheTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArcheType
        fields = '__all__'


class ArcheTypeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArcheType
        fields = ['title', 'slug']


class CharacterSceneSerializer(serializers.ModelSerializer):
    scene_page_no = serializers.IntegerField(source='scene.page_no', read_only=True)
    scene_header = serializers.CharField(source='scene.scene_header', read_only=True)

    class Meta:
        model = CharacterScene
        fields = '__all__'


class CharacterSerializer(serializers.ModelSerializer):
    archetype_title = serializers.CharField(source='archetype.title', read_only=True)
    character_scene = CharacterSceneSerializer(many=True, read_only=True, source='characterscene_set')

    class Meta:
        model = Character
        fields = '__all__'


class CharacterUpdateSerializer(serializers.ModelSerializer):
    archetype_title = serializers.CharField(source='archetype.title', read_only=True)
    character_scene = CharacterSceneSerializer(many=True, read_only=True, source='characterscene_set')

    class Meta:
        model = Character
        fields = '__all__'
        read_only_fields = ('character_uuid', 'script', 'image')


class DialogueSerializer(serializers.ModelSerializer):
    character_name = serializers.SerializerMethodField()
    dual_character_name = serializers.SerializerMethodField()
    comment = CommentSerializer(required=False, read_only=True)

    class Meta:
        model = Dialogue
        fields = '__all__'

    def get_character_name(self, obj):
        character = obj.character
        return getattr(character, 'name', '') if character else ''

    def get_dual_character_name(self, obj):
        dual_character = obj.dual_character
        return getattr(dual_character, 'name', '') if dual_character else ''


class DialogueUpdateSerializer(serializers.ModelSerializer):
    character_name = serializers.SerializerMethodField()
    dual_character_name = serializers.SerializerMethodField()
    comment = CommentSerializer(required=False, read_only=True)

    class Meta:
        model = Dialogue
        fields = '__all__'
        read_only_fields = ('dialogue_uuid', 'scene', 'script')

    def get_character_name(self, obj):
        character = obj.character
        return getattr(character, 'name', '') if character else ''

    def get_dual_character_name(self, obj):
        dual_character = obj.dual_character
        return getattr(dual_character, 'name', '') if dual_character else ''


class ScriptNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScriptNotification
        fields = '__all__'


class UpdateNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScriptNotification
        fields = ['read']


class CharacterImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Character
        fields = ['image']


class CharacterNameSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Character
        fields = ['name']


class CharacterStructureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Character
        fields = ['name', 'character_health', 'possession', 'image']
