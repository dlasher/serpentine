# serpentine
python-based loving nod to the classic commodore game Serpentine
* requires pygame
* arrow keys for movement
* PLAYER is BLUE, ENEMY snakes are RED
* YELLOW blocks are food - eat them for growth
* CYAN circles are PLAYER eggs, enemy snakes eat them for growth
* PINK circles are ENEMY eggs, eat those for points + growth
* ENEMY snakes turn GREEN when length 2 or less - can be eaten head-on.
* headfirst into the wall pauses the game, change direction to unpause (it's a feature! Really!)


## serpentine
* classic rules
* enemy snakes can't harm you
* enemy snakes ignore you
* enemy snakes have a fairly small detection range for eggs & food
* chomp them till they're gone, you win

## serpentine-hard
* updated rules
* enemy snakes detect range for eggs & food is 50% of the screen width/height when normal sized
* enemy snakes detect range for eggs & food is 100% of the screen width/height when sized 2 or less
* enemy snakes will chase you when they get your scent (aka your tail)
* enemy snakes subtract from YOUR length, just like you do from theirs
* enemy snakes are aware when they're stuck, and unstick
* when single enemy snake is left, egg laying timer is cut in half.

Written with a combination of terribly written python, pygame, grok, gemini.

Enjoy!
