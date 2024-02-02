from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from .utils import token_validator, compressed_image
from .serializer import *
import uuid
from rest_framework import status
from django.db.models import F
from django.db.models import Q
from .raw_queries import *
from django.core.mail import send_mail
import stripe
import json
from rest_framework.parsers import MultiPartParser, FormParser
from django.conf import settings
from django.db import IntegrityError
import base64
import datetime

stripe.api_key = 'sk_test_51NbFFrL2MME1ps3wfbAiYaOfux9XN4i25NGlNVgBcsOPcAxnwsKRRxoUdHDkX9nToy4zV84V8zgCVT3t1XPbVoc200VShiI03H'


# Create your views here.
def create_script_activity(data):
    data['activity_uuid'] = str(uuid.uuid4())
    activity = ScriptActivity.objects.create(**data)
    activity.save()


def get_user_id(request):
    data = token_validator(request)
    return data


def create_notification(user, notification_type, message):
    script_notification = ScriptNotification.objects.create(
        **{'notification_uuid': str(uuid.uuid4()), 'user': user, 'notification_type': notification_type,
           'message': message})
    script_notification.save()


def character_possession_update(script):
    characters = Character.objects.filter(script=script)
    number_of_dialogues = Dialogue.objects.filter(script=script).count()
    for character in characters:
        possesion = Dialogue.objects.filter(character=character, script=script).count() / number_of_dialogues
        character.possession = round(possesion * 100, 2)
        character.save()


class DashboardView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get(self, request):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        # raw queries to fetch data from script and folder table
        scripts = Script.objects.raw(
            f"select * from scriptmodule_script where created_by={user_data.get('user_id')} and parent_id is null ORDER BY updated_on desc LIMIT 3")
        folders = ScriptFolder.objects.raw(
            f"SELECT * FROM scriptmodule_scriptfolder WHERE created_by={user_data.get('user_id')} ORDER BY updated_on desc LIMIT 3;")
        folder_serializer = ScriptFolderSerializer(folders, many=True)
        script_serializer = ScriptSerializer(scripts, many=True)
        return Response({'scripts': script_serializer.data, 'folders': folder_serializer.data},
                        status=status.HTTP_200_OK)


class DashboardSeeMoreView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get(self, request):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        # raw queries to fetch data from script and folder table
        scripts = Script.objects.raw(
            f"select * from scriptmodule_script where created_by={user_data.get('user_id')} and parent_id is null and script_folder_id is null ORDER BY updated_on desc")
        folders = ScriptFolder.objects.raw(
            f"SELECT * FROM scriptmodule_scriptfolder WHERE created_by={user_data.get('user_id')} ORDER BY updated_on desc")
        folder_serializer = ScriptFolderSerializer(folders, many=True)
        script_serializer = ScriptSerializer(scripts, many=True)
        return Response({'scripts': script_serializer.data, 'folders': folder_serializer.data},
                        status=status.HTTP_200_OK)


class ScriptRetrieveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_contributor(self, script, contributor, editor):
        if editor:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='script-editor',
                                               script_permission=True)
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor, script_permission=True)
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid=script_uuid)

        if not script:
            return Response('Script not found', status=status.HTTP_200_OK)
        contributor = self.get_contributor(script=script, contributor=user_data.get('user_id'), editor=False)
        if script.created_by == user_data.get('user_id') or contributor:
            serializer = ScriptSerializer(script)

            acts = Act.objects.filter(script=script).order_by('act_no')
            data = []
            for act in acts:
                scenes = Scene.objects.filter(act=act, script=script).order_by('scene_no')
                act_body = []
                for scene in scenes:
                    scene_serializer = SceneSerializer(scene)
                    dialogues = Dialogue.objects.filter(scene=scene).order_by('dialogue_no')
                    dialogue_serializer = DialogueSerializer(dialogues, many=True)
                    scene_serializer.data['dialogue_data'] = dialogue_serializer.data
                    scene_data = scene_serializer.data
                    scene_data['dialogue_data'] = dialogue_serializer.data
                    act_body.append(scene_data)

                data.append({'actHead': act.title, 'actUUID': act.act_uuid, 'actNo': act.act_no, 'actBody': act_body})

            return Response({'script_info': serializer.data, 'data': data}, status=status.HTTP_200_OK)
        return Response("You don't have permission to View this script", status=status.HTTP_401_UNAUTHORIZED)

    def put(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid=script_uuid)
        if not script:
            return Response('Script not found', status=status.HTTP_200_OK)
        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)
        contributor = self.get_contributor(script=script, contributor=user_data.get('user_id'), editor=True)
        if script.created_by == user_data.get('user_id') or contributor:
            serializer = ScriptUpdateSerializer(script, data=request.data, partial=True)
            if serializer.is_valid():
                if script.parent:
                    script.parent.updated_on = timezone.now()
                    script.parent.save()

                if script.script_folder:
                    script.script_folder.updated_on = timezone.now()
                    script.script_folder.save()

                script.updated_on = timezone.now()
                serializer.save()
                script.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to edit this script", status=status.HTTP_401_UNAUTHORIZED)


class ScriptVersionGetView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_script(self, script_uuid, created_by):
        try:
            return Script.objects.get(script_uuid=script_uuid, created_by=created_by)
        except Script.DoesNotExist:
            return None

    def get(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid=script_uuid, created_by=user_data.get('user_id'))
        if not script:
            return Response('Script not found', status=status.HTTP_400_BAD_REQUEST)

        data = {}

        if script.parent:
            scripts = Script.objects.filter(parent=script.parent).order_by('version')
            data[script.parent.version] = script.parent.script_uuid
        else:
            scripts = Script.objects.filter(parent=script).order_by('version')
            data[script.version] = script.script_uuid

        for s in scripts:
            data[s.version] = s.script_uuid

        return Response(data.values(), status=status.HTTP_200_OK)


class ScriptCopyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_object(self, script_uuid, created_by):
        try:
            return Script.objects.get(script_uuid=script_uuid, created_by=created_by)
        except Script.DoesNotExist:
            return None

    def get(self, request, script_uuid, new_script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_object(script_uuid=script_uuid, created_by=user_data.get('user_id'))
        if not script:
            return Response("You don't have permission to create draft of a script", status=status.HTTP_400_BAD_REQUEST)

        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)

        if script.parent:
            parent = script.parent
            version = Script.objects.filter(parent=parent).count() + 2
            script.parent.updated_on = timezone.now()
            script.parent.save()
        else:
            parent = script
            version = 2

        if script.script_folder:
            script.script_folder.updated_on = timezone.now()
            script.script_folder.save()
        # creating script
        script_serializer = ScriptSerializer(data={
            'script_uuid': new_script_uuid,
            'parent': parent.id,
            'title': script.title,
            'version': version,
            'word_count': script.word_count,
            'estimated_time': script.estimated_time,
            'display_watermark': script.display_watermark,
            'download_path': script.download_path,
            'water_mark': script.water_mark,
            'water_mark_opacity': script.water_mark_opacity,
            'save_minute': script.save_minute,
            'number_of_pages': script.number_of_pages,
            'written_by': script.written_by,
            'email_address': script.email_address,
            'contact_name': script.contact_name,
            'phone_number': script.phone_number,
            'created_by': user_data.get('user_id'),
            'color': script.color,
            'script_folder': script.script_folder.id if script.script_folder else None
        })
        if not script_serializer.is_valid():
            return Response(script_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        script_serializer.save()
        arche_types = ArcheType.objects.filter(script=script)
        for arche_type in arche_types:
            # copy archetype of a script
            arche_type_serializer = ArcheTypeSerializer(
                data={'arche_type_uuid': str(uuid.uuid4()), 'title': arche_type.title, 'slug': arche_type.slug,
                      'script': script_serializer.data.get('id')})
            if not arche_type_serializer.is_valid():
                return Response(arche_type_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            arche_type_serializer.save()
        characters = Character.objects.filter(script=script)
        for character in characters:
            if character.archetype:
                arche_type = ArcheType.objects.filter(title=character.archetype.title,
                                                      script__id=script_serializer.data.get('id')).first().id
            else:
                arche_type = None
            # copy data of a characters of a script
            character_serializer = CharacterSerializer(
                data={'character_uuid': str(uuid.uuid4()), 'name': character.name, 'gender': character.gender,
                      'interest': character.interest, 'occupation': character.occupation,
                      'character_health': character.character_health, 'age': character.age,
                      'possession': character.possession, 'need': character.need, 'traits': character.traits,
                      'obstacle': character.obstacle, 'character_map': character.character_map,
                      'character_synopsis': character.character_synopsis, 'total_word': character.total_word,
                      'archetype': arche_type, 'script': script_serializer.data.get('id')})
            if not character_serializer.is_valid():
                return Response(character_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            character_serializer.save()

        locations = Location.objects.filter(script=script)
        for location in locations:
            location_serializer = LocationSerializer(
                data={'location_uuid': str(uuid.uuid4()), 'location_heading': location.location_heading,
                      'location_body': location.location_body,
                      'script': script_serializer.data.get('id')})
            if not location_serializer.is_valid():
                return Response(location_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            location_serializer.save()
        acts = Act.objects.filter(script=script).order_by('act_no')
        inside_data = []
        for act in acts:
            # copy act data of a script
            act_serializer = ActSerializer(
                data={'act_uuid': str(uuid.uuid4()), 'title': act.title, 'total_word': act.total_word,
                      'page_no': act.page_no, 'previous_act': act.previous_act, 'next_act': act.next_act,
                      'act_no': act.act_no, 'script': script_serializer.data.get('id')})
            if not act_serializer.is_valid():
                return Response(act_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            act_serializer.save()
            act_body = []
            scenes = Scene.objects.filter(act=act).order_by('scene_no')

            # copy scene of an act of a script
            for scene in scenes:
                scene_serializer = SceneSerializer(data={'scene_uuid': str(uuid.uuid4()), 'scene_no': scene.scene_no,
                                                         'scene_header': scene.scene_header, 'action': scene.action,
                                                         'transaction_keyword': scene.transaction_keyword,
                                                         'scene_goal': scene.scene_goal,
                                                         'scene_length': scene.scene_length,
                                                         'emotional_value': scene.emotional_value,
                                                         'total_word': scene.total_word, 'page_no': scene.page_no,
                                                         'bg_color': scene.bg_color,
                                                         'previous_scene': scene.previous_scene,
                                                         'next_scene': scene.next_scene,
                                                         'act': act_serializer.data.get('id'),
                                                         'script': script_serializer.data.get('id')})
                if not scene_serializer.is_valid():
                    return Response(scene_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                scene_serializer.save()
                scene_data = scene_serializer.data
                character_scenes = CharacterScene.objects.filter(scene=scene, script=script)
                for character_scene in character_scenes:
                    character_scene_serializer = CharacterSceneSerializer(
                        data={'character_scene_uuid': str(uuid.uuid4()), 'character': character_scene.character.id,
                              'scene': scene_serializer.data.get('id'), 'script': script_serializer.data.get('id')})
                    if not character_scene_serializer.is_valid():
                        return Response(character_scene_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                    character_scene_serializer.save()
                dialogues = Dialogue.objects.filter(scene=scene).order_by('dialogue_no')
                d = []
                for dialogue in dialogues:
                    if dialogue.dual_character:
                        dual_character = Character.objects.filter(
                            name=dialogue.dual_character.name,
                            script=script_serializer.data.get('id')
                        ).first()
                        dual_character_id = dual_character.id if dual_character else None
                    else:
                        dual_character_id = None

                    character_id = Character.objects.filter(
                        name=dialogue.character.name,
                        script=script_serializer.data.get('id')
                    ).first().id if dialogue.character and Character.objects.filter(
                        name=dialogue.character.name,
                        script=script_serializer.data.get('id')
                    ) else None

                    dialogue_serializer = DialogueSerializer(
                        data={'dialogue_uuid': str(uuid.uuid4()), 'line': dialogue.line,
                              'total_word': dialogue.total_word,
                              'dual': dialogue.dual, 'dual_line': dialogue.dual_line,
                              'parenthetical': dialogue.parenthetical,
                              'dual_parenthetical': dialogue.dual_parenthetical,
                              'scene': scene_serializer.data.get('id'),
                              'dual_character': dual_character_id,
                              'dialogue_no': dialogue.dialogue_no,
                              'previous_dialogue': dialogue.previous_dialogue,
                              'next_dialogue': dialogue.next_dialogue,
                              'character': character_id,
                              'script': script_serializer.data.get('id')})
                    if not dialogue_serializer.is_valid():
                        return Response(dialogue_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                    dialogue_serializer.save()
                    d.append(dialogue_serializer.data)
                scene_data['dialogue_data'] = d
                act_body.append(scene_data)
            inside_data.append(
                {'actHead': act_serializer.data.get('title'), 'actUUID': act_serializer.data.get('act_uuid'),
                 'actNo': act_serializer.data.get('act_no'), 'actBody': act_body})

        create_script_activity({'action': 'create', 'message': f"copy of a script {script_uuid} created successfully",
                                'details': {'created_by': user_data.get('user_id')}})
        return Response({'script_info': script_serializer.data, 'data': inside_data}, status=status.HTTP_200_OK)


class CreateScriptDraftView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_object(self, script_uuid, created_by):
        try:
            return Script.objects.get(script_uuid=script_uuid, created_by=created_by)
        except Script.DoesNotExist:
            return None

    def get(self, request, script_uuid, new_script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_object(script_uuid=script_uuid, created_by=user_data.get('user_id'))
        if not script:
            return Response("You don't have permission to create draft of a script", status=status.HTTP_400_BAD_REQUEST)

        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)

        if script.parent:
            parent = script.parent
            version = Script.objects.filter(parent=parent).count() + 2
            script.parent.updated_on = timezone.now()
            script.parent.save()
        else:
            parent = script
            version = 2

        if script.script_folder:
            script.script_folder.updated_on = timezone.now()
            script.script_folder.save()
        # creating script
        script_serializer = ScriptSerializer(data={
            'script_uuid': new_script_uuid,
            'parent': parent.id,
            'title': script.title,
            'version': version,
            'word_count': script.word_count,
            'estimated_time': script.estimated_time,
            'display_watermark': script.display_watermark,
            'download_path': script.download_path,
            'water_mark': script.water_mark,
            'water_mark_opacity': script.water_mark_opacity,
            'save_minute': script.save_minute,
            'number_of_pages': script.number_of_pages,
            'written_by': script.written_by,
            'email_address': script.email_address,
            'contact_name': script.contact_name,
            'phone_number': script.phone_number,
            'created_by': user_data.get('user_id'),
            'color': script.color,
            'script_folder': script.script_folder.id if script.script_folder else None
        })
        if not script_serializer.is_valid():
            return Response(script_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        script_serializer.save()

        new_script_id = script_serializer.data.get("id")
        new_script = Script.objects.get(id=new_script_id)

        bulk_list = []
        arche_types = ArcheType.objects.filter(script=script)

        for arche_type in arche_types:
            bulk_list.append(ArcheType(arche_type_uuid=str(uuid.uuid4()), title=arche_type.title, slug=arche_type.slug,
                                       script=new_script))

        ArcheType.objects.bulk_create(bulk_list)
        bulk_list.clear()

        characters = Character.objects.filter(script=script)
        for character in characters:
            if character.archetype:
                try:
                    arche_type = ArcheType.objects.get(title=character.archetype.title, script__id=new_script_id)
                except ArcheType.DoesNotExist:
                    arche_type = None
            else:
                arche_type = None

            bulk_list.append(Character(character_uuid=str(uuid.uuid4()), name=character.name, gender=character.gender,
                                       interest=character.interest, occupation=character.occupation,
                                       character_health=character.character_health, age=character.age,
                                       possession=character.possession, need=character.need, traits=character.traits,
                                       obstacle=character.obstacle, character_map=character.character_map,
                                       character_synopsis=character.character_synopsis, total_word=character.total_word,
                                       archetype=arche_type, script=new_script))
        Character.objects.bulk_create(bulk_list)
        bulk_list.clear()
        locations = Location.objects.filter(script=script)
        for location in locations:
            bulk_list.append(Location(location_uuid=str(uuid.uuid4()), location_heading=location.location_heading,
                                      location_body=location.location_body,
                                      script=new_script))

        Location.objects.bulk_create(bulk_list)
        bulk_list.clear()
        acts = Act.objects.filter(script=script).order_by('act_no')
        inside_data = []

        # Create a list to hold the Act instances

        character_scene_objects = []
        for act in acts:
            try:
                new_act = Act.objects.create(act_uuid=str(uuid.uuid4()), title=act.title, page_no=act.page_no,
                                             act_no=act.act_no, script=new_script)
                new_act.save()

            except IntegrityError as e:
                return Response(str(e), status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response(str(e), status=status.HTTP_400_BAD_REQUEST)

            act_body = []
            scenes = Scene.objects.filter(act=act).order_by('scene_no')

            for scene in scenes:
                try:
                    new_scene = Scene.objects.create(scene_uuid=str(uuid.uuid4()), scene_no=scene.scene_no,
                                                     scene_header=scene.scene_header, action=scene.action,
                                                     transaction_keyword=scene.transaction_keyword,
                                                     scene_goal=scene.scene_goal,
                                                     scene_length=scene.scene_length,
                                                     emotional_value=scene.emotional_value,
                                                     total_word=scene.total_word, page_no=scene.page_no,
                                                     bg_color=scene.bg_color,
                                                     previous_scene=scene.previous_scene,
                                                     next_scene=scene.next_scene,
                                                     act=new_act,
                                                     script=new_script)
                    new_scene.save()
                except IntegrityError as e:
                    return Response(str(e), status=status.HTTP_400_BAD_REQUEST)
                except Exception as e:
                    return Response(str(e), status=status.HTTP_400_BAD_REQUEST)

                character_sceness = CharacterScene.objects.filter(script=script, scene=scene)
                for cs in character_sceness:
                    try:
                        character_name = Character.objects.get(name=cs.character.name, script=new_script)
                    except Character.DoesNotExist:
                        character_name = None
                    character_scene_objects.append(CharacterScene(character_scene_uuid=str(uuid.uuid4()),
                                                                  character=character_name,
                                                                  scene=new_scene, script=new_script))

                dialogues = Dialogue.objects.filter(scene=scene).order_by('dialogue_no')
                dd = []
                for dialogue in dialogues:
                    if dialogue.dual_character:
                        try:
                            dual_character = Character.objects.get(name=dialogue.dual_character.name, script=new_script)
                        except:
                            dual_character = None
                    else:
                        dual_character = None

                    try:
                        character = Character.objects.get(name=dialogue.character.name, script=new_script)
                    except:
                        character = None
                    the_uuid = str(uuid.uuid4())
                    dd.append(Dialogue(dialogue_uuid=the_uuid, target_uuid=the_uuid, line=dialogue.line,
                                       total_word=dialogue.total_word,
                                       dual=dialogue.dual, dual_line=dialogue.dual_line,
                                       parenthetical=dialogue.parenthetical,
                                       dual_parenthetical=dialogue.dual_parenthetical,
                                       scene=new_scene,
                                       dual_character=dual_character,
                                       dialogue_no=dialogue.dialogue_no,
                                       previous_dialogue=dialogue.previous_dialogue,
                                       next_dialogue=dialogue.next_dialogue,
                                       character=character,
                                       script=new_script))
                d = Dialogue.objects.bulk_create(dd)
                scene_data = SceneSerializer(new_scene).data
                scene_data['dialogue_data'] = DialogueSerializer(d, many=True).data
                act_body.append(scene_data)

            inside_data.append({
                'actHead': new_act.title, 'actUUID': act.act_uuid,
                'actNo': new_act.act_no, 'actBody': act_body
            })

        CharacterScene.objects.bulk_create(character_scene_objects)
        # Create script activity
        create_script_activity({'action': 'create', 'message': f"Copy of a script {script_uuid} created successfully",
                                'details': {'created_by': user_data.get('user_id')}})

        # Return the Response with serialized data
        return Response({'script_info': script_serializer.data, 'data': inside_data}, status=status.HTTP_200_OK)


class DeleteScriptView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_script(self, script_uuid, created_by):
        try:
            return Script.objects.get(script_uuid=script_uuid, created_by=created_by)
        except Script.DoesNotExist:
            return None

    def delete(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid=script_uuid, created_by=user_data.get('user_id'))
        if not script:
            return Response(status=status.HTTP_204_NO_CONTENT)

        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)

        if not script.parent:
            child = Script.objects.filter(
                Q(script_uuid=script_uuid, created_by=user_data.get('user_id')) | Q(parent__script_uuid=script_uuid,
                                                                                    created_by=user_data.get(
                                                                                        'user_id'))).order_by(
                '-updated_on')

            if child.filter(~Q(script_condition='Not Registered')).exists():
                return Response(
                    'Your script is in lock mode. You can not update or delete',
                    status=status.HTTP_400_BAD_REQUEST)

            Act.objects.filter(script__in=child).delete()
            Scene.objects.filter(script__in=child).delete()
            Dialogue.objects.filter(script__in=child).delete()
            Location.objects.filter(script__in=child).delete()
            StoryDocs.objects.filter(script__in=child).delete()
            SubStory.objects.filter(script__in=child).delete()
            Character.objects.filter(script__in=child).delete()
            ArcheType.objects.filter(script__in=child).delete()
            CharacterScene.objects.filter(script__in=child).delete()
            child.delete()
            subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int) and json.loads(subscription.get('permission'))['number_of_script'] < 5:
                update_subscription_plan_permission_number_of_script_add(subscription_id=subscription.get('id'))

            return Response(status=status.HTTP_204_NO_CONTENT)

        if script.parent:
            script.parent.updated_on = timezone.now()
            script.parent.save()

        if script.script_folder:
            script.script_folder.updated_on = timezone.now()
            script.script_folder.save()
        Character.objects.filter(script=script).delete()
        ArcheType.objects.filter(script=script).delete()
        Dialogue.objects.filter(script=script).delete()
        Scene.objects.filter(script=script).delete()
        Act.objects.filter(script=script).delete()
        Location.objects.filter(script=script).delete()
        StoryDocs.objects.filter(script=script).delete()
        SubStory.objects.filter(script=script).delete()
        CharacterScene.objects.filter(script=script).delete()
        Script.objects.filter(parent=script.parent, version__gt=script.version).update(version=F('version') - 1)
        script.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ScriptView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get(self, request):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        scripts = Script.objects.filter(created_by=user_data.get('user_id'), parent=None).order_by('-updated_on')
        serializer = ScriptSerializer(scripts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        request.data['created_by'] = user_data.get('user_id')

        subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
        if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                      int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
            return Response("Please buy pro package. You don't have permission to create a script",
                            status=status.HTTP_400_BAD_REQUEST)
        if request.data.get('script_folder'):
            script_folder = ScriptFolder.objects.get(script_folder_uuid=request.data.get('script_folder'))
            request.data['script_folder'] = script_folder.id
            script_folder.updated_on = timezone.now()
            script_folder.save()

        serializer = ScriptSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int):
                update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
            create_script_activity({'action': 'create', 'message': 'new script created',
                                    'details': {'created_by': user_data.get('user_id')}})

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ContributorView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_script(self, script_uuid, user):
        try:
            return Script.objects.get(script_uuid=script_uuid, created_by=user)
        except Script.DoesNotExist:
            return None

    def get(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        script = self.get_script(script_uuid=script_uuid, user=user_data.get('user_id'))
        if not script:
            return Response("Script not found", status=status.HTTP_400_BAD_REQUEST)

        contributor = Contributor.objects.filter(script=script)
        serializer = ContributorSerializer(contributor, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        script = self.get_script(script_uuid=script_uuid, user=user_data.get('user_id'))
        if not script:
            return Response('Script not found', status=status.HTTP_200_OK)

        contributor_id = fetch_user_with_email(request.data.get('contributor_email'))
        if contributor_id:
            link = request.data.pop('link', None)
            request.data['contributor'] = contributor_id.get('id')
            request.data['script'] = script
            contributor_check = Contributor.objects.filter(contributor=contributor_id.get('id'), script=script)
            if contributor_check.exists():
                serializer = ContributorUpdateSerializer(contributor_check.first(), data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            contributor = Contributor.objects.create(**request.data)
            contributor.save()
            create_script_activity({'action': 'create', 'message': 'new contributor added',
                                    'details': {'created_by': user_data.get('user_id')}})
            message = f"New contributor added to script {link}"
            # send_mail("Invitation to collaborate", message, 'email',
            #           [request.data.get('contributor_email')], fail_silently=False)
            create_notification(user=contributor_id.get('id'), notification_type='contributor',
                                message=f"You have been added to {script.title} as a {request.data['contributor_role']}")
            return Response(ContributorSerializer(contributor).data, status=status.HTTP_201_CREATED)
        return Response('User not found associate with this email', status=status.HTTP_200_OK)


class ContributorRetrieveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_object(self, contributor_uuid):
        try:
            return Contributor.objects.get(contributor_uuid=contributor_uuid)
        except Contributor.DoesNotExist:
            return None

    def get(self, request, contributor_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        contributor = self.get_object(contributor_uuid)
        if contributor:
            serializer = ContributorSerializer(contributor)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response({'error': 'Contributor not found'}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, contributor_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        contributor = self.get_object(contributor_uuid)
        if contributor:
            serializer = ContributorUpdateSerializer(contributor, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                create_script_activity({'action': 'update',
                                        'message': f'contributor {contributor_uuid} updated',
                                        'details': {'created_by': user_data.get('user_id')}})
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response('Contributor not found', status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, contributor_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        contributor = self.get_object(contributor_uuid)
        if contributor:
            contributor.delete()
            create_script_activity({'action': 'delete',
                                    'message': f'contributor {contributor_uuid} deleted',
                                    'details': {'created_by': user_data.get('user_id')}})
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response('No contributor found', status=status.HTTP_404_NOT_FOUND)


class StoryDocsListCreateView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_contributor(self, script, contributor, editor):
        if editor:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='script-editor',
                                               story_docs=True)
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor, story_docs=True)
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def post(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            return Response({'error': 'Script not found'}, status=status.HTTP_404_NOT_FOUND)
        contributor = self.get_contributor(script=script, contributor=user_data.get('user_id'), editor=True)
        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)

        if script.created_by == user_data.get('user_id') or contributor:
            request.data['script'] = script.id

            serializer = StoryDocsSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                create_script_activity({'action': 'create', 'message': 'new story docs added',
                                        'details': {'created_by': user_data.get('user_id')}})

                if script.parent:
                    script.parent.updated_on = timezone.now()
                    script.parent.save()

                if script.script_folder:
                    script.script_folder.updated_on = timezone.now()
                    script.script_folder.save()

                script.updated_on = timezone.now()
                script.save()

                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to edit this script", status=status.HTTP_401_UNAUTHORIZED)


class StoryDocsRetrieveUpdateDeleteView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_contributor(self, script, contributor, editor):
        if editor:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='script-editor',
                                               story_docs=True)
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor, story_docs=True)
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get_object(self, script):
        try:
            return StoryDocs.objects.get(script=script)
        except StoryDocs.DoesNotExist:
            return None

    def get(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            return Response({'error': 'Script not found'}, status=status.HTTP_404_NOT_FOUND)

        contributor = self.get_contributor(script=script, contributor=user_data.get('user_id'), editor=False)

        if script.created_by == user_data.get('user_id') or contributor:
            story_docs = self.get_object(script)
            if story_docs:
                serializer = StoryDocsSerializer(story_docs)
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response("story docs not found", status=status.HTTP_200_OK)
        return Response("You don't have permission to edit this script", status=status.HTTP_401_UNAUTHORIZED)

    def put(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
                return Response("Please buy pro package. You don't have permission to create a script",
                                status=status.HTTP_400_BAD_REQUEST)
            script = Script.objects.create(**{'script_uuid': script_uuid, 'created_by': user_data.get('user_id')})
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int):
                update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
            create_script_activity({'action': 'create', 'message': 'new script created',
                                    'details': {'created_by': user_data.get('user_id')}})

        contributor = self.get_contributor(script=script, contributor=user_data.get('user_id'), editor=True)
        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)

        if script.created_by == user_data.get('user_id') or contributor:
            story_docs = self.get_object(script=script)
            if story_docs:
                serializer = StoryDocsUpdateSerializer(story_docs, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    create_script_activity({'action': 'update',
                                            'message': f'story docs {story_docs.story_docs_uuid} updated',
                                            'details': {'created_by': user_data.get('user_id')}})
                    if script.parent:
                        script.parent.updated_on = timezone.now()
                        script.parent.save()

                    if script.script_folder:
                        script.script_folder.updated_on = timezone.now()
                        script.script_folder.save()

                    script.updated_on = timezone.now()
                    script.save()
                    return Response(serializer.data, status=status.HTTP_200_OK)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            request.data['script'] = script.id
            request.data['story_docs_uuid'] = str(uuid.uuid4())
            serializer = StoryDocsSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                create_script_activity({'action': 'create', 'message': 'new story docs added',
                                        'details': {'created_by': user_data.get('user_id')}})

                if script.parent:
                    script.parent.updated_on = timezone.now()
                    script.parent.save()

                if script.script_folder:
                    script.script_folder.updated_on = timezone.now()
                    script.script_folder.save()

                script.updated_on = timezone.now()
                script.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_404_NOT_FOUND)
        return Response("You don't have permission to edit this script", status=status.HTTP_401_UNAUTHORIZED)

    # def delete(self, request, script_uuid):
    #     user_data = get_user_id(request)
    #     if not user_data.get('user_id'):
    #         return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
    #
    #     script = self.get_script(script_uuid)
    #     if not script:
    #         return Response({'error': 'Script not found'}, status=status.HTTP_404_NOT_FOUND)
    #     if not script.created_by == user_data.get('user_id'):
    #         return Response("You don't have permission to this scope", status=status.HTTP_401_UNAUTHORIZED)
    #
    #     if not script.parent:
    #         story_docs = self.get_object(script)
    #         if story_docs:
    #             sub_story = SubStory.objects.filter(story_docs=story_docs)
    #             sub_story.delete()
    #             create_script_activity({'action': 'delete',
    #                                     'message': f'sub story of story docs {story_docs.story_docs_uuid} deleted',
    #                                     'details': {'created_by': user_data.get('user_id')}})
    #             story_docs.delete()
    #             create_script_activity({'action': 'delete',
    #                                     'message': f'story docs {story_docs.story_docs_uuid} deleted',
    #                                     'details': {'created_by': user_data.get('user_id')}})
    #             return Response({'message': 'StoryDocs deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
    #         return Response({'error': 'StoryDocs not found'}, status=status.HTTP_404_NOT_FOUND)
    #     parent_script = self.get_script(script.parent.script_uuid)
    #     story_docs = self.get_object(parent_script)
    #     if story_docs:
    #         story_docs.delete()
    #         create_script_activity({'action': 'delete',
    #                                 'message': f'story docs {story_docs.story_docs_uuid} deleted',
    #                                 'details': {'created_by': user_data.get('user_id')}})
    #         return Response({'message': 'StoryDocs deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
    #     return Response({'error': 'StoryDocs not found'}, status=status.HTTP_404_NOT_FOUND)


class SubStoryDocsListCreateView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_contributor(self, script, contributor, editor):
        if editor:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='script-editor',
                                               story_docs=True)
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor, story_docs=True)
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get_story_docs(self, script):
        try:
            return StoryDocs.objects.get(script=script)
        except StoryDocs.DoesNotExist:
            return None

    def get(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        script = self.get_script(script_uuid)
        if not script:
            if not script:
                subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
                if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                              int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
                    return Response("Please buy pro package. You don't have permission to create a script",
                                    status=status.HTTP_400_BAD_REQUEST)
                script = Script.objects.create(**{'script_uuid': script_uuid, 'created_by': user_data.get('user_id')})
                if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                              int):
                    update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
                create_script_activity({'action': 'create', 'message': 'new script created',
                                        'details': {'created_by': user_data.get('user_id')}})
        contributor = self.get_contributor(script=script, contributor=user_data.get('user_id'), editor=False)

        if script.created_by == user_data.get('user_id') or contributor:
            sub_story_docs = SubStory.objects.filter(**{'story_docs__script': script})
            serializer = SubStorySerializer(sub_story_docs, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response("You don't have permission to edit this script", status=status.HTTP_401_UNAUTHORIZED)

    def post(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)

        if not script:
            subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
                return Response("Please buy pro package. You don't have permission to create a script",
                                status=status.HTTP_400_BAD_REQUEST)
            script = Script.objects.create(**{'script_uuid': script_uuid, 'created_by': user_data.get('user_id')})
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int):
                update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
            create_script_activity({'action': 'create', 'message': 'new script created',
                                    'details': {'created_by': user_data.get('user_id')}})

        contributor = self.get_contributor(script=script, contributor=user_data.get('user_id'), editor=True)

        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)

        if script.created_by == user_data.get('user_id') or contributor:
            story_docs = self.get_story_docs(script)
            if not story_docs:
                return Response('No story docs found of this script', status=status.HTTP_400_BAD_REQUEST)
            request.data['story_docs'] = story_docs.id
            request.data['script'] = script.id
            serializer = SubStorySerializer(data=request.data)
            if serializer.is_valid():
                if request.data.get('sub_story_no'):
                    sub_story_no = request.data.get('sub_story_no')
                    SubStory.objects.filter(sub_story_no__gte=sub_story_no, story_docs=story_docs).update(
                        sub_story_no=F('sub_story_no') + 1)
                serializer.save()
                create_script_activity({'action': 'create', 'message': 'new sub story docs created',
                                        'details': {'created_by': user_data.get('user_id')}})

                if script.parent:
                    script.parent.updated_on = timezone.now()
                    script.parent.save()

                if script.script_folder:
                    script.script_folder.updated_on = timezone.now()
                    script.script_folder.save()

                script.updated_on = timezone.now()
                script.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to edit this script", status=status.HTTP_401_UNAUTHORIZED)


class SubStoryRetrieveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_contributor(self, script, contributor, editor):
        if editor:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='script-editor',
                                               story_docs=True)
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor, story_docs=True)
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get_object(self, sub_story_uuid, script):
        try:
            return SubStory.objects.get(sub_story_uuid=sub_story_uuid, script=script)
        except SubStory.DoesNotExist:
            return None

    def get_story_docs(self, script):
        try:
            return StoryDocs.objects.get(script=script)
        except StoryDocs.DoesNotExist:
            return None

    def get(self, request, script_uuid, sub_story_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid=script_uuid)
        if not script:
            if not script:
                subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
                if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                              int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
                    return Response("Please buy pro package. You don't have permission to create a script",
                                    status=status.HTTP_400_BAD_REQUEST)
                script = Script.objects.create(**{'script_uuid': script_uuid, 'created_by': user_data.get('user_id')})
                if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                              int):
                    update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
                create_script_activity({'action': 'create', 'message': 'new script created',
                                        'details': {'created_by': user_data.get('user_id')}})

        contributor = self.get_contributor(script=script, contributor=user_data.get('user_id'), editor=False)
        sub_story = self.get_object(sub_story_uuid=sub_story_uuid, script=script)
        if not sub_story:
            return Response("No sub story found by this id", status=status.HTTP_400_BAD_REQUEST)

        if script.created_by == user_data.get('user_id') or contributor:
            serializer = SubStorySerializer(sub_story)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response("You don't have permission to view this scope", status=status.HTTP_401_UNAUTHORIZED)

    def put(self, request, script_uuid, sub_story_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        script = self.get_script(script_uuid=script_uuid)
        if not script:
            subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
                return Response("Please buy pro package. You don't have permission to create a script",
                                status=status.HTTP_400_BAD_REQUEST)
            script = Script.objects.create(**{'script_uuid': script_uuid, 'created_by': user_data.get('user_id')})
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int):
                update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
            create_script_activity({'action': 'create', 'message': 'new script created',
                                    'details': {'created_by': user_data.get('user_id')}})

        sub_story = self.get_object(sub_story_uuid=sub_story_uuid, script=script)
        contributor = self.get_contributor(script=script, contributor=user_data.get('user_id'), editor=True)

        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)

        if script.created_by == user_data.get('user_id') or contributor:
            if not sub_story:
                story_docs = self.get_story_docs(script=script)
                if not story_docs:
                    story_docs = StoryDocs.objects.create(**{'story_docs_uuid': str(uuid.uuid4()), 'script': script})
                request.data['story_docs'] = story_docs.id
                request.data['script'] = script.id
                serializer = SubStorySerializer(data=request.data)
                if serializer.is_valid():
                    serializer.save()
                    create_script_activity({'action': 'create', 'message': f'sub_story {sub_story_uuid} updated',
                                            'details': {'created_by': user_data.get('user_id')}})
                    if script.parent:
                        script.parent.updated_on = timezone.now()
                        script.parent.save()

                    if script.script_folder:
                        script.script_folder.updated_on = timezone.now()
                        script.script_folder.save()

                    script.updated_on = timezone.now()
                    script.save()

                    return Response(serializer.data, status=status.HTTP_200_OK)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            serializer = SubStoryUpdateSerializer(sub_story, request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                create_script_activity({'action': 'update', 'message': f'sub_story {sub_story_uuid} updated',
                                        'details': {'created_by': user_data.get('user_id')}})
                if script.parent:
                    script.parent.updated_on = timezone.now()
                    script.parent.save()

                if script.script_folder:
                    script.script_folder.updated_on = timezone.now()
                    script.script_folder.save()

                script.updated_on = timezone.now()
                script.save()

                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to edit this", status=status.HTTP_401_UNAUTHORIZED)

    def delete(self, request, script_uuid, sub_story_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid=script_uuid)

        contributor = self.get_contributor(script=script, contributor=user_data.get('user_id'), editor=True)

        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)

        if script.created_by == user_data.get('user_id') or contributor:
            sub_story = self.get_object(sub_story_uuid, script)
            if not sub_story:
                return Response("No sub story found by this id", status=status.HTTP_400_BAD_REQUEST)
            sub_story.delete()

            SubStory.objects.filter(sub_story_no__gt=sub_story.sub_story_no, story_docs=sub_story.story_docs).update(
                sub_story_no=F('sub_story_no') - 1)

            if script.parent:
                script.parent.updated_on = timezone.now()
                script.parent.save()

            if script.script_folder:
                script.script_folder.updated_on = timezone.now()
                script.script_folder.save()

            script.updated_on = timezone.now()
            script.save()

            create_script_activity({'action': 'delete', 'message': f'sub_story {sub_story_uuid} deleted',
                                    'details': {'created_by': user_data.get('user_id')}})
            return Response('Sub story deleted successfully', status=status.HTTP_204_NO_CONTENT)


class ActListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get_contributor(self, script, contributor, editor):
        if editor:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='script-editor',
                                               script_permission=True)
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor, script_permission=True)
        except Contributor.DoesNotExist:
            return None

    def get(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script=script, contributor=user_data.get('user_id'), editor=False)
        if script.created_by == user_data.get('user_id') or contributor:
            acts = Act.objects.filter(script=script).order_by('act_no')
            serializer = ActSerializer(acts, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response("You don't have permission to view this script", status=status.HTTP_401_UNAUTHORIZED)

    def post(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid=script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)
        contributor = self.get_contributor(script=script, contributor=user_data.get('user_id'), editor=True)
        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)

        if script.created_by == user_data.get('user_id') or contributor:
            request.data['script'] = script.id
            request.data['total_word'] = len(request.data['title'].split())
            serializer = ActSerializer(data=request.data)
            if serializer.is_valid():
                act_no = request.data.get('act_no')
                # checking if act_no exist in this script if exist it will upgrade the act_no which is greater than
                # or equal to the act_no
                if act_no:
                    Act.objects.filter(act_no__gte=act_no, script=script).update(act_no=F('act_no') + 1)
                if script.parent:
                    script.parent.updated_on = timezone.now()
                    script.parent.save()

                if script.script_folder:
                    script.script_folder.updated_on = timezone.now()
                    script.script_folder.save()

                if request.data.get('page_no'):
                    script.number_of_pages = max(script.number_of_pages, request.data['page_no'])
                script.updated_on = timezone.now()
                script.word_count += request.data['total_word']
                script.save()
                serializer.save()
                create_script_activity({'action': 'create', 'message': f'act created of {script_uuid}',
                                        'details': {'created_by': user_data.get('user_id')}})
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to edit this script", status=status.HTTP_401_UNAUTHORIZED)


class ActRetrieveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_object(self, act_uuid, script):
        try:
            return Act.objects.get(act_uuid=act_uuid, script=script)
        except Act.DoesNotExist:
            return None

    def get_contributor(self, script, contributor, editor):
        if editor:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='script-editor',
                                               script_permission=True)
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor, script_permission=True)
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get(self, request, script_uuid, act_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid=script_uuid)
        if not script:
            return Response('No script found with this script', status=status.HTTP_400_BAD_REQUEST)

        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        act = self.get_object(act_uuid=act_uuid, script=script)
        if not act:
            return Response('No act found with this act', status=status.HTTP_400_BAD_REQUEST)
        serializer = ActSerializer(act)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, script_uuid, act_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid=script_uuid)
        if not script:
            return Response("this act doesn't belong to any script", status=status.HTTP_400_BAD_REQUEST)

        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)

        act = self.get_object(act_uuid=act_uuid, script=script)
        if not act:
            return Response('No act found with this act', status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script=script, contributor=user_data.get('user_id'), editor=True)
        if script.created_by == user_data.get('user_id') or contributor:
            if request.data.get('act_no') and act.act_no != request.data['act_no']:
                Act.objects.filter(act_no__gte=request.data['act_no']).update(act_no=F('act_no') + 1)
            serializer = ActUpdateSerializer(act, request.data, partial=True)
            if serializer.is_valid():
                serializer.save()

                if script.parent:
                    script.parent.updated_on = timezone.now()
                    script.parent.save()

                if script.script_folder:
                    script.script_folder.updated_on = timezone.now()
                    script.script_folder.save()

                script.updated_on = timezone.now()
                script.save()

                create_script_activity({'action': 'update', 'message': f'act {act_uuid} updated',
                                        'details': {'created_by': user_data.get('user_id')}})
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to edit this act", status=status.HTTP_401_UNAUTHORIZED)

    def delete(self, request, script_uuid, act_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        script = self.get_script(script_uuid=script_uuid)
        if not script:
            return Response("this act doesn't belong to any script", status=status.HTTP_400_BAD_REQUEST)

        act = self.get_object(act_uuid=act_uuid, script=script)
        if not act:
            return Response('No act found with this act', status=status.HTTP_400_BAD_REQUEST)

        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script=script, contributor=user_data.get('user_id'), editor=True)

        if script.created_by == user_data.get('user_id') or contributor:
            scenes = Scene.objects.filter(act=act)
            if scenes:
                # Check if there are any Dialogues associated with the scene
                for scene in scenes:
                    dialogue = Dialogue.objects.filter(scene=scene, script=script)
                    if dialogue.exists():
                        dialogue.delete()

                    # Check if there are any CharacterScenes associated with the scene
                    character_scene = CharacterScene.objects.filter(scene=scene, script=script)
                    if character_scene:
                        character_scene.delete()

                    scene.delete()

            create_script_activity(
                {'action': 'delete', 'message': f'delete all the scenes. Which is connected to act {act_uuid}',
                 'details': {'created_by': user_data.get('user_id')}})
            Act.objects.filter(script=script, act_no__gt=act.act_no).update(act_no=F('act_no') - 1)

            script.word_count -= act.total_word
            if script.parent:
                script.parent.updated_on = timezone.now()
                script.parent.save()

            if script.script_folder:
                script.script_folder.updated_on = timezone.now()
                script.script_folder.save()

            script.updated_on = timezone.now()
            script.save()
            character_possession_update(script=script)
            act.delete()

            create_script_activity({'action': 'delete', 'message': f'act {act_uuid} deleted',
                                    'details': {'created_by': user_data.get('user_id')}})
            return Response('Deleted successfully', status=status.HTTP_204_NO_CONTENT)
        return Response("You don't have permission to delete this act", status=status.HTTP_401_UNAUTHORIZED)


