import pygame
import random
import time

# Constants
CELL_SIZE = 20
GRID_WIDTH = 80
GRID_HEIGHT = 60
WINDOW_WIDTH = GRID_WIDTH * CELL_SIZE
WINDOW_HEIGHT = GRID_HEIGHT * CELL_SIZE

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
BLUE = (0, 0, 255)
LIGHT_BLUE = (173, 216, 230)  # Head color for player snake
RED = (255, 0, 0)
ORANGE = (255, 165, 0)      # Head color for enemy snakes
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
CYAN = (0, 255, 255)       # Player egg color
PINK = (255, 192, 203)       # Enemy egg color


# Point class to represent coordinates
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

# Egg class to represent eggs with position and time laid
class Egg:
    def __init__(self, point, time_laid, egg_type): # Added egg_type
        self.point = point
        self.time_laid = time_laid
        self.egg_type = egg_type # "player" or "enemy"

    def get_point(self):
        return self.point

    def get_type(self): # Added get_type method
        return self.egg_type


# Snake class to manage snake properties
class Snake:
    def __init__(self, body, color, head_color):
        self.body = body  # List of Point objects
        self.color = color
        self.head_color = head_color
        self.original_color = color
        self.is_green = False # Track if currently green
        self.last_move_time = 0 # For speed control
        self.move_interval = 0.1 # Normal speed move interval
        self.last_head_position = None # Track last head position for stuck detection
        self.stuck_timer_start_time = 0 # Timer to track stuck time

