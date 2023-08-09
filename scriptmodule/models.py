from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


# Create your models here.

class Comment(models.Model):
    comment_uuid = models.CharField(max_length=50)
    title = models.CharField(max_length=200, null=True, blank=True)
    body = models.TextField(null=True, blank=True)
    bg_color = models.CharField(max_length=8, null=True)
    created_on = models.DateTimeField(auto_now_add=True)

    created_by = models.IntegerField()

    def __str__(self):
        return self.title


SCRIPT_MODE = (
    ('dark', 'Dark'),
    ('light', 'Light')
)


class Script(models.Model):
    script_uuid = models.CharField(max_length=50)
    title = models.CharField(max_length=200, null=True, blank=True)
    version = models.IntegerField(default=0, null=True, blank=True)
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
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)

    created_by = models.IntegerField()

    def __str__(self):
        return self.script_uuid


CONTRIBUTOR_ROLE = (
    ('editor', 'Editor'),
    ('reviewer', 'Reviewer'),
    ('viewer', 'Viewer'),
    ('actor', 'Actor')
)


class Contributor(models.Model):
    contributor_uuid = models.CharField(max_length=50)
    contributor_role = models.CharField(max_length=30, choices=CONTRIBUTOR_ROLE, default='viewer')

    script = models.ForeignKey(Script, on_delete=models.SET_NULL, null=True, blank=True)
    contributor = models.IntegerField()

    def __str__(self):
        return str(self.contributor) + '-' + self.contributor_role


class StoryDocs(models.Model):
    story_docs_uuid = models.CharField(max_length=50)
    heading = models.CharField(max_length=200)

    script = models.OneToOneField(Script, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.heading


class SubStory(models.Model):
    sub_story_uuid = models.CharField(max_length=50)
    sub_heading = models.CharField(max_length=200)
    body = models.TextField(null=True, blank=True)

    previous_sub_story = models.CharField(max_length=50, null=True, blank=True)
    next_sub_story = models.CharField(max_length=50, null=True, blank=True)
    sub_story_no = models.IntegerField(default=1)
    story_docs = models.ForeignKey(StoryDocs, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.sub_heading


class Act(models.Model):
    act_uuid = models.CharField(max_length=50)
    title = models.CharField(max_length=200)
    total_word = models.IntegerField(default=0)
    page_no = models.IntegerField(default=1)

    previous_act = models.CharField(max_length=50, null=True, blank=True)
    next_act = models.CharField(max_length=50, null=True, blank=True)
    act_no = models.IntegerField(default=1)
    script = models.ForeignKey(Script, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.title


class Scene(models.Model):
    scene_uuid = models.CharField(max_length=50)
    scene_header = models.CharField(max_length=200)
    transaction_keyword = models.CharField(max_length=200)
    action = models.CharField(max_length=200)
    scene_no = models.IntegerField(default=1)
    scene_goal = models.CharField(max_length=200)
    scene_length = models.FloatField()
    emotional_value = models.IntegerField(validators=[MinValueValidator(-10), MaxValueValidator(10)])
    total_word = models.IntegerField(default=0)
    page_no = models.IntegerField(default=1)

    previous_scene = models.CharField(max_length=50, null=True, blank=True)
    next_scene = models.CharField(max_length=50, null=True, blank=True)

    act = models.ForeignKey(Act, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.scene_header


LOCATION_TYPE = (
    ('int', 'Int'),
    ('ext', 'Ext')
)


class Location(models.Model):
    location_uuid = models.CharField(max_length=50)
    location_type = models.CharField(max_length=5, choices=LOCATION_TYPE)
    description = models.TextField(null=True, blank=True)

    scene = models.ForeignKey(Scene, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.location_type + ' ' + self.scene.scene_header


class ArcheType(models.Model):
    arche_type_uuid = models.CharField(max_length=50)
    title = models.CharField(max_length=200)
    slug = models.CharField(max_length=200)

    def __str__(self):
        return self.title


class Character(models.Model):
    character_uuid = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    image = models.ImageField(null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)
    possession = models.CharField(max_length=10, null=True, blank=True)
    need = models.TextField(null=True, blank=True)
    traits = models.TextField(null=True, blank=True)
    obstacle = models.TextField(null=True, blank=True)
    character_map = models.JSONField(null=True, blank=True)
    character_synopsis = models.TextField(null=True, blank=True)
    total_word = models.IntegerField()
    character_image_generation = models.IntegerField(default=0)

    archetype = models.ForeignKey(ArcheType, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name


class CharacterScene(models.Model):
    character = models.ForeignKey(Character, on_delete=models.SET_NULL, null=True, blank=True)
    scene = models.ForeignKey(Scene, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.character.name + " " + self.scene.scene_header


class Dialogue(models.Model):
    dialogue_uuid = models.CharField(max_length=50)
    line = models.TextField(null=True, blank=True)
    total_word = models.IntegerField(default=0)
    dual = models.BooleanField(default=False)
    dual_line = models.OneToOneField('self', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='dual_dialogue')
    dual_character = models.OneToOneField(Character, on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name='dual_dialogue_character')

    dialogue_no = models.IntegerField(default=1)

    previous_dialogue = models.CharField(max_length=50, null=True, blank=True)
    next_dialogue = models.CharField(max_length=50, null=True, blank=True)
    character = models.OneToOneField(Character, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='character')

    scene = models.ForeignKey(Scene, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        if self.dual_dialogue:
            return self.character.name + ': ' + self.line + '||' + self.dual_dialogue_character.name + ": " + self.dual_dialogue.line
        return self.character.name + ': ' + self.line


ACTIVITY_ACTION = (
    ('create', 'Create'),
    ('update', 'Update'),
    ('delete', 'Delete')
)


class ScriptActivity(models.Model):
    activity_uuid = models.CharField(max_length=50)
    message = models.TextField(null=True, blank=True)
    details = models.JSONField(null=True, blank=True)
    action = models.CharField(max_length=30, choices=ACTIVITY_ACTION, default='create')
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.activity_uuid