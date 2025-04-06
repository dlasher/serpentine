import pygame
import random
import time
import heapq
import threading  # Import threading
import queue  # Import queue for thread communication

# Constants (same as before)
CELL_SIZE = 20
GRID_WIDTH = 80
GRID_HEIGHT = 60
WINDOW_WIDTH = GRID_WIDTH * CELL_SIZE
WINDOW_HEIGHT = GRID_HEIGHT * CELL_SIZE

# Colors (same as before)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
BLUE = (0, 0, 255)
LIGHT_BLUE = (173, 216, 230)
RED = (255, 0, 0)
ORANGE = (255, 165, 0)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
CYAN = (0, 255, 255)
PINK = (255, 192, 203)

# --- NEW CONSTANT: Minimum enemy length after stuck reduction ---
ENEMY_MIN_LENGTH_AFTER_STUCK = 2
# --- MODIFIED CONSTANT: Player Tail Detection Range (Increased to 25) ---
PLAYER_TAIL_DETECTION_RANGE = 25

# Point class (same as before)
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def __hash__(self): # Need to make Point hashable for dictionary keys in A*
        return hash((self.x, self.y))

    def get_tuple(self): # Helper to get tuple representation
        return (self.x, self.y)

    def __lt__(self, other): # Implement less than for heapq comparison
        if self.y != other.y:
            return self.y < other.y
        return self.x < other.x


# Egg class (same as before)
class Egg:
    def __init__(self, point, time_laid, egg_type):
        self.point = point
        self.time_laid = time_laid
        self.egg_type = egg_type

    def get_point(self):
        return self.point

    def get_type(self):
        return self.egg_type


# Snake class (modified to have a target and track stuck status and communication queue)
class Snake:
    def __init__(self, body, color, head_color):
        self.body = body
        self.color = color
        self.head_color = head_color
        self.original_color = color
        self.is_green = False
        self.last_move_time = 0
        self.move_interval = 0.1 # Default move interval
        self.target = None  # Current target for the snake (Point or None)
        self.target_type = None # Type of target ("food" or "egg" or "tail")
        self.last_head_position = body[0] # Initialize with initial head position
        self.last_head_move_time = time.time() # Initialize with current time
        self.stuck_clear_target = False # Flag to indicate target should be cleared due to stuck
        self.path_queue = queue.Queue() # Queue for pathfinding results from thread


