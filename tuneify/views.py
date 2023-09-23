from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login as auth_login
from .models import UserProfile
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from spotipy.exceptions import SpotifyException
from datetime import datetime
from .models import ListeningHistory, UserProfile, SimilarityScore
from django.db.models import Count
from collections import defaultdict
from functools import wraps
from django.contrib.auth.models import User
from django.urls import reverse
import requests

# Create your views here.
scopes = 'user-library-read user-read-private user-read-email user-read-recently-played'


def spotify_auth(request):
    sp_oauth = SpotifyOAuth(
        settings.SPOTIPY_CLIENT_ID,
        settings.SPOTIPY_CLIENT_SECRET,
        settings.SPOTIPY_REDIRECT_URL,
        scope=scopes,
    )
    auth_url = f"https://accounts.spotify.com/authorize?client_id={sp_oauth.client_id}&response_type=code&redirect_uri={sp_oauth.redirect_uri}&scope={sp_oauth.scope}"
    return redirect(auth_url)

def spotify_profile(request):
    access_token = request.session.get('spotify_access_token')

    if not access_token:
        messages.error(request, 'Spotify access token not found. Please authenticate with Spotify first.')
        return redirect('spotify_auth')
    
    try:
        sp = spotipy.Spotify(auth=access_token)
        current_user = sp.current_user()
        display_name = current_user['display_name']

    except SpotifyException as e:
        messages.error(request, f'Spotify API error: {e}')
        return redirect('home')
    
    return render(request, 'spotify/profile.html', {'display_name': display_name})


def spotify_authroize(request):
    authorization_url = 'https://accounts.spotify.com/authrorize'
    redirect_url = request.build_absolute_uri(reverse('spotify_callback'))
    params = {
        'client_id' : 'your_client_id',
        'redirect_uri' : redirect_url,
        'response_type' : 'code',
        'scope' : scopes,
    }
    authorization_uri = f'{authorization_url}?client_id={params["client_id"]}&redirect_uri ={params["redirect_uri"]}&response_type={params["response_type"]}&scope={params["scope"]}'

    return redirect(authorization_url)

def spotify_callback(request):
    code = request.GET.get('code')

    token_url = 'https://accounts.spotify.com/api/token'
    data = {
        'client_id' : 'c9341baf78624ba987043a8966bb724b',
        'client_secret' : '9feb6c5393374b0d9bea14dc391ecccb',
        'grant_type' : 'authorization_code',
        'code' : code,
        'redirect_uri' : request.build_absolute_uri(reverse('spotify_callback')),
    }
    response = requests.post(token_url, data=data)

    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data['access_token']

        return redirect('home')
    
    else:
        return redirect('error_page')
    

def profile_view(request):
    # Your profile view logic here
    return render(request, 'profile.html')  # Render a template for the profile page



# def spotify_callback(request):
#     sp_oauth = SpotifyOAuth(
#         settings.SPOTIPY_CLIENT_ID,
#         settings.SPOTIPY_CLIENT_SECRET,
#         settings.SPOTIPY_REDIRECT_URL,
#     )
#     token_info = sp_oauth.get_access_token(request.GET.get('code'))

#     if not token_info:
#         messages.error(request, 'Spotify authentication failed. Please tryb again.')
#         return redirect('spotify_auth')
    
#     access_token = token_info['access_token']
    
#     try:
#         sp = spotipy.Spotify(auth=access_token)
#         current_user = sp.current_user()
#         spotify_id = current_user['id']
#         display_name = current_user['display_name']

#         # auth_login(request, user_profile.user)

#     except SpotifyException as e:
#         messages.error(request, f'Spotify API error: {e}')
#         return redirect('home')
    
#     user_profile, created = UserProfile.objects.get_or_create(spotify_id = spotify_id, defaults={'display_name': display_name})

#     if created:
#         user, _ = User.objects.get_or_create(username=spotify_id)
#         user.userprofile = user_profile
#         user.save()

#     #Store the access token
#     request.session['spotify_access_tjjoken'] = access_token

#     return redirect('spotify_profile')

