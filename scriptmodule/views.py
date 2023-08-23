from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from .utils import token_validator
from .serializer import *
import uuid
from rest_framework import status
from django.db.models import F
from django.db.models import Q


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
                act_no = request.data.get('act_no')
                # checking if act_no exist in this script if exist it will upgrade the act_no which is greater than
                # or equal to the act_no
                if act_no:
                    Act.objects.filter(act_no__gte=act_no).update(act_no=F('act_no') + 1)
                serializer.save()
                create_script_activity({'action': 'create', 'message': f'act created of {script_uuid}',
                                        'details': {'created_by': user_data.get('user_id')}})
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
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
                scene_no = request.data.get('scene_no')
                # checking if scene_no exist in this act. If exist it will upgrade the scene_no which is greater than
                # or equal to the scene_no
                if scene_no:
                    Scene.objects.filter(act=act, scene_no__gte=scene_no).update(scene_no=F('scene_no') + 1)
                serializer.save()
                scene_id = serializer.data.get('id')
                location_type = serializer.data.get('scene_header').lstrip()[:3]
                if location_type and location_type != 'int':
                    if location_type != 'ext':
                        location_type = "int"
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
                            location_type = "int"
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


class LocationRetrieveView(APIView):
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
            if scene:
                location = Location.objects.get(scene=scene)
                serializer = LocationSerializer(location)
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response("No script found", status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to view this location", status=status.HTTP_401_UNAUTHORIZED)

    def put(self, request, script_uuid, act_uuid, scene_uuid):
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
            scene = self.get_scene(scene_uuid, act)
            if scene:
                location = Location.objects.get(scene=scene)
                serializer = LocationUpdateSerializer(location, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    create_script_activity(
                        {'action': 'update', 'message': f"{location.location_uuid} updated",
                         'details': {'created_by': user_data.get('user_id')}})
                    return Response(serializer.data, status=status.HTTP_200_OK)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            return Response("No script found", status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to view this location", status=status.HTTP_401_UNAUTHORIZED)


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

        contributor = self.get_contributor(script, user_data.get('user_id'), True)
        if script.created_by == user_data.get('user_id') or contributor:
            characters = Character.objects.filter(script=script)
            serializer = CharacterSerializer(characters, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response("You don't have permission to view this character", status=status.HTTP_401_UNAUTHORIZED)

    def post(self, request, script_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), True)
        if script.created_by == user_data.get('user_id') or contributor:
            if request.data.get('archetype'):
                archetype = ArcheType.objects.get(name=request.data.get('arche_type'), script=script)
                request.data['archetype'] = archetype.id
            request.data['total_word'] = len(request.data.get('name').split(" "))
            request.data['script'] = script.id
            # Calculate the empty column ratio
            total_columns = Character._meta.fields  # All fields including primary key
            empty_columns = sum(
                1 for field in total_columns if field.name != 'id' and not request.data.get(field.name)
            )

            if len(total_columns) == 0:
                character_health = 0  # To avoid division by zero
            else:
                character_health = empty_columns / (len(total_columns) - 1)  # Excluding primary key

            request.data['character_health'] = round((1 - character_health) * 100, 2)
            serializer = CharacterSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                create_script_activity(
                    {'action': 'create', 'message': f"new character created",
                     'details': {'created_by': user_data.get('user_id')}})
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to create character", status=status.HTTP_401_UNAUTHORIZED)


class CharacterRetrieveView(APIView):
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
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), False)
        if script.created_by == user_data.get('user_id') or contributor:
            character = self.get_character(script, character_uuid)
            serializer = CharacterSerializer(character)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response("You don't have permission to view this character", status=status.HTTP_401_UNAUTHORIZED)

    def put(self, request, script_uuid, character_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), True)
        if script.created_by == user_data.get('user_id') or contributor:
            character = self.get_character(script, character_uuid)
            if request.data.get('archetype'):
                archetype = ArcheType.objects.get(title=request.data.get('archetype'), script=script)
                request.data['archetype'] = archetype.id
            if request.data.get('name'):
                request.data['total_word'] = len(request.data.get('name').split(" "))
            serializer = CharacterUpdateSerializer(character, data=request.data, partial=True)
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
                create_script_activity(
                    {'action': 'update', 'message': f"{character_uuid} character updated",
                     'details': {'created_by': user_data.get('user_id')}})
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to edit this character", status=status.HTTP_401_UNAUTHORIZED)

    def delete(self, request, script_uuid, character_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

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

                character_dialogue = Dialogue.objects.filter(Q(character=character) | Q(dual_character=character))
                if character_dialogue:
                    character_dialogue.delete()
                    create_script_activity(
                        {'action': 'delete', 'message': f"{character_uuid}'s dialogue deleted",
                         'details': {'created_by': user_data.get('user_id')}})

                character.delete()
                create_script_activity(
                    {'action': 'delete', 'message': f"{character_uuid} character deleted",
                     'details': {'created_by': user_data.get('user_id')}})

                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response('No character found', status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to view this character", status=status.HTTP_401_UNAUTHORIZED)


class CharacterSceneListView(APIView):
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
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

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
                   'total_word': len(character_name.split(" "))})
            create_script_activity({'action': 'create', 'message': f"character {c.character_uuid} created",
                                    'details': {'created_by': user_data.get('user_id')}})
            return c.id
        return character.id

    def character_scene_handling(self, scene, character, user_data):
        character_scene = CharacterScene.objects.filter(
            **{'scene__id': scene.id, 'character__id': character})
        if not character_scene:
            character_scene = CharacterScene.objects.create(
                **{'character_scene_uuid': uuid.uuid4(),
                   'character': Character.objects.get(id=character),
                   'scene': scene})
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
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

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
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

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
            serializer = DialogueSerializer(data=request.data)
            dialogue_no = request.data.get('dialogue_no')
            if request.data.get('dual'):
                dual_character = self.character_handling(script=script,
                                                         character_name=request.data.get('dual_character'),
                                                         user_data=user_data)
                request.data['dual_character'] = dual_character
            if serializer.is_valid():
                if dialogue_no:
                    Dialogue.objects.filter(scene=scene, dialogue_no__gte=dialogue_no).update(
                        dialogue_no=F('dialogue_no') + 1)
                serializer.save()
                self.character_scene_handling(scene=scene, character=request.data.get('character'), user_data=user_data)
                if request.data.get('dual'):
                    self.character_scene_handling(scene=scene, character=request.data.get('dual_character'),
                                                  user_data=user_data)

                scene.total_word += request.data.get('total_word')
                scene.scene_length += request.data.get('total_word')  # Adjust this according to your calculation logic
                scene.save()

                # Extract the associated Act
                act = scene.act

                # Update the Act's total_word with scene_length
                act.total_word += scene.scene_length  # Add scene_length to the act's total_word
                act.save()

                # Extract the associated Script from the Act
                script = act.script

                # Update the Script's word_count with the act's total_word
                script.word_count += act.total_word  # Add act's total_word to the script's word_count
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
        print(character)
        if not character:
            c = Character.objects.create(
                **{'name': character_name, 'character_uuid': uuid.uuid4(), 'script': script,
                   'total_word': len(character_name.split(" "))})
            create_script_activity({'action': 'create', 'message': f"character {c.character_uuid} created",
                                    'details': {'created_by': user_data.get('user_id')}})
            return c.id
        return character.id

    def character_scene_handling(self, scene, character, user_data):
        character_scene = CharacterScene.objects.filter(
            **{'scene__id': scene.id, 'character__id': character})
        if not character_scene:
            character_scene = CharacterScene.objects.create(
                **{'character_scene_uuid': uuid.uuid4(),
                   'character': Character.objects.get(id=character),
                   'scene': scene})
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
            if request.data['dual'] != dialogue.dual:
                if request.data.get('dual'):
                    dual_character = self.character_handling(script=script,
                                                             character_name=request.data.get('dual_character'),
                                                             user_data=user_data)
                    print(dual_character)
                    request.data['dual_character'] = dual_character

            serializer = DialogueUpdateSerializer(dialogue, data=request.data, partial=True)
            dialogue_no = request.data.get('dialogue_no')
            if serializer.is_valid():
                if dialogue_no:
                    Dialogue.objects.filter(scene=scene, dialogue_no__gte=dialogue_no).update(
                        dialogue_no=F('dialogue_no') + 1)
                serializer.save()
                if request.data.get('character'):
                    self.character_scene_handling(scene=scene, character=request.data.get('character'),
                                                  user_data=user_data)
                if request.data.get('dual'):
                    self.character_scene_handling(scene=scene, character=request.data.get('dual_character'),
                                                  user_data=user_data)

                scene.total_word += request.data.get('total_word') - dialogue.total_word
                scene.scene_length += request.data.get(
                    'total_word') - dialogue.total_word  # Adjust this according to your calculation logic
                scene.save()

                # Extract the associated Act
                act = scene.act

                # Update the Act's total_word with scene_length
                act.total_word += request.data.get(
                    'total_word') - dialogue.total_word  # Add scene_length to the act's total_word
                act.save()

                # Extract the associated Script from the Act
                script = act.script

                # Update the Script's word_count with the act's total_word
                script.word_count += request.data.get(
                    'total_word') - dialogue.total_word  # Add act's total_word to the script's
                # word_count
                script.updated_on = timezone.now()
                script.save()

                create_script_activity(
                    {'action': 'update', 'message': f"dialogue {dialogue_uuid} updated",
                     'details': {'created_by': user_data.get('user_id')}})
                return Response(serializer.data, status=status.HTTP_200_OK)
            print(serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to view dialogues", status=status.HTTP_401_UNAUTHORIZED)

    def delete(self, request, script_uuid, act_uuid, scene_uuid, dialogue_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)

        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

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


def create_comment(data):
    serializer = CommentSerializer(data=data)
    if serializer.is_valid():
        serializer.save()
        return serializer.data, True
    return serializer.errors, False


class DialogueComment(APIView):
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

    def get_scene(self, scene_uuid):
        try:
            return Scene.objects.get(scene_uuid=scene_uuid)
        except Scene.DoesNotExist:
            return None

    def get_dialogue(self, scene, dialogue_uuid):
        try:
            return Dialogue.objects.get(scene=scene, dialogue_uuid=dialogue_uuid)
        except Dialogue.DoesNotExist:
            return None

    def post(self, request, script_uuid, scene_uuid, dialogue_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), False)
        if script.created_by == user_data.get('user_id') or contributor:
            scene = self.get_scene(scene_uuid=scene_uuid)
            if not scene:
                return Response("No scene found with this id", status=status.HTTP_400_BAD_REQUEST)
            dialogue = self.get_dialogue(scene=scene, dialogue_uuid=dialogue_uuid)
            if not dialogue:
                return Response("No dialogue found", status=status.HTTP_400_BAD_REQUEST)
            request.data['created_by'] = user_data.get('user_id')
            comment_data, s = create_comment(data=request.data)
            if s:
                dialogue.comment = Comment.objects.get(id=comment_data['id'])
                dialogue.save()
                return Response(comment_data, status=status.HTTP_201_CREATED)
            return Response(comment_data, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to view dialogues", status=status.HTTP_401_UNAUTHORIZED)


class SceneComment(APIView):
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

    def get_scene(self, scene_uuid):
        try:
            return Scene.objects.get(scene_uuid=scene_uuid)
        except Scene.DoesNotExist:
            return None

    def post(self, request, script_uuid, scene_uuid):
        user_data = get_user_id(request)
        if not user_data.get('user_id'):
            return Response("Invalid Token. Please Login again.", status=status.HTTP_401_UNAUTHORIZED)
        script = self.get_script(script_uuid)
        if not script:
            return Response('No script found with this id', status=status.HTTP_400_BAD_REQUEST)

        contributor = self.get_contributor(script, user_data.get('user_id'), False)
        if script.created_by == user_data.get('user_id') or contributor:
            scene = self.get_scene(scene_uuid=scene_uuid)
            if not scene:
                return Response("No scene found with this id", status=status.HTTP_400_BAD_REQUEST)

            request.data['created_by'] = user_data.get('user_id')
            comment_data, s = create_comment(data=request.data)
            if s:
                scene.comment = Comment.objects.get(id=comment_data['id'])
                scene.save()
                return Response(comment_data, status=status.HTTP_201_CREATED)
            return Response(comment_data, status=status.HTTP_400_BAD_REQUEST)
        return Response("You don't have permission to view dialogues", status=status.HTTP_401_UNAUTHORIZED)


class CommentRetrieveView(APIView):
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

        contributor = self.get_contributor(script, user_data.get('user_id'), False)
        if script.created_by == user_data.get('user_id') or contributor:
            comment = self.get_comment(comment_uuid=comment_uuid)
            if not comment:
                return Response("No comment found", status=status.HTTP_400_BAD_REQUEST)

            if comment.created_by != user_data.get('user_id'):
                return Response("You don't have permission to edit this comment", status=status.HTTP_401_UNAUTHORIZED)
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
                return Response("No comment found", status=status.HTTP_400_BAD_REQUEST)
            if comment.created_by != user_data.get('user_id'):
                return Response("You don't have permission to edit this comment", status=status.HTTP_401_UNAUTHORIZED)
            comment.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response("You don't have permission to delete comment", status=status.HTTP_401_UNAUTHORIZED)
