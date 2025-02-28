from django.db import models
from django.contrib.auth.models import User

class Game(models.Model):
    game_id = models.IntegerField(unique=True)
    current_turn = models.ForeignKey('Player', null=True, on_delete=models.SET_NULL, related_name='current_game')

class Player(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    character = models.CharField(max_length=50)