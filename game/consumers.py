from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import Game, Player
import json

# Debug
import logging
logger = logging.getLogger(__name__)

class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.game_id = self.scope['url_route']['kwargs']['game_id']
        self.game_group_name = f'game_{self.game_id}'
        self.user = self.scope['user']
        await self.add_player_to_game()
        await self.channel_layer.group_add(self.game_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.game_group_name, self.channel_name)

    async def receive(self, text_data):
        logger.info(f"Received from {self.user.username}: {text_data}") # Debug
        data = json.loads(text_data)
        if data['action'] == 'move':
            location = data['location']
            player = self.user.username
            character = await self.get_player_character(player)
            from_location = await self.get_player_location(player)
            has_moved = await self.get_player_has_moved(player)

            logger.info(f"From: {from_location}, To: {location}") # Debug

            if not has_moved:
                # First move: Ensure they're moving from their initial location
                if await self.is_move_valid(player, from_location, location):
                    await self.update_player_location(player, location)
                    await self.set_player_has_moved(player, True)
                    await self.channel_layer.group_send(
                        self.game_group_name,
                        {'type': 'game_message', 'character': character, 'from': from_location, 'to': location}
                    )
                else:
                    await self.send(text_data=json.dumps({'error': f'First move must be from your initial location ({from_location}) to an adjacent location.'}))
            else:
                # Subsequent moves
                if await self.is_move_valid(player, from_location, location):
                    await self.update_player_location(player, location)
                    await self.channel_layer.group_send(
                        self.game_group_name,
                        {'type': 'game_message', 'character': character, 'from': from_location, 'to': location}
                    )
                else:
                    await self.send(text_data=json.dumps({'error': f'Move to {location} not allowed'}))

    async def game_message(self, event):
        await self.send(text_data=json.dumps({
            'character': event['character'],
            'from': event['from'],
            'to': event['to']
        }))

    async def player_list_message(self, event):
        await self.send(text_data=json.dumps({
            'player_list': event['player_list']
        }))

    @database_sync_to_async
    def add_player_to_game(self):
        game, _ = Game.objects.get_or_create(game_id=self.game_id)
        Player.objects.get_or_create(user=self.user, game=game)  # Character and location set in view

    @database_sync_to_async
    def get_player_character(self, username):
        return Player.objects.get(user__username=username, game__game_id=self.game_id).character

    @database_sync_to_async
    def get_player_location(self, username):
        return Player.objects.get(user__username=username, game__game_id=self.game_id).location

    @database_sync_to_async
    def get_player_has_moved(self, username):
        return Player.objects.get(user__username=username, game__game_id=self.game_id).has_moved

    @database_sync_to_async
    def update_player_location(self, player, location):
        player_obj = Player.objects.get(user__username=player, game__game_id=self.game_id)
        player_obj.location = location
        player_obj.save()

    @database_sync_to_async
    def set_player_has_moved(self, player, value):
        player_obj = Player.objects.get(user__username=player, game__game_id=self.game_id)
        player_obj.has_moved = value
        player_obj.save()

    @database_sync_to_async
    def get_all_players(self):
        return list(Player.objects.filter(game__game_id=self.game_id).values('id', 'character', 'location', 'has_moved',
                                                                             'user__username'))

    async def broadcast_player_list(self):
        players = await self.get_all_players()
        await self.channel_layer.group_send(
            self.game_group_name,
            {'type': 'player_list_message', 'player_list': players}
        )

    @database_sync_to_async
    def is_move_valid(self, player, from_location, to_location):
        logger.info(f"Validating move from {from_location} to {to_location}")
        valid_moves = {
            'Study': ['Hallway12', 'Hallway14', 'Kitchen'],  # Secret passage
            'Hall': ['Hallway12', 'Hallway23', 'Hallway25'],
            'Lounge': ['Hallway23', 'Hallway36', 'Conservatory'],  # Secret passage
            'Library': ['Hallway14', 'Hallway45', 'Hallway47'],
            'BilliardRoom': ['Hallway25', 'Hallway45', 'Hallway58'],
            'DiningRoom': ['Hallway36', 'Hallway56', 'Hallway69'],
            'Conservatory': ['Hallway47', 'Hallway78', 'Lounge'],  # Secret passage
            'Ballroom': ['Hallway58', 'Hallway78', 'Hallway89'],
            'Kitchen': ['Hallway69', 'Hallway89', 'Study'],  # Secret passage
            'Hallway12': ['Study', 'Hall'],
            'Hallway14': ['Study', 'Library'],
            'Hallway23': ['Hall', 'Lounge'],
            'Hallway25': ['Hall', 'BilliardRoom'],
            'Hallway36': ['Lounge', 'DiningRoom'],
            'Hallway45': ['Library', 'BilliardRoom'],
            'Hallway47': ['Library', 'Conservatory'],
            'Hallway56': ['BilliardRoom', 'DiningRoom'],
            'Hallway58': ['BilliardRoom', 'Ballroom'],
            'Hallway69': ['DiningRoom', 'Kitchen'],
            'Hallway78': ['Conservatory', 'Ballroom'],
            'Hallway89': ['Ballroom', 'Kitchen']
        }
        if from_location not in valid_moves or to_location not in valid_moves[from_location]:
            logger.info(f"Invalid: Not adjacent")
            return False
        if 'Hallway' in to_location and Player.objects.filter(game__game_id=self.game_id,
                                                              location=to_location).exists():
            logger.info(f"Invalid: {to_location} occupied")
            return False
        logger.info("Move is valid")
        return True