# Game class to manage the game state and logic
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Serpentine")
        self.clock = pygame.time.Clock()

        # Initialize player snake
        self.player = Snake(
            [Point(GRID_WIDTH // 2, GRID_HEIGHT // 2),
             Point(GRID_WIDTH // 2 - 1, GRID_HEIGHT // 2),
             Point(GRID_WIDTH // 2 - 2, GRID_HEIGHT // 2)],
            BLUE, LIGHT_BLUE
        )
        self.direction = (1, 0)  # Start moving right

        # Initialize enemy snakes
        self.enemies = [
            Snake([Point(GRID_WIDTH // 4, GRID_HEIGHT // 4),
                   Point(GRID_WIDTH // 4 + 1, GRID_HEIGHT // 4),
                   Point(GRID_WIDTH // 4 + 2, GRID_HEIGHT // 4)], RED, ORANGE),
            Snake([Point(3 * GRID_WIDTH // 4, 3 * GRID_HEIGHT // 4),
                   Point(3 * GRID_WIDTH // 4 - 1, GRID_HEIGHT // 4),
                   Point(3 * GRID_WIDTH // 4 - 2, GRID_HEIGHT // 4)], RED, ORANGE),
        ]

        self.food = None
        self.player_eggs = [] # list of Egg objects
        self.enemy_eggs = [] # list of Egg objects
        self.score = 0
        self.game_start_time = time.time() # Initialize game start time
        self.last_player_egg_time = self.game_start_time
        self.last_enemy_egg_time = self.game_start_time
        self.last_food_time = self.game_start_time
        self.game_over = False
        self.end_message = ""  # To hold "Game Over" or "You've Won" message
        self.frame_time = 0.1  # Update every 0.1 seconds
        self.last_update = time.time()
        self.grew = False  # Track if player snake grew this frame
        self.game_end_time = 0 # To store the time when game ended
        self.last_timer_seconds = 0 # Store last timer value to freeze display


    def update(self):
        if self.game_over:
            return

        current_time = time.time()
        if current_time - self.last_update < self.frame_time:
            return
        self.last_update = current_time

        # Handle player input
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

        # Move player snake
        head = self.player.body[0]
        new_head = Point(head.x + new_direction[0], head.y + new_direction[1])

        # Wall collision: stop and wait for direction change
        if (new_head.x < 0 or new_head.x >= GRID_WIDTH or
                new_head.y < 0 or new_head.y >= GRID_HEIGHT):
            if new_direction == self.direction:
                return
            else:
                self.direction = new_direction
                return

        # Self-collision check
        if new_head in self.player.body[:-1]:
            self.game_over = True
            self.end_message = f"Game Over! Score: {self.score}"
            self.game_end_time = time.time() # Record game over time
            return

        self.player.body.insert(0, new_head)
        self.direction = new_direction
        self.grew = False

        # Move enemy snakes
        for i, enemy in enumerate(self.enemies[:]):  # Copy list to modify during iteration
            enemy_current_time = time.time()
            if enemy_current_time - enemy.last_move_time < enemy.move_interval:
                continue # Skip move if not enough time passed for this enemy
            enemy.last_move_time = enemy_current_time

            e_head = enemy.body[0]
            previous_head_position = e_head # Store head position before move attempt
            target_food = self.food
            target_player_egg = None # Initialize target player egg
            target_player_tail = None # Initialize target player tail
            enemy_grew = False

            # Detection range calculation based on enemy length - Increased radius for short snakes
            if len(enemy.body) <= 2:
                detection_range_x = GRID_WIDTH  # Increased X range
                detection_range_y = GRID_HEIGHT # Increased Y range
            else: # len(enemy.body) >= 3
                detection_range_x = GRID_WIDTH // 2
                detection_range_y = GRID_HEIGHT // 2


            # Detect player tail first, within range 5 (highest priority)
            player_tail = self.player.body[-1]
            dist_x_to_tail = abs(e_head.x - player_tail.x)
            dist_y_to_tail = abs(e_head.y - player_tail.y)
            if dist_x_to_tail <= 5 and dist_y_to_tail <= 5:
                target_player_tail = player_tail # Target player tail if in range


            # Detect player eggs next, if no tail is targeted (medium priority)
            if not target_player_tail: # Only check for eggs if tail is not targeted
                for egg_obj in self.player_eggs:
                    egg = egg_obj.get_point()
                    dist_x_to_egg = abs(e_head.x - egg.x)
                    dist_y_to_egg = abs(e_head.y - egg.y)
                    if dist_x_to_egg <= detection_range_x and dist_y_to_egg <= detection_range_y:
                        target_player_egg = egg # Target the first player egg found within range
                        break # Prioritize egg, so break after finding one

            # If no player egg or tail is targeted, then check for food (lowest priority)
            if not target_player_tail and not target_player_egg and target_food:
                dist_x_to_food = abs(e_head.x - target_food.x)
                dist_y_to_food = abs(e_head.y - target_food.y)
                if dist_x_to_food <= detection_range_x and dist_y_to_food <= detection_range_y:
                    target_food = self.food # keep targetting food if in range

            possible_moves = [(0, -1), (0, 1), (-1, 0), (1, 0)]
            valid_moves = []

            for move in possible_moves:
                dx, dy = move
                new_e_head_temp = Point( # Use temp Point for validation to not affect actual new_e_head yet
                    max(0, min(GRID_WIDTH - 1, e_head.x + dx)),
                    max(0, min(GRID_HEIGHT - 1, e_head.y + dy))
                )
                collision = False
                for other_enemy_index, other_enemy in enumerate(self.enemies):
                    if i != other_enemy_index and new_e_head_temp in other_enemy.body: # Check collision with other enemies
                        collision = True
                        break
                if not collision:
                    valid_moves.append(move)

            if not valid_moves: # No valid moves, choose randomly from all (potentially colliding)
                moves_to_use = possible_moves
            else:
                moves_to_use = valid_moves

            dx = 0
            dy = 0 # Initialize move direction to no move (in case no target and no valid moves)

            if target_player_tail: # Move towards player tail if detected (highest priority)
                if e_head.x < target_player_tail.x:
                    dx = 1
                elif e_head.x > target_player_tail.x:
                    dx = -1
                if e_head.y < target_player_tail.y:
                    dy = 1
                elif e_head.y > target_player_tail.y:
                    dy = -1
                move_towards_tail = (dx, dy)
                if move_towards_tail in moves_to_use: # Prioritize valid move towards tail
                    dx, dy = move_towards_tail
                elif moves_to_use: # If direct move invalid, use any valid move
                    dx, dy = random.choice(moves_to_use)
                elif possible_moves: # No valid moves at all, use a potentially colliding move if possible
                    dx, dy = move_towards_tail if move_towards_tail in possible_moves else random.choice(possible_moves)


            elif target_player_egg: # Move towards player egg if detected (medium priority)
                if e_head.x < target_player_egg.x:
                    dx = 1
                elif e_head.x > target_player_egg.x:
                    dx = -1
                if e_head.y < target_player_egg.y:
                    dy = 1
                elif e_head.y > target_player_egg.y:
                    dy = -1
                move_towards_egg = (dx, dy)
                if move_towards_egg in moves_to_use: # Prioritize valid move towards egg
                    dx, dy = move_towards_egg
                elif moves_to_use: # If direct move invalid, use any valid move
                    dx, dy = random.choice(moves_to_use)
                elif possible_moves: # No valid moves at all, use a potentially colliding move if possible
                    dx, dy = move_towards_egg if move_towards_egg in possible_moves else random.choice(possible_moves)


            elif target_food: # Move towards food if detected (lowest priority)
                if e_head.x < target_food.x:
                    dx = 1
                elif e_head.x > target_food.x:
                    dx = -1
                if e_head.y < target_food.y:
                    dy = 1
                elif e_head.y > target_food.y:
                    dy = -1
                move_towards_food = (dx, dy)
                if move_towards_food in moves_to_use: # Prioritize valid move towards food
                    dx, dy = move_towards_food
                elif moves_to_use: # If direct move invalid, use any valid move
                    dx, dy = random.choice(moves_to_use)
                elif possible_moves: # No valid moves at all, use a potentially colliding move if possible
                    dx, dy = move_towards_food if move_towards_food in possible_moves else random.choice(possible_moves)


            elif valid_moves: # No target, use any valid move if available
                 dx, dy = random.choice(valid_moves)
            elif possible_moves: # If absolutely no valid moves (highly unlikely but for robustness), choose any move to avoid complete standstill
                dx, dy = random.choice(possible_moves)
            else: # No moves at all - stay put (dx, dy already initialized to 0,0)
                pass # Keep dx, dy as 0, 0 - effectively no move


            new_e_head = Point(
                max(0, min(GRID_WIDTH - 1, e_head.x + dx)),
                max(0, min(GRID_HEIGHT - 1, e_head.y + dy))
            )


            if new_e_head == previous_head_position: # Head didn't move - potential stuck situation
                if enemy.last_head_position is None: # First detection of being stuck
                    enemy.last_head_position = previous_head_position
                    enemy.stuck_timer_start_time = current_time
                elif current_time - enemy.stuck_timer_start_time >= 20: # Stuck for 20 seconds
                    # Escape mechanism: choose a random valid move to get unstuck
                    escape_moves = valid_moves if valid_moves else possible_moves # Prioritize valid moves, use all if none
                    if escape_moves:
                        escape_dx, escape_dy = random.choice(escape_moves)
                        new_e_head = Point(
                            max(0, min(GRID_WIDTH - 1, e_head.x + escape_dx)),
                            max(0, min(GRID_HEIGHT - 1, e_head.y + escape_dy))
                        )
                        # Force move in escape direction
                        dx, dy = escape_dx, escape_dy # Update dx, dy for movement application below


                    enemy.last_head_position = None # Reset stuck status after escape attempt
                    enemy.stuck_timer_start_time = 0 # Reset stuck timer


            else: # Head moved successfully
                enemy.last_head_position = None # Reset stuck detection
                enemy.stuck_timer_start_time = 0


            if new_e_head not in enemy.body:
                enemy.body.insert(0, new_e_head)
                if target_food and new_e_head == target_food: # Eat food
                    enemy.body.append(enemy.body[-1])  # Grow enemy by 1 (original behaviour)
                    self.food = None
                    enemy_grew = True
                elif target_player_egg and new_e_head == target_player_egg: # Eat player egg
                    enemy.body.extend([enemy.body[-1]] * 2) # Grow by 2 segments
                    self.player_eggs.remove(egg_obj) # Remove eaten egg, remove Egg object
                    enemy_grew = True
                elif target_player_tail and new_e_head == target_player_tail:
                    enemy.body.extend([enemy.body[-1]] * 2) # Grow significantly by targeting tail
                    self.player.body.pop() # Player loses tail segment when tail eaten
                    if self.player.body: # Ensure player is still alive after losing tail
                        self.player.body.pop() # Remove one more segment, for significant tail bite
                    else:
                        self.game_over = True # Player dies if tail bite removes last segment
                        self.end_message = f"Game Over! Score: {self.score}"
                        self.game_end_time = time.time()
                        return
                    target_player_tail = None # Reset tail target after eating
                    enemy_grew = True


                if not enemy_grew:
                    enemy.body.pop()

            # Update enemy snake green status and speed based on length
            if len(enemy.body) <= 2:
                if not enemy.is_green: # Only change to green once
                    enemy.color = GREEN
                    enemy.head_color = GREEN
                    enemy.is_green = True
                    enemy.move_interval = 0.2 # Slower speed
            elif enemy.is_green: # Revert to red if grew beyond length 2
                enemy.color = enemy.original_color # Revert to original color
                enemy.head_color = ORANGE
                enemy.is_green = False
                enemy.move_interval = 0.1 # Normal speed


        # Spawn food every 5 seconds
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

        # Enemy egg laying - Halve the time when only 1 enemy left
        enemy_egg_interval = 30 # Normal interval
        if len(self.enemies) == 1:
            enemy_egg_interval = 15 # Halved interval

        if current_time - self.last_enemy_egg_time > enemy_egg_interval:
            for enemy in self.enemies:
                if random.random() < 0.3 and len(enemy.body) >= 3: # Check length >= 3
                    self.enemy_eggs.append(Egg(enemy.body[-1], current_time, "enemy")) # Egg type "enemy"
                    enemy.body.pop() # Reduce enemy length by 1 after laying egg
            self.last_enemy_egg_time = current_time

        # Player egg laying - NO egg lay if length is 2 or less
        if current_time - self.last_player_egg_time > 10:
            if random.random() < 0.5 and len(self.player.body) > 2: # Check player length > 2 (modified)
                self.player_eggs.append(Egg(self.player.body[-1], current_time, "player")) # Egg type "player"
                self.player.body.pop() # Reduce player length by 1 after laying egg
            self.last_player_egg_time = current_time

        # Collision with food
        if self.food and self.player.body[0] == self.food:
            self.grew = True
            self.food = None
            self.score += 10

        # Collision with eggs and enemies
        enemies_to_remove = []
        enemy_eggs_to_remove = [] # List to store enemy eggs to remove

        # Collision with Enemy Eggs
        for egg_obj in self.enemy_eggs:
            egg_point = egg_obj.get_point()
            if self.player.body[0] == egg_point:
                self.grew = True # Player snake grows
                enemy_eggs_to_remove.append(egg_obj) # Remove the egg
                self.score += 50 # Add score for eating enemy egg
                break # Only eat one egg per frame

        # Player no longer collides with Player Eggs


        # Collision with Enemies - Modified for body collision and head-on fix + stuck escape
        for i, enemy in enumerate(self.enemies):
            # ADDED CHECK: Ensure both snake bodies are not empty before accessing index 0 for head-on
            if self.player.body and enemy.body:
                if self.player.body[0] == enemy.body[0]: # Head-on collision
                    if enemy.color == GREEN:
                        enemies_to_remove.append(i)
                        self.grew = True
                        self.score += 50
                    else:
                        self.game_over = True
                        self.end_message = f"Game Over! Score: {self.score}"
                        self.game_end_time = time.time() # Record game over time
                        return
            # Enemy head collides with player body (NEW - Enemy eats Player)
            if enemy.body[0] in self.player.body[1:]:
                if self.player.body[0] != enemy.body[0]: # To prevent duplicate processing of head-on
                    original_player_length = len(self.player.body)
                    collision_index = self.player.body.index(enemy.body[0])
                    removed_length = original_player_length - collision_index
                    self.player.body = self.player.body[:collision_index] # Player loses length from collision point onwards
                    enemy.body.extend([enemy.body[-1]] * removed_length) # Enemy gains the length
                    self.grew = True # Player grew (due to length change, though visually shrinking)
                    if len(enemy.body) <= 2: # Turn green if enemy length <= 2
                        enemy.color = GREEN
                        enemy.head_color = GREEN
                        enemy.is_green = True
                        enemy.move_interval = 0.2 # Slower speed
                    break # Only process one body collision per frame

            # Player head collides with enemy body (ORIGINAL - Player eats Enemy)
            elif self.player.body[0] in enemy.body[1:]: # Player head collides with enemy body (existing logic)
                original_enemy_length = len(enemy.body) # Store original enemy length
                pos = enemy.body.index(self.player.body[0])
                enemy.body = enemy.body[:pos]
                removed_length = original_enemy_length - len(enemy.body) # Calculate removed length
                self.player.body.extend([self.player.body[-1]] * removed_length) # Player grows by removed length
                self.grew = True
                if len(enemy.body) <= 2: # Turn green if length is now 1 or 2
                    enemy.color = GREEN
                    enemy.head_color = GREEN
                    enemy.is_green = True
                    enemy.move_interval = 0.2 # Slower speed

        # Remove eaten enemy eggs
        for egg_obj in enemy_eggs_to_remove:
            self.enemy_eggs.remove(egg_obj)
            self.grew = True

        for i in sorted(enemies_to_remove, reverse=True):
            self.enemies.pop(i)

        # Hatch eggs - fixed 10 seconds hatch time
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


        # Remove tail if no growth
        if not self.grew:
            self.player.body.pop()

        # Win condition: check if all enemy snakes are eaten
        if not self.enemies:
            self.game_over = True
            self.end_message = f"You've Won! Score: {self.score}"
            self.game_end_time = time.time() # Record game over time


    def draw(self):
        self.screen.fill(BLACK)

        # Draw boundary
        pygame.draw.rect(self.screen, WHITE, (0, 0, WINDOW_WIDTH, WINDOW_HEIGHT), 2)

        # Draw player snake
        for i, seg in enumerate(self.player.body):
            color = self.player.head_color if i == 0 else self.player.color
            pygame.draw.rect(self.screen, color, (seg.x * CELL_SIZE, seg.y * CELL_SIZE, CELL_SIZE, CELL_SIZE))

        # Draw enemy snakes
        for enemy in self.enemies:
            for i, seg in enumerate(enemy.body):
                color = enemy.head_color if i == 0 else enemy.color
                pygame.draw.rect(self.screen, color, (seg.x * CELL_SIZE, seg.y * CELL_SIZE, CELL_SIZE, CELL_SIZE))

        # Draw food
        if self.food:
            pygame.draw.rect(self.screen, YELLOW, (self.food.x * CELL_SIZE, self.food.y * CELL_SIZE, CELL_SIZE, CELL_SIZE))

        # Draw eggs - colored based on type
        for egg_obj in self.player_eggs: # Player eggs - CYAN
            egg = egg_obj.get_point()
            pygame.draw.circle(self.screen, CYAN, (int(egg.x * CELL_SIZE + CELL_SIZE / 2), int(egg.y * CELL_SIZE + CELL_SIZE / 2)), int(CELL_SIZE / 2))
        for egg_obj in self.enemy_eggs: # Enemy eggs - PINK
            egg = egg_obj.get_point()
            pygame.draw.circle(self.screen, PINK, (int(egg.x * CELL_SIZE + CELL_SIZE / 2), int(egg.y * CELL_SIZE + CELL_SIZE / 2)), int(CELL_SIZE / 2))


        # Draw score, timer, and length
        font = pygame.font.SysFont(None, 30)
        score_text = font.render(f"Score: {self.score}", True, WHITE)

        if not self.game_over: # Update timer only if game is not over
            elapsed_seconds = int(time.time() - self.game_start_time)
            minutes = elapsed_seconds // 60
            seconds = elapsed_seconds % 60
            timer_string = f"Time: {minutes:02}:{seconds:02}" # MM:SS format
            self.last_timer_seconds = elapsed_seconds # Store total seconds for freezing
        else:
            elapsed_seconds = self.last_timer_seconds # Use the last stored value to freeze timer
            minutes = elapsed_seconds // 60
            seconds = elapsed_seconds % 60
            timer_string = f"Time: {minutes:02}:{seconds:02}" # MM:SS format


        timer_text = font.render(timer_string, True, WHITE)
        length_text = font.render(f"Length: {len(self.player.body)}", True, WHITE)

        self.screen.blit(score_text, (10, 10))
        self.screen.blit(timer_text, (150, 10)) # Position timer next to score
        self.screen.blit(length_text, (300, 10)) # Position length next to timer, adjusted position

        # Game over or win screen
        if self.game_over:
            font = pygame.font.SysFont(None, 40)
            color = RED if "Game Over" in self.end_message else GREEN
            text = font.render(self.end_message, True, color)
            text_rect = text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
            self.screen.blit(text, text_rect)

        pygame.display.flip()

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and self.game_over and event.key == pygame.K_RETURN:
                    return True  # Restart game

            self.update()
            self.draw()
            self.clock.tick(60)  # 60 FPS

        return False

# Main function to run the game
def main():
    while True:
        game = Game()
        if not game.run():
            break
    pygame.quit()

if __name__ == "__main__":
    main()
