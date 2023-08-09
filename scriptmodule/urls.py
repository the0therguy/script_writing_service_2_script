from django.urls import path
from .views import *

urlpatterns = [
    path('api/v1/scripts/', ScriptView.as_view(), name='get-and-create-script'),
    path('api/v1/contributors/<str:script_uuid>/', ContributorView.as_view(), name='get-and-create-contributors'),
    path('api/v1/contributor/<str:contributor_uuid>/', ContributorRetrieveView.as_view(),
         name='contributor-get-update-delete')
]
