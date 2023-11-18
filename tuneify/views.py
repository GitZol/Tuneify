from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login as auth_login, authenticate
from .models import UserProfile
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from spotipy.exceptions import SpotifyException
from datetime import datetime
from .models import ListeningHistory, UserProfile, SimilarityScore
from django.db.models import Count
from collections import defaultdict
from functools import wraps
from django.contrib.auth.models import User
from django.urls import reverse
import requests
import spotipy.util as util
from collections import Counter 
import json
from social_django.views import auth as social_auth
from social_core.backends.oauth import BaseOAuth2
from social_django.utils import psa
import googleapiclient.discovery
from googleapiclient.errors import HttpError
from .forms import CustomUserCreationForm
from django.contrib.auth.views import LogoutView
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash


# Create your views here.
scopes = 'user-library-read user-read-private user-read-email user-read-recently-played user-top-read playlist-modify-public playlist-modify-private'


def spotify_auth(request):
    sp_oauth = SpotifyOAuth(
        settings.SPOTIPY_CLIENT_ID,
        settings.SPOTIPY_CLIENT_SECRET,
        settings.SPOTIPY_REDIRECT_URL,
        scope=scopes,
    )
    auth_url = f"https://accounts.spotify.com/authorize?client_id={sp_oauth.client_id}&response_type=code&redirect_uri={sp_oauth.redirect_uri}&scope={sp_oauth.scope}"

    if request.user.is_authenticated:

        if UserProfile.objects.filter(user=request.user).exists():
            return HttpResponse("You have already linked a Spotify account.")
        return redirect(auth_url)

    else:
        return redirect('register_page')
    

@login_required(login_url='login_page')
def spotify_profile(request):
    access_token = request.session.get('spotify_access_token')

    if not access_token:
        messages.error(request, 'Spotify access token not found. Please authenticate with Spotify first.')
        return redirect('spotify_auth')
    
    try:
        sp = spotipy.Spotify(auth=access_token)
        current_user = sp.current_user()
        display_name = current_user['display_name']
        user_id = current_user['id']
        profile_picture_url = current_user['images'][0]['url'] if 'images' in current_user and current_user['images'] else None
        recently_played_tracks = sp.current_user_recently_played(limit=50)
        top_artists = sp.current_user_top_artists(limit=10)

        obscurity_scores = calculate_music_obscurity(request, recently_played_tracks)

        seed_tracks = [track['track']['uri'] for track in recently_played_tracks.get('items', [])]
        
        recommended_tracks = get_music_recommendations(access_token, seed_tracks, limit=50)

        if request.method == 'POST':
            if 'create-playlist' in request.POST:
                playlist_name = "Tuneify Recommended Tracks Playlist"
                create_and_add_playlist(access_token, user_id, playlist_name, [track['uri'] for track in recommended_tracks])
                messages.success(request, 'Playlist created successfully!')

                return HttpResponseRedirect(reverse('spotify_profile'))

        top_tracks = sp.current_user_top_tracks(limit=10)
        top_genres = get_top_genres(request)

        unique_tracks_uris = set()
        unique_recently_played_tracks = []


        for track_data in recently_played_tracks.get('items', []):
            track_uri = track_data['track']['uri']

            if track_uri not in unique_tracks_uris:
                track_info = sp.track(track_uri)

                if 'album' in track_info and 'images' in track_info['album'] and len(track_info['album']['images']) > 0:
                    track_data['track_image_url'] = track_info['album']['images'][0]['url']

                    unique_recently_played_tracks.append(track_data)
                    unique_tracks_uris.add(track_uri)


        top_tracks_with_images = []
        top_artists_with_images = []

        for track in top_tracks['items']:
            cover_url = get_album_cover_url(track, access_token)

            if cover_url:
                track['album_cover_url'] = cover_url
                top_tracks_with_images.append(track)

        for artist in top_artists['items']:
            artist_info = sp.artist(artist['id'])

            if 'images' in artist_info and artist_info['images']:
                images_url = artist_info['images'][0]['url']
                artist['artist_image_url'] = images_url

            else:
                artist['artist_image_url'] = None

            top_artists_with_images.append(artist)

        context = {
            'display_name': display_name,
            'profile_picture_url': profile_picture_url,
            'recently_played_tracks': unique_recently_played_tracks,
            'top_artists': top_artists_with_images,
            'recommended_tracks': recommended_tracks,
            'top_tracks': top_tracks_with_images,
            'obscurity_scores': obscurity_scores,
            'top_genres': top_genres,
        }

    except SpotifyException as e:
        messages.error(request, f'Spotify API error: {e}')
        return redirect('home')
    except Exception as e:
        messages.error(request, f'An error occurred: {e}')
        return redirect('home')
    
    return render(request, 'spotify/profile.html', context)

