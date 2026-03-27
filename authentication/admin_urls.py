from django.urls import path
from .admin_views import UserListView , UsetToggleActiveView , UserDeleteView , CreateAdminView

urlpatterns=[
    path('users/', UserListView.as_view(), name='admin_user_list'),
    path('users/<int:user_id>/toggle/', UsetToggleActiveView.as_view(), name='admin_user_toggle'),
    path('users/<int:user_id>/delete/', UserDeleteView.as_view(), name='admin_user_delete'),
    path('users/create-admin/', CreateAdminView.as_view(), name='admin_create_admin')

]