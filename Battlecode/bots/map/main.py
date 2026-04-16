import random
from queue import PriorityQueue
from collections import deque
from cambc import Controller, Direction, EntityType, Environment, Position
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
        self.core_stored_resource = {}
        self.marker_locations = []
        self.unreachable_ores = [] # List of unreachable ores
        self.unreachable_tiles = []
        self.came_from = None   # Save pathfinder state for continuing in next turn
        self.cost_so_far = None
        self.best_tile = None
        self.closed = None
        self.open_heap = None
        self.ore_target = None  # Prevents constant changing of ore target

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

            if self.map[tile.y][tile.x][0] == 0:
                self.map[tile.y][tile.x][0] = ct.get_tile_env(tile)

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

                if self.map[tile.y][tile.x][0] == Environment.ORE_TITANIUM and tile not in self.tit and tile not in self.unreachable_ores and not(entity == EntityType.HARVESTER or (team != my_team and entity not in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.ROAD])):
                    self.tit.append(tile)
                elif self.map[tile.y][tile.x][0] == Environment.ORE_AXIONITE and  tile not in self.ax and tile not in self.unreachable_ores and not(entity == EntityType.HARVESTER or (team != my_team and entity not in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.ROAD])):
                    self.ax.append(tile)

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

    def _neighbors_bridge(self, current, grid, width, height, unreachable, team, ct_pos, avoid):

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

    def _neighbors_conv(self, current, grid, width, height, unreachable, team, ct_pos, avoid):

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

    def _neighbors_any(self, current, grid, width, height, unreachable, team, ct_pos, avoid):

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

                if tile[0] == 0 or ((
                    not (tile[4] in [EntityType.BUILDER_BOT]
                        and ct_pos.distance_squared(Position(cx, cy)) <= 2)
                ) and (
                    tile[1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE,
                                EntityType.CONVEYOR, EntityType.MARKER,
                                EntityType.ROAD, EntityType.SPLITTER]
                    or (tile[1] == EntityType.CORE and tile[2] == team)
                    or (tile[1] is None and tile[0] != Environment.WALL)
                )):
                    results.append((nx, ny))

        return results

    def _neighbors_normal(self, current, grid, width, height, unreachable, team, ct_pos, avoid):

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
                unreachable, team, ct_pos, avoid
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

    '''def pathfinder(self, ct, target, start=None, bridge=False, conv=False, avoid=False, any=False):       # Pass Position
        pre_path_finder_time = ct.get_cpu_time_elapsed()
        if start == None:
            start = self.pos
        start = (start.x, start.y)
        target = (target.x, target.y)
        moveTile = 0        # Tie breakers for equal path lengths
        dist = 0
        q = []
        heapq.heappush(q, (0, moveTile, dist, start))  # Priority list to choose which tile to check next
        came_from = {}      # Dictionary of movement path
        cost_so_far = {}    # Dictionary of cost of movement
        came_from[start] = None
        cost_so_far[start] = 0
        closed = set()
        grid = self.map
        height = len(grid)
        width = len(grid[0])
        unreachable = self.unreachable_tiles
        team = self.team
        best_tile = start
        if bridge:
            best_dist = (self.heuristic_squaredEuclidean(start, target))**(1/2)
        else:
            best_dist = self.heuristic_Chebyshev(start, target)

        counter = 0
        while q:
            counter += 1
            if counter%10 == 0:
                print(counter)
            _, _, _, current = heapq.heappop(q)   # Returns highest priority item on queue

            if current in closed:   # Prevents revisiting of tiles already evaluated
                continue

            closed.add(current)

            if current == target:
                best_tile = current
                break

            # Update best reachable tile
            if bridge:
                d = (self.heuristic_squaredEuclidean(current[3], target))**(1/2)
            else:
                d = self.heuristic_Chebyshev(current[3], target)    #abs(current[3].x - target.x) + abs(current[3].y - target.y)   # self.heuristic_Chebyshev(current[3], target)
            if d < best_dist:
                best_dist = d
                best_tile = current
            
            check_tiles = []
            
            # Adds all surrounding
            if bridge:      # If bridge consider all tiles a bridge can be built to
                if avoid:
                    for i in range(7):
                        for j in range(7):
                            if (not (i == 3 and j == 3)) and ((((i-3)**2)+((j-3)**2)) <= 9) and current[3].x + (i-3) >= 0 and current[3].x + (i-3) < len(self.map[0]) and current[3].y + (j-3) >= 0 and current[3].y + (j-3) < len(self.map) and (current[3] not in self.unreachable_tiles) and ((self.map[current[3].y + (j-3)][current[3].x + (i-3)][1] in [EntityType.MARKER, EntityType.ROAD, EntityType.CORE, EntityType.SPLITTER] and self.map[current[3].y + (j-3)][current[3].x + (i-3)][2] == self.team) or (self.map[current[3].y + (j-3)][current[3].x + (i-3)][1] == None and self.map[current[3].y + (j-3)][current[3].x + (i-3)][0] in [Environment.EMPTY])):  # (not (self.map[current[3].y + (j-3)][current[3].x + (i-3)][4] in [EntityType.BUILDER_BOT] and self.pos.distance_squared(current[3]) <= 9)) and 
                                check_tiles.append((current[3].x + (i-3), current[3].y + (j-3)))
                                #ct.draw_indicator_dot(Position(current[3].x + (i-3), current[3].y + (j-3)), 255, 0, 0)
                else:
                    for i in range(7):
                        for j in range(7):
                            if (not (i == 3 and j == 3)) and ((((i-3)**2)+((j-3)**2)) <= 9) and current[3].x + (i-3) >= 0 and current[3].x + (i-3) < len(self.map[0]) and current[3].y + (j-3) >= 0 and current[3].y + (j-3) < len(self.map) and (current[3] not in self.unreachable_tiles) and ((self.map[current[3].y + (j-3)][current[3].x + (i-3)][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.MARKER, EntityType.ROAD, EntityType.CORE, EntityType.SPLITTER] and self.map[current[3].y + (j-3)][current[3].x + (i-3)][2] == self.team) or (self.map[current[3].y + (j-3)][current[3].x + (i-3)][1] == None and self.map[current[3].y + (j-3)][current[3].x + (i-3)][0] in [Environment.EMPTY])):  # (not (self.map[current[3].y + (j-3)][current[3].x + (i-3)][4] in [EntityType.BUILDER_BOT] and self.pos.distance_squared(current[3]) <= 9)) and 
                                check_tiles.append((current[3].x + (i-3), current[3].y + (j-3)))
                                #ct.draw_indicator_dot(Position(current[3].x + (i-3), current[3].y + (j-3)), 255, 0, 0)
            elif conv:      # If conveyor, consider only straight surrounding tiles
                if avoid:
                    for i in range(3):
                        for j in range(3):
                            if (not (abs(i-1) == abs(j-1))) and current[3].x + (i-1) >= 0 and current[3].x + (i-1) < len(self.map[0]) and current[3].y + (j-1) >= 0 and current[3].y + (j-1) < len(self.map) and (current[3] not in self.unreachable_tiles) and ((self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] in [EntityType.MARKER, EntityType.ROAD, EntityType.CORE, EntityType.SPLITTER] and self.map[current[3].y + (j-1)][current[3].x + (i-1)][2] == self.team) or (self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] == None and self.map[current[3].y + (j-1)][current[3].x + (i-1)][0] in [Environment.EMPTY])) and not (self.map[current[3].y + (j-1)][current[3].x + (i-1)][4] is not None and current[3].distance_squared(self.pos) == 1):  # (not (self.map[current[3].y + (j-1)][current[3].x + (i-1)][4] in [EntityType.BUILDER_BOT] and self.pos.distance_squared(current[3]) <= 1) and
                                check_tiles.append((current[3].x + (i-1), current[3].y + (j-1)))
                                #ct.draw_indicator_dot(Position(current[3].x + (i-1), current[3].y + (j-1)), 0, 255, 0)
                else:
                    for i in range(3):
                        for j in range(3):
                            if (not (abs(i-1) == abs(j-1))) and current[3].x + (i-1) >= 0 and current[3].x + (i-1) < len(self.map[0]) and current[3].y + (j-1) >= 0 and current[3].y + (j-1) < len(self.map) and (current[3] not in self.unreachable_tiles) and ((self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.MARKER, EntityType.ROAD, EntityType.CORE, EntityType.SPLITTER] and self.map[current[3].y + (j-1)][current[3].x + (i-1)][2] == self.team) or (self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] == None and self.map[current[3].y + (j-1)][current[3].x + (i-1)][0] in [Environment.EMPTY])) and not (self.map[current[3].y + (j-1)][current[3].x + (i-1)][4] is not None and current[3].distance_squared(self.pos) == 1):  # (not (self.map[current[3].y + (j-1)][current[3].x + (i-1)][4] in [EntityType.BUILDER_BOT] and self.pos.distance_squared(current[3]) <= 1) and
                                check_tiles.append((current[3].x + (i-1), current[3].y + (j-1)))
                                #ct.draw_indicator_dot(Position(current[3].x + (i-1), current[3].y + (j-1)), 0, 255, 0)
            elif any:
                for i in range(3):
                    for j in range(3):
                        if (not (i == 1 and j == 1)) and current[3].x + (i-1) >= 0 and current[3].x + (i-1) < len(self.map[0]) and current[3].y + (j-1) >= 0 and current[3].y + (j-1) < len(self.map) and (current[3] not in self.unreachable_tiles) and (self.map[current[3].y + (j-1)][current[3].x + (i-1)][0] == 0 or (not (self.map[current[3].y + (j-1)][current[3].x + (i-1)][4] in [EntityType.BUILDER_BOT] and self.pos.distance_squared(current[3]) <= 2)) and (self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.MARKER, EntityType.ROAD, EntityType.SPLITTER] or (self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] == EntityType.CORE and self.map[current[3].y + (j-1)][current[3].x + (i-1)][2] == self.team) or (self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] == None and self.map[current[3].y + (j-1)][current[3].x + (i-1)][0] != Environment.WALL))):
                            check_tiles.append((current[3].x + (i-1), current[3].y + (j-1)))
            
            else:           # If normal one square movement, consider all surrounding tiles from current position
                for i in range(3):
                    for j in range(3):
                        if (not (i == 1 and j == 1)) and current[3].x + (i-1) >= 0 and current[3].x + (i-1) < len(self.map[0]) and current[3].y + (j-1) >= 0 and current[3].y + (j-1) < len(self.map) and (current[3] not in self.unreachable_tiles) and ((not (self.map[current[3].y + (j-1)][current[3].x + (i-1)][4] in [EntityType.BUILDER_BOT] and self.pos.distance_squared(current[3]) <= 2)) and (self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.MARKER, EntityType.ROAD, EntityType.SPLITTER] or (self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] == EntityType.CORE and self.map[current[3].y + (j-1)][current[3].x + (i-1)][2] == self.team) or (self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] == None and self.map[current[3].y + (j-1)][current[3].x + (i-1)][0] != Environment.WALL))):
                            check_tiles.append((current[3].x + (i-1), current[3].y + (j-1)))
                            #ct.draw_indicator_dot(Position(current[3].x + (i-1), current[3].y + (j-1)), 0, 0, 255)
            for tile in check_tiles:
                moveTile = 0
                dist = 11
                tile_pos = Position(tile[0], tile[1])
                #if current[3].distance_squared(tile_pos) > 1:   # Prefer to move in a straight line rather than diagonally
                    #counter += 1
                if self.map[tile[1]][tile[0]][1] == None:   # Prefer not to move over non-passable spaces (to save resources building extra paths)
                    moveTile += 1
                if bridge:
                    dist = dist - current[3].distance_squared(tile_pos) # Prefer to build longest bridge
                else:
                    dist = current[3].distance_squared(tile_pos)    # Prefer to move in straight lines (as I think is more valuable for information)
                #ct.draw_indicator_dot(tile, 0, 0, 255)
                if bridge:
                    new_cost = cost_so_far[current[3]] + (tile_pos.distance_squared(current[3]))**(1/2)
                    #new_cost = cost_so_far[current[3]] + tile_pos.distance_squared(current[3])  # For bridges, squared euclidean distance matters
                else:
                    new_cost = cost_so_far[current[3]] + 1     # Each move costs one move cooldown whether straight or diagonal for general movement
                if tile_pos not in cost_so_far or new_cost < cost_so_far[tile_pos]:     # Considers tile if not considered before or new path gets to it quicker
                    cost_so_far[tile_pos] = new_cost    # Updates smallest cost for location
                    if bridge:      # Calculates which tile to move to based off heuristic
                        priority = new_cost + self.heuristic_squaredEuclidean(tile_pos, target)
                    elif conv:
                        priority = new_cost + self.heuristic_Chebyshev(tile_pos, target)
                    else:   # General movement
                        priority = new_cost + abs(tile_pos.x - target.x) + abs(tile_pos.y - target.y)
                    q.put((priority, moveTile, dist, tile_pos))
                    came_from[tile_pos] = current[3]    # Updates check locations
            #break
        post_path_finder_time = ct.get_cpu_time_elapsed()
        print(f" Path Finder Time: {post_path_finder_time - pre_path_finder_time}, ({counter})")
        print(f"Current Time: {post_path_finder_time}")
        return came_from, cost_so_far, best_tile'''

    '''def pathfinder(self, ct, target, start=None, bridge=False, conv=False, avoid=False, any=False):       # Pass Position
        pre_path_finder_time = ct.get_cpu_time_elapsed()
        if start == None:
            start = self.pos
        q = PriorityQueue()
        moveTile = 0        # Tie breakers for equal path lengths
        dist = 0
        q.put((0, moveTile, dist,  start))  # Priority list to choose which tile to check next
        came_from = {}      # Dictionary of movement path
        cost_so_far = {}    # Dictionary of cost of movement
        came_from[start] = None
        cost_so_far[start] = 0
        best_tile = start
        if bridge:
            best_dist = self.heuristic_squaredEuclidean(start, target)
        else:
            best_dist = self.heuristic_Chebyshev(start, target)

        counter = 0
        while not q.empty():
            counter += 1
            if counter%10 == 0:
                print(counter)
            current = q.get()   # Returns highest priority item on queue

            # Update best reachable tile
            if bridge:
                d = (self.heuristic_squaredEuclidean(current[3], target))**(1/2)
            else:
                d = self.heuristic_Chebyshev(current[3], target)    #abs(current[3].x - target.x) + abs(current[3].y - target.y)   # self.heuristic_Chebyshev(current[3], target)
            if d < best_dist:
                best_dist = d
                best_tile = current[3]
                if d == 0:
                    break
            
            if (current[3].x == target.x) and (current[3].y == target.y):
                break
            
            check_tiles = []
            
            # Adds all surrounding
            if bridge:      # If bridge consider all tiles a bridge can be built to
                if avoid:
                    for i in range(7):
                        for j in range(7):
                            if (not (i == 3 and j == 3)) and ((((i-3)**2)+((j-3)**2)) <= 9) and current[3].x + (i-3) >= 0 and current[3].x + (i-3) < len(self.map[0]) and current[3].y + (j-3) >= 0 and current[3].y + (j-3) < len(self.map) and (current[3] not in self.unreachable_tiles) and ((self.map[current[3].y + (j-3)][current[3].x + (i-3)][1] in [EntityType.MARKER, EntityType.ROAD, EntityType.CORE, EntityType.SPLITTER] and self.map[current[3].y + (j-3)][current[3].x + (i-3)][2] == self.team) or (self.map[current[3].y + (j-3)][current[3].x + (i-3)][1] == None and self.map[current[3].y + (j-3)][current[3].x + (i-3)][0] in [Environment.EMPTY])):  # (not (self.map[current[3].y + (j-3)][current[3].x + (i-3)][4] in [EntityType.BUILDER_BOT] and self.pos.distance_squared(current[3]) <= 9)) and 
                                check_tiles.append((current[3].x + (i-3), current[3].y + (j-3)))
                                #ct.draw_indicator_dot(Position(current[3].x + (i-3), current[3].y + (j-3)), 255, 0, 0)
                else:
                    for i in range(7):
                        for j in range(7):
                            if (not (i == 3 and j == 3)) and ((((i-3)**2)+((j-3)**2)) <= 9) and current[3].x + (i-3) >= 0 and current[3].x + (i-3) < len(self.map[0]) and current[3].y + (j-3) >= 0 and current[3].y + (j-3) < len(self.map) and (current[3] not in self.unreachable_tiles) and ((self.map[current[3].y + (j-3)][current[3].x + (i-3)][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.MARKER, EntityType.ROAD, EntityType.CORE, EntityType.SPLITTER] and self.map[current[3].y + (j-3)][current[3].x + (i-3)][2] == self.team) or (self.map[current[3].y + (j-3)][current[3].x + (i-3)][1] == None and self.map[current[3].y + (j-3)][current[3].x + (i-3)][0] in [Environment.EMPTY])):  # (not (self.map[current[3].y + (j-3)][current[3].x + (i-3)][4] in [EntityType.BUILDER_BOT] and self.pos.distance_squared(current[3]) <= 9)) and 
                                check_tiles.append((current[3].x + (i-3), current[3].y + (j-3)))
                                #ct.draw_indicator_dot(Position(current[3].x + (i-3), current[3].y + (j-3)), 255, 0, 0)
            elif conv:      # If conveyor, consider only straight surrounding tiles
                if avoid:
                    for i in range(3):
                        for j in range(3):
                            if (not (abs(i-1) == abs(j-1))) and current[3].x + (i-1) >= 0 and current[3].x + (i-1) < len(self.map[0]) and current[3].y + (j-1) >= 0 and current[3].y + (j-1) < len(self.map) and (current[3] not in self.unreachable_tiles) and ((self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] in [EntityType.MARKER, EntityType.ROAD, EntityType.CORE, EntityType.SPLITTER] and self.map[current[3].y + (j-1)][current[3].x + (i-1)][2] == self.team) or (self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] == None and self.map[current[3].y + (j-1)][current[3].x + (i-1)][0] in [Environment.EMPTY])) and not (self.map[current[3].y + (j-1)][current[3].x + (i-1)][4] is not None and current[3].distance_squared(self.pos) == 1):  # (not (self.map[current[3].y + (j-1)][current[3].x + (i-1)][4] in [EntityType.BUILDER_BOT] and self.pos.distance_squared(current[3]) <= 1) and
                                check_tiles.append((current[3].x + (i-1), current[3].y + (j-1)))
                                #ct.draw_indicator_dot(Position(current[3].x + (i-1), current[3].y + (j-1)), 0, 255, 0)
                else:
                    for i in range(3):
                        for j in range(3):
                            if (not (abs(i-1) == abs(j-1))) and current[3].x + (i-1) >= 0 and current[3].x + (i-1) < len(self.map[0]) and current[3].y + (j-1) >= 0 and current[3].y + (j-1) < len(self.map) and (current[3] not in self.unreachable_tiles) and ((self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.MARKER, EntityType.ROAD, EntityType.CORE, EntityType.SPLITTER] and self.map[current[3].y + (j-1)][current[3].x + (i-1)][2] == self.team) or (self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] == None and self.map[current[3].y + (j-1)][current[3].x + (i-1)][0] in [Environment.EMPTY])) and not (self.map[current[3].y + (j-1)][current[3].x + (i-1)][4] is not None and current[3].distance_squared(self.pos) == 1):  # (not (self.map[current[3].y + (j-1)][current[3].x + (i-1)][4] in [EntityType.BUILDER_BOT] and self.pos.distance_squared(current[3]) <= 1) and
                                check_tiles.append((current[3].x + (i-1), current[3].y + (j-1)))
                                #ct.draw_indicator_dot(Position(current[3].x + (i-1), current[3].y + (j-1)), 0, 255, 0)
            elif any:
                for i in range(3):
                    for j in range(3):
                        if (not (i == 1 and j == 1)) and current[3].x + (i-1) >= 0 and current[3].x + (i-1) < len(self.map[0]) and current[3].y + (j-1) >= 0 and current[3].y + (j-1) < len(self.map) and (current[3] not in self.unreachable_tiles) and (self.map[current[3].y + (j-1)][current[3].x + (i-1)][0] == 0 or (not (self.map[current[3].y + (j-1)][current[3].x + (i-1)][4] in [EntityType.BUILDER_BOT] and self.pos.distance_squared(current[3]) <= 2)) and (self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.MARKER, EntityType.ROAD, EntityType.SPLITTER] or (self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] == EntityType.CORE and self.map[current[3].y + (j-1)][current[3].x + (i-1)][2] == self.team) or (self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] == None and self.map[current[3].y + (j-1)][current[3].x + (i-1)][0] != Environment.WALL))):
                            check_tiles.append((current[3].x + (i-1), current[3].y + (j-1)))
            
            else:           # If normal one square movement, consider all surrounding tiles from current position
                for i in range(3):
                    for j in range(3):
                        if (not (i == 1 and j == 1)) and current[3].x + (i-1) >= 0 and current[3].x + (i-1) < len(self.map[0]) and current[3].y + (j-1) >= 0 and current[3].y + (j-1) < len(self.map) and (current[3] not in self.unreachable_tiles) and ((not (self.map[current[3].y + (j-1)][current[3].x + (i-1)][4] in [EntityType.BUILDER_BOT] and self.pos.distance_squared(current[3]) <= 2)) and (self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.MARKER, EntityType.ROAD, EntityType.SPLITTER] or (self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] == EntityType.CORE and self.map[current[3].y + (j-1)][current[3].x + (i-1)][2] == self.team) or (self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] == None and self.map[current[3].y + (j-1)][current[3].x + (i-1)][0] != Environment.WALL))):
                            check_tiles.append((current[3].x + (i-1), current[3].y + (j-1)))
                            #ct.draw_indicator_dot(Position(current[3].x + (i-1), current[3].y + (j-1)), 0, 0, 255)
            for tile in check_tiles:
                moveTile = 0
                dist = 11
                tile_pos = Position(tile[0], tile[1])
                #if current[3].distance_squared(tile_pos) > 1:   # Prefer to move in a straight line rather than diagonally
                    #counter += 1
                if self.map[tile[1]][tile[0]][1] == None:   # Prefer not to move over non-passable spaces (to save resources building extra paths)
                    moveTile += 1
                if bridge:
                    dist = dist - current[3].distance_squared(tile_pos) # Prefer to build longest bridge
                else:
                    dist = current[3].distance_squared(tile_pos)    # Prefer to move in straight lines (as I think is more valuable for information)
                #ct.draw_indicator_dot(tile, 0, 0, 255)
                if bridge:
                    new_cost = cost_so_far[current[3]] + (tile_pos.distance_squared(current[3]))**(1/2)
                    #new_cost = cost_so_far[current[3]] + tile_pos.distance_squared(current[3])  # For bridges, squared euclidean distance matters
                else:
                    new_cost = cost_so_far[current[3]] + 1     # Each move costs one move cooldown whether straight or diagonal for general movement
                if tile_pos not in cost_so_far or new_cost < cost_so_far[tile_pos]:     # Considers tile if not considered before or new path gets to it quicker
                    cost_so_far[tile_pos] = new_cost    # Updates smallest cost for location
                    if bridge:      # Calculates which tile to move to based off heuristic
                        priority = new_cost + self.heuristic_squaredEuclidean(tile_pos, target)
                    elif conv:
                        priority = new_cost + self.heuristic_Chebyshev(tile_pos, target)
                    else:   # General movement
                        priority = new_cost + abs(tile_pos.x - target.x) + abs(tile_pos.y - target.y)
                    q.put((priority, moveTile, dist, tile_pos))
                    came_from[tile_pos] = current[3]    # Updates check locations
            #break
        post_path_finder_time = ct.get_cpu_time_elapsed()
        dist = self.heuristic_Chebyshev(start, target)
        print(f"Path Finder Stats:")
        print(f" time | iter |  t/l  | t/dist")
        print(f" {post_path_finder_time - pre_path_finder_time:04} | {counter:04} | {(post_path_finder_time - pre_path_finder_time)/counter:.2f} | {(post_path_finder_time - pre_path_finder_time)/dist:.2f}")
        print("")
        return came_from, cost_so_far, best_tile
        '''

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
            if self.map[self.pos.add(d).y][self.pos.add(d).x][1] == EntityType.CORE:
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
                    elif marker_status == 2:
                        self.enemy_core_pos = Position(target_x, target_y)
                        print(marker_value, i)
                        print(marker_status, marker_value_id, target_x, target_y, self.id)
                        if marker_value_id == self.id:
                            self.target = self.enemy_core_pos
                            self.status = ATTACK_ENEMY_CORE
                            return
                    elif marker_status == 3:
                        self.status = 3
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
        if target == None:
            target = self.target
        came_from_explore, cost_explore, best_tile_explore = self.pathfinder(ct, target, any=True)
        if came_from_explore == None:
            return
        path_explore = self.reconstruct_path(came_from_explore, target)
        if len(path_explore) == 0:
            print("Invalid tile")
            self.find_invalid_tiles(ct, target)
            if self.built_harvester[1] != None:
                ct.draw_indicator_dot(self.built_harvester[1], 0, 0, 255)
                if len(self.map[self.built_harvester[1].y][self.built_harvester[1].x][3]) > 1:
                    self.built_harvester[1] = self.map[self.built_harvester[1].y][self.built_harvester[1].x][3][1]
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
                    ct.resign()
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
                ct.resign()     # PROBLEM
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
                        if self.map[path[0].add(d).y][path[0].add(d).x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR]:
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

            if grid[ny][nx][0] != Environment.WALL and grid[ny][nx][2] not in NON_PASSABLE:
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
                    
                    if grid[yy][xx][0] != Environment.WALL and grid[ny][nx][2] not in NON_PASSABLE:
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

    def attack_enemy_core(self, ct):
        pos = self.pos
        vision_tiles = ct.get_nearby_tiles()
        list_of_gunners = []
        self.target = self.enemy_core_pos
        if self.pos.distance_squared(self.enemy_core_pos) <= 25:
            for i in vision_tiles:
                if self.map[i.y][i.x][1] in [EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR]:
                    if self.map[i.y][i.x][1] == EntityType.BRIDGE:
                        building_target = ct.get_bridge_target(ct.get_tile_building_id(i))
                    else:
                        building_target = i.add(ct.get_direction(ct.get_tile_building_id(i)))

                    if ct.is_in_vision(building_target) and (ct.is_tile_passable(building_target) or building_target == pos or ct.get_tile_building_id(building_target) is None) and building_target.distance_squared(self.enemy_core_pos) <= 5:
                       if building_target.distance_squared(pos) < self.target.distance_squared(pos) or self.target == self.enemy_core_pos:
                            self.target = building_target
                            if ct.can_move(pos.direction_to(self.target)):
                                ct.move(pos.direction_to(self.target))
                                return

                elif self.map[i.y][i.x][1] in [EntityType.SPLITTER]:
                    splitter_outs = [i.add(ct.get_direction(ct.get_tile_building_id(i))), i.add(ct.get_direction(ct.get_tile_building_id(i)).rotate_left().rotate_left()), i.add(ct.get_direction(ct.get_tile_building_id(i)).rotate_right().rotate_right())]
                    for building_target in splitter_outs:
                        if ct.is_in_vision(building_target) and (ct.is_tile_passable(building_target) or building_target == pos or ct.get_tile_building_id(building_target) is None) and building_target.distance_squared(self.enemy_core_pos) <= 5:
                            if building_target.distance_squared(pos) < self.target.distance_squared(pos) or self.target == self.enemy_core_pos:
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
            if self.pos == self.target:
                if ct.can_destroy(self.target):
                    ct.destroy(self.target)
                elif ct.can_fire(self.target):
                    ct.fire(self.target)
                if ct.get_entity_type(ct.get_tile_building_id(self.pos)) not in [EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.ROAD, EntityType.SPLITTER]:
                    print("Moving away")
                    for i in DIRECTIONS:
                        if ct.can_move(i):
                            ct.move(i)
                            if self.target.distance_squared(self.enemy_core_pos) < 5 and ct.can_build_gunner(self.target, self.target.direction_to(self.enemy_core_pos)):
                                print("WOAH")
                                ct.build_gunner(self.target, self.target.direction_to(self.enemy_core_pos))
                            return
                else:
                    return

            elif ct.get_position().distance_squared(self.target) < 4 and ct.can_build_gunner(self.target, self.target.direction_to(self.enemy_core_pos)):
                ct.build_gunner(self.target, self.target.direction_to(self.enemy_core_pos))

            if self.target != self.enemy_core_pos:
                self.explore(ct)
                return

            vision_tiles = ct.get_nearby_tiles()
            random.shuffle(vision_tiles)
            for i in vision_tiles:
                if ct.is_tile_passable(i) and i.distance_squared(self.enemy_core_pos) < 9:
                    self.target = i
                    self.explore(ct)
                    self.target = self.enemy_core_pos
                    return
            else:
                print("CRY")

    def defence(self, ct):
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
                if ct.get_entity_type(ct.get_tile_building_id(i)) in [EntityType.SPLITTER]:
                    building_targets = [i.add(ct.get_direction(ct.get_tile_building_id(i))), i.add(ct.get_direction(ct.get_tile_building_id(i)).rotate_left().rotate_left()), i.add(ct.get_direction(ct.get_tile_building_id(i)).rotate_right().rotate_right())]
                    for building_target in building_targets:
                        if ct.is_in_vision(building_target) and ct.get_entity_type(ct.get_tile_building_id(building_target)) not in [EntityType.CORE, EntityType.SPLITTER, EntityType.GUNNER] and ct.get_tile_env(building_target) != Environment.WALL:
                            if building_target.distance_squared(pos) < self.target.distance_squared(pos) or self.target == self.core_pos:
                                self.target = building_target

            for i in ct.get_nearby_tiles():
                if ct.get_hp(ct.get_tile_building_id(i)) < ct.get_max_hp(ct.get_tile_building_id(i)) and ct.get_team() == self.team:
                    if i.distance_squared(pos) < self.target.distance_squared(pos) or self.target == self.core_pos:
                        print(f"Healing {i}")
                        self.target = i

        if self.target == self.core_pos and ct.get_entity_type(ct.get_tile_building_id(pos)) == EntityType.CORE:
            print("Cry")
            return

        if ct.can_heal(self.target):
            print("Healing")
            ct.heal(self.target)
            return
        elif ct.can_destroy(self.target) and ct.get_entity_type(ct.get_tile_building_id(self.target)) not in [EntityType.SPLITTER, EntityType.GUNNER]:
            ct.destroy(self.target)
            self.target = self.core_pos
        for d in STRAIGHTS:
            if ct.can_build_gunner(self.target, d.opposite()) and ct.get_tile_building_id(self.target.add(d)) is not None and ct.get_entity_type(ct.get_tile_building_id(self.target.add(d))) in [EntityType.SPLITTER] and ct.can_build_gunner(self.target, d.opposite()):
                ct.build_gunner(self.target, d.opposite())

        if pos == self.target:
            for d in DIRECTIONS:
                if ct.can_move(d):
                    ct.move(d)

        if not(ct.get_position().add(ct.get_position().direction_to(self.target)) == self.target):
            self.explore(ct)

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
            if (ct.get_entity_type(ct.get_tile_builder_bot_id(target)) == EntityType.BUILDER_BOT and ct.get_team() != ct.get_team(ct.get_tile_builder_bot_id(target))) or ct.get_team(ct.get_tile_building_id(target)) not in [None, ct.get_team()]:
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
            if (ct.get_entity_type(ct.get_tile_builder_bot_id(i)) == EntityType.BUILDER_BOT and ct.get_team() != ct.get_team(ct.get_tile_builder_bot_id(i))) or ct.get_team(ct.get_tile_building_id(i)) != ct.get_team():
                ct.draw_indicator_dot(i, 255, 0, 0)
                if ct.can_rotate(target.direction_to(i)):
                    ct.rotate(target.direction_to(i))
                    break

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

                '''for tile in ct.get_nearby_tiles():
                if ct.get_entity_type(ct.get_tile_building_id(tile)) in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and self.pos.distance_squared(tile) <= 5:
                    stored_res = ct.get_stored_resource(ct.get_tile_building_id(tile))
                    if stored_res != None and tile not in self.core_stored_resource:        # Adds new conveyors
                        self.core_stored_resource[tile] = stored_res
                    elif stored_res != None and self.core_stored_resource[tile] != stored_res and self.core_stored_resource[tile] != None:
                        self.core_stored_resource[tile] = None      # Indicates valid place for foundry
                        marker_status = 5   # Set up foundry
                        message = (
                                marker_status * (2**28)     # Assumes marker never destroyed
                                + ct.get_current_round() * (2**12)  # Uses this to decide whether it should just build a new bot
                                + tile.x * (2**6)
                                + tile.y)
                        for i in ct.get_nearby_tiles():
                            if ct.is_tile_empty(i) and ct.can_place_marker(i):
                                ct.place_marker(i, message)
                        break
                elif ct.get_entity_type(ct.get_tile_building_id(tile)) == EntityType.MARKER:
                    round = self.initialise_builder_bot(ct)
                    if self.status == 5:
                        if ct.get_entity_type(ct.get_tile_building_id(self.target)) not in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR]:
                            self.status = 0
                            self.target = Position(1000, 1000)
                        elif ct.get_current_round() >= 100 + round and ct.get_current_round() != 101 + round:  # Builds a new bot if founder not built in 100 rounds
                            if ct.can_spawn(self.pos.add(self.pos.direction_to(tile))):
                                ct.spawn_builder(self.pos.add(self.pos.direction_to(tile)))
                                self.num_spawned += 1
                else:
                    if tile in self.core_stored_resource:
                        del self.core_stored_resource[tile]     # Removes tiles that previously had conveyors but do not anymore'''

            # Bots to do healing
            elif ct.get_hp() < 500 or self.num_spawned < 6:
                print("Healing bots")
                core_tiles = ct.get_nearby_tiles(3)
                for i in core_tiles:
                    if ct.can_spawn(i):
                        ct.spawn_builder(i)
                        self.num_spawned += 1
                        break

            # Extra bots to attack enemy core
            elif self.enemy_core_pos != Position(1000, 1000) and self.num_spawned < 20: # need a better check
                if ct.get_global_resources()[0] < ct.get_builder_bot_cost()[0]:
                    print("Waiting for resources to spawn builder bot")
                    return
                for spawn_pos in ct.get_nearby_tiles(8):
                    if ct.can_spawn(spawn_pos):
                        ct.spawn_builder(spawn_pos)
                        # Place marker, so bot knows where to go
                        bot_id = ct.get_tile_builder_bot_id(spawn_pos)
                        marker_status = 2   # Defence bot
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

            elif self.enemy_core_pos == Position(1000, 1000):
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
                elif len(self.tit) != 0:
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
                else:
                    self.target = Position(1000, 1000)
                    self.status = EXPLORING

            elif self.status == DEFENCE:  # Defence algorithm
                self.defence(ct)

            elif self.status == ATTACK_ENEMY_CORE:
                print("Attacking Enemy Core")
                if self.enemy_core_pos.distance_squared(self.pos) > 25:
                    self.target = self.enemy_core_pos
                    self.explore(ct)
                    return
                self.attack_enemy_core(ct)

            # IDK about whats below here...
                '''
            elif self.status == 5:  # Build foundry
                if self.pos.distance_squared(self.target) > 2:
                    self.explore(ct)
                else:
                    if ct.can_destroy(self.target) and ct.get_entity_type(ct.get_tile_building_id(self.target)) in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR]:
                        ct.destroy(self.target)

                    dir = None

                    for tile in ct.get_nearby_tiles(5):
                        if self.target.distance_squared(tile) == 1 and ct.get_entity_type(ct.get_tile_building_id(tile)) in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR]:
                            if ct.get_direction(ct.get_tile_building_id(tile)) == tile.direction_to(self.target):
                                dir = tile.direction_to(self.target)
                                break

                    if dir == None:
                        if len(self.tit) > 0 or len(self.ax) > 0:
                            self.status = 2
                        else:
                            self.status = 1

                    else:

                        if ct.can_build_splitter(self.target, dir):
                            ct.build_splitter(self.target, dir)

                        elif ct.get_entity_type(ct.get_tile_building_id(self.target)) == EntityType.SPLITTER:
                            dir = ct.get_direction(ct.get_tile_building_id(self.target))

                            if self.map[self.target.add(dir).y][self.target.add(dir).x][1] != EntityType.CORE:
                                if self.map[self.target.add(dir).y][self.target.add(dir).x][1] != EntityType.FOUNDRY:

                                    if self.pos.distance_squared(self.target.add(dir)) > 2:
                                        temp = self.target
                                        self.target = self.target.add(dir)
                                        self.explore(ct)
                                        self.target = temp
                                    if ct.can_destroy(self.target.add(dir)):
                                        ct.destroy(self.target.add(dir))
                                    if ct.can_build_foundry(self.target.add(dir)):
                                        ct.build_foundry(self.target.add(dir))

                                elif self.map[self.target.add(dir).y][self.target.add(dir).x][1] == EntityType.FOUNDRY:
                                    pass    # build defences around harvester and splitter

                            elif self.map[self.target.add(dir.rotate_left().rotate_left()).y][self.target.add(dir.rotate_left().rotate_left()).x][1] != EntityType.CORE and self.map[self.target.add(dir.rotate_left().rotate_left()).add(dir).y][self.target.add(dir.rotate_left().rotate_left()).add(dir).x][1] == EntityType.CORE:
                                if self.map[self.target.add(dir.rotate_left().rotate_left()).y][self.target.add(dir.rotate_left().rotate_left()).x][1] != EntityType.FOUNDRY:

                                    if self.pos.distance_squared(self.target.add(dir.rotate_left().rotate_left())) > 2:
                                        temp = self.target
                                        self.target = self.target.add(dir.rotate_left().rotate_left())
                                        self.explore(ct)
                                        self.target = temp
                                    if ct.can_destroy(self.target.add(dir.rotate_left().rotate_left())):
                                        ct.destroy(self.target.add(dir.rotate_left().rotate_left()))
                                    if ct.can_build_foundry(self.target.add(dir.rotate_left().rotate_left())):
                                        ct.build_foundry(self.target.add(dir.rotate_left().rotate_left()))

                                elif self.map[self.target.add(dir.rotate_left()).y][self.target.add(dir.rotate_left()).x][1] == EntityType.FOUNDRY:
                                    pass    # build defences around harvester and splitter

                            elif self.map[self.target.add(dir.rotate_right().rotate_right()).y][self.target.add(dir.rotate_right().rotate_right()).x][1] != EntityType.CORE and self.map[self.target.add(dir.rotate_right().rotate_right()).add(dir).y][self.target.add(dir.rotate_right().rotate_right()).add(dir).x][1] == EntityType.CORE and self.map[self.target.add(dir.rotate_left().rotate_left()).y][self.target.add(dir.rotate_left().rotate_left()).x][1] != EntityType.FOUNDRY:
                                if self.map[self.target.add(dir.rotate_right().rotate_right()).y][self.target.add(dir.rotate_right().rotate_right()).x][1] != EntityType.FOUNDRY:

                                    if self.pos.distance_squared(self.target.add(dir.rotate_right().rotate_right())) > 2:
                                        temp = self.target
                                        self.target = self.target.add(dir.rotate_right().rotate_right())
                                        self.explore(ct)
                                        self.target = temp
                                    if ct.can_destroy(self.target.add(dir.rotate_right().rotate_right())):
                                        ct.destroy(self.target.add(dir.rotate_right().rotate_right()))
                                    if ct.can_build_foundry(self.target.add(dir.rotate_right().rotate_right())):
                                        ct.build_foundry(self.target.add(dir.rotate_right().rotate_right()))

                                elif self.map[self.target.add(dir.rotate_right()).y][self.target.add(dir.rotate_right()).x][1] == EntityType.FOUNDRY:
                                    pass    # build defences around harvester and splitter

                        if self.marker_location != Position(1000, 1000) and self.map[self.target.y][self.target.x][1] == EntityType.SPLITTER and (self.map[self.target.add(ct.get_direction(ct.get_tile_building_id(self.target))).y][self.target.add(ct.get_direction(ct.get_tile_building_id(self.target))).x][1] == EntityType.FOUNDRY or self.map[self.target.add(ct.get_direction(ct.get_tile_building_id(self.target)).rotate_left().rotate_left()).y][self.target.add(ct.get_direction(ct.get_tile_building_id(self.target)).rotate_left().rotate_left()).x][1] == EntityType.FOUNDRY or self.map[self.target.add(ct.get_direction(ct.get_tile_building_id(self.target)).rotate_right()).y][self.target.add(ct.get_direction(ct.get_tile_building_id(self.target)).rotate_right()).x][1] == EntityType.FOUNDRY):  # Ensures marker gets destroyed
                            if ct.can_destroy(self.marker_location):
                                ct.destroy(self.marker_location)
                                self.target = Position(1000, 1000)
                                self.marker_location = Position(1000, 1000)
                            else:
                                temp = self.target
                                self.target = self.marker_location
                                self.explore(ct, self.marker_location)
                                self.target = temp
                        elif self.marker_location == Position(1000, 1000) and self.map[self.target.y][self.target.x][1] == EntityType.SPLITTER and (self.map[self.target.add(ct.get_direction(ct.get_tile_building_id(self.target))).y][self.target.add(ct.get_direction(ct.get_tile_building_id(self.target))).x][1] == EntityType.FOUNDRY or self.map[self.target.add(ct.get_direction(ct.get_tile_building_id(self.target)).rotate_left().rotate_left()).y][self.target.add(ct.get_direction(ct.get_tile_building_id(self.target)).rotate_left().rotate_left()).x][1] == EntityType.FOUNDRY or self.map[self.target.add(ct.get_direction(ct.get_tile_building_id(self.target)).rotate_right()).y][self.target.add(ct.get_direction(ct.get_tile_building_id(self.target)).rotate_right()).x][1] == EntityType.FOUNDRY):
                            self.target = Position(1000, 1000)

                    #else not enough money so wait
                
                if self.target == Position(1000, 1000) and self.marker_location == Position(1000, 1000):
                    if len(self.tit) > 0 or len(self.ax) > 0:
                        self.status = 2
                    else:
                        self.status = 1
            
            '''

            elif self.enemy_core_pos != Position(1000, 1000):
                if self.pathfinder_start_pos == Position(1000, 1000):
                    self.pathfinder_start_pos = self.pos
                    ct.draw_indicator_dot(self.pathfinder_start_pos, 255, 255, 255)
                else:
                    ct.draw_indicator_dot(self.pathfinder_start_pos, 255, 255, 255)
                count = 0
                came_from, cost, best_tile_other = self.pathfinder(ct, self.core_pos, self.pathfinder_start_pos, True)
                if came_from == None:
                    return
                path = self.reconstruct_path(came_from, self.core_pos)
                if self.core_pos in path:
                    self.pathfinder_start_pos = Position(1000, 1000)
                    for tile in path:
                        if (count % 3) == 0:
                            ct.draw_indicator_dot(tile, 255, 0, 0)
                        elif (count % 3) ==1:
                            ct.draw_indicator_dot(tile, 0, 255, 0)
                        elif (count % 3) ==2:
                            ct.draw_indicator_dot(tile, 0, 0, 255)
                        count += 1
                    #ct.resign()
                else:
                    # move in a random direction
                    move_dir = random.choice(DIRECTIONS)
                    move_pos = self.pos.add(move_dir)
                    # we need to place a conveyor or road to stand on, before we can move onto a tile
                    if ct.can_build_road(move_pos):
                        ct.build_road(move_pos)
                    if ct.can_move(move_dir):
                        ct.move(move_dir)
                
                #else:
                    #ct.draw_indicator_dot(self.pos, 0, 0, 0)
                ct.draw_indicator_dot(self.enemy_core_pos, 255, 255, 0)
                ct.draw_indicator_dot(self.core_pos, 0, 255, 255)
                


            #for y in range(len(self.map)):
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

        elif etype == EntityType.GUNNER:
            if self.status == INIT:
                self.gn_init(ct)
            elif self.status == ATTACK_ENEMY_CORE:
                print("ATTACK")
                self.gn_attack_enemy_core(ct)
            elif self.status == DEFENCE:
                print("DEFENCE")
                self.gn_defend_core(ct)