from SpotifyProject import settings as st
def spotify_authroize(request):
    authorization_url = 'https://accounts.spotify.com/authrorize'
    redirect_uri = request.build_absolute_uri(reverse('spotify_callback'))

    client_id = st.SPOTIPY_CLIENT_ID
    params = {
        'client_id' : client_id,
        'redirect_uri' : redirect_uri,
        'response_type' : 'code',
        'scope' : scopes,
    }
    authorization_uri = f'{authorization_url}?client_id={params["client_id"]}&redirect_uri={params["redirect_uri"]}&response_type={params["response_type"]}&scope={params["scope"]}'

    return redirect(authorization_uri)

def spotify_callback(request):
    code = request.GET.get('code')

    token_url = 'https://accounts.spotify.com/api/token'
    client_id = st.SPOTIPY_CLIENT_ID
    client_secret = st.SPOTIPY_CLIENT_SECRET
    data = {
        'client_id' : client_id,
        'client_secret' : client_secret,
        'grant_type' : 'authorization_code',
        'code' : code,
        'redirect_uri' : request.build_absolute_uri(reverse('spotify_callback')),
    }
    response = requests.post(token_url, data=data)

    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data['access_token']
        request.session['spotify_access_token'] = access_token

        messages.success(request, 'Successfully authenticated with Spotify.')

        return redirect('home')
    
    else:
        messages.error(request, 'Failed to authenticated with Spotofy. Please try again later.')
        return redirect('home')
    
def get_album_cover_url(track, access_token):
    sp = spotipy.Spotify(auth=access_token)
    track_info = sp.track(track['uri'])
    if 'album' in track_info and 'images' in track_info['album'] and len(track_info['album']['images']) > 0:
        return track_info['album']['images'][0]['url']
    return None

def profile_view(request):
    # Your profile view logic here
    return render(request, 'spotify/profile.html')  # Render a template for the profile page


def get_listening_history(request):
    #get user's access token from the session
    access_token = request.session.get('spotify_access_token')

    if not access_token:
        # handle the case where there is no access token
        return JsonResponse({'error': 'User is not authenticated.'}, status=401)
    

    try:
        #initialise spotify client
        sp = spotipy.Spotify(auth=access_token)
        # Retrieve user's listening history
        listening_history = sp.current_user_recently_played(limit=10)

        request.session['listening_history'] = listening_history
    except spotipy.SpotifyException as e:
        # Handle spotify API errors
        if "Insufficient client scope" in str(e):
            return JsonResponse({'error': 'Insufficient client scope. Make sure you have the required scope.'}, status=403)
        else:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'success': 'listening history retrieved and stored in  session. '})
 
def save_listening_history(request):
    access_token = request.session.get('spotify_access_token')

    if not access_token:
        return JsonResponse({'error': 'User is not authenticated.'}, status=401 )
    
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(access_token))

    try:
        recent_tracks = sp.current_user_saved_albums(limit=10)

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
    listening_history = request.session.get('listening_history', [])

    context = {
        'recently_played_tracks' : listening_history, 
    }
    return render(request, 'spotify/home.html', context)

def about(request):
    access_token = request.session.get('spotify_access_token')

    if not access_token:
        messages.error(request, 'Spotify access token not found. Please authenticate with Spotify first.')
        return redirect('spotify_auth')
    
    try:
        sp = spotipy.Spotify(auth=access_token)
        current_user = sp.current_user()
        profile_picture_url = current_user['images'][0]['url'] if 'images' in current_user and current_user['images'] else None

        context = {
            'profile_picture_url': profile_picture_url,
            }
        
    except SpotifyException as e:
        messages.error(request, f'Spotify API error: {e}')
        return redirect('home')
    except Exception as e:
        messages.error(request, f'An error occurred: {e}')
        return redirect('home')
    
    return render(request, 'spotify/about.html', context)

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


def get_music_recommendations(access_token, seed_tracks, limit=50):
    try:
        sp = spotipy.Spotify(auth=access_token)
        
        top_5_tracks = seed_tracks[:5]
        recommendations = sp.recommendations(seed_tracks= top_5_tracks, limit=limit)

        if 'error' in recommendations:
            print("Spotify API Error:", recommendations['error'])

        recommended_tracks = recommendations.get('tracks', [])

        for track in recommended_tracks:
            album_uri = track['album']['uri']
            album_info = sp.album(album_uri)

            if 'images' in album_info and len(album_info['images']) > 0:
                track['album_cover_url'] = album_info['images'][0]['url']    

        return recommended_tracks
    except Exception as e:
        print("An error occurred:", e)
        return []


