from django.urls import path
from .views import *

urlpatterns = [
    path('api/v1/scripts/', ScriptView.as_view(), name='testing'),
]
