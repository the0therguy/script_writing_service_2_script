from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from .utils import token_validator
from .serializer import *
import uuid
from rest_framework import status


# Create your views here.
def create_script_activity(data):
    data['activity_uuid'] = str(uuid.uuid4())
    activity = ScriptActivity.objects.create(**data)
    activity.save()


def get_user_id(request):
    data = token_validator(request)
    return data


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
        serializer = ScriptSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            create_script_activity({'action': 'create', 'message': 'new script created',
                                    'details': {'created_by': user_data.get('user_id')}})

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ContributorView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        try:
            script = Script.objects.get(script_uuid=script_uuid, created_by=user_data.get('user_id'))
        except Script.DoesNotExist:
            return Response({'script_uuid': 'Script not found.'}, status=status.HTTP_404_NOT_FOUND)

        contributor = Contributor.objects.filter(script=script)
        serializer = ContributorSerializer(contributor, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        try:
            script = Script.objects.get(script_uuid=script_uuid, created_by=user_data.get('user_id'))
        except Script.DoesNotExist:
            return Response({'script_uuid': 'Script not found.'}, status=status.HTTP_404_NOT_FOUND)

        contributor_check = Contributor.objects.filter(script=script, contributor=request.data.get('contributor'))
        if contributor_check.exists():
            return Response('Contributor already exist', status=status.HTTP_200_OK)

        contributor = Contributor.objects.create(
            **{'contributor_uuid': request.data.get('contributor_uuid'), 'script': script,
               'contributor_role': request.data.get('contributor_role'),
               'contributor': request.data.get('contributor')})
        contributor.save()
        create_script_activity({'action': 'create', 'message': 'new contributor added',
                                'details': {'created_by': user_data.get('user_id')}})
        return Response('Contributor added', status=status.HTTP_201_CREATED)


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

    def post(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        try:
            script = Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return Response({'script_uuid': 'Script not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not script.created_by == user_data.get('user_id'):
            return Response("You don't have permission to this scope", status=status.HTTP_401_UNAUTHORIZED)
        if not script.parent:
            request.data['script'] = script.id
            serializer = StoryDocsSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                create_script_activity({'action': 'create', 'message': 'new contributor added',
                                        'details': {'created_by': user_data.get('user_id')}})
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        parent_script = Script.objects.get(script_uuid=script.parent.script_uuid)
        story_docs = StoryDocs.objects.create(
            **{'story_docs_uuid': request.data.get('uuid'), 'heading': request.data.get('heading'),
               'script': parent_script})
        story_docs.save()
        create_script_activity({'action': 'create', 'message': 'new contributor added',
                                'details': {'created_by': user_data.get('user_id')}})

        return Response(status=status.HTTP_201_CREATED)


class StoryDocsRetrieveUpdateDeleteView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

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
        if not script.parent:
            story_docs = self.get_object(script)
            if story_docs:
                serializer = StoryDocsSerializer(story_docs)
                return Response(serializer.data)
            return Response({'error': 'StoryDocs not found'}, status=status.HTTP_404_NOT_FOUND)
        parent_script = self.get_script(script.parent.script_uuid)
        story_docs = self.get_object(parent_script)
        if story_docs:
            serializer = StoryDocsSerializer(story_docs)
            return Response(serializer.data)
        return Response({'error': 'StoryDocs not found'}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            return Response({'error': 'Script not found'}, status=status.HTTP_404_NOT_FOUND)
        if not script.created_by == user_data.get('user_id'):
            return Response("You don't have permission to this scope", status=status.HTTP_401_UNAUTHORIZED)

        if not script.parent:
            story_docs = self.get_object(script)
            if story_docs:
                serializer = StoryDocsUpdateSerializer(story_docs, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    create_script_activity({'action': 'update',
                                            'message': f'story docs {story_docs.story_docs_uuid} updated',
                                            'details': {'created_by': user_data.get('user_id')}})
                    return Response(serializer.data)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            return Response({'error': 'StoryDocs not found'}, status=status.HTTP_404_NOT_FOUND)
        parent_script = self.get_script(script.parent.script_uuid)
        story_docs = self.get_object(parent_script)
        if story_docs:
            serializer = StoryDocsUpdateSerializer(story_docs, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                create_script_activity({'action': 'update',
                                        'message': f'story docs {story_docs.story_docs_uuid} updated',
                                        'details': {'created_by': user_data.get('user_id')}})
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response({'error': 'StoryDocs not found'}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            return Response({'error': 'Script not found'}, status=status.HTTP_404_NOT_FOUND)
        if not script.created_by == user_data.get('user_id'):
            return Response("You don't have permission to this scope", status=status.HTTP_401_UNAUTHORIZED)

        if not script.parent:
            story_docs = self.get_object(script)
            if story_docs:
                sub_story = SubStory.objects.filter(story_docs=story_docs)
                sub_story.delete()
                create_script_activity({'action': 'delete',
                                        'message': f'sub story of story docs {story_docs.story_docs_uuid} deleted',
                                        'details': {'created_by': user_data.get('user_id')}})
                story_docs.delete()
                create_script_activity({'action': 'delete',
                                        'message': f'story docs {story_docs.story_docs_uuid} deleted',
                                        'details': {'created_by': user_data.get('user_id')}})
                return Response({'message': 'StoryDocs deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
            return Response({'error': 'StoryDocs not found'}, status=status.HTTP_404_NOT_FOUND)
        parent_script = self.get_script(script.parent.script_uuid)
        story_docs = self.get_object(parent_script)
        if story_docs:
            story_docs.delete()
            create_script_activity({'action': 'delete',
                                    'message': f'story docs {story_docs.story_docs_uuid} deleted',
                                    'details': {'created_by': user_data.get('user_id')}})
            return Response({'message': 'StoryDocs deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
        return Response({'error': 'StoryDocs not found'}, status=status.HTTP_404_NOT_FOUND)


class SubStoryDocsListCreateView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

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
        if script:
            if not script.parent:
                sub_story = SubStory.objects.filter(**{'story_docs__script': script}).order_by('sub_story_no')
                serializer = SubStorySerializer(sub_story, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
            parent_script = self.get_script(script.parent.script_uuid)
            if parent_script:
                sub_story = SubStory.objects.filter(**{'story_docs__script': parent_script}).order_by('sub_story_no')
                serializer = SubStorySerializer(sub_story, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response('No Script Found', status=status.HTTP_400_BAD_REQUEST)
        return Response('No Script Found', status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script.created_by == user_data.get('user_id'):
            return Response("You don't have permission to this scope", status=status.HTTP_401_UNAUTHORIZED)

        if script:
            if not script.parent:
                story_docs = self.get_story_docs(script)
                if story_docs:
                    request.data['story_docs'] = story_docs.id
                    serializer = SubStorySerializer(data=request.data)
                    if serializer.is_valid():
                        serializer.save()
                        create_script_activity({'action': 'create', 'message': 'new sub_story created',
                                                'details': {'created_by': user_data.get('user_id')}})
                        return Response(serializer.data, status=status.HTTP_201_CREATED)
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                story_docs = StoryDocs.objects.create(**{'story_docs_uuid': uuid.uuid4(), 'script': script})
                story_docs.save()
                request.data['story_docs'] = story_docs.id
                serializer = SubStorySerializer(data=request.data)
                if serializer.is_valid():
                    serializer.save()
                    create_script_activity({'action': 'create', 'message': 'new sub_story created',
                                            'details': {'created_by': user_data.get('user_id')}})
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            parent_script = self.get_script(script.parent.script_uuid)
            if parent_script:
                story_docs = self.get_story_docs(parent_script)
                if story_docs:
                    request.data['story_docs'] = story_docs.id
                    serializer = SubStorySerializer(data=request.data)
                    if serializer.is_valid():
                        serializer.save()
                        create_script_activity({'action': 'create', 'message': 'new sub_story created',
                                                'details': {'created_by': user_data.get('user_id')}})
                        return Response(serializer.data, status=status.HTTP_201_CREATED)
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                story_docs = StoryDocs.objects.create(**{'story_docs_uuid': uuid.uuid4(), 'script': parent_script})
                story_docs.save()
                create_script_activity({'action': 'create', 'message': 'new story doc created',
                                        'details': {'created_by': user_data.get('user_id')}})
                request.data['story_docs'] = story_docs.id
                serializer = SubStorySerializer(data=request.data)
                if serializer.is_valid():
                    serializer.save()
                    create_script_activity({'action': 'create', 'message': 'new sub_story created',
                                            'details': {'created_by': user_data.get('user_id')}})
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            return Response('No script found', status=status.HTTP_400_BAD_REQUEST)
        return Response({'error': 'Script not found'}, status=status.HTTP_404_NOT_FOUND)


class SubStoryRetrieveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_object(self, sub_story_uuid):
        try:
            return SubStory.objects.get(sub_story_uuid=sub_story_uuid)
        except SubStory.DoesNotExist:
            return None

    def get(self, request, sub_story_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        sub_story = self.get_object(sub_story_uuid)
        if not sub_story:
            return Response("No sub story found by this id", status=status.HTTP_400_BAD_REQUEST)

        serializer = SubStorySerializer(sub_story)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, sub_story_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        sub_story = self.get_object(sub_story_uuid)
        if not sub_story:
            return Response("No sub story found by this id", status=status.HTTP_400_BAD_REQUEST)

        if not sub_story.story_docs.script.created_by == user_data.get('user_id'):
            return Response("You don't have permission to this scope", status=status.HTTP_401_UNAUTHORIZED)

        serializer = SubStoryUpdateSerializer(sub_story, request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            create_script_activity({'action': 'update', 'message': f'sub_story {sub_story_uuid} updated',
                                    'details': {'created_by': user_data.get('user_id')}})

            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, sub_story_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        sub_story = self.get_object(sub_story_uuid)
        if not sub_story:
            return Response("No sub story found by this id", status=status.HTTP_400_BAD_REQUEST)

        if not sub_story.story_docs.script.created_by == user_data.get('user_id'):
            return Response("You don't have permission to this scope", status=status.HTTP_401_UNAUTHORIZED)

        sub_story.delete()
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

    def get_contributor(self, script, contributor):
        try:
            return Contributor.objects.get(script=script, contributor=contributor, contributor_role='co-writer')
        except Contributor.DoesNotExist:
            return None

    def get(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

        acts = Act.objects.filter(**{'script': script}).order_by('act_no')
        serializer = ActSerializer(acts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)
        contributor = self.get_contributor(script, user_data.get('user_id'))

        if script.created_by == user_data.get('user_id') or contributor:
            request.data['script'] = script.id
            serializer = ActSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                create_script_activity({'action': 'create', 'message': f'act created of {script_uuid}',
                                        'details': {'created_by': user_data.get('user_id')}})
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        if not contributor:
            return Response("You don't have permission to edit this script", status=status.HTTP_401_UNAUTHORIZED)


class ActRetrieveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_object(self, act_uuid):
        try:
            return Act.objects.get(act_uuid=act_uuid)
        except Act.DoesNotExist:
            return None

    def get_contributor(self, script, contributor):
        try:
            return Contributor.objects.get(script=script, contributor=contributor, contributor_role='co-writer')
        except Contributor.DoesNotExist:
            return None

    def get_script(self, script_uuid):
        try:
            return Script.objects.get(script_uuid=script_uuid)
        except Script.DoesNotExist:
            return None

    def get(self, request, act_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        act = self.get_object(act_uuid)
        if not act:
            return Response('No act found with this act', status=status.HTTP_400_BAD_REQUEST)
        serializer = ActSerializer(act)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, act_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        act = self.get_object(act_uuid)
        if not act:
            return Response('No act found with this act', status=status.HTTP_400_BAD_REQUEST)

        script = self.get_script(act.script.script_uuid)
        if not script:
            return Response("this act doesn't belong to any script", status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'))
        if script.created_by == user_data.get('user_id') or contributor:
            serializer = ActUpdateSerializer(act, request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                create_script_activity({'action': 'update', 'message': f'act {act_uuid} updated',
                                        'details': {'created_by': user_data.get('user_id')}})
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to edit this act", status=status.HTTP_401_UNAUTHORIZED)

    def delete(self, request, act_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        act = self.get_object(act_uuid)
        if not act:
            return Response('No act found with this act', status=status.HTTP_400_BAD_REQUEST)

        script = self.get_script(act.script.script_uuid)
        if not script:
            return Response("this act doesn't belong to any script", status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'))

        if script.created_by == user_data.get('user_id') or contributor:
            scene = Scene.objects.filter(act=act)
            scene.delete()
            create_script_activity(
                {'action': 'delete', 'message': f'delete all the scenes. Which is connected to act {act_uuid}',
                 'details': {'created_by': user_data.get('user_id')}})
            act.delete()
            create_script_activity({'action': 'delete', 'message': f'act {act_uuid} deleted',
                                    'details': {'created_by': user_data.get('user_id')}})
            return Response('Deleted successfully', status=status.HTTP_204_NO_CONTENT)
        return Response("You don't have permission to delete this act", status=status.HTTP_401_UNAUTHORIZED)


class SceneCreateView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_act(self, act_uuid):
        try:
            return Act.objects.get(act_uuid=act_uuid)
        except Act.DoesNotExist:
            return None

    def get_contributor(self, script, contributor):
        try:
            return Contributor.objects.get(script=script, contributor=contributor, contributor_role='co-writer')
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

        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)
        act = self.get_act(act_uuid)
        if not act:
            return Response('No act found with this id', status=status.HTTP_400_BAD_REQUEST)

        scene = Scene.objects.filter(**{'act': act}).order_by('scene_no')
        serializer = SceneSerializer(scene, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, script_uuid, act_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)
        act = self.get_act(act_uuid)
        if not act:
            return Response('No act found with this id', status=status.HTTP_400_BAD_REQUEST)
        contributor = self.get_contributor(script, user_data.get('user_id'))

        if script.created_by == user_data.get('user_id') or contributor:
            request.data['act'] = act.id
            serializer = SceneSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                scene_id = serializer.data.get('id')
                location_type = serializer.data.get('scene_header').lstrip()[:3]
                if location_type and location_type != 'int':
                    if location_type != 'ext':
                        location_type = ""
                create_script_activity({'action': 'create', 'message': f"{request.data.get('scene_uuid')} was created",
                                        'details': {'created_by': user_data.get('user_id')}})
                location = LocationSerializer(data=
                                              {'location_uuid': str(uuid.uuid4()), 'location_type': location_type,
                                               'scene': scene_id})
                if location.is_valid():
                    location.save()
                    create_script_activity(
                        {'action': 'create', 'message': f"{request.data.get('scene_uuid')} of location was created",
                         'details': {'created_by': user_data.get('user_id')}})
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

    def get_act(self, act_uuid):
        try:
            return Act.objects.get(act_uuid=act_uuid)
        except Act.DoesNotExist:
            return None

    def get(self, request, script_uuid, act_uuid, scene_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)
        act = self.get_act(act_uuid)
        if not act:
            return Response('No act found with this id', status=status.HTTP_400_BAD_REQUEST)
        contributor = self.get_contributor(script, user_data.get('user_id'), False)
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

        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)
        contributor = self.get_contributor(script, user_data.get('user_id'), True)
        if script.created_by == user_data.get('user_id') or contributor:
            act = self.get_act(act_uuid)
            if not act:
                return Response('No act found with this id', status=status.HTTP_400_BAD_REQUEST)

            scene = self.get_scene(scene_uuid, act)
            if not scene:
                return Response('No scene found with this id', status=status.HTTP_400_BAD_REQUEST)

            serializer = SceneUpdateSerializer(scene, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                if scene.scene_header != serializer['scene_header']:
                    location_type = serializer.data.get('scene_header').lstrip()[:3]
                    if location_type and location_type != 'int':
                        if location_type != 'ext':
                            location_type = ""
                    location = Location.objects.get(scene=scene)
                    if location_type != location.location_type:
                        location_serializer = LocationUpdateSerializer(location, {'location_type': location_type},
                                                                       partial=True)
                        if location_serializer.is_valid():
                            location_serializer.save()
                            create_script_activity(
                                {'action': 'update', 'message': f"{location.location_uuid} updated",
                                 'details': {'created_by': user_data.get('user_id')}})
                create_script_activity(
                    {'action': 'update', 'message': f"{request.data.get('scene_uuid')} scene updated",
                     'details': {'created_by': user_data.get('user_id')}})
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to view this scene", status=status.HTTP_401_UNAUTHORIZED)

    def delete(self, request, script_uuid, act_uuid, scene_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)
        act = self.get_act(act_uuid)
        if not act:
            return Response('No act found with this id', status=status.HTTP_400_BAD_REQUEST)
        contributor = self.get_contributor(script, user_data.get('user_id'), True)
        if script.created_by == user_data.get('user_id') or contributor:
            act = self.get_act(act_uuid)
            if not act:
                return Response('No act found with this id', status=status.HTTP_400_BAD_REQUEST)

            scene = self.get_scene(scene_uuid, act)
            if not scene:
                return Response('No scene found with this id', status=status.HTTP_400_BAD_REQUEST)
            location = Location.objects.get(scene=scene)
            if location:
                location.delete()
                create_script_activity(
                    {'action': 'delete', 'message': f"location {location.location_uuid} deleted",
                     'details': {'created_by': user_data.get('user_id')}})
            scene.delete()
            create_script_activity(
                {'action': 'delete', 'message': f"{request.data.get('scene_uuid')} scene deleted",
                 'details': {'created_by': user_data.get('user_id')}})
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response("You don't have permission to delete scene", status=status.HTTP_401_UNAUTHORIZED)
