import json

from django.db import models, transaction
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import os
import uuid
from django.db.models import Q

# Create your models here.


SCRIPT_MODE = (
    ('dark', 'Dark'),
    ('light', 'Light')
)

SCRIPT_CONDITION = (
    ('Not Registered', 'Not Registered'),
    ('Pending', 'Pending'),
    ('Processing', 'Processing'),
    ('Registered', 'Registered')
)


class ScriptFolder(models.Model):
    script_folder_uuid = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=50, unique=True)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(default=timezone.now, blank=True)

    created_by = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.title


class Script(models.Model):
    script_uuid = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=200, null=True, blank=True)
    version = models.IntegerField(default=1, null=True, blank=True)
    word_count = models.IntegerField(default=0, null=True, blank=True)
    estimated_time = models.FloatField(null=True, blank=True)
    display_watermark = models.BooleanField(default=False)
    water_mark = models.CharField(max_length=50, null=True, blank=True)
    water_mark_opacity = models.FloatField(null=True, blank=True)
    download_path = models.CharField(max_length=50, null=True, blank=True)
    save_minute = models.IntegerField(default=5)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(default=timezone.now, blank=True)
    number_of_pages = models.IntegerField(default=1)
    written_by = models.CharField(max_length=200, null=True, blank=True)
    email_address = models.EmailField(null=True, blank=True)
    contact_name = models.CharField(max_length=200, null=True, blank=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    color = models.CharField(max_length=8, default="green", null=True, blank=True)
    script_condition = models.CharField(max_length=50, choices=SCRIPT_CONDITION, default='Not Registered')

    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)

    script_folder = models.ForeignKey(ScriptFolder, on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.IntegerField()

    def __str__(self):
        if not self.title:
            return self.script_uuid
        return self.title


class Comment(models.Model):
    comment_uuid = models.CharField(max_length=50, unique=True)
    target_uuid = models.CharField(max_length=50, unique=True)
    body = models.TextField(null=True, blank=True)
    position = models.IntegerField(default=1)
    bg_color = models.CharField(max_length=8, default="green", null=True, blank=True)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(null=True, blank=True)

    created_by = models.IntegerField()
    script = models.ForeignKey(Script, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        if self.title:
            return self.title
        return self.comment_uuid


CONTRIBUTOR_ROLE = (
    ('script-editor', 'Script Editor'),
    ('script-consultant', 'Script Consultant')
)


class Contributor(models.Model):
    contributor_uuid = models.CharField(max_length=50, unique=True)
    contributor_role = models.CharField(max_length=30, choices=CONTRIBUTOR_ROLE, default='script-consultant')

    contributor = models.IntegerField()
    contributor_email = models.EmailField(null=True, blank=True)
    outline = models.BooleanField(default=False)
    character = models.BooleanField(default=False)
    location = models.BooleanField(default=False)
    structure = models.BooleanField(default=False)
    story_docs = models.BooleanField(default=False)
    script_permission = models.BooleanField(default=False)

    script = models.ForeignKey(Script, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.contributor_uuid + '-' + self.contributor_role + '-' + self.script.script_uuid


class StoryDocs(models.Model):
    story_docs_uuid = models.CharField(max_length=50, unique=True)
    heading = models.CharField(max_length=200, null=True, blank=True)

    script = models.OneToOneField(Script, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        if self.heading:
            return self.heading
        return self.story_docs_uuid


class SubStory(models.Model):
    sub_story_uuid = models.CharField(max_length=50, unique=True)
    sub_heading = models.CharField(max_length=200, null=True, blank=True)
    body = models.TextField(null=True, blank=True)

    previous_sub_story = models.CharField(max_length=50, null=True, blank=True)
    next_sub_story = models.CharField(max_length=50, null=True, blank=True)
    sub_story_no = models.IntegerField(default=1)
    story_docs = models.ForeignKey(StoryDocs, on_delete=models.SET_NULL, null=True, blank=True)
    script = models.ForeignKey(Script, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        if self.sub_heading:
            return self.sub_heading
        return self.sub_story_uuid


class Act(models.Model):
    act_uuid = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=200)
    total_word = models.IntegerField(default=0)
    page_no = models.IntegerField(default=1)

    previous_act = models.CharField(max_length=50, null=True, blank=True)
    next_act = models.CharField(max_length=50, null=True, blank=True)
    act_no = models.IntegerField(default=1)
    script = models.ForeignKey(Script, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        if self.title:
            return self.title
        return self.act_uuid


class Scene(models.Model):
    scene_uuid = models.CharField(max_length=50, unique=True)
    scene_header = models.CharField(max_length=200, null=True, blank=True)
    transaction_keyword = models.CharField(max_length=200, null=True, blank=True)
    action = models.TextField(null=True, blank=True)
    scene_no = models.IntegerField(default=1)
    scene_goal = models.CharField(max_length=200, null=True, blank=True)
    scene_length = models.FloatField(default=0.0)
    emotional_value = models.IntegerField(validators=[MinValueValidator(-10), MaxValueValidator(10)], default=0)
    total_word = models.IntegerField(default=0)
    page_no = models.IntegerField(default=1)
    bg_color = models.CharField(max_length=8, default="green", null=True, blank=True)

    previous_scene = models.CharField(max_length=50, null=True, blank=True)
    next_scene = models.CharField(max_length=50, null=True, blank=True)

    act = models.ForeignKey(Act, on_delete=models.SET_NULL, null=True, blank=True)
    comment = models.OneToOneField(Comment, on_delete=models.SET_NULL, null=True, blank=True)
    script = models.ForeignKey(Script, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        if self.scene_header:
            return self.scene_header
        return self.scene_uuid


class Location(models.Model):
    location_uuid = models.CharField(max_length=50, unique=True)
    location_heading = models.CharField(max_length=2200, null=True, blank=True)
    location_body = models.TextField(null=True, blank=True)

    script = models.ForeignKey(Script, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.location_type + ' ' + self.scene.scene_header


class ArcheType(models.Model):
    arche_type_uuid = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=200)
    slug = models.CharField(max_length=200)
    script = models.ForeignKey(Script, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.title


CHARACTER_GENDER = (
    ('male', "Male"),
    ('female', "Female"),
    ('other', "Other"),
)


def get_script_image_path(instance, filename):
    unique_filename = f"{str(uuid.uuid4())}-{filename}"

    # Get the script_uuid and use it as the folder name
    script_uuid = instance.script.script_uuid
    return f"script_images/{script_uuid}/{unique_filename}"


class Character(models.Model):
    character_uuid = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    gender = models.CharField(max_length=10, choices=CHARACTER_GENDER, default='male')
    interest = models.TextField(null=True, blank=True)
    occupation = models.CharField(max_length=250, null=True, blank=True)
    character_health = models.FloatField(default=0.0)
    image = models.ImageField(upload_to=get_script_image_path, null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)
    possession = models.FloatField(default=0.0)
    need = models.TextField(null=True, blank=True)
    want = models.TextField(null=True, blank=True)
    traits = models.TextField(null=True, blank=True)
    obstacle = models.TextField(null=True, blank=True)
    character_map = models.TextField(null=True, blank=True, default=json.dumps({
        "inputValue1": "Bold, audacious.",
        "inputValue2": "Wears leather jackets.",
        "inputValue3": "PTSD, anxious.",
        "inputValue4": "Always smoking.",
        "inputValue5": "a bit of a brute!",
        "inputValue6": "Ladies man.",
        "inputValue7": "6 foot 3.",
        "inputValue8": "Speak French and Spanish.",
        "inputValue9": "Very polite to his elders when he has to be.",
        "inputValue10": "Wise",
        "inputValue11": "Protective over family.",
        "inputValue12": "Ready to fight.",
        "inputValue13": "Slight limp when he walks.",
        "inputValue14": "Worker Bee!",
    }))
    character_synopsis = models.TextField(null=True, blank=True)
    total_word = models.IntegerField(default=0)
    character_image_generation = models.IntegerField(default=0)

    archetype = models.ForeignKey(ArcheType, on_delete=models.SET_NULL, null=True, blank=True)
    script = models.ForeignKey(Script, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name

    @transaction.atomic
    def dialogue_delete_and_update_total_word(self):
        character_dialogue = Dialogue.objects.filter(Q(character=self) | Q(dual_character=self))
        if character_dialogue.exists():
            total_words_to_subtract = sum(dialogue.total_word for dialogue in character_dialogue)

            # Update the total word count for related Scene, SceneAct, and Script
            for dialogue in character_dialogue:
                if dialogue.scene:
                    dialogue.scene.total_word -= dialogue.total_word
                    dialogue.scene.scene_length -= dialogue.total_word
                    dialogue.scene.save()
                if dialogue.scene.act:
                    dialogue.scene.act.total_word -= dialogue.total_word
                    dialogue.scene.act.save()

                dialogue.scene.script.word_count -= dialogue.total_word
                dialogue.scene.script.save()
                dialogue.save()

                character_dialogue.delete()

            return True


class CharacterScene(models.Model):
    character_scene_uuid = models.CharField(max_length=50, unique=True)
    character = models.ForeignKey(Character, on_delete=models.SET_NULL, null=True, blank=True)
    scene = models.ForeignKey(Scene, on_delete=models.SET_NULL, null=True, blank=True)
    script = models.ForeignKey(Script, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.character.name + " " + self.scene.scene_header


class Dialogue(models.Model):
    dialogue_uuid = models.CharField(max_length=50, unique=True)
    target_uuid = models.CharField(max_length=50, unique=True)
    line = models.TextField(null=True, blank=True)
    total_word = models.IntegerField(default=0)
    parenthetical = models.TextField(null=True, blank=True)
    dual = models.BooleanField(default=False)
    dual_line = models.TextField(null=True, blank=True)
    dual_character = models.ForeignKey(Character, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='dual_dialogue_character')
    dual_parenthetical = models.TextField(null=True, blank=True)
    dialogue_no = models.IntegerField(default=1)

    previous_dialogue = models.CharField(max_length=50, null=True, blank=True)
    next_dialogue = models.CharField(max_length=50, null=True, blank=True)
    character = models.ForeignKey(Character, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='character')

    scene = models.ForeignKey(Scene, on_delete=models.SET_NULL, null=True, blank=True)
    comment = models.OneToOneField(Comment, on_delete=models.SET_NULL, null=True, blank=True)
    script = models.ForeignKey(Script, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.character.name + ': ' + self.line


ACTIVITY_ACTION = (
    ('create', 'Create'),
    ('update', 'Update'),
    ('delete', 'Delete')
)


class ScriptActivity(models.Model):
    activity_uuid = models.CharField(max_length=50, unique=True)
    message = models.TextField(null=True, blank=True)
    details = models.JSONField(null=True, blank=True)
    action = models.CharField(max_length=30, choices=ACTIVITY_ACTION, default='create')
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.activity_uuid


NOTIFICATION_TYPE = (
    ('activities', 'activities'),
    ('comments', 'comments'),
    ('register', 'register'),
    ('feature_update', 'feature_update'),
    ('contributor', 'contributor')
)


class ScriptNotification(models.Model):
    notification_uuid = models.CharField(max_length=50, unique=True)
    read = models.BooleanField(default=False)
    notification_type = models.CharField(max_length=200, choices=NOTIFICATION_TYPE, default='activities')
    message = models.TextField(null=True, blank=True)
    details = models.JSONField(null=True, blank=True)
    created_on = models.DateTimeField(auto_now_add=True)

    user = models.IntegerField()

    def __str__(self):
        return self.notification_uuid
