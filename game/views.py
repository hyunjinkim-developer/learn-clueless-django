from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django import forms
from .models import Game, Player
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

# Custom form for signup
class SignupForm(forms.Form):
    username = forms.CharField(max_length=150, required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)

def login_view(request):
    if request.method == 'POST':
        if 'login' in request.POST:
            form = AuthenticationForm(request, data=request.POST)
            if form.is_valid():
                user = form.get_user()
                login(request, user)
                return redirect('select_character', game_id=1)
        elif 'signup' in request.POST:
            form = SignupForm(request.POST)
            if form.is_valid():
                username = form.cleaned_data['username']
                password = form.cleaned_data['password']
                if not User.objects.filter(username=username).exists():
                    user = User.objects.create_user(username=username, password=password)
                    login(request, user)  # Auto-login after signup
                    return redirect('select_character', game_id=1)
                else:
                    form.add_error('username', 'Username already exists.')
        else:
            form = AuthenticationForm() if 'login' in request.GET else SignupForm()
    else:
        form = AuthenticationForm() if 'login' not in request.GET else SignupForm()
    return render(request, 'game/login.html', {'form': form, 'show_signup': 'signup' in request.GET})

def logout_view(request):
    logout(request)
    return redirect('login')

def select_character_view(request, game_id):
    game, _ = Game.objects.get_or_create(game_id=game_id)
    taken_characters = Player.objects.filter(game=game, character__isnull=False).values_list('character', flat=True)
    all_characters = [
        'Miss Scarlet', 'Col. Mustard', 'Mrs. White',
        'Mr. Green', 'Mrs. Peacock', 'Prof. Plum'
    ]
    available_characters = [char for char in all_characters if char not in taken_characters]

    # Check if player already has a character for this game
    player = Player.objects.filter(user=request.user, game=game).first()
    if player and player.character and player.character in all_characters:
        return redirect('game', game_id=game_id)

    if request.method == 'POST':
        selected_character = request.POST.get('character')
        if selected_character in available_characters:
            initial_locations = {
                'Miss Scarlet': 'Hallway23',
                'Col. Mustard': 'Hallway36',
                'Mrs. White': 'Hallway89',
                'Mr. Green': 'Hallway78',
                'Mrs. Peacock': 'Hallway47',
                'Prof. Plum': 'Hallway14'
            }
            player, created = Player.objects.get_or_create(user=request.user, game=game)
            player.character = selected_character
            player.location = initial_locations.get(selected_character)
            if not player.location:
                player.location = 'Hallway12'
            player.save()
            # Broadcast the updated player list
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'game_{game_id}',
                {
                    'type': 'player_list_message',
                    'player_list': list(
                        Player.objects.filter(game=game).values('id', 'character', 'location', 'has_moved',
                                                                'user__username'))
                }
            )
            return redirect('game', game_id=game_id)
        else:
            return render(request, 'game/select_character.html', {
                'game_id': game_id,
                'available_characters': available_characters,
                'error': 'Invalid character selection or character already taken.'
            })

    return render(request, 'game/select_character.html', {
        'game_id': game_id,
        'available_characters': available_characters
    })


def game_view(request, game_id):
    game, _ = Game.objects.get_or_create(game_id=game_id)
    player = Player.objects.filter(user=request.user, game=game).first()
    if not player or not player.character:
        return redirect('select_character', game_id=game_id)

    players = Player.objects.filter(game=game).values('id', 'character', 'location', 'has_moved', 'user__username')
    return render(request, 'game/game.html', {
        'game_id': game_id,
        'players': list(players)
    })