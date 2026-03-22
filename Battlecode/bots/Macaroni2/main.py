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
        self.target = Position(0, 0)
        self.status = 0
        self.last_positions = [Position(0, 0), Position(0,0)]


    def initialise(self, ct):
        vision_tiles = ct.get_nearby_tiles()
        for i in vision_tiles:
            if ct.get_entity_type(ct.get_tile_building_id(i)) == EntityType.MARKER and ct.get_team(ct.get_tile_building_id(i)) == ct.get_team():
                marker_value = ct.get_marker_value(ct.get_tile_building_id(i))
                marker_value_id = (marker_value % (2 ** 28)) // (2 ** 12)
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
                    return

            # Save position of the core
            if ct.get_entity_type(ct.get_tile_building_id(ct.get_position())) == EntityType.CORE and ct.get_team(ct.get_tile_building_id(ct.get_position())) == ct.get_team():
                self.core_pos = ct.get_position(ct.get_tile_building_id(ct.get_position()))
            else:
                ct.draw_indicator_dot(ct.get_position(), 0, 0, 0)

            # Where road should be - Currently Core does not try to place a marker down a second time, if it can not the first time.
            if ct.get_entity_type(ct.get_tile_building_id(self.core_pos.add(Direction.NORTHWEST).add(Direction.NORTH))) == EntityType.ROAD:
                if ct.can_destroy(self.core_pos.add(Direction.NORTHWEST).add(Direction.NORTH)):
                    ct.destroy(self.core_pos.add(Direction.NORTHWEST).add(Direction.NORTH))


    def find_enemy_core(self, ct):
        pos = ct.get_position()

        self.go_to(ct)

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
                        + bot_id * (2 ** 12)
                        + enemy_core_x * (2 ** 6)
                        + enemy_core_y)
                for i in DIRECTIONS:
                    if ct.can_place_marker(pos.add(i)):
                        ct.place_marker(pos.add(i),message)
                        self.status = 2
                        return

            # Core was not at the location (could change to inform home about this?)
            self.status = 3
            ct.draw_indicator_dot(pos, 0, 200, 200)


    def spread_the_news_about_said_enemy_core(self, ct):

        pos = ct.get_position()

        self.target = self.core_pos
        self.go_to(ct)

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
        pos = ct.get_position()
        # Search for an unmined ore to Ore if it can.

        for j in adj_tiles:
            if ct.get_tile_env(j) in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]:
                if ct.can_destroy(j):
                    ct.destroy(j)
                    for d in Direction:
                        if ct.can_move(d):
                            ct.move(d)
                if ct.can_build_harvester(j):
                    ct.build_harvester(j)
                    return

                self.target = self.core_pos
                for i in adj_tiles:
                    if ct.get_entity_type(ct.get_tile_building_id(i)) == EntityType.HARVESTER:
                        for d in NON_DIAGONALS:
                            # CHECK IF i.add(d) is legal
                            if not(i.add(d).x >= 0 and i.add(d).y >= 0 and i.add(d).x <= ct.get_map_width() and i.add(d).y <= ct.get_map_height()):
                                ct.draw_indicator_dot(pos, 255, 0, 0)
                                break

                            if ct.get_entity_type(ct.get_tile_building_id(i.add(d))) == EntityType.BRIDGE:
                                break
                            dir_A = i.direction_to(self.target)
                            dir_B = i.add(dir_A).direction_to(self.target)
                            dir_C = i.add(dir_A).add(dir_B).direction_to(self.target)
                            goals = [i.add(d).add(dir_A).add(dir_B).add(dir_C), i.add(d).add(dir_A).add(dir_B)] + [
                                i.add(d).add(dir_A).add(dir_B).add(k) for k in DIRECTIONS] + [i.add(d).add(dir_A).add(k)
                                                                                              for k in DIRECTIONS]

                            for k in range(len(goals)):
                                ct.draw_indicator_line(i.add(d), goals[k], 50 * k, 50 * k, 50 * k)
                                if (ct.can_build_bridge(i.add(d), goals[k])
                                        and (ct.get_tile_building_id(goals[k]) is None or ct.get_team() == ct.get_team(
                                            ct.get_tile_building_id(goals[k])))
                                        and (ct.get_tile_env(goals[k]) == Environment.EMPTY)):
                                    ct.draw_indicator_line(i.add(d), goals[k], 0, 255, 0)
                                    ct.build_bridge(i.add(d), goals[k])
                                    self.target = goals[k]
                                    self.status = 5
                                    return

        for i in vision_tiles:
            ct.draw_indicator_dot(i, 200, 200, 200)
            if ct.get_tile_env(i) in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE] and not(ct.get_entity_type(ct.get_tile_building_id(i))== EntityType.HARVESTER):
                self.target = i
                self.go_to(ct)
                return

        # Well and truly lost, so just keeping moving forward, if it can.
        if self.dir == Direction.CENTRE:
            self.dir = random.choice(DIRECTIONS)
        pos = ct.get_position()
        if ct.can_move(self.dir):
            ct.move(self.dir)
        elif ct.can_build_road(pos.add(self.dir)):
            ct.build_road(pos.add(self.dir))
            if ct.can_move(self.dir):
                ct.move(self.dir)
        else:
            self.dir = random.choice(DIRECTIONS)


    def build_conveyor_home(self, ct):
        adj_tiles = ct.get_nearby_tiles(4) # Gives a diamond shape, and outer ring is where it can act if it sees a harvestor
        pos = ct.get_position()
        self.target = self.core_pos


        # BUILD BRIDGE FROM END OF LAST BRIDGE - This if statement should always be true
        if ct.get_entity_type(ct.get_tile_building_id(pos)) == EntityType.ROAD or ct.get_tile_building_id(pos) is None:
            if ct.can_destroy(pos):
                ct.destroy(pos)

            dir_A = pos.direction_to(self.target)
            dir_B = pos.add(dir_A).direction_to(self.target)
            dir_C = pos.add(dir_A).add(dir_B).direction_to(self.target)

            goals = [pos.add(dir_A).add(dir_B).add(dir_C), pos.add(dir_A).add(dir_B)] + [pos.add(dir_A).add(dir_B).add(i) for i in DIRECTIONS] + [pos.add(dir_A).add(i) for i in DIRECTIONS]
            for i in range(len(goals)):
                ct.draw_indicator_line(pos, goals[i], 50*i, 50*i, 50*i)

                if (ct.can_build_bridge(pos, goals[i])
                        and (ct.get_tile_building_id(goals[i]) is None or ct.get_team() == ct.get_team(ct.get_tile_building_id(goals[i])))
                        and ct.get_tile_env(goals[i]) == Environment.EMPTY):
                    if ct.get_team() is None:
                        ct.draw_indicator_line(pos, self.core_pos, 0, 0, 0)
                    elif ct.get_tile_env(goals[i]) == None:
                        ct.draw_indicator_line(pos, goals[i], 0, 0, 255)
                    ct.build_bridge(pos, goals[i])
                    self.target = goals[i]
                    self.status = 5
                    return
            # Cant build bridge anywhere
            self.status = 3

        elif ct.get_entity_type(ct.get_tile_building_id(pos)) == EntityType.BRIDGE:
            self.status = 3
            ct.draw_indicator_dot(pos, 0, 255, 255)

        elif ct.get_position().distance_squared(self.core_pos) <= 4:
            ct.draw_indicator_dot(pos, 255, 0, 0)
            self.status = 3

        elif ct.get_entity_type(ct.get_tile_building_id(pos)) == EntityType.BUILDER_BOT:
            return

        else: # EDGE CASE
            ct.draw_indicator_dot(pos, 255, 0, 0)
            self.status = 3

        if ct.get_position().distance_squared(self.core_pos) <= 4:
            self.status = 3


    def go_to(self, ct, status=3, set_status=False):
        pos = ct.get_position()
        move_dir = pos.direction_to(self.target)

        for i in range(8):
            ct.draw_indicator_dot(pos.add(move_dir), 250, 250, 250)
            if pos.add(move_dir) in self.last_positions:
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
        self.last_positions[1] = self.last_positions[0]
        self.last_positions[0] = pos
        self.dir = move_dir
        ct.move(self.dir)

        if set_status and ct.get_position() == self.target:
            self.status = status


    def destroy_core(self, ct):
        pos = ct.get_position()

        self.go_to(ct)

        if pos.distance_squared(self.target) <= 3:
            ct.self_destruct()


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
                            + bot_id * (2**12)
                            + possible_core_locations[self.num_spawned][0] * (2**6)
                            + possible_core_locations[self.num_spawned][1])
                    self.num_spawned += 1
                    for i in close_vision_tiles:
                        if ct.is_tile_empty(i) and ct.can_place_marker(i):
                            ct.place_marker(i, message)



        elif ct.get_entity_type() == EntityType.BUILDER_BOT:


            if ct.get_global_resources()[0] < 200 and self.status != 4:
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
                self.go_to(ct, 4, True)

            elif self.status == 6:
                self.destroy_core(ct)

            elif self.status == "core_defence":
                self.defence()

            elif self.status == "find foe":
                self.find_foe()