def get_listening_history(request):
    #get user's access token from the session
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
    
    return JsonResponse({'listening_history': listening_history}, safe=False)
 
def save_listening_history(request):
    access_token = request.session.get('spotify_access_token')

    if not access_token:
        return JsonResponse({'error': 'User is not authenticated.'}, status=401 )
    
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(access_token))

    try:
        recent_tracks = sp.current_user_saved_albums(limit=50)

        for track in recent_tracks['items']:
            song_name = track['track']['name']
            artist = track['track']['artists'][0]['name']
            timestamp = datetime.fromisoformat(track['played_at'])

            ListeningHistory.objects.create(
                user=request.user.userprofile,
                song_name=song_name,
                artist=artist,
                timestamp=timestamp
            )
        
        return HttpResponse('Listening history saved successfully.')
    
    except spotipy.SpotifyException as e:

        if "Insufficient client scope" in str(e):
            return JsonResponse({'error': 'Insufficient client scope. Make sure you have the required scope.'}, status=403)
        
        else:
            return JsonResponse({'error': str(e)}, status=500)

def home(request):
    return render(request, 'spotify/home.html')

def preprocess_listening_history(request):
    # get the listening history from the db
    user = request.user.userprofile
    listening_history_data = ListeningHistory.objects.filter(user=user)

    if not listening_history_data:
        return HttpResponse('No listening history data available.')
    
    #remove dupes
    unique_entries = []
    seen_entries = set()

    for entry in listening_history_data:
        key = (entry.song_name, entry.artist)
        if key not in seen_entries:
            unique_entries.append(entry)
            seen_entries.add(key)

    
    
    #calculate listening frequency for songs and artist
    song_counts = defaultdict(int)
    artist_counts = defaultdict(int)

    for entry in unique_entries:
        song_counts[entry.song_name] += 1
        artist_counts[entry.artist] += 1

    user_profiles = UserProfile.objects.all()
    user_listening_histories = defaultdict(list)

    for user_profile in user_profiles:
        listening_histories = ListeningHistory.objects.filter(user= user_profile)
        user_listening_histories[user_profile] = listening_histories

    # Calculate similarity
    similarity_scores = {}

    for user_profile1 in user_profiles:
        for user_profile2 in user_profiles:
            if user_profile1 != user_profile2:
                intersection = len(set(user_listening_histories[user_profile1]) & set(user_listening_histories[user_profile2]))                
                
                union = len(set(user_listening_histories[user_profile1]) | set(user_listening_histories[user_profile2]))

                similarity_score = intersection / union if union > 0 else 0

                similarity_scores[(user_profile1, user_profile2)] = similarity_score
    return JsonResponse({'similarity_scores': similarity_scores})

def get_user_similarity_score(request):
    user_profile = request.user.userprofile

    similarity_scores = SimilarityScore.objects.filter(user1=user_profile).order_by('-score')

    response_data = {
        'user_profile': user_profile.display_name,
        'similarity_scores' : [
            {
                'user_profile': score.user2.display_name,
                'score': score.score
            }
            for score in similarity_scores
        ]
    }

    return JsonResponse(response_data)

def spotify_authenticated_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwrgs):
        access_token = request.session.get('spotify_access_token')
        if not access_token:
            return redirect('spotify_auth')
        
        return view_func(request, *args, **kwrgs)
    
    return _wrapped_view

#@spotify_authenticated_required
def check_similarity(request):
    access_token = request.session.get('spotify_access_token')
    
    if not access_token:
        return redirect('spotify_auth')

    sp = spotipy.Spotify(auth=access_token)

    user_profile = getattr(request.user, 'userprofile', None)

    if user_profile:
        print(f'Access Token: {access_token}')
        print(f'User Profile Display Name: {user_profile.display_name}')

        similarity_scores = SimilarityScore.objects.filter(user1=user_profile).order_by('-score')
        print(similarity_scores)

        return render(request, 'spotify/similarity_results.html', {'similarity_scores': similarity_scores})
    else:
        return render(request, 'spotify/similarity_results.html', {'similarity_scores': []})

