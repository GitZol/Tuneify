"""
URL configuration for SpotifyProject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, re_path, include
from django.conf import settings
from django.conf.urls.static import static
from tuneify import views
from django.contrib.auth.views import LoginView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('get_listening_history/', views.get_listening_history, name='get_listening_history'),
    path('spotify_auth/', views.spotify_auth, name='spotify_auth'),
    path('spotify_callback/', views.spotify_callback, name='spotify_callback'),
    path('listening_history/', views.get_listening_history, name='listening_history'),
    path('', views.home, name='home'),
    path('spotify_profile/', views.spotify_profile, name='spotify_profile'),
    path('get_user_similarity_scores/', views.get_user_similarity_score, name='get_user_similarity_scores'),
    path('check_similarity/', views.check_similarity, name='check_similarity'),
    path('profile/', views.profile_view, name='profile'),
    path('create_and_add_playlist/', views.create_and_add_playlist, name='create_and_add_playlist'),
    # path('register_or_login/', views.register_or_login, name='register_or_login'),
    path('register/', views.register_page, name='register_page'),
    path('login/', views.login_page, name='login_page'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('account/', views.account, name='account'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)