class SceneCreateView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_act(self, act_uuid, script):
        try:
            return Act.objects.get(act_uuid=act_uuid, script=script)
        except Act.DoesNotExist:
            return None

    def get_contributor(self, script, contributor, editor):
        if editor:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='script-editor',
                                               script_permission=True)
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor, script_permission=True)
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get(self, request, script_uuid, act_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid=script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)
        act = self.get_act(act_uuid=act_uuid, script=script)
        if not act:
            return Response('No act found with this id', status=status.HTTP_400_BAD_REQUEST)

        scene = Scene.objects.filter(**{'act': act}).order_by('scene_no')
        serializer = SceneSerializer(scene, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, script_uuid, act_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid=script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)
        act = self.get_act(act_uuid=act_uuid, script=script)
        if not act:
            return Response('No act found with this id', status=status.HTTP_400_BAD_REQUEST)
        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)
        contributor = self.get_contributor(script=script, contributor=user_data.get('user_id'), editor=True)

        if script.created_by == user_data.get('user_id') or contributor:
            request.data['act'] = act.id
            length = 0
            if request.data.get('scene_header'):
                length = len(request.data.get('scene_header').split(' '))
            if request.data.get('action'):
                length += len(request.data.get('action').split(' '))
            if request.data.get('transaction_keyword'):
                length += len(request.data.get('transaction_keyword').split(' '))

            request.data['scene_length'] = length
            request.data['total_word'] = length
            request.data['script'] = script.id

            serializer = SceneSerializer(data=request.data)
            if serializer.is_valid():
                # checking if scene_no exist in this act. If exist it will upgrade the scene_no which is greater than
                # or equal to the scene_no
                if script.parent:
                    script.parent.updated_on = timezone.now()
                    script.parent.save()

                if script.script_folder:
                    script.script_folder.updated_on = timezone.now()
                    script.script_folder.save()

                script.word_count += length
                serializer.save()
                act.total_word += length
                act.save()
                script.updated_on = timezone.now()
                script.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to create scene", status=status.HTTP_401_UNAUTHORIZED)


class SceneRetrieveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_scene(self, scene_uuid, act):
        try:
            return Scene.objects.get(scene_uuid=scene_uuid, act=act)
        except Scene.DoesNotExist:
            return None

    def get_contributor(self, script, contributor, editor):
        if editor:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='script-editor',
                                               script_permission=True)
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor, script_permission=True)
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get_act(self, act_uuid, script):
        try:
            return Act.objects.get(act_uuid=act_uuid, script=script)
        except Act.DoesNotExist:
            return None

    def get(self, request, script_uuid, act_uuid, scene_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid=script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)
        act = self.get_act(act_uuid=act_uuid, script=script)
        if not act:
            return Response('No act found with this id', status=status.HTTP_400_BAD_REQUEST)
        contributor = self.get_contributor(script=script, contributor=user_data.get('user_id'), editor=False)
        if script.created_by == user_data.get('user_id') or contributor:
            scene = self.get_scene(scene_uuid, act)
            if not scene:
                return Response('No scene found with this id', status=status.HTTP_400_BAD_REQUEST)
            serializer = SceneSerializer(scene)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response("You don't have permission to create scene", status=status.HTTP_401_UNAUTHORIZED)

    def put(self, request, script_uuid, act_uuid, scene_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid=script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)
        contributor = self.get_contributor(script=script, contributor=user_data.get('user_id'), editor=True)
        if script.created_by == user_data.get('user_id') or contributor:
            act = self.get_act(act_uuid=act_uuid, script=script)
            if not act:
                return Response('No act found with this id', status=status.HTTP_400_BAD_REQUEST)

            scene = self.get_scene(scene_uuid=scene_uuid, act=act)
            if not scene:
                return Response('No scene found with this id', status=status.HTTP_400_BAD_REQUEST)
            length = 0
            if request.data.get('scene_header'):
                length = len(request.data.get('scene_header').split(' '))
            if request.data.get('action'):
                length += len(request.data.get('action').split(' '))
            if request.data.get('transaction_keyword'):
                length += len(request.data.get('transaction_keyword').split(' '))

            request.data['scene_length'] = length
            request.data['total_word'] = length
            serializer = SceneUpdateSerializer(scene, data=request.data, partial=True)
            outline = request.data.pop('outline', None)
            if serializer.is_valid():
                scene_no = request.data.get('scene_no')
                # checking if scene_no exist in this act. If exist it will upgrade the scene_no which is greater than
                # or equal to the scene_no
                if not outline and scene_no:
                    Scene.objects.filter(act=act, scene_no__gte=scene_no).update(scene_no=F('scene_no') + 1)

                if script.parent:
                    script.parent.updated_on = timezone.now()
                    script.parent.save()

                if script.script_folder:
                    script.script_folder.updated_on = timezone.now()
                    script.script_folder.save()

                script.word_count += scene.total_word - length
                serializer.save()
                create_script_activity(
                    {'action': 'update', 'message': f"{request.data.get('scene_uuid')} scene updated",
                     'details': {'created_by': user_data.get('user_id')}})
                script.updated_on = timezone.now()
                script.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to view this scene", status=status.HTTP_401_UNAUTHORIZED)

    def delete(self, request, script_uuid, act_uuid, scene_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid=script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)
        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)
        act = self.get_act(act_uuid=act_uuid, script=script)
        if not act:
            return Response('No act found with this id', status=status.HTTP_400_BAD_REQUEST)
        contributor = self.get_contributor(script=script, contributor=user_data.get('user_id'), editor=True)
        if script.created_by == user_data.get('user_id') or contributor:

            scene = self.get_scene(scene_uuid=scene_uuid, act=act)
            if not scene:
                return Response('No scene found with this id', status=status.HTTP_400_BAD_REQUEST)
            Scene.objects.filter(act=act, scene_no__gt=scene.scene_no).update(scene_no=F('scene_no') - 1)

            scene.delete()
            create_script_activity(
                {'action': 'delete', 'message': f"{request.data.get('scene_uuid')} scene deleted",
                 'details': {'created_by': user_data.get('user_id')}})

            if script.parent:
                script.parent.updated_on = timezone.now()
                script.parent.save()

            if script.script_folder:
                script.script_folder.updated_on = timezone.now()
                script.script_folder.save()

            Dialogue.objects.filter(scene=scene, script=script).delete()
            CharacterScene.objects.filter(scene=scene, script=script).delete()

            character_possession_update(script=script)

            script.word_count -= scene.total_word
            act.total_word -= scene.total_word
            act.save()
            script.updated_on = timezone.now()
            script.save()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response("You don't have permission to delete scene", status=status.HTTP_401_UNAUTHORIZED)


class LocationListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get_contributor(self, script, contributor, editor):
        if editor:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='script-editor',
                                               location=True)
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor, location=True)
        except Contributor.DoesNotExist:
            return None

    def get_location(self, script, location_uuid):
        try:
            return Location.objects.get(location_uuid=location_uuid, script=script)
        except Location.DoesNotExist:
            return None

    def get(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
                return Response("Please buy pro package. You don't have permission to create a script",
                                status=status.HTTP_400_BAD_REQUEST)
            script = Script.objects.create(**{'script_uuid': script_uuid, 'created_by': user_data.get('user_id')})
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int):
                update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
            create_script_activity({'action': 'create', 'message': 'new script created',
                                    'details': {'created_by': user_data.get('user_id')}})

        contributor = self.get_contributor(script, user_data.get('user_id'), False)
        if script.created_by == user_data.get('user_id') or contributor:
            locations = Location.objects.filter(script=script)
            serializer = LocationSerializer(locations, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response("You don't have permission to view this script", status=status.HTTP_401_UNAUTHORIZED)

    def put(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
                return Response("Please buy pro package. You don't have permission to create a script",
                                status=status.HTTP_400_BAD_REQUEST)
            script = Script.objects.create(**{'script_uuid': script_uuid, 'created_by': user_data.get('user_id')})
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int):
                update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
            create_script_activity({'action': 'create', 'message': 'new script created',
                                    'details': {'created_by': user_data.get('user_id')}})

        contributor = self.get_contributor(script, user_data.get('user_id'), True)
        if script.created_by == user_data.get('user_id') or contributor:
            location = self.get_location(location_uuid=request.data.get('location_uuid'), script=script)
            if location:
                serializer = LocationUpdateSerializer(location, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    create_script_activity(
                        {'action': 'update', 'message': f"{request.data.get('location_uuid')} updated",
                         'details': {'created_by': user_data.get('user_id')}})
                    return Response(serializer.data, status=status.HTTP_200_OK)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            request.data['script'] = script.id
            serializer = LocationSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                create_script_activity(
                    {'action': 'create', 'message': f"{request.data['location_uuid']} created",
                     'details': {'created_by': user_data.get('user_id')}})
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to view this script", status=status.HTTP_401_UNAUTHORIZED)


class LocationDeleteView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get_contributor(self, script, contributor, editor):
        if editor:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='script-editor',
                                               location=True)
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor, location=True)
        except Contributor.DoesNotExist:
            return None

    def get_location(self, script, location_uuid):
        try:
            return Location.objects.get(location_uuid=location_uuid, script=script)
        except Location.DoesNotExist:
            return None

    def delete(self, request, script_uuid, location_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
                return Response("Please buy pro package. You don't have permission to create a script",
                                status=status.HTTP_400_BAD_REQUEST)
            script = Script.objects.create(**{'script_uuid': script_uuid, 'created_by': user_data.get('user_id')})
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int):
                update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
            create_script_activity({'action': 'create', 'message': 'new script created',
                                    'details': {'created_by': user_data.get('user_id')}})

        contributor = self.get_contributor(script, user_data.get('user_id'), True)
        if script.created_by == user_data.get('user_id') or contributor:
            location = self.get_location(location_uuid=location_uuid, script=script)
            if not location:
                return Response(status=status.HTTP_204_NO_CONTENT)
            location.delete()
            create_script_activity(
                {'action': 'delete', 'message': f"{location_uuid} deleted",
                 'details': {'created_by': user_data.get('user_id')}})
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response("You don't have permission to view this script", status=status.HTTP_401_UNAUTHORIZED)


class ArcheTypeListCreate(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_scene(self, scene_uuid, act):
        try:
            return Scene.objects.get(scene_uuid=scene_uuid, act=act)
        except Scene.DoesNotExist:
            return None

    def get_contributor(self, script, contributor, co_writer):
        if co_writer:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='co-writer')
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor)
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), False)
        if script.created_by == user_data.get('user_id') or contributor:
            arche_type = ArcheType.objects.filter(script=script)
            serializer = ArcheTypeSerializer(arche_type, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response("You don't have permission to view arche type", status=status.HTTP_401_UNAUTHORIZED)

    def post(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), True)
        if script.created_by == user_data.get('user_id') or contributor:
            request.data['script'] = script.id
            request.data['slug'] = request.data.get('title').lower().replace(" ", "")
            serializer = ArcheTypeSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                create_script_activity(
                    {'action': 'create', 'message': f"{request.data.get('arche_type_uuid')} created",
                     'details': {'created_by': user_data.get('user_id')}})
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to add archetype", status=status.HTTP_401_UNAUTHORIZED)


class ArcheRetrieveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_contributor(self, script, contributor, co_writer):
        if co_writer:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='co-writer')
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor)
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get_arche_type(self, script, arche_type_uuid):
        try:
            return ArcheType.objects.get(script=script, arche_type_uuid=arche_type_uuid)
        except ArcheType.DoesNotExist:
            return None

    def get(self, request, script_uuid, arche_type_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), False)
        if script.created_by == user_data.get('user_id') or contributor:
            arche_type = self.get_arche_type(script, arche_type_uuid)
            serializer = ArcheTypeSerializer(arche_type)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response("You don't have permission to view this arche-type", status=status.HTTP_401_UNAUTHORIZED)

    def put(self, request, script_uuid, arche_type_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), False)
        if script.created_by == user_data.get('user_id') or contributor:
            arche_type = self.get_arche_type(script, arche_type_uuid)
            request.data['slug'] = request.data.get('title').lower().replace(" ", "")
            serializer = ArcheTypeUpdateSerializer(arche_type, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                create_script_activity(
                    {'action': 'update', 'message': f"{arche_type_uuid} updated",
                     'details': {'created_by': user_data.get('user_id')}})
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to edit this arche type", status=status.HTTP_401_UNAUTHORIZED)

    def delete(self, request, script_uuid, arche_type_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), False)
        if script.created_by == user_data.get('user_id') or contributor:
            arche_type = self.get_arche_type(script, arche_type_uuid)
            if arche_type:
                arche_type.delete()
                create_script_activity(
                    {'action': 'delete', 'message': f"{arche_type_uuid} deleted",
                     'details': {'created_by': user_data.get('user_id')}})
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response('No data found with this arche type uuid', status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to delete this arche type", status=status.HTTP_401_UNAUTHORIZED)


class CharacterListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_contributor(self, script, contributor, editor):
        if editor:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='script-editor',
                                               character=True)
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor, character=True)
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
                return Response("Please buy pro package. You don't have permission to create a script",
                                status=status.HTTP_400_BAD_REQUEST)
            script = Script.objects.create(**{'script_uuid': script_uuid, 'created_by': user_data.get('user_id')})
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int):
                update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
            create_script_activity({'action': 'create', 'message': 'new script created',
                                    'details': {'created_by': user_data.get('user_id')}})

        contributor = self.get_contributor(script, user_data.get('user_id'), False)
        if script.created_by == user_data.get('user_id') or contributor:
            characters = Character.objects.filter(script=script).order_by('-possession')
            serializer = CharacterSerializer(characters, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response("You don't have permission to view this character", status=status.HTTP_401_UNAUTHORIZED)

    def post(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
                return Response("Please buy pro package. You don't have permission to create a script",
                                status=status.HTTP_400_BAD_REQUEST)
            script = Script.objects.create(**{'script_uuid': script_uuid, 'created_by': user_data.get('user_id')})
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int):
                update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
            create_script_activity({'action': 'create', 'message': 'new script created',
                                    'details': {'created_by': user_data.get('user_id')}})

        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), True)
        if script.created_by == user_data.get('user_id') or contributor:
            try:
                character = Character.objects.get(name=request.data.get('name'), script=script)
                return Response("Character with this name already exist", status=status.HTTP_400_BAD_REQUEST)
            except Character.DoesNotExist:
                pass
            if request.data.get('image'):
                image_data = request.data.get('image')
                image_size = len(image_data.read())
                image_data.seek(0)  # Reset the file pointer to the beginning

                if image_size > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
                    return Response("Image file is too large to view", status=status.HTTP_400_BAD_REQUEST)

                compressed_image_data = compressed_image(image_data)
                request.data['image'] = compressed_image_data
            mutable_data = request.data.copy()

            if request.data.get('archetype'):
                try:
                    archetype = ArcheType.objects.get(title=request.data.get('archetype'), script=script)
                except ArcheType.DoesNotExist:
                    archetype = ArcheType.objects.create(arche_type_uuid=str(uuid.uuid4()),
                                                         title=request.data.get('archetype'),
                                                         slug=request.data.get('archetype').lower().replace(" ", ""),
                                                         script=script)
                mutable_data['archetype'] = archetype.id

            mutable_data['total_word'] = len(request.data.get('name').split(" "))
            mutable_data['script'] = script.id

            # Calculate the empty column ratio
            total_columns = Character._meta.fields  # All fields including primary key
            empty_columns = sum(
                1 for field in total_columns if field.name != 'id' and not mutable_data.get(field.name)
            )

            if len(total_columns) == 0:
                character_health = 0  # To avoid division by zero
            else:
                character_health = empty_columns / (len(total_columns) - 1)  # Excluding primary key

            mutable_data['character_health'] = round((1 - character_health) * 100, 2)
            serializer = CharacterSerializer(data=mutable_data)
            if serializer.is_valid():
                serializer.save()

                if script.parent:
                    script.parent.updated_on = timezone.now()
                    script.parent.save()

                if script.script_folder:
                    script.script_folder.updated_on = timezone.now()
                    script.script_folder.save()
                script.save()

                create_script_activity(
                    {'action': 'create', 'message': f"new character created",
                     'details': {'created_by': user_data.get('user_id')}})
                if script.created_by != user_data.get('user_id'):
                    create_notification(user=script.created_by, notification_type="activities",
                                        message=f"New character added in script {script.title}")
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to create character", status=status.HTTP_401_UNAUTHORIZED)


class CharacterRetrieveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]
    parser_classes = [MultiPartParser, FormParser]

    def get_contributor(self, script, contributor, editor):
        if editor:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='script-editor',
                                               character=True)
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor, character=True)
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get_character(self, script, character_uuid):
        try:
            return Character.objects.get(script=script, character_uuid=character_uuid)
        except Character.DoesNotExist:
            return None

    def get(self, request, script_uuid, character_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
                return Response("Please buy pro package. You don't have permission to create a script",
                                status=status.HTTP_400_BAD_REQUEST)
            script = Script.objects.create(**{'script_uuid': script_uuid, 'created_by': user_data.get('user_id')})
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int):
                update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
            create_script_activity({'action': 'create', 'message': 'new script created',
                                    'details': {'created_by': user_data.get('user_id')}})

        contributor = self.get_contributor(script, user_data.get('user_id'), False)
        if script.created_by == user_data.get('user_id') or contributor:
            character = self.get_character(script, character_uuid)
            if not character:
                return Response("No character found with this id", status=status.HTTP_400_BAD_REQUEST)
            serializer = CharacterSerializer(character)

            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response("You don't have permission to view this character", status=status.HTTP_401_UNAUTHORIZED)

    def put(self, request, script_uuid, character_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
                return Response("Please buy pro package. You don't have permission to create a script",
                                status=status.HTTP_400_BAD_REQUEST)
            script = Script.objects.create(**{'script_uuid': script_uuid, 'created_by': user_data.get('user_id')})
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int):
                update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
            create_script_activity({'action': 'create', 'message': 'new script created',
                                    'details': {'created_by': user_data.get('user_id')}})

        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), True)
        if script.created_by == user_data.get('user_id') or contributor:
            character = self.get_character(script, character_uuid)
            if not character:
                return Response("No character found with this id", status=status.HTTP_400_BAD_REQUEST)
            mutable_data = request.data.copy()
            if request.data.get('archetype'):
                try:
                    archetype = ArcheType.objects.get(title=request.data.get('archetype'), script=script)
                except ArcheType.DoesNotExist:
                    archetype = ArcheType.objects.create(arche_type_uuid=str(uuid.uuid4()),
                                                         title=request.data.get('archetype'),
                                                         slug=request.data.get('archetype').lower().replace(" ", ""),
                                                         script=script)
                mutable_data['archetype'] = archetype.id
            if request.data.get('name'):
                mutable_data['total_word'] = len(mutable_data.get('name').split(" "))

            serializer = CharacterUpdateSerializer(character, data=mutable_data, partial=True)
            if serializer.is_valid():
                serializer.save()
                # Calculate the empty column ratio
                total_columns = Character._meta.fields  # All fields including primary key
                empty_columns = sum(
                    1 for field in total_columns if field.name != 'id' and not request.data.get(field.name)
                )

                if len(total_columns) == 0:
                    character_health = 0  # To avoid division by zero
                else:
                    character_health = empty_columns / (len(total_columns) - 1)  # Excluding primary key

                # Update the character_health field
                character.character_health = round((1 - character_health) * 100, 2)
                character.save()
                if script.parent:
                    script.parent.updated_on = timezone.now()
                    script.parent.save()

                if script.script_folder:
                    script.script_folder.updated_on = timezone.now()
                    script.script_folder.save()
                script.save()

                create_script_activity(
                    {'action': 'update', 'message': f"{character_uuid} character updated",
                     'details': {'created_by': user_data.get('user_id')}})
                if script.created_by != user_data.get('user_id'):
                    create_notification(user=script.created_by, notification_type='activities',
                                        message=f"Your {script.title}'s {character.name} is updated")
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to edit this character", status=status.HTTP_401_UNAUTHORIZED)

    def delete(self, request, script_uuid, character_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
                return Response("Please buy pro package. You don't have permission to create a script",
                                status=status.HTTP_400_BAD_REQUEST)
            script = Script.objects.create(**{'script_uuid': script_uuid, 'created_by': user_data.get('user_id')})
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int):
                update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
            create_script_activity({'action': 'create', 'message': 'new script created',
                                    'details': {'created_by': user_data.get('user_id')}})

        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), True)
        if script.created_by == user_data.get('user_id') or contributor:
            character = self.get_character(script, character_uuid)
            if character:
                character_scene = CharacterScene.objects.filter(character=character)
                if character_scene:
                    character_scene.delete()
                    create_script_activity(
                        {'action': 'delete', 'message': f"{character_uuid}'s character scene deleted",
                         'details': {'created_by': user_data.get('user_id')}})

                character.dialogue_delete_and_update_total_word()
                create_script_activity(
                    {'action': 'delete', 'message': f"{character_uuid}'s character dialogue deleted",
                     'details': {'created_by': user_data.get('user_id')}})
                character.delete()
                character_possession_update(script)
                if script.parent:
                    script.parent.updated_on = timezone.now()
                    script.parent.save()

                if script.script_folder:
                    script.script_folder.updated_on = timezone.now()
                    script.script_folder.save()
                script.save()

                create_script_activity(
                    {'action': 'delete', 'message': f"{character_uuid} character deleted",
                     'details': {'created_by': user_data.get('user_id')}})
                if script.created_by != user_data.get('user_id'):
                    create_notification(user=script.created_by, notification_type='activities',
                                        message=f"Your {script.title}'s {character.name} has been deleted")
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response('No character found', status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to view this character", status=status.HTTP_401_UNAUTHORIZED)


class CharacterSceneListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_contributor(self, script, contributor, editor):
        if editor:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='script-editor',
                                               character=True)
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor, character=True)
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get_character(self, script, character_uuid):
        try:
            return Character.objects.get(script=script, character_uuid=character_uuid)
        except Character.DoesNotExist:
            return None

    def get(self, request, script_uuid, character_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
                return Response("Please buy pro package. You don't have permission to create a script",
                                status=status.HTTP_400_BAD_REQUEST)
            script = Script.objects.create(**{'script_uuid': script_uuid, 'created_by': user_data.get('user_id')})
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int):
                update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
            create_script_activity({'action': 'create', 'message': 'new script created',
                                    'details': {'created_by': user_data.get('user_id')}})

        contributor = self.get_contributor(script, user_data.get('user_id'), False)
        if script.created_by == user_data.get('user_id') or contributor:
            character = self.get_character(script=script, character_uuid=character_uuid)
            if not character:
                return Response("Character doesn't found", status=status.HTTP_400_BAD_REQUEST)

            character_scene = CharacterScene.objects.filter(character=character)
            serializer = CharacterSceneSerializer(character_scene, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response("You don't have permission to view this character", status=status.HTTP_401_UNAUTHORIZED)


class DialogueListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_contributor(self, script, contributor, editor):
        if editor:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='script-editor',
                                               script_permission=True)
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor, script_permission=True)
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get_scene(self, act, scene_uuid):
        try:
            return Scene.objects.get(act=act, scene_uuid=scene_uuid)
        except Scene.DoesNotExist:
            return None

    def get_act(self, script, act_uuid):
        try:
            return Act.objects.get(script=script, act_uuid=act_uuid)
        except Act.DoesNotExist:
            return None

    def get_character(self, script, name):
        try:
            return Character.objects.get(script=script, name=name)
        except Character.DoesNotExist:
            return None

    def character_handling(self, script, character_name, user_data):
        character = self.get_character(script=script, name=character_name)
        if not character:
            c = Character.objects.create(
                **{'name': character_name, 'character_uuid': uuid.uuid4(), 'script': script,
                   'character_health': round((7 / 18) * 100),
                   'total_word': len(character_name.split(" "))})
            create_script_activity({'action': 'create', 'message': f"character {c.character_uuid} created",
                                    'details': {'created_by': user_data.get('user_id')}})
            return c.id
        return character.id

    def character_scene_handling(self, scene, character, user_data, script):
        character_scene = CharacterScene.objects.filter(
            **{'scene__id': scene.id, 'character__id': character})
        if not character_scene:
            character_scene = CharacterScene.objects.create(
                **{'character_scene_uuid': uuid.uuid4(),
                   'character': Character.objects.get(id=character),
                   'scene': scene, 'script': script})
            character_scene.save()
            create_script_activity(
                {'action': 'create',
                 'message': f"character's scene {character_scene.character_scene_uuid} created",
                 'details': {'created_by': user_data.get('user_id')}})

    def get(self, request, script_uuid, act_uuid, scene_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
                return Response("Please buy pro package. You don't have permission to create a script",
                                status=status.HTTP_400_BAD_REQUEST)
            script = Script.objects.create(**{'script_uuid': script_uuid, 'created_by': user_data.get('user_id')})
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int):
                update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
            create_script_activity({'action': 'create', 'message': 'new script created',
                                    'details': {'created_by': user_data.get('user_id')}})

        contributor = self.get_contributor(script, user_data.get('user_id'), False)
        if script.created_by == user_data.get('user_id') or contributor:
            act = self.get_act(script=script, act_uuid=act_uuid)
            if not act:
                return Response("No act available", status=status.HTTP_400_BAD_REQUEST)
            scene = self.get_scene(act=act, scene_uuid=scene_uuid)
            if not scene:
                return Response('No scene available', status=status.HTTP_400_BAD_REQUEST)

            dialogues = Dialogue.objects.filter(scene=scene).order_by('dialogue_no')
            serializer = DialogueSerializer(dialogues, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response("You don't have permission to view dialogues", status=status.HTTP_401_UNAUTHORIZED)

    def post(self, request, script_uuid, act_uuid, scene_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
                return Response("Please buy pro package. You don't have permission to create a script",
                                status=status.HTTP_400_BAD_REQUEST)
            script = Script.objects.create(**{'script_uuid': script_uuid, 'created_by': user_data.get('user_id')})
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int):
                update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
            create_script_activity({'action': 'create', 'message': 'new script created',
                                    'details': {'created_by': user_data.get('user_id')}})

        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), True)
        if script.created_by == user_data.get('user_id') or contributor:
            act = self.get_act(script=script, act_uuid=act_uuid)
            if not act:
                return Response("No act available", status=status.HTTP_400_BAD_REQUEST)
            scene = self.get_scene(act=act, scene_uuid=scene_uuid)
            if not scene:
                return Response('No scene available', status=status.HTTP_400_BAD_REQUEST)

            if request.data.get('character'):
                character = self.character_handling(script=script, character_name=request.data.get('character'),
                                                    user_data=user_data)
                request.data['character'] = character
            request.data['scene'] = scene.id
            request.data['script'] = script.id
            total_word = 0
            if request.data.get('line'):
                total_word += len(request.data.get('line').split(" "))
            if request.data.get('parenthetical'):
                total_word += len(request.data.get('parenthetical').split(" "))
            dialogue_no = request.data.get('dialogue_no')
            if request.data.get('dual'):
                dual_character = self.character_handling(script=script,
                                                         character_name=request.data.get('dual_character'),
                                                         user_data=user_data)
                request.data['dual_character'] = dual_character
                total_word += len(request.data.get('dual_line').split(" "))
                if request.data.get('dual_parenthetical'):
                    total_word += len(request.data.get('dual_parenthetical').split(" "))
            request.data['total_word'] = total_word
            serializer = DialogueSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                if dialogue_no:
                    Dialogue.objects.filter(scene=scene, dialogue_no__gte=dialogue_no).update(
                        dialogue_no=F('dialogue_no') + 1)
                self.character_scene_handling(scene=scene, character=request.data.get('character'), user_data=user_data,
                                              script=script)
                updating_character = Character.objects.get(id=request.data.get('character'))
                updating_character.possession = round((Dialogue.objects.filter(script=script,
                                                                               character=updating_character).count() / Dialogue.objects.filter(
                    script=script).count()) * 100)
                updating_character.save()

                if request.data.get('dual'):
                    self.character_scene_handling(scene=scene, character=request.data.get('dual_character'),
                                                  user_data=user_data, script=script)
                    dual_character_update = Character.objects.get(id=request.data.get('dual_character'))
                    dual_character_update.possession = round((Dialogue.objects.filter(script=script,
                                                                                      character=dual_character_update).count() / Dialogue.objects.filter(
                        script=script).count()) * 100)
                    dual_character_update.save()

                scene.total_word += total_word
                scene.scene_length += total_word  # Adjust this according to your calculation logic
                scene.save()

                # Update the Act's total_word with scene_length
                act.total_word += total_word  # Add scene_length to the act's total_word
                act.save()

                # Extract the associated Script from the Act
                # Update the Script's word_count with the act's total_word
                script.word_count += total_word  # Add act's total_word to the script's word_count
                if script.parent:
                    script.parent.updated_on = timezone.now()
                    script.parent.save()

                if script.script_folder:
                    script.script_folder.updated_on = timezone.now()
                    script.script_folder.save()

                script.updated_on = timezone.now()
                script.save()

                create_script_activity(
                    {'action': 'create', 'message': f"dialogue {request.data.get('dialogue_uuid')} created",
                     'details': {'created_by': user_data.get('user_id')}})
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to create dialogue", status=status.HTTP_401_UNAUTHORIZED)


class DialogueRetrieveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_contributor(self, script, contributor, editor):
        if editor:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='script-editor',
                                               script_permission=True)
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor, script_permission=True)
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get_act(self, script, act_uuid):
        try:
            return Act.objects.get(script=script, act_uuid=act_uuid)
        except Act.DoesNotExist:
            return None

    def get_scene(self, act, scene_uuid):
        try:
            return Scene.objects.get(act=act, scene_uuid=scene_uuid)
        except Scene.DoesNotExist:
            return None

    def get_dialogue(self, scene, dialogue_uuid):
        try:
            return Dialogue.objects.get(scene=scene, dialogue_uuid=dialogue_uuid)
        except Dialogue.DoesNotExist:
            return None

    def get_character(self, script, name):
        try:
            return Character.objects.get(script=script, name=name)
        except Character.DoesNotExist:
            return None

    def character_handling(self, script, character_name, user_data):
        character = self.get_character(script=script, name=character_name)
        if not character:
            c = Character.objects.create(
                **{'name': character_name, 'character_uuid': uuid.uuid4(), 'script': script,
                   'total_word': len(character_name.split()),
                   'character_map': '''{"inputValue1":"Bold, audacious.","inputValue2":"Wears leather jackets.",
                   "inputValue3":"PTSD, anxious.","inputValue4":"Always smoking.","inputValue5":"a bit of a brute!",
                   "inputValue6":"Hi This is Test","inputValue7":"6 foot 3.","inputValue8":"Speak French and 
                   Spanish.","inputValue9":"Very polite to his elders when he has to be.","inputValue10":"Wise",
                   "inputValue11":"Protective over family.","inputValue12":"Ready to fight.","inputValue13":"Slight 
                   limp when he walks.","inputValue14":"Worker Bee!"}'''})
            create_script_activity({'action': 'create', 'message': f"character {c.character_uuid} created",
                                    'details': {'created_by': user_data.get('user_id')}})
            return c.id
        return character.id

    def character_scene_handling(self, scene, character, user_data, script):
        character_scene = CharacterScene.objects.filter(
            **{'scene__id': scene.id, 'character__id': character})
        if not character_scene:
            character_scene = CharacterScene.objects.create(
                **{'character_scene_uuid': uuid.uuid4(),
                   'character': Character.objects.get(id=character),
                   'scene': scene, 'script': script})
            character_scene.save()
            create_script_activity(
                {'action': 'create',
                 'message': f"character's scene {character_scene.character_scene_uuid} created",
                 'details': {'created_by': user_data.get('user_id')}})

    def get(self, request, script_uuid, act_uuid, scene_uuid, dialogue_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), False)
        if script.created_by == user_data.get('user_id') or contributor:
            act = self.get_act(script=script, act_uuid=act_uuid)
            if not act:
                return Response("No act available", status=status.HTTP_400_BAD_REQUEST)
            scene = self.get_scene(act=act, scene_uuid=scene_uuid)
            if not scene:
                return Response('No scene available', status=status.HTTP_400_BAD_REQUEST)

            dialogue = self.get_dialogue(scene=scene, dialogue_uuid=dialogue_uuid)
            if not dialogue:
                return Response("No dialogue found in this uuid", status=status.HTTP_400_BAD_REQUEST)
            serializer = DialogueSerializer(dialogue)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response("You don't have permission to view dialogue", status=status.HTTP_401_UNAUTHORIZED)

    def put(self, request, script_uuid, act_uuid, scene_uuid, dialogue_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), True)
        if script.created_by == user_data.get('user_id') or contributor:
            act = self.get_act(script=script, act_uuid=act_uuid)
            if not act:
                return Response("No act available", status=status.HTTP_400_BAD_REQUEST)
            scene = self.get_scene(act=act, scene_uuid=scene_uuid)
            if not scene:
                return Response('No scene available', status=status.HTTP_400_BAD_REQUEST)

            dialogue = self.get_dialogue(scene=scene, dialogue_uuid=dialogue_uuid)
            if not dialogue:
                return Response("No dialogue found in this uuid", status=status.HTTP_400_BAD_REQUEST)

            if request.data.get('character'):
                character = self.character_handling(script=script, character_name=request.data.get('character'),
                                                    user_data=user_data)
                request.data['character'] = character

            total_word = 0
            if request.data.get('line'):
                total_word += len(request.data.get('line').split(" "))
            if request.data.get('parenthetical'):
                total_word += len(request.data.get('parenthetical').split(" "))

            if request.data.get('dual') and request.data['dual'] != dialogue.dual:
                if request.data.get('dual'):
                    dual_character = self.character_handling(script=script,
                                                             character_name=request.data.get('dual_character'),
                                                             user_data=user_data)
                    request.data['dual_character'] = dual_character
                    total_word += len(request.data.get('dual_line').split(" "))
            if request.data.get('dual_character'):
                if request.data.get('dual_character') != dialogue.dual_character:
                    dual_character = self.character_handling(script=script,
                                                             character_name=request.data.get('dual_character'),
                                                             user_data=user_data)
                    request.data['dual_character'] = dual_character
            if request.data.get('dual_parenthetical'):
                total_word += len(request.data.get('dual_parenthetical').split(" "))

            serializer = DialogueUpdateSerializer(dialogue, data=request.data, partial=True)
            dialogue_no = request.data.get('dialogue_no')
            if serializer.is_valid():
                if dialogue_no:
                    Dialogue.objects.filter(scene=scene, dialogue_no__gte=dialogue_no).update(
                        dialogue_no=F('dialogue_no') + 1)
                if request.data.get('character'):
                    self.character_scene_handling(scene=scene, character=request.data.get('character'),
                                                  user_data=user_data, script=script)
                    updating_character = Character.objects.get(id=request.data.get('character'))
                    updating_character.possession = round((Dialogue.objects.filter(script=script,
                                                                                   character=updating_character).count() / Dialogue.objects.filter(
                        script=script).count()) * 100)
                    updating_character.save()

                if request.data.get('dual'):
                    self.character_scene_handling(scene=scene, character=request.data.get('dual_character'),
                                                  user_data=user_data, script=script)
                    dual_character_update = Character.objects.get(id=request.data.get('dual_character'))
                    dual_character_update.possession = round((Dialogue.objects.filter(script=script,
                                                                                      character=dual_character_update).count() / Dialogue.objects.filter(
                        script=script).count()) * 100)
                    dual_character_update.save()

                scene.total_word += total_word - dialogue.total_word
                scene.scene_length += total_word - dialogue.total_word  # Adjust this according to your calculation logic
                scene.save()

                # Extract the associated Act
                # Update the Act's total_word with scene_length
                act.total_word += total_word - dialogue.total_word  # Add scene_length to the act's total_word
                act.save()

                # Extract the associated Script from the Act
                # Update the Script's word_count with the act's total_word
                script.word_count += total_word - dialogue.total_word  # Add act's total_word to the script's
                # word_count
                if script.parent:
                    script.parent.updated_on = timezone.now()
                    script.parent.save()

                if script.script_folder:
                    script.script_folder.updated_on = timezone.now()
                    script.script_folder.save()

                script.updated_on = timezone.now()
                script.save()
                serializer.save()

                create_script_activity(
                    {'action': 'update', 'message': f"dialogue {dialogue_uuid} updated",
                     'details': {'created_by': user_data.get('user_id')}})
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to view dialogues", status=status.HTTP_401_UNAUTHORIZED)

    def delete(self, request, script_uuid, act_uuid, scene_uuid, dialogue_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), True)
        if script.created_by == user_data.get('user_id') or contributor:
            act = self.get_act(script=script, act_uuid=act_uuid)
            if not act:
                return Response("No act available", status=status.HTTP_400_BAD_REQUEST)
            scene = self.get_scene(act=act, scene_uuid=scene_uuid)
            if not scene:
                return Response('No scene available', status=status.HTTP_400_BAD_REQUEST)

            dialogue = self.get_dialogue(scene=scene, dialogue_uuid=dialogue_uuid)
            if not dialogue:
                return Response("No dialogue found in this uuid", status=status.HTTP_400_BAD_REQUEST)

            dialogue.delete()
            scene.total_word -= dialogue.total_word
            scene.scene_length -= dialogue.total_word  # Adjust this according to your calculation logic
            scene.save()

            # Extract the associated Act
            act = scene.act

            # Update the Act's total_word with scene_length
            act.total_word -= dialogue.total_word  # Add scene_length to the act's total_word
            act.save()

            # Extract the associated Script from the Act
            script = act.script

            # Update the Script's word_count with the act's total_word
            script.word_count -= dialogue.total_word  # Add act's total_word to the script's
            # word_count
            script.updated_on = timezone.now()
            script.save()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response("You don't have permission to view dialogues", status=status.HTTP_401_UNAUTHORIZED)


class CommentListView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_contributor(self, script, contributor, editor):
        if editor:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='script-editor',
                                               script_permission=True)
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor, script_permission=True)
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        script = self.get_script(script_uuid=script_uuid)
        if not script:
            subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
                return Response("Please buy pro package. You don't have permission to create a script",
                                status=status.HTTP_400_BAD_REQUEST)
            script = Script.objects.create(**{'script_uuid': script_uuid, 'created_by': user_data.get('user_id')})
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int):
                update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
            create_script_activity({'action': 'create', 'message': 'new script created',
                                    'details': {'created_by': user_data.get('user_id')}})

        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), False)
        if script.created_by == user_data.get('user_id') or contributor:
            comments = Comment.objects.filter(script=script).order_by('-created_on')
            serializer = CommentSerializer(comments, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(status=status.HTTP_200_OK)


def create_comment(data):
    data['updated_on'] = datetime.datetime.now()
    serializer = CommentSerializer(data=data)
    if serializer.is_valid():
        serializer.save()
        return serializer.data, True
    return serializer.errors, False


class CreateScriptComment(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_contributor(self, script, contributor, editor):
        try:
            return Contributor.objects.get(script=script, contributor=contributor, script_permission=True)
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get_scene(self, scene_uuid, script):
        try:
            return Scene.objects.get(scene_uuid=scene_uuid, script=script)
        except Scene.DoesNotExist:
            return None

    def get_dialogue(self, script, dialogue_uuid):
        try:
            return Dialogue.objects.get(dialogue_uuid=dialogue_uuid, script=script)
        except Dialogue.DoesNotExist:
            return None

    def get_comment(self, script, comment_uuid):
        try:
            return Comment.objects.get(comment_uuid=comment_uuid, script=script)
        except Comment.DoesNotExist:
            return None

    def post(self, request, script_uuid, object_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        script = self.get_script(script_uuid)
        if not script:
            subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
                return Response("Please buy pro package. You don't have permission to create a script",
                                status=status.HTTP_400_BAD_REQUEST)
            script = Script.objects.create(**{'script_uuid': script_uuid, 'created_by': user_data.get('user_id')})
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int):
                update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
            create_script_activity({'action': 'create', 'message': 'new script created',
                                    'details': {'created_by': user_data.get('user_id')}})

        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), False)
        if script.created_by == user_data.get('user_id') or contributor:
            comment = self.get_comment(comment_uuid=request.data['comment_uuid'], script=script)
            if comment:
                request.data['updated_on'] = datetime.datetime.now()
                comment_serializer = CommentUpdateSerializer(comment, data=request.data, partial=True)
                if comment_serializer.is_valid():
                    comment_serializer.save()
                    return Response(comment_serializer.data, status=status.HTTP_200_OK)
                return Response(comment_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            scene = self.get_scene(scene_uuid=object_uuid, script=script)
            request.data['created_by'] = user_data.get('user_id')
            request.data['script'] = script.id
            if scene:
                comment_data, s = create_comment(data=request.data)
                if s:
                    scene.comment = Comment.objects.get(id=comment_data['id'])
                    scene.save()
                    commenter_full_name = fetch_user_with_id(id=user_data.get('user_id'))['full_name']
                    create_notification(user=script.created_by, notification_type='comment',
                                        message=f"{commenter_full_name} has been commented on you {script.title}'s scene")
                    return Response(comment_data, status=status.HTTP_201_CREATED)
                return Response(comment_data, status=status.HTTP_400_BAD_REQUEST)

            dialogue = self.get_dialogue(dialogue_uuid=object_uuid, script=script)
            if not dialogue:
                return Response("No dialogue or scene found", status=status.HTTP_400_BAD_REQUEST)
            comment_data, s = create_comment(data=request.data)
            if s:
                dialogue.comment = Comment.objects.get(id=comment_data['id'])
                dialogue.save()
                commenter_full_name = fetch_user_with_id(id=user_data.get('user_id'))['full_name']
                create_notification(user=script.created_by, notification_type='comment',
                                    message=f"{commenter_full_name} has been commented on you {script.title}'s dialogue")
                return Response(comment_data, status=status.HTTP_201_CREATED)
            return Response(comment_data, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to view dialogues", status=status.HTTP_401_UNAUTHORIZED)


class CommentRetrieveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_contributor(self, script, contributor, editor):
        try:
            return Contributor.objects.get(script=script, contributor=contributor, script_permission=True)
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get_comment(self, comment_uuid):
        try:
            return Comment.objects.get(comment_uuid=comment_uuid)
        except Comment.DoesNotExist:
            return None

    def get(self, request, script_uuid, comment_uuid):
        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

        comment = self.get_comment(comment_uuid=comment_uuid)
        if not comment:
            return Response("Comment doesn't exist", status=status.HTTP_400_BAD_REQUEST)
        serializer = CommentSerializer(comment)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, script_uuid, comment_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), False)
        if script.created_by == user_data.get('user_id') or contributor:
            comment = self.get_comment(comment_uuid=comment_uuid)
            if not comment:
                return Response("No comment found", status=status.HTTP_400_BAD_REQUEST)

            if comment.created_by != user_data.get('user_id'):
                return Response("You don't have permission to edit this comment", status=status.HTTP_401_UNAUTHORIZED)
            request.data['updated_on'] = datetime.datetime.now()
            serializer = CommentUpdateSerializer(comment, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to edit comment", status=status.HTTP_401_UNAUTHORIZED)

    def delete(self, request, script_uuid, comment_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), False)
        if script.created_by == user_data.get('user_id') or contributor:
            comment = self.get_comment(comment_uuid=comment_uuid)
            if not comment:
                return Response(status=status.HTTP_204_NO_CONTENT)
            if comment.created_by != user_data.get('user_id'):
                return Response("You don't have permission to delete this comment", status=status.HTTP_401_UNAUTHORIZED)
            comment.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response("You don't have permission to delete comment", status=status.HTTP_401_UNAUTHORIZED)


