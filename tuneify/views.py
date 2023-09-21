from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from .models import UserProfile
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from spotipy.exceptions import SpotifyException
# Create your views here.
scopes = 'user-library-read user-read-private user-read-email user-read-recently-played'


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            #create a user profile for the registered user
            display_name = request.POST['display_name']
            profile_picture = request.FILES.get('profile_picture')
            UserProfile.objects.create(user=user, display_name=display_name, profile_picture=profile_picture)
            login(request, user)
            return redirect('dashboard') #replace with dashboard url
    
    else:
        form= UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

def spotify_auth(request):
    sp_oauth = SpotifyOAuth(
        settings.SPOTIPY_CLIENT_ID,
        settings.SPOTIPY_CLIENT_SECRET,
        settings.SPOTIPY_REDIRECT_URL,
        scope=scopes,
    )
    auth_url = f"https://accounts.spotify.com/authorize?client_id={sp_oauth.client_id}&response_type=code&redirect_uri={sp_oauth.redirect_uri}&scope={sp_oauth.scope}"
    return redirect(auth_url)

def spotify_callback(request):
    sp_oauth = SpotifyOAuth(
        settings.SPOTIPY_CLIENT_ID,
        settings.SPOTIPY_CLIENT_SECRET,
        settings.SPOTIPY_REDIRECT_URL,
    )
    token_info = sp_oauth.get_access_token(request.GET.get('code'))

    if not token_info:
        messages.error(request, 'Spotify authentication failed. Please tryb again.')
        return redirect('spotify_auth')
    
    request.session['spotify_access_token'] = token_info['access_token']

    return redirect('spotify_profile')

def spotify_profile(request):
    access_token = request.session.get('spotify_access_token')

    if not access_token:
        messages.error(request, 'Spotify access token not found. Please authenticate with Spotify first.')
        return redirect('spotify_auth')

    try:
        sp = spotipy.Spotify(auth=access_token)
        user_profile = sp.current_user()
    except SpotifyException as e:
        messages.error(request, f'Spotify API error: {e}')
        return redirect('home')
        

    return render(request, 'spotify/profile.html', {'user_profile':user_profile})

def get_listening_history(request):
    #get user's access token from the session
    print(request.session.get('spotify_access_token'))
    access_token = request.session.get('spotify_access_token')

    if not access_token:
        # handle the case where there is no access token
        return JsonResponse({'error': 'User is not authenticated.'}, status=401)
    
    #initialise spotify client
    sp = spotipy.Spotify(auth=access_token)

    try:
        # Retrieve user's listening history
        listening_history = sp.current_user_recently_played(limit=50)

    except spotipy.SpotifyException as e:
        # Handle spotify API errors
        if "Insufficient client scope" in str(e):
            return JsonResponse({'error': 'Insufficient client scope. Make sure you have the required scope.'}, status=403)
        else:
            return JsonResponse({'error': str(e)}, status=500)
    
    context = {
        'listening_history' : listening_history,
    }
    return render(request, 'listening_history.html', context)

def home(request):
    return render(request, 'spotify/home.html')