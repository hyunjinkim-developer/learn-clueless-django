from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import Game, Player
import json
import logging

logger = logging.getLogger(__name__)  # Logger for debugging and errors

# Define the WebSocket consumer for game interactions
class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.game_id = self.scope['url_route']['kwargs']['game_id']  # Extract game ID from URL
        self.game_group_name = f'game_{self.game_id}'  # Group name for WebSocket broadcasting
        self.user = self.scope['user']  # Current authenticated user
        await self.add_player_to_game()  # Add player to the game
        await self.channel_layer.group_add(self.game_group_name, self.channel_name)  # Join the game group
        await self.accept()  # Accept the WebSocket connection
        await self.broadcast_player_list()  # Send initial player list
        await self.check_and_set_initial_turn()  # Set the first turn if not already set

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.game_group_name, self.channel_name)  # Leave the game group
        await self.broadcast_player_list()  # Update player list on disconnect

    async def receive(self, text_data):
        try:
            logger.info(f"Received from {self.user.username}: {text_data}")  # Log incoming message
            data = json.loads(text_data)  # Parse JSON data into a Python dictionary
            if data['action'] == 'move':  # Handle move action
                location = data['location']  # New location from client
                player = self.user.username  # Current player's username
                character = await self.get_player_character(player)  # Get player's character
                from_location = await self.get_player_location(player)  # Get current location
                has_moved = await self.get_player_has_moved(player)  # Check if player has moved
                logger.info(f"From: {from_location}, To: {location}, Has Moved: {has_moved}")  # Log move details

                if not has_moved:  # First move logic
                    if await self.is_move_valid(player, from_location, location):
                        await self.update_player_location(player, location)  # Update location
                        await self.set_player_has_moved(player, True)  # Mark as moved
                        await self.channel_layer.group_send(
                            self.game_group_name,
                            {'type': 'game_message', 'character': character, 'from': from_location, 'to': location}
                        )  # Broadcast move
                        logger.info("Broadcasting updated player list after first move")  # Log broadcast
                        await self.broadcast_player_list()  # Broadcast updated player list after move
                        await self.next_turn()  # Switch to next player
                    else:
                        await self.send(text_data=json.dumps({'error': f'First move must be from your initial location ({from_location}) to an adjacent location.'}))
                else:  # Subsequent move logic
                    if await self.is_move_valid(player, from_location, location):
                        await self.update_player_location(player, location)  # Update location
                        await self.channel_layer.group_send(
                            self.game_group_name,
                            {'type': 'game_message', 'character': character, 'from': from_location, 'to': location}
                        )  # Broadcast move
                        logger.info("Broadcasting updated player list after subsequent move")  # Log broadcast
                        await self.broadcast_player_list()  # Broadcast updated player list after move
                        await self.next_turn()  # Switch to next player
                    else:
                        await self.send(text_data=json.dumps({'error': f'Move to {location} not allowed'}))
        except Exception as e:
            logger.error(f"Error in receive: {e}")  # Log any errors
            await self.send(text_data=json.dumps({'error': 'An unexpected error occurred. Please try again.'}))

    async def game_message(self, event):
        await self.send(text_data=json.dumps({
            'character': event['character'],  # Character that moved
            'from': event['from'],  # Previous location
            'to': event['to']  # New location
        }))  # Send move update to client

    async def player_list_message(self, event):
        await self.send(text_data=json.dumps({
            'player_list': event['player_list']  # List of all players
        }))  # Send updated player list

    async def turn_message(self, event):
        await self.send(text_data=json.dumps({
            'turn': event['turn']  # Turn notification message
        }))  # Send turn update

    # Sync database operations for async environment
    @database_sync_to_async
    def add_player_to_game(self):
        game, _ = Game.objects.get_or_create(game_id=self.game_id)  # Get or create game
        Player.objects.get_or_create(user=self.user, game=game)  # Get or create player

    @database_sync_to_async
    def get_player_character(self, username):
        return Player.objects.get(user__username=username, game__game_id=self.game_id).character  # Get character's name

    @database_sync_to_async
    def get_player_location(self, username):
        return Player.objects.get(user__username=username, game__game_id=self.game_id).location  # Get current location

    @database_sync_to_async
    def get_player_has_moved(self, username):
        return Player.objects.get(user__username=username, game__game_id=self.game_id).has_moved  # Check if moved

    @database_sync_to_async
    def update_player_location(self, player, location):
        player_obj = Player.objects.get(user__username=player, game__game_id=self.game_id)  # Get player
        player_obj.location = location  # Update location
        player_obj.save()  # Save changes

    @database_sync_to_async
    def set_player_has_moved(self, player, value):
        player_obj = Player.objects.get(user__username=player, game__game_id=self.game_id)  # Get player
        player_obj.has_moved = value  # Update has_moved
        player_obj.save()  # Save changes

    @database_sync_to_async
    def get_all_players(self):
        return list(Player.objects.filter(game__game_id=self.game_id).values('id', 'character', 'location', 'has_moved', 'user__username'))  # Get all players' data

    @database_sync_to_async
    def get_current_turn(self):
        game = Game.objects.get(game_id=self.game_id)  # Get game
        return game.current_player_id if hasattr(game, 'current_player_id') else None  # Get current turn or None

    @database_sync_to_async
    def set_current_turn(self, player_id):
        game = Game.objects.get(game_id=self.game_id)  # Get game
        game.current_player_id = player_id  # Set current player ID
        game.save()  # Save changes

    @database_sync_to_async
    def get_next_player_id(self):
        players = Player.objects.filter(game__game_id=self.game_id).order_by('id')  # Get all players ordered by ID
        if not players.exists():
            return None  # Return None if no players
        current_id = self.get_current_turn()  # Get current turn
        if current_id is None:
            return players.first().id  # Default to first player if no current turn
        for i, player in enumerate(players):
            if player.id == current_id:
                next_index = (i + 1) % len(players)  # Cycle to next player
                return players[next_index].id
        return players.first().id  # Default to first player if current not found

    async def check_and_set_initial_turn(self):
        current_turn = await self.get_current_turn()  # Get current turn
        if current_turn is None:
            players = await self.get_all_players()  # Get all players
            if players:
                await self.set_current_turn(players[0]['id'])  # Set first player as turn
                await self.broadcast_turn()  # Broadcast initial turn

    async def next_turn(self):
        next_player_id = await self.get_next_player_id()  # Get next player ID
        if next_player_id:
            await self.set_current_turn(next_player_id)  # Set new turn
            await self.broadcast_turn()  # Broadcast new turn

    async def broadcast_turn(self):
        current_turn_id = await self.get_current_turn()  # Get current turn ID
        if current_turn_id:
            player = await self.get_player_by_id(current_turn_id)  # Get player details
            await self.channel_layer.group_send(
                self.game_group_name,
                {'type': 'turn_message', 'turn': f"It’s {player['user__username']}'s turn"}  # Send turn message
            )

    async def broadcast_player_list(self):
        players = await self.get_all_players()  # Fetch all players' data
        await self.channel_layer.group_send(
            self.game_group_name,
            {'type': 'player_list_message', 'player_list': players}  # Broadcast player list to all clients
        )  # Send updated player list to all connected clients
    @database_sync_to_async
    def get_player_by_id(self, player_id):
        return Player.objects.filter(id=player_id, game__game_id=self.game_id).values('id', 'character', 'location', 'has_moved', 'user__username').first()  # Get player by ID

    @database_sync_to_async
    def is_move_valid(self, player, from_location, to_location):
        logger.info(f"Validating move from {from_location} to {to_location}")  # Log validation start
        valid_moves = {
            'Study': ['Hallway1', 'Hallway3', 'Kitchen'],
            'Hall': ['Hallway1', 'Hallway2', 'Hallway4'],
            'Lounge': ['Hallway2', 'Hallway5', 'Conservatory'],
            'Library': ['Hallway3', 'Hallway6', 'Hallway8'],
            'BilliardRoom': ['Hallway4', 'Hallway6', 'Hallway7', 'Hallway9'],
            'DiningRoom': ['Hallway5', 'Hallway7', 'Hallway10'],
            'Conservatory': ['Hallway8', 'Hallway11', 'Lounge'],
            'Ballroom': ['Hallway9', 'Hallway11', 'Hallway12'],
            'Kitchen': ['Hallway10', 'Hallway12', 'Study'],
            'Hallway1': ['Study', 'Hall'],
            'Hallway2': ['Hall', 'Lounge'],
            'Hallway3': ['Study', 'Library'],
            'Hallway4': ['Hall', 'BilliardRoom'],
            'Hallway5': ['Lounge', 'DiningRoom'],
            'Hallway6': ['Library', 'BilliardRoom'],
            'Hallway7': ['BilliardRoom', 'DiningRoom'],
            'Hallway8': ['Library', 'Conservatory'],
            'Hallway9': ['BilliardRoom', 'Ballroom'],
            'Hallway10': ['DiningRoom', 'Kitchen'],
            'Hallway11': ['Conservatory', 'Ballroom'],
            'Hallway12': ['Ballroom', 'Kitchen']
        }  # Valid move adjacency map with new hallway names
        if from_location not in valid_moves or to_location not in valid_moves[from_location]:
            logger.info(f"Invalid: Not adjacent")  # Log if move is not adjacent
            return False
        if 'Hallway' in to_location and Player.objects.filter(game__game_id=self.game_id, location=to_location).exists():
            logger.info(f"Invalid: {to_location} occupied")  # Log if hallway is occupied
            return False
        logger.info("Move is valid")  # Log successful validation
        return True