class ScriptFolderCreateView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get(self, request):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        folders = ScriptFolder.objects.filter(created_by=user_data.get('user_id')).order_by('-updated_on')
        serializer = ScriptFolderSerializer(folders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        if not request.data.get('title'):
            request.data['title'] = request.data['script_folder_uuid']
        request.data['created_by'] = user_data.get('user_id')
        serializer = ScriptFolderSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            create_script_activity(
                {'action': 'create',
                 'message': f"script folder created",
                 'details': {'created_by': user_data.get('user_id')}})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ScriptFolderRetrieveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_folder(self, script_folder_uuid, created_by):
        try:
            return ScriptFolder.objects.get(script_folder_uuid=script_folder_uuid, created_by=created_by)
        except ScriptFolder.DoesNotExist:
            return None

    def get(self, request, script_folder_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        folder = self.get_folder(script_folder_uuid=script_folder_uuid, created_by=user_data.get('user_id'))
        if not folder:
            return Response("There is no folder with this id", status=status.HTTP_400_BAD_REQUEST)
        scripts = Script.objects.filter(script_folder=folder, created_by=user_data.get('user_id'), parent=None)
        serializer = ScriptSerializer(scripts, many=True)
        return Response(serializer.data)

    def put(self, request, script_folder_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        folder = self.get_folder(script_folder_uuid=script_folder_uuid, created_by=user_data.get('user_id'))
        if not folder:
            return Response("There is no folder with this id", status=status.HTTP_400_BAD_REQUEST)
        serializer = ScriptFolderUpdateSerializer(folder, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            folder.updated_on = timezone.now()
            folder.save()
            create_script_activity(
                {'action': 'update',
                 'message': f"folder {folder.script_folder_uuid} has been updated",
                 'details': {'created_by': user_data.get('user_id')}})
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, script_folder_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        folder = self.get_folder(script_folder_uuid=script_folder_uuid, created_by=user_data.get('user_id'))
        if not folder:
            return Response("There is no folder with this id", status=status.HTTP_400_BAD_REQUEST)

        scripts = Script.objects.filter(script_folder=folder, created_by=user_data.get('user_id'))
        scripts.delete()
        folder.delete()
        create_script_activity(
            {'action': 'delete',
             'message': f"script folder {folder.title} has been deleted",
             'details': {'created_by': user_data.get('user_id')}})
        return Response(status=status.HTTP_204_NO_CONTENT)


class MoveScriptToFolder(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_folder(self, script_folder_uuid, user):
        try:
            return ScriptFolder.objects.get(script_folder_uuid=script_folder_uuid, created_by=user)
        except ScriptFolder.DoesNotExist:
            return None

    def get_script(self, script_uuid, user):
        try:
            return Script.objects.get(script_uuid=script_uuid, created_by=user)
        except Script.DoesNotExist:
            return None

    def put(self, request):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        folder = self.get_folder(request.data.get('script_folder_uuid'), user_data.get('user_id'))
        if not folder:
            return Response("No folder found with this id", status=status.HTTP_400_BAD_REQUEST)
        script = self.get_script(request.data.get('script_uuid'), user_data.get('user_id'))
        if not script:
            return Response("No script found with this id", status=status.HTTP_400_BAD_REQUEST)

        script.script_folder = folder
        script.save()
        Script.objects.filter(parent=script, created_by=user_data.get('user_id')).update(
            script_folder=folder)
        serializer = ScriptSerializer(script)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ScriptOutlineView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_object(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_object(script_uuid=script_uuid)
        data = []
        if not script:
            return Response(data, status=status.HTTP_200_OK)

        acts = Act.objects.filter(script=script).order_by('act_no')

        data = []
        for act in acts:
            scenes = Scene.objects.filter(act=act, script=script).order_by('scene_no')
            act_body = []
            for scene in scenes:
                act_body.append(SceneSerializer(scene).data)
            data.append({'actHead': act.title, 'actUUID': act.act_uuid, 'actNo': act.act_no, 'actBody': act_body})

        return Response(data, status=status.HTTP_200_OK)

    def put(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_object(script_uuid=script_uuid)
        if not script:
            return Response([], status=status.HTTP_200_OK)

        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)
        subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
        if not json.loads(subscription['permission'])["outline_edit"]:
            return Response("Please buy pro package. You don't have permission to create a script",
                            status=status.HTTP_400_BAD_REQUEST)
        for data in request.data:
            scene = Scene.objects.get(pk=data['id'])
            serializer = SceneUpdateSerializer(scene, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()

                if script.parent:
                    script.parent.updated_on = timezone.now()
                    script.parent.save()

                if script.script_folder:
                    script.script_folder.updated_on = timezone.now()
                    script.script_folder.save()

                create_script_activity(
                    {'action': 'update', 'message': f"{scene.scene_uuid} scene updated",
                     'details': {'created_by': user_data.get('user_id')}})

                script.updated_on = timezone.now()
                script.save()
            else:
                return Response("Something Went Wrong", status=status.HTTP_400_BAD_REQUEST)

        return Response("successfully updated", status=status.HTTP_200_OK)


class TestingCursor(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get(self, request):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        # data = fetch_user_with_email(email=email)
        data = fetch_user_with_id(id=user_data.get('user_id'))['full_name']
        print(data)
        # print(data.__dir__())
        return Response("done")


class NotificationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get(self, request):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        notifications = ScriptNotification.objects.filter(user=user_data.get('user_id')).order_by('-created_on')[:15]
        serializer = ScriptNotificationSerializer(notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        ScriptNotification.objects.filter(read=False, user=user_data.get('user_id')).update(read=True)
        data = ScriptNotification.objects.filter(user=user_data.get('user_id')).order_by('-created_on')[:15]
        serializer = ScriptNotificationSerializer(data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PendingScriptView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get(self, request):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        role_id = fetch_user_with_id(id=user_data.get('user_id'))['role_id']
        fetch_role = fetch_role_with_user_id(role_id)['slug']
        if fetch_role == 'admin':
            pending_scripts_list = Script.objects.filter(script_condition='Pending').order_by('-updated_on')
            serializer = ScriptSerializer(pending_scripts_list, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response("No permission", status=status.HTTP_403_FORBIDDEN)


class PendingScriptConditionChange(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def put(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        role_id = fetch_user_with_id(id=user_data.get('user_id'))['role_id']
        fetch_role = fetch_role_with_user_id(role_id)['slug']
        if fetch_role == 'admin':
            script = Script.objects.get(script_uuid=script_uuid)
            Script.objects.filter(script_uuid=script_uuid).update(
                script_condition=request.data.get('script_condition'))
            create_notification(user=script.created_by, message=f"script {script.title} has been updated",
                                notification_type='register')
            return Response(status=status.HTTP_200_OK)
        return Response("No permission", status=status.HTTP_403_FORBIDDEN)


class SubmitScriptForRegister(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def put(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        try:
            script = Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return Response("script doesn't exist", status=status.HTTP_400_BAD_REQUEST)

        if script and script.created_by != user_data.get('user_id'):
            return Response("You don't have permission to perform this action", status=status.HTTP_400_BAD_REQUEST)
        try:
            intent = stripe.PaymentIntent.create(amount=request.data['amount'], currency='usd',
                                                 automatic_payment_methods={
                                                     'enabled': True,
                                                 }, )
            return Response({
                'clientSecret': intent['client_secret']
            }, status=status.HTTP_200_OK)
        except stripe.error.CardError as e:
            print(e)
            return Response(str(e), status=status.HTTP_403_FORBIDDEN)


class ScriptRegisterTransactionView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def put(self, request, transaction_status, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        if transaction_status == 'success':
            Script.objects.filter(script_uuid=script_uuid).update(script_condition='Pending')
            create_notification(user=user_data.get('user_id'), message='script has been submitted for register',
                                notification_type='register')
            return Response("Your script submitted for register", status=status.HTTP_200_OK)
        return Response("Transaction failed", status=status.HTTP_400_BAD_REQUEST)


class ScriptStructureSceneView(APIView):
    permission_classes = [AllowAny]  # Allow any user to access this view
    authentication_classes = [TokenAuthentication]  # Use Token Authentication for user authentication

    def get_object(self, script_uuid):
        try:
            # Try to retrieve a Script object based on script_uuid and created_by
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get(self, request, script_uuid):
        user_data = get_user_id(request)

        # Check if a valid user ID is obtained from the request
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        # Fetch the subscription plan for the user and check if the 'structure page' permission is set to 'Yes'
        subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
        if subscription:
            if not json.loads(subscription.get('permission'))['structure_guide']:
                return Response("Please buy the pro subscription pack", status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response("Please buy the pro subscription pack", status=status.HTTP_400_BAD_REQUEST)

        # Get the Script object based on the script_uuid and user ID
        script = self.get_object(script_uuid=script_uuid)

        # Check if a script with the given ID exists
        data = []
        if not script:
            return Response(data, status=status.HTTP_200_OK)

        # Retrieve Acts associated with the script, along with their scenes and character information
        acts = Act.objects.filter(script=script).order_by('act_no')
        for index, act in enumerate(acts):
            scenes = Scene.objects.filter(act=act, script=script).order_by('scene_no')
            s = []
            for scene in scenes:
                character = []
                for c in CharacterScene.objects.filter(scene=scene, script=script):
                    character.append(c.character.name)
                s.append({
                    'scene_header': scene.scene_header,
                    'page': scene.page_no,
                    'scene_length': scene.scene_length,
                    'emotional_value': scene.emotional_value,
                    'characters': character
                })
            data.append({
                'act_header': act.title,
                'act_length': act.total_word,
                'scenes': s
            })

        return Response(data, status=status.HTTP_200_OK)


class ScriptStructureCharacterView(APIView):
    permission_classes = [AllowAny]  # Allow any user to access this view
    authentication_classes = [TokenAuthentication]  # Use Token Authentication for user authentication

    def get_object(self, script_uuid):
        try:
            # Try to retrieve a Script object based on script_uuid and created_by
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get(self, request, script_uuid):
        user_data = get_user_id(request)

        # Check if a valid user ID is obtained from the request
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        # Fetch the subscription plan for the user and check if the 'structure page' permission is set to 'Yes'
        subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
        if subscription:
            if not json.loads(subscription.get('permission'))['structure_guide']:
                return Response("Please buy the pro subscription pack", status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response("Please buy the pro subscription pack", status=status.HTTP_400_BAD_REQUEST)

        script = self.get_object(script_uuid=script_uuid)
        # Check if a script with the given ID exists
        if not script:
            return Response(
                {'character': [], 'script': {'title': "", 'run_time': 0,
                                             'page_count': 0,
                                             'project_health': 0,
                                             'number_of_words': 0}},
                status=status.HTTP_200_OK)
        # get the characters based on script
        characters = Character.objects.filter(script=script).order_by('possession')

        data = CharacterStructureSerializer(characters, many=True)
        health = 0
        for index, d in enumerate(data.data):
            health += d.get('character_health')
        return Response(
            {'character': data.data, 'script': {'title': script.title, 'run_time': script.number_of_pages,
                                                'page_count': script.number_of_pages,
                                                'project_health': health // len(data.data),
                                                'number_of_words': script.word_count}},
            status=status.HTTP_200_OK)


class CharacterImageRetrieveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]
    parser_classes = [MultiPartParser, FormParser]

    def get_contributor(self, script, contributor, editor):
        if editor:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='script-editor',
                                               character=True)
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor, character=True)
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get_character(self, script, character_uuid):
        try:
            return Character.objects.get(script=script, character_uuid=character_uuid)
        except Character.DoesNotExist:
            return None

    def get(self, request, script_uuid, character_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
                return Response("Please buy pro package. You don't have permission to create a script",
                                status=status.HTTP_400_BAD_REQUEST)
            script = Script.objects.create(**{'script_uuid': script_uuid, 'created_by': user_data.get('user_id')})
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int):
                update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
            create_script_activity({'action': 'create', 'message': 'new script created',
                                    'details': {'created_by': user_data.get('user_id')}})

        contributor = self.get_contributor(script, user_data.get('user_id'), False)
        if script.created_by == user_data.get('user_id') or contributor:
            character = self.get_character(script, character_uuid)
            serializer = CharacterImageSerializer(character)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response("You don't have permission to view.", status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, script_uuid, character_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
                return Response("Please buy pro package. You don't have permission to create a script",
                                status=status.HTTP_400_BAD_REQUEST)
            script = Script.objects.create(**{'script_uuid': script_uuid, 'created_by': user_data.get('user_id')})
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int):
                update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
            create_script_activity({'action': 'create', 'message': 'new script created',
                                    'details': {'created_by': user_data.get('user_id')}})

        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), True)
        if script.created_by == user_data.get('user_id') or contributor:
            character = self.get_character(script, character_uuid)
            if not character:
                return Response("There is no character by this id", status=status.HTTP_400_BAD_REQUEST)
            if request.data.get('image'):
                image_data = request.data.get('image')
                image_size = len(image_data.read())
                image_data.seek(0)  # Reset the file pointer to the beginning

                if image_size > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
                    return Response("Image file is too large to save", status=status.HTTP_400_BAD_REQUEST)

                compressed_image_data = compressed_image(image_data)
                request.data['image'] = compressed_image_data
                mutable_data = request.data.copy()

                serializer = CharacterImageSerializer(character, data=mutable_data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    if script.parent:
                        script.parent.updated_on = timezone.now()
                        script.parent.save()

                    if script.script_folder:
                        script.script_folder.updated_on = timezone.now()
                        script.script_folder.save()
                    script.save()

                    create_script_activity(
                        {'action': 'update', 'message': f"{character_uuid} character updated",
                         'details': {'created_by': user_data.get('user_id')}})
                    if script.created_by != user_data.get('user_id'):
                        create_notification(user=script.created_by, notification_type='activities',
                                            message=f"Your {script.title}'s {character.name} is updated")

                    return Response(serializer.data, status=status.HTTP_200_OK)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CharacterNameSearch(APIView):
    permission_classes = [AllowAny]  # Allow any user to access this view
    authentication_classes = [TokenAuthentication]  # Use Token Authentication for user authentication

    def get_contributor(self, script, contributor, editor):
        if editor:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='script-editor',
                                               character=True)
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor, character=True)
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get(self, request, script_uuid, character_name):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), False)
        if script.created_by == user_data.get('user_id') or contributor:
            character = Character.objects.filter(name__icontains=character_name, script=script)
            serializer = CharacterNameSearchSerializer(character, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response("You don't have permission to view.", status=status.HTTP_400_BAD_REQUEST)


class CharacterNameGet(APIView):
    permission_classes = [AllowAny]  # Allow any user to access this view
    authentication_classes = [TokenAuthentication]  # Use Token Authentication for user authentication

    def get_contributor(self, script, contributor, editor):
        if editor:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='script-editor',
                                               character=True)
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor, character=True)
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
                return Response("Please buy pro package. You don't have permission to create a script",
                                status=status.HTTP_400_BAD_REQUEST)
            script = Script.objects.create(**{'script_uuid': script_uuid, 'created_by': user_data.get('user_id')})
            if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                          int):
                update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
            create_script_activity({'action': 'create', 'message': 'new script created',
                                    'details': {'created_by': user_data.get('user_id')}})

        contributor = self.get_contributor(script, user_data.get('user_id'), False)
        if script.created_by == user_data.get('user_id') or contributor:
            character = Character.objects.filter(script=script)
            serializer = CharacterNameSearchSerializer(character, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response("You don't have permission to view.", status=status.HTTP_400_BAD_REQUEST)


class ActSceneCreateView(APIView):
    permission_classes = [AllowAny]  # Allow any user to access this view
    authentication_classes = [TokenAuthentication]  # Use Token Authentication for user authentication

    def get_contributor(self, script, contributor, editor):
        if editor:
            try:
                return Contributor.objects.get(script=script, contributor=contributor, contributor_role='script-editor',
                                               script_permission=True)
            except Contributor.DoesNotExist:
                return None
        try:
            return Contributor.objects.get(script=script, contributor=contributor, script_permission=True)
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get_act(self, act_uuid, script):
        try:
            return Act.objects.get(act_uuid=act_uuid, script=script)
        except Act.DoesNotExist:
            return None

    def get_scene(self, scene_uuid, script):
        try:
            return Scene.objects.get(scene_uuid=scene_uuid, script=script)
        except Scene.DoesNotExist:
            return None

    def get_dialogue(self, dialogue_uuid, script):
        try:
            return Dialogue.objects.get(dialogue_uuid=dialogue_uuid, script=script)
        except Dialogue.DoesNotExist:
            return None

    def get_character(self, script, name):
        try:
            return Character.objects.get(script=script, name=name)
        except Character.DoesNotExist:
            return None

    def character_handling(self, script, character_name, user_data):
        character = self.get_character(script=script, name=character_name)
        if not character:
            c = Character.objects.create(
                **{'name': character_name, 'character_uuid': uuid.uuid4(), 'script': script,
                   'character_health': round((8 / 19) * 100)})
            c.save()
            create_script_activity({'action': 'create', 'message': f"character {c.character_uuid} created",
                                    'details': {'created_by': user_data.get('user_id')}})
            return c.id
        return character.id

    def character_scene_handling(self, scene, character, user_data, script):
        character_scene = CharacterScene.objects.filter(
            **{'scene__id': scene.id, 'character__id': character})
        if not character_scene:
            character_scene = CharacterScene.objects.create(
                **{'character_scene_uuid': uuid.uuid4(),
                   'character': Character.objects.get(id=character),
                   'scene': scene, 'script': script})
            character_scene.save()
            create_script_activity(
                {'action': 'create',
                 'message': f"character's scene {character_scene.character_scene_uuid} created",
                 'details': {'created_by': user_data.get('user_id')}})

        else:
            condition_primary = Q(scene__id=scene.id, character__id=character, script=script)
            condition_dual = Q(scene__id=scene.id, dual_character__id=character, script=script)

            # Combine the conditions using OR
            dialogue = Dialogue.objects.filter(condition_primary | condition_dual)
            if not dialogue:
                character_scene.delete()

    def put(self, request, script_uuid):
        dual_character = 0
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        request_act = request.data['act']
        request_scene = request.data.get('scene')
        dialogues = []
        dialogue_data = []
        if request_scene:
            dialogue_data = request_scene.pop("data", None)

        script = self.get_script(script_uuid=script_uuid)
        if not script:
            try:
                subscription = fetch_subscription_plan_with_user_id(user_id=user_data.get('user_id'))
                if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                              int) and json.loads(subscription.get('permission'))['number_of_script'] <= 0:
                    return Response("Please buy pro package. You don't have permission to create a script",
                                    status=status.HTTP_400_BAD_REQUEST)
                script = Script.objects.create(**{'script_uuid': script_uuid, 'created_by': user_data.get('user_id')})

                if isinstance(json.loads(subscription.get('permission'))['number_of_script'],
                              int):
                    update_subscription_plan_permission_number_of_script_minus(subscription_id=subscription.get('id'))
            except IntegrityError as e:
                # Handle the case where there is an integrity error (e.g., unique constraint violation)
                return Response(str(e), status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                # Handle other exceptions that might occur during the creation process
                return Response(str(e), status=status.HTTP_400_BAD_REQUEST)

        if script.script_condition != 'Not Registered':
            return Response('Your script is in lock mode. You can not update or delete',
                            status=status.HTTP_400_BAD_REQUEST)
        contributor = self.get_contributor(script=script, contributor=user_data.get('user_id'), editor=True)

        if script.created_by == user_data.get('user_id') or contributor:
            act = self.get_act(act_uuid=request_act.get('act_uuid'), script=script)
            if not act:
                total_word = 0
                if request_act.get('title'):
                    total_word = len(request_act.get('title').split())
                request_act["total_word"] = total_word
                request_act["script"] = script
                act_no = request_act.get("act_no")
                try:
                    if act_no:
                        Act.objects.filter(act_no__gte=act_no, script=script).update(act_no=F('act_no') + 1)
                    act = Act.objects.create(**request_act)
                    # Object created successfully
                    script.word_count += total_word
                except IntegrityError as e:
                    # Handle the case where there is an integrity error (e.g., unique constraint violation)
                    return Response(str(e), status=status.HTTP_400_BAD_REQUEST)
                except Exception as e:
                    # Handle other exceptions that might occur during the creation process
                    return Response(str(e), status=status.HTTP_400_BAD_REQUEST)
            else:
                total_word = 0
                if request_act.get('title'):
                    total_word = len(request_act.get('title').split())
                    request_act["total_word"] = total_word
                act_no = request_act.get("act_no")
                act_serializer = ActUpdateSerializer(act, data=request_act, partial=True)
                if act_serializer.is_valid():
                    if act_no and act.act_no != request_act.get("act_no"):
                        Act.objects.filter(act_no__gte=act_no, script=script).update(act_no=F('act_no') + 1)
                    act_serializer.save()
                    script.word_count += act.total_word - total_word
                else:
                    return Response(act_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            if not request_scene:
                act_serializer = ActSerializer(act)
                return Response(
                    [{'act': act_serializer.data, 'scene': {}}],
                    status=status.HTTP_201_CREATED)
            scene = self.get_scene(scene_uuid=request_scene.get("scene_uuid"), script=script)
            if scene:
                act_serializer = ActSerializer(self.get_act(act_uuid=request_act.get('act_uuid'), script=script))
                length = 0
                if request_scene.get('scene_header'):
                    length = len(request_scene.get('scene_header').split(' '))
                if request_scene.get('action'):
                    length += len(request_scene.get('action').split(' '))
                if request_scene.get('transaction_keyword'):
                    length += len(request_scene.get('transaction_keyword').split(' '))

                request_scene['scene_length'] = abs(scene.scene_length - length)
                request_scene['total_word'] = abs(scene.scene_length - length)
                scene_serializer = SceneUpdateSerializer(scene, data=request_scene, partial=True)
                scene_no = request_scene.get('scene_no')

                if scene_serializer.is_valid():
                    scene_serializer.save()
                    if scene_no and request_scene.get('scene_no') != scene.scene_no:
                        Scene.objects.filter(act=act, scene_no__gte=scene_no).update(scene_no=F('scene_no') + 1)

                    script.word_count += abs(scene.scene_length - length)

                    if not dialogue_data:
                        create_script_activity(
                            {'action': 'update', 'message': f"{request_scene.get('scene_uuid')} scene updated",
                             'details': {'created_by': user_data.get('user_id')}})
                        script.updated_on = timezone.now()
                        script.save()
                        sceening = scene_serializer.data
                        return Response(
                            [{'act': act_serializer.data, 'scene': sceening}],
                            status=status.HTTP_201_CREATED)

                    for d in dialogue_data:
                        dialogue = self.get_dialogue(dialogue_uuid=d.get('dialogue_uuid'), script=script)
                        if not dialogue:
                            if d.get('character'):
                                character = self.character_handling(script=script,
                                                                    character_name=d.get('character'),
                                                                    user_data=user_data)
                                d['character'] = character
                            d['scene'] = scene.id
                            d['script'] = script.id

                            total_word = 0
                            if d.get('line'):
                                total_word += len(d.get('line').split())
                            if d.get('parenthetical'):
                                total_word += len(d.get('parenthetical').split())

                            if d.get('dual'):
                                dual_character = self.character_handling(script=script,
                                                                         character_name=d.get(
                                                                             'dual_character'),
                                                                         user_data=user_data)
                                d['dual_character'] = dual_character
                                if d.get('dual_line'):
                                    total_word += len(d.get('dual_line').split())

                                if d.get('dual_parenthetical'):
                                    total_word += len(d.get('dual_parenthetical').split())

                            d['total_word'] = total_word
                            d["dialogue_no"] = Dialogue.objects.filter(scene=scene, script=script).count() + 1
                            dialogue_serializer = DialogueSerializer(data=d)
                            if dialogue_serializer.is_valid():
                                scene.total_word += total_word
                                scene.scene_length += total_word  # Adjust this according to your calculation logic
                                scene.save()

                                # Update the Act's total_word with scene_length
                                act.total_word += total_word  # Add scene_length to the act's total_word
                                act.save()
                                script.word_count += total_word

                                dialogue_serializer.save()

                                character_possession_update(script=script)

                                if d.get('character'):
                                    self.character_scene_handling(scene=scene, character=d.get('character'),
                                                                  user_data=user_data, script=script)

                                if d.get('dual'):
                                    if d.get('dual_character'):
                                        self.character_scene_handling(scene=scene, character=d.get('dual_character'),
                                                                      user_data=user_data, script=script)

                                create_script_activity(
                                    {'action': 'create', 'message': f"dialogue {d.get('dialogue_uuid')} created",
                                     'details': {'created_by': user_data.get('user_id')}})

                                dialogues.append(dialogue_serializer.data)

                            else:
                                return Response(dialogue_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

                        else:
                            if d.get('character'):
                                character = self.character_handling(script=script,
                                                                    character_name=d.get('character'),
                                                                    user_data=user_data)
                                d['character'] = character
                            d['scene'] = scene.id
                            d['script'] = script.id
                            total_word = 0
                            if d.get('line'):
                                total_word += len(d.get('line').split())
                            if d.get('parenthetical'):
                                total_word += len(d.get('parenthetical').split())

                            if d.get('dual') and d['dual'] != dialogue.dual:
                                if d.get('dual'):
                                    dual_character = self.character_handling(script=script,
                                                                             character_name=d.get(
                                                                                 'dual_character'),
                                                                             user_data=user_data)
                                    d['dual_character'] = dual_character
                                    total_word += len(d.get('dual_line').split())
                            if d.get('dual_character'):
                                if d.get('dual_character') != dialogue.dual_character:
                                    dual_character = self.character_handling(script=script,
                                                                             character_name=d.get(
                                                                                 'dual_character'),
                                                                             user_data=user_data)
                                    d['dual_character'] = dual_character
                            if d.get('dual_parenthetical'):
                                total_word += len(d.get('dual_parenthetical').split())

                            d['total_word'] = total_word
                            dialogue_serializer = DialogueUpdateSerializer(dialogue, data=d, partial=True)
                            dialogue_character = dialogue.character.id if dialogue.character else None
                            if dialogue.dual_character:
                                dual_character = dialogue.dual_character.id
                            if dialogue_serializer.is_valid():
                                if d.get("dialogue_no") and d.get("dialogue_no") != dialogue.dialogue_no:
                                    Dialogue.objects.filter(scene=scene, dialogue_no__gte=d.get("dialogue_no")).update(
                                        dialogue_no=F('dialogue_no') + 1)

                                scene.total_word += total_word - dialogue.total_word
                                scene.scene_length += total_word - dialogue.total_word  # Adjust this according to your calculation logic
                                scene.save()

                                # Extract the associated Act
                                # Update the Act's total_word with scene_length
                                act.total_word += total_word - dialogue.total_word  # Add scene_length to the act's total_word
                                act.save()

                                # Extract the associated Script from the Act
                                # Update the Script's word_count with the act's total_word
                                script.word_count += total_word - dialogue.total_word  # Add act's total_word to the script's
                                dialogue_serializer.save()
                                character_possession_update(script=script)
                                if d.get('character') and dialogue_character != d.get('character'):
                                    self.character_scene_handling(scene=scene, character=dialogue_character,
                                                                  user_data=user_data, script=script)
                                    self.character_scene_handling(scene=scene, character=d.get('character'),
                                                                  user_data=user_data, script=script)

                                if d.get('dual') and dual_character and dual_character != d.get('dual_character'):
                                    self.character_scene_handling(scene=scene, character=d.get('dual_character'),
                                                                  user_data=user_data, script=script)
                                    self.character_scene_handling(scene=scene, character=dual_character,
                                                                  user_data=user_data, script=script)

                                create_script_activity(
                                    {'action': 'update', 'message': f"dialogue {d.get('dialogue_uuid')} updated",
                                     'details': {'created_by': user_data.get('user_id')}})
                                dialogues.append(dialogue_serializer.data)

                            else:
                                return Response(dialogue_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

                    create_script_activity(
                        {'action': 'update', 'message': f"{request_scene.get('scene_uuid')} scene updated",
                         'details': {'created_by': user_data.get('user_id')}})
                    script.updated_on = timezone.now()
                    script.word_count += abs(scene.scene_length - length)
                    script.save()
                    sceening = scene_serializer.data
                    sceening['dialogue_data'] = dialogues
                    return Response(
                        [{'act': act_serializer.data, 'scene': sceening}],
                        status=status.HTTP_201_CREATED)
                else:
                    return Response(scene_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            else:
                request_scene['act'] = act.id
                request_scene['script'] = script.id
                scene_no = request_scene.get('scene_no')
                length = 0
                if request_scene.get('scene_header'):
                    length = len(request_scene.get('scene_header').split(' '))
                if request_scene.get('action'):
                    length += len(request_scene.get('action').split(' '))
                if request_scene.get('transaction_keyword'):
                    length += len(request_scene.get('transaction_keyword').split(' '))

                request_scene['scene_length'] = length
                request_scene['total_word'] = length
                scene_serializer = SceneSerializer(data=request_scene)
                if scene_serializer.is_valid():
                    scene_serializer.save()
                    if scene_no:
                        Scene.objects.filter(scene_no__gte=scene_no, act=act, script=script).update(
                            scene_no=F('scene_no') + 1)

                    if script.parent:
                        script.parent.updated_on = timezone.now()
                        script.parent.save()

                    if script.script_folder:
                        script.script_folder.updated_on = timezone.now()
                        script.script_folder.save()

                    script.word_count += length
                    scene_id = scene_serializer.data.get('id')
                    act.total_word += length
                    act.save()

                    scene = Scene.objects.get(scene_uuid=request_scene.get("scene_uuid"), script=script, act=act)

                    if not dialogue_data:
                        create_script_activity(
                            {'action': 'update', 'message': f"{request_scene.get('scene_uuid')} scene updated",
                             'details': {'created_by': user_data.get('user_id')}})
                        script.updated_on = timezone.now()
                        script.save()
                        act_serializer = ActSerializer(act)
                        sceening = scene_serializer.data
                        # sceening['dialogue_data'] = dialogues
                        return Response(
                            [{'act': act_serializer.data, 'scene': sceening}],
                            status=status.HTTP_201_CREATED)

                    for d in dialogue_data:
                        if d.get('character'):
                            character = self.character_handling(script=script,
                                                                character_name=d.get('character'),
                                                                user_data=user_data)
                            d['character'] = character
                        d['scene'] = scene.id
                        d['script'] = script.id

                        total_word = 0
                        if request.data.get('line'):
                            total_word += len(request.data.get('line').split())
                        if request.data.get('parenthetical'):
                            total_word += len(request.data.get('parenthetical').split())

                        if request.data.get('dual'):
                            dual_character = self.character_handling(script=script,
                                                                     character_name=d.get(
                                                                         'dual_character'),
                                                                     user_data=user_data)
                            request.data['dual_character'] = dual_character
                            if d.get('dual_line'):
                                total_word += len(d.get('dual_line').split())

                            if request.data.get('dual_parenthetical'):
                                total_word += len(request.data.get('dual_parenthetical').split(" "))

                        request.data['total_word'] = total_word
                        dialogue_serializer = DialogueSerializer(data=d)
                        if dialogue_serializer.is_valid():
                            scene.total_word += total_word
                            scene.scene_length += total_word  # Adjust this according to your calculation logic
                            scene.save()

                            # Update the Act's total_word with scene_length
                            act.total_word += total_word  # Add scene_length to the act's total_word
                            act.save()
                            script.word_count += total_word

                            dialogue_serializer.save()

                            character_possession_update(script=script)
                            if d.get('character'):
                                self.character_scene_handling(scene=scene, character=d.get('character'),
                                                              user_data=user_data, script=script)

                            if d.get('dual'):
                                if d.get('dual_character'):
                                    self.character_scene_handling(scene=scene, character=d.get('dual_character'),
                                                                  user_data=user_data, script=script)

                            dialogues.append(dialogue_serializer.data)
                            create_script_activity(
                                {'action': 'create', 'message': f"dialogue {d.get('dialogue_uuid')} created",
                                 'details': {'created_by': user_data.get('user_id')}})

                        else:
                            return Response(dialogue_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

                    script.updated_on = timezone.now()
                    script.word_count += length
                    script.save()
                    act_serializer = ActSerializer(act)
                    sceening = scene_serializer.data
                    sceening['dialogue_data'] = dialogues
                    return Response(
                        [{'act': act_serializer.data, 'scene': sceening}],
                        status=status.HTTP_201_CREATED)
                return Response(scene_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to create scene", status=status.HTTP_401_UNAUTHORIZED)


class SharaScriptView(APIView):
    permission_classes = [AllowAny]  # Allow any user to access this view
    authentication_classes = [TokenAuthentication]  # Use Token Authentication for user authentication

    def get_object(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get_contributor(self, script, contributor):
        try:
            return Contributor.objects.get(script=script, contributor=contributor)
        except Contributor.DoesNotExist:
            return None

    def get(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        script = self.get_object(script_uuid=script_uuid)
        if not script:
            return Response("No script found with this id", status=status.HTTP_400_BAD_REQUEST)
        contributor = self.get_contributor(script=script, contributor=user_data.get('user_id'))
        if not contributor:
            return Response("You don't have permission to access this script", status=status.HTTP_401_UNAUTHORIZED)

        true_values = {
            'outline': contributor.outline,
            'character': contributor.character,
            'location': contributor.location,
            'structure': contributor.structure,
            'story_docs': contributor.story_docs,
            'script_permission': contributor.script_permission,
        }

        # Filter out the fields with True values
        true_fields = {key: value for key, value in true_values.items() if value}
        serializer = ScriptSerializer(script)
        acts = Act.objects.filter(script=script).order_by('act_no')
        data = []
        for act in acts:
            scenes = Scene.objects.filter(act=act, script=script).order_by('scene_no')
            act_body = []
            for scene in scenes:
                scene_serializer = SceneSerializer(scene)
                dialogues = Dialogue.objects.filter(scene=scene).order_by('dialogue_no')
                dialogue_serializer = DialogueSerializer(dialogues, many=True)
                scene_serializer.data['dialogue_data'] = dialogue_serializer.data
                scene_data = scene_serializer.data
                scene_data['dialogue_data'] = dialogue_serializer.data
                act_body.append(scene_data)

            data.append({'actHead': act.title, 'actUUID': act.act_uuid, 'actNo': act.act_no, 'actBody': act_body})

        return Response(
            {'role': contributor.contributor_role, 'permission': true_fields.keys(), 'script_info': serializer.data,
             "data": data}, status=status.HTTP_200_OK)
