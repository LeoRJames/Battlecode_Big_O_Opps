import random
from queue import PriorityQueue
from collections import deque
from cambc import Controller, Direction, EntityType, Environment, Position, ResourceType
import heapq

# non-centre directions
DIRECTIONS = [d for d in Direction if d != Direction.CENTRE]
STRAIGHTS = [Direction.NORTH, Direction.SOUTH, Direction.WEST, Direction.EAST]
DIAGONALS = [Direction.NORTHWEST, Direction.NORTHEAST, Direction.SOUTHEAST, Direction.SOUTHWEST]
NON_PASSABLE = [EntityType.HARVESTER, EntityType.BARRIER, EntityType.BREACH, EntityType.FOUNDRY, EntityType.GUNNER, EntityType.LAUNCHER, EntityType.SENTINEL, Environment.WALL]

# STATUS CONSTANTS
INIT = 0
FIND_ENEMY_CORE = 100
REPORT_ENEMY_CORE_LOCATION = 1000
GO_TO_ENEMY_CORE = 3
ATTACK_ENEMY_CORE = 4
EXPLORING = 1
MINING_TITANIUM = 2
DEFENCE = 7
ATTACK_ENEMY_SUPPLY_LINES = 5
FOUNDRY = 6
MOVING_TURRET = 8
ATTACK_ENEMY_CONVEYORS = 9

