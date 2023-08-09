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

class ScriptView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_user_id(self, request):
        data = token_validator(request)
        return data

    def get(self, request):
        user_data = self.get_user_id(request)
        if not user_data.get('user_id'):
            return Response(user_data.get('message'), status=status.HTTP_401_UNAUTHORIZED)
        scripts = Script.objects.filter(created_by=user_data.get('user_id'), parent=None).order_by('-updated_on')
        serializer = ScriptSerializer(scripts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        user_data = self.get_user_id(request)
        if not user_data.get('user_id'):
            return Response(user_data.get('message'), status=status.HTTP_401_UNAUTHORIZED)
        request.data['created_by'] = user_data.get('user_id')
        serializer = ScriptSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            activity = ScriptActivity.objects.create(
                **{'activity_uuid': uuid.uuid4(), 'action': 'create', 'message': 'new script created',
                   'details': {'created_by': user_data.get('user_id')}})
            activity.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ContributorView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_user_id(self, request):
        data = token_validator(request)
        return data

    def get(self, request, script_uuid):
        user_data = self.get_user_id(request)
        if not user_data.get('user_id'):
            return Response(user_data.get('message'), status=status.HTTP_401_UNAUTHORIZED)
        try:
            script = Script.objects.get(script_uuid=script_uuid, created_by=user_data.get('user_id'))
        except Script.DoesNotExist:
            return Response({'script_uuid': 'Script not found.'}, status=status.HTTP_404_NOT_FOUND)

        contributor = Contributor.objects.filter(script=script)
        serializer = ContributorSerializer(contributor, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, script_uuid):
        user_data = self.get_user_id(request)
        if not user_data.get('user_id'):
            return Response(user_data.get('message'), status=status.HTTP_401_UNAUTHORIZED)
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
        activity = ScriptActivity.objects.create(
            **{'activity_uuid': uuid.uuid4(), 'action': 'create', 'message': 'new contributor added',
               'details': {'created_by': user_data.get('user_id')}})
        activity.save()
        return Response('Contributor added', status=status.HTTP_201_CREATED)


class ContributorRetrieveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def get_user_id(self, request):
        data = token_validator(request)
        return data

    def get_object(self, contributor_uuid):
        try:
            return Contributor.objects.get(contributor_uuid=contributor_uuid)
        except Contributor.DoesNotExist:
            return None

    def get(self, request, contributor_uuid):
        user_data = self.get_user_id(request)
        if not user_data.get('user_id'):
            return Response(user_data.get('message'), status=status.HTTP_401_UNAUTHORIZED)

        contributor = self.get_object(contributor_uuid)
        if contributor:
            serializer = ContributorSerializer(contributor)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response({'error': 'Contributor not found'}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, contributor_uuid):
        user_data = self.get_user_id(request)
        if not user_data.get('user_id'):
            return Response(user_data.get('message'), status=status.HTTP_401_UNAUTHORIZED)

        contributor = self.get_object(contributor_uuid)
        if contributor:
            serializer = ContributorUpdateSerializer(contributor, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                activity = ScriptActivity.objects.create(
                    **{'activity_uuid': uuid.uuid4(), 'action': 'update',
                       'message': f'contributor {contributor_uuid} updated',
                       'details': {'created_by': user_data.get('user_id')}})
                activity.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response('Contributor not found', status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, contributor_uuid):
        user_data = self.get_user_id(request)
        if not user_data.get('user_id'):
            return Response(user_data.get('message'), status=status.HTTP_401_UNAUTHORIZED)

        contributor = self.get_object(contributor_uuid)
        if contributor:
            contributor.delete()
            activity = ScriptActivity.objects.create(
                **{'activity_uuid': uuid.uuid4(), 'action': 'delete',
                   'message': f'contributor {contributor_uuid} deleted',
                   'details': {'created_by': user_data.get('user_id')}})
            activity.save()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response('No contributor found', status=status.HTTP_404_NOT_FOUND)
