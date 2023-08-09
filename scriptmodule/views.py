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
        # return Response('done')
