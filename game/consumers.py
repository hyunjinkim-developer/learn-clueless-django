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

        await self.channel_layer.group_send(
            self.game_group_name,
            {'type': 'game_message', 'message': f"{self.user.username} joined!"}
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.game_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data['action'] == 'move':
            location = data['location']
            await self.channel_layer.group_send(
                self.game_group_name,
                {'type': 'game_message', 'message': f"{self.user.username} moved to {location}"}
            )

    async def game_message(self, event):
        await self.send(text_data=json.dumps({'message': event['message']}))

    @database_sync_to_async
    def add_player_to_game(self):
        if self.user.is_authenticated:
            game, _ = Game.objects.get_or_create(game_id=self.game_id)
            Player.objects.get_or_create(user=self.user, game=game, defaults={'character': 'Detective'})