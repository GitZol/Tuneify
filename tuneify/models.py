from django.db import models
from django.contrib.auth.models import User
# Create your models here.

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    display_name = models.CharField(max_length=255)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)

class ListeningHistory(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    song_name = models.CharField(max_length=255)
    artist = models.CharField(max_length=255)
    timestamp = models.DateTimeField()

class SimilarityScore(models.Model):
    user1 = models.ForeignKey(UserProfile, related_name='user1_scores', on_delete=models.CASCADE)
    user2 = models.ForeignKey(UserProfile, related_name='user2_scores', on_delete=models.CASCADE)
    score = models.FloatField()