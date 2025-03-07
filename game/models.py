from django.db import models
from django.contrib.auth.models import User

class Game(models.Model):
    game_id = models.IntegerField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Player(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    character = models.CharField(max_length=50, blank=True)
    location = models.CharField(max_length=50, blank=True)
    cards = models.JSONField(default=list)
    has_moved = models.BooleanField(default=False)  # Track if player has made their first move

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['game', 'character'], name='unique_character_per_game')
        ]

class GameState(models.Model):
    game = models.OneToOneField(Game, on_delete=models.CASCADE)
    solution = models.JSONField()
    current_turn = models.ForeignKey(Player, null=True, on_delete=models.SET_NULL)