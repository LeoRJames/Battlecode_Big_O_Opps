import random
from queue import PriorityQueue
from cambc import Controller, Direction, EntityType, Environment, Position
import random

# non-centre directions
DIRECTIONS = [d for d in Direction if d != Direction.CENTRE]
STRAIGHTS = [Direction.NORTH, Direction.SOUTH, Direction.WEST, Direction.EAST]
DIAGONALS = [Direction.NORTHWEST, Direction.NORTHEAST, Direction.SOUTHEAST, Direction.SOUTHWEST]

# STATUS CONSTANTS
INIT = 0
FIND_ENEMY_CORE = 1
REPORT_ENEMY_CORE_LOCATION = 2
GO_TO_ENEMY_CORE = 3
ATTACK_ENEMY_CORE = 4

EXPLORING = 5
MINING_TITANIUM = 6

DEFENCE = 7


class Player:
    def __init__(self):
        self.num_spawned = 0  # number of builder bots spawned so far (core)
        self.map = []
        self.core_pos = Position(1000, 1000)
        self.enemy_core_pos = Position(1000, 1000)  # Records a (central) core position
        self.pathfinder_start_pos = Position(1000, 1000)
        self.tit = []  # List of Positions of unmined titanium
        self.ax = []  # List of Positions of unmined axionite
        self.built_harvester = [False,  False]  # 0: True if built harvester and must connect; 1: Not False if built first conveyor and must move on to, otherwise stores position of that conveyor
        self.closest_conn_to_core = [Position(1000, 1000), False]  # True if do not adapt
        self.status = INIT  # Look above for constants
        self.target = Position(1000, 1000)  # Target position for exploring
        self.transport_resource_var = False
        self.move_dir = Direction.NORTH # Arbitrary
        self.explore_target = Position(1000,1000)


    def initialise_map(self, ct):  # Set up 2d array for each tile on map each storing a list of three info pieces (tile type, building, team)
        for j in range(ct.get_map_height()):
            row = []
            for i in range(ct.get_map_width()):
                row.append([0, 0, 0, [0], 0])
            self.map.append(row)

    def update_map(self, ct):
        for tile in ct.get_nearby_tiles():
            self.map[tile.y][tile.x][0] = ct.get_tile_env(tile)  # Sets environment type of tile (EMPTY, WALL, ORE_TITANIUM, ORE_AXIONITE)
            if ct.get_tile_building_id(tile) != None:
                self.map[tile.y][tile.x][1] = ct.get_entity_type(ct.get_tile_building_id(tile))  # Sets Entity_Type on tile (CORE, GUNNER, SENTINEL, BREACH, LAUNCHER, CONVEYOR, SPLITTER, ARMOURED_CONVEYOR, BRIDGE, HARVESTER, FOUNDRY, ROAD, BARRIER, MARKER, None)
                if ct.get_entity_type(ct.get_tile_building_id(tile)) in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.SPLITTER, EntityType.GUNNER, EntityType.BREACH, EntityType.SENTINEL]:
                    self.map[tile.y][tile.x][3][0] = ct.get_direction(ct.get_tile_building_id(tile))  # Sets direction of directional buildings
                elif ct.get_entity_type(ct.get_tile_building_id(tile)) == EntityType.BRIDGE:
                    self.map[tile.y][tile.x][3][0] = ct.get_bridge_target(ct.get_tile_building_id(tile))  # Sets target of bridge
                    if tile not in self.map[ct.get_bridge_target(ct.get_tile_building_id(tile)).y][ct.get_bridge_target(ct.get_tile_building_id(tile)).x][3]:  # Sets source of bridges ending at a tile
                        self.map[ct.get_bridge_target(ct.get_tile_building_id(tile)).y][ct.get_bridge_target(ct.get_tile_building_id(tile)).x][3].append(tile)
                else:
                    self.map[tile.y][tile.x][3][0] = None
            else:
                self.map[tile.y][tile.x][1] = None
            if ct.get_tile_builder_bot_id(tile) != None:
                self.map[tile.y][tile.x][4] = ct.get_entity_type(ct.get_tile_builder_bot_id(tile))  # Sets builder bot
            else:
                self.map[tile.y][tile.x][4] = None
            self.map[tile.y][tile.x][2] = ct.get_team(ct.get_tile_building_id(tile))  # Sets the team of the building
            harvester_count, connected = self.supply_connectivity(ct, start=tile)
            if self.enemy_core_pos == Position(1000, 1000) and ct.get_entity_type(ct.get_tile_building_id(tile)) == EntityType.CORE and ct.get_team(ct.get_tile_building_id(tile)) != ct.get_team():
                self.enemy_core_pos = ct.get_position(ct.get_tile_building_id(tile))  # Should be algorithm to get central position (use aarnavs search and symmetry stuff for this)
                # ct.draw_indicator_dot(tile, 0, 0, 255)

            elif ((not self.closest_conn_to_core[1] and ct.get_entity_type(ct.get_tile_building_id(tile)) in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.SPLITTER] and ct.get_team(ct.get_tile_building_id(tile)) == ct.get_team()) or connected[0] in [EntityType.CORE, True]) and ct.get_position().distance_squared(tile) < ct.get_position().distance_squared(self.closest_conn_to_core[0]):
                self.closest_conn_to_core[0] = tile
            if ct.get_tile_env(tile) == Environment.ORE_TITANIUM and ct.get_entity_type(ct.get_tile_building_id(tile)) != EntityType.HARVESTER and tile not in self.tit:
                self.tit.append(tile)
            elif tile in self.tit and (ct.get_entity_type(ct.get_tile_building_id(tile)) == EntityType.HARVESTER or ct.get_team(ct.get_tile_building_id(tile)) != ct.get_team()) and (self.status != MINING_TITANIUM or not self.built_harvester[0]):  # Remoce from list if another bot has built harveter on it
                self.tit.remove(tile)
            elif ct.get_tile_env(tile) == Environment.ORE_AXIONITE and ct.get_entity_type(ct.get_tile_building_id(tile)) != EntityType.HARVESTER and tile not in self.ax:
                self.ax.append(tile)
            elif tile in self.ax and ct.get_entity_type(ct.get_tile_building_id(tile)) == EntityType.HARVESTER:
                self.ax.remove(tile)

    def supply_connectivity(self, ct, start=None, check_back=True):  # ITERATIVE FOR EACH PATH
        if start is None:
            start = ct.get_position()
        # check_back: Flag to first check back to source, then check forward to end
        harvester_count = [0]  # Counts how many harvesters on path (max four, more than this causes backlog)
        connected = [False]  # False if not connected; True if unknown (not recorded on map); otherwise entity type of what it connects to
        next_tile = start
        visited = set()
        while check_back:  # Checks back to source
            check_back = False
        while not check_back:  # Checks forward to end

            if next_tile in visited:
                ckeck_back = True
                break
            visited.add(next_tile)

            if self.map[next_tile.y][next_tile.x][2] != ct.get_team():
                check_back = True
                break

            # Could also account for other check back routes (could cause endless route if not ensuring to not recheck routes)
            if self.map[next_tile.y][next_tile.x][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.CONVEYOR]:
                left_tile = next_tile.add(self.map[next_tile.y][next_tile.x][3][0].rotate_left().rotate_left())
                if self.map[left_tile.y][left_tile.x][1] is EntityType.HARVESTER:
                    harvester_count[0] += 1
                right_tile = next_tile.add(self.map[next_tile.y][next_tile.x][3][0].rotate_right().rotate_right())
                if self.map[right_tile.y][right_tile.x][1] is EntityType.HARVESTER:
                    harvester_count[0] += 1

            # Check for continuing or ending route
            if self.map[next_tile.y][next_tile.x][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.CONVEYOR]:  # Continue in direction of conveyor
                next_tile = next_tile.add(self.map[next_tile.y][next_tile.x][3][0])
            elif self.map[next_tile.y][next_tile.x][1] is EntityType.BRIDGE:  # Continue to end point of bridge
                next_tile = self.map[next_tile.y][next_tile.x][3][0]
            elif self.map[next_tile.y][next_tile.x][1] in [EntityType.CORE, EntityType.BREACH, EntityType.GUNNER, EntityType.SENTINEL]:  # Valid end point
                connected = [self.map[next_tile.y][next_tile.x][1]]
                check_back = True
            elif self.map[next_tile.y][next_tile.x][1] is EntityType.SPLITTER:  # Assume splitter direction is same direction of conveyor into it
                connected[0] = EntityType.SPLITTER
                left_splitter_harvester_count, left_splitter_connected = self.supply_connectivity(ct, next_tile.add(self.map[next_tile.y][next_tile.x][3].rotate_left().rotate_left()), check_back)
                for i in range(len(left_splitter_harvester_count)):
                    harvester_count.append(left_splitter_harvester_count[i])
                    connected.append(left_splitter_connected[i])
                forward_splitter_harvester_count, forward_splitter_connected = self.supply_connectivity(ct, next_tile.add(self.map[next_tile.y][next_tile.x][3]), check_back)
                for i in range(len(forward_splitter_harvester_count)):
                    harvester_count.append(forward_splitter_harvester_count[i])
                    connected.append(forward_splitter_connected[i])
                right_splitter_harvester_count, right_splitter_connected = self.supply_connectivity(ct, next_tile.add(self.map[next_tile.y][next_tile.x][3].rotate_right().rotate_right()), check_back)
                for i in range(len(right_splitter_harvester_count)):
                    harvester_count.append(right_splitter_harvester_count[i])
                    connected.append(right_splitter_connected[i])

            elif self.map[next_tile.y][next_tile.x][1] is EntityType.FOUNDRY:
                sum = [-1, 1]
                for num in sum:
                    pass
                pass  # Search surrounding four tile for conveyors or splitters not facing into foundry
            elif self.map[next_tile.y][next_tile.x][1] == 0:  # Unlnown on map
                connected = [True]
                check_back = True
            else:  # Not connected
                check_back = True

        return harvester_count, connected

    def heuristic_Chebyshev(self, next, target):  # Pass Positions
        return max(abs(next.x - target.x), abs(next.y - target.y))  # Chebyshev distance

    def heuristic_squaredEuclidean(self, next, target):
        return next.distance_squared(target)

    def pathfinder(self, ct, target, start=None, bridge=False, conv=False):  # Pass Position
        if start == None:
            start = ct.get_position()
        q = PriorityQueue()
        moveTile = 0  # Tie breakers for equal path lengths
        dist = 0
        q.put((0, moveTile, dist, start))  # Priority list to choose which tile to check next
        came_from = {}  # Dictionary of movement path
        cost_so_far = {}  # Dictionary of cost of movement
        came_from[start] = None
        cost_so_far[start] = 0
        best_tile = start
        if bridge:
            best_dist = self.heuristic_squaredEuclidean(start, target)
        else:
            best_dist = self.heuristic_Chebyshev(start, target)

        while not q.empty():
            current = q.get()  # Returns highest priority item on queue

            # Update best reachable tile
            if bridge:
                d = (self.heuristic_squaredEuclidean(current[3], target)) ** (1 / 2)
            else:
                d = self.heuristic_Chebyshev(current[3], target)  # abs(current[3].x - target.x) + abs(current[3].y - target.y)   # self.heuristic_Chebyshev(current[3], target)
            if d < best_dist:
                best_dist = d
                best_tile = current[3]

            if (current[3].x == target.x) and (current[3].y == target.y):
                break

            check_tiles = []

            # Adds all surrounding

            if bridge:  # If bridge consider all tiles a bridge can be built to
                for i in range(7):
                    for j in range(7):
                        if (not (i == 3 and j == 3)) and ((((i - 3) ** 2) + ((j - 3) ** 2)) <= 9) and current[3].x + (i - 3) >= 0 and current[3].x + (i - 3) < len(self.map[0]) and current[3].y + (j - 3) >= 0 and current[3].y + (j - 3) < len(self.map) and (
                        ((self.map[current[3].y + (j - 3)][current[3].x + (i - 3)][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.MARKER, EntityType.ROAD, EntityType.CORE] and self.map[current[3].y + (j - 3)][current[3].x + (i - 3)][2] == ct.get_team()) or (self.map[current[3].y + (j - 3)][current[3].x + (i - 3)][1] == None and self.map[current[3].y + (j - 3)][current[3].x + (i - 3)][0] not in [Environment.WALL]))):  # (not (self.map[current[3].y + (j-3)][current[3].x + (i-3)][4] in [EntityType.BUILDER_BOT] and ct.get_position().distance_squared(current[3]) <= 9)) and
                            check_tiles.append((current[3].x + (i - 3), current[3].y + (j - 3)))
                            # ct.draw_indicator_dot(Position(current[3].x + (i-3), current[3].y + (j-3)), 255, 0, 0)
            elif conv:  # If conveyor, consider only straight surrounding tiles
                for i in range(3):
                    for j in range(3):
                        if (not (abs(i - 1) == abs(j - 1))) and current[3].x + (i - 1) >= 0 and current[3].x + (i - 1) < len(self.map[0]) and current[3].y + (j - 1) >= 0 and current[3].y + (j - 1) < len(self.map) and (
                        ((self.map[current[3].y + (j - 1)][current[3].x + (i - 1)][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.MARKER, EntityType.ROAD, EntityType.CORE] and self.map[current[3].y + (j - 1)][current[3].x + (i - 1)][2] == ct.get_team()) or (self.map[current[3].y + (j - 1)][current[3].x + (i - 1)][1] == None and self.map[current[3].y + (j - 1)][current[3].x + (i - 1)][0] not in [Environment.WALL]))):  # (not (self.map[current[3].y + (j-1)][current[3].x + (i-1)][4] in [EntityType.BUILDER_BOT] and ct.get_position().distance_squared(current[3]) <= 1) and
                            check_tiles.append((current[3].x + (i - 1), current[3].y + (j - 1)))
                            # ct.draw_indicator_dot(Position(current[3].x + (i-1), current[3].y + (j-1)), 0, 255, 0)
            else:  # If normal one square movement, consider all surrounding tiles from current position
                for i in range(3):
                    for j in range(3):
                        if (not (i == 1 and j == 1)) and current[3].x + (i - 1) >= 0 and current[3].x + (i - 1) < len(self.map[0]) and current[3].y + (j - 1) >= 0 and current[3].y + (j - 1) < len(self.map) and ((not (self.map[current[3].y + (j - 1)][current[3].x + (i - 1)][4] in [EntityType.BUILDER_BOT] and ct.get_position().distance_squared(current[3]) <= 2)) and (
                                self.map[current[3].y + (j - 1)][current[3].x + (i - 1)][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.MARKER, EntityType.ROAD] or (self.map[current[3].y + (j - 1)][current[3].x + (i - 1)][1] == EntityType.CORE and self.map[current[3].y + (j - 1)][current[3].x + (i - 1)][2] == ct.get_team()) or (self.map[current[3].y + (j - 1)][current[3].x + (i - 1)][1] == None and self.map[current[3].y + (j - 1)][current[3].x + (i - 1)][0] != Environment.WALL))):
                            check_tiles.append((current[3].x + (i - 1), current[3].y + (j - 1)))
                            # ct.draw_indicator_dot(Position(current[3].x + (i-1), current[3].y + (j-1)), 0, 0, 255)
            for tile in check_tiles:
                moveTile = 0
                dist = 11
                tile_pos = Position(tile[0], tile[1])
                # if current[3].distance_squared(tile_pos) > 1:   # Prefer to move in a straight line rather than diagonally
                # counter += 1
                if self.map[tile[1]][tile[0]][1] == None:  # Prefer not to move over non-passable spaces (to save resources building extra paths)
                    moveTile += 1
                if bridge:
                    dist = dist - current[3].distance_squared(tile_pos)  # Prefer to build longest bridge
                else:
                    dist = current[3].distance_squared(tile_pos)  # Prefer to move in straight lines (as I think is more valuable for information)
                # ct.draw_indicator_dot(tile, 0, 0, 255)
                if bridge:
                    new_cost = cost_so_far[current[3]] + (tile_pos.distance_squared(current[3])) ** (1 / 2)
                    # new_cost = cost_so_far[current[3]] + tile_pos.distance_squared(current[3])  # For bridges, squared euclidean distance matters
                else:
                    new_cost = cost_so_far[current[3]] + 1  # Each move costs one move cooldown whether straight or diagonal for general movement
                if tile_pos not in cost_so_far or new_cost < cost_so_far[tile_pos]:  # Considers tile if not considered before or new path gets to it quicker
                    cost_so_far[tile_pos] = new_cost  # Updates smallest cost for location
                    if bridge:  # Calculates which tile to move to based off heuristic
                        priority = new_cost + self.heuristic_squaredEuclidean(tile_pos, target)
                    else:
                        priority = new_cost + self.heuristic_Chebyshev(tile_pos, target)
                    q.put((priority, moveTile, dist, tile_pos))
                    came_from[tile_pos] = current[3]  # Updates check locations
            # break
        return came_from, cost_so_far, best_tile

    def reconstruct_path(self, came_from, goal):
        if goal not in came_from:
            return []  # no path found
        path = []
        cur = goal
        while cur is not None:  # Works back from goal to start position (came_from[start] = None set in pathfinder)
            path.append(cur)
            cur = came_from[cur]
        path.reverse()
        return path

    def initialise_builder_bot(self, ct):
        self.initialise_map(ct)

        # Should Spawn on Core, so the if check should not be necessary
        if ct.get_entity_type(ct.get_tile_building_id(ct.get_position())) == EntityType.CORE and ct.get_team(ct.get_tile_building_id(ct.get_position())) == ct.get_team():
            self.core_pos = ct.get_position(ct.get_tile_building_id(ct.get_position()))
            self.closest_conn_to_core[0] = self.core_pos # Not sure why this is necessary

        # Read Marker for bot
        vision_tiles = ct.get_nearby_tiles()
        for i in vision_tiles:
            if ct.get_entity_type(ct.get_tile_building_id(i)) == EntityType.MARKER and ct.get_team(ct.get_tile_building_id(i)) == ct.get_team():
                marker_value = ct.get_marker_value(ct.get_tile_building_id(i))
                marker_value_id = (marker_value % (2 ** 28)) // (2 ** 12)
                marker_status = marker_value // (2 ** 28)

                if marker_value_id == ct.get_id():  # if marker is referring to this bot
                    if marker_status == 1: # Load Position to check for opponent core
                        target_x = (marker_value % (2 ** 12)) // (2 ** 6)
                        target_y = marker_value % (2 ** 6)
                        self.target = Position(target_x, target_y)
                        self.status = FIND_ENEMY_CORE
                        print(f"Looking for ENEMY CORE at {self.target}.")

                    elif marker_status == 2: # Load Position to go attack opponent core
                        target_x = (marker_value % (2 ** 12)) // (2 ** 6)
                        target_y = marker_value % (2 ** 6)
                        self.target = Position(target_x, target_y)
                        self.enemy_core_pos = self.target
                        self.status = GO_TO_ENEMY_CORE
                        print(f"Attacking ENEMY CORE at {self.target}.")

                    elif marker_status == 3:  # DEFEND CORE
                        self.status = DEFENCE
                        print(f"Defending.")

                    # Destroy marker
                    if ct.can_move(ct.get_position().direction_to(i)):
                        ct.move(ct.get_position().direction_to(i))
                    if ct.can_destroy(i):  # Destroy marker
                        ct.destroy(i)
                    else:
                        print(" - could not destroy marker :(")
                    return
        self.status = EXPLORING # BACKUP

    def explore(self, ct, target=None):
        if target == None or target == Position(1000, 1000) or ct.get_position() == target:
            target = self.target
        closest_tile = Position(1000, 1000)
        # ct.draw_indicator_line(ct.get_position(), target, 0, 255, 0)
        for tile in ct.get_nearby_tiles():  # Find closest passable tile to target in vision
            if ct.get_position() != tile and tile.distance_squared(target) < closest_tile.distance_squared(target) and ct.get_tile_builder_bot_id(tile) == None and self.map[tile.y][tile.x][0] != Environment.WALL and ((self.map[tile.y][tile.x][1] == EntityType.CORE and self.map[tile.y][tile.x][2] == ct.get_team()) or self.map[tile.y][tile.x][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.MARKER, EntityType.ROAD, None]):
                closest_tile = tile
        if closest_tile.distance_squared(self.target) < self.explore_target.distance_squared(self.target):
            self.explore_target = closest_tile
        if closest_tile != Position(1000, 1000):
            came_from_explore, cost_explore, best_tile_unused_1 = self.pathfinder(ct, closest_tile)
            path_explore = self.reconstruct_path(came_from_explore, closest_tile)
            ct.draw_indicator_line(ct.get_position(), closest_tile, 0, 0, 255)
            if len(path_explore) == 0:  # If there is no moveable path to target
                move_dir = ct.get_position().direction_to(closest_tile)
                for i in range(8):
                    move_dir = move_dir.rotate_left()  # Try to move anticlockwise around target
                    ct.draw_indicator_dot(ct.get_position().add(move_dir), 255, 0, 0)
                    if ct.can_build_road(ct.get_position().add(move_dir)):
                        ct.build_road(ct.get_position().add(move_dir))
                    if ct.can_move(move_dir):
                        ct.move(move_dir)
                        self.move_dir = move_dir
                        break
                if ct.get_move_cooldown() == 0:
                    ct.draw_indicator_line(ct.get_position(), ct.get_position().add(move_dir), 255, 0, 0)
                    ct.resign()
            else:
                for i in range(len(path_explore)):
                    ct.draw_indicator_dot(path_explore[i], 0, 255, 255)
                if ct.can_build_road(path_explore[1]):  # Fails if trying to build on to core
                    ct.build_road(path_explore[1])
                if ct.can_move(ct.get_position().direction_to(path_explore[1])):
                    ct.move(ct.get_position().direction_to(path_explore[1]))
                else:
                    if ct.get_tile_builder_bot_id(path_explore[1]) != None:
                        move_dir = ct.get_position().direction_to(path_explore[1])
                        for i in range(8):
                            move_dir = move_dir.rotate_left()  # Try to move anticlockwise around target
                            if ct.can_build_road(ct.get_position().add(move_dir)):
                                ct.build_road(ct.get_position().add(move_dir))
                            if ct.can_move(move_dir):
                                ct.move(move_dir)
                                self.move_dir = move_dir
                            else:
                                ct.draw_indicator_dot(ct.get_position().add(move_dir), 255, 0, 0)
                    else:
                        ct.draw_indicator_line(ct.get_position(), ct.get_position().add(ct.get_position().direction_to(path_explore[1])), 0, 255, 0)
                        # ct.resign()
                        # Ran out of money
        else:
            self.explore(ct, self.explore_target)
        if self.explore_target == self.target:
            self.explore_target = Position(1000, 1000)

    '''def transport_resource(self, ct, start=None, target=None):
        if start is None:   # start is location of ore 
            start = ct.get_position()
        if target is None:
            target = self.target
        if not self.transport_resource_var:     # Must move towards target and decide what to do
            if ct.get_position().distance_squared(start) <= 20:    # If in vision radius'''

    def harvest_ore(self, ct, ore):
        if not self.built_harvester[0]:  # If have not built harvester, must move towards it and build

            came_from_move_harvester, cost_move_harvester, best_tile_unused_2 = self.pathfinder(ct, ore)  # Movement path from current location to ore
            path_move_harvester = self.reconstruct_path(came_from_move_harvester, best_tile_unused_2)
            if len(path_move_harvester) == 0:  # If another bot builds a harvester on ore on same turn then raises eror (should change in map to remove ores from list if it contains a harvester)
                ct.draw_indicator_line(ct.get_position(), ore, 255, 0, 0)
                ct.resign()
            elif len(path_move_harvester) == 1:  # Happens to be on top of ore when switch to mine mode
                for d in DIRECTIONS:
                    if ct.can_build_road(ct.get_position().add(d)):
                        ct.build_road(ct.get_position().add(d))
                    if ct.can_move(d):
                        ct.move(d)

            came_from_first_conv, cost_first_conv, best_tile_first_conv = self.pathfinder(ct, ore, conv=True)  # Conveyor build path from current location to ore
            path_first_conv = self.reconstruct_path(came_from_first_conv, best_tile_first_conv)
            if len(path_first_conv) == 0:
                ct.draw_indicator_line(ct.get_position(), ore, 0, 255, 0)
                ct.resign()
            elif len(path_first_conv) == 1 and ct.get_position().distance_squared(ore) > 2:
                came_from_first_conv, cost_first_conv, best_tile_first_conv = self.pathfinder(ct, ore, bridge=True)  # Bridge build path from current location to ore    I THINK WILL CAUSE SOME ERRORS
                path_first_conv = self.reconstruct_path(came_from_first_conv, best_tile_first_conv)
            if len(path_first_conv) < 2:
                self.tit.remove(ore)  # Strange case so just give up to orevent error
                return
            if self.map[path_first_conv[-2].y][path_first_conv[-2].x][1] == EntityType.ROAD and self.map[path_first_conv[-2].y][path_first_conv[-2].x][2] == ct.get_team() and ct.can_destroy(path_first_conv[-2]) and ct.get_position().distance_squared(ore) <= 5:
                ct.destroy(path_first_conv[-2])
            elif self.map[path_first_conv[-2].y][path_first_conv[-2].x][2] != ct.get_team() and ct.get_position().distance_squared(ore) <= 5:
                self.tit.remove(ore)  # If other team have built a building where you want to build conveyor just forget about it
            elif ct.get_position() != path_first_conv[-2] and self.map[path_first_conv[-2].y][path_first_conv[-2].x][1] in [EntityType.CONVEYOR] and self.map[path_first_conv[-2].y][path_first_conv[-2].x][2] == ct.get_team() and ct.get_position().distance_squared(ore) <= 5:  # May be other builder bot sitting and waiting for money to build harvester    ct.get_entity_type(ct.get_tile_builder_bot_id(path_first_conv[-2])) == EntityType.BUILDER_BOT
                self.tit.remove(ore)
            if ct.can_build_conveyor(path_first_conv[-2], Direction.NORTH) and ct.get_position().distance_squared(ore) <= 5:  # Check if can build conveyor next to ore
                came_from_harvester_core, cost_from_harvester_core, best_tile_harvester_core = self.pathfinder(ct, self.core_pos, path_first_conv[-2], conv=True)
                came_from_harvester_conn, cost_from_harvester_conn, best_tile_harvester_conn = self.pathfinder(ct, self.closest_conn_to_core[0], path_first_conv[-2], conv=True)
                if cost_from_harvester_core[best_tile_harvester_core] <= cost_from_harvester_conn[best_tile_harvester_conn]:  # Must choose to build conveyors back to core or closest conveyor as stored
                    path_from_harvester = self.reconstruct_path(came_from_harvester_core, best_tile_harvester_core)
                    if len(path_from_harvester) <= 4 or len(path_from_harvester) > 5 + (path_first_conv[-2].distance_squared(best_tile_harvester_core)) ** (1 / 2):  # Uses bridge if cost of a bridge path around obstacle is less than conveyor path (based on scaling factor)
                        came_from_harvester, cost_from_harvester, best_tile_harvester_core = self.pathfinder(ct, self.core_pos, path_first_conv[-2], bridge=True)
                        path_from_harvester = self.reconstruct_path(came_from_harvester, best_tile_harvester_core)
                        if len(path_from_harvester) > 1:
                            came_from_harvester_conv_check, cost_from_harvester_conv_check, best_tile_harvester_core_conv_check = self.pathfinder(ct, path_from_harvester[1], path_first_conv[-2], conv=True)
                            if best_tile_harvester_core_conv_check == path_from_harvester[1] and cost_from_harvester_conv_check[best_tile_harvester_core_conv_check] == (abs(path_from_harvester[1].x - path_first_conv[-2].x) + abs(path_from_harvester[1].y - path_first_conv[-2].y)):  # If can build conveyors between these points directly
                                came_from_harvester = came_from_harvester_conv_check
                                cost_from_harvester = cost_from_harvester_conv_check
                                path_from_harvester = self.reconstruct_path(came_from_harvester, best_tile_harvester_core_conv_check)
                    else:
                        came_from_harvester = came_from_harvester_core
                        cost_from_harvester = cost_from_harvester_core
                else:
                    path_from_harvester = self.reconstruct_path(came_from_harvester_conn, best_tile_harvester_conn)
                    if len(path_from_harvester) <= 4 or len(path_from_harvester) > 5 + (path_first_conv[-2].distance_squared(best_tile_harvester_conn)) ** (1 / 2):
                        came_from_harvester, cost_from_harvester, best_tile_harvester_conn = self.pathfinder(ct, self.closest_conn_to_core[0], path_first_conv[-2], bridge=True)
                        path_from_harvester = self.reconstruct_path(came_from_harvester, best_tile_harvester_conn)
                        if len(path_from_harvester) > 1:
                            came_from_harvester_conv_check, cost_from_harvester_conv_check, best_tile_harvester_conn_conv_check = self.pathfinder(ct, path_from_harvester[1], path_first_conv[-2], conv=True)
                            if best_tile_harvester_conn_conv_check == path_from_harvester[1] and cost_from_harvester_conv_check[best_tile_harvester_conn_conv_check] == (abs(path_from_harvester[1].x - path_first_conv[-2].x) + abs(path_from_harvester[1].y - path_first_conv[-2].y)):  # If can build conveyors between these points directly
                                came_from_harvester = came_from_harvester_conv_check
                                cost_from_harvester = cost_from_harvester_conv_check
                                path_from_harvester = self.reconstruct_path(came_from_harvester, best_tile_harvester_conn_conv_check)
                    else:
                        came_from_harvester = came_from_harvester_conn
                        cost_from_harvester = cost_from_harvester_conn

                if len(path_from_harvester) == 0:
                    ct.draw_indicator_line(self.core_pos, path_first_conv[-2], 255, 255, 0)
                    ct.resign()
                elif len(path_from_harvester) == 1:
                    ct.draw_indicator_dot(path_from_harvester[0], 0, 0, 0)
                    ct.resign()
                else:
                    if path_from_harvester[0].distance_squared(path_from_harvester[1]) == 1 and ct.can_build_conveyor(path_from_harvester[0], path_from_harvester[0].direction_to(path_from_harvester[1])):
                        self.closest_conn_to_core[1] = True
                        ct.build_conveyor(path_from_harvester[0], path_from_harvester[0].direction_to(path_from_harvester[1]))
                        self.built_harvester[1] = path_from_harvester[0]
                        ct.draw_indicator_line(path_from_harvester[0], path_from_harvester[1], 255, 0, 255)
                    elif ct.can_build_bridge(path_from_harvester[0], path_from_harvester[1]):  # MAY CAUSE ERROR
                        self.closest_conn_to_core[1] = True
                        ct.build_bridge(path_from_harvester[0], path_from_harvester[1])
                        self.built_harvester[1] = path_from_harvester[1]
                        ct.draw_indicator_line(path_from_harvester[0], path_from_harvester[1], 255, 255, 255)
                    elif self.map[path_from_harvester[0].y][path_from_harvester[0].x][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.SPLITTER] and self.map[path_from_harvester[0].y][path_from_harvester[0].x][2] == ct.get_team():  # If already a friendly transport mechanism in space then move on
                        self.closest_conn_to_core[1] = True
                    else:
                        ct.draw_indicator_dot(path_from_harvester[0], 0, 0, 0)
                        ct.draw_indicator_line(path_from_harvester[0], path_from_harvester[1], 255, 0, 255)
                        # ct.resign()    # Probbaly ran out of money
                    if ct.can_move(ct.get_position().direction_to(path_from_harvester[0])):  # Moves on to built conveyor or bridge
                        ct.move(ct.get_position().direction_to(path_from_harvester[0]))
                    else:  # Ran out of money
                        ct.draw_indicator_line(ct.get_position(), ct.get_position().add(ct.get_position().direction_to(path_from_harvester[0])), 0, 0, 255)
                        # ct.resign()
            elif self.map[path_first_conv[-1].y][path_first_conv[-1].x][1] == EntityType.ROAD and self.map[path_first_conv[-1].y][path_first_conv[-1].x][2] == ct.get_team() and ct.can_destroy(path_first_conv[-1]) and ct.get_position().distance_squared(ore) <= 1:
                ct.destroy(path_first_conv[-1])  # Destroy road built over ore
            elif ct.can_build_harvester(ore) and ore in self.tit and self.built_harvester[1] != False:  # If can build harvester, build it
                ct.draw_indicator_dot(path_first_conv[-2], 0, 0, 255)
                self.built_harvester[0] = True  # Flag harvester is built so must now build path back
                self.closest_conn_to_core[1] = True  # Ensures this happens in case that does not need to build any conveyors tp connect harvester
                ct.build_harvester(ore)
                if self.map[ct.get_position().y][ct.get_position().x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and self.map[ct.get_position().y][ct.get_position().x][2] == ct.get_team():
                    self.built_harvester[1] = False  # Reset if built conveyor next to ore
            elif ct.get_position().distance_squared(ore) <= 2:  # If ran out of money to build harvester
                pass

            else:  # Move towards ore if not close enough to do anything else
                came_from_to_ore, cost_to_ore, best_tile_unused_3 = self.pathfinder(ct, ore)
                path_to_ore = self.reconstruct_path(came_from_to_ore, best_tile_unused_3)
                if len(path_to_ore) == 0:
                    ct.draw_indicator_line(ct.get_position(), ore, 0, 255, 255)
                    ct.resign()
                else:
                    if ct.can_build_road(path_to_ore[1]):
                        ct.build_road(path_to_ore[1])
                    if ct.can_move(ct.get_position().direction_to(path_to_ore[1])):
                        ct.move(ct.get_position().direction_to(path_to_ore[1]))
                    else:
                        self.target = ct.get_position().add(ct.get_position().direction_to(path_to_ore[1]))
                        ct.draw_indicator_line(ct.get_position(), path_to_ore[1], 0, 0, 0)
        else:
            if self.built_harvester[1] != False:  # If bridge built
                if ct.get_position().distance_squared(self.built_harvester[1]) <= 2:  # If directly next to position it needs to move to
                    came_from_built_harvester_core, cost_from_built_harvester_core, best_tile_built_harvester_core = self.pathfinder(ct, self.core_pos, self.built_harvester[1], conv=True)
                    came_from_built_harvester_conn, cost_from_built_harvester_conn, best_tile_built_harvester_conn = self.pathfinder(ct, self.closest_conn_to_core[0], self.built_harvester[1], conv=True)
                    if cost_from_built_harvester_core[best_tile_built_harvester_core] <= cost_from_built_harvester_conn[best_tile_built_harvester_conn]:  # Choose closest between core and stored closest cnveyor
                        path_from_built_harvester = self.reconstruct_path(came_from_built_harvester_core, best_tile_built_harvester_core)
                        if len(path_from_built_harvester) <= 4 or len(path_from_built_harvester) > 5 + (self.built_harvester[1].distance_squared(best_tile_built_harvester_core)) ** (1 / 2):  # Uses bridge if cost of a bridge path around obstacle is less than conveyor path (based on scaling factor):
                            came_from_built_harvester, cost_from_built_harvester, best_tile_built_harvester_core = self.pathfinder(ct, self.core_pos, self.built_harvester[1], bridge=True)
                            path_from_built_harvester = self.reconstruct_path(came_from_built_harvester, best_tile_built_harvester_core)
                            if len(path_from_built_harvester) > 1:
                                came_from_built_harvester_conv_check, cost_from_built_harvester_conv_check, best_tile_built_harvester_core_conv_check = self.pathfinder(ct, path_from_built_harvester[1], self.built_harvester[1], conv=True)
                                if best_tile_built_harvester_core_conv_check == path_from_built_harvester[1] and cost_from_built_harvester_conv_check[best_tile_built_harvester_core_conv_check] == (abs(path_from_built_harvester[1].x - self.built_harvester[1].x) + abs(path_from_built_harvester[1].y - self.built_harvester[1].y)):  # If can build conveyors between these points directly
                                    came_from_built_harvester = came_from_built_harvester_conv_check
                                    cost_from_built_harvester = cost_from_built_harvester_conv_check
                                    path_from_built_harvester = self.reconstruct_path(came_from_built_harvester, best_tile_built_harvester_core_conv_check)
                        else:
                            came_from_built_harvester = came_from_built_harvester_core  # Not updating target of path here (if not conveyor path exists)
                            cost_from_built_harvester = cost_from_built_harvester_core

                    else:
                        path_from_built_harvester = self.reconstruct_path(came_from_built_harvester_conn, best_tile_built_harvester_conn)
                        if len(path_from_built_harvester) <= 4 or len(path_from_built_harvester) > 5 + (self.built_harvester[1].distance_squared(best_tile_built_harvester_conn)) ** (1 / 2):
                            came_from_built_harvester, cost_from_built_harvester, best_tile_built_harvester_conn = self.pathfinder(ct, self.closest_conn_to_core[0], self.built_harvester[1], bridge=True)
                            path_from_built_harvester = self.reconstruct_path(came_from_built_harvester, best_tile_built_harvester_conn)
                            for i in range(len(path_from_built_harvester)):
                                ct.draw_indicator_dot(path_from_built_harvester[i], 255, 255, 0)
                            if len(path_from_built_harvester) > 1:
                                came_from_built_harvester_conv_check, cost_from_built_harvester_conv_check, best_tile_built_harvester_conn_conv_check = self.pathfinder(ct, path_from_built_harvester[1], self.built_harvester[1], conv=True)
                                if best_tile_built_harvester_conn_conv_check == path_from_built_harvester[1] and cost_from_built_harvester_conv_check[best_tile_built_harvester_conn_conv_check] == (abs(path_from_built_harvester[1].x - self.built_harvester[1].x) + abs(path_from_built_harvester[1].y - self.built_harvester[1].y)):  # If can build conveyors between these points directly
                                    came_from_built_harvester = came_from_built_harvester_conv_check
                                    cost_from_built_harvester = cost_from_built_harvester_conv_check
                                    path_from_built_harvester = self.reconstruct_path(came_from_built_harvester, best_tile_built_harvester_conn_conv_check)
                        else:
                            came_from_built_harvester = came_from_built_harvester_conn
                            cost_from_built_harvester = cost_from_built_harvester_conn
                    self.built_harvester[1] = False
                    if len(path_from_built_harvester) == 0:
                        ct.draw_indicator_line(ct.get_position(), self.core_pos, 255, 255, 255)
                        ct.resign()
                    elif len(path_from_built_harvester) == 1 or (self.map[path_from_built_harvester[0].y][path_from_built_harvester[0].x][1] in [EntityType.CORE, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.SPLITTER] and self.map[path_from_built_harvester[0].y][path_from_built_harvester[0].x][2] == ct.get_team()):  # Check for being at end of path
                        self.built_harvester[0] = False
                        self.closest_conn_to_core[1] = False
                        if len(path_from_built_harvester) > 1:
                            ct.draw_indicator_line(path_from_built_harvester[0], path_from_built_harvester[1], 255, 0, 255)
                        if len(path_from_built_harvester) > 0:
                            ct.draw_indicator_line(path_from_built_harvester[0], self.core_pos, 0, 255, 255)
                            ct.draw_indicator_line(path_from_built_harvester[0], self.closest_conn_to_core[0], 0, 255, 255)
                        self.tit.remove(ore)  # Remove ore from build queue
                    else:
                        if self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0])).x][1] == EntityType.ROAD and self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0])).x][2] == ct.get_team() and ct.can_destroy(ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0]))):  # If a friendly road is on path, destroy it
                            ct.destroy(ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0])))
                        if path_from_built_harvester[0].distance_squared(path_from_built_harvester[1]) == 1 and ct.can_build_conveyor(path_from_built_harvester[0], path_from_built_harvester[0].direction_to(path_from_built_harvester[1])):  # Build conveyor and move on to it
                            ct.build_conveyor(path_from_built_harvester[0], path_from_built_harvester[0].direction_to(path_from_built_harvester[1]))
                            if ct.can_move(ct.get_position().direction_to(path_from_built_harvester[0])):
                                ct.move(ct.get_position().direction_to(path_from_built_harvester[0]))
                            else:
                                self.target = ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0]))
                                ct.draw_indicator_line(ct.get_position(), path_from_built_harvester[0], 0, 255, 255)
                        elif ct.can_build_bridge(path_from_built_harvester[0], path_from_built_harvester[1]):
                            ct.build_bridge(path_from_built_harvester[0], path_from_built_harvester[1])
                            self.built_harvester[1] = path_from_built_harvester[1]
                        else:
                            # if ct.get_conveyor_cost()[0] < ct.get
                            ct.draw_indicator_dot(path_from_built_harvester[0], 255, 0, 255)
                            ct.draw_indicator_line(path_from_built_harvester[0], path_from_built_harvester[1], 255, 255, 255)
                            # ct.resign()    # So that does not fail if not enough resources
                            if path_from_built_harvester[0].distance_squared(path_from_built_harvester[1]) > 1:
                                self.built_harvester[1] = path_from_built_harvester[0]

                else:
                    self.explore(ct, self.built_harvester[1])
            else:  # Connect harvester with conveyors
                came_from_built_harvester_core, cost_from_built_harvester_core, best_tile_built_harvester_core = self.pathfinder(ct, self.core_pos, conv=True)
                # if cost_from_built_harvester_core[best_tile_built_harvester_core] > 0 + ct.get_position().distance_squared(best_tile_built_harvester_core):   # Uses bridge if cost of a bridge path around obstacle is less than conveyor path (based on scaling factor)
                #    came_from_built_harvester_core, cost_from_built_harvester_core, best_tile_built_harvester_core = self.pathfinder(ct, self.core_pos, bridge=True)
                came_from_built_harvester_conn, cost_from_built_harvester_conn, best_tile_built_harvester_conn = self.pathfinder(ct, self.closest_conn_to_core[0], conv=True)
                # if cost_from_built_harvester_conn[best_tile_built_harvester_conn] > 0 + ct.get_position().distance_squared(best_tile_built_harvester_conn):   # Uses bridge if cost of a bridge path around obstacle is less than conveyor path (based on scaling factor)
                #    came_from_built_harvester_conn, cost_from_built_harvester_conn, best_tile_built_harvester_conn = self.pathfinder(ct, self.closest_conn_to_core[0], bridge=True)
                if cost_from_built_harvester_core[best_tile_built_harvester_core] <= cost_from_built_harvester_conn[best_tile_built_harvester_conn]:  # Choose closest between core and stored closest cnveyor
                    path_from_built_harvester = self.reconstruct_path(came_from_built_harvester_core, best_tile_built_harvester_core)  # BOTTOM LEFT FAILS BECAUSE THE OPTIMAL CONVEYOR POSITION CHANGES TO RIGHT NEXT TO ITSELF WHICH MEANS IT DOESNT CONSIDER CONVEYOR PATH SO ASSUMES IT HAS COMPLETE ROUTE AS CONSTRUCTS ROUTE OF LENGTH ONE
                    if len(path_from_built_harvester) <= 4 or len(path_from_built_harvester) > 5 + (ct.get_position().distance_squared(best_tile_built_harvester_core)) ** (1 / 2) or (len(path_from_built_harvester) == 2 and path_from_built_harvester[1] not in [EntityType.ARMOURED_CONVEYOR, EntityType.CONVEYOR, EntityType.CORE, EntityType.BRIDGE, EntityType.SPLITTER]) or (len(path_from_built_harvester) == 1 and best_tile_built_harvester_core != self.core_pos):  # NOT PERFECT METRIC (COULD CONVERT THIS BACK TO HOW IT WAS BEFORE)
                        if ct.get_tile_building_id(ct.get_position()) != None and ct.get_entity_type(ct.get_tile_building_id(ct.get_position().add(ct.get_direction(ct.get_tile_building_id(ct.get_position()))))) != EntityType.HARVESTER:
                            came_from_built_harvester, cost_from_built_harvester, best_tile_built_harvester_core = self.pathfinder(ct, self.core_pos, ct.get_position().add(ct.get_direction(ct.get_tile_building_id(ct.get_position()))), bridge=True)
                        else:
                            came_from_built_harvester, cost_from_built_harvester, best_tile_built_harvester_core = self.pathfinder(ct, self.core_pos, bridge=True)
                        path_from_built_harvester = self.reconstruct_path(came_from_built_harvester, best_tile_built_harvester_core)
                        ct.draw_indicator_line(ct.get_position(), best_tile_built_harvester_core, 255, 0, 255)
                        for i in range(len(path_from_built_harvester) - 1):
                            ct.draw_indicator_line(path_from_built_harvester[i], path_from_built_harvester[i + 1], 0, 255, 255)
                        if len(path_from_built_harvester) > 1:
                            came_from_built_harvester_conv_check, cost_from_built_harvester_conv_check, best_tile_built_harvester_core_conv_check = self.pathfinder(ct, path_from_built_harvester[1], conv=True)
                            if best_tile_built_harvester_core_conv_check == path_from_built_harvester[1] and cost_from_built_harvester_conv_check[best_tile_built_harvester_core_conv_check] == (abs(path_from_built_harvester[1].x - ct.get_position().x) + abs(path_from_built_harvester[1].y - ct.get_position().y)):  # If can build conveyors between these points directly
                                came_from_built_harvester = came_from_built_harvester_conv_check
                                cost_from_built_harvester = cost_from_built_harvester_conv_check
                                path_from_built_harvester = self.reconstruct_path(came_from_built_harvester, best_tile_built_harvester_core_conv_check)
                            ct.draw_indicator_line(ct.get_position(), ct.get_position().add(Direction.WEST), 0, 255, 0)
                        # TOP ONE FAILS BECAUSE BRIDGE PATH GOES FROM TILE NEXT TO CONVEYOR FIRST TO OWN POSITION AND THEN OVER WALL SO TRIES TO RECONSTRUCT PATH FROM ITSELF TO ITSELF AND SO ASSUMES PATH IS COMPLETE BECAUSE IT IS OF LENGTH ONE. CHANGE SUCH THAT IT CHECKS IF PATH_FROM_BUILT_HARVESTER[1] IS OWN POSITION SO THEN TRIES TO BUILD CONVEYOR PATH TO 2. ALSO ADD CHECK THAT IF WANT TO BUILD BRIDGE AT OWN POSITION AND ON A CONVEYOR THEN DESTROY CONVEYOR
                    else:
                        came_from_built_harvester = came_from_built_harvester_core  # Not updating target of path here (if not conveyor path exists)
                        cost_from_built_harvester = cost_from_built_harvester_core
                    for i in range(len(path_from_built_harvester)):
                        ct.draw_indicator_dot(path_from_built_harvester[i], 255, 255, 0)

                else:
                    path_from_built_harvester = self.reconstruct_path(came_from_built_harvester_conn, best_tile_built_harvester_conn)
                    if len(path_from_built_harvester) <= 4 or len(path_from_built_harvester) > 5 + ct.get_position().distance_squared(best_tile_built_harvester_conn) or (len(path_from_built_harvester) == 2 and path_from_built_harvester[1] not in [EntityType.ARMOURED_CONVEYOR, EntityType.CONVEYOR, EntityType.CORE, EntityType.BRIDGE, EntityType.SPLITTER]) or (len(path_from_built_harvester) == 1 and best_tile_built_harvester_conn != self.closest_conn_to_core[0]):
                        if ct.get_tile_building_id(ct.get_position()) != None and ct.get_entity_type(ct.get_tile_building_id(ct.get_position().add(ct.get_direction(ct.get_tile_building_id(ct.get_position()))))) != EntityType.HARVESTER:
                            came_from_built_harvester, cost_from_built_harvester, best_tile_built_harvester_conn = self.pathfinder(ct, self.closest_conn_to_core[0], ct.get_position().add(ct.get_direction(ct.get_tile_building_id(ct.get_position()))), bridge=True)
                            ct.draw_indicator_line(self.closest_conn_to_core[0], ct.get_position().add(ct.get_direction(ct.get_tile_building_id(ct.get_position()))), 255, 0, 255)
                        else:
                            came_from_built_harvester, cost_from_built_harvester, best_tile_built_harvester_conn = self.pathfinder(ct, self.closest_conn_to_core[0], bridge=True)
                        path_from_built_harvester = self.reconstruct_path(came_from_built_harvester, best_tile_built_harvester_conn)
                        if len(path_from_built_harvester) > 1 and ct.get_position() != path_from_built_harvester[1]:
                            ct.draw_indicator_line(path_from_built_harvester[0], path_from_built_harvester[1], 0, 255, 255)
                            ct.draw_indicator_dot(path_from_built_harvester[0], 0, 0, 0)
                            ct.draw_indicator_dot(path_from_built_harvester[1], 255, 0, 0)
                            came_from_built_harvester_conv_check, cost_from_built_harvester_conv_check, best_tile_built_harvester_conn_conv_check = self.pathfinder(ct, path_from_built_harvester[1], conv=True)
                            if best_tile_built_harvester_conn_conv_check == path_from_built_harvester[1] and cost_from_built_harvester_conv_check[best_tile_built_harvester_conn_conv_check] == (abs(path_from_built_harvester[1].x - ct.get_position().x) + abs(path_from_built_harvester[1].y - ct.get_position().y)):  # If can build conveyors between these points directly
                                came_from_built_harvester = came_from_built_harvester_conv_check
                                cost_from_built_harvester = cost_from_built_harvester_conv_check
                                path_from_built_harvester = self.reconstruct_path(came_from_built_harvester, best_tile_built_harvester_conn_conv_check)
                    else:
                        came_from_built_harvester = came_from_built_harvester_conn
                        cost_from_built_harvester = cost_from_built_harvester_conn
                if len(path_from_built_harvester) == 0:
                    ct.draw_indicator_line(ct.get_position(), self.core_pos, 255, 255, 255)
                    ct.resign()
                elif len(path_from_built_harvester) == 1 or (ct.get_position().distance_squared(path_from_built_harvester[1]) == 1 and self.map[path_from_built_harvester[1].y][path_from_built_harvester[1].x][1] in [EntityType.CORE, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.SPLITTER] and self.map[path_from_built_harvester[1].y][path_from_built_harvester[1].x][2] == ct.get_team() and not (
                        self.map[path_from_built_harvester[1].y][path_from_built_harvester[1].x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and self.map[path_from_built_harvester[1].y][path_from_built_harvester[1].x][3][0] == ct.get_position().direction_to(path_from_built_harvester[1]).opposite())) or (
                (ct.get_position().distance_squared(path_from_built_harvester[0]) == 1 and self.map[path_from_built_harvester[0].y][path_from_built_harvester[0].x][1] in [EntityType.CORE, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.SPLITTER] and self.map[path_from_built_harvester[0].y][path_from_built_harvester[0].x][2] == ct.get_team())):  # Check for being at end of path MAY NEED To ADD TO FOR BRIDGE STUFF
                    self.built_harvester[0] = False
                    self.closest_conn_to_core[1] = False
                    ct.draw_indicator_dot(ct.get_position().add(Direction.NORTH), 255, 255, 255)
                    if len(path_from_built_harvester) > 1:
                        ct.draw_indicator_dot(path_from_built_harvester[1], 0, 0, 0)
                    elif len(path_from_built_harvester) > 0:
                        ct.draw_indicator_line(path_from_built_harvester[0], self.core_pos, 0, 255, 0)
                    self.tit.remove(ore)  # Remove ore from build queue
                else:
                    if ct.get_position().distance_squared(path_from_built_harvester[1]) == 1 and (self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).x][1] == EntityType.ROAD and self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).x][2] == ct.get_team() or
                                                                                                  self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).x][2] == ct.get_team() and
                                                                                                  self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).x][3] == ct.get_position().direction_to(path_from_built_harvester[1]).opposite()) and ct.can_destroy(ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1]))):  # If a friendly road is on path, destroy it
                        ct.destroy(ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])))
                    elif ct.get_position().distance_squared(path_from_built_harvester[0]) == 1 and self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0])).x][1] == EntityType.ROAD and self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0])).x][2] == ct.get_team() and ct.can_destroy(
                            ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0]))):  # If a friendly road is on path, destroy it
                        ct.destroy(ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0])))
                    elif self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).x][1] == EntityType.HARVESTER and self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).x][2] == ct.get_team() and path_from_built_harvester[0] == ct.get_position() and self.map[ct.get_position().y][ct.get_position().x][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.CONVEYOR,
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              EntityType.ROAD, EntityType.MARKER] and \
                            self.map[ct.get_position().y][ct.get_position().x][2] == ct.get_team() and ct.can_destroy(ct.get_position()):
                        ct.destroy(ct.get_position())
                    if ct.get_tile_building_id(ct.get_position()) != None and ((ct.get_position().distance_squared(path_from_built_harvester[1]) == 1 and ct.get_direction(ct.get_tile_building_id(ct.get_position())) != ct.get_position().direction_to(path_from_built_harvester[1])) or (ct.get_position().distance_squared(path_from_built_harvester[0]) == 1 and ct.get_direction(ct.get_tile_building_id(ct.get_position())) != ct.get_position().direction_to(path_from_built_harvester[0])) or (ct.get_position() == path_from_built_harvester[0] and ct.get_position().distance_squared(path_from_built_harvester[1]) > 1)) and \
                            self.map[ct.get_position().y][ct.get_position().x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and self.map[ct.get_position().y][ct.get_position().x][2] == ct.get_team() and ct.can_destroy(ct.get_position()):  # If finds new path that is more optimal but current conveyor faces in the wrong direction must rebuild
                        ct.destroy(ct.get_position())
                    if len(path_from_built_harvester) > 2 and ct.can_destroy(path_from_built_harvester[1]) and ct.get_entity_type(ct.get_tile_building_id(path_from_built_harvester[1])) in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and ((path_from_built_harvester[1].distance_squared(path_from_built_harvester[2]) == 1 and ct.get_direction(ct.get_tile_building_id(path_from_built_harvester[1])) != path_from_built_harvester[1].direction_to(path_from_built_harvester[
                                                                                                                                                                                                                                                                                                                                                                                                                                                                    2]))):  # or (path_from_built_harvester[0].distance_squared(path_from_built_harvester[1]) == 1 and ct.get_direction(ct.get_tile_building_id(path_from_built_harvester[0])) != path_from_built_harvester[0].direction_to(path_from_built_harvester[1]))): #or (path_from_built_harvester[0] == path_from_built_harvester[1] and ct.get_position().distance_squared(path_from_built_harvester[1]) > 1)) and self.map[ct.get_position().y][ct.get_position().x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and self.map[ct.get_position().y][ct.get_position().x][2] == ct.get_team() and ct.can_destroy(ct.get_position()):      # If finds new path that is more optimal but current conveyor faces in the wrong direction must rebuild
                        ct.destroy(path_from_built_harvester[1])
                    if ct.get_position().distance_squared(path_from_built_harvester[1]) == 1 and ct.can_build_conveyor(ct.get_position(), ct.get_position().direction_to(path_from_built_harvester[1])):
                        ct.build_conveyor(ct.get_position(), ct.get_position().direction_to(path_from_built_harvester[1]))
                    elif ct.can_build_harvester(path_from_built_harvester[1]):
                        ct.build_harvester(path_from_built_harvester[1])
                        if path_from_built_harvester[1] in self.tit:
                            self.tit.remove(path_from_built_harvester[1])  # Can remove this as still connecting other ore
                        elif path_from_built_harvester[1] in self.ax:
                            self.ax.remove(path_from_built_harvester[1])
                    elif len(path_from_built_harvester) > 2 and path_from_built_harvester[1].distance_squared(path_from_built_harvester[2]) == 1 and ct.can_build_conveyor(path_from_built_harvester[1], path_from_built_harvester[1].direction_to(path_from_built_harvester[2])) and self.map[path_from_built_harvester[1].y][path_from_built_harvester[1].x][0] not in [Environment.ORE_AXIONITE, Environment.ORE_TITANIUM]:  # Build conveyor and move on to it
                        ct.build_conveyor(path_from_built_harvester[1], path_from_built_harvester[1].direction_to(path_from_built_harvester[2]))
                        if ct.can_move(ct.get_position().direction_to(path_from_built_harvester[1])):
                            ct.move(ct.get_position().direction_to(path_from_built_harvester[1]))
                        else:
                            self.target = ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1]))
                            ct.draw_indicator_line(ct.get_position(), path_from_built_harvester[1], 0, 255, 255)
                    elif ct.can_build_bridge(path_from_built_harvester[0], path_from_built_harvester[1]):
                        ct.build_bridge(path_from_built_harvester[0], path_from_built_harvester[1])
                        self.built_harvester[1] = path_from_built_harvester[1]
                    else:
                        ct.draw_indicator_dot(path_from_built_harvester[0], 255, 0, 255)
                        if len(path_from_built_harvester) > 1:
                            ct.draw_indicator_line(path_from_built_harvester[0], path_from_built_harvester[0].add(path_from_built_harvester[0].direction_to(path_from_built_harvester[1])), 255, 255, 255)
                        if len(path_from_built_harvester) > 2:
                            ct.draw_indicator_line(path_from_built_harvester[1], path_from_built_harvester[1].add(path_from_built_harvester[1].direction_to(path_from_built_harvester[2])), 255, 255, 255)
                        # if path_from_built_harvester[0].distance_squared(path_from_built_harvester[1]) > 1:
                        # self.built_harvester[1] = path_from_built_harvester[0]
                        # ct.resign()

    def find_enemy_core(self, ct):
        self.explore(ct)

        if self.enemy_core_pos != Position(1000, 1000):
            print(f"ENEMY CORE found at {self.enemy_core_pos}")
            self.status = REPORT_ENEMY_CORE_LOCATION
            self.enemy_core_pos = self.target
            self.target = self.core_pos
            return

        if ct.is_in_vision(self.target): # Core not at location
            print(f"No ENEMY CORE found at {self.enemy_core_pos}")
            self.status = EXPLORING


    def report_enemy_core_location(self,ct):
        self.explore(ct)

        pos = ct.get_position()
        enemy_core_x, enemy_core_y = self.enemy_core_pos.x, self.enemy_core_pos.y
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
                    self.status = EXPLORING
                    print("Reported Enemy Core Location back to Base")
                    self.target = Position(0,0)
                    return
            if ct.can_place_marker(pos.add(i)):
                ct.place_marker(pos.add(i), message)
                return


    def attack_enemy_core(self, ct):
        vision_tiles = ct.get_nearby_tiles()
        pos = ct.get_position()

        if self.target == self.enemy_core_pos:
            for i in vision_tiles:
                if ct.get_entity_type(ct.get_tile_building_id(i)) in [EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR]:
                    if ct.get_entity_type(ct.get_tile_building_id(i)) == EntityType.BRIDGE and ( ct.is_in_vision(ct.get_bridge_target(ct.get_tile_building_id(i))) and (ct.is_tile_empty(ct.get_bridge_target(ct.get_tile_building_id(i)) or ct.get_entity_type(ct.get_tile_building_id(ct.get_bridge_target(ct.get_tile_building_id(i))))) == EntityType.ROAD) and ct.get_bridge_target( ct.get_tile_building_id(i)).distance_squared(self.enemy_core_pos) <= 16):
                        self.target = ct.get_bridge_target(ct.get_tile_building_id(i))
                    elif ct.get_entity_type(ct.get_tile_building_id(i)) == EntityType.BRIDGE and (pos.distance_squared(i) < pos.distance_squared(self.target) and ct.get_entity_type(ct.get_tile_building_id(ct.get_bridge_target(ct.get_tile_building_id(i)))) == EntityType.CORE):
                        self.target = i
                    elif ct.get_entity_type(ct.get_tile_building_id(i)) in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and ct.is_in_vision(i.add(ct.get_direction(ct.get_tile_building_id(i)))) and ct.get_entity_type(ct.get_tile_building_id(i.add(ct.get_direction(ct.get_tile_building_id(i))))) == EntityType.CORE and i.distance_squared(self.enemy_core_pos) <= 25:
                        self.target = i
                    elif ct.get_entity_type(ct.get_tile_building_id(i)) in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and ct.is_in_vision(i.add(ct.get_direction(ct.get_tile_building_id(i)))) and (ct.get_tile_building_id(i.add(ct.get_direction(ct.get_tile_building_id(i)))) is None or (ct.get_entity_type(ct.get_tile_building_id(i.add(ct.get_direction(ct.get_tile_building_id(i))))) == EntityType.ROAD and ct.get_team(ct.get_tile_building_id(i.add(ct.get_direction(ct.get_tile_building_id(i))))) == ct.get_team(ct.get_tile_building_id(i)))) and i.add(ct.get_direction(ct.get_tile_building_id(i))).distance_squared(self.enemy_core_pos) <= 25:
                        self.target = i.add(ct.get_direction(ct.get_tile_building_id(i)))

        self.explore(ct)
        if ct.can_destroy(self.target):
            ct.destroy(self.target)
        if ct.can_build_gunner(self.target, self.target.direction_to(self.enemy_core_pos)):
            ct.build_gunner(self.target, self.target.direction_to(self.enemy_core_pos))
            self.target = self.enemy_core_pos
            self.last_positions = []
        if ct.get_position() == self.target:
            if ct.get_entity_type(ct.get_tile_building_id(ct.get_position())) in [EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and ct.can_fire(ct.get_position()):
                ct.fire(ct.get_position())
                self.target = self.enemy_core_pos
                self.last_positions = []


    def exploring(self, ct):
        if len(self.tit) != 0:  # Check if can mine ore at location
            self.status = MINING_TITANIUM
            self.target = Position(1000, 1000)

        else:  # Explore from outside corner in
            CORNERS = [Position(0, 0),
                       Position(ct.get_map_width() - 1, 0),
                       Position(0, ct.get_map_height() - 1),
                       Position(ct.get_map_width() - 1, ct.get_map_height() - 1)]

            closest_corner = Position(1000, 1000)
            iteration = 0
            while closest_corner == Position(1000, 1000) and iteration < (Position(0, 0).distance_squared(Position(int(ct.get_map_width() / 2),int(ct.get_map_height() / 2)))) / 7:  # Ends if new position to explore is found or is at centre
                for corner in CORNERS:
                    for i in range(7 * iteration):
                        corner = corner.add(Direction.CENTRE)
                        if corner == Position(int(ct.get_map_width() / 2), int(ct.get_map_height() / 2)):
                            break
                    if self.map[corner.y][corner.x] == [0, 0, 0, [0], 0] and ct.get_position().distance_squared(
                            corner) < ct.get_position().distance_squared(closest_corner):
                        closest_corner = corner
                iteration += 1
            if closest_corner == Position(1000, 1000):
                self.status = -1
                print("Bored")
            else:  # Explore to chosen corner
                self.target = closest_corner
                self.explore(ct)
            # Find closest corner, move until it is in vision radius (covered by first if)
            # ct.draw_indicator_dot(self.target, 255, 0, 0)


    def mining_titaniam(self,ct):
        if len(self.tit) == 0:
            self.status = EXPLORING
            print("RETURNING TO EXPLORING")
            return
        if self.target == Position(1000, 1000) or ct.get_position() == self.target:
            self.target = Position(1000, 1000)
            self.harvest_ore(ct, self.tit[0])  # Make smarter selection cases
        else:  # Allows for getting to a position around obstacles (other builder bots)
            self.explore(ct)
        ct.draw_indicator_dot(ct.get_position(), 0, 255, 0)
        if len(self.tit) > 0:
            ct.draw_indicator_line(ct.get_position(), self.tit[0], 0, 255, 0)


    def defence(self, ct):
        if ct.get_hp(ct.get_tile_building_id(self.core_pos)) < 500:
            self.target = self.core_pos
            if ct.can_heal(self.core_pos):
                ct.heal(self.core_pos)
            self.explore(ct)
            return

        # Note: building Launchers is Useless
        if self.target == Position(1000, 1000):
            for i in [self.core_pos.add(Direction.NORTHEAST).add(Direction.NORTHEAST), self.core_pos.add(Direction.SOUTHWEST).add(Direction.SOUTHWEST)]:
                if ct.is_in_vision(i) and ct.get_entity_type(ct.get_tile_building_id(i)) not in [EntityType.LAUNCHER, EntityType.CONVEYOR]:
                    print(f"Looking to build Launcher at {i}")
                    self.target = i
        if self.target == Position(1000, 1000):
            print(" Launchers built")
            return

        if ct.get_position().add(ct.get_position().direction_to(self.target)) == self.target:
            if ct.get_entity_type(ct.get_tile_building_id(self.target)) not in [EntityType.LAUNCHER, EntityType.CONVEYOR]:
                if ct.can_destroy(self.target):
                    ct.destroy(self.target)
            if ct.can_build_launcher(self.target):
                ct.build_launcher(self.target)
                print("Built Launcher!")
                self.target = Position(1000, 1000)
                return
            if ct.get_entity_type(ct.get_tile_building_id(self.target)) == EntityType.LAUNCHER:
                self.target = Position(1000, 1000)
                return
        self.explore(ct)


    def gn_attack_enemy_core(self, ct):
        d = ct.get_direction()
        target = ct.get_position()
        for i in range(2):
            target = target.add(d)
            if ct.get_entity_type(ct.get_tile_builder_bot_id(target)) == EntityType.BUILDER_BOT and ct.get_team() == ct.get_team(ct.get_tile_building_id(target)):
                return
            if ct.can_fire(target):
                ct.fire(target)
                return


    def launch_enemy_bots_away(self, ct):
        vision_tiles = ct.get_nearby_tiles()
        random.shuffle(vision_tiles)
        for i in ct.get_attackable_tiles():
            if ct.get_tile_builder_bot_id(i) is not None and ct.get_team(ct.get_tile_builder_bot_id(i)) != ct.get_team():
                for j in vision_tiles:
                    if ct.can_launch(i, j):
                        ct.launch(i, j)
                        print("HAHA LOOSER")
                        ct.draw_indicator_line(i, j, 200, 0, 0)
                        return


    def run(self, ct: Controller) -> None:
        if ct.get_current_round() > 500:
            ct.resign()

        etype = ct.get_entity_type()

        if etype == EntityType.CORE:

            if self.status == INIT:
                if not self.map:
                    self.initialise_map(ct)
                    self.core_pos = ct.get_position()
                    self.update_map(ct)
                self.status = 1

            vision_tiles = ct.get_nearby_tiles()
            possible_core_locations = [
                [ct.get_map_width() - 1 - self.core_pos.x, self.core_pos.y                          ],  # Horizontal Flip
                [self.core_pos.x                         , ct.get_map_height() - 1 - self.core_pos.y],  # Vertical Flip
                [ct.get_map_width() - 1 - self.core_pos.x, ct.get_map_height() - 1 - self.core_pos.y]]  # Opposite Corner

            if self.num_spawned < 3:
                spawn_pos = ct.get_position().add(Direction.NORTH)
                if ct.can_spawn(spawn_pos):
                    ct.spawn_builder(spawn_pos)

                    # Place marker, so bot knows where to go
                    bot_id = ct.get_tile_builder_bot_id(spawn_pos)
                    marker_status = 1
                    message = (
                            marker_status * (2 ** 28)
                            + bot_id * (2 ** 12)
                            + possible_core_locations[self.num_spawned][0] * (2 ** 6)
                            + possible_core_locations[self.num_spawned][1]
                    )
                    self.num_spawned += 1
                    for i in ct.get_nearby_tiles(5):  # Will sometimes cause errors where builder bot cannot move to tile where marker was placed and destroy it
                        if ct.is_tile_empty(i) and ct.can_place_marker(i):
                            ct.place_marker(i, message)

            elif self.num_spawned < 6: # Spawn Defence Bots
                spawn_pos = ct.get_position()
                if ct.can_spawn(spawn_pos):
                    ct.spawn_builder(spawn_pos)

                    # Place marker, so bot knows where to go
                    bot_id = ct.get_tile_builder_bot_id(spawn_pos)
                    marker_status = 3
                    message = (
                            marker_status * (2 ** 28)
                            + bot_id * (2 ** 12)
                            + 0 * (2 ** 6)
                            + 0
                    )
                    self.num_spawned += 1
                    for i in ct.get_nearby_tiles(5):  # Will sometimes cause errors where builder bot cannot move to tile where marker was placed and destroy it
                        if ct.is_tile_empty(i) and ct.can_place_marker(i):
                            ct.place_marker(i, message)

            for i in vision_tiles:
                if self.enemy_core_pos == Position(1000,1000) and ct.get_entity_type(ct.get_tile_building_id(i)) == EntityType.MARKER and ct.get_team(ct.get_tile_building_id(i)) == ct.get_team():
                    print("ANYTHING")
                    marker_value = ct.get_marker_value(ct.get_tile_building_id(i))
                    marker_value_id = (marker_value % (2 ** 28)) // (2 ** 12)
                    marker_status = marker_value // (2 ** 28)

                    if marker_status == 2:
                        # OPPONENT CORE LOCATION
                        target_x = (marker_value % (2 ** 12)) // (2 ** 6)
                        target_y = marker_value % (2 ** 6)
                        self.enemy_core_pos = Position(target_x, target_y)
                        ct.draw_indicator_line(ct.get_position(), self.enemy_core_pos, 0, 0, 0)
                        return

                if self.enemy_core_pos != Position(1000, 1000) and ct.get_unit_count() < 12:
                    spawn_pos = ct.get_position()
                    if ct.can_spawn(spawn_pos) and ct.get_global_resources()[0] > 800:    # ARBRITARY THRESHOLD
                        ct.spawn_builder(spawn_pos)
                        self.num_spawned += 1

                        bot_id = ct.get_tile_builder_bot_id(spawn_pos)
                        if bot_id is None: # should not happen
                            bot_id = 0
                        marker_status = 2
                        message = (
                                marker_status * (2 ** 28)
                                + bot_id * (2 ** 12)
                                + self.enemy_core_pos.x * (2 ** 6)
                                + self.enemy_core_pos.y)

                        for j in ct.get_nearby_tiles(5):  # Will sometimes cause errors where builder bot cannot move to tile where marker was placed and destroy it
                            if ct.is_tile_empty(j) and ct.can_place_marker(j):
                                ct.place_marker(j, message)
                                return
                        for j in ct.get_nearby_tiles():  # Will sometimes cause errors where builder bot cannot move to tile where marker was placed and destroy it
                            if ct.is_tile_empty(j) and ct.can_place_marker(j):
                                ct.place_marker(j, message)
                                return
                        print("WHHOPS")

        elif etype == EntityType.BUILDER_BOT:

            if self.status == INIT:
                print("Initialising...")
                self.initialise_builder_bot(ct) # Includes initialising map

            self.update_map(ct)

            if self.status == FIND_ENEMY_CORE:
                print(f"Finding Enemy Core at {self.target}")
                self.find_enemy_core(ct)

            elif self.status == EXPLORING:
                print(f"Just roaming 'bout... Tit: {self.tit}")
                self.exploring(ct)


            elif self.status == MINING_TITANIUM:  # Mining titanium ore
                print("Dont mind me, I'm just mining some titanium.")
                self.mining_titaniam(ct)
            
            elif self.status == REPORT_ENEMY_CORE_LOCATION:
                print(f"Reporting Enemy Core at {self.enemy_core_pos}")
                self.report_enemy_core_location(ct)

            elif self.status == GO_TO_ENEMY_CORE:
                print(f"Going to Enemy Core at {self.enemy_core_pos}")
                self.explore(ct)
                if ct.is_in_vision(self.enemy_core_pos):
                    self.status = ATTACK_ENEMY_CORE

            elif self.status == ATTACK_ENEMY_CORE:
                print(f"Attacking Enemy Core at {self.enemy_core_pos}")
                self.attack_enemy_core(ct)

            elif self.status == DEFENCE:
                print(f"Defending Core {self.target}")
                self.defence(ct)





            # for y in range(len(self.map)):
            #    for x in range(len(self.map[y])):
            #        if self.map[y][x][1] == EntityType.BUILDER_BOT:
            #            ct.draw_indicator_dot(Position(x,y), 0, 0, 0)
            #        elif self.map[y][x][1] == EntityType.ARMOURED_CONVEYOR:
            #            ct.draw_indicator_dot(Position(x,y), 255, 0, 0)
            #        elif self.map[y][x][1] == EntityType.BRIDGE:
            #            ct.draw_indicator_dot(Position(x,y), 0, 255, 0)
            #        elif self.map[y][x][1] == EntityType.CONVEYOR:
            #            ct.draw_indicator_dot(Position(x,y), 0, 0, 255)
            #        elif self.map[y][x][1] == EntityType.MARKER:
            #            ct.draw_indicator_dot(Position(x,y), 100, 100, 100)
            #        elif self.map[y][x][1] == EntityType.ROAD:
            #            ct.draw_indicator_dot(Position(x,y), 255, 255, 255)
            #        elif self.map[y][x][1] == None:
            #            ct.draw_indicator_dot(Position(x,y), 255, 0, 255)
            #        if self.map[y][x][1] in [EntityType.BUILDER_BOT, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.MARKER, EntityType.ROAD]:
            #            ct.draw_indicator_dot(Position(x,y), 0, 0, 0)
            #        elif self.map[y][x][0] == Environment.EMPTY:
            #            ct.draw_indicator_dot(Position(x,y), 0, 255, 0)
            #        elif self.map[y][x][0] == Environment.WALL:
            #            ct.draw_indicator_dot(Position(x,y), 255, 0, 0)
            #        elif self.map[y][x][0] == Environment.ORE_TITANIUM:
            #            ct.draw_indicator_dot(Position(x,y), 0, 0, 255)
            #        elif self.map[y][x][0] == Environment.ORE_AXIONITE:
            #            ct.draw_indicator_dot(Position(x,y), 255, 255, 0)

        elif ct.get_entity_type() == EntityType.GUNNER:

            self.gn_attack_enemy_core(ct)

        elif ct.get_entity_type() == EntityType.LAUNCHER:

            self.launch_enemy_bots_away(ct)