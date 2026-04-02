import random
from cambc import Controller, Direction, EntityType, Environment, Position
from markdown_it.rules_inline import entity

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
        self.last_positions = []


    def bb_initialise(self, ct):
        vision_tiles = ct.get_nearby_tiles()
        for i in vision_tiles:
            if ct.get_entity_type(ct.get_tile_building_id(i)) == EntityType.MARKER and ct.get_team(ct.get_tile_building_id(i)) == ct.get_team():
                marker_value = ct.get_marker_value(ct.get_tile_building_id(i))
                marker_value_id = (marker_value % (2 ** 28)) // (2 ** 12)
                marker_status = marker_value // (2 ** 28)

                if marker_value_id == ct.get_id(): # if marker is referring to this bot

                    # Destroy marker if it can
                    if ct.can_move(ct.get_position().direction_to(i)):
                        ct.move(ct.get_position().direction_to(i))
                    if ct.can_destroy(i):   # Destroy marker
                        ct.destroy(i)

                    if marker_status == 1:
                        # Load Position to check for opponent core
                        target_x = (marker_value % (2 ** 12)) // (2 ** 6)
                        target_y = marker_value % (2 ** 6)
                        self.target = Position(target_x, target_y)
                        self.status = 1

                    elif marker_status == 2:
                        # Load Position to go attack opponent core
                        target_x = (marker_value % (2 ** 12)) // (2 ** 6)
                        target_y = marker_value % (2 ** 6)
                        self.target = Position(target_x, target_y)
                        self.enemy_core_position = self.target
                        self.status = 6
                    return

            # Save position of the core
            if ct.get_entity_type(ct.get_tile_building_id(ct.get_position())) == EntityType.CORE and ct.get_team(ct.get_tile_building_id(ct.get_position())) == ct.get_team():
                self.core_pos = ct.get_position(ct.get_tile_building_id(ct.get_position()))

            # Where road should be - Currently Core does not try to place a marker down a second time, if it can not the first time.
            if ct.get_entity_type(ct.get_tile_building_id(self.core_pos.add(Direction.NORTHWEST).add(Direction.NORTH))) == EntityType.ROAD:
                if ct.can_destroy(self.core_pos.add(Direction.NORTHWEST).add(Direction.NORTH)):
                    ct.destroy(self.core_pos.add(Direction.NORTHWEST).add(Direction.NORTH))


    def bb_find_enemy_core(self, ct):
        pos = ct.get_position()

        self.bb_go_to(ct)

        if ct.get_current_round() > 100: # Dont get stuck
            self.status = 3
            self.last_positions = []
            return

        if ct.is_in_vision(self.target):
            self.last_positions = []
            building_id = ct.get_tile_building_id(self.target)
            if building_id and ct.get_entity_type(building_id) == EntityType.CORE: # ENEMY CORE HAS BEEN FOUND!

                enemy_core_x, enemy_core_y = self.target.x, self.target.y
                self.enemy_core_position = self.target
                self.target = self.core_pos
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
                        self.target = self.core_pos
                        return

            # Core was not at the location (could change to inform home about this?)
            self.status = 3


    def bb_spread_the_news_about_said_enemy_core(self, ct):

        pos = ct.get_position()
        enemy_core_x, enemy_core_y = self.enemy_core_position.x, self.enemy_core_position.y
        marker_status = 2
        bot_id = 0
        message = (
                marker_status * (2 ** 28)
                + bot_id * (2 ** 20)
                + enemy_core_x * (2 ** 6)
                + enemy_core_y)

        for i in DIRECTIONS:
            if ct.get_position().distance_squared(self.core_pos) <= 9:
                if ct.can_place_marker(pos.add(i)):
                    ct.place_marker(pos.add(i), message)
                    self.status = 3
                    return
            if ct.can_place_marker(pos.add(i)):
                ct.place_marker(pos.add(i), message)
                self.bb_go_to(ct)
                return

        if ct.get_position().distance_squared(self.core_pos) <= 9:
            vision_tiles = ct.get_nearby_tiles(4)
            for i in vision_tiles:
                if ct.is_tile_empty(i):
                    self.target=i
        self.bb_go_to(ct)


    def bb_find_ores(self, ct):
        vision_tiles = ct.get_nearby_tiles()
        adj_tiles = ct.get_nearby_tiles(4)
        pos = ct.get_position()
        # Search for an unmined ore to Ore if it can.

        for j in adj_tiles:
            if ct.get_tile_env(j) in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE]:
                if ct.can_destroy(j) and ct.get_entity_type(ct.get_tile_building_id(j)) != EntityType.HARVESTER:
                    ct.destroy(j)
                    for d in Direction:
                        if ct.can_move(d):
                            ct.move(d)
                if ct.can_build_harvester(j):
                    ct.build_harvester(j)
                    self.last_positions = []
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

                            goals = [i.add(d).add(dir_A).add(dir_B).add(dir_C)] + [i.add(d).add(dir_A).add(dir_B).add(dir_C).add(k) for k in DIRECTIONS] + [i.add(d).add(dir_A).add(dir_B).add(k) for k in DIRECTIONS] + [i.add(d).add(dir_A).add(k).add(k) for k in DIRECTIONS]
                            for k in range(len(goals)):
                                if (ct.can_build_bridge(i.add(d), goals[k])
                                        and ((ct.get_tile_building_id(goals[k]) is None) or ct.get_team() == ct.get_team(ct.get_tile_building_id(goals[k])))
                                        and (ct.get_tile_env(goals[k]) == Environment.EMPTY)
                                        and (ct.get_tile_env(i.add(d)) == Environment.EMPTY)):
                                    ct.draw_indicator_line(i.add(d), goals[k], 0, 255, 0)
                                    ct.build_bridge(i.add(d), goals[k])
                                    self.last_positions = []
                                    self.target = goals[k]
                                    self.status = 5
                                    return
                                elif ct.can_build_bridge(i.add(d), goals[k]):
                                    ct.draw_indicator_line(i.add(d), goals[k], 250 , 0, 0)

        vision_tiles = ct.get_nearby_tiles()
        for i in vision_tiles:
            if ct.get_tile_env(i) in [Environment.ORE_TITANIUM, Environment.ORE_AXIONITE] and not(ct.get_entity_type(ct.get_tile_building_id(i))== EntityType.HARVESTER):
                self.target = i
                self.bb_go_to(ct)
                return

        # Well and truly lost, so just keeping moving forward, if it can.
        if self.dir == Direction.CENTRE:
            self.dir = random.choice(DIRECTIONS)
        pos = ct.get_position()
        if ct.can_move(self.dir):
            ct.move(self.dir)
            self.last_positions.append(pos)
        elif ct.can_build_road(pos.add(self.dir)):
            ct.build_road(pos.add(self.dir))
            if ct.can_move(self.dir):
                ct.move(self.dir)
                self.last_positions.append(pos)
        else:
            self.dir = random.choice(DIRECTIONS)


    def bb_build_conveyor_home(self, ct):
        pos = ct.get_position()
        self.target = self.core_pos

        # Try to build conveyor, if not possible, build bridge.
        dir_A = pos.direction_to(self.target)
        if dir_A in DIAGONALS:
            dir_A = dir_A.rotate_left()
        dir_B = pos.add(dir_A).direction_to(self.target)
        if dir_B in DIAGONALS:
            dir_B = dir_B.rotate_left()

        # This code should run only if it reaches a base of a bridge it built earlier
        if ct.get_entity_type(ct.get_tile_building_id(pos)) == EntityType.ROAD or ct.get_tile_building_id(pos) is None:
            if not(ct.can_destroy(pos)):
                # Path should be an enemy path so not worth caring about imo
                self.status = 3
                return
            ct.destroy(pos)

            # If subsequent tile matches the requirement for a conveyor, build one.
            next_pos = pos.add(dir_A)
            next_pos_id = ct.get_tile_building_id(next_pos)
            if ((ct.get_entity_type(next_pos_id) in [EntityType.ROAD, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.CORE] and ct.get_team(next_pos_id) == ct.get_team(next_pos_id))
                    or (ct.get_tile_env(next_pos) == Environment.EMPTY and next_pos_id is None)):

                # Then, it should be able to build a conveyor (excluding money constraints)
                if ct.can_build_conveyor(pos, dir_A):
                    ct.build_conveyor(pos, dir_A)
                else:
                    return
            else:
                dir_A = pos.direction_to(self.target)
                dir_B = pos.add(dir_A).direction_to(self.target)
                dir_C = pos.add(dir_A).add(dir_B).direction_to(self.target)
                goals = ([pos.add(dir_A).add(dir_B).add(dir_C)] + [pos.add(dir_A).add(dir_B).add(dir_C).add(k) for k in DIRECTIONS]
                         + [pos.add(dir_A).add(dir_B).add(k) for k in DIRECTIONS] + [pos.add(dir_A).add(dir_B).add(k).add(k) for k in DIRECTIONS]
                         + [pos.add(dir_A).add(dir_B).add(k).add(k.rotate_left()) for k in DIRECTIONS] + [pos.add(dir_A).add(dir_B).add(k).add(k.rotate_right()) for k in DIRECTIONS])

                for i in range(len(goals)):
                    if (ct.can_build_bridge(pos, goals[i])
                            and (ct.get_tile_building_id(goals[i]) is None or ct.get_team() == ct.get_team(
                                ct.get_tile_building_id(goals[i])))
                            and ct.get_tile_env(goals[i]) == Environment.EMPTY):
                        ct.build_bridge(pos, goals[i])
                        self.target = goals[i]
                        self.status = 5
                        ct.draw_indicator_line(pos, goals[i], 255, 255, 255)
                        return
                # Cant build bridge anywhere
                if ct.get_global_resources()[0] < 10 * ct.get_scale_percent():  # resources too low
                    return
                self.status = 3
            return

        # If it is standing on a conveyor and needs to build one ahead
        elif ct.get_entity_type(ct.get_tile_building_id(pos)) in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR]:
            conveyor_direction = ct.get_direction(ct.get_tile_building_id(pos))
            base_pos = pos.add(dir_A)
            base_pos_id = ct.get_tile_building_id(base_pos)
            next_pos = base_pos.add(dir_B)
            next_pos_id = ct.get_tile_building_id(next_pos)
            ct.draw_indicator_line(base_pos, next_pos, 0, 255, 0)

            if base_pos_id is None or (ct.get_entity_type(base_pos_id) == EntityType.ROAD and ct.get_team(base_pos_id) == ct.get_team()):
                if ct.can_destroy(pos.add(dir_A)):
                    ct.destroy(pos.add(dir_A))

                if ((ct.get_entity_type(next_pos_id) in [EntityType.ROAD, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.CORE] and ct.get_team(next_pos_id) == ct.get_team())
                        or (ct.get_tile_env(next_pos) == Environment.EMPTY and next_pos_id is None)):
                    # Then, it should be able to build a conveyor (excluding money constraints)
                    if ct.can_build_conveyor(base_pos, dir_B):
                        ct.build_conveyor(base_pos, dir_B)
                        if ct.get_entity_type(next_pos_id) in [EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.CORE]:
                            self.status = 3
                            return
                        ct.move(dir_A)
                    else:
                        return
                else:
                    # Needs to build bridge
                    pos = pos.add(conveyor_direction)
                    dir_A = pos.direction_to(self.target)
                    dir_B = pos.add(dir_A).direction_to(self.target)
                    dir_C = pos.add(dir_A).add(dir_B).direction_to(self.target)
                    goals = ([pos.add(dir_A).add(dir_B).add(dir_C)] + [pos.add(dir_A).add(dir_B).add(dir_C).add(k) for k
                                                                       in DIRECTIONS]
                             + [pos.add(dir_A).add(dir_B).add(k) for k in DIRECTIONS] + [
                                 pos.add(dir_A).add(dir_B).add(k).add(k) for k in DIRECTIONS]
                             + [pos.add(dir_A).add(dir_B).add(k).add(k.rotate_left()) for k in DIRECTIONS] + [
                                 pos.add(dir_A).add(dir_B).add(k).add(k.rotate_right()) for k in DIRECTIONS])

                    for i in range(len(goals)):
                        if (ct.can_build_bridge(pos, goals[i])
                                and (ct.get_tile_building_id(goals[i]) is None or ct.get_team() == ct.get_team(
                                    ct.get_tile_building_id(goals[i])))
                                and ct.get_tile_env(goals[i]) == Environment.EMPTY):
                            ct.build_bridge(pos, goals[i])
                            self.target = goals[i]
                            self.status = 5
                            ct.draw_indicator_line(pos, goals[i], 255, 255, 255)
                            return
                    # Cant build bridge anywhere
                    if ct.get_global_resources()[0] < 10 * ct.get_scale_percent():  # resources too low
                        return
                    self.status = 3
            return

        # probably connected to a bridge which is connected to the core
        elif ct.get_entity_type(ct.get_tile_building_id(pos)) == EntityType.BRIDGE:
            self.status = 3
            return

        # Something has gone wrong
        else:
            self.status = 3
            return


    def bb_go_to(self, ct, status=3, set_status=False, move=True):
        '''
            If there is e.g. enemy bot on target tile,
        '''
        pos = ct.get_position()
        move_dir = pos.direction_to(self.target)

        if len(self.last_positions) > 20: # if stuck in a loop, show its ppath
            for i in range(len(self.last_positions) -1):
                ct.draw_indicator_line(self.last_positions[i], self.last_positions[i+1], 5*i, 50, 50)

        for i in range(8):
            if i == 7:
                return False

            if pos.add(move_dir) in self.last_positions and pos.add(move_dir) != self.target:
                move_dir = move_dir.rotate_left()
                continue

            if not(pos.add(move_dir).x >= 0 and pos.add(move_dir).y >= 0 and pos.add(move_dir).x < ct.get_map_width() and pos.add(move_dir).y < ct.get_map_height()):
                continue
            building_id = ct.get_tile_building_id(pos.add(move_dir))
            if not (ct.is_tile_passable(pos.add(move_dir))) and ct.can_destroy(
                    pos.add(move_dir)) and ct.get_entity_type(building_id) not in [EntityType.HARVESTER, EntityType.GUNNER]:  # Remove obstacles
                ct.destroy(pos.add(move_dir))
            if ct.can_move(move_dir):
                break
            elif ct.can_build_road(pos.add(move_dir)):
                ct.build_road(pos.add(move_dir))
                if ct.can_move(move_dir):
                    break
            else:  # else move clockwise around the target
                move_dir = move_dir.rotate_left()

        self.last_positions.append(pos)
        self.dir = move_dir
        if not(move):
            return self.dir
        ct.move(self.dir)

        if set_status and ct.get_position() == self.target:
            self.last_positions = []
            self.status = status


    def bb_go_to_enemy_core(self, ct):
        pos = ct.get_position()
        self.bb_go_to(ct)

        if pos.distance_squared(self.enemy_core_position) <= 10:
            vision_tiles = ct.get_nearby_tiles()
            for i in vision_tiles:
                if ct.get_entity_type(ct.get_tile_building_id(i)) == EntityType.CORE:
                    ct.draw_indicator_dot(i, 0, 0, 0)
            self.status = 7
            return


    def bb_destroy_enemy_defences(self, ct): # NEEDS REWORK
        vision_tiles = ct.get_nearby_tiles()
        pos = ct.get_position()

        if self.target == self.enemy_core_position: # i.e needs to be updates
            for i in vision_tiles:
                if ct.get_entity_type(ct.get_tile_building_id(i)) in [EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR]:
                    if ct.get_entity_type(ct.get_tile_building_id(i)) == EntityType.BRIDGE and (ct.is_in_vision(ct.get_bridge_target(ct.get_tile_building_id(i)))  and (ct.is_tile_empty(ct.get_bridge_target(ct.get_tile_building_id(i)) or ct.get_entity_type(ct.get_tile_building_id(ct.get_bridge_target(ct.get_tile_building_id(i))))) == EntityType.ROAD) and ct.get_bridge_target(ct.get_tile_building_id(i)).distance_squared(self.enemy_core_position) <= 16):
                        self.target = ct.get_bridge_target(ct.get_tile_building_id(i))
                    elif ct.get_entity_type(ct.get_tile_building_id(i)) == EntityType.BRIDGE and (pos.distance_squared(i) < pos.distance_squared(self.target) and ct.get_entity_type(ct.get_tile_building_id(ct.get_bridge_target(ct.get_tile_building_id(i)))) == EntityType.CORE):
                        self.target = i
                    elif ct.get_entity_type(ct.get_tile_building_id(i)) in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and ct.get_entity_type(ct.get_tile_building_id(i.add(ct.get_direction(ct.get_tile_building_id(i))))) == EntityType.CORE and i.distance_squared(self.enemy_core_position) <= 25:
                        self.target = i
                    elif ct.get_entity_type(ct.get_tile_building_id(i)) in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and (ct.get_tile_building_id(i.add(ct.get_direction(ct.get_tile_building_id(i)))) is None or (ct.get_entity_type(ct.get_tile_building_id(i.add(ct.get_direction(ct.get_tile_building_id(i))))) == EntityType.ROAD and ct.get_team(ct.get_tile_building_id(i.add(ct.get_direction(ct.get_tile_building_id(i))))) == ct.get_team(ct.get_tile_building_id(i)))) and i.add(ct.get_direction(ct.get_tile_building_id(i))).distance_squared(self.enemy_core_position) <= 25:
                        self.target = i.add(ct.get_direction(ct.get_tile_building_id(i)))



        self.bb_go_to(ct)
        if ct.can_destroy(self.target):
            ct.destroy(self.target)
        if ct.can_build_gunner(self.target, self.target.direction_to(self.enemy_core_position)):
            ct.build_gunner(self.target, self.target.direction_to(self.enemy_core_position))
            self.target = self.enemy_core_position
            self.last_positions = []
        if ct.get_position() == self.target:
            if ct.get_entity_type(ct.get_tile_building_id(ct.get_position())) in [EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and ct.can_fire(ct.get_position()):
                ct.fire(ct.get_position())
                self.target = self.enemy_core_position
                self.last_positions = []


    def gn_attack_enemy_core(self, ct):
        d = ct.get_direction()
        target = ct.get_position()
        for i in range(3):
            target = target.add(d)
            if ct.get_entity_type(ct.get_tile_builder_bot_id(target)) == EntityType.BUILDER_BOT and ct.get_team() == ct.get_team(ct.get_tile_building_id(target)):
                return
            if ct.can_fire(target):
                ct.fire(target)


    def run(self, ct: Controller) -> None:

        if ct.get_entity_type() == EntityType.CORE:
            close_vision_tiles = ct.get_nearby_tiles(5)
            vision_tiles = ct.get_nearby_tiles()
            core_position_x, core_position_y = ct.get_position()[0], ct.get_position()[1]
            possible_core_locations = [
                [ct.get_map_width() - 1 - core_position_x, core_position_y], # Horizontal Flip
                [core_position_x, ct.get_map_height() - 1- core_position_y], # Vertical Flip
                [ct.get_map_width() - 1 - core_position_x, ct.get_map_height() - 1 - core_position_y]] # Rotation

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

            for i in vision_tiles:
                if self.enemy_core_position == Position(1000,1000) and ct.get_entity_type(ct.get_tile_building_id(i)) == EntityType.MARKER and ct.get_team(
                        ct.get_tile_building_id(i)) == ct.get_team():
                    marker_value = ct.get_marker_value(ct.get_tile_building_id(i))
                    marker_value_id = (marker_value % (2 ** 28)) // (2 ** 12)
                    marker_status = marker_value // (2 ** 28)

                    if marker_status == 2:
                        # OPPONENT CORE LOCATION
                        target_x = (marker_value % (2 ** 12)) // (2 ** 6) - 1
                        target_y = marker_value % (2 ** 6)
                        self.enemy_core_position = Position(target_x, target_y)
                        ct.draw_indicator_line(ct.get_position(), self.enemy_core_position, 0, 0, 0)
                        return

                if self.enemy_core_position != Position(1000, 1000):
                    spawn_pos = ct.get_position().add(Direction.NORTH)
                    if ct.can_spawn(spawn_pos) and ct.get_global_resources()[0] > 800:
                        ct.spawn_builder(spawn_pos)
                        self.num_spawned += 1

                    # Place marker, so bot knows where to go
                    bot_id = ct.get_tile_builder_bot_id(spawn_pos)
                    if bot_id is None:
                        bot_id = 0
                    marker_status = 2
                    message = (
                            marker_status * (2 ** 28)
                            + bot_id * (2 ** 12)
                            + self.enemy_core_position.x * (2 ** 6)
                            + self.enemy_core_position.y)

                    if ct.can_place_marker(i):
                        ct.place_marker(i, message)


        elif ct.get_entity_type() == EntityType.BUILDER_BOT:


            if ct.get_global_resources()[0] < 100 and self.status != 4 and self.status != 5:
                return
            # Just spawned
            if self.status == 0:
                self.bb_initialise(ct)

            # Find enemy core
            elif self.status == 1:
                self.bb_find_enemy_core(ct)

            # Tell everyone about enemy core?
            elif self.status == 2:
                self.bb_spread_the_news_about_said_enemy_core(ct)

            #Look for ores
            elif self.status == 3:
                self.bb_find_ores(ct)

            elif self.status == 4:
                self.bb_build_conveyor_home(ct)

            elif self.status == 5:
                self.bb_go_to(ct, 4, True)

            elif self.status == 6:
                self.bb_go_to_enemy_core(ct)

            elif self.status == 7:
                self.bb_destroy_enemy_defences(ct)

            else:
                self.status = 3


        elif ct.get_entity_type() == EntityType.GUNNER:
            self.gn_attack_enemy_core(ct)
