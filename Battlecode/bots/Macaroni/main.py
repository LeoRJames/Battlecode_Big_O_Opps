import random
from cambc import Controller, Direction, EntityType, Environment, Position

DIRECTIONS = [d for d in Direction if d != Direction.CENTRE]
DIAGONALS  = [Direction.NORTHEAST, Direction.NORTHWEST, Direction.SOUTHEAST, Direction.SOUTHWEST]
NON_DIAGONALS = [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]


class Player:
    def __init__(self):
        self.num_spawned = 0  # number of builder bots spawned so far (core)
        self.dir = Direction.CENTRE  # Arbitrary
        self.core_pos = Position(1000, 1000)  # Arbitrary farr outside map range
        self.enemy_core_position = Position(1000, 1000)
        self.closest_conveyor = Position(1000, 1000)
        self.connect_harvester = False
        self.target = Position(0, 0)
        self.status = 0
        self.last_position = Position(0, 0)


    def initialise(self, ct):

        vision_tiles = ct.get_nearby_tiles()
        for i in vision_tiles:
            if ct.get_entity_type(ct.get_tile_building_id(i)) == EntityType.MARKER and ct.get_team(ct.get_tile_building_id(i)) == ct.get_team():
                marker_value = ct.get_marker_value(ct.get_tile_building_id(i))
                marker_value_id = (marker_value % (2 ** 28)) // (2 ** 20)
                marker_status = marker_value // (2 ** 28)

                if marker_value_id == ct.get_id(): # if marker is referring to this bot
                    if ct.can_move(ct.get_position().direction_to(i)):
                        ct.move(ct.get_position().direction_to(i))
                    if ct.can_destroy(i):   # Destroy marker
                        ct.destroy(i)
                    if marker_status == 1:
                        # Load Position to check for opponent core
                        target_x = (marker_value % (2 ** 12)) // (2 ** 6) -1
                        target_y = marker_value % (2 ** 6)
                        self.target = Position(target_x, target_y)
                        self.status = 1
                        ct.draw_indicator_dot(self.target,200,0,0)
                    return

            # Save position of the core
            if ct.get_entity_type(ct.get_tile_building_id(ct.get_position())) == EntityType.CORE and ct.get_team(ct.get_tile_building_id(ct.get_position())) == ct.get_team():
                self.core_pos = ct.get_position(ct.get_tile_building_id(ct.get_position()))
                ct.draw_indicator_dot(self.core_pos, 0, 255, 0)
            else:
                ct.draw_indicator_dot(ct.get_position(), 0, 0, 0)


    def find_enemy_core(self, ct):
        pos = ct.get_position()

        self.move(ct)
        ct.move(self.dir)

        if ct.get_current_round() > 100: # Dont get stuck
            self.status = 3
            return

        if ct.is_in_vision(self.target):
            building_id = ct.get_tile_building_id(self.target)
            if building_id and ct.get_entity_type(building_id) == EntityType.CORE: # ENEMY CORE HAS BEEN FOUND!
                self.target = self.core_pos
                enemy_core_x, enemy_core_y = ct.get_position(building_id).x, ct.get_position(building_id).y
                self.enemy_core_position = ct.get_position(building_id)
                marker_status = 2
                bot_id = 0
                message = (
                        marker_status * (2 ** 28)
                        + bot_id * (2 ** 20)
                        + enemy_core_x * (2 ** 6)
                        + enemy_core_y)
                for i in DIRECTIONS:
                    if ct.can_place_marker(pos.add(i)):
                        ct.place_marker(pos.add(i),message)
                        self.status = 2
                        return

            # Core was not here
            self.status = 3
            ct.draw_indicator_dot(pos, 0, 200, 200)


    def spread_the_news_about_said_enemy_core(self, ct):

        pos = ct.get_position()

        self.target = self.core_pos
        self.move(ct)
        ct.move(self.dir)

        enemy_core_x, enemy_core_y = self.enemy_core_position.x, self.enemy_core_position.y
        marker_status = 2
        bot_id = 0
        message = (
                marker_status * (2 ** 28)
                + bot_id * (2 ** 20)
                + enemy_core_x * (2 ** 6)
                + enemy_core_y)

        if random.randint(1,5) == 5 or ct.is_in_vision(self.core_pos):
            for i in DIRECTIONS:
                if ct.can_place_marker(pos.add(i)):
                    ct.place_marker(pos.add(i), message)

                    if ct.is_in_vision(self.core_pos):
                        self.status = 3
                        ct.draw_indicator_dot(pos, 0, 200, 200)
                    return


    def find_ores(self, ct):
        vision_tiles = ct.get_nearby_tiles()
        adj_tiles = ct.get_nearby_tiles(4)
        # Search for an unmined ore to Ore if it can.

        for i in adj_tiles:
            if ct.get_tile_env(i) in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]:
                if ct.can_build_harvester(i):
                    ct.build_harvester(i)
                    self.status = 4
                    return

        for i in vision_tiles:
            if ct.get_tile_env(i) in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE] and not(ct.get_tile_building_id(i)):
                self.target = i
                self.move(ct)
                ct.move(self.dir)
                return

        # Well and truly lost, so just keeping moving forward, if it can.
        if self.dir == Direction.CENTRE:
            self.dir = random.choice(DIRECTIONS)
        pos = ct.get_position()
        if ct.can_move(self.dir):
            ct.move(self.dir)
        elif ct.can_build_road(pos.add(self.dir)):
            ct.build_road(pos.add(self.dir))
            ct.move(self.dir)
        else:
            self.dir = random.choice(DIRECTIONS)


    def build_conveyor_home(self, ct):
        adj_tiles = ct.get_nearby_tiles(4)
        pos = ct.get_position()
        self.target = self.core_pos

        self.dir = pos.direction_to(self.target)
        if self.dir in DIAGONALS:
            self.dir = self.dir.rotate_right()

        for i in adj_tiles:
            if ct.get_entity_type(ct.get_tile_building_id(i)) == EntityType.HARVESTER:
                for j in NON_DIAGONALS:
                    if not(ct.get_entity_type(ct.get_tile_building_id(i.add(j))) == EntityType.CONVEYOR) and not(ct.get_entity_type(ct.get_tile_building_id(i.add(j))) == EntityType.HARVESTER) and ct.can_destroy(i.add(j)):
                        ct.destroy(i.add(j))
                    if ct.can_build_conveyor(i.add(j), self.dir):
                        ct.build_conveyor(i.add(j), self.dir)
                        return

        if ct.get_team(ct.get_tile_building_id(pos)) != ct.get_team():
            dir_A = pos.direction_to(self.target)
            if dir_A in DIAGONALS:
                dir_A = dir_A.rotate_right()

            if ct.can_destroy(pos):
                ct.destroy(pos)
            else:
                ct.move(pos.direction_to(self.last_position))
                self.last_position = pos
                pos = ct.get_position()
            if ct.can_destroy(pos):
                    ct.destroy(pos)
            if ct.can_build_bridge(pos,pos.add(dir_A).add(dir_A)):
                ct.build_bridge(pos,pos.add(dir_A).add(dir_A))
                self.target = pos.add(dir_A).add(dir_A)
                self.status = 5
                return

        if ct.get_entity_type(ct.get_tile_building_id(pos)) == EntityType.ROAD:
            dir_A = pos.direction_to(self.target)
            if dir_A in DIAGONALS:
                dir_A = dir_A.rotate_right()

            dir_B = pos.add(dir_A).direction_to(self.target)
            if dir_B in DIAGONALS:
                dir_B = dir_B.rotate_right()
            ct.draw_indicator_line(pos.add(dir_A), pos, 0, 0, 0)

            if ct.can_destroy(pos):
                ct.destroy(pos)
            if ct.can_build_conveyor(pos,dir_A):
                ct.build_conveyor(pos,dir_A)
                return

        dir_A = pos.direction_to(self.target)
        if ct.get_tile_env(pos.add(dir_A)) == Environment.WALL and ct.get_entity_type(ct.get_tile_building_id(pos)) != EntityType.BRIDGE:
            if ct.can_destroy(pos):
                ct.destroy(pos)

            goal = pos.add(dir_A).add(dir_A)
            if ct.get_entity_type(ct.get_tile_building_id(goal)) == EntityType.CONVEYOR or ct.get_entity_type(
                    ct.get_tile_building_id(goal)) == EntityType.ROAD or ct.get_tile_env(goal) == Environment.EMPTY:
                ct.draw_indicator_line(pos, pos.add(dir_A).add(dir_A), 0, 200, 0)
                if ct.can_build_bridge(pos,pos.add(dir_A).add(dir_A)):
                    ct.build_bridge(pos,pos.add(dir_A).add(dir_A))

                    self.target = pos.add(dir_A).add(dir_A)
                    self.status = 5
                    return

            for i in DIAGONALS:
                goal = pos.add(dir_A).add(dir_A).add(i)
                ct.draw_indicator_line(pos, goal, 0, 200, 0)
                if ct.get_entity_type(ct.get_tile_building_id(goal)) == EntityType.CONVEYOR or ct.get_entity_type(ct.get_tile_building_id(goal)) == EntityType.ROAD or ct.get_tile_env(goal) == Environment.EMPTY:
                    if ct.can_build_bridge(pos, goal):

                        ct.build_bridge(pos, goal)

                        self.target = goal
                        self.status = 5
                        return


        if dir_A in DIAGONALS:
            dir_A = dir_A.rotate_right()
        dir_B = pos.add(dir_A).direction_to(self.target)
        if dir_B in DIAGONALS:
            dir_B = dir_B.rotate_right()
        dir_C = pos.add(dir_A).add(dir_B).direction_to(self.target)
        ct.draw_indicator_line(pos.add(dir_A), pos, 0, 0, 0)

        if ct.can_destroy(pos.add(dir_A)) and ct.get_entity_type(ct.get_tile_building_id(pos.add(dir_A))) != EntityType.CONVEYOR:
            ct.destroy(pos.add(dir_A))


        if ct.can_build_conveyor(pos.add(dir_A), dir_B):
            ct.build_conveyor(pos.add(dir_A), dir_B)
            #ct.build_bridge(pos.add(dir_A), pos.add(dir_A).add(dir_B))

        '''  WORKING ON CHANGING TO BRIDGES
        if ct.can_build_bridge(pos.add(dir_A), pos.add(dir_A).add(dir_B).add(dir_C)):
            ct.build_bridge(pos.add(dir_A), pos.add(dir_A).add(dir_B).add(dir_C))
            goal = pos.add(dir_A).add(dir_B).add(dir_C)
            self.target = goal
            self.status = 5
            return

        elif ct.can_build_bridge(pos.add(dir_A), pos.add(dir_A).add(dir_B)):
            ct.build_bridge(pos.add(dir_A), pos.add(dir_A).add(dir_B))
        '''

        self.dir = dir_A
        if ct.can_move(self.dir):
            ct.move(self.dir)
            self.last_position = pos


        if ct.get_position().distance_squared(self.core_pos) <= 4:
            self.status = 3


    def move(self, ct):
        pos = ct.get_position()
        move_dir = pos.direction_to(self.target)

        for i in range(8):
            ct.draw_indicator_dot(pos.add(move_dir), 250, 250, 250)
            if pos.add(move_dir) == self.last_position:
                move_dir = move_dir.rotate_left()
                ct.draw_indicator_dot(pos, 250, 0, 0)
                pass
            building_id = ct.get_tile_building_id(pos.add(move_dir))
            if not(ct.is_tile_passable(pos.add(move_dir))) and ct.can_destroy(pos.add(move_dir)) and ct.get_entity_type(building_id) != EntityType.HARVESTER:    # Remove obstacles
                ct.destroy(pos.add(move_dir))
            if ct.can_move(move_dir):
                break
            elif ct.can_build_road(pos.add(move_dir)):
                ct.build_road(pos.add(move_dir))
                if ct.can_move(move_dir):
                    break
            else: # else move clockwise around the target
                move_dir = move_dir.rotate_left()
            if i == 7:
                return False
        self.last_position = pos
        self.dir = move_dir


    def go_to(self, ct, status=3):
        pos = ct.get_position()
        move_dir = pos.direction_to(self.target)

        for i in range(8):
            ct.draw_indicator_dot(pos.add(move_dir), 250, 250, 250)
            if pos.add(move_dir) == self.last_position:
                move_dir = move_dir.rotate_left()
                ct.draw_indicator_dot(pos, 250, 0, 0)
                pass
            building_id = ct.get_tile_building_id(pos.add(move_dir))
            if not (ct.is_tile_passable(pos.add(move_dir))) and ct.can_destroy(
                    pos.add(move_dir)) and ct.get_entity_type(building_id) != EntityType.HARVESTER:  # Remove obstacles
                ct.destroy(pos.add(move_dir))
            if ct.can_move(move_dir):
                break
            elif ct.can_build_road(pos.add(move_dir)):
                ct.build_road(pos.add(move_dir))
                if ct.can_move(move_dir):
                    break
            else:  # else move clockwise around the target
                move_dir = move_dir.rotate_left()
            if i == 7:
                return False
        self.last_position = pos
        self.dir = move_dir
        ct.move(self.dir)

        if ct.get_position() == self.target:
            self.status = status


    def run(self, ct: Controller) -> None:
        if ct.get_entity_type() == EntityType.CORE:
            close_vision_tiles = ct.get_nearby_tiles(5)
            core_position_x, core_position_y = ct.get_position()[0], ct.get_position()[1]
            possible_core_locations = [
                [ct.get_map_width() - core_position_x, core_position_y], # Horizontal Flip
                [core_position_x, ct.get_map_height() - core_position_y], # Vertical Flip
                [ct.get_map_width() - core_position_x, ct.get_map_height() - core_position_y]] # Rotation

            # First 3 bots have to find enemy base
            if self.num_spawned < 3:
                spawn_pos = ct.get_position().add(Direction.NORTH)
                if ct.can_spawn(spawn_pos):
                    ct.spawn_builder(spawn_pos)

                    # Place marker, so bot knows where to go
                    bot_id = ct.get_tile_builder_bot_id(spawn_pos)
                    marker_status = 1
                    message = (
                            marker_status * (2**28)
                            + bot_id * (2**20)
                            + possible_core_locations[self.num_spawned][0] * (2**6)
                            + possible_core_locations[self.num_spawned][1])
                    self.num_spawned += 1
                    for i in close_vision_tiles:
                        if ct.is_tile_empty(i) and ct.can_place_marker(i):
                            ct.place_marker(i, message)


        elif ct.get_entity_type() == EntityType.BUILDER_BOT:


            if ct.get_global_resources()[0] < 400 and self.status != 4:
                return
            # Just spawned
            if self.status == 0:
                self.initialise(ct)

            # Find enemy core
            elif self.status == 1:
                self.find_enemy_core(ct)

            # Tell everyone about enemy core?
            elif self.status == 2:
                self.spread_the_news_about_said_enemy_core(ct)

            #Look for ores
            elif self.status == 3:
                self.find_ores(ct)

            elif self.status == 4:
                self.build_conveyor_home(ct)

            elif self.status == 5:
                self.go_to(ct, 4)

            elif self.status == "lost":
                self.find_ores(ct)

            elif self.status == "core_defence":
                self.defence()

            elif self.status == "find foe":
                self.find_foe()




