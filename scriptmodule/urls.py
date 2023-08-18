from django.urls import path
from .views import *

urlpatterns = [
    path('api/v1/scripts/', ScriptView.as_view(), name='get-and-create-script'),
    path('api/v1/contributors/<str:script_uuid>/', ContributorView.as_view(), name='get-and-create-contributors'),
    path('api/v1/contributor/<str:contributor_uuid>/', ContributorRetrieveView.as_view(),
         name='contributor-get-update-delete'),
    path('api/v1/storydocs/<str:script_uuid>/', StoryDocsListCreateView.as_view(), name='story-list-create-view'),
    path('api/v1/storydoc/<str:script_uuid>/', StoryDocsRetrieveUpdateDeleteView.as_view(),
         name='story-docs-update-delete'),
    path('api/v1/sub-stories/<str:script_uuid>/', SubStoryDocsListCreateView.as_view(),
         name='sub-story-list-create-view'),
    path('api/v1/sub-story/<str:sub_story_uuid>/', SubStoryRetrieveView.as_view(), name='sub-story-get-put-delete'),
    path('api/v1/acts/<str:script_uuid>/', ActListView.as_view(), name='acts-get-create'),
    path('api/v1/act/<str:act_uuid>/', ActRetrieveView.as_view(), name='act-get-put-delete'),
    path('api/v1/scenes/<str:script_uuid>/<str:act_uuid>/', SceneCreateView.as_view(), name='scene-get-create'),
    path('api/v1/scene/<str:script_uuid>/<str:act_uuid>/<str:scene_uuid>/', SceneRetrieveView.as_view(),
         name='scene-get-update-delete'),
    path('api/v1/location/<str:script_uuid>/<str:act_uuid>/<str:scene_uuid>/', LocationRetrieveView.as_view(),
         name='location-get-update'),
    path('api/v1/arche-types/<str:script_uuid>/', ArcheTypeListCreate.as_view(), name='archi-types-get-create'),
    path('api/v1/arche-type/<str:script_uuid>/<str:arche_type_uuid>/', ArcheRetrieveView.as_view(), name='archi'
                                                                                                           '-type-get'),
]