# Game class (modified for threading, target persistence, food consumption fix, and stuck enemy detection)
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Serpentine")
        self.clock = pygame.time.Clock()

        # Initialize player snake - now starts in the middle (MODIFIED)
        self.player = Snake(
            [Point(GRID_WIDTH // 2, GRID_HEIGHT // 2), # Vertically centered
             Point(GRID_WIDTH // 2 - 1, GRID_HEIGHT // 2),
             Point(GRID_WIDTH // 2 - 2, GRID_HEIGHT // 2)],
            BLUE, LIGHT_BLUE
        )
        self.direction = (1, 0)

        # Initialize enemy snakes (same as before)
        self.enemies = [
            Snake([Point(GRID_WIDTH // 4, GRID_HEIGHT // 4),
                   Point(GRID_WIDTH // 4 + 1, GRID_WIDTH // 4),
                   Point(GRID_WIDTH // 4 + 2, GRID_WIDTH // 4)], RED, ORANGE),
            Snake([Point(3 * GRID_WIDTH // 4, 3 * GRID_HEIGHT // 4),
                   Point(3 * GRID_WIDTH // 4 - 1, GRID_HEIGHT // 4),
                   Point(3 * GRID_WIDTH // 4 - 2, GRID_HEIGHT // 4)], RED, ORANGE),
        ]

        self.food = None
        self.player_eggs = []
        self.enemy_eggs = []
        self.score = 0
        self.game_start_time = time.time()
        self.last_player_egg_time = self.game_start_time
        self.last_enemy_egg_time = self.game_start_time
        self.last_food_time = self.game_start_time
        self.game_over = False
        self.end_message = ""
        self.frame_time = 0.1
        self.last_update = time.time()
        self.grew = False
        self.game_end_time = 0
        self.last_timer_seconds = 0


    def find_path(self, start_point, end_point, exclude_snake_body=None, target_type_to_ignore=None): # Modified: added target_type_to_ignore
        """A* pathfinding algorithm."""
        start_node = start_point
        goal_node = end_point

        open_set = [(0, start_node)]  # Priority queue: (f_score, node)
        came_from = {}
        g_score = {start_node: 0}
        f_score = {start_node: self.heuristic(start_node, goal_node)}

        while open_set:
            current_f_score, current_node = heapq.heappop(open_set)

            if current_node == goal_node:
                return self.reconstruct_path(came_from, current_node, start_point)

            if current_f_score > f_score[current_node]: # Optimization to skip outdated entries in priority queue
                continue

            for neighbor in self.get_neighbors(current_node, exclude_snake_body, target_type_to_ignore): # Modified: Pass target_type_to_ignore
                tentative_g_score = g_score[current_node] + 1 # Cost of 1 to move to a neighbor

                if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                    came_from[neighbor] = current_node
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = tentative_g_score + self.heuristic(neighbor, goal_node)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))

        return None  # No path found


    def reconstruct_path(self, came_from, current_node, start_point):
        """Reconstructs the path found by A*."""
        path = [current_node]
        while current_node != start_point:
            current_node = came_from[current_node]
            path.append(current_node)
        path.reverse()  # Reverse to get path from start to end
        return path

    def heuristic(self, a, b):
        """Manhattan distance heuristic."""
        return abs(a.x - b.x) + abs(a.y - b.y)


    def get_neighbors(self, point, snake_to_ignore=None, target_type_to_ignore=None): # Modified: Pass target_type_to_ignore
        """Returns valid neighbors for a given point, considering obstacles."""
        neighbors = []
        possible_moves = [(0, -1), (0, 1), (-1, 0), (1, 0)] # Up, Down, Left, Right
        grid_width_range = range(GRID_WIDTH) # Pre-calculate ranges for boundary checks
        grid_height_range = range(GRID_HEIGHT)

        for dx, dy in possible_moves:
            neighbor_x = point.x + dx
            neighbor_y = point.y + dy
            neighbor_point = Point(neighbor_x, neighbor_y)

            if neighbor_x in grid_width_range and neighbor_y in grid_height_range: # Efficient boundary check
                if not self.is_obstacle(neighbor_point, snake_to_ignore, target_type_to_ignore):
                    neighbors.append(neighbor_point)
        return neighbors


    def is_obstacle(self, point, snake_to_ignore=None, target_type_to_ignore=None): # Modified: Added target_type_to_ignore
        """Checks if a point is an obstacle (snake body, egg, etc.)."""
        if point in self.player.body:
            return True
        for enemy in self.enemies:
            if enemy != snake_to_ignore: # Check if enemy is NOT the snake to ignore
                if point in enemy.body:
                    return True
            elif enemy == snake_to_ignore: # If it IS the snake to ignore, handle self-body check
                # Allow head to move into the cell occupied by the current tail
                if len(enemy.body) > 1 and point in enemy.body[:-1]: # Exclude the tail segment for self-check
                    return True

        for egg_obj in self.player_eggs + self.enemy_eggs:
            if point == egg_obj.get_point():
                if target_type_to_ignore == "egg": # Modified: Ignore egg obstacle if target_type_to_ignore is "egg"
                    return False # Treat egg as NOT an obstacle when targeting eggs
                return True # Treat eggs as obstacles by default

        return False # Not an obstacle

    def pathfinding_thread(self, enemy_index, game_state): # Pass game_state instead of self
        """Pathfinding logic to be run in a separate thread for each enemy."""
        enemy = game_state.enemies[enemy_index] # Access enemy from game_state
        e_head = enemy.body[0]
        target_food = None
        target_player_egg = None
        target_player_tail = None # NEW: Target Player Tail
        target_point = None

        # Determine detection range based on enemy count (same as in update())
        detection_range = GRID_WIDTH + GRID_HEIGHT  # Default full range
        if len(game_state.enemies) > 1: # Access enemies from game_state
            detection_range = (GRID_WIDTH + GRID_HEIGHT) * 0.5  # 50% reduced range

        # Check if enemy needs target cleared due to being stuck (same as in update())
        if enemy.stuck_clear_target:
            enemy.stuck_clear_target = False
            enemy.target = None

        # Check if enemy already has a target (same as in update())
        if enemy.target:
            target_point = enemy.target

            if enemy.target_type == "food" and (game_state.food is None or game_state.food != enemy.target): # Access food from game_state
                enemy.target = None
                target_point = None
            elif enemy.target_type == "egg":
                egg_exists = False
                for egg_obj in game_state.player_eggs: # Access player_eggs from game_state
                    if egg_obj.get_point() == enemy.target:
                        egg_exists = True
                        break
                if not egg_exists:
                    enemy.target = None
                    target_point = None
            elif enemy.target_type == "tail": # NEW: Check for tail target validity
                if len(game_state.player.body) <= 1 or game_state.player.body[-1] != enemy.target: # Player tail no longer valid
                    enemy.target = None
                    target_point = None


        # --- NEW: Closest Target Logic ---
        closest_target_point = None
        min_target_distance = float('inf')
        chosen_target_type = None

        # Check for closest egg
        for egg_obj in game_state.player_eggs: # Access player_eggs from game_state
            egg = egg_obj.get_point()
            dist_x_to_egg = abs(e_head.x - egg.x)
            dist_y_to_egg = abs(e_head.y - egg.y)
            distance_to_egg = dist_x_to_egg + dist_y_to_egg

            if distance_to_egg <= detection_range:
                if distance_to_egg < min_target_distance:
                    min_target_distance = distance_to_egg
                    closest_target_point = egg
                    chosen_target_type = "egg"

        # Check for closest food (if no egg closer or no eggs found)
        if game_state.food: # Access food from game_state
            dist_x_to_food = abs(e_head.x - game_state.food.x) # Access food from game_state
            dist_y_to_food = abs(e_head.y - game_state.food.y) # Access food from game_state
            distance_to_food = dist_x_to_food + dist_y_to_food

            if distance_to_food <= detection_range:
                if distance_to_food < min_target_distance: # Closer than current closest
                    min_target_distance = distance_to_food
                    closest_target_point = game_state.food # Access food from game_state
                    chosen_target_type = "food"

        # Check for player tail (if no egg or food closer or none found)
        if len(game_state.player.body) > 1: # Player needs to have a tail
            player_tail = game_state.player.body[-1] # Get player tail
            dist_x_to_tail = abs(e_head.x - player_tail.x)
            dist_y_to_tail = abs(e_head.y - player_tail.y)
            distance_to_tail = dist_x_to_tail + dist_y_to_tail

            if distance_to_tail <= PLAYER_TAIL_DETECTION_RANGE: # Tail detection range
                if distance_to_tail < min_target_distance: # Closer than current closest
                    closest_target_point = player_tail
                    chosen_target_type = "tail"


        if closest_target_point: # Set the closest target
            target_point = closest_target_point
            enemy.target = closest_target_point
            enemy.target_type = chosen_target_type
        else: # No target found in range
            enemy.target = None
            enemy.target_type = None
        # --- END NEW: Closest Target Logic ---


        next_move_point = None
        if target_point: # Pathfind to target (either egg or food or tail)
            target_type_ignore = "egg" if enemy.target_type == "egg" else None
            path = self.find_path(e_head, target_point, exclude_snake_body=enemy, target_type_to_ignore=target_type_ignore) # Use self.find_path
            if path and len(path) > 1:
                next_move_point = path[1]

        enemy.path_queue.put(next_move_point) # Put result in the enemy's queue


    def update(self):
        if self.game_over:
            return

        current_time = time.time()
        if current_time - self.last_update < self.frame_time:
            return
        self.last_update = current_time

        # Handle player input (same as before, plus new key checks)
        keys = pygame.key.get_pressed()
        new_direction = self.direction
        if keys[pygame.K_UP] and self.direction != (0, 1):
            new_direction = (0, -1)
        elif keys[pygame.K_DOWN] and self.direction != (0, -1):
            new_direction = (0, 1)
        elif keys[pygame.K_LEFT] and self.direction != (1, 0):
            new_direction = (-1, 0)
        elif keys[pygame.K_RIGHT] and self.direction != (-1, 0):
            new_direction = (1, 0)

        # --- NEW: Enemy snake length modification ---
        if keys[pygame.K_o]: # Increase enemy length
            for enemy in self.enemies:
                enemy.body.extend([enemy.body[-1]] * 5) # Add 5 segments to each enemy
            time.sleep(0.1) # Small delay to prevent continuous triggering

        if keys[pygame.K_i]: # Decrease enemy length
            for enemy in self.enemies:
                if len(enemy.body) > 2: # Ensure enemy length is at least 2 after decrease
                    enemy.body = enemy.body[:-1] # Remove 1 tail segment from each enemy
            time.sleep(0.1) # Small delay
        # --- END NEW ---


        # Move player snake (same as before)
        head = self.player.body[0]
        new_head = Point(head.x + new_direction[0], head.y + new_direction[1]) # Corrected: Use head.y


        # Wall collision: Stop game if out of bounds, otherwise conditionally change direction (MODIFIED)
        if (new_head.x < 0 or new_head.x >= GRID_WIDTH or
                new_head.y < 0 or new_head.y >= GRID_HEIGHT):
            if new_direction != self.direction: # Attempting to turn at the wall
                # Check if the *intended* turn would *still* be out of bounds in the next step
                test_head = self.player.body[0]
                test_new_head = Point(test_head.x + new_direction[0], test_head.y + new_direction[1])
                if not (test_new_head.x < 0 or test_new_head.x >= GRID_WIDTH or
                        test_new_head.y < 0 or test_new_head.y >= GRID_HEIGHT): # New direction is valid (not immediately out of bounds)
                    self.direction = new_direction # Allow the direction change
                else:
                    return # Prevent move and direction change - stay in old direction at wall edge.
            else:
                return # Still moving in the same direction into the wall, so stop.


        # Self-collision check (same as before)
        if new_head in self.player.body[:-1]:
            self.game_over = True
            self.end_message = f"Game Over! Score: {self.score}"
            self.game_end_time = time.time()
            return

        self.player.body.insert(0, new_head)
        self.direction = new_direction
        self.grew = False


        # --- THREADED ENEMY MOVEMENT (Corrected) ---
        threads = [] # List to keep track of enemy threads
        active_enemies_indices = [] # Keep track of indices of enemies for whom threads were started

        for i, enemy in enumerate(self.enemies[:]): # Enumerate enemies
            enemy_current_time = time.time()
            if enemy_current_time - enemy.last_move_time < enemy.move_interval:
                continue # Skip move if not enough time passed for this enemy

            enemy.last_move_time = enemy_current_time
            active_enemies_indices.append(i) # Record the index of the active enemy
            # Start a new thread for pathfinding for this enemy
            thread = threading.Thread(target=self.pathfinding_thread, args=(i, self)) # Pass original index 'i'
            threads.append(thread)
            thread.start()

        # Wait for threads and process results, using recorded indices
        for thread_index, enemy_original_index in enumerate(active_enemies_indices): # Iterate through recorded indices
            threads[thread_index].join() # Join thread based on thread_index
            enemy = self.enemies[enemy_original_index] # Get the correct enemy using original index
            next_move_point = enemy.path_queue.get() # Get result from queue

            e_head = enemy.body[0]
            enemy_grew = False
            new_e_head = None # Initialize new_e_head

            if next_move_point: # Move based on pathfinding result
                new_e_head = next_move_point
            else: # Fallback to original random movement (if no path) - same as before
                possible_moves = [(0, -1), (0, 1), (-1, 0), (1, 0)]
                valid_moves = []
                for move in possible_moves:
                    dx, dy = move
                    new_e_head_temp = Point(
                        max(0, min(GRID_WIDTH - 1, e_head.x + dx)),
                        max(0, min(GRID_HEIGHT - 1, e_head.y + dy))
                    )
                    collision = False
                    for other_enemy_index, other_enemy in enumerate(self.enemies):
                        if enemy_original_index != other_enemy_index and new_e_head_temp in other_enemy.body: # Use original index for comparison
                            collision = True
                            break
                    if not collision:
                        valid_moves.append(move)

                if valid_moves:
                    dx, dy = random.choice(valid_moves)
                else: # No valid moves
                    moves = [(0, -1), (0, 1), (-1, 0)]
                    dx, dy = random.choice(moves)
                new_e_head = Point(
                    max(0, min(GRID_WIDTH - 1, e_head.x + dx)),
                    max(0, min(GRID_HEIGHT - 1, e_head.y + dy))
                )

            # Stuck enemy detection: Check if head position changed (same as before)
            current_time = time.time() # Get current time for stuck detection
            if new_e_head == enemy.last_head_position:
                if current_time - enemy.last_head_move_time >= 3: # 3 seconds stuck
                    enemy.stuck_clear_target = True # Set flag to clear target next cycle
                    enemy.target = None # Clear target to unstuck enemy
                    enemy.target_type = None # Clear target type as well

                    # --- NEW: Reduce enemy snake length if stuck ---
                    if len(enemy.body) > ENEMY_MIN_LENGTH_AFTER_STUCK:
                        enemy.body.pop() # Remove tail segment
                        print(f"ENEMY SNAKE {enemy_original_index+1} IS STUCK AND LENGTH REDUCED! Target was: {enemy.target}, New Length: {len(enemy.body)}") # DEBUG PRINT - ENEMY STUCK & LENGTH REDUCED
                    else:
                        print(f"ENEMY SNAKE {enemy_original_index+1} IS STUCK (Min Length Reached)! Target was: {enemy.target}") # DEBUG PRINT - ENEMY STUCK - MIN LENGTH
                    # --- END NEW ---
            else: # Head position changed
                enemy.last_head_position = e_head # Update last head position
                enemy.last_head_move_time = current_time # Update last move time


            if new_e_head not in enemy.body:
                enemy.body.insert(0, new_e_head)
                # Consumption checks: (same as before)
                if enemy.target_type == "food": # Food Consumption Check
                    if enemy.target and new_e_head == enemy.target:
                        enemy.body.append(enemy.body[-1])
                        self.food = None
                        enemy_grew = True
                        enemy.target = None
                        enemy.target_type = None
                elif enemy.target_type == "egg": # Egg Consumption Check (using elif now)
                    if enemy.target and new_e_head == enemy.target:
                        enemy.body.extend([enemy.body[-1]] * 2)
                        enemy_grew = True
                        egg_removed = False # Flag to track if an egg was removed
                        for egg_obj_to_remove in list(self.player_eggs): # Iterate through a copy to allow removal
                            egg_point = egg_obj_to_remove.get_point()
                            if egg_point:
                                if egg_obj_to_remove.get_point() == enemy.target: # Compare with enemy.target directly - PROBLEM LINE
                                    self.player_eggs.remove(egg_obj_to_remove)
                                    egg_removed = True
                                    break # Exit loop after removing the egg
                        enemy.target = None # Reset target *AFTER* the loop (Corrected position)
                        enemy.target_type = None # Reset target_type *AFTER* the loop (Corrected position)
                elif enemy.target_type == "tail": # NEW: Tail Consumption Check (no growth for now)
                    if enemy.target and new_e_head == enemy.target:
                        enemy.target = None # Invalidate target after reaching it (for now, no consumption effect)
                        enemy.target_type = None

                if not enemy_grew:
                    enemy.body.pop()

            # --- NEW: Vary Enemy Speed based on Target ---
            if enemy.color == RED: # Only for RED enemies as per request
                if enemy.target_type == "tail":
                    enemy.move_interval = 0.025
                elif enemy.target_type == "food":
                    enemy.move_interval = 0.1
                elif enemy.target_type == "egg":
                    enemy.move_interval = 0.025
                else: # No specific target type, revert to default interval for Red snake
                    enemy.move_interval = 0.1 # Or whatever default you prefer for red snakes
            else: # For non-RED enemies, keep default interval or other logic
                enemy.move_interval = 0.1 # Or their default if you have other speed logic

            # Update enemy snake green status and speed (Green status speed logic remains unchanged)
            if len(enemy.body) <= 2:
                if not enemy.is_green:
                    enemy.color = GREEN
                    enemy.head_color = GREEN
                    enemy.is_green = True
                    enemy.move_interval = 0.2
            elif enemy.is_green:
                enemy.color = enemy.original_color
                enemy.head_color = ORANGE
                enemy.is_green = False
                enemy.move_interval = 0.1
        # --- END THREADED ENEMY MOVEMENT (Corrected) ---


        # Spawn food (same as before - no changes needed for pathfinding)
        if not self.food and current_time - self.last_food_time > 5:
            while True:
                food = Point(random.randint(0, GRID_WIDTH - 1), random.randint(0, GRID_HEIGHT - 1))
                valid_food_pos = True
                if food in self.player.body: valid_food_pos = False
                for e in self.enemies:
                    if food in e.body: valid_food_pos = False
                for egg_obj in self.player_eggs + self.enemy_eggs:
                    if food == egg_obj.get_point(): valid_food_pos = False
                if valid_food_pos:
                    self.food = food
                    self.last_food_time = current_time
                    break

        # Enemy egg laying (modified to reduce chance with more enemies)
        enemy_egg_interval = 30 # Default interval
        enemy_egg_laying_probability = 1.0 # Default probability (100%)
        if len(self.enemies) == 1:
            enemy_egg_interval = 10 # 10 seconds when only one enemy left
        elif len(self.enemies) >= 2:
            enemy_egg_laying_probability = 0.5 # 50% chance with 2+ enemies

        if current_time - self.last_enemy_egg_time > enemy_egg_interval:
            for enemy in self.enemies:
                if random.random() < enemy_egg_laying_probability and len(enemy.body) >= 3: # Use probability here
                    if len(enemy.body) > 3: # Ensure snake remains at least length 3
                        self.enemy_eggs.append(Egg(enemy.body[-1], current_time, "enemy"))
                        enemy.body.pop() # Only pop tail if length > 3
                    elif len(enemy.body) == 3: # If length is 3, just lay egg without shrinking
                        self.enemy_eggs.append(Egg(enemy.body[-1], current_time, "enemy"))
                        pass # Do not shrink the snake, just lay the egg
            self.last_enemy_egg_time = current_time


        # Player egg laying (same as before - no changes needed for pathfinding)
        if current_time - self.last_player_egg_time > 10:
            if random.random() < 0.5 and len(self.player.body) >= 3:
                self.player_eggs.append(Egg(self.player.body[-1], current_time, "player"))
                self.player.body.pop()
            self.last_player_egg_time = current_time

        # Collision with food (same as before - no changes needed for pathfinding)
        if self.food and self.player.body[0] == self.food:
            self.grew = True
            self.food = None
            self.score += 10

        # Collision with eggs and enemies (MODIFIED to allow enemy consume player)
        enemies_to_remove = []
        enemy_eggs_to_remove = []

        # Collision with Enemy Eggs (same as before - no changes needed for pathfinding)
        for egg_obj in self.enemy_eggs:
            egg_point = egg_obj.get_point()
            if self.player.body[0] == egg_point:
                self.grew = True
                enemy_eggs_to_remove.append(egg_obj)
                self.score += 50
                break

        # Collision with Enemies (MODIFIED to allow enemy consume player body)
        for i, enemy in enumerate(self.enemies):
            if self.player.body[0] == enemy.body[0]: # Player head to enemy head collision
                if enemy.color == GREEN: # Green enemy loses
                    enemies_to_remove.append(i)
                    self.grew = True
                    self.score += 50
                else: # Non-green enemy wins - game over for player
                    self.game_over = True
                    self.end_message = f"Game Over! Score: {self.score}"
                    self.game_end_time = time.time()
                    return
            elif self.player.body[0] in enemy.body[1:]: # Player head to enemy body
                original_enemy_length = len(enemy.body)
                pos = enemy.body.index(self.player.body[0])
                enemy.body = enemy.body[:pos]
                removed_length = original_enemy_length - len(enemy.body)
                self.player.body.extend([self.player.body[-1]] * removed_length)
                self.grew = True
                if len(enemy.body) <= 2:
                    enemy.color = GREEN
                    enemy.head_color = GREEN
                    enemy.is_green = True
                    enemy.move_interval = 0.2
            # --- NEW: Enemy head to player body collision ---
            elif enemy.body[0] in self.player.body: # Enemy head to player body collision
                if self.player.body.index(enemy.body[0]) != 0: # ...but not if enemy head hits player head (already handled above)
                    original_player_length = len(self.player.body)
                    pos = self.player.body.index(enemy.body[0])
                    self.player.body = self.player.body[:pos] # Player loses body segments
                    removed_length = original_player_length - len(self.player.body)
                    enemy.body.extend([enemy.body[-1]] * removed_length) # Enemy grows
                    if len(self.player.body) <= 2: # Check if player is now too short - game over
                        self.game_over = True # Player snake too short
                        self.end_message = f"Game Over! Score: {self.score} - Eaten by Enemy!"
                        self.game_end_time = time.time()
                        return


        # Remove eaten enemy eggs (same as before - no changes needed for pathfinding)
        for egg_obj in enemy_eggs_to_remove:
            self.enemy_eggs.remove(egg_obj)
            self.grew = True

        for i in sorted(enemies_to_remove, reverse=True):
            self.enemies.pop(i)

        # Hatch eggs (same as before - no changes needed for pathfinding)
        player_eggs_to_hatch = []
        for egg_obj in self.player_eggs:
            if current_time - egg_obj.time_laid >= 10:
                player_eggs_to_hatch.append(egg_obj)
        for egg_obj in player_eggs_to_hatch:
            self.player_eggs.remove(egg_obj)
            self.score += 100

        enemy_eggs_to_hatch = []
        for egg_obj in self.enemy_eggs:
            if current_time - egg_obj.time_laid >= 10:
                enemy_eggs_to_hatch.append(egg_obj)
        for egg_obj in enemy_eggs_to_hatch:
            self.enemy_eggs.remove(egg_obj)
            pos = egg_obj.get_point()
            new_enemy = Snake([pos,
                                            Point(max(0, min(GRID_WIDTH - 1, pos.x - 1)), pos.y),
                                            Point(max(0, min(GRID_WIDTH - 1, pos.x - 2)), pos.y)], RED, ORANGE)
            self.enemies.append(new_enemy)


        # Remove tail if no growth (same as before - no changes needed for pathfinding)
        if not self.grew:
            self.player.body.pop()

        # Win condition (same as before - no changes needed for pathfinding)
        if not self.enemies:
            self.game_over = True
            self.end_message = f"You've Won! Score: {self.score}"
            self.game_end_time = time.time()


    def draw(self):
        # Draw function (same as before - no changes needed for pathfinding)
        self.screen.fill(BLACK)
        pygame.draw.rect(self.screen, WHITE, (0, 0, WINDOW_WIDTH, WINDOW_HEIGHT), 2)

        for i, seg in enumerate(self.player.body):
            color = self.player.head_color if i == 0 else self.player.color
            pygame.draw.rect(self.screen, color, (seg.x * CELL_SIZE, seg.y * CELL_SIZE, CELL_SIZE, CELL_SIZE))

        for enemy in self.enemies:
            for i, seg in enumerate(enemy.body):
                color = enemy.head_color if i == 0 else enemy.color
                pygame.draw.rect(self.screen, color, (seg.x * CELL_SIZE, seg.y * CELL_SIZE, CELL_SIZE, CELL_SIZE))

        if self.food:
            pygame.draw.rect(self.screen, YELLOW, (self.food.x * CELL_SIZE, self.food.y * CELL_SIZE, CELL_SIZE, CELL_SIZE))

        for egg_obj in self.player_eggs:
            egg = egg_obj.get_point()
            pygame.draw.circle(self.screen, CYAN, (int(egg.x * CELL_SIZE + CELL_SIZE / 2), int(egg.y * CELL_SIZE + CELL_SIZE / 2)), int(CELL_SIZE / 2))
        for egg_obj in self.enemy_eggs:
            egg = egg_obj.get_point()
            pygame.draw.circle(self.screen, PINK, (int(egg.x * CELL_SIZE + CELL_SIZE / 2), int(egg.y * CELL_SIZE + CELL_SIZE / 2)), int(CELL_SIZE / 2))


        font = pygame.font.SysFont(None, 30)
        score_text = font.render(f"Score: {self.score}", True, WHITE)
        player_length_text = font.render(f"Length: {len(self.player.body)}", True, WHITE) # Render player length


        y_offset = 70 # Start y position for enemy target info
        for i, enemy in enumerate(self.enemies):
            if enemy.target: # Only display target if enemy has one
                target_type_str = f" ({enemy.target_type})" if enemy.target_type else "" # Add target type if available
                # --- MODIFIED LINE: Include enemy length in the target text ---
                target_text = font.render(f"Enemy {i+1} Target: {enemy.target.get_tuple()}{target_type_str}, Len: {len(enemy.body)}", True, WHITE)
                self.screen.blit(target_text, (10, y_offset))
                y_offset += 20 # Move y_offset down for next enemy's target


        if not self.game_over:
            elapsed_seconds = int(time.time() - self.game_start_time)
            minutes = elapsed_seconds // 60
            seconds = elapsed_seconds % 60
            timer_string = f"Time: {minutes:02}:{seconds:02}"
            self.last_timer_seconds = seconds
            timer_text = font.render(timer_string, True, WHITE)
            self.screen.blit(timer_text, (10, 30))
        else:
            game_over_text = font.render(self.end_message, True, WHITE)
            text_rect = game_over_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
            self.screen.blit(game_over_text, text_rect)
            time_elapsed = time.time() - self.game_end_time
            if time_elapsed < 3:
                score_text = font.render(f"{self.end_message}", True, YELLOW)
            else:
                score_text = font.render(f"{self.end_message}", True, WHITE)


        self.screen.blit(player_length_text, (10, 50))
        self.screen.blit(score_text, (10, 10))
        pygame.display.flip()


    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    break
                if event.type == pygame.KEYDOWN:
                    if self.game_over:
                        return False

            self.update()
            self.draw()
            # --- MODIFIED clock tick to 60 ---
            self.clock.tick(60) # Limit frame rate to 60 FPS
        pygame.quit()
        return True


def main():
    game = Game()
    if not game.run():
        print ("bye bye")

if __name__ == '__main__':
    main()
