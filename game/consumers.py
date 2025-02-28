from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Game, Player
import json

class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.game_id = self.scope['url_route']['kwargs']['game_id']
        self.game_group_name = f'game_{self.game_id}'
        self.user = self.scope['user']

        await self.add_player_to_game()
        await self.channel_layer.group_add(self.game_group_name, self.channel_name)
        await self.accept()

        players = await self.get_players_in_game()
        await self.channel_layer.group_send(
            self.game_group_name,
            {'type': 'game_message', 'message': f"{self.user.username} joined! Players: {', '.join(players)}"}
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.game_group_name, self.channel_name)
        players = await self.get_players_in_game()
        await self.channel_layer.group_send(
            self.game_group_name,
            {'type': 'game_message', 'message': f"{self.user.username} left! Players: {', '.join(players)}"}
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data['action'] == 'move':
            location = data['location']
            players = await self.get_players_in_game()
            await self.channel_layer.group_send(
                self.game_group_name,
                {'type': 'game_message', 'message': f"{self.user.username} moved to {location}. Players: {', '.join(players)}"}
            )

    async def game_message(self, event):
        await self.send(text_data=json.dumps({'message': event['message']}))

    @database_sync_to_async
    def add_player_to_game(self):
        if self.user.is_authenticated:
            game, _ = Game.objects.get_or_create(game_id=self.game_id)
            Player.objects.get_or_create(user=self.user, game=game, defaults={'character': f"Detective_{self.user.username}"})

    @database_sync_to_async
    def get_players_in_game(self):
        game = Game.objects.get(game_id=self.game_id)
        return [player.user.username for player in Player.objects.filter(game=game)]