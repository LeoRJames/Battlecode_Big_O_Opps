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
        self.built_harvester = [False, None]    # 0: True if built harvester and must connect; 1: Not False if built first conveyor and must move on to, otherwise stores position of that conveyor
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

                if entity == EntityType.SPLITTER and team == self.team:
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


                if self.map[tile.y][tile.x][0] == Environment.ORE_TITANIUM and tile not in self.tit and tile not in self.unreachable_ores and not(entity == EntityType.HARVESTER or (team != my_team and entity not in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.ROAD])):
                    self.tit.append(tile)
                elif self.map[tile.y][tile.x][0] == Environment.ORE_AXIONITE and  tile not in self.ax and tile not in self.unreachable_ores and not(entity == EntityType.HARVESTER or (team != my_team and entity not in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.ROAD])):
                    self.ax.append(tile)

                if entity == EntityType.HARVESTER:
                    if team == my_team:
                        if tile not in self.mined_tit and env == Environment.ORE_TITANIUM:
                            self.mined_tit.append(tile)
                        elif tile not in self.mined_ax and env == Environment.ORE_AXIONITE:
                            self.mined_ax.append(tile)
                    else:
                        if tile not in self.enemy_mined_tit and env == Environment.ORE_TITANIUM and tile not in self.attacked_enemy_mined_tit:
                            print("add")
                            self.enemy_mined_tit.append(tile)
                        elif tile not in self.enemy_mined_ax and env == Environment.ORE_AXIONITE:   # and tile not in self.attacked_enemy_mined_ax
                            self.enemy_mined_ax.append(tile)

                if tile in self.tit and (entity == EntityType.HARVESTER or (team != my_team and entity not in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.ROAD])): #  and (self.status != 2 or not self.built_harvester[0]):  # Remove from list if another bot has built harveter on it
                    self.tit.remove(tile)
                    if tile == self.ore_target:
                        self.ore_target = None
                elif tile in self.ax and (entity == EntityType.HARVESTER or (team != my_team and entity not in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.ROAD])): # and (self.status != 2 or not self.built_harvester[0]):
                    self.ax.remove(tile)
                    if tile == self.ore_target:
                        self.ore_target = None

            # No building on tile
            else:
                self.map[tile.y][tile.x][1] = None
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
                if current in unreachable:
                    continue

                tile = grid[ny][nx]

                if avoid:
                    valid = (
                        tile[1] in [EntityType.MARKER, EntityType.ROAD,
                                    EntityType.CORE, EntityType.SPLITTER]
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
            if current in unreachable:
                continue

            tile = grid[ny][nx]

            if tile[4] is not None and ct_pos.distance_squared(Position(cx, cy)) == 1:
                continue

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
                if current in unreachable:
                    continue

                tile = grid[ny][nx]

                if tile[0] == Environment.WALL:
                    continue

                if tile[0] == 0 or (current == target and (self.target.x, self.target.y) == target) or ((
                    not (tile[4] in [EntityType.BUILDER_BOT]
                        and ct_pos.distance_squared(Position(cx, cy)) <= 2)
                ) and (
                    tile[1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE,
                                EntityType.CONVEYOR, EntityType.MARKER,
                                EntityType.ROAD, EntityType.SPLITTER]
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
                if current in unreachable:
                    continue

                tile = grid[ny][nx]

                if not (
                    tile[4] in [EntityType.BUILDER_BOT]
                    and ct_pos.distance_squared(Position(cx, cy)) <= 2
                ) and (
                    tile[1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE,
                                EntityType.CONVEYOR, EntityType.MARKER,
                                EntityType.ROAD, EntityType.SPLITTER]
                    or (tile[1] == EntityType.CORE and tile[2] == team)
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


            if conv and counter > 20:   # At this point, better to build a
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
                    elif marker_status == 2 or 4:
                        if marker_status == 4:
                            self.attack_enemy_core_close = False
                        self.enemy_core_pos = Position(target_x, target_y)
                        print(marker_value, i)
                        print(marker_status, marker_value_id, target_x, target_y, self.id)
                        if marker_value_id == self.id:
                            self.target = self.enemy_core_pos
                            self.status = ATTACK_ENEMY_CORE
                            return
                    elif marker_status == 3:
                        self.enemy_core_pos = Position(target_x, target_y)
                        if marker_value_id == self.id:
                            self.target = self.enemy_core_pos
                            self.status = ATTACK_ENEMY_SUPPLY_LINES
                            return
                #else:
                #    if marker_status == 5 and not self.built_harvester[0]:
                #        self.target = Position(target_x, target_y)
                #        self.status = 5
                    #return marker_value_id
        if self.status == INIT:
            self.status = DEFENCE
            if sum([ 1 if ct.get_entity_type(i) == EntityType.BUILDER_BOT else 0 for i in ct.get_nearby_entities(5)]) > 4:
                self.status = EXPLORING

    def explore(self, ct, target=None):
        if self.invalid_tiles:
            print("Finding Invalid Tiles")
            self.find_invalid_tiles(ct, target)
            if self.built_harvester[1] != None:
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
                ct.draw_indicator_dot(path_explore[i], 0, 255, 255)
            if len(path_explore) > 1:    # If next to target but cannot move there as there is a builder bot this condition is not satisfied so will just wait
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

            # Happens to be on top of ore, move
            if self.map[self.pos.y][self.pos.x][2] == self.team and self.pos == ore:
                print(f"Moving from on top of ore")
                for d in DIRECTIONS:
                    if ct.can_build_road(self.pos.add(d)):
                        ct.build_road(self.pos.add(d))
                    if ct.can_move(d):
                        ct.move(d)
                        break

            # Checks if another bot has claimed the ore or there is a possible place to put conveyor next to harvester
            can_build_harvester = False
            if ct.get_entity_type(ct.get_tile_building_id(ore)) == EntityType.MARKER and ct.get_team(ct.get_tile_building_id(ore)) == self.team:
                marker_value = ct.get_marker_value(ct.get_tile_building_id(ore))
                marker_value_id = (marker_value % (2 ** 28)) // (2 ** 12)
                if marker_value_id == ct.get_id():
                    print(f"Secured harvester target : {ore}")
                    can_build_harvester = True
            elif self.map[ore.y][ore.x][1] in [EntityType.ROAD, None] and self.map[ore.y][ore.x][2] in [self.team, None] :
                for d in STRAIGHTS:
                    check_location = ore.add(d)
                    exists = True if 0 < check_location.x < ct.get_map_width() and 0 < check_location.y < ct.get_map_height() else False
                    if exists:
                        is_not_wall = True if self.map[check_location.y][check_location.x][0] != Environment.WALL else False
                        if is_not_wall and self.map[check_location.y][check_location.x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.ROAD, EntityType.BRIDGE, EntityType.SPLITTER, None] and self.map[check_location.y][check_location.x][2] in [self.team, None] :
                            can_build_harvester = True
                            self.built_harvester[1] = check_location

            if not can_build_harvester:
                print(f"Can not build Harvester at {ore}, removing from list.")
                self.ore_target = None
                self.unreachable_ores.append(ore)
                if ore in self.tit:
                    self.tit.remove(ore)
                elif ore in self.ax:
                    self.ax.remove(ore)
                else:
                    print("ore is not in tit or ax!")
                    #ct.resign()
                return

            if ore.distance_squared(self.pos) > 2:
                print(f"Ore is out of action range ({ore})")
                self.target = ore
                self.explore(ct, ore)
                self.target = Position(1000, 1000)
                return

            if ct.get_global_resources()[0] < ct.get_harvester_cost()[0] and ct.can_place_marker(ore):
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

            elif ct.get_global_resources()[0] >= ct.get_harvester_cost()[0]:
                if ct.can_destroy(ore) and self.map[ore.y][ore.x][1] not in [EntityType.HARVESTER, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR]:
                    ct.destroy(ore)
                if ct.can_build_harvester(ore):
                    ct.build_harvester(ore)
                    self.built_harvester[0] = True

        else:
            if self.built_harvester[1] is not None:
                print(f"Going to {self.built_harvester[1]}")
                if self.pos != self.built_harvester[1]:
                    self.target = self.built_harvester[1]
                    self.explore(ct)
                    return
                self.built_harvester[1] = None

            path_dict, cost, best_end_tile = self.pathfinder(ct, self.core_pos, bridge=True) # , avoid=True)
            if path_dict == None:
                return

            # Check if a path exists to core
            if best_end_tile != self.core_pos:
                # No path exists!
                print("No path home exists!")
                #ct.resign()     # PROBLEM
            path = self.reconstruct_path(path_dict, best_end_tile)
            ct.draw_indicator_line(path[1], path[0], 0, 0, 0)

            # Now find conveyor route to next best bridge location
            path_dict, cost, best_end_tile = self.pathfinder(ct, path[1], path[0], conv=True) #, avoid=True)
            if path_dict == None:
                return
            print(f"Bridge cost: {ct.get_bridge_cost()}, Conveyor cost: {cost[best_end_tile] * ct.get_conveyor_cost()}")
            if best_end_tile != path[1] or ct.get_bridge_cost()[0] < cost[best_end_tile] * ct.get_conveyor_cost()[0] :
                print("Bridge Path is Better!")
                if ct.can_destroy(path[0]):
                    ct.destroy(path[0])
                if ct.can_build_bridge(path[0], path[1]):
                    ct.build_bridge(path[0], path[1])
                    self.built_harvester[1] = path[1]
                elif ct.get_bridge_cost()[0] > ct.get_global_resources()[0]:
                    print("Waiting for money to build bridge")
                    return
            else:
                print("conveyor is better")
                path = self.reconstruct_path(path_dict, best_end_tile)
                conveyor_dir = path[0].direction_to(path[1])
                if ct.can_destroy(path[0]):
                    ct.destroy(path[0])
                if len(path) > 2 and self.map[path[1].y][path[1].x][1] == EntityType.CORE:
                    for d in STRAIGHTS:
                        yy = path[0].add(d).y
                        xx = path[0].add(d).x
                        if yy >= 0 and yy < len(self.map) and xx >= 0 and xx < len(self.map[0]) and self.map[path[0].add(d).y][path[0].add(d).x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR]:
                            direction = self.map[path[0].add(d).y][path[0].add(d).x][3][0]
                            if ct.can_build_splitter(path[0],direction):
                                ct.build_splitter(path[0], direction)
                                print("Path Building Complete")
                                self.built_harvester = [False, None]
                                self.ore_target = None
                                return
                            elif ct.get_splitter_cost()[0] > ct.get_global_resources()[0]:
                                print("Waiting for money to build splitter")
                                return

                if ct.can_build_conveyor(path[0], conveyor_dir):
                    ct.build_conveyor(path[0], conveyor_dir)
                    self.built_harvester[1] = path[1]
                elif ct.get_conveyor_cost()[0] > ct.get_global_resources()[0]:
                    print("Waiting for money to build conveyor")
                    return

            if self.map[path[1].y][path[1].x][1] in [EntityType.CORE, EntityType.SPLITTER, EntityType.ARMOURED_CONVEYOR, EntityType.CONVEYOR, EntityType.BRIDGE]:
                print("Path Building Complete")
                self.built_harvester = [False, None]
                self.ore_target = None

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
        else:
            print(wall_loop)
            for tile in wall_loop:
                ct.draw_indicator_dot(Position(tile[0], tile[1]), 255, 0, 0)
            inside_points = self.cells_inside_loop(wall_loop)
            print(inside_points)
            for tile in inside_points:
                ct.draw_indicator_dot(Position(tile[0], tile[1]), 0, 255, 0)
                self.unreachable_tiles.append(Position(tile[0], tile[1]))

    def find_enemy_core(self, ct):
        if self.enemy_core_pos == Position(1000, 1000) and self.target != Position(1000, 1000) and self.map[self.target.y][self.target.x][0] == 0:
            self.explore(ct, self.target)
        elif self.enemy_core_pos != Position(1000, 1000):  # Report enemy core position back to core
            self.status = REPORT_ENEMY_CORE_LOCATION
        elif len(self.tit + self.ax) != 0:    # Mine for ore
            self.status = MINING_TITANIUM
            self.target = Position(1000, 1000)
        else:   # Explore from outside corner in
            self.status = EXPLORING
            self.target = Position(1000, 1000)
        if ct.get_current_round() > 200:
            self.status = EXPLORING

    def attack_enemy_core(self, ct, close=None):
        if close == None:
            close = self.attack_enemy_core_close
        pos = self.pos
        vision_tiles = ct.get_nearby_tiles()
        list_of_gunners = []
        self.target = self.enemy_core_pos
        if self.pos.distance_squared(self.enemy_core_pos) <= 40:
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
                            self.target = building_target
                            print(self.target)

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
                        self.attack_enemy_core_close = False
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

    def defence(self, ct):
        print("DEFENCE")
        if ct.is_in_vision(self.core_pos) and ct.get_hp(ct.get_tile_building_id(self.core_pos)) < 500:
            self.target = self.core_pos
            if ct.can_heal(self.core_pos):
                ct.heal(self.core_pos)
            # Get back to core to heal
            if self.map[self.pos.y][self.pos.x][1] != EntityType.CORE:
                self.explore(ct)
            return

        self.target = self.core_pos
        vision_tiles = ct.get_nearby_tiles()
        pos = self.pos

        if self.target == self.core_pos:
            for i in vision_tiles:
                building_targets = None
                i_building = ct.get_entity_type(ct.get_tile_building_id(i))
                if i_building in [EntityType.SPLITTER]:
                    building_targets = [i.add(ct.get_direction(ct.get_tile_building_id(i))), i.add(ct.get_direction(ct.get_tile_building_id(i)).rotate_left().rotate_left()), i.add(ct.get_direction(ct.get_tile_building_id(i)).rotate_right().rotate_right())]
                elif i_building in [EntityType.FOUNDRY]:
                    building_targets = [i.add(Direction.NORTH), i.add(Direction.WEST), i.add(Direction.EAST), i.add(Direction.SOUTH)]
                elif self.pos.distance_squared(self.core_pos) <= 2 and ct.get_tile_building_id(i) != None and i_building in [EntityType.ROAD] and self.pos.distance_squared(i) <= 2 and ct.get_team(ct.get_tile_building_id(i)) == self.team:
                    self.target = i
                if building_targets != None:
                    for building_target in building_targets:
                        
                        if building_target.x >= 0 and building_target.x < len(self.map[0]) and building_target.y >= 0 and building_target.y < len(self.map) and ct.is_in_vision(building_target) and ((i_building == EntityType.FOUNDRY and ct.get_entity_type(ct.get_tile_building_id(building_target)) not in [EntityType.CORE, EntityType.SPLITTER, EntityType.HARVESTER, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.FOUNDRY]) or (i_building == EntityType.SPLITTER and ct.get_entity_type(ct.get_tile_building_id(building_target)) not in [EntityType.CORE, EntityType.SPLITTER, EntityType.HARVESTER, EntityType.SENTINEL, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.FOUNDRY])) and ct.get_tile_env(building_target) != Environment.WALL:
                            if ct.get_entity_type(ct.get_tile_building_id(building_target)) != EntityType.GUNNER or i_building != EntityType.SPLITTER or (ct.get_entity_type(ct.get_tile_building_id(building_target)) == EntityType.GUNNER and i_building == EntityType.SPLITTER and ct.get_sentinel_cost()[0] < ct.get_global_resources()[0]):
                                if building_target.distance_squared(pos) < self.target.distance_squared(pos) or self.target == self.core_pos:
                                    self.target = building_target
                                    print(self.target)

            for i in ct.get_nearby_tiles():
                if ct.get_hp(ct.get_tile_building_id(i)) < ct.get_max_hp(ct.get_tile_building_id(i)) and ct.get_team() == self.team:
                    if i.distance_squared(pos) < self.target.distance_squared(pos) or self.target == self.core_pos:
                        print(f"Healing {i}")
                        self.target = i

        if self.target == self.core_pos and ct.get_entity_type(ct.get_tile_building_id(pos)) == EntityType.CORE:
            print("Cry")
            return
        
        if self.pos.distance_squared(self.target) > 2:
            self.explore(ct)
            return

        elif ct.can_heal(self.target) and ct.get_entity_type(ct.get_tile_building_id(self.target)) != EntityType.ROAD:
            print("Healing")
            ct.heal(self.target)
            return
        elif ct.can_destroy(self.target) and ct.get_entity_type(ct.get_tile_building_id(self.target)) not in [EntityType.SPLITTER, EntityType.GUNNER, EntityType.HARVESTER, EntityType.SENTINEL, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.FOUNDRY]:
            ct.destroy(self.target)
            self.target = self.core_pos
        if self.target in ct.get_nearby_tiles():
            for d in STRAIGHTS:
                if ct.get_entity_type(ct.get_tile_building_id(self.target)) == EntityType.GUNNER and ct.can_destroy(self.target) and ct.get_sentinel_cost()[0] <= ct.get_global_resources()[0]:
                    ct.destroy(self.target)
                if (( 0 < self.target.add(d).y < ct.get_map_height() and ct.get_tile_building_id(self.target.add(d)) is not None) and
                        0 < self.target.add(d).x < ct.get_map_width() and ct.get_entity_type(ct.get_tile_building_id(self.target.add(d))) in [EntityType.SPLITTER, EntityType.FOUNDRY] and 
                        ct.can_build_sentinel(self.target, self.target.direction_to(self.core_pos).opposite())):
                    ct.build_sentinel(self.target, self.target.direction_to(self.core_pos).opposite())
                elif (( 0 < self.target.add(d).y < ct.get_map_height() and ct.get_tile_building_id(self.target.add(d)) is not None) and 
                        (0 < self.target.add(d).x < ct.get_map_width() and ct.get_entity_type(ct.get_tile_building_id(self.target.add(d))) in [EntityType.SPLITTER, EntityType.FOUNDRY]) and 
                        ct.can_build_gunner(self.target, d.opposite())):
                    ct.build_gunner(self.target, d.opposite())

        if pos == self.target:
            for d in DIRECTIONS:
                if ct.can_move(d):
                    ct.move(d)

        #if not(ct.get_position().add(ct.get_position().direction_to(self.target)) == self.target):
            #self.explore(ct)

    def gn_init(self,ct):
        vision_tiles = ct.get_nearby_tiles()
        for i in vision_tiles:
            if ct.get_tile_building_id(i) is not None and ct.get_entity_type(ct.get_tile_building_id(i)) == EntityType.CORE:
                if ct.get_team(ct.get_tile_building_id(i)) != ct.get_team():
                    self.status = ATTACK_ENEMY_CORE
                else:
                    self.status = DEFENCE
                return

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
                    if ct.can_rotate(target.direction_to(i)):
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
        target = ct.get_position()

        for i in range(2):
            target = target.add(d)
            if not(0 < target.add(d).x < ct.get_map_width() and 0 < target.add(d).y < ct.get_map_height()):
                break
            if (ct.get_entity_type(ct.get_tile_builder_bot_id(target)) == EntityType.BUILDER_BOT and ct.get_team() != ct.get_team(ct.get_tile_builder_bot_id(target))) or (ct.get_team(ct.get_tile_building_id(target)) not in [None, ct.get_team()] and ct.get_entity_type(ct.get_tile_building_id(target)) not in [EntityType.ROAD, EntityType.MARKER]):
                if ct.can_fire(target):
                    ct.fire(target)
                elif ct.get_ammo_amount()    < 2:
                    print("Out of Ammo")
                return

        target = ct.get_position()
        # If no builder bot found, look for one:
        for i in [target.add(d) for d in DIRECTIONS] + [target.add(d).add(d) for d in DIRECTIONS]:
            if i.x < 0 or i.x >= ct.get_map_width() or i.y<0 or i.y >= ct.get_map_height():
                continue
            if (ct.get_entity_type(ct.get_tile_builder_bot_id(i)) == EntityType.BUILDER_BOT and ct.get_team() != ct.get_team(ct.get_tile_builder_bot_id(i))) or (ct.get_team(ct.get_tile_building_id(i)) != ct.get_team() and ct.get_entity_type(ct.get_tile_building_id(i)) not in [EntityType.ROAD, EntityType.MARKER]):
                ct.draw_indicator_dot(i, 255, 0, 0)
                if ct.can_rotate(target.direction_to(i)) and ct.get_global_resources()[0] > 100:
                    ct.rotate(target.direction_to(i))
                    break

    '''def exploring_the_map(self,  ct):
        if self.target != Position(1000, 1000) and self.map[self.target.y][self.target.x][0] == 0:
            self.explore(ct)
        else:
            CORNERS = ((0, 0))'''

    def exploring_the_map(self, ct):
        if self.target != Position(1000, 1000) and self.map[self.target.y][self.target.x][0] == 0:
            self.explore(ct)
        else:
            self.target = Position(1000, 1000)
            CORNERS = [Position(0, 0), Position(ct.get_map_width()-1, 0), Position(0, ct.get_map_height()-1), Position(ct.get_map_width()-1, ct.get_map_height()-1)]
            closest_corner = self.target    #=Position(1000, 1000)
            iteration = 0
            while closest_corner == Position(1000, 1000) and iteration < (Position(0, 0).distance_squared(Position(int(ct.get_map_width()/2), int(ct.get_map_height()/2))))/7: # Ends if new position to explore is found or is at centre
                for corner in CORNERS:
                    for i in range(7*iteration):
                        corner = corner.add(Direction.CENTRE)
                        if corner == Position(int(ct.get_map_width()/2), int(ct.get_map_height()/2)):
                            break
                    if self.map[corner.y][corner.x] == [0, 0, 0, [0], 0] and self.pos.distance_squared(corner) < self.pos.distance_squared(closest_corner):
                        closest_corner = corner
                iteration += 1
            if closest_corner == Position(1000, 1000):
                self.status = DEFENCE # Switch to defence for now
                self.target = Position(1000, 1000)
            else:   # Explore to chosen corner
                self.target = closest_corner
                self.explore(ct)
            # Find closest corner, move until it is in vision radius (covered by first if)
            ct.draw_indicator_dot(self.target, 255, 0, 0)

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
                    self.status = EXPLORING
                    print("Reported Enemy Core Location back to Base")
                    self.target = Position(0, 0)
                    return
            if ct.can_place_marker(pos.add(i)):
                ct.place_marker(pos.add(i), message)
                break
        self.explore(ct)

    def run(self, ct: Controller) -> None:

        #if ct.get_current_round() > 500:
        #    ct.resign()

        etype = ct.get_entity_type()

        if etype == EntityType.CORE:

            if self.team == None:
                self.team = ct.get_team()
                self.pos = ct.get_position()
                self.id = ct.get_id()
                self.core_pos = self.pos

            self.update_map(ct)

            # Inital 3 bots to find enemy core location
            if self.num_spawned < 3:
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
                            + possible_core_locations[self.num_spawned][0] * (2**6)
                            + possible_core_locations[self.num_spawned][1])
                    self.num_spawned += 1
                    for i in ct.get_nearby_tiles(6):    # Will sometimes cause errors where builder bot cannot move to tile where marker was placed and destroy it
                        if ct.can_place_marker(i) and ct.is_tile_empty(i):
                            ct.place_marker(i, message)
                            break

            # Bots to do healing
            elif ct.get_hp() < 500 or self.num_spawned < 5:
                print("Healing bots")
                core_tiles = ct.get_nearby_tiles(3)
                for i in core_tiles:
                    if ct.can_spawn(i):
                        ct.spawn_builder(i)
                        self.num_spawned += 1
                        break

            # Bots to attack supply lines
            elif self.enemy_core_pos != Position(1000, 1000) and 9 <= self.num_spawned < 13: # 10 <= ...
                if ct.get_global_resources()[0] < ct.get_builder_bot_cost()[0]:
                    print("Waiting for resources to spawn builder bot")
                    return
                for spawn_pos in ct.get_nearby_tiles(8):
                    if ct.can_spawn(spawn_pos):
                        ct.spawn_builder(spawn_pos)
                        # Place marker, so bot knows where to go
                        bot_id = ct.get_tile_builder_bot_id(spawn_pos)
                        marker_status = 3   # Defence bot
                        message = (
                                marker_status * (2**28)
                                + bot_id * (2**12)
                                + self.enemy_core_pos.x * (2 ** 6)
                                + self.enemy_core_pos.y)

                        self.num_spawned += 1
                        for i in ct.get_nearby_tiles(7):
                            ct.draw_indicator_dot(i,200,200,200)
                            if ct.can_place_marker(i) and ct.is_tile_empty(i):
                                ct.place_marker(i, message)
                        break

            # Extra bots to attack enemy core
            elif self.enemy_core_pos != Position(1000, 1000) and (self.num_spawned < 13 or (self.num_spawned < 20 and ct.get_global_resources()[0] > 1000)): # need a better check
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
                        message = (
                                marker_status * (2**28)
                                + bot_id * (2**12)
                                + self.enemy_core_pos.x * (2 ** 6)
                                + self.enemy_core_pos.y)

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
                if len(self.tit + self.ax) != 0:
                    self.target = Position(1000, 1000)
                    self.status = MINING_TITANIUM
                elif len(self.enemy_mined_tit) != 0 and self.enemy_core_pos != Position(1000, 1000):
                    self.target = Position(1000, 1000)
                    self.status = ATTACK_ENEMY_SUPPLY_LINES
                else:
                    print("Done everything")
                    #self.status = ATTACK_ENEMY_CORE
                    self.exploring_the_map(ct)

            elif self.status == MINING_TITANIUM:  # Mining ore
                print("Mining")
                if self.ore_target is not None:
                    if self.ore_target in self.tit + self.ax:
                        self.harvest_ore(ct, self.ore_target)
                    else:
                        self.ore_target = None
                elif len(self.tit) != 0 and not (len(self.ax) != 0 and ct.get_current_round() >= 750):
                    closest_tit = Position(1000, 1000)
                    for i in range(len(self.tit)):
                        if self.tit[i].distance_squared(self.core_pos) < closest_tit.distance_squared(self.core_pos):
                            closest_tit = self.tit[i]
                    self.harvest_ore(ct, closest_tit)
                    self.ore_target = closest_tit
                    ct.draw_indicator_line(self.pos, closest_tit, 0, 255, 0)
                elif len(self.ax) != 0:
                    closest_ax = Position(1000, 1000)
                    for j in range(len(self.ax)):
                        if self.ax[j].distance_squared(self.core_pos) < closest_ax.distance_squared(self.core_pos):
                            closest_ax = self.ax[j]
                    self.harvest_ore(ct, closest_ax)
                    self.ore_target = closest_ax
                    ct.draw_indicator_line(self.pos, closest_ax, 0, 255, 0)
                elif self.enemy_core_pos != Position(1000, 1000):
                    self.target = Position(1000, 1000)
                    self.status = ATTACK_ENEMY_SUPPLY_LINES
                else:
                    self.target = Position(1000, 1000)
                    self.status = EXPLORING

            elif self.status == DEFENCE:  # Defence algorithm
                self.defence(ct)

            elif self.status == ATTACK_ENEMY_CORE:
                print("Attacking Enemy Core")
                if self.enemy_core_pos.distance_squared(self.pos) > 40:
                    self.target = self.enemy_core_pos
                    self.explore(ct)
                    return
                self.attack_enemy_core(ct)

            elif self.status == ATTACK_ENEMY_SUPPLY_LINES:
                print("Attack enemy supply lines")
                print(self.target)
                if self.enemy_core_pos == Position(1000, 1000):
                    self.target = Position(1000, 1000)
                    self.status = EXPLORING
                    return
                if (self.target == Position(1000, 1000) or self.target == self.enemy_core_pos) and len(self.enemy_mined_tit) != 0:
                    self.target = self.enemy_mined_tit[0]
                    self.enemy_mined_tit_target = self.enemy_mined_tit[0]
                elif self.target == self.enemy_core_pos and self.enemy_core_pos.distance_squared(self.pos) > 20:
                    self.explore(ct)
                    return
                elif len(self.enemy_mined_tit) == 0:
                    self.target = Position(1000, 1000)
                    self.enemy_mined_tit_target = None
                    self.exploring_the_map(ct)
                    return
                elif self.enemy_mined_tit_target == None:   # Robust check
                    if len(self.enemy_mined_tit) != 0:
                        self.target = self.enemy_mined_tit[0]
                        self.enemy_mined_tit_target = self.enemy_mined_tit[0]
                    else:
                        self.target = Position(1000, 1000)
                        self.enemy_mined_tit_target = None
                        self.exploring_the_map(ct)
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
                        return
                    # Non-passable enemy tile built on target tile or own building that do not want to destroy
                    elif 0 < self.pos.distance_squared(self.target) <= 20 and ((self.map[self.target.y][self.target.x][2] != self.team and self.map[self.target.y][self.target.x][1] not in [EntityType.ROAD, EntityType.CONVEYOR, EntityType.SPLITTER, EntityType.BRIDGE]) or (self.map[self.target.y][self.target.x][2] in [self.team, None] and self.map[self.target.y][self.target.x][1] not in [EntityType.BARRIER, EntityType.MARKER, EntityType.ROAD, None])):
                        self.target = self.enemy_mined_tit_target
                    elif (self.pos != self.target and self.map[self.target.y][self.target.x][2] != ct.get_team()) or (self.pos.distance_squared(self.target) > 2 and (self.map[self.target.y][self.target.x][2] == self.team or self.map[self.target.y][self.target.x][1] == None)):
                        self.explore(ct)

            elif self.status == FOUNDRY:
                print("FOUNDRY")
                if self.target == Position(1000, 1000):
                    self.status = DEFENCE
                    return
                if self.pos.distance_squared(self.target) > 2:
                    self.explore(ct)
                    '''came_from, cost, best_tile = self.pathfinder(ct, self.target)
                    if came_from == None:
                        return
                    path = self.reconstruct_path(came_from, best_tile)
                    if len(path) > 1:
                        if ct.can_build_road(path[1]):
                            ct.build_road(path[1])
                        if ct.can_move(self.pos.direction_to(path[1])):
                            ct.move(self.pos.direction_to(path[1]))'''
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
                            elif building in [EntityType.GUNNER, EntityType.SENTINEL] and team == self.team and chosen_tile == None:    # If turret on tile then could build here if not another tile already found
                                chosen_tile = check_tile
                             # reset now before target is changed as not needed to remain True
                        if chosen_tile == None:
                            self.splitter_resource[self.target] = False
                            self.target = Position(1000, 1000)
                            self.status = DEFENCE
                        else:
                            self.splitter_target = self.target
                            self.target = chosen_tile
                        
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
                                ct.destroy(self.target)
                            else:
                                self.splitter_resource[self.target] = False
                                self.target = Position(1000, 1000)
                                self.status = DEFENCE
                        if ct.can_build_foundry(self.target):
                            ct.build_foundry(self.target)
                            self.splitter_resource[self.splitter_target] = False
                            self.splitter_target = None
                            self.target = Position(1000, 1000)
                            self.status = DEFENCE
                            return

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
                    target = tile
                elif bot != None and target == None and ct.get_team(ct.get_tile_builder_bot_id(tile)) != self.team:   # Then enemy builder bots
                    target = tile
            if target != None:
                if ct.can_fire(target):
                    ct.fire(target)
