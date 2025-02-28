from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import AuthenticationForm

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('game', game_id=1)
    else:
        form = AuthenticationForm()
    return render(request, 'game/login.html', {'form': form})

def game_view(request, game_id):
    if not request.user.is_authenticated:
        return redirect('login')
    return render(request, 'game/game.html', {'game_id': game_id})