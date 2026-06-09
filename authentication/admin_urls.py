from django.urls import path
from .admin_views import UserListView , UserToggleActiveView , UserDeleteView , CreateUserView ,  UserUpdateView , SuperAdminKPIView
urlpatterns=[
    path('users/', UserListView.as_view(), name='admin_user_list'),
    path('users/<int:user_id>/toggle/', UserToggleActiveView.as_view(), name='admin_user_toggle'),
    path('users/<int:user_id>/delete/', UserDeleteView.as_view(), name='admin_user_delete'),
    path('users/create/', CreateUserView.as_view(), name='admin_create_user'),
    #update user
    path('users/<int:user_id>/update/',UserUpdateView.as_view(), name='user_update'),
    path('kpis/', SuperAdminKPIView.as_view(), name='admin-kpis'),
]