class Player:
    def __init__(self):
        self.id = None
        self.team = None
        self.pos = None
        self.num_spawned = 0 # number of builder bots spawned so far (core)
        self.map = []
        self.core_pos = Position(1000, 1000)
        self.enemy_core_pos = Position(1000, 1000)  # Records a (central) core position
        self.pathfinder_start_pos = Position(1000, 1000)
        self.tit = []   # List of Positions of unmined titanium
        self.ax = []    # List of Positions of unmined axionite
        self.built_harvester = [False, None, None]    # 0: True if built harvester and must connect; 1: Not False if built first conveyor and must move on to, otherwise stores position of that conveyor; 2: position of built harvester
        self.closest_conn_to_core = [Position(1000, 1000), False]   # True if do not adapt
        self.status = 0     # Tells bot what to do
        self.target = Position(1000, 1000)  # Target position for exploring
        self.transport_resource_var = False
        self.move_dir = Direction.CENTRE     # Arbitrary
        self.splitter_resource = {}
        self.marker_locations = []
        self.unreachable_ores = [] # List of unreachable ores
        self.unreachable_tiles = []
        self.came_from = None   # Save pathfinder state for continuing in next turn
        self.cost_so_far = None
        self.best_tile = None
        self.closed = None
        self.open_heap = None
        self.ore_target = None  # Prevents constant changing of ore target
        self.invalid_tiles = False
        self.mined_tit = [] # Tracks ores we have mined
        self.mined_ax = []
        self.enemy_mined_tit = []   # Tracks ores enemy has mined
        self.attacked_enemy_mined_tit = []
        self.enemy_mined_ax = []
        self.splitter_target = None
        self.enemy_mined_tit_target= None
        self.attack_enemy_core_timer = 0
        self.attack_enemy_core_close = True
        self.extra_spawned = 0
        self.temp_counter = 0
        self.try_avoid = True
        self.pathfiner_fail_count = 0
        self.explore_start = None
        self.defence_mode = 10
        self.defence_target = Position(1000, 1000)
        self.moving_turret_supply = False
        self.find_enemy_core_target = None
        self.mined_tit_count = 0
        self.prev_fire = [None, None]   # 0: position; 1: hp after firing
        self.enemy_supply = None
        self.bot_count = 0
        self.possible_core_locations = []
        self.circling_count = 0

    def initialise_map(self, ct):   # Set up 2d array for each tile on map each storing a list of three info pieces (tile type, building, team)
        self.team = ct.get_team()
        for j in range(ct.get_map_height()):
            row = []
            for i in range(ct.get_map_width()):
                row.append([0, 0, 0, [0], 0])
            self.map.append(row)

    def update_map(self, ct):
        pre_update_map_time = ct.get_cpu_time_elapsed()

        if not self.map:
            self.initialise_map(ct)

        for tile in ct.get_nearby_tiles():
            start_time = ct.get_cpu_time_elapsed()

            env = ct.get_tile_env(tile)

            if self.map[tile.y][tile.x][0] == 0:
                self.map[tile.y][tile.x][0] = env

            # Get these now to minimise ct usage
            building_id = ct.get_tile_building_id(tile)
            team = ct.get_team(building_id)
            my_team = self.team

            if building_id is not None:
                # Sets Entity_Type on tile (CORE, GUNNER, SENTINEL, BREACH, LAUNCHER, CONVEYOR, SPLITTER, ARMOURED_CONVEYOR, BRIDGE, HARVESTER, FOUNDRY, ROAD, BARRIER, MARKER, None)
                self.map[tile.y][tile.x][1] = ct.get_entity_type(building_id)
                entity = self.map[tile.y][tile.x][1]

                if entity in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.SPLITTER, EntityType.GUNNER, EntityType.BREACH, EntityType.SENTINEL]:
                    self.map[tile.y][tile.x][3][0] = ct.get_direction(building_id)   # Sets direction of directional

                elif entity == EntityType.BRIDGE:
                    self.map[tile.y][tile.x][3][0] = ct.get_bridge_target(building_id)   # Sets target of bridge
                    bridge_target = self.map[tile.y][tile.x][3][0]

                    if tile not in self.map[bridge_target.y][bridge_target.x][3]:   # Sets source of bridges ending at a tile
                        self.map[bridge_target.y][bridge_target.x][3].append(tile)

                # What is this for?
                elif entity == EntityType.MARKER and team == my_team:
                    self.marker_locations.append(tile)

                elif self.enemy_core_pos == Position(1000, 1000) and entity == EntityType.CORE and team != my_team:
                    self.enemy_core_pos = ct.get_position(building_id)
                else:
                    self.map[tile.y][tile.x][3][0] = None

                if team == self.team and (entity in [EntityType.SPLITTER] and tile.distance_squared(self.core_pos) <= 5):# or (entity == EntityType.BRIDGE and self.map[bridge_target.y][bridge_target.x][1] == EntityType.CORE)):
                    res = ct.get_stored_resource(building_id)
                    if tile in self.splitter_resource and self.splitter_resource[tile] == False or res == ResourceType.REFINED_AXIONITE:   # Harvester already built to that splitter
                        pass
                    elif res != None and tile not in self.splitter_resource:    # If not recorded a resource
                        self.splitter_resource[tile] = res
                    elif tile in self.splitter_resource and (self.splitter_resource[tile] == True or (res != None  and self.splitter_resource[tile] != res)):    # If a different resource recorded through splitter
                        self.splitter_resource[tile] = True
                        if self.status == DEFENCE and ct.get_global_resources()[0] > ct.get_foundry_cost()[0]:
                            self.status = FOUNDRY
                            self.target = tile


                if self.map[tile.y][tile.x][0] == Environment.ORE_TITANIUM and tile not in self.tit and tile not in self.unreachable_ores and not(entity == EntityType.HARVESTER or (team != my_team and entity not in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.ROAD]) or (team == my_team and entity in [EntityType.SENTINEL, EntityType.GUNNER, EntityType.LAUNCHER, EntityType.FOUNDRY, EntityType.BREACH])) and not (tile.distance_squared(self.core_pos) >= 25**2 and entity == EntityType.BARRIER):
                    self.tit.append(tile)
                elif self.map[tile.y][tile.x][0] == Environment.ORE_AXIONITE and tile not in self.ax and tile not in self.unreachable_ores and not(entity == EntityType.HARVESTER or (team != my_team and entity not in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.ROAD]) or (team == my_team and entity in [EntityType.SENTINEL, EntityType.GUNNER, EntityType.LAUNCHER, EntityType.FOUNDRY, EntityType.BREACH])) and not (tile.distance_squared(self.core_pos) >= 25**2 and entity == EntityType.BARRIER):
                    self.ax.append(tile)

                if entity == EntityType.HARVESTER:
                    if team == my_team:
                        if tile not in self.mined_tit and env == Environment.ORE_TITANIUM:
                            self.mined_tit.append(tile)
                        elif tile not in self.mined_ax and env == Environment.ORE_AXIONITE:
                            self.mined_ax.append(tile)
                    else:
                        if tile not in self.enemy_mined_tit and env == Environment.ORE_TITANIUM and tile not in self.attacked_enemy_mined_tit:
                            self.enemy_mined_tit.append(tile)
                        elif tile not in self.enemy_mined_ax and env == Environment.ORE_AXIONITE:   # and tile not in self.attacked_enemy_mined_ax
                            self.enemy_mined_ax.append(tile)

                if tile in self.tit and (entity == EntityType.HARVESTER or (team != my_team and entity not in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.ROAD]) or (team == my_team and entity in [EntityType.SENTINEL, EntityType.GUNNER, EntityType.LAUNCHER, EntityType.FOUNDRY, EntityType.BREACH]) or (tile.distance_squared(self.core_pos) >= 25**2 and entity == EntityType.BARRIER)): #  and (self.status != 2 or not self.built_harvester[0]):  # Remove from list if another bot has built harveter on it
                    self.tit.remove(tile)
                    if tile == self.ore_target:
                        self.ore_target = None
                elif tile in self.ax and (entity == EntityType.HARVESTER or (team != my_team and entity not in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.ROAD]) or (team == my_team and entity in [EntityType.SENTINEL, EntityType.GUNNER, EntityType.LAUNCHER, EntityType.FOUNDRY, EntityType.BREACH]) or (tile.distance_squared(self.core_pos) >= 25**2 and entity == EntityType.BARRIER)): # and (self.status != 2 or not self.built_harvester[0]):
                    self.ax.remove(tile)
                    if tile == self.ore_target:
                        self.ore_target = None

            # No building on tile
            else:
                if self.map[tile.y][tile.x][1] == EntityType.BRIDGE:
                    bridge_target = self.map[tile.y][tile.x][3][0]
                    if tile in self.map[bridge_target.y][bridge_target.x][3]:
                        self.map[bridge_target.y][bridge_target.x][3].remove(tile)
                self.map[tile.y][tile.x][1] = None
                self.map[tile.y][tile.x][3][0] = None
                if   self.map[tile.y][tile.x][0] == Environment.ORE_TITANIUM and tile not in self.tit and tile not in self.unreachable_ores:
                    self.tit.append(tile)
                elif self.map[tile.y][tile.x][0] == Environment.ORE_AXIONITE and  tile not in self.ax and tile not in self.unreachable_ores:
                    self.ax.append(tile)

            if ct.get_tile_builder_bot_id(tile) is not None:
                self.map[tile.y][tile.x][4] = EntityType.BUILDER_BOT  # Sets builder bot
            else:
                self.map[tile.y][tile.x][4] = None

            self.map[tile.y][tile.x][2] = team  # Sets the team of the building

            #harvester_count, connected = self.supply_connectivity(ct, start=tile)
            #if ((not self.closest_conn_to_core[1] and entity in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.SPLITTER] and ct.get_team(ct.get_tile_building_id(tile)) == my_team) or connected[0] in [EntityType.CORE, True]) and self.pos.distance_squared(tile) < self.pos.distance_squared(self.closest_conn_to_core[0]):
            #    self.closest_conn_to_core[0] = tile

            end_time = ct.get_cpu_time_elapsed()
            if end_time - start_time > 7: print(f"({tile.x},{tile.y}) : {end_time-start_time}μs")

        post_update_map_time = ct.get_cpu_time_elapsed()
        print(f"Map Update Time: {post_update_map_time - pre_update_map_time} ({(post_update_map_time - pre_update_map_time) / 69:.1f})")

    def simple_supply_connectivity(self, ct, start=None):
        if start is None:
            start = self.pos
        next_tile = start
        end = None
        own_team = False
        count = 0
        while count < 10:
            building = self.map[next_tile.y][next_tile.x][1]
            team = self.map[next_tile.y][next_tile.x][2]
            print(next_tile, building, team)
            if building in [0, None, EntityType.HARVESTER, EntityType.ROAD, EntityType.LAUNCHER, EntityType.MARKER, EntityType.BARRIER]:    # Useless end point
                end = None
                break
            elif building in [EntityType.ARMOURED_CONVEYOR, EntityType.CONVEYOR, EntityType.SPLITTER]:    # Continue in direction of conveyor
                next_tile = next_tile.add(self.map[next_tile.y][next_tile.x][3][0])
            elif building is EntityType.BRIDGE:    # Continue to end point of bridge
                next_tile = self.map[next_tile.y][next_tile.x][3][0]
            elif building in [EntityType.CORE, EntityType.BREACH, EntityType.GUNNER, EntityType.SENTINEL, EntityType.FOUNDRY]:    # Valid end point
                end = building
                if team == self.team:
                    own_team = True
                break
            else:
                pass
            count += 1
        return end, own_team

    def supply_connectivity(self, ct, start=None, check_back=True, visited=False):  # ITERATIVE FOR EACH PATH
        if start is None:
            start = self.pos
        # check_back: Flag to first check back to source, then check forward to end
        harvester_count = [0] # Counts how many harvesters on path (max four, more than this causes backlog)
        connected = [False]   # False if not connected; True if unknown (not recorded on map); otherwise entity type of what it connects to
        next_tile = start
        if visited == False:
            visited = set()
        while check_back:   # Checks back to source
            check_back = False
        while not check_back:   # Checks forward to end

            if next_tile in visited:
                check_back = True
                break
            visited.add(next_tile)

            if self.map[next_tile.y][next_tile.x][2] != self.team:
                check_back = True
                break

            # Could also account for other check back routes (could cause endless route if not ensuring to not recheck routes)
            if self.map[next_tile.y][next_tile.x][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.CONVEYOR]:

                left_tile = next_tile.add(self.map[next_tile.y][next_tile.x][3][0].rotate_left().rotate_left())
                if not (left_tile.y < 0 or left_tile.y >= ct.get_map_height() or left_tile.x < 0 or left_tile.x >= ct.get_map_width()):
                    if self.map[left_tile.y][left_tile.x][1] is EntityType.HARVESTER:
                        harvester_count[0] += 1

                right_tile = next_tile.add(self.map[next_tile.y][next_tile.x][3][0].rotate_right().rotate_right())
                if not (right_tile.y < 0 or right_tile.y >= ct.get_map_height() or right_tile.x < 0 or right_tile.x >= ct.get_map_width()):
                    if self.map[right_tile.y][right_tile.x][1] is EntityType.HARVESTER:
                        harvester_count[0] += 1

            # Check for continuing or ending route
            if self.map[next_tile.y][next_tile.x][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.CONVEYOR]:    # Continue in direction of conveyor
                next_tile = next_tile.add(self.map[next_tile.y][next_tile.x][3][0])
            elif self.map[next_tile.y][next_tile.x][1] is EntityType.BRIDGE:    # Continue to end point of bridge
                next_tile = self.map[next_tile.y][next_tile.x][3][0]
            elif self.map[next_tile.y][next_tile.x][1] in [EntityType.CORE, EntityType.BREACH, EntityType.GUNNER, EntityType.SENTINEL]:    # Valid end point
                connected = [self.map[next_tile.y][next_tile.x][1]]
                check_back = True
            elif self.map[next_tile.y][next_tile.x][1] is EntityType.SPLITTER:  # Assume splitter direction is same direction of conveyor into it
                connected[0] = EntityType.SPLITTER
                left_splitter_harvester_count, left_splitter_connected = self.supply_connectivity(ct, next_tile.add(self.map[next_tile.y][next_tile.x][3][0].rotate_left().rotate_left()), check_back, visited=visited)
                for i in range(len(left_splitter_harvester_count)):
                    harvester_count.append(left_splitter_harvester_count[i])
                    connected.append(left_splitter_connected[i])
                forward_splitter_harvester_count, forward_splitter_connected = self.supply_connectivity(ct, next_tile.add(self.map[next_tile.y][next_tile.x][3][0]), check_back, visited=visited)
                for i in range(len(forward_splitter_harvester_count)):
                    harvester_count.append(forward_splitter_harvester_count[i])
                    connected.append(forward_splitter_connected[i])
                right_splitter_harvester_count, right_splitter_connected = self.supply_connectivity(ct, next_tile.add(self.map[next_tile.y][next_tile.x][3][0].rotate_right().rotate_right()), check_back, visited=visited)
                for i in range(len(right_splitter_harvester_count)):
                    harvester_count.append(right_splitter_harvester_count[i])
                    connected.append(right_splitter_connected[i])
                
            elif self.map[next_tile.y][next_tile.x][1] is EntityType.FOUNDRY:
                sum = [-1, 1]
                for num in sum:
                    pass
                pass    # Search surrounding four tile for conveyors or splitters not facing into foundry
            elif self.map[next_tile.y][next_tile.x][1] == 0:    # Unlnown on map
                connected = [True]
                check_back = True
            else:   # Not connected
                check_back = True

        return harvester_count, connected
    
    def heuristic_Chebyshev(self, next, target):     # Pass Positions
        return max(abs(next.x - target.x), abs(next.y - target.y))  # Chebyshev distance
    
    def heuristic_squaredEuclidean(self, next, target):
        return next.distance_squared(target)

    def _neighbors_bridge(self, current, grid, width, height, unreachable, team, ct_pos, avoid, target):

        cx, cy = current
        results = []

        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if dx == 0 and dy == 0:
                    continue
                if dx*dx + dy*dy > 9:
                    continue

                nx, ny = cx + dx, cy + dy
                if not (0 <= nx < width and 0 <= ny < height):
                    continue
                if Position(cx, cy) in unreachable:
                    continue
                if avoid and 4 <= ((cx - self.core_pos.x)**2 + (cy - self.core_pos.y)**2) <= 8:   # Do not use tiles around core
                    continue

                tile = grid[ny][nx]

                if avoid:
                    valid = (
                        tile[1] in [EntityType.MARKER, EntityType.ROAD,
                                    EntityType.CORE]
                        and tile[2] == team
                    )
                else:
                    valid = (
                        tile[1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE,
                                    EntityType.CONVEYOR, EntityType.MARKER,
                                    EntityType.ROAD, EntityType.CORE,
                                    EntityType.SPLITTER]
                        and tile[2] == team
                    )

                if valid or (tile[1] is None and tile[0] == Environment.EMPTY):
                    results.append((nx, ny))

        return results

    def _neighbors_conv(self, current, grid, width, height, unreachable, team, ct_pos, avoid, target):

        cx, cy = current
        results = []

        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if Position(cx, cy) in unreachable:
                continue

            tile = grid[ny][nx]

            if tile[4] is not None and ct_pos.distance_squared(Position(cx, cy)) == 1 and tile[1] != EntityType.CORE:
                continue
            if avoid and 4 <= ((cx - self.core_pos.x)**2 + (cy - self.core_pos.y)**2) <= 8:   # Do not use tiles around core
                continue

            if avoid:
                valid = (
                    tile[1] in [EntityType.MARKER, EntityType.ROAD,
                                EntityType.CORE]
                    and tile[2] == team
                )
            else:
                valid = (
                    tile[1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE,
                                EntityType.CONVEYOR, EntityType.MARKER,
                                EntityType.ROAD, EntityType.CORE,
                                EntityType.SPLITTER]
                    and tile[2] == team
                )

            if valid or (tile[1] is None and tile[0] == Environment.EMPTY):
                results.append((nx, ny))

        return results

    def _neighbors_any(self, current, grid, width, height, unreachable, team, ct_pos, avoid, target):

        cx, cy = current
        results = []

        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue

                nx, ny = cx + dx, cy + dy
                if not (0 <= nx < width and 0 <= ny < height):
                    continue
                if Position(cx, cy) in unreachable:
                    continue

                tile = grid[ny][nx]

                if tile[0] == Environment.WALL and not (nx, ny) == target:
                    continue

                if tile[0] == 0 or ((nx, ny) == target) or (target == (self.enemy_core_pos.x, self.enemy_core_pos.y) and tile[1] == EntityType.CORE) or ((    # current == target and (self.target.x, self.target.y) == target
                    not (tile[4] in [EntityType.BUILDER_BOT]
                        and ct_pos.distance_squared(Position(cx, cy)) <= 8)
                ) and (
                    tile[1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE,
                                EntityType.CONVEYOR, EntityType.MARKER,
                                EntityType.ROAD, EntityType.SPLITTER]
                    or (tile[1] == EntityType.BARRIER and tile[2] == team)
                    or (tile[1] == EntityType.CORE and (tile[2] == team or (tile[2] != team and self.status == ATTACK_ENEMY_CORE and target[0] != 1000 and grid[target[1]][target[0]][1] == EntityType.CORE)))
                    or (tile[1] is None and tile[0] != Environment.WALL)
                )):
                    results.append((nx, ny))

        return results

    def _neighbors_normal(self, current, grid, width, height, unreachable, team, ct_pos, avoid, target):

        cx, cy = current
        results = []

        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue

                nx, ny = cx + dx, cy + dy
                if not (0 <= nx < width and 0 <= ny < height):
                    continue
                if Position(cx, cy) in unreachable:
                    continue

                tile = grid[ny][nx]

                if not (
                    tile[4] in [EntityType.BUILDER_BOT]
                    and ct_pos.distance_squared(Position(cx, cy)) <= 8
                ) and (
                    tile[1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE,
                                EntityType.CONVEYOR, EntityType.MARKER,
                                EntityType.ROAD, EntityType.SPLITTER]
                    or (tile[1] in [EntityType.CORE, EntityType.BARRIER] and tile[2] == team)
                    or (tile[1] is None and tile[0] != Environment.WALL)
                ):
                    results.append((nx, ny))

        return results

    def tuple_distance_squared(self, x, y):
        return ((y[0] - x[0])**2 + (y[1] - x[1])**2)

    def pathfinder(self, ct, target, start=None, bridge=False, conv=False, avoid=False, any=False):

        start_time = ct.get_cpu_time_elapsed()

        if start is None:
            start = self.pos

        # Convert to tuples for internal use
        start = (start.x, start.y)
        target = (target.x, target.y)

        moveTile = 0        # Tie breakers for equal path lengths
        dist = 0

        grid = self.map
        height = len(grid)
        width = len(grid[0])
        unreachable = self.unreachable_tiles
        team = self.team
        ct_pos = self.pos

        # ----- Heuristic -----
        if bridge:
            def heuristic(p):
                return self.heuristic_squaredEuclidean(
                    Position(p[0], p[1]),
                    Position(target[0], target[1])
                )
        elif conv:
            def heuristic(p):
                return self.heuristic_Chebyshev(
                    Position(p[0], p[1]),
                    Position(target[0], target[1])
                )
        else:
            def heuristic(p):
                return (abs(p[0] - target[0]) + abs(p[1] - target[1]))

        # ----- Neighbor selector -----
        if bridge:
            get_neighbors = self._neighbors_bridge
        elif conv:
            get_neighbors = self._neighbors_conv
        elif any:
            get_neighbors = self._neighbors_any
        else:
            get_neighbors = self._neighbors_normal

        # ----- A* structures -----
        if self.open_heap == None:
            open_heap = []
            heapq.heappush(open_heap, (0, moveTile, dist, start))
        else:
            open_heap = self.open_heap
            self.open_heap = None

        if self.came_from == None:
            came_from = {start: None}
        else:
            came_from = self.came_from
            self.came_from = None
        if self.cost_so_far == None:
            cost_so_far = {start: 0}
        else:
            cost_so_far = self.cost_so_far
            self.cost_so_far = None
        if self.closed == None:
            closed = set()
        else:
            closed = self.closed
            self.closed = None
        if self.best_tile == None:
            best_tile = start
        else:
            best_tile = self.best_tile
            self.best_tile = None
        best_dist = heuristic(best_tile)
        counter = 0

        while open_heap:

            if ct.get_cpu_time_elapsed() > 1500:    # Cut off time to give sufficient time after completion to do remaining processes
                self.open_heap = open_heap
                self.came_from = came_from
                self.cost_so_far = cost_so_far
                self.best_tile = best_tile
                self.closed = closed
                print("out of time")
                return None, None, None

            _, _, _, current = heapq.heappop(open_heap)

            if current in closed:
                continue
            closed.add(current)
            counter += 1


            if conv and counter > 20:   # At this point, better to build a bridge
                break

            if current == target:
                best_tile = current
                break

            d = heuristic(current)
            if d < best_dist:
                best_dist = d
                best_tile = current

            for nx, ny in get_neighbors(
                current, grid, width, height,
                unreachable, team, ct_pos, avoid, target
            ):

                moveTile = 0
                dist = 11
                #if current[3].distance_squared(tile_pos) > 1:   # Prefer to move in a straight line rather than diagonally
                    #counter += 1
                if grid[ny][nx][1] == None:   # Prefer not to move over non-passable spaces (to save resources building extra paths)
                    moveTile += 1
                if bridge:
                    dist = dist - self.tuple_distance_squared(current, (ny, nx)) # Prefer to build longest bridge
                else:
                    dist = self.tuple_distance_squared(current, (ny, nx))    # Prefer to move in straight lines (as I think is more valuable for information)
                #ct.draw_indicator_dot(tile, 0, 0, 255)
                #if bridge:
                    #new_cost = cost_so_far[current] + (self.tuple_distance_squared(current, (ny, nx)))**(1/2)
                    #new_cost = cost_so_far[current[3]] + tile_pos.distance_squared(current[3])  # For bridges, squared euclidean distance matters
                #else:
                new_cost = cost_so_far[current] + 1     # Each move costs one move cooldown whether straight or diagonal for general movement

                if (nx, ny) not in cost_so_far or new_cost < cost_so_far[(nx, ny)]:
                    cost_so_far[(nx, ny)] = new_cost
                    priority = new_cost + heuristic((nx, ny))
                    heapq.heappush(open_heap, (priority, moveTile, dist, (nx, ny)))
                    came_from[(nx, ny)] = current

        end_time = ct.get_cpu_time_elapsed()
        print(f"Path Finder Time: {end_time - start_time}, ({counter})")

        # --- Post-process to convert tuples back to Position ---

        came_from_pos = {}
        for node, parent in came_from.items():
            node_pos = Position(node[0], node[1])
            parent_pos = Position(parent[0], parent[1]) if parent is not None else None
            came_from_pos[node_pos] = parent_pos

        cost_so_far_pos = {
            Position(node[0], node[1]): cost
            for node, cost in cost_so_far.items()
        }

        return came_from_pos, cost_so_far_pos, Position(*best_tile)

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
        self.team = ct.get_team()
        self.id = ct.get_id()

        vision_tiles = ct.get_nearby_tiles()
        for d in DIRECTIONS:
            yy = self.pos.add(d).y
            xx = self.pos.add(d).x

            if yy >= 0 and yy < len(self.map) and xx >= 0 and xx < len(self.map[0]) and self.map[self.pos.add(d).y][self.pos.add(d).x][1] == EntityType.CORE:
                self.core_pos = ct.get_position(ct.get_tile_building_id(self.pos.add(d)))
                break

        for i in vision_tiles:
            if self.map[i.y][i.x][1] == EntityType.MARKER and  self.map[i.y][i.x][2] == self.team:
                marker_value = ct.get_marker_value(ct.get_tile_building_id(i))
                marker_status = marker_value // (2 ** 28)
                marker_value_id = (marker_value % (2 ** 28)) // (2 ** 12)
                target_x = (marker_value % (2 ** 12)) // (2 ** 6)
                target_y = marker_value % (2 ** 6)

                # If marker is referring to [this bot or all bots]
                if marker_value_id in [self.id, 0]:

                    # Delete marker if referring specifically to this bot
                    if marker_value_id == self.id:
                        move_dir = self.pos.direction_to(i)
                        if ct.can_move(move_dir):
                            ct.move(move_dir)
                        if ct.can_destroy(i) and marker_status != 10:   # Destroy marker
                            ct.destroy(i)

                    # Load Position to check for opponent core
                    if marker_status == 1:
                        self.target = Position(target_x, target_y)
                        self.status = FIND_ENEMY_CORE

                    # Update known location of enemy core
                    elif marker_status == 2 or marker_status == 4:
                        self.enemy_core_pos = Position(target_x, target_y)
                        if self.enemy_core_pos == Position(0, 0):
                            self.enemy_core_pos = Position(1000, 1000)
                            self.possible_core_locations = [
                                                            [ct.get_map_width() - 1 - self.core_pos.x, self.core_pos.y],  # Horizontal Flip
                                                            [self.core_pos.x, ct.get_map_height() - 1 - self.core_pos.y],  # Vertical Flip
                                                            [ct.get_map_width() - 1 - self.core_pos.x, ct.get_map_height() - 1 - self.core_pos.y]]  # Rotation
                        print(marker_value, i)
                        print(marker_status, marker_value_id, target_x, target_y, self.id)
                        if marker_value_id == self.id:
                            if marker_status == 4:
                                self.attack_enemy_core_close = False
                            self.target = self.enemy_core_pos
                            self.status = ATTACK_ENEMY_CORE
                            self.explore_start = None
                            return
                    elif marker_status == 3:
                        self.enemy_core_pos = Position(target_x, target_y)
                        if self.enemy_core_pos == Position(0, 0):
                            self.enemy_core_pos = Position(1000, 1000)
                            self.possible_core_locations = [
                                                            [ct.get_map_width() - 1 - self.core_pos.x, self.core_pos.y],  # Horizontal Flip
                                                            [self.core_pos.x, ct.get_map_height() - 1 - self.core_pos.y],  # Vertical Flip
                                                            [ct.get_map_width() - 1 - self.core_pos.x, ct.get_map_height() - 1 - self.core_pos.y]]  # Rotation
                        if marker_value_id == self.id:
                            self.target = self.enemy_core_pos
                            self.status = ATTACK_ENEMY_SUPPLY_LINES
                            self.explore_start = None
                            return
                    elif marker_status == 5:
                        if marker_value_id == self.id:
                            self.status = MINING_TITANIUM
                            return
                        
                    elif marker_status == 6:
                        self.enemy_core_pos = Position(target_x, target_y)
                        if self.enemy_core_pos == Position(0, 0):
                            self.enemy_core_pos = Position(1000, 1000)
                            self.possible_core_locations = [
                                                            [ct.get_map_width() - 1 - self.core_pos.x, self.core_pos.y],  # Horizontal Flip
                                                            [self.core_pos.x, ct.get_map_height() - 1 - self.core_pos.y],  # Vertical Flip
                                                            [ct.get_map_width() - 1 - self.core_pos.x, ct.get_map_height() - 1 - self.core_pos.y]]  # Rotation
                        if marker_value_id == self.id:
                            self.target = self.enemy_core_pos
                            self.status = MOVING_TURRET
                            self.explore_start = None
                            return
                #else:
                #    if marker_status == 5 and not self.built_harvester[0]:
                #        self.target = Position(target_x, target_y)
                #        self.status = 5
                    #return marker_value_id
        if self.status == INIT:
            self.status = DEFENCE
            self.defence_mode = 10
            if sum([ 1 if ct.get_entity_type(i) == EntityType.BUILDER_BOT else 0 for i in ct.get_nearby_entities(5)]) > 4 and ct.get_hp(ct.get_tile_building_id(self.core_pos)) == ct.get_max_hp(ct.get_tile_building_id(self.core_pos)):
                self.status = EXPLORING

    def explore(self, ct, target=None):
        if self.invalid_tiles:
            print("Finding Invalid Tiles")
            res = self.find_invalid_tiles(ct, target)
            if self.built_harvester[1] != None and res:
                ct.draw_indicator_dot(self.built_harvester[1], 0, 0, 255)
                if len(self.map[self.built_harvester[1].y][self.built_harvester[1].x][3]) > 1:
                    self.built_harvester[1] = self.map[self.built_harvester[1].y][self.built_harvester[1].x][3][1]
            self.invalid_tiles = False  # Reset flag
            return
        if target == None:
            target = self.target
        came_from_explore, cost_explore, best_tile_explore = self.pathfinder(ct, target, any=True)
        if came_from_explore == None:
            return
        path_explore = self.reconstruct_path(came_from_explore, target)
        if len(path_explore) == 0:
            print("Invalid tile")
            self.invalid_tiles = True   # Flag to run next turn
            return
        else:
            for i in range(len(path_explore)):
                print(path_explore[i])
                ct.draw_indicator_dot(path_explore[i], 0, 255, 255)
            if len(path_explore) > 1:    # If next to target but cannot move there as there is a builder bot this condition is not satisfied so will just wait
                if self.map[path_explore[1].y][path_explore[1].x][1] == EntityType.BARRIER:
                    if ct.can_destroy(path_explore[1]):
                        ct.destroy(path_explore[1])
                    else:
                        print("Cannot destroy barrier")
                if ct.can_build_road(path_explore[1]):  # Fails if trying to build on to core
                    ct.build_road(path_explore[1])
                if ct.can_move(self.pos.direction_to(path_explore[1])):
                    ct.move(self.pos.direction_to(path_explore[1]))
                else:
                    if ct.get_tile_builder_bot_id(path_explore[1]) != None:
                        move_dir = self.pos.direction_to(path_explore[1])
                        for i in range(8):
                            move_dir = move_dir.rotate_left()   # Try to move anticlockwise around target
                            if ct.can_build_road(self.pos.add(move_dir)):
                                ct.build_road(self.pos.add(move_dir))
                            if ct.can_move(move_dir):
                                ct.move(move_dir)
                                self.move_dir = move_dir
                            else:
                                ct.draw_indicator_dot(self.pos.add(move_dir), 255, 0, 0)
                    else:
                        ct.draw_indicator_line(self.pos, self.pos.add(self.pos.direction_to(path_explore[1])), 0, 255, 0)
                        #ct.resign()
                            # Ran out of money

    def harvest_ore(self, ct, ore):
        if not self.built_harvester[0]:        # If have not built harvester, must move towards it and build
            print(f"Going to build Harvester at {ore}")

            # If far away from ore, just move towards it
            if ore.distance_squared(self.pos) >= 20:
                print(f"Ore is out of vision range, so just moving towards it.")
                self.target = ore
                self.explore(ct, ore)
                self.target = Position(1000, 1000)
                return

            # Checks if another bot has claimed the ore or there is a possible place to put conveyor next to harvester
            can_build_harvester = False
            if self.built_harvester[1] != None and self.built_harvester[1].distance_squared(ore) > 1:
                self.built_harvester[1] = None
            if self.map[ore.y][ore.x][4] != None and 0 < self.pos.distance_squared(ore) <= 2:
                self.bot_count += 1
            if self.bot_count == 5:
                self.bot_count = 0
            elif ct.get_entity_type(ct.get_tile_building_id(ore)) == EntityType.MARKER and ct.get_team(ct.get_tile_building_id(ore)) == self.team:
                marker_value = ct.get_marker_value(ct.get_tile_building_id(ore))
                marker_value_id = (marker_value % (2 ** 28)) // (2 ** 12)
                if marker_value_id == ct.get_id():
                    print(f"Secured harvester target : {ore}")
                    can_build_harvester = True
            elif self.map[ore.y][ore.x][1] in [EntityType.ROAD, EntityType.BARRIER, None] and self.map[ore.y][ore.x][2] in [self.team, None] :
                for d in STRAIGHTS:
                    check_location = ore.add(d)
                    exists = True if 0 <= check_location.x < len(self.map[0]) and 0 <= check_location.y < len(self.map) else False
                    if exists:
                        is_not_wall = True if self.map[check_location.y][check_location.x][0] != Environment.WALL else False
                        if is_not_wall and self.map[check_location.y][check_location.x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.ROAD, EntityType.BRIDGE, EntityType.SPLITTER, None] and self.map[check_location.y][check_location.x][2] in [self.team, None]:
                            if self.built_harvester[1] == None or check_location.distance_squared(self.core_pos) <= self.built_harvester[1].distance_squared(self.core_pos):
                                can_build_harvester = True
                                self.built_harvester[1] = check_location

            if not can_build_harvester:
                print(f"Can not build Harvester at {ore}, removing from list.")
                self.ore_target = None
                self.unreachable_ores.append(ore)
                self.bot_count = 0
                if ore in self.tit:
                    self.tit.remove(ore)
                elif ore in self.ax:
                    self.ax.remove(ore)
                else:
                    print("ore is not in tit or ax!")
                    #ct.resign()
                return

            if self.target == Position(1000, 1000) and ore.distance_squared(self.pos) > 2:
                print(f"Ore is out of action range ({ore})")
                self.target = ore
                self.explore(ct, ore)
                self.target = Position(1000, 1000)
                return
            elif self.target != Position(1000, 1000) and self.target.distance_squared(self.pos) > 2:
                self.explore(ct)
                self.target = Position(1000, 1000)
            
            if ore.distance_squared(self.pos) <= 2 and ore.distance_squared(self.core_pos) > 25**2:     # No point in connecting ores so far away as will cost a lot and probably go through an already clogged up route
                print(f"Ore is too far away")
                if ct.can_destroy(ore) and self.map[ore.y][ore.x][1] not in [EntityType.HARVESTER, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.SPLITTER, EntityType.FOUNDRY]:
                    ct.destroy(ore)
                if ct.can_build_barrier(ore):   # Add the ability to build from these to attack enemy
                    ct.build_barrier(ore)
                    self.ore_target = None
                    if ore in self.tit:
                        self.tit.remove(ore)
                    elif ore in self.ax:
                        self.ax.remove(ore)
                    else:
                        print("ore is not in tit or ax!")
                        #ct.resign()
                self.bot_count = 0
                return
            
            for d in STRAIGHTS:
                check_location = ore.add(d)
                if check_location != self.built_harvester[1]:
                    exists = True if 0 <= check_location.x < len(self.map[0]) and 0 <= check_location.y < len(self.map) else False
                    if exists:
                        is_not_wall = True if self.map[check_location.y][check_location.x][0] != Environment.WALL else False
                        if is_not_wall and self.map[check_location.y][check_location.x][4] == None and ((self.map[check_location.y][check_location.x][1] in [None, EntityType.ROAD] and self.map[check_location.y][check_location.x][2] in [None, self.team]) or self.map[check_location.y][check_location.x][1] == EntityType.MARKER):
                            self.target = check_location

            if ct.get_global_resources()[0] < ct.get_harvester_cost()[0] and ct.can_place_marker(ore) and not (self.map[ore.y][ore.x][1] == EntityType.MARKER and self.map[ore.y][ore.x][2] == self.team):
                print("Bagsying ORE")
                marker_status = 10
                bot_id = ct.get_id()
                X, Y = 0, 0 # Not necessary information
                message = (
                        marker_status * (2 ** 28)
                        + bot_id * (2 ** 12)
                        + X * (2 ** 6)
                        + Y)
                ct.place_marker(ore, message)
                return
            
            elif self.target != Position(1000, 1000):   # Must add firing
                if self.pos != ore:
                    temp = self.target
                    self.target = ore
                    self.explore(ct)
                    self.target = temp
                '''if self.pos == self.target:
                    for d in DIRECTIONS:
                        if ct.can_build_road(self.pos.add(d)):
                            ct.build_road(self.pos.add(d))
                        if ct.can_move(d):
                            ct.move(d)'''
                if ct.can_destroy(self.target) and self.map[self.target.y][self.target.x][1] in [EntityType.ROAD] and self.map[self.target.y][self.target.x][2] == self.team:
                    ct.destroy(self.target)
                if ct.can_build_barrier(self.target):
                    ct.build_barrier(self.target)
                    self.target = Position(1000, 1000)

            elif ct.get_global_resources()[0] >= ct.get_harvester_cost()[0]:
                # Happens to be on top of ore, move
                if self.map[self.pos.y][self.pos.x][2] == self.team and self.pos == ore:
                    print(f"Moving from on top of ore")
                    for d in DIRECTIONS:
                        if ct.can_build_road(self.pos.add(d)):
                            ct.build_road(self.pos.add(d))
                        if ct.can_move(d):
                            ct.move(d)
                            break
                if ct.can_destroy(ore) and self.map[ore.y][ore.x][1] not in [EntityType.HARVESTER, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.SPLITTER, EntityType.FOUNDRY]:
                    ct.destroy(ore)
                if ct.can_build_harvester(ore):
                    ct.build_harvester(ore)
                    self.bot_count = 0
                    self.built_harvester[0] = True
                    self.built_harvester[2] = ore

        else:
            if self.built_harvester[1] is not None:
                print(f"Going to {self.built_harvester[1]}")
                if self.pos != self.built_harvester[1]:
                    self.target = self.built_harvester[1]
                    self.explore(ct)
                    return
                self.built_harvester[1] = None

            if self.built_harvester[2] in self.mined_tit and (len(self.mined_tit) % 5) == 0 and self.try_avoid:
                if self.map[self.pos.y][self.pos.x][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.CONVEYOR, EntityType.SPLITTER] and self.map[self.pos.y][self.pos.x][2] == self.team:
                    path_dict, cost, best_end_tile = self.pathfinder(ct, self.core_pos, start=self.pos.add(self.map[self.pos.y][self.pos.x][3][0]), bridge=True, avoid=True)
                else:
                    path_dict, cost, best_end_tile = self.pathfinder(ct, self.core_pos, bridge=True, avoid=True)
            else:
                if self.map[self.pos.y][self.pos.x][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.CONVEYOR, EntityType.SPLITTER]:
                    path_dict, cost, best_end_tile = self.pathfinder(ct, self.core_pos, start=self.pos.add(self.map[self.pos.y][self.pos.x][3][0]), bridge=True)
                else:
                    path_dict, cost, best_end_tile = self.pathfinder(ct, self.core_pos, bridge=True)
            if path_dict == None:
                self.pathfinder_fail_count += 1
                if self.pathfiner_fail_count > 5:
                    if self.try_avoid:
                        self.try_avoid = False
                    else:
                        self.try_avoid = True
                        self.ore_target = None
                        self.built_harvester = [False, None, None]
                        if ore in self.tit:
                            self.tit.remove(ore)
                        elif ore in self.ax:
                            self.ax.remove(ore)
                        else:
                            print("ore is not in tit or ax!")
                    self.pathfinder_fail_count = 0
                return

            # Check if a path exists to core
            if best_end_tile != self.core_pos:
                # No path exists!
                print("No path home exists!")
                #ct.resign()     # PROBLEM
                if self.try_avoid:
                    self.try_avoid = False
                else:
                    self.try_avoid = True
                    self.ore_target = None
                    self.built_harvester = [False, None, None]
                    self.pathfinder_fail_count = 0
                    if ore in self.tit:
                        self.tit.remove(ore)
                    elif ore in self.ax:
                        self.ax.remove(ore)
                    else:
                        print("ore is not in tit or ax!")
                return
            path = self.reconstruct_path(path_dict, best_end_tile)
            ct.draw_indicator_line(path[1], path[0], 0, 0, 0)

            # Now find conveyor route to next best bridge location
            if self.built_harvester[2] in self.mined_tit and (len(self.mined_tit) % 5) == 0 and self.try_avoid:
                path_dict, cost, best_end_tile = self.pathfinder(ct, path[1], path[0], conv=True, avoid=True)
            else:
                path_dict, cost, best_end_tile = self.pathfinder(ct, path[1], path[0], conv=True)
            if path_dict == None:
                return
            print(f"Bridge cost: {ct.get_bridge_cost()}, Conveyor cost: {cost[best_end_tile] * ct.get_conveyor_cost()}")
            if best_end_tile != path[1] or ct.get_bridge_cost()[0] < cost[best_end_tile] * ct.get_conveyor_cost()[0] :
                print("Bridge Path is Better!")
                if self.map[path[0].y][path[0].x][2] != self.team:
                    move_dir = self.pos.direction_to(path[0])
                    if ct.can_move(move_dir) and self.pos != path[0]:
                        ct.move(move_dir)
                if ct.can_fire(path[0]) and self.map[path[0].y][path[0].x][2] != self.team:
                    ct.fire(path[0])
                elif ct.can_destroy(path[0]) and not (self.map[path[0].y][path[0].x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.SPLITTER, EntityType.BRIDGE, EntityType.FOUNDRY, EntityType.HARVESTER] and self.map[path[0].y][path[0].x][2] == self.team):
                    ct.destroy(path[0])
                if ct.can_build_bridge(path[0], path[1]):
                    ct.build_bridge(path[0], path[1])
                    self.built_harvester[1] = path[1]
                elif self.map[path[0].y][path[0].x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.SPLITTER, EntityType.BRIDGE] and self.map[path[0].y][path[0].x][2] == self.team:
                    move_dir = self.pos.direction_to(path[0])
                    if ct.can_move(move_dir):
                        ct.move(move_dir)
                elif ct.get_bridge_cost()[0] > ct.get_global_resources()[0]:
                    print("Waiting for money to build bridge")
                    return
            else:
                print("conveyor is better")
                path = self.reconstruct_path(path_dict, best_end_tile)
                conveyor_dir = path[0].direction_to(path[1])
                if self.map[path[0].y][path[0].x][2] != self.team:
                    move_dir = self.pos.direction_to(path[0])
                    if ct.can_move(move_dir):
                        ct.move(move_dir)
                if ct.can_fire(path[0]) and self.map[path[0].y][path[0].x][2] != self.team:
                    ct.fire(path[0])
                elif ct.can_destroy(path[0]) and not (self.map[path[0].y][path[0].x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.SPLITTER, EntityType.BRIDGE, EntityType.FOUNDRY, EntityType.HARVESTER] and self.map[path[0].y][path[0].x][2] == self.team):
                    ct.destroy(path[0])
                if not (self.built_harvester[2] in self.mined_tit and len(self.mined_tit) > 12 and self.try_avoid) and len(path) >= 2 and self.map[path[1].y][path[1].x][1] == EntityType.CORE:
                    splitter_dir = self.pos.direction_to(path[0])
                    if ct.can_build_splitter(path[0], splitter_dir):
                        ct.build_splitter(path[0], splitter_dir)
                        print("Path Building Complete")
                        self.mined_tit_count += 1
                        self.built_harvester = [False, None, None]
                        self.ore_target = None
                        self.pathfinder_fail_count = 0
                        self.try_avoid = True
                        return
                    elif ct.get_splitter_cost()[0] > ct.get_global_resources()[0]:
                        print("Waiting for money to build splitter")
                        return
                    '''for d in STRAIGHTS:
                        yy = path[0].add(d).y
                        xx = path[0].add(d).x
                        if 0 <= yy < len(self.map) and 0 <= xx < len(self.map[0]) and self.map[yy][xx][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR]:
                            direction = self.map[path[0].add(d).y][path[0].add(d).x][3][0]
                            if ct.can_build_splitter(path[0],direction):
                                ct.build_splitter(path[0], direction)
                                print("Path Building Complete")
                                self.built_harvester = [False, None, None]
                                self.ore_target = None
                                self.pathfinder_fail_count = 0
                                self.try_avoid = True
                                return
                            elif ct.get_splitter_cost()[0] > ct.get_global_resources()[0]:
                                print("Waiting for money to build splitter")
                                return
                    print("Coming from bridge")
                    #return
                    # Splitter from bridge
                    for d in STRAIGHTS:
                        yy = path[0].add(d).y
                        xx = path[0].add(d).x
                        if 0 <= yy < len(self.map) and 0 <= xx < len(self.map[0]) and self.map[yy][xx][1] == EntityType.CORE:
                            direction = d
                            if ct.can_build_splitter(path[0],direction):
                                ct.build_splitter(path[0], direction)
                                print("Path Building Complete")
                                self.built_harvester = [False, None, None]
                                self.ore_target = None
                                self.pathfinder_fail_count = 0
                                self.try_avoid = True
                                return
                            elif ct.get_splitter_cost()[0] > ct.get_global_resources()[0]:
                                print("Waiting for money to build splitter")
                                return'''

                if ct.can_build_conveyor(path[0], conveyor_dir):
                    if self.map[path[1].y][path[1].x][1] == EntityType.SPLITTER and self.map[path[1].y][path[1].x][3][0] != conveyor_dir:
                        if ct.can_build_bridge(path[0], path[1]):
                            ct.build_bridge(path[0], path[1])
                            self.built_harvester[1] = path[1]
                    else:
                        ct.build_conveyor(path[0], conveyor_dir)
                        move_dir = self.pos.direction_to(path[0])
                        if ct.can_move(move_dir):
                            ct.move(move_dir)
                        else:
                            self.built_harvester[1] = path[0]
                elif self.map[path[0].y][path[0].x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.SPLITTER, EntityType.BRIDGE] and self.map[path[0].y][path[0].x][2] == self.team:
                    move_dir = self.pos.direction_to(path[0])
                    if ct.can_move(move_dir):
                        ct.move(move_dir)
                elif ct.get_conveyor_cost()[0] > ct.get_global_resources()[0]:
                    print("Waiting for money to build conveyor")
                    return

            if self.map[path[1].y][path[1].x][1] in [EntityType.CORE, EntityType.SPLITTER, EntityType.ARMOURED_CONVEYOR, EntityType.CONVEYOR, EntityType.BRIDGE]:
                print("Path Building Complete")
                self.mined_tit_count += 1
                self.built_harvester = [False, None, None]
                self.ore_target = None
                self.pathfinder_fail_count = 0
                self.try_avoid = True

            # Check if path exists to core

    def pad_map(self):  # Must account for loops that run along edge of map so pad map with wall on outside

        h = len(self.map)
        w = len(self.map[0])

        padded = [[[Environment.WALL]] * (w + 2)]
        for row in self.map:
            padded.append([[Environment.WALL]] + row + [[Environment.WALL]])
        padded.append([[Environment.WALL]] * (w + 2))

        return padded
    
    def smallest_wall_loop(self, target=None):

        if target == None:
            target = self.target

        DIRS = [(1,0), (-1,0), (0,1), (0,-1)]

        grid = self.pad_map()

        h = len(grid)
        w = len(grid[0])

        target_y = target.y + 1     # + 1 is Padded grid offset
        target_x = target.x + 1

        if grid[target_y][target_x][0] != Environment.WALL:
            print(target_x, target_y)
            return None

        best_loop = None

        for dx, dy in DIRS:
            nx, ny = target_x + dx, target_y + dy

            if not (0 <= nx < w and 0 <= ny < h):
                continue

            if grid[ny][nx][0] != Environment.WALL and (len(grid[ny][nx]) < 2 or grid[ny][nx][1] not in NON_PASSABLE):
                continue

            queue = deque()
            queue.append((nx, ny, [(target_x, target_y), (nx, ny)]))
            visited = {(target_x, target_y), (nx, ny)}

            while queue:
                x, y, path = queue.popleft()

                for ddx, ddy in DIRS:
                    xx, yy = x + ddx, y + ddy

                    if not (0 <= xx < w and 0 <= yy < h):
                        continue

                    if (xx, yy) == (target_x, target_y) and len(path) >= 4:
                        loop = path + [(target_x, target_y)]
                        if best_loop is None or len(loop) < len(best_loop):
                            best_loop = loop
                        continue

                    if (xx, yy) in visited:
                        continue
                    
                    if grid[yy][xx][0] != Environment.WALL and (len(grid[yy][xx]) < 2 or grid[yy][xx][1] not in NON_PASSABLE):
                        continue

                    visited.add((xx, yy))
                    queue.append((xx, yy, path + [(xx, yy)]))

        if best_loop:
            # remove padding offset
            return [(x-1, y-1) for x, y in best_loop]

        return None
    
    def cells_inside_loop(self, loop):
        # Convert loop to set for O(1) lookup
        wall = set(loop)

        xs = [x for x, _ in loop]
        ys = [y for _, y in loop]

        min_x, max_x = min(xs) - 1, max(xs) + 1
        min_y, max_y = min(ys) - 1, max(ys) + 1

        width = max_x - min_x + 1
        height = max_y - min_y + 1

        # Track visited cells
        visited = set()

        # Flood fill starting from outside corner
        start = (min_x, min_y)
        queue = deque([start])
        visited.add(start)

        while queue:
            x, y = queue.popleft()

            for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
                nx, ny = x + dx, y + dy

                if nx < min_x or nx > max_x or ny < min_y or ny > max_y:
                    continue
                if (nx, ny) in visited:
                    continue
                if (nx, ny) in wall:
                    continue

                visited.add((nx, ny))
                queue.append((nx, ny))

        # Any cell that wasn't visited and isn't a wall is inside
        inside = []
        for y in range(min_y + 1, max_y):
            for x in range(min_x + 1, max_x):
                if (x, y) not in visited and (x, y) not in wall:
                    inside.append((x, y))

        return inside

    def find_invalid_tiles(self, ct, target=None):
        if target == None:
            target = self.target

        wall_tile_y = target.y
        wall_tile_x = target.x
        if not (wall_tile_y >= 0 and wall_tile_y < len(self.map) and wall_tile_x >= 0 and wall_tile_x < len(self.map[0])):
            print("weird bug")
            print(target)
            return
        while wall_tile_y > 0 and self.map[wall_tile_y][wall_tile_x][0] != Environment.WALL:    # Check up/north to wall or edge of map
            wall_tile_y -= 1
        if self.map[wall_tile_y][wall_tile_x][0] != Environment.WALL:
            wall_tile_y = target.y
            wall_tile_x = target.x
            while wall_tile_y < (len(self.map) - 1) and self.map[wall_tile_y][wall_tile_x][0] != Environment.WALL:    # Check down/south to wall or edge of map
                wall_tile_y += 1
            if self.map[wall_tile_y][wall_tile_x][0] != Environment.WALL:
                wall_tile_y = target.y
                wall_tile_x = target.x
                while wall_tile_x > 0 and self.map[wall_tile_y][wall_tile_x][0] != Environment.WALL:    # Check left/west to wall or edge of map
                    wall_tile_x -= 1
                if self.map[wall_tile_y][wall_tile_x][0] != Environment.WALL:
                    wall_tile_y = target.y
                    wall_tile_x = target.x
                    while wall_tile_x < (len(self.map[0]) - 1) and self.map[wall_tile_y][wall_tile_x][0] != Environment.WALL:    # Check right/east to wall or edge of map
                        wall_tile_x += 1
                    if self.map[wall_tile_y][wall_tile_x][0] != Environment.WALL:
                        print("trapped in small box. Some obscure map this is.")
                        return
                    
        #ct.draw_indicator_dot(Position(wall_tile_x, wall_tile_y), 0, 255, 0)
        wall_loop = self.smallest_wall_loop(Position(wall_tile_x, wall_tile_y))
        if wall_loop == None:
            print("No loop")
            return False
        else:
            print(wall_loop)
            for tile in wall_loop:
                ct.draw_indicator_dot(Position(tile[0], tile[1]), 255, 0, 0)
                self.unreachable_tiles.append(Position(tile[0], tile[1]))
            inside_points = self.cells_inside_loop(wall_loop)
            print(inside_points)
            for tile in inside_points:
                ct.draw_indicator_dot(Position(tile[0], tile[1]), 0, 255, 0)
                self.unreachable_tiles.append(Position(tile[0], tile[1]))
            return True

    def find_enemy_core(self, ct):
        if len(self.tit) > 0 and self.mined_tit_count == 0:
            self.find_enemy_core_target = self.target
            self.status = MINING_TITANIUM
        elif self.find_enemy_core_target != None:
            self.target = self.find_enemy_core_target
            self.find_enemy_core_target = None
        elif self.enemy_core_pos == Position(1000, 1000) and self.target != Position(1000, 1000) and self.map[self.target.y][self.target.x][0] == 0:
            self.explore(ct, self.target)
        elif self.enemy_core_pos != Position(1000, 1000):  # Report enemy core position back to core
            self.find_enemy_core_target = None
            self.status = REPORT_ENEMY_CORE_LOCATION
        elif len(self.tit + self.ax) != 0:    # Mine for ore
            self.find_enemy_core_target = None
            self.status = MINING_TITANIUM
            self.target = Position(1000, 1000)
        else:   # Explore from outside corner in
            self.find_enemy_core_target = None
            self.status = EXPLORING
            self.target = Position(1000, 1000)
        #if ct.get_current_round() > 200:
            #self.status = EXPLORING

    def transport_resources(self, ct, end, start=None):
        if start == None:
            start = self.pos
        if self.target == Position(1000, 1000):
            self.target = start
        if self.pos != self.target:
            self.explore(ct)
            return
        if self.map[self.pos.y][self.pos.x][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.CONVEYOR, EntityType.SPLITTER] and self.map[self.pos.y][self.pos.x][2] == self.team:
            path_dict, cost, best_end_tile = self.pathfinder(ct, end, start=self.pos.add(self.map[self.pos.y][self.pos.x][3][0]), bridge=True, avoid=True)
        else:
            path_dict, cost, best_end_tile = self.pathfinder(ct, end, bridge=True, avoid=True)
        if path_dict == None:
            self.pathfinder_fail_count += 1
            if self.pathfiner_fail_count > 5:
                print("NO PATH")
                self.pathfinder_fail_count = 0
            return
        path = self.reconstruct_path(path_dict, best_end_tile)
        if len(path) < 2:
            print("NO PATH", path)
            self.status = EXPLORING
            return
        path_dict, cost, best_end_tile = self.pathfinder(ct, path[1], path[0], conv=True, avoid=True)
        if best_end_tile != path[1] or ct.get_bridge_cost()[0] < cost[best_end_tile] * ct.get_conveyor_cost()[0] :
            print("Bridge Path is Better!")
            if self.map[path[0].y][path[0].x][2] != self.team:
                move_dir = self.pos.direction_to(path[0])
                if ct.can_move(move_dir) and self.pos != path[0]:
                    ct.move(move_dir)
            if ct.can_fire(path[0]) and self.map[path[0].y][path[0].x][2] != self.team:
                ct.fire(path[0])
            elif ct.can_destroy(path[0]) and not (self.map[path[0].y][path[0].x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.SPLITTER, EntityType.BRIDGE, EntityType.FOUNDRY, EntityType.HARVESTER] and self.map[path[0].y][path[0].x][2] == self.team):
                ct.destroy(path[0])
            if ct.can_build_bridge(path[0], path[1]):
                ct.build_bridge(path[0], path[1])
                self.target = path[1]
            elif self.map[path[0].y][path[0].x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.SPLITTER, EntityType.BRIDGE] and self.map[path[0].y][path[0].x][2] == self.team:
                move_dir = self.pos.direction_to(path[0])
                if ct.can_move(move_dir):
                    ct.move(move_dir)
            elif ct.get_bridge_cost()[0] > ct.get_global_resources()[0]:
                print("Waiting for money to build bridge")
                return
        else:
            print("conveyor is better")
            path = self.reconstruct_path(path_dict, best_end_tile)
            conveyor_dir = path[0].direction_to(path[1])
            if self.map[path[0].y][path[0].x][2] != self.team:
                move_dir = self.pos.direction_to(path[0])
                if ct.can_move(move_dir):
                    ct.move(move_dir)
            if ct.can_fire(path[0]) and self.map[path[0].y][path[0].x][2] != self.team:
                ct.fire(path[0])
            elif ct.can_destroy(path[0]) and not (self.map[path[0].y][path[0].x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.SPLITTER, EntityType.BRIDGE, EntityType.FOUNDRY, EntityType.HARVESTER] and self.map[path[0].y][path[0].x][2] == self.team):
                ct.destroy(path[0])
            if ct.can_build_conveyor(path[0], conveyor_dir):
                ct.build_conveyor(path[0], conveyor_dir)
                move_dir = self.pos.direction_to(path[0])
                if ct.can_move(move_dir):
                    ct.move(move_dir)
                self.target = path[0]
            elif self.map[path[0].y][path[0].x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.SPLITTER, EntityType.BRIDGE] and self.map[path[0].y][path[0].x][2] == self.team:
                move_dir = self.pos.direction_to(path[0])
                if ct.can_move(move_dir):
                    ct.move(move_dir)

    def attack_enemy_core(self, ct, close=None):
        if close == None:
            close = self.attack_enemy_core_close
        pos = self.pos
        vision_tiles = ct.get_nearby_tiles()
        list_of_gunners = []
        self.target = self.enemy_core_pos
        if self.pos.distance_squared(self.enemy_core_pos) <= 50:
            for i in vision_tiles:
                if self.map[i.y][i.x][1] in [EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR]:
                    if self.map[i.y][i.x][1] == EntityType.BRIDGE:
                        building_target = ct.get_bridge_target(ct.get_tile_building_id(i))
                        if building_target in vision_tiles:
                            target_type = ct.get_entity_type(ct.get_tile_building_id(building_target))
                            target_team = ct.get_team(ct.get_tile_building_id(building_target))
                            if target_type in [EntityType.GUNNER, EntityType.SENTINEL] and target_team == self.team:
                                building_target = None
                                continue
                            elif target_type in NON_PASSABLE or target_type == EntityType.CORE or (ct.get_tile_builder_bot_id(building_target) != None and pos != building_target):
                                if ct.get_tile_builder_bot_id(i) == None or pos == i:
                                    building_target = i
                                else:
                                    building_target = None
                                    continue
                    else:
                        building_target = i.add(ct.get_direction(ct.get_tile_building_id(i)))
                        if building_target in vision_tiles:
                            target_type = ct.get_entity_type(ct.get_tile_building_id(building_target))
                            target_team = ct.get_team(ct.get_tile_building_id(building_target))
                            if target_type in [EntityType.GUNNER, EntityType.SENTINEL] and target_team == self.team:
                                building_target = None
                                continue
                            elif target_type in NON_PASSABLE or target_type == EntityType.CORE or (ct.get_tile_builder_bot_id(building_target) != None and pos != building_target):
                                if ct.get_tile_builder_bot_id(i) == None or pos == i:
                                    building_target = i
                                else:
                                    building_target = None
                                    continue

                    if building_target != None and ct.is_in_vision(building_target) and (ct.get_tile_builder_bot_id(building_target) == None or pos == building_target) and (ct.is_tile_passable(building_target) or building_target == pos or ct.get_tile_building_id(building_target) is None) and building_target.distance_squared(self.enemy_core_pos) <= 32:
                       if (close and building_target.distance_squared(self.enemy_core_pos) < self.target.distance_squared(self.enemy_core_pos)) or (not close and building_target.distance_squared(self.enemy_core_pos) > self.target.distance_squared(self.enemy_core_pos)) or self.target == self.enemy_core_pos:
                            end, own_team = self.simple_supply_connectivity(ct, building_target)
                            if not (end != None and own_team == True):
                                self.target = building_target

                elif self.map[i.y][i.x][1] in [EntityType.SPLITTER]:
                    splitter_outs = [i.add(ct.get_direction(ct.get_tile_building_id(i))), i.add(ct.get_direction(ct.get_tile_building_id(i)).rotate_left().rotate_left()), i.add(ct.get_direction(ct.get_tile_building_id(i)).rotate_right().rotate_right())]
                    for building_target in splitter_outs:
                        if building_target not in ct.get_nearby_tiles():
                            continue
                        target_type = ct.get_entity_type(ct.get_tile_building_id(building_target))
                        target_team = ct.get_team(ct.get_tile_building_id(building_target))
                        if target_type in [EntityType.GUNNER, EntityType.SENTINEL] and target_team == self.team:
                            building_target = None
                            continue
                        elif target_type in NON_PASSABLE or target_type == EntityType.CORE or (ct.get_tile_builder_bot_id(building_target) != None and pos != building_target):
                            if ct.get_tile_builder_bot_id(i) == None or pos == i:
                                    building_target = i
                            else:
                                building_target = None
                                continue
                        if building_target != None and ct.is_in_vision(building_target) and (ct.get_tile_builder_bot_id(building_target) == None or pos == building_target) and self.map[building_target.y][building_target.x][0] != Environment.WALL and (ct.is_tile_passable(building_target) or building_target == pos or ct.get_tile_building_id(building_target) is None) and building_target.distance_squared(self.enemy_core_pos) <= 32:
                            
                            if (close and building_target.distance_squared(self.enemy_core_pos) < self.target.distance_squared(self.enemy_core_pos)) or (not close and building_target.distance_squared(self.enemy_core_pos) > self.target.distance_squared(self.enemy_core_pos)) or self.target == self.enemy_core_pos:
                                end, own_team = self.simple_supply_connectivity(ct, building_target)
                                if not (end != None and own_team == True):
                                    self.target = building_target

                elif ct.get_entity_type(ct.get_tile_building_id(i)) in [EntityType.GUNNER]:
                    list_of_gunners.append(i)

            print("Choosing", self.target)
            '''
            if self.target != self.enemy_core_pos:
                pass

            for i in list_of_gunners:
                for d in DIRECTIONS:
                    if ct.is_in_vision(i.add(d)) and ct.get_entity_type(ct.get_tile_building_id(i.add(d))) in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR]:
                        building_target = i.add(d).add(ct.get_direction(ct.get_tile_building_id(i)))

                        if ct.is_in_vision(building_target) and building_target == i and (ct.is_passable(i.add(d)) or pos == i.add(d)):
                            if building_target.distance_squared(pos) < self.target.distance_squared(pos) or self.target == self.enemy_core_pos:
                                print("SPLITTER?")
                                print(building_target)
                                self.target = building_target
            '''
            if 0 < self.pos.distance_squared(self.target) <= 2 and self.map[self.target.y][self.target.x][1] not in [EntityType.SENTINEL, EntityType.GUNNER]:
                if ct.can_destroy(self.target):
                    ct.destroy(self.target)
            if self.pos == self.target:
                if ct.can_destroy(self.target):
                    ct.destroy(self.target)
                elif ct.can_fire(self.target):
                    self.attack_enemy_core_timer += 1
                    if self.attack_enemy_core_timer > 50:
                        self.attack_enemy_core_timer = 0
                        if self.attack_enemy_core_close:
                            self.attack_enemy_core_close = False
                        else:
                            self.attack_enemy_core_close = True
                        return
                    ct.fire(self.target)
                if ct.get_entity_type(ct.get_tile_building_id(self.pos)) not in [EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.ROAD, EntityType.SPLITTER]:
                    print("Moving away")
                    for i in DIRECTIONS:
                        if ct.can_move(i):
                            ct.move(i)
                            if self.target.distance_squared(self.enemy_core_pos) < 5 and ct.can_build_gunner(self.target, self.target.direction_to(self.enemy_core_pos)):
                                print("WOAH")
                                ct.build_gunner(self.target, self.target.direction_to(self.enemy_core_pos))
                                self.attack_enemy_core_timer = 0
                            return
                else:
                    return

            elif ct.get_position().distance_squared(self.enemy_core_pos) <= 8 and ct.get_position().distance_squared(self.target) <= 2 and ct.can_build_gunner(self.target, self.target.direction_to(self.enemy_core_pos)):
                ct.build_gunner(self.target, self.target.direction_to(self.enemy_core_pos))
                self.attack_enemy_core_timer = 0
                return
            elif ct.get_position().distance_squared(self.enemy_core_pos) > 8 and ct.get_position().distance_squared(self.target) <= 2 and ct.can_build_sentinel(self.target, self.target.direction_to(self.enemy_core_pos)):
                ct.build_sentinel(self.target, self.target.direction_to(self.enemy_core_pos))
                self.attack_enemy_core_timer = 0
                return

            if not (self.pos.distance_squared(self.target) <= 2 and (ct.get_tile_building_id(self.target) == None or (ct.get_tile_building_id(self.target) != None and ct.get_team(ct.get_tile_building_id(self.target)) == self.team))):
                self.explore(ct)
                return

            '''vision_tiles = ct.get_nearby_tiles()
            random.shuffle(vision_tiles)
            for i in vision_tiles:
                if ct.is_tile_passable(i) and i.distance_squared(self.enemy_core_pos) < 9:
                    self.target = i
                    self.explore(ct)
                    self.target = self.enemy_core_pos
                    return
            else:
                print("CRY")'''
            
    def attack_enemy_supply_lines_V2(self, ct):
        if (self.target == Position(1000, 1000) or self.target == self.enemy_core_pos) and len(self.enemy_mined_tit) != 0:
            self.target = self.enemy_mined_tit[0]
            self.enemy_mined_tit_target = self.enemy_mined_tit[0]
        elif self.target == self.enemy_core_pos and self.enemy_core_pos.distance_squared(self.pos) > 20:
            self.explore(ct)
            return
        elif len(self.enemy_mined_tit) == 0:
            if len(self.attacked_enemy_mined_tit) > 0 and self.pos.distance_squared(self.enemy_core_pos) > 15**2:
                self.status = MINING_TITANIUM
                self.target = Position(1000, 1000)
                return
            self.circling_count += 1
            if self.circling_count <= 50:
                self.enemy_mined_tit_target = None
                self.explore_start = self.enemy_core_pos
                self.exploring_the_map(ct, self.enemy_core_pos)
                return
            else:
                self.status = ATTACK_ENEMY_CONVEYORS
        elif self.enemy_mined_tit_target == None:   # Robust check
            if len(self.enemy_mined_tit) != 0:
                self.target = self.enemy_mined_tit[0]
                self.enemy_mined_tit_target = self.enemy_mined_tit[0]
            else:
                self.explore_start = self.enemy_core_pos
                self.exploring_the_map(ct, self.enemy_core_pos)
                return
        if self.target.distance_squared(self.pos) > 8:
            self.explore(ct)
        print(self.target)
        target_tile_1 = []
        target_tile_2 = []
        enemy_supply = False
        if self.target in self.enemy_mined_tit:
            checks = [(-1, 0), (1, 0), (0, -1), (0, 1)]
            for check in checks:
                # If a clear space or own building that can be removed then just go for it
                dx = self.target.x + check[0]
                dy = self.target.y + check[1]
                pos = Position(dx, dy)
                if not (dx >= 0 and dx < len(self.map[0]) and dy >= 0 and dy < len(self.map) and pos not in self.unreachable_tiles and self.map[dy][dx][0] != Environment.WALL and self.map[dy][dx][0] != 0):
                    continue
                if pos == self.prev_fire[0] and ct.get_tile_building_id(self.prev_fire[0]) != None and ct.get_hp(ct.get_tile_building_id(self.prev_fire[0])) > self.prev_fire[1]:
                    continue
                tile = self.map[dy][dx]
                if tile[1] == None or (tile[2] == self.team and tile[1] in [EntityType.BARRIER, EntityType.ROAD]):
                    target_tile_1.append(pos)
                # If an enemy supply line or road it can be used but continue checking for better tiles
                elif tile[1] in [EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.ROAD, EntityType.SPLITTER] and tile[2] != ct.get_team():
                    target_tile_2.append(pos)
                    if tile[1] != EntityType.ROAD:
                        if tile[1] in [EntityType.CONVEYOR, EntityType.SPLITTER]:
                            enemy_supply = pos.add(tile[3][0])
                        else:   # Bridge
                            enemy_supply = tile[3][0]
                elif tile[4] != None and ct.get_team(ct.get_tile_builder_bot_id(pos)) != self.team:
                    enemy_supply = pos
            self.target = Position(1000, 1000)
            if enemy_supply == False:
                self.enemy_supply = None
                self.enemy_mined_tit.remove(self.enemy_mined_tit_target)
                self.attacked_enemy_mined_tit.append(self.enemy_mined_tit_target)
                self.enemy_mined_tit_target = None
                self.target = self.enemy_core_pos
                if len(self.enemy_mined_tit) == 0:
                    self.target = Position(1000, 1000)
                return
            elif len(target_tile_1) + len(target_tile_2) == 0:
                self.enemy_supply = None
                self.attack_enemy_conveyors(ct)
                self.target == Position(1000, 1000)
                return    # Attack enemy conveyors
            else:
                for tile in target_tile_1:  # Prevents sentinel from pointing into harvester as it cannot receive supply
                    if tile.direction_to(enemy_supply) != tile.direction_to(self.enemy_mined_tit_target):
                        self.target = tile
                        break
                if self.target == Position(1000, 1000):
                    for tile in target_tile_2:
                        if tile.direction_to(enemy_supply) != tile.direction_to(self.enemy_mined_tit_target):
                            self.target = tile
                            break
                if self.target == Position(1000, 1000):
                    self.enemy_supply = None
                    self.attack_enemy_conveyors(ct)
                    return    # Attack enemy conveyors
                self.enemy_supply = enemy_supply
        print(self.target)
        if 0 < self.pos.distance_squared(self.target) <= 2 and (self.map[self.target.y][self.target.x][1] == None or (self.map[self.target.y][self.target.x][2] == self.team and self.map[self.target.y][self.target.x][1] in [EntityType.ROAD, EntityType.BARRIER]) ):
            if ct.can_destroy(self.target):
                ct.destroy(self.target)
            print("Want to build sentinel", self.target)
            if ct.can_build_sentinel(self.target, self.target.direction_to(self.enemy_supply)): # Should check money first
                ct.build_sentinel(self.target, self.target.direction_to(self.enemy_supply))
                print(self.enemy_supply)
                self.enemy_mined_tit.remove(self.enemy_mined_tit_target)
                self.attacked_enemy_mined_tit.append(self.enemy_mined_tit_target)
                self.enemy_mined_tit_target = None
                self.target = self.enemy_core_pos
                self.enemy_supply = None
                if len(self.enemy_mined_tit) == 0:
                    self.target = Position(1000, 1000)
                return
        elif self.pos == self.target:
            if self.map[self.target.y][self.target.x][1] == None:   # Move out of way and build sentinel
                for d in DIRECTIONS:
                    if ct.can_build_road(self.pos.add(d)):
                        ct.build_road(self.pos.add(d))
                    if ct.can_move(d):
                        ct.move(d)
                        break
                if ct.can_build_sentinel(self.target, self.target.direction_to(self.enemy_supply)): # Should check money first
                    ct.build_sentinel(self.target, self.target.direction_to(self.enemy_supply))
                    print(self.enemy_supply)
                    self.enemy_mined_tit.remove(self.enemy_mined_tit_target)
                    self.attacked_enemy_mined_tit.append(self.enemy_mined_tit_target)
                    self.enemy_mined_tit_target = None
                    self.target = self.enemy_core_pos
                    self.enemy_supply = None
                    if len(self.enemy_mined_tit) == 0:
                        self.target = Position(1000, 1000)
                    return
            elif ct.can_fire(self.target):
                if self.prev_fire[0] == None or (self.prev_fire[0] == self.target and ct.get_hp(ct.get_tile_building_id(self.target)) <= self.prev_fire[1]):
                    ct.fire(self.target)
                    if ct.get_tile_building_id(self.target) != None:
                        self.prev_fire[0] = self.target
                        self.prev_fire[1] = ct.get_hp(ct.get_tile_building_id(self.target))
                    else:
                        self.prev_fire = [None, None]
                else:
                    self.target = self.enemy_mined_tit_target
        elif 0 < self.pos.distance_squared(self.target) <= 20 and self.map[self.target.y][self.target.x][2] == self.team and self.map[self.target.y][self.target.x][1] in [EntityType.SENTINEL, EntityType.GUNNER, EntityType.BREACH]:
            self.enemy_mined_tit.remove(self.enemy_mined_tit_target)
            self.attacked_enemy_mined_tit.append(self.enemy_mined_tit_target)
            self.enemy_mined_tit_target = None
            self.target = self.enemy_core_pos
            if len(self.enemy_mined_tit) == 0:
                self.target = Position(1000, 1000)
            return
        # Non-passable enemy tile built on target tile or own building that do not want to destroy
        elif 0 < self.pos.distance_squared(self.target) <= 20 and ((self.map[self.target.y][self.target.x][2] != self.team and self.map[self.target.y][self.target.x][1] not in [EntityType.ROAD, EntityType.CONVEYOR, EntityType.SPLITTER, EntityType.BRIDGE]) or (self.map[self.target.y][self.target.x][2] in [self.team, None] and self.map[self.target.y][self.target.x][1] not in [EntityType.BARRIER, EntityType.MARKER, EntityType.ROAD, None])):
            self.target = self.enemy_mined_tit_target
        elif (self.pos != self.target and self.map[self.target.y][self.target.x][2] != ct.get_team()) or (self.pos.distance_squared(self.target) > 2 and (self.map[self.target.y][self.target.x][2] == self.team or self.map[self.target.y][self.target.x][1] == None)):
            self.explore(ct)

    def attack_enemy_conveyors(self, ct):
        print("Attacking enemy conveyors")
        # This if may need more checks for safety
        if self.target != Position(1000, 1000) and self.map[self.target.y][self.target.x][1] not in [EntityType.CONVEYOR, EntityType.SPLITTER, EntityType.BRIDGE, EntityType.BARRIER]:
            if self.pos.distance_squared(self.target) > 2:
                self.explore(ct)
            elif self.pos == self.target:   # Not doing firing stuff as probably better to just go and attack other conveyors
                for d in DIRECTIONS:
                    if ct.can_build_road(self.pos.add(d)):
                        ct.build_road(self.pos.add(d))
                    if ct.can_move(d):
                        ct.move(d)
                        break
            if ct.can_destroy(self.target): # May need more checks
                ct.destroy(self.target)
            if ct.get_barrier_cost()[0] >= ct.get_global_resources()[0]:
                if ct.can_build_barrier(self.target):
                    ct.build_barrier(self.target)
                self.target = Position(1000, 1000)
            return
        vision_tiles = self.centre_vision(self.pos, 20)
        supply_target = None
        for tile in vision_tiles:
            map_tile = self.map[tile[1]][tile[0]]
            pos = Position(tile[0], tile[1])
            if not self.is_on_map(Position(tile[0], tile[1])) or (self.prev_fire[0] != None and pos.distance_squared(self.prev_fire[0]) <= 8 and self.pos.distance_squared(self.prev_fire[0]) <= 8 and ct.get_hp(ct.get_tile_building_id(self.prev_fire[0])) > self.prev_fire[1]):
                continue
            if map_tile[1] in [EntityType.CONVEYOR, EntityType.SPLITTER, EntityType.BRIDGE] and map_tile[2] != self.team:
                end, team = self.simple_supply_connectivity(ct, pos)
                if end != None and team == False:
                    if supply_target == None or self.pos.distance_squared(pos) < self.pos.distance_squared(supply_target):
                        supply_target = pos
        if supply_target == None:
            self.target = Position(1000, 1000)
            if self.enemy_core_pos == Position(1000, 1000):
                self.explore_start = None
                self.exploring_the_map(ct)
            else:
                self.explore_start = self.enemy_core_pos
                self.exploring_the_map(ct, self.enemy_core_pos)
            return
        self.target = supply_target
        if self.pos != self.target:
            self.explore(ct)
            return
        if self.map[self.target.y][self.target.x][1] in [EntityType.CONVEYOR, EntityType.SPLITTER, EntityType.BRIDGE] and self.map[self.target.y][self.target.x][2] != self.team:
            if ct.can_fire(self.target):
                if self.prev_fire[0] == None or (self.prev_fire[0] == self.target and ct.get_hp(ct.get_tile_building_id(self.target)) <= self.prev_fire[1]):
                    ct.fire(self.target)
                    if ct.get_tile_building_id(self.target) != None:
                        self.prev_fire[0] = self.target
                        self.prev_fire[1] = ct.get_hp(ct.get_tile_building_id(self.target))
                    else:
                        self.prev_fire = [None, None]
                        for d in DIRECTIONS:
                            if ct.can_build_road(self.pos.add(d)):
                                ct.build_road(self.pos.add(d))
                            if ct.can_move(d):
                                ct.move(d)
                                break
                        if ct.can_build_barrier(self.target):   # May need to modify to always build a barrier
                            ct.build_barrier(self.target)
                            self.target = Position(1000, 1000)
                else:
                    pass
        else:
            self.target = Position(1000, 1000)
            
    def attack_enemy_supply_lines(self, ct):
        if self.enemy_core_pos == Position(1000, 1000): # Do not really need this
            self.target = Position(1000, 1000)
            self.status = EXPLORING
            self.explore_start = None
            return
        if (self.target == Position(1000, 1000) or self.target == self.enemy_core_pos) and len(self.enemy_mined_tit) != 0:
            self.target = self.enemy_mined_tit[0]
            self.enemy_mined_tit_target = self.enemy_mined_tit[0]
        elif self.target == self.enemy_core_pos and self.enemy_core_pos.distance_squared(self.pos) > 20:
            self.explore(ct)
            return
        elif len(self.enemy_mined_tit) == 0:
            self.enemy_mined_tit_target = None
            self.explore_start = self.enemy_core_pos
            self.exploring_the_map(ct, self.enemy_core_pos)
            return
        elif self.enemy_mined_tit_target == None:   # Robust check
            if len(self.enemy_mined_tit) != 0:
                self.target = self.enemy_mined_tit[0]
                self.enemy_mined_tit_target = self.enemy_mined_tit[0]
            else:
                self.explore_start = self.enemy_core_pos
                self.exploring_the_map(ct, self.enemy_core_pos)
                return
        if self.target.distance_squared(self.pos) > 8:
            self.explore(ct)
        print(self.target)
        target_tile = None
        if self.target in self.enemy_mined_tit:
            checks = [(-1, 0), (1, 0), (0, -1), (0, 1)]
            for check in checks:
                # If a clear space or own building that can be removed then just go for it
                dx = self.target.x + check[0]
                dy = self.target.y + check[1]
                pos = Position(dx, dy)
                if not (dx >= 0 and dx < len(self.map[0]) and dy >= 0 and dy < len(self.map) and pos not in self.unreachable_tiles and self.map[dy][dx][0] != Environment.WALL and self.map[dy][dx][0] != 0):
                    continue
                tile = self.map[dy][dx]
                if tile[1] == None or (tile[2] == ct.get_team() and tile[1] in [EntityType.BARRIER, EntityType.ROAD]):
                    target_tile = pos
                    break
                # If an enemy supply line or road it can be used but continue checking for better tiles
                elif tile[1] in [EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.ROAD, EntityType.SPLITTER] and tile[2] != ct.get_team():
                    target_tile = pos
                elif tile[2] == ct.get_team() and tile[1] in [EntityType.SENTINEL, EntityType.GUNNER, EntityType.BREACH]:
                    self.enemy_mined_tit.remove(self.enemy_mined_tit_target)
                    self.attacked_enemy_mined_tit.append(self.enemy_mined_tit_target)
                    self.enemy_mined_tit_target = None
                    self.target = self.enemy_core_pos
                    if len(self.enemy_mined_tit) == 0:
                        self.target = Position(1000, 1000)
                        self.status = EXPLORING
                        self.explore_start = None
                    return
        if target_tile != None:
            self.target = target_tile
        print(self.target)
        if self.target in self.enemy_mined_tit:
            # Algorithm to build own supply line and connect turret to start destroying supply line
            self.enemy_mined_tit.remove(self.enemy_mined_tit_target)
            self.attacked_enemy_mined_tit.append(self.enemy_mined_tit_target)
            self.enemy_mined_tit_target = None
            self.target = self.enemy_core_pos
            if len(self.enemy_mined_tit) == 0:
                self.target = Position(1000, 1000)
                self.status = EXPLORING
                self.explore_start = None
            return
        else:
            if 0 < self.pos.distance_squared(self.target) <= 2 and (self.map[self.target.y][self.target.x][1] == None or (self.map[self.target.y][self.target.x][2] == self.team and self.map[self.target.y][self.target.x][1] in [EntityType.ROAD, EntityType.BARRIER]) ):
                if ct.can_destroy(self.target):
                    ct.destroy(self.target)
                print("Want to build sentinel", self.target)
                if ct.can_build_sentinel(self.target, self.target.direction_to(self.enemy_core_pos)): # Should check money first
                    ct.build_sentinel(self.target, self.target.direction_to(self.enemy_core_pos))
                    self.enemy_mined_tit.remove(self.enemy_mined_tit_target)
                    self.attacked_enemy_mined_tit.append(self.enemy_mined_tit_target)
                    self.enemy_mined_tit_target = None
                    self.target = self.enemy_core_pos
                    if len(self.enemy_mined_tit) == 0:
                        self.target = Position(1000, 1000)
                        self.status = EXPLORING
                        self.explore_start = None
                    return
            elif self.pos == self.target:
                if self.map[self.target.y][self.target.x][1] == None:   # Move out of way and build sentinel
                    for d in DIRECTIONS:
                        if ct.can_build_road(self.pos.add(d)):
                            ct.build_road(self.pos.add(d))
                        if ct.can_move(d):
                            ct.move(d)
                            break
                    if ct.can_build_sentinel(self.target, self.target.direction_to(self.enemy_core_pos)): # Should check money first
                        ct.build_sentinel(self.target, self.target.direction_to(self.enemy_core_pos))
                        self.enemy_mined_tit.remove(self.enemy_mined_tit_target)
                        self.attacked_enemy_mined_tit.append(self.enemy_mined_tit_target)
                        self.enemy_mined_tit_target = None
                        self.target = self.enemy_core_pos
                        if len(self.enemy_mined_tit) == 0:
                            self.target = Position(1000, 1000)
                            self.status = EXPLORING
                            self.explore_start = None
                        return
                elif ct.can_fire(self.target):
                    ct.fire(self.target)
            elif 0 < self.pos.distance_squared(self.target) <= 20 and self.map[self.target.y][self.target.x][2] == self.team and self.map[self.target.y][self.target.x][1] in [EntityType.SENTINEL, EntityType.GUNNER, EntityType.BREACH]:
                self.enemy_mined_tit.remove(self.enemy_mined_tit_target)
                self.attacked_enemy_mined_tit.append(self.enemy_mined_tit_target)
                self.enemy_mined_tit_target = None
                self.target = self.enemy_core_pos
                if len(self.enemy_mined_tit) == 0:
                    self.target = Position(1000, 1000)
                    self.status = EXPLORING
                    self.explore_start = None
                return
            # Non-passable enemy tile built on target tile or own building that do not want to destroy
            elif 0 < self.pos.distance_squared(self.target) <= 20 and ((self.map[self.target.y][self.target.x][2] != self.team and self.map[self.target.y][self.target.x][1] not in [EntityType.ROAD, EntityType.CONVEYOR, EntityType.SPLITTER, EntityType.BRIDGE]) or (self.map[self.target.y][self.target.x][2] in [self.team, None] and self.map[self.target.y][self.target.x][1] not in [EntityType.BARRIER, EntityType.MARKER, EntityType.ROAD, None])):
                self.target = self.enemy_mined_tit_target
            elif (self.pos != self.target and self.map[self.target.y][self.target.x][2] != ct.get_team()) or (self.pos.distance_squared(self.target) > 2 and (self.map[self.target.y][self.target.x][2] == self.team or self.map[self.target.y][self.target.x][1] == None)):
                self.explore(ct)

    def moving_turret_start(self, ct, end):     # Basic, could account for own supply lines or enemies
        start = None
        for harv in self.mined_tit:
            if start == None or harv.distance_squared(end) < start.distance_squared(end):
                start = harv
        return start
    
    def moving_turret_end(self, end, start, radii):   # radii: sentinel = 32, gunners = 9

        vision = self.centre_vision(end, radii)
        result = None

        for coord in vision:

            tile = self.map[coord[1]][coord[0]]
            if tile[0] != Environment.WALL and (tile[2] == None or (tile[2] != self.team and tile[1] in [EntityType.ROAD, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.MARKER]) or (tile[2] == self.team and tile[1] not in [EntityType.HARVESTER, EntityType.FOUNDRY, EntityType.CORE])):
                if result == None or self.tuple_distance_squared(start, (coord[0], coord[1])) < self.tuple_distance_squared(start, result):
                    result = (coord[0], coord[1])

        return result
    
    def centre_vision(self, centre, radii):    # Pass centre tuple; radii: sentinel = 32, gunners = 9, builder bot = 20
        result = []
        rootRadii = int(radii**0.5)
        width = len(self.map[0])
        height = len(self.map)

        for dx in range(-rootRadii, rootRadii+1):
            for dy in range(-rootRadii, rootRadii+1):
                if dx*dx + dy*dy <= radii:
                    x = centre[0] + dx
                    y = centre[1] + dy
                    if not (0 <= x < width):
                        continue
                    if not (0 <= y < height):
                        continue
                    result.append((x, y))
        
        return result   # Return list of tuples representing all tiles on map within a radii of a centre point

    def moving_turret(self, ct, end, start=None):
        if start == None:
            start = self.moving_turret_start(ct, end)
            if start == None:
                print("No start position")
                self.moving_turret_supply = False
                return

        radii = 32
        end_pos = self.moving_turret_end(end, (start.x, start.y), radii) # Sentinel
        if end_pos == None:
            print("No end position")
            self.moving_turret_supply = False
            return
        
        if not self.moving_turret_supply:
            if self.map[start.y][start.x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR]:
                if self.pos != start:
                    self.target = start
                    self.explore(ct)
                    return
            elif self.map[start.y][start.x][1] == EntityType.BRIDGE:
                if self.pos != self.map[start.y][start.x][3][0]:
                    self.target = self.map[start.y][start.x][3][0]
                    self.explore(ct)
                    return
            elif self.map[start.y][start.x][1] in [EntityType.HARVESTER, EntityType.FOUNDRY, EntityType.SPLITTER]:
                width = len(self.map[0])
                height = len(self.map)
                target = None
                for d in STRAIGHTS:
                    check = start.add(d)
                    if not (0 <= start.x < width and 0 <= start.y < height):
                        continue
                    tile = self.map[check.y][check.x]
                    if tile[0] == Environment.WALL:
                        continue
                    if tile[1] == None:
                        target = check
                        break
                    elif tile[1] in [EntityType.ROAD, EntityType.BARRIER] and tile[2] == self.team:
                        target = check
                    elif tile[1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and target == None:
                        target = check
                if target == None:
                    print("No end position")
                    return
                self.target = target
                if self.map[self.target.y][self.target.x][1] == EntityType.BARRIER and self.pos.distance_squared(self.target) > 2:
                    self.explore(ct)
                    return
                elif self.map[self.target.y][self.target.x][1] != EntityType.BARRIER and self.pos != self.target:
                    self.explore(ct)
                    return
            if self.pos == self.target or (self.map[self.target.y][self.target.x][1] == EntityType.BARRIER and self.pos.distance_squared(self.target) <= 2):
                if self.map[self.target.y][self.target.x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and self.map[self.target.y][self.target.x][2] == self.team:
                    if ct.can_destroy(self.target) and ct.get_splitter_cost()[0] > ct.get_global_resources()[0]:
                        ct.destroy(self.target)
                        if ct.can_build_splitter(self.target, self.map[self.target.y][self.target.x][3][0]):    # Can do this as map only updates at start of turn
                            ct.build_splitter(self.target, self.map[self.target.y][self.target.x][3][0])        # Will now run through above again to decide where to start conveyor path
                        else:
                            print("CANNOT BUILD SPLITTER")
                        return
                elif ct.can_destroy(self.target):
                    ct.destroy(self.target)
                    return
                elif ct.can_fire(self.target):
                    ct.fire(self.target)
                    return
                elif self.map[self.target.y][self.target.x][1] == None:
                    self.moving_turret_supply = True
        
        # LOOK AT VISION RADIUS FOR ENEMY TILES (USE FUNCTION JUST ABOVE FOR THIS NOT CT ONE)
        # IF ENEMY TURRETS OR SUPPLY LINES THEN BUILD SENTINEL TO DESTROY THEM AT END OF MOVING TURRET PATH (OBVIOUSLY JUST WAIT IF THERE IS ALREADY A SENTINEL)
        # IF AT ENEMY CORE THEN BUILD TURRET AND MOVE ON
        bot_vision = self.centre_vision(self.pos, 20)
        sentinel_target = None
        for coord in bot_vision:
            print(coord)
            tile = self.map[coord[1]][coord[0]]
            if tile[1] == EntityType.SENTINEL and tile[2] != self.team and self.pos in ct.get_attackable_tiles_from(Position(coord[0], coord[1]), tile[3][0], EntityType.SENTINEL):
                sentinel_target = coord
                break
            elif tile[1] in [EntityType.SENTINEL, EntityType.GUNNER, EntityType.BREACH, EntityType.LAUNCHER] and tile[2] != self.team:
                sentinel_target = coord
            elif sentinel_target == None and tile[1] in [EntityType.ARMOURED_CONVEYOR, EntityType.CONVEYOR, EntityType.BRIDGE, EntityType.SPLITTER, EntityType.FOUNDRY, EntityType.BARRIER] and tile[2] != self.team:
                sentinel_target = coord
        if sentinel_target == None:
            if (end.x, end.y) in self.centre_vision(self.pos, 20) and self.map[end.y][end.x][2] != self.team:
                sentinel_target = Position(end.x, end.y)
            elif (end.x, end.y) in self.centre_vision(self.pos, 20) and not self.map[end.y][end.x][2] != self.team:
                self.moving_turret_supply = False
                self.status = ATTACK_ENEMY_CORE # Temporary, should have more checks
                return
            else:
                if self.map[self.target.y][self.target.x][1] == EntityType.SENTINEL and self.map[self.target.y][self.target.x][2] == self.team:
                    if self.pos.distance_squared(self.target) > 2:
                        self.explore(ct)
                    if ct.can_destroy(self.target):
                        ct.destroy(self.target)
                        self.transport_resources(ct, Position(end_pos[0], end_pos[1]))
                    return
                elif self.map[self.target.y][self.target.x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR]:
                    possible_sentinel_pos = self.target.add(self.map[self.target.y][self.target.x][3][0])
                    if self.map[possible_sentinel_pos.y][possible_sentinel_pos.x][1] == EntityType.SENTINEL and self.map[possible_sentinel_pos.y][possible_sentinel_pos.x][2] == self.team:
                        if self.pos.distance_squared(possible_sentinel_pos) > 2:
                            temp = self.target
                            self.target = possible_sentinel_pos
                            self.explore(ct)
                            self.target = temp
                        if ct.can_destroy(possible_sentinel_pos):
                            ct.destroy(possible_sentinel_pos)
                            self.transport_resources(ct, Position(end_pos[0], end_pos[1]))
                    else:
                        self.transport_resources(ct, Position(end_pos[0], end_pos[1]))
                    return
                else:
                    self.transport_resources(ct, Position(end_pos[0], end_pos[1]))
                    return
        else:
            sentinel_target = Position(sentinel_target[0], sentinel_target[1])
        print(sentinel_target)
        if self.map[self.target.y][self.target.x][1] in [None, EntityType.ROAD] and self.pos == self.target:
            for d in DIRECTIONS:    # Try to move without building first so that can build sentinel on same turn
                next = self.pos.add(d)
                vision_next = self.centre_vision((next.x, next.y), 20)
                if (sentinel_target.x, sentinel_target.y) in vision_next:
                    if ct.can_move(d):
                        ct.move(d)
                        break
            if self.pos == self.target: # If could not move without building then build sentinel on next turn
                for d in DIRECTIONS:
                    next = self.pos.add(d)
                    vision_next = self.centre_vision((next.x, next.y), 20)
                    if (sentinel_target.x, sentinel_target.y) in vision_next:
                        if ct.can_build_road(self.pos.add(d)):
                            ct.build_road(self.pos.add(d))
                        if ct.can_move(d):
                            ct.move(d)
                            break
            if self.pos == self.target and ct.get_road_cost()[0] > ct.get_global_resources()[0]: # If could not move then and could afford road just continue path
                self.transport_resources(ct, Position(end_pos[0], end_pos[1]))
            elif ct.get_action_cooldown() == 0:
                if ct.can_build_sentinel(self.target, self.target.direction_to(sentinel_target)):
                    ct.build_sentinel(self.target, self.target.direction_to(sentinel_target))
                else:
                    print("waiting to build sentinel")
                    return
        elif self.map[self.target.y][self.target.x][1] in [None, EntityType.ROAD] and 0 < self.pos.distance_squared(self.target) <= 2:
            if sentinel_target in ct.get_attackable_tiles_from(self.target, self.target.direction_to(sentinel_target), EntityType.SENTINEL):
                if ct.can_destroy(self.target):
                    ct.destroy(self.target)
                if ct.can_build_sentinel(self.target, self.target.direction_to(sentinel_target)):
                    ct.build_sentinel(self.target, self.target.direction_to(sentinel_target))
                else:
                    print("waiting for money to build sentinel")
                    return
            else:
                self.transport_resources(ct, Position(end_pos[0], end_pos[1]))
        elif self.map[self.target.y][self.target.x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR]:
            sentinel_pos = self.target.add(self.map[self.target.y][self.target.x][3][0])
            if self.map[sentinel_pos.y][sentinel_pos.x][1] == EntityType.SENTINEL:
                attackable_tiles = ct.get_attackable_tiles_from(sentinel_pos, self.map[sentinel_pos.y][sentinel_pos.x][3][0], EntityType.SENTINEL)
                if sentinel_target not in attackable_tiles:
                    print("change pos")
                    if self.pos.distance_squared(sentinel_pos) > 2:
                        print("Moving to sentinel_pos:", sentinel_pos)
                        temp = self.target
                        self.target = sentinel_pos
                        self.explore(ct)
                        self.target = temp
                    if ct.can_destroy(sentinel_pos):
                        ct.destroy(sentinel_pos)
                    if ct.can_build_sentinel(sentinel_pos, sentinel_pos.direction_to(sentinel_target)):
                        ct.build_sentinel(sentinel_pos, sentinel_pos.direction_to(sentinel_target))
                    else:
                        print("Waiting for money or too far away to build sentinel 1")
                elif Position(end[0], end[1]) in attackable_tiles or self.map[end[1]][end[0]]:
                    self.moving_turret_supply = False
                    return
            else:
                if sentinel_target in ct.get_attackable_tiles_from(sentinel_pos, sentinel_pos.direction_to(sentinel_target), EntityType.SENTINEL):
                    if self.pos.distance_squared(sentinel_pos) > 2:
                        print("Moving to sentinel_pos:", sentinel_pos)
                        temp = self.target
                        self.target = sentinel_pos
                        self.explore(ct)
                        self.target = temp
                    if self.map[sentinel_pos.y][sentinel_pos.x][1] in [EntityType.ROAD, None] and self.map[sentinel_pos.y][sentinel_pos.x][2] == self.team and ct.can_destroy(sentinel_pos):
                        ct.destroy(sentinel_pos)
                    if ct.can_build_sentinel(sentinel_pos, sentinel_pos.direction_to(sentinel_target)):
                        ct.build_sentinel(sentinel_pos, sentinel_pos.direction_to(sentinel_target))
                    else:
                        print("Waiting for money or too far away to build sentinel 2")
                else:
                    self.transport_resources(ct, Position(end_pos[0], end_pos[1]))
        elif self.map[self.target.y][self.target.x][1] == EntityType.SENTINEL and 0 < self.pos.distance_squared(self.target) <= 2:
            attackable_tiles = ct.get_attackable_tiles_from(self.target, self.map[self.target.y][self.target.x][3][0], EntityType.SENTINEL)
            if sentinel_target not in attackable_tiles:
                print("change pos")
                if ct.can_destroy(self.target):
                    ct.destroy(self.target)
                if ct.can_build_sentinel(self.target, self.target.direction_to(sentinel_target)):
                    ct.build_sentinel(self.target, self.target.direction_to(sentinel_target))
            elif Position(end_pos[0], end_pos[1]) in attackable_tiles:
                self.moving_turret_supply = False
                return
        elif self.pos.distance_squared(self.target) > 2:
            self.explore(ct)
        
    def is_on_map(self, tile):
        return True if (0 <= tile.x < len(self.map[0]) and 0 <= tile.y < len(self.map)) else False

    def defence(self, ct):
        '''
        Order of importance (numbers refer to self.defence_mode):
         - 1 If there is an enemy turret, we need to destroy conveyor to it
         - 2 Put gunner down to destroy the enemy turret mentioned above
         - 3 If buildings' health is low, heal!
         - 4 Reconnect broken conveyor paths
         - 5 If can build sentinel next to a splitter/foundry
         - 6 Upgrade conveyors
         - 7 Destroy roads and barriers next to core
         - 10 Unassigned/Default

        Reorder by changing the numbers below (untested):
         Note: putting destroy turret lower than reconnect conveyors does NOT work
        '''

        destroy_turret_food =  1
        destroy_turret = 2
        heal = 3
        reconnect_conveyors = 4
        build_defences = 5 #5
        # Work in progress
        upgrade_conveyors = 6
        destroy_roads = 7

        # If bot has low hp, heal + move (movement hopefully keeps it out of enemy fire)
        if ct.get_hp() < 0.5 * ct.get_max_hp():
            print("Running and healing")
            d = DIRECTIONS.copy()
            random.shuffle(d)
            for i in d:
                if ct.can_move(i):
                    ct.move(i)
                if ct.can_heal(self.pos):
                    ct.heal(self.pos)

        vision_tiles = ct.get_nearby_tiles()
        if self.defence_mode == 10:  # Used as a scale for how important each job is
            self.target = self.core_pos

        for i in vision_tiles:
            building_targets = None
            i_building, i_direction, i_team = self.map[i.y][i.x][1], self.map[i.y][i.x][3][0], self.map[i.y][i.x][2]
            i_id = ct.get_tile_building_id(i)

            # Check if enemy turret needs destroying
            if i_building in [EntityType.GUNNER, EntityType.SENTINEL, EntityType.BREACH] and i_team != self.team: #  and self.defence_mode >= destroy_turret_food: # and i.distance_squared(self.core_pos) < 35: # I THINK this is the range of a sentinel
                #print(f"{i_building} at ({i.x}, {i.y})")

                for s in STRAIGHTS:
                    tile = i.add(s)
                    if not ct.is_in_vision(tile) or not self.is_on_map(tile):
                        break
                    if self.map[tile.y][tile.x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and self.map[tile.y][tile.x][3][0] == s.opposite():
                        self.target = tile
                        self.defence_mode = destroy_turret_food
                        self.defence_target = i
                    elif self.map[tile.y][tile.x][1] in [EntityType.SPLITTER] and self.map[tile.y][tile.x][3][0] != s:
                        self.target = tile
                        self.defence_mode = destroy_turret_food
                        self.defence_target = i
                    elif self.map[tile.y][tile.x][1] in [EntityType.HARVESTER, FOUNDRY] and self.map[tile.y][tile.x][2] == self.team: # Should be able to change
                        self.target = tile
                        self.defence_mode = destroy_turret_food
                        self.defence_target = i

                # IIRC this can only be > 1 if type is a bridge
                if len(self.map[i.y][i.x][3]) > 1 and self.map[i.y][i.x][3][1] not in STRAIGHTS and self.defence_mode != destroy_turret_food:
                    self.target = self.map[i.y][i.x][3].pop(1) # Pop to remove the bridge from the list
                    self.defence_mode = destroy_turret_food
                    self.defence_target = i

                if self.defence_mode == destroy_turret_food:
                    #print(f"Need to cut off its access!")
                    break

                # This enemy turret is not being fed by anything and just needs to be destroyed. This looks for surrounding tiles to place a defensive gunner.
                # Maybe this should also check if the tile has Titanium or refined axionite to feed it?
                if self.defence_mode < destroy_turret:
                    break

                for j in DIRECTIONS:
                    tile = i.add(j)
                    if not(self.is_on_map(tile)):
                        continue

                    map_tile = self.map[tile.y][tile.x]

                    if map_tile[0] == Environment.WALL:
                        pass

                    if map_tile[1] in [EntityType.GUNNER, EntityType.SENTINEL] and map_tile[2] == self.team and map_tile[3][0] == j.opposite():
                        print("Defence already built!")
                        break

                    # Checks if a bridge is feeding the tile
                    if len(map_tile[3]) > 1:
                        self.defence_target = i
                        self.target = tile
                        self.defence_mode = destroy_turret
                        break

                    # Otherwise looks for a conveyor feeding the tile
                    for k in [a for a in STRAIGHTS if a != j.opposite()]:
                        tile = i.add(j).add(k)
                        if self.is_on_map(tile):
                            map_tile = self.map[tile.y][tile.x]
                            if (map_tile[1] in [EntityType.ARMOURED_CONVEYOR, EntityType.CONVEYOR] and map_tile[3][0] == k.opposite()) or map_tile[1] in [EntityType.HARVESTER, EntityType.FOUNDRY]:
                                self.defence_target = i
                                self.target = i.add(j)
                                self.defence_mode = destroy_turret
                                break

                    # If has found a tile feeding it, break
                    if self.target == i.add(j):
                        #print("Building not being actively supplied")
                        #print(f"Going to destroy it with a defensive building at {self.target}")
                        break

            # Check if any tiles need healing
            elif i_building and ct.get_hp(i_id) < ct.get_max_hp(i_id) and i_team == self.team and i_building != EntityType.ROAD and self.defence_mode >= heal: # and (self.map[i.y][i.x][4] != EntityType.BUILDER_BOT or self.pos == i)
                if i.distance_squared(self.pos) < self.target.distance_squared(self.pos) or self.defence_mode >= heal:
                    self.target = i
                self.defence_mode = heal

            # Check if conveyor route home needs rebuilding
            elif i_building in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and ct.is_in_vision(i) and self.map[i.add(i_direction).y][i.add(i_direction).x][1] not in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.SPLITTER, EntityType.BRIDGE, EntityType.SENTINEL, EntityType.GUNNER] and self.defence_mode >= reconnect_conveyors:
                print(i)
                if ct.get_tile_builder_bot_id(i) is None and not (ct.is_in_vision(i.add(i_direction)) and ct.get_tile_builder_bot_id(i.add(i_direction)) is not None) and ct.get_stored_resource(ct.get_tile_building_id(i)) is not None or self.pos == i:
                    self.target = i
                    self.defence_mode = reconnect_conveyors

            # Build gunners next to a splitter
            elif i_building == EntityType.SPLITTER and self.defence_mode >= build_defences:
                building_targets = [i.add(i_direction), i.add(i_direction.rotate_left().rotate_left()), i.add(i_direction.rotate_right().rotate_right())]
                if self.defence_mode > build_defences:
                    self.target = self.core_pos

            # Build gunners next to a foundry
            elif i_building in [EntityType.FOUNDRY] and self.defence_mode >= build_defences:
                building_targets = [i.add(Direction.NORTH), i.add(Direction.WEST), i.add(Direction.EAST), i.add(Direction.SOUTH)]
                if self.defence_mode > build_defences:
                    self.target = self.core_pos

            # Upgrade conveyors to armoured conveyors
            elif self.defence_mode >= upgrade_conveyors and i_building == EntityType.CONVEYOR and i_team == self.team:
                resources, cost = ct.get_global_resources(), ct.get_armoured_conveyor_cost()
                if resources[0] > 5*cost[0] and resources[1] > 5*cost[1] and (self.target == self.core_pos or self.target.distance_squared(self.core_pos) > i.distance_squared(self.core_pos)):
                    self.target = i
                    self.defence_mode = upgrade_conveyors
                    print(i)

            elif self.defence_mode >= destroy_roads and self.pos.distance_squared(self.core_pos) <= 2 and i.distance_squared(self.core_pos) <= 8 and ((i_building in [EntityType.ROAD] and i_team == self.team) or (i_building in [EntityType.ROAD] and i_team != self.team and ct.get_global_resources()[0] > 500) or (i_building in [EntityType.BARRIER] and i_team == self.team)):
                self.target = i
                self.defence_mode = destroy_roads

            if building_targets is not None:
                for building_target in building_targets:
                    if self.is_on_map(building_target) and ct.is_in_vision(building_target) and self.map[building_target.y][building_target.x][1] not in [EntityType.CORE, EntityType.SPLITTER, EntityType.HARVESTER, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.FOUNDRY, EntityType.SENTINEL, EntityType.GUNNER] and ct.get_tile_env(building_target) != Environment.WALL:
                        if building_target.distance_squared(self.pos) < self.target.distance_squared(self.pos) or self.target == self.core_pos:
                            self.target = building_target
                            self.defence_mode = build_defences
                            print(self.target)


        if self.pos.distance_squared(self.target) >= 4 and self.defence_mode != 10: # and self.defence_mode >= 3:
            print(f"Defence mode: {self.defence_mode}, target: ({self.target.x}, {self.target.y})")
            self.explore(ct)
            return

        if self.defence_mode == destroy_turret_food:
            print(f"Defence_mode 1, ({self.target.x},{self.target.y}) ({self.defence_target.x},{self.defence_target.y})")
            map_tile = self.map[self.target.y][self.target.x]
            if map_tile[1] not in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.SPLITTER, EntityType.BRIDGE, EntityType.HARVESTER]:
                self.defence_mode = 10
                return

            target_tile = self.map[self.defence_target.y][self.defence_target.x]
            if target_tile[1] not in [EntityType.GUNNER, EntityType.SENTINEL, EntityType.BREACH] or target_tile[2] == self.team:
                self.defence_mode = 10
                return

            if self.pos.distance_squared(self.target) >= 4:
                print("Exploring,", self.target)
                self.explore(ct, self.target)
            elif ct.can_destroy(self.target):
                ct.destroy(self.target)
                self.defence_mode = 10
                # self.defence(ct)
                return
            elif map_tile[2] != self.team:
                if ct.can_move(self.pos.direction_to(self.target)):
                    ct.move(self.pos.direction_to(self.target))
                if ct.can_fire(self.target):
                    ct.fire(self.target)
                if ct.get_entity_type(ct.get_tile_building_id(self.target)) is None:
                    self.defence_mode = 10
            else:
                print("WTF")
                self.defence_mode = 10
                # ct.resign()
            return

        elif self.defence_mode == destroy_turret:
            print(f"Defence_mode 2, ({self.target.x},{self.target.y}) ({self.defence_target.x},{self.defence_target.y})")
            target = self.defence_target
            target_tile = self.map[target.y][target.x]
            map_tile = self.map[self.target.y][self.target.x]

            if target_tile[1] not in [EntityType.GUNNER, EntityType.SENTINEL, EntityType.BREACH] or target_tile[2] == self.team or map_tile[1] in [EntityType.GUNNER, EntityType.SENTINEL, EntityType.BREACH]:
                self.defence_mode = 10
                return

            #if map_tile[1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.SPLITTER, EntityType.BRIDGE]:
            #    self.defence_mode = 10
            #    return

            if ct.can_destroy(self.target):
                ct.destroy(self.target)

            if ct.can_fire_from(self.target, self.target.direction_to(target), EntityType.GUNNER, target):
                if ct.can_build_gunner(self.target, self.target.direction_to(target)):
                    ct.build_gunner(self.target, self.target.direction_to(target))
                    self.defence_mode = 10
                else:
                    print("Attempting to build gunner" , ct.get_gunner_cost())
            elif ct.can_fire_from(self.target, self.target.direction_to(target), EntityType.SENTINEL, target):
                if ct.can_build_sentinel(self.target, self.target.direction_to(target)):
                    ct.build_sentinel(self.target, self.target.direction_to(target))
                    self.defence_mode = 10
                else:
                    print("Attempting to build sentinel" ,ct.get_sentinel_cost())
            else:
                print(f"Can not build turret to attack {target} from {self.target}")
                self.defence_mode = 10

            if self.pos.distance_squared(target) >= 4:
                self.explore(ct, target)

        elif self.defence_mode == heal:
            print(f"Defence_mode 3: Healing {self.target}")
            if ct.can_heal(self.target):
                print("Healing")
                ct.heal(self.target)
            self.defence_mode = 10

        elif self.defence_mode == reconnect_conveyors:
            print(f"Defence_mode 4: Connecting ({self.target.x}, {self.target.y})")
            self.defence_mode = 10
            if self.pos != self.target:
                self.explore(ct,self.target)
                return
            self.built_harvester[0] = True
            self.harvest_ore(ct, self.target)
            return

        elif self.defence_mode == build_defences:
            print(f"Defence_mode 5: Adding Sentinels @ {self.target}")
            if self.map[self.target.y][self.target.x][1] in [EntityType.GUNNER, EntityType.SENTINEL] or self.target == self.core_pos:
                print("Sentinel/ Gunner already built!")
                self.defence_mode = 10
                return

            if ct.can_destroy(self.target):
                ct.destroy(self.target)

            for d in STRAIGHTS:
                if ct.can_build_sentinel(self.target, self.target.direction_to(self.core_pos).opposite()) and self.is_on_map(self.target.add(d)) and self.map[self.target.add(d).y][self.target.add(d).x][1] in [EntityType.SPLITTER, EntityType.FOUNDRY]:
                    # Maybe improve this logic
                    ct.build_sentinel(self.target, self.target.direction_to(self.core_pos).opposite())
                    return
            print("Sentinel Cost:", ct.get_sentinel_cost() )

        elif self.defence_mode == upgrade_conveyors:
            print(f"Defence_mode 6: Upgrading {self.target}")
            if self.map[self.target.y][self.target.x][1] == EntityType.CONVEYOR and ct.can_destroy(self.target) and ct.get_armoured_conveyor_cost()[0] >= ct.get_global_resources()[0] and ct.get_armoured_conveyor_cost()[1] >= ct.get_global_resources()[1]:
                direction = self.map[self.target.y][self.target.x][3][0]
                ct.destroy(self.target)
                ct.draw_indicator_line(self.pos, self.core_pos, 0, 0, 0)
                if ct.can_build_armoured_conveyor(self.target, direction):
                    ct.build_armoured_conveyor(self.target, direction)
                #else:
                    #ct.resign()
            self.defence_mode = 10

        elif self.defence_mode == destroy_roads:
            if self.pos.distance_squared(self.target) > 2:
                self.explore(ct)
            elif self.map[self.target.y][self.target.x][2] != self.team and self.pos != self.target:
                self.explore(ct)
            if ct.can_destroy(self.target) and self.map[self.target.y][self.target.x][1] in [EntityType.ROAD, EntityType.BARRIER]:
                ct.destroy(self.target)
                self.defence_mode = 10
            elif ct.can_fire(self.target):
                ct.fire(self.target)
                if ct.get_tile_building_id(self.target) == None:
                    self.defence_mode = 10
        else:
            if ct.get_hp() < ct.get_max_hp() and ct.can_heal(self.pos):
                ct.heal(self.pos)
            if self.pos.distance_squared(self.core_pos) > 2:
                self.target = self.core_pos
                self.explore(ct)
            else:
                if self.pos == self.core_pos:
                    if ct.can_move(Direction.NORTH):
                        ct.move(Direction.NORTH)
                else:
                    dire = self.pos.direction_to(self.core_pos)
                    if dire in DIAGONALS:
                        if ct.can_move(dire.rotate_left()):
                            ct.move(dire.rotate_left())
                    elif dire in STRAIGHTS:
                        if ct.can_move(dire.rotate_left().rotate_left()):
                            ct.move(dire.rotate_left().rotate_left())
                    else:
                        print(dire)
                return
            # Add some feature to roam about (leo's new thingy)
            print("Nothing to do!", self.defence_mode)
            # Very basic explore algorithm
        '''
        # Destroy roads around the core (to give space for markers) - dubious - may use up titanium
        if self.pos.distance_squared(self.core_pos) < 4:
            width = len(self.map[0])
            height = len(self.map)
            for i in DIRECTIONS:
                tile = self.pos.add(i)
                if not (0 <= tile.x < width and 0 <= tile.y < height):
                    continue
                if self.map[tile.y][tile.x][1] == EntityType.ROAD:
                    if ct.can_destroy(tile):
                        ct.destroy(tile)
                        return
                    else:
                        if ct.can_move(i):
                            ct.move(i)
                            if ct.can_fire(tile):
                                ct.fire(tile)'''

        if self.pos == self.target and self.target != self.core_pos:
            for d in DIRECTIONS:
                if ct.can_move(d):
                    ct.move(d)

    def foundry(self, ct):
        if self.target == Position(1000, 1000):
            self.status = DEFENCE
            self.defence_mode = 10
            return
        if self.pos.distance_squared(self.target) > 2:
            self.explore(ct)
        else:
            if self.map[self.target.y][self.target.x][1] == EntityType.SPLITTER:   # Choose tile to build harvester
                checks = [(-1, 0), (1, 0), (0, -1), (0, 1)]
                chosen_tile = None
                for shift in checks:
                    xx = self.target.x + shift[0]
                    yy = self.target.y + shift[1]
                    if not (xx >= 0 and xx < len(self.map[0]) and yy >= 0 and yy < len(self.map)):
                        continue
                    tile = self.map[yy][xx]
                    env = tile[0]
                    building = tile[1]
                    team = tile[2]
                    check_tile = Position(xx, yy)
                    if env == Environment.WALL:
                        continue
                    if building == EntityType.FOUNDRY and team == self.team:  # If a foundry already on splitter then ignore
                        chosen_tile = None
                        break
                    elif building == None:  # If nothing on a tile then good place to build
                        chosen_tile = check_tile
                        if check_tile.distance_squared(self.core_pos) <= 5:
                            break
                    elif building in [EntityType.GUNNER, EntityType.SENTINEL] and team == self.team and chosen_tile == None:    # If turret on tile then could build here if not another tile already found
                        chosen_tile = check_tile
                        # reset now before target is changed as not needed to remain True
                if chosen_tile == None:
                    self.splitter_resource[self.target] = False
                    self.target = Position(1000, 1000)
                    self.status = DEFENCE
                    self.defence_mode = 10
                else:
                    self.splitter_target = self.target
                    self.target = chosen_tile

            elif self.map[self.target.y][self.target.x][1] == EntityType.BRIDGE:
                return
                if ct.get_splitter_cost()[0] > ct.get_global_resources()[0]:
                    self.status = DEFENCE
                    self.defence_mode = 10
                    return
                if ct.can_destroy(self.target):
                    ct.destroy(self.target)
                checks = [(-1, 0), (1, 0), (0, -1), (0, 1)]
                conveyor = None
                for shift in checks:    # Check for conveyors or splitters outputting to this tile
                    xx = self.target.x + shift[0]
                    yy = self.target.y + shift[1]
                    if not (xx >= 0 and xx < len(self.map[0]) and yy >= 0 and yy < len(self.map)):
                        continue
                    tile = self.map[yy][xx]
                    env = tile[0]
                    building = tile[1]
                    team = tile[2]
                    check_tile = Position(xx, yy)
                    if env == Environment.WALL:
                        continue
                    elif building in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.SPLITTER, EntityType.HARVESTER, EntityType.FOUNDRY]:
                        conveyor = check_tile   # Accept first
                        break
                if conveyor == None:    # If none into this tile then just face towards core
                    if ct.can_build_splitter(self.target, self.target.direction_to(self.core_pos)):
                        ct.build_splitter(self.target, self.target.direction_to(self.core_pos))
                else:
                    if ct.can_build_splitter(self.target, conveyor.direction_to(self.target)):
                        ct.build_splitter(self.target, conveyor.direction_to(self.target))

            else:
                if self.pos == self.target:
                    for d in DIRECTIONS:
                        if ct.can_build_road(self.pos.add(d)):
                            ct.build_road(self.pos.add(d))
                        if ct.can_move(d):
                            ct.move(d)
                            break
                if self.map[self.target.y][self.target.x][1] == EntityType.FOUNDRY:
                    self.splitter_resource[self.splitter_target] = False
                    self.splitter_target = None
                    self.target = Position(1000, 1000)
                    self.status = DEFENCE
                    self.defence_mode = 10
                    return
                elif self.map[self.target.y][self.target.x][1] not in [EntityType.SPLITTER, EntityType.HARVESTER, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.FOUNDRY] and ct.can_destroy(self.target):
                    checks = [(-1, 0), (1, 0), (0, -1), (0, 1)]
                    foundry = False
                    for shift in checks:
                        building = self.map[self.splitter_target.y + shift[1]][self.splitter_target.x + shift[0]][1]
                        team = self.map[self.splitter_target.y + shift[1]][self.splitter_target.x + shift[0]][2]
                        check_tile = Position(self.splitter_target.x + shift[0], self.splitter_target.y + shift[1])
                        if building == EntityType.FOUNDRY and team == self.team:  # If a foundry already on splitter then ignore
                            foundry = True
                            break
                    if not foundry:
                        if ct.can_destroy(self.target):
                            ct.destroy(self.target)
                    else:
                        self.splitter_resource[self.target] = False
                        self.target = Position(1000, 1000)
                        self.status = DEFENCE
                        self.defence_mode = 10
                if ct.can_build_foundry(self.target):
                    ct.build_foundry(self.target)
                    self.splitter_resource[self.splitter_target] = False
                    self.splitter_target = None
                    self.target = Position(1000, 1000)
                    self.status = DEFENCE
                    self.defence_mode = 10
                    return

    def gn_init(self,ct):
        self.update_map(ct)
        vision_tiles = ct.get_nearby_tiles()
        for i in vision_tiles:
            if ct.get_tile_building_id(i) is not None and ct.get_entity_type(ct.get_tile_building_id(i)) == EntityType.CORE:
                if ct.get_team(ct.get_tile_building_id(i)) != ct.get_team():
                    self.status = ATTACK_ENEMY_CORE
                else:
                    self.status = DEFENCE
                    self.defence_mode = 10
                print(self.status)
                return
        self.status = DEFENCE
        self.defence_mode = 10
        print("Defence")

    def gn_attack_enemy_core(self, ct):
        d = ct.get_direction()
        target = ct.get_position()
        if ct.get_tile_builder_bot_id(target.add(d)) is  None:
            for i in [target.add(d) for d in DIRECTIONS]:
                ct.draw_indicator_dot(i, 0, 0, 0)
                if (i.x < 0 or i.x >= ct.get_map_width() or i.y<0 or i.y >= ct.get_map_height()):
                    continue
                if ct.get_tile_building_id(i) is not None and  ct.get_entity_type(ct.get_tile_building_id(i)) == EntityType.CORE and ct.get_tile_builder_bot_id(i) is not None:
                    ct.draw_indicator_dot(i, 255, 0, 0)
                    if ct.can_rotate(target.direction_to(i)) and 0 != ct.get_ammo_amount():
                        ct.rotate(target.direction_to(i))
                        break
        for i in range(2):
            target = target.add(d)
            if ct.get_entity_type(ct.get_tile_builder_bot_id(target)) == EntityType.BUILDER_BOT and ct.get_team() == ct.get_team(ct.get_tile_building_id(target)):
                return
            if ct.can_fire(target):
                ct.fire(target)
                return

    def gn_defend_core(self, ct):
        d = ct.get_direction()

        done = True
        for i in STRAIGHTS:
            target = ct.get_position()
            target = target.add(i)
            if not(self.is_on_map(target)):
                break

            # Check if being fed by a splitter
            fed_by_conv = ct.get_entity_type(ct.get_tile_building_id(target)) in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and ct.get_direction(ct.get_tile_building_id(target)) == i.opposite()
            fed_by_splitter_harvester = ct.get_entity_type(ct.get_tile_building_id(target)) in [EntityType.SPLITTER] and ct.get_direction(ct.get_tile_building_id(target)) != i
            fed_by_harv_foun = ct.get_entity_type(ct.get_tile_building_id(target)) in [EntityType.HARVESTER, EntityType.FOUNDRY]
            fed_by_bridge = len(self.map[ct.get_position().y][ct.get_position().x][3]) > 1

            if fed_by_conv or fed_by_splitter_harvester or fed_by_harv_foun or fed_by_bridge:
                target = ct.get_position()
                for j in [target.add(d) for d in DIRECTIONS] + [target.add(d).add(d) for d in DIRECTIONS]:
                    print(j)
                    if not(self.is_on_map(j)):
                        break
                    if (ct.get_team(ct.get_tile_building_id(j)) not in [ct.get_team(), None] and ct.get_entity_type(ct.get_tile_building_id(j)) not in [EntityType.ROAD, EntityType.MARKER, None]) or (ct.get_entity_type(ct.get_tile_builder_bot_id(j)) == EntityType.BUILDER_BOT and ct.get_team() != ct.get_team(ct.get_tile_builder_bot_id(j))):
                        done = False

        if done:
            print("Wanting to self-destruct")
            ct.self_destruct()

        target = ct.get_position()
        for i in range(2):
            target = target.add(d)
            if not(0 <= target.x < ct.get_map_width() and 0 <= target.y < ct.get_map_height()):
                break
            if (ct.get_entity_type(ct.get_tile_builder_bot_id(target)) == EntityType.BUILDER_BOT and ct.get_team() != ct.get_team(ct.get_tile_builder_bot_id(target))) or (ct.get_team(ct.get_tile_building_id(target)) not in [None, ct.get_team()] and ct.get_entity_type(ct.get_tile_building_id(target)) not in [EntityType.ROAD, EntityType.MARKER]) or ct.get_entity_type(ct.get_tile_building_id(target)) == EntityType.ROAD:
                if ct.can_fire(target):
                    ct.fire(target)
                elif ct.get_ammo_amount() < 2:
                    print("Out of Ammo")
                return

        target = ct.get_position()
        # If no builder bot found, look for one:
        for i in [target.add(d) for d in DIRECTIONS] + [target.add(d).add(d) for d in DIRECTIONS]:
            if i.x < 0 or i.x >= ct.get_map_width() or i.y<0 or i.y >= ct.get_map_height():
                continue
            if (ct.get_entity_type(ct.get_tile_builder_bot_id(i)) == EntityType.BUILDER_BOT and ct.get_team() != ct.get_team(ct.get_tile_builder_bot_id(i))) or (ct.get_team(ct.get_tile_building_id(i)) != ct.get_team() and ct.get_entity_type(ct.get_tile_building_id(i)) not in [EntityType.ROAD, EntityType.MARKER]):
                ct.draw_indicator_dot(i, 255, 0, 0)
                if ct.can_rotate(target.direction_to(i)) and 0 != ct.get_ammo_amount(): # and ct.get_global_resources()[0] > 50:
                    ct.rotate(target.direction_to(i))
                    break
    
    def ceil(self, a, b, div=7):   # Pass a, b Position
        radii1 = int((abs( a.x - b.x ) // div ) )
        radii2 = int((abs( a.y - b.y ) // div ) )
        if radii1 >= radii2:
            radii = radii1
            rem = abs( a.x - b.x ) % div
            if rem > 0:
                radii = radii1 + 1
        else:
            radii = radii2
            rem = abs( a.y - b.y ) % div
            if rem > 0:
                radii = radii2 + 1
        return radii
        

    def find_corners(self, centre, radii=None):
        if radii == None:
            radii = self.ceil(self.target, centre)
        count = 0
        x1 = centre.x-radii*7
        if x1 < 0:
            x1 = 0
            count += 1
        y1 = centre.y-radii*7
        if y1 < 0:
            y1 = 0
            count += 1
        x2 = centre.x+radii*7
        if x2 > len(self.map[0]) -1:
            x2 = len(self.map[0]) -1
            count += 1
        y2 = centre.y+radii*7
        if y2 > len(self.map) - 1:
            y2 = len(self.map) - 1
            count += 1
        return count, x1, x2, y1, y2, radii

    def exploring_the_map(self, ct, centre=None, start=None):
        if centre == None:
            centre = Position(len(self.map[0])//2, len(self.map)//2)
        if start == None:
            if self.explore_start == None:
                start = centre # Start at centre of map
            else:
                start = self.explore_start
        if self.target != Position(1000, 1000) and self.pos.distance_squared(self.target) > 20:
            if self.target in self.unreachable_tiles:
                count, x1, x2, y1, y2, radii = self.find_corners(centre, radii = self.ceil(self.target, centre) + 1)
                self.target = Position(x1, y1)
            print(self.target)
            self.explore(ct)
        elif self.target == Position(1000, 1000):
            if self.target in self.unreachable_tiles:
                count, x1, x2, y1, y2, radii = self.find_corners(centre, radii = self.ceil(self.target, centre) + 1)
                self.target = Position(x1, y1)
            else:
                self.target = Position(start.x, start.y)
            self.explore_start = self.target
            print(self.target)
            self.explore(ct)
        else:
            count, x1, x2, y1, y2, radii = self.find_corners(centre)
            print(centre, start, x1, x2, y1, y2, self.target, radii)
            if count == 4 and (self.target.x, self.target.y) == (x1, y2):
                self.target = Position(1000, 1000)
                self.explore_start = None
                if self.enemy_core_pos == Position(1000, 1000):
                    self.status = DEFENCE
                    self.defence_mode = 10
                else:
                    self.status = ATTACK_ENEMY_CORE
                return
            CORNERS = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
            if CORNERS[3] == (self.target.x, self.target.y):
                radii += 1
                x1 = centre.x-radii*7
                if x1 < 0:
                    x1 = 0
                y1 = centre.y-radii*7
                if y1 < 0:
                    y1 = 0
                self.target = Position(x1, y1)
                self.explore_start = self.target
                print(self.target)
                self.explore(ct)
                return
            for i in range(len(CORNERS)):
                if CORNERS[i] == (self.target.x, self.target.y):
                    self.target = Position(CORNERS[i+1][0], CORNERS[i+1][1])
                    self.explore_start = self.target
                    print(self.target)
                    self.explore(ct)
                    return

    def report_enemy_core_location(self, ct):
        self.target = self.core_pos
        pos = self.pos
        enemy_core_x, enemy_core_y = self.enemy_core_pos.x, self.enemy_core_pos.y
        marker_status = 2
        bot_id = 0
        message = (
                marker_status * (2 ** 28)
                + bot_id * (2 ** 20)
                + enemy_core_x * (2 ** 6)
                + enemy_core_y)

        for i in DIRECTIONS:
            if self.pos.distance_squared(self.core_pos) <= 16:
                if ct.can_destroy(pos.add(i)) and self.map[pos.add(i).y][pos.add(i).x][1] in [EntityType.ROAD]:
                    ct.destroy(pos.add(i))
                if ct.can_place_marker(pos.add(i)):
                    ct.place_marker(pos.add(i), message)
                    if len(self.enemy_mined_tit) != 0:  # Try to get early attack in
                        self.status = ATTACK_ENEMY_SUPPLY_LINES
                        self.explore_start = None
                    else:
                        self.status = EXPLORING
                    print("Reported Enemy Core Location back to Base")
                    self.target = Position(0, 0)
                    return
            if ct.can_place_marker(pos.add(i)):
                ct.place_marker(pos.add(i), message)
                break

        if self.pos.distance_squared(self.core_pos) > 8:
            self.explore(ct)

    def run(self, ct: Controller) -> None:

        etype = ct.get_entity_type()

        if etype == EntityType.CORE:
            #if ct.get_current_round() > 300:
            #    ct.resign()

            if self.team == None:
                self.team = ct.get_team()
                self.pos = ct.get_position()
                self.id = ct.get_id()
                self.core_pos = self.pos

            self.update_map(ct)

            # Inital 3 bots to find enemy core location
            if (self.num_spawned < 3 or (self.enemy_core_pos == Position(1000, 1000) and ct.get_current_round() > 500 and ct.get_global_resources()[0] > 500 and self.temp_counter < 6) or (self.enemy_core_pos == Position(1000, 1000) and ct.get_current_round() > 1000 and ct.get_global_resources()[0] > 1000 and self.temp_counter < 9) or (self.enemy_core_pos == Position(1000, 1000) and ct.get_current_round() > 1250 and ct.get_global_resources()[0] > 500 and self.temp_counter < 12) or (self.enemy_core_pos == Position(1000, 1000) and ct.get_current_round() > 1500 and ct.get_global_resources()[0] > 500 and self.temp_counter < 15) or (self.enemy_core_pos == Position(1000, 1000) and ct.get_current_round() > 1750 and ct.get_global_resources()[0] > 500 and self.temp_counter < 18)):
                
                possible_core_locations = [
                    [ct.get_map_width() - 1 - self.core_pos.x, self.core_pos.y],  # Horizontal Flip
                    [self.core_pos.x, ct.get_map_height() - 1 - self.core_pos.y],  # Vertical Flip
                    [ct.get_map_width() - 1 - self.core_pos.x, ct.get_map_height() - 1 - self.core_pos.y]]  # Rotation

                spawn_pos = self.pos.add(Direction.NORTH)
                if ct.can_spawn(spawn_pos):
                    print("Spawning Builder to Find Enemy Base")
                    ct.spawn_builder(spawn_pos)

                    # Place marker, so bot knows where to go
                    bot_id = ct.get_tile_builder_bot_id(spawn_pos)
                    marker_status = 1   # explores towards possible core location
                    message = (
                            marker_status * (2**28)
                            + bot_id * (2**12)
                            + possible_core_locations[self.temp_counter%3][0] * (2**6)
                            + possible_core_locations[self.temp_counter%3][1])
                    self.temp_counter += 1
                    if self.num_spawned < 3:
                        self.num_spawned += 1
                    else:
                        self.extra_spawned += 1
                    for i in ct.get_nearby_tiles(6):    # Will sometimes cause errors where builder bot cannot move to tile where marker was placed and destroy it
                        if ct.can_place_marker(i) and ct.is_tile_empty(i):
                            ct.place_marker(i, message)
                            break

            elif ((self.extra_spawned < 1 and ct.get_current_round() > 10 and len(self.map[0]) >= 15 and len(self.map) >= 15 and self.enemy_core_pos == Position(1000, 1000)) or (self.extra_spawned < 2 and ct.get_current_round() > 1000 and ct.get_global_resources()[0] > 1000)) and self.num_spawned >= 3 and ct.get_builder_bot_cost()[0] < ct.get_global_resources()[0]:
                for spawn_pos in ct.get_nearby_tiles(8):
                    if ct.can_spawn(spawn_pos):
                        ct.spawn_builder(spawn_pos)
                        # Place marker, so bot knows where to go
                        bot_id = ct.get_tile_builder_bot_id(spawn_pos)
                        marker_status = 5   # Extra harvest bot for big map
                        message = (
                                marker_status * (2**28)
                                + bot_id * (2**12)
                                + 0 * (2 ** 6)
                                + 0)

                        self.extra_spawned += 1
                        for i in ct.get_nearby_tiles(7):
                            ct.draw_indicator_dot(i,200,200,200)
                            if ct.can_place_marker(i) and ct.is_tile_empty(i):
                                ct.place_marker(i, message)
                        break

            # Bots to do healing
            elif ct.get_hp() < 500 or self.num_spawned < 4 or (self.num_spawned < 5 and ct.get_global_resources()[0] >= 500):
                print("Healing bots")
                core_tiles = ct.get_nearby_tiles(3)
                for i in core_tiles:
                    if ct.can_spawn(i):
                        ct.spawn_builder(i)
                        if self.num_spawned < 5:
                            self.num_spawned += 1
                        break

            # Bots to attack supply lines
            elif ct.get_current_round() > 25 and ct.get_global_resources()[0] > 300 and (9 <= self.num_spawned < 13 or (20 <= self.num_spawned <= 30 and self.num_spawned % 2 == 0 and ct.get_global_resources()[0] > 1500)):
                if ct.get_global_resources()[0] < ct.get_builder_bot_cost()[0]:
                    print("Waiting for resources to spawn builder bot")
                    return
                for spawn_pos in ct.get_nearby_tiles(8):
                    if ct.can_spawn(spawn_pos):
                        ct.spawn_builder(spawn_pos)
                        # Place marker, so bot knows where to go
                        bot_id = ct.get_tile_builder_bot_id(spawn_pos)
                        marker_status = 3   # Defence bot
                        if self.enemy_core_pos != Position(1000, 1000):
                            message = (
                                    marker_status * (2**28)
                                    + bot_id * (2**12)
                                    + self.enemy_core_pos.x * (2 ** 6)
                                    + self.enemy_core_pos.y)
                        else:
                            message = (
                                    marker_status * (2**28)
                                    + bot_id * (2**12)
                                    + 0 * (2 ** 6)
                                    + 0)

                        self.num_spawned += 1
                        for i in ct.get_nearby_tiles(7):
                            ct.draw_indicator_dot(i,200,200,200)
                            if ct.can_place_marker(i) and ct.is_tile_empty(i):
                                ct.place_marker(i, message)
                        break

            # Extra bots to attack enemy core
            elif ct.get_current_round() > 25 and ct.get_global_resources()[0] > 300 and (self.num_spawned < 13 or (17 <= self.num_spawned <= 20 and ct.get_global_resources()[0] > 1000) or (20 <= self.num_spawned <= 30 and self.num_spawned % 2 == 1 and ct.get_global_resources()[0] > 1500)):
                if ct.get_global_resources()[0] < ct.get_builder_bot_cost()[0]:
                    print("Waiting for resources to spawn builder bot")
                    return
                for spawn_pos in ct.get_nearby_tiles(8):
                    if ct.can_spawn(spawn_pos):
                        ct.spawn_builder(spawn_pos)
                        # Place marker, so bot knows where to go
                        bot_id = ct.get_tile_builder_bot_id(spawn_pos)
                        if self.num_spawned < 13:
                            marker_status = 2   # Defence bot
                        else:
                            marker_status = 4
                        if self.enemy_core_pos != Position(1000, 1000):
                            message = (
                                    marker_status * (2**28)
                                    + bot_id * (2**12)
                                    + self.enemy_core_pos.x * (2 ** 6)
                                    + self.enemy_core_pos.y)
                        else:
                            message = (
                                    marker_status * (2**28)
                                    + bot_id * (2**12)
                                    + 0 * (2 ** 6)
                                    + 0)

                        self.num_spawned += 1
                        for i in ct.get_nearby_tiles(7):
                            ct.draw_indicator_dot(i,200,200,200)
                            if ct.can_place_marker(i) and ct.is_tile_empty(i):
                                ct.place_marker(i, message)
                        break

            # Moving turret bots
            elif ct.get_current_round() > 25 and ct.get_global_resources()[0] > 300 and self.num_spawned < 17:
                if ct.get_global_resources()[0] < ct.get_builder_bot_cost()[0]:
                    print("Waiting for resources to spawn builder bot")
                    return
                for spawn_pos in ct.get_nearby_tiles(8):
                    if ct.can_spawn(spawn_pos):
                        ct.spawn_builder(spawn_pos)
                        # Place marker, so bot knows where to go
                        bot_id = ct.get_tile_builder_bot_id(spawn_pos)
                        marker_status = 6
                        if self.enemy_core_pos != Position(1000, 1000):
                            message = (
                                    marker_status * (2**28)
                                    + bot_id * (2**12)
                                    + self.enemy_core_pos.x * (2 ** 6)
                                    + self.enemy_core_pos.y)
                        else:
                            message = (
                                    marker_status * (2**28)
                                    + bot_id * (2**12)
                                    + 0 * (2 ** 6)
                                    + 0)

                        self.num_spawned += 1
                        for i in ct.get_nearby_tiles(7):
                            ct.draw_indicator_dot(i,200,200,200)
                            if ct.can_place_marker(i) and ct.is_tile_empty(i):
                                ct.place_marker(i, message)
                        break

            if self.enemy_core_pos == Position(1000, 1000):
                for i in self.marker_locations:
                    if self.map[i.y][i.x][1] == EntityType.MARKER:
                        marker_value = ct.get_marker_value(ct.get_tile_building_id(i))
                        marker_value_id = (marker_value % (2 ** 28)) // (2 ** 12)
                        marker_status = marker_value // (2 ** 28)
                        target_x = (marker_value % (2 ** 12)) // (2 ** 6)
                        target_y = marker_value % (2 ** 6)
                        if marker_status == 2:
                            print("Updated Enemy Core Position")
                            self.enemy_core_pos = Position(target_x, target_y)
                            break
                    else:
                        self.marker_locations.remove(i)

        elif etype == EntityType.BUILDER_BOT:

            # Update map, position and prints update timings
            self.pos = ct.get_position()
            self.update_map(ct)

            # Sets self.core_pos, self.team, self.id, and uses markers & env factors to set self.status
            if self.status == INIT:
                self.initialise_builder_bot(ct)

            elif self.status == FIND_ENEMY_CORE:
                print(f"Finding Enemy Core at ({self.target.x},{self.target.y})")
                self.find_enemy_core(ct)

            elif self.status == REPORT_ENEMY_CORE_LOCATION:
                print(f"Reporting Enemy Core at {self.enemy_core_pos}")
                self.report_enemy_core_location(ct)

            elif self.status == EXPLORING:
                print(f"Just roaming 'bout... \n Tit: {self.tit} \n Ax: {self.ax}")
                if (len(self.tit) != 0 and (ct.get_current_round() <= 50 or len(self.mined_tit) < 4 or (len(self.mined_tit) < 8 and ct.get_current_round() >= 250 and len(self.enemy_mined_tit) == 0) or (ct.get_current_round() > 1000 and len(self.ax) == 0 and len(self.mined_ax) > 4 and len(self.mined_tit) < 12) or (len(self.mined_tit) < 12 and not (len(self.ax) != 0 and ((ct.get_global_resources()[0] > 750 and ct.get_global_resources()[1] == 0) or ct.get_current_round() >= 750))) or (ct.get_current_round() >= 1000 and ct.get_global_resources()[0] >= 1000))) or (len(self.ax) != 0 and ct.get_current_round() > 50 and len(self.mined_tit) > 0 and (len(self.mined_ax) < 2 or ct.get_current_round() > 1000 or (len(self.mined_ax) < 4 and ct.get_current_round() >= 250) or (ct.get_current_round() >= 1000 and ct.get_global_resources()[0] >= 1000))):
                    self.target = Position(1000, 1000)
                    self.status = MINING_TITANIUM
                elif len(self.enemy_mined_tit) != 0:# and self.enemy_core_pos != Position(1000, 1000):
                    self.target = Position(1000, 1000)
                    self.status = ATTACK_ENEMY_SUPPLY_LINES
                    self.explore_start = None
                elif (len(self.tit) == 0 and len(self.mined_tit) < 5) or (len(self.ax) == 0 and len(self.mined_ax) == 0 and ct.get_global_resources()[1] == 0) or (len(self.enemy_mined_tit) == 0 and len(self.attacked_enemy_mined_tit) < 3):
                    print("Search for more to do")
                    self.exploring_the_map(ct)
                else:
                    self.target = Position(1000, 1000)
                    self.status = ATTACK_ENEMY_CORE
                    self.explore_start = None

            elif self.status == MINING_TITANIUM:  # Mining ore
                print("Mining")
                if self.find_enemy_core_target != None and ((len(self.tit) == 0 and self.built_harvester[0] == False) or (self.mined_tit_count != 0 and self.built_harvester[0] == False)):
                    self.status = FIND_ENEMY_CORE
                    return
                if self.ore_target is not None or self.built_harvester[0]:
                    if self.built_harvester[0] or self.ore_target in self.tit + self.ax:
                        if self.ore_target in self.unreachable_tiles:
                            self.unreachable_ores.append(self.ore_target)
                            if self.ore_target in self.tit:
                                self.tit.remove(self.ore_target)
                            elif self.ore_target in self.ax:
                                self.ax.remove(self.ore_target)
                            self.ore_target = None
                        else:
                            self.harvest_ore(ct, self.ore_target)
                    else:
                        self.ore_target = None
                elif len(self.tit) != 0 and (ct.get_current_round() <= 50 or len(self.mined_tit) < 4 or (len(self.mined_tit) < 8 and ct.get_current_round() >= 250 and len(self.enemy_mined_tit) == 0) or (ct.get_current_round() > 1000 and len(self.ax) == 0 and len(self.mined_ax) > 4 and len(self.mined_tit) < 12) or (len(self.mined_tit) < 12 and not (len(self.ax) != 0 and ((ct.get_global_resources()[0] > 750 and ct.get_global_resources()[1] == 0) or ct.get_current_round() >= 750))) or (ct.get_current_round() >= 1000 and ct.get_global_resources()[0] >= 1000)):
                    closest_tit = Position(1000, 1000)
                    for i in range(len(self.tit)):
                        if self.tit[i].distance_squared(self.core_pos) < closest_tit.distance_squared(self.core_pos):
                            closest_tit = self.tit[i]
                    self.harvest_ore(ct, closest_tit)
                    self.ore_target = closest_tit
                    ct.draw_indicator_line(self.pos, closest_tit, 0, 255, 0)
                elif len(self.ax) != 0 and ct.get_current_round() > 50 and len(self.mined_tit) > 0 and (len(self.mined_ax) < 2 or ct.get_current_round() > 1000 or (len(self.mined_ax) < 4 and ct.get_current_round() >= 250) or (ct.get_current_round() >= 1000 and ct.get_global_resources()[0] >= 1000)):
                    closest_ax = Position(1000, 1000)
                    for j in range(len(self.ax)):
                        if self.ax[j].distance_squared(self.core_pos) < closest_ax.distance_squared(self.core_pos):
                            closest_ax = self.ax[j]
                    self.harvest_ore(ct, closest_ax)
                    self.ore_target = closest_ax
                    ct.draw_indicator_line(self.pos, closest_ax, 0, 255, 0)
                #self.enemy_core_pos != Position(1000, 1000) and 
                elif len(self.mined_tit) > 4 and len(self.mined_ax)>2 and not (ct.get_current_round() >= 1000 and ct.get_global_resources()[0] >= 1000):
                    '''if self.map[self.enemy_core_pos.y][self.enemy_core_pos.x][1] == 0:
                        self.status = ATTACK_ENEMY_SUPPLY_LINES
                    else:
                        self.moving_turret_supply = False
                        self.status = MOVING_TURRET'''
                    self.status = ATTACK_ENEMY_SUPPLY_LINES
                    self.target = Position(1000, 1000)
                    self.explore_start = None
                else:
                    self.target = Position(1000, 1000)
                    self.status = EXPLORING

            elif self.status == DEFENCE:  # Defence algorithm
                self.defence(ct)

            elif self.status == ATTACK_ENEMY_CORE:
                print("Attacking Enemy Core")
                if self.enemy_core_pos == Position(1000, 1000):
                    if len(self.possible_core_locations) != 0:
                        self.target = Position(1000, 1000)
                        for loc in self.possible_core_locations:
                            loc_pos = Position(loc[0], loc[1])
                            if self.pos.distance_squared(loc_pos) < self.pos.distance_squared(self.target):
                                self.target = loc_pos
                        if self.target == Position(1000, 1000):
                            print("NOOOO", self.possible_core_locations)
                            return
                        if self.pos.distance_squared(self.target) > 13:
                            self.explore(ct)
                        else:
                            self.possible_core_locations.remove([self.target.x, self.target.y])
                    else:
                        self.possible_core_locations = [
                                                        [ct.get_map_width() - 1 - self.core_pos.x, self.core_pos.y],  # Horizontal Flip
                                                        [self.core_pos.x, ct.get_map_height() - 1 - self.core_pos.y],  # Vertical Flip
                                                        [ct.get_map_width() - 1 - self.core_pos.x, ct.get_map_height() - 1 - self.core_pos.y]]  # Rotation
                else:
                    if self.enemy_core_pos.distance_squared(self.pos) > 50:
                        self.target = self.enemy_core_pos
                        self.explore(ct)
                        return
                    self.attack_enemy_core(ct)

            elif self.status == ATTACK_ENEMY_SUPPLY_LINES:
                if self.enemy_core_pos == Position(1000, 1000):
                    print("Finding core", self.possible_core_locations)
                    if len(self.possible_core_locations) != 0:
                        self.target = Position(1000, 1000)
                        for loc in self.possible_core_locations:
                            loc_pos = Position(loc[0], loc[1])
                            if self.pos.distance_squared(loc_pos) < self.pos.distance_squared(self.target):
                                self.target = loc_pos
                        if self.target == Position(1000, 1000):
                            print("NOOOO", self.possible_core_locations)
                            return
                        if self.pos.distance_squared(self.target) > 13:
                            self.explore(ct)
                        else:
                            self.possible_core_locations.remove([self.target.x, self.target.y])
                    else:
                        self.possible_core_locations = [
                                                        [ct.get_map_width() - 1 - self.core_pos.x, self.core_pos.y],  # Horizontal Flip
                                                        [self.core_pos.x, ct.get_map_height() - 1 - self.core_pos.y],  # Vertical Flip
                                                        [ct.get_map_width() - 1 - self.core_pos.x, ct.get_map_height() - 1 - self.core_pos.y]]  # Rotation
                else:
                    print("Attack enemy supply lines")
                    print(self.target)
                    self.attack_enemy_supply_lines_V2(ct)

            elif self.status == MOVING_TURRET:
                print("Moving turret")
                if self.enemy_core_pos == Position(1000, 1000):
                    print("Finding core", self.possible_core_locations)
                    if len(self.possible_core_locations) != 0:
                        self.target = Position(1000, 1000)
                        for loc in self.possible_core_locations:
                            loc_pos = Position(loc[0], loc[1])
                            if self.pos.distance_squared(loc_pos) < self.pos.distance_squared(self.target):
                                self.target = loc_pos
                        if self.target == Position(1000, 1000):
                            print("NOOOO", self.possible_core_locations)
                            return
                        if self.pos.distance_squared(self.target) > 13:
                            self.explore(ct)
                        else:
                            self.possible_core_locations.remove([self.target.x, self.target.y])
                    else:
                        self.possible_core_locations = [
                                                        [ct.get_map_width() - 1 - self.core_pos.x, self.core_pos.y],  # Horizontal Flip
                                                        [self.core_pos.x, ct.get_map_height() - 1 - self.core_pos.y],  # Vertical Flip
                                                        [ct.get_map_width() - 1 - self.core_pos.x, ct.get_map_height() - 1 - self.core_pos.y]]  # Rotation
                elif len(self.mined_tit) == 0:
                    self.status = ATTACK_ENEMY_CORE
                else:
                    self.moving_turret(ct, self.enemy_core_pos)

            elif self.status == FOUNDRY:    # Defence fixes broken connections
                print("FOUNDRY")
                print(self.target)
                self.foundry(ct)

            elif self.status == ATTACK_ENEMY_CONVEYORS:
                print("ATTACK ENEMY CONVEYORS")
                self.attack_enemy_conveyors(ct)

        elif etype == EntityType.GUNNER:
            if self.status == INIT:
                self.gn_init(ct)
            elif self.status == ATTACK_ENEMY_CORE:
                print("ATTACK")
                self.gn_attack_enemy_core(ct)
            elif self.status == DEFENCE:
                print("DEFENCE")
                self.gn_defend_core(ct)

        elif etype == EntityType.SENTINEL:
            self.update_map(ct)
            if self.pos == None:
                self.pos = ct.get_position()
            if self.team == None:
                self.team = ct.get_team()
            if self.core_pos == Position(1000, 1000):
                for id in ct.get_nearby_buildings():
                    if ct.get_entity_type(id) == EntityType.CORE and ct.get_team(id) == self.team:
                        self.core_pos = Position(2000, 2000)
                if self.core_pos != Position(2000, 2000):
                    self.core_pos = Position(3000, 3000)
            target = None
            for tile in ct.get_attackable_tiles():
                xx = tile.x
                yy = tile.y
                map_tile = self.map[yy][xx]
                team = map_tile[2]
                building = map_tile[1]
                bot = map_tile[4]
                if building == EntityType.CORE and team != self.team and not (bot != None and ct.get_team(ct.get_tile_builder_bot_id(tile)) == self.team):   # Prioritise attacking core
                    target = tile
                    break
                elif team != self.team and building != EntityType.HARVESTER and not (bot != None and ct.get_team(ct.get_tile_builder_bot_id(tile)) == self.team):     # Then enemy buildings
                    end, own_team = self.simple_supply_connectivity(ct, tile)
                    if not (end != None and own_team == True):
                        target = tile
                elif bot != None and target == None and ct.get_team(ct.get_tile_builder_bot_id(tile)) != self.team:   # Then enemy builder bots
                    target = tile
            if target != None:
                if ct.can_fire(target):
                    ct.fire(target)
            else:
                if self.core_pos == Position(3000, 3000):
                    ct.self_destruct()
