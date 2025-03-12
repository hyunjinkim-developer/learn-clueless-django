from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django import forms
from .models import Game, Player  # Import Game model from models.py
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

# Custom form for user signup
class SignupForm(forms.Form):
    username = forms.CharField(max_length=150, required=True)  # Username field with max length 150
    password = forms.CharField(widget=forms.PasswordInput, required=True)  # Password field with hidden input

# View to handle login and signup
def login_view(request):
    if request.method == 'POST':
        if 'login' in request.POST:  # Handle login submission
            form = AuthenticationForm(request, data=request.POST)
            if form.is_valid():
                user = form.get_user()  # Authenticate the user
                login(request, user)  # Log the user in
                return redirect('select_character', game_id=1)  # Redirect to character selection
        elif 'signup' in request.POST:  # Handle signup submission
            form = SignupForm(request.POST)
            if form.is_valid():
                username = form.cleaned_data['username']
                password = form.cleaned_data['password']
                if not User.objects.filter(username=username).exists():  # Check if username is unique
                    user = User.objects.create_user(username=username, password=password)  # Create new user
                    login(request, user)  # Log the new user in
                    return redirect('select_character', game_id=1)  # Redirect to character selection
                else:
                    form.add_error('username', 'Username already exists.')  # Add error if username taken
        else:
            form = AuthenticationForm() if 'login' in request.GET else SignupForm()  # Default form based on GET param
    else:
        form = AuthenticationForm() if 'login' not in request.GET else SignupForm()  # Default form for GET request
    return render(request, 'game/login.html', {'form': form, 'show_signup': 'signup' in request.GET})  # Render login/signup page

# View to handle user logout
def logout_view(request):
    logout(request)  # Log the user out
    return redirect('login')  # Redirect to login page

# View to allow players to select a character
def select_character_view(request, game_id):
    print(f"Request user: {request.user}, Game ID: {game_id}")  # Log request details
    game, _ = Game.objects.get_or_create(game_id=game_id)  # Get or create game instance
    print(f"Game created: {game}")  # Log game instance
    taken_characters = Player.objects.filter(game=game, character__isnull=False).values_list('character', flat=True)  # Get taken characters
    print(f"Taken characters: {taken_characters}")  # Log taken characters
    all_characters = [
        'Miss Scarlet', 'Col. Mustard', 'Mrs. White',
        'Mr. Green', 'Mrs. Peacock', 'Prof. Plum'  # Added Mrs. Peacock
    ]  # List of all possible characters
    available_characters = [char for char in all_characters if char not in taken_characters]  # Filter available characters
    print(f"Available characters: {available_characters}")  # Log available characters

    player = Player.objects.filter(user=request.user, game=game).first()  # Get current player's record
    print(f"Player: {player}")  # Log player instance
    if player and player.character and player.character in all_characters:
        print("Redirecting to game view")  # Log redirect
        return redirect('game', game_id=game_id)  # Redirect if character already selected

    if request.method == 'POST':
        selected_character = request.POST.get('character')  # Get selected character from form
        print(f"Selected character: {selected_character}")  # Log selected character
        if selected_character in available_characters:
            initial_locations = {
                'Miss Scarlet': 'Hallway2',  # Initial location for Miss Scarlet
                'Col. Mustard': 'Hallway5',  # Initial location for Col. Mustard
                'Mrs. White': 'Hallway12',  # Initial location for Mrs. White
                'Mr. Green': 'Hallway11',  # Initial location for Mr. Green
                'Mrs. Peacock': 'Hallway8',  # Initial location for Mrs. Peacock
                'Prof. Plum': 'Hallway3'  # Initial location for Prof. Plum
            }  # Mapping of characters to initial locations with new hallway names
            initial_location = initial_locations.get(selected_character)  # Get initial location, returns None if not found
            print(f"Initial location: {initial_location}")  # Log initial location
            if not initial_location:
                print("No initial location found, rendering error")  # Log error case
                return render(request, 'game/select_character.html', {
                    'game_id': game_id,
                    'available_characters': available_characters,
                    'error': f'No initial location defined for {selected_character}.'
                })  # Render with error if location missing
            player, created = Player.objects.get_or_create(user=request.user, game=game)  # Get or create player
            print(f"Player created: {created}, Player: {player}")  # Log player creation
            player.character = selected_character  # Assign character
            player.location = initial_location  # Assign initial location
            player.save()  # Save player record
            # Broadcast updated player list to all clients
            channel_layer = get_channel_layer()
            print("Broadcasting player list")  # Log broadcast start
            async_to_sync(channel_layer.group_send)(
                f'game_{game_id}',
                {
                    'type': 'player_list_message',
                    'player_list': list(Player.objects.filter(game=game).values('id', 'character', 'location', 'has_moved', 'user__username'))
                }
            )
            # Broadcast initial board update to place character
            print("Broadcasting initial board update")  # Log board update
            async_to_sync(channel_layer.group_send)(
                f'game_{game_id}',
                {
                    'type': 'game_message',
                    'character': selected_character,
                    'from': '',  # No previous location for initial setup
                    'to': player.location
                }
            )
            print("Redirecting to game page")  # Log redirect
            return redirect('game', game_id=game_id)  # Redirect to game page
        else:
            print("Invalid character selection")  # Log invalid selection
            return render(request, 'game/select_character.html', {
                'game_id': game_id,
                'available_characters': available_characters,
                'error': 'Invalid character selection or character already taken.'
            })  # Render with error if invalid
    print("Rendering select character page")  # Log rendering
    return render(request, 'game/select_character.html', {
        'game_id': game_id,
        'available_characters': available_characters
    })  # Render character selection page

# View to display the game board
def game_view(request, game_id):
    game, _ = Game.objects.get_or_create(game_id=game_id)  # Get or create game instance
    player = Player.objects.filter(user=request.user, game=game).first()  # Get current player
    if not player or not player.character:
        return redirect('select_character', game_id=game_id)  # Redirect if no character selected
    players = Player.objects.filter(game=game).values('id', 'character', 'location', 'has_moved', 'user__username')  # Get all players' data
    return render(request, 'game/game.html', {
        'game_id': game_id,
        'players': list(players),  # Pass players data to template
        'request': request  # Explicitly pass request to ensure context processors work
    })