def create_and_add_playlist(access_token, user_id, playlist_name, tracks_uris):
    try:
        sp = spotipy.Spotify(auth=access_token)

        playlist = sp.user_playlist_create(user_id, playlist_name)

        sp.user_playlist_add_tracks(user_id, playlist['id'], tracks_uris)

        return playlist
    except Exception as e:
        print("An error occurred:", e)
        return None
    
def calculate_music_obscurity(request, recently_played_tracks):
    access_token = request.session.get('spotify_access_token')

    if not access_token:
        messages.error(request, 'Spotify access token not found. Please authenticate with Spotify first.')
        return redirect('spotify_auth')
    
    try:
        sp = spotipy.Spotify(auth=access_token)
        obscurity_threshold = 60

        obscurity_scores = []
        total_popularity_score = 0

        for track in recently_played_tracks['items']:
            track_name = track['track']['name']
            track_popularity = track['track']['popularity']
            total_popularity_score += track_popularity
            track_uri = track['track']['uri']
            track_info = sp.track(track_uri)

            if track_popularity < obscurity_threshold:
                track_image_url = track_info['album']['images'][0]['url']
                obscurity_scores.append({
                    'track_name': track_name,
                    'obscurity_score': track_popularity,
                    'track_image_url' : track_image_url,
                    })

        overall_obscurity_score = (
        sum(score['obscurity_score'] for score in obscurity_scores) / len(recently_played_tracks['items'])
        if recently_played_tracks['items']
        else 0
        )

        obscurity_percentage = (1 - overall_obscurity_score) * 100

        return obscurity_scores, overall_obscurity_score, obscurity_percentage
    
    except spotipy.SpotifyException as e:
        messages.error(request, f'Spotify API error: {e}')
        return redirect('home')
    except Exception as e:
        messages.error(request, f'An error occurred: {e}')
        return redirect('home')
    
def get_top_genres(request):
    access_token = request.session.get('spotify_access_token')
    sp = spotipy.Spotify(auth=access_token)

    top_artitst = sp.current_user_top_artists(limit=20)

    genre_counts = {}
    for artist in top_artitst['items']:
        artist_details = sp.artist(artist['id'])
        artist_genres = artist_details['genres']
        for genre in artist_genres:
            if genre in genre_counts:
                genre_counts[genre] += 1
            else:
                genre_counts[genre]= 1

    top_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    return top_genres

def register_page(request):
    registration_form = UserCreationForm(request.POST)

    if request.method == 'POST':
        if registration_form.is_valid():
            user = registration_form.save()
            auth_login(request, user)
            print("user regitered")
            return redirect('spotify_profile')
        else:
            print("user not registered")
        
    return render(request, 'registration_form.html', {'registration_form': registration_form})
    

def login_page(request):
    login_form = AuthenticationForm()

    if request.method == 'POST':
        login_form = AuthenticationForm(request, request.POST)
        if login_form.is_valid():
            user = login_form.get_user()
            auth_login(request, user)
            print("user is valid")
            return redirect('spotify_profile')
        else:
            print("user not valid")
    return render(request, 'login_form.html', {'login_form': login_form})

class CustomLogoutView(LogoutView):
    template_name = 'logout.html'

    def get(self, *args, **kwargs):
        self.request.session.flush()
        messages.success(self.request, 'You have been logged out successfully.')
        return super().get(*args, **kwargs)

@login_required
def account(request):
    access_token = request.session.get('spotify_access_token')

    if not access_token:
        messages.error(request, 'Spotify access token not found. Please authenticate with Spotify first.')
        return redirect('spotify_auth')
    
    try:
        sp = spotipy.Spotify(auth=access_token)
        current_user = sp.current_user()
        profile_picture_url = current_user['images'][0]['url'] if 'images' in current_user and current_user['images'] else None

    except SpotifyException as e:
        messages.error(request, f'Spotify API error: {e}')
        return redirect('home')
    except Exception as e:
        messages.error(request, f'An error occurred: {e}')
        return redirect('home')

    password_change_form = PasswordChangeForm(request.user)
    if request.method == "POST":
        password_change_form = PasswordChangeForm(request.user)
        if password_change_form.is_valid():
            user = password_change_form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updates.')
            return redirect('account')
        else:
            messages.error(request, "Please correct the error(s) below.")
    else:
        password_change_form = PasswordChangeForm(request.user)

    return render(request, 'spotify/account.html', {'user': request.user, 'password_change_form' : password_change_form, 'profile_picture_url': profile_picture_url})