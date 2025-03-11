from django.db import models
from django.contrib.auth.models import User

# Define the Game model to represent a game instance with a unique ID
class Game(models.Model):
    game_id = models.IntegerField(primary_key=True)  # Unique identifier for each game
    current_player_id = models.IntegerField(null=True, blank=True)  # Tracks whose turn it is, nullable for initial state

    def __str__(self):
        return f"Game {self.game_id}"  # String representation of the game

# Define the GameState model to store game state as JSON (e.g., cards, clues)
class GameState(models.Model):
    game = models.OneToOneField(Game, on_delete=models.CASCADE, primary_key=True)  # One-to-one relationship with Game
    state = models.JSONField(default=dict)  # JSON field to store dynamic game state

    def __str__(self):
        return f"State for Game {self.game.game_id}"  # String representation of the game state

# Define the Player model to represent players in a game
class Player(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # Foreign key to Django's User model, deletes player if user is deleted
    game = models.ForeignKey(Game, on_delete=models.CASCADE)  # Foreign key to Game model, deletes player if game is deleted
    character = models.CharField(max_length=20, null=True, blank=True)  # Player's character (e.g., "Miss Scarlet"), nullable
    location = models.CharField(max_length=20, default='Hallway1')  # Current location on the board, updated default to Hallway1
    cards = models.JSONField(default=list)  # List of cards held by the player, defaults to empty list
    has_moved = models.BooleanField(default=False)  # Tracks if player has made their first move

    def __str__(self):
        return f"{self.user.username} in {self.game.game_id}"  # String representation of the player