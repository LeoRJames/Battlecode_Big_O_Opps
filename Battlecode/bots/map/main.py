import random
from queue import PriorityQueue

from cambc import Controller, Direction, EntityType, Environment, Position

# non-centre directions
DIRECTIONS = [d for d in Direction if d != Direction.CENTRE]
STRAIGHTS = [Direction.NORTH, Direction.SOUTH, Direction.WEST, Direction.EAST]
DIAGONALS = [Direction.NORTHWEST, Direction.NORTHEAST, Direction.SOUTHEAST, Direction.SOUTHWEST]

class Player:
    def __init__(self):
        self.num_spawned = 0 # number of builder bots spawned so far (core)
        self.map = []
        self.core_pos = Position(1000, 1000)
        self.enemy_core_pos = Position(1000, 1000)  # Records a (central) core position
        self.pathfinder_start_pos = Position(1000, 1000)
        self.tit = []   # List of Positions of unmined titanium
        self.ax = []    # List of Positions of unmined axionite
        self.built_harvester = [False, False]    # 0: True if built harvester and must connect; 1: Not False if built first conveyor and must move on to, otherwise stores position of that conveyor
        self.closest_conn_to_core = [Position(1000, 1000), False]   # True if do not adapt

    def initialise_map(self, ct):   # Set up 2d array for each tile on map each storing a list of three info pieces (tile type, building, team)
        for j in range(ct.get_map_width()):
            row = []
            for i in range(ct.get_map_height()):
                row.append([0, 0, 0])
            self.map.append(row)

    def update_map(self, ct):
        for tile in ct.get_nearby_tiles():
            self.map[tile.y][tile.x][0] = ct.get_tile_env(tile)    # Sets environment type of tile (EMPTY, WALL, ORE_TITANIUM, ORE_AXIONITE)
            if ct.get_tile_building_id(tile) != None:
                self.map[tile.y][tile.x][1] = ct.get_entity_type(ct.get_tile_building_id(tile))    # Sets Entity_Type on tile (CORE, GUNNER, SENTINEL, BREACH, LAUNCHER, CONVEYOR, SPLITTER, ARMOURED_CONVEYOR, BRIDGE, HARVESTER, FOUNDRY, ROAD, BARRIER, MARKER, None)
            else:
                self.map[tile.y][tile.x][1] = None
            self.map[tile.y][tile.x][2] = ct.get_team(ct.get_tile_building_id(tile))  # Sets the team of the building
            if ct.get_entity_type(ct.get_tile_building_id(tile)) == EntityType.CORE and ct.get_team(ct.get_tile_building_id(tile)) != ct.get_team():
                self.enemy_core_pos = tile     # Should be algorithm to get central position (use aarnavs search and symmetry stuff for this)
                #ct.draw_indicator_dot(tile, 0, 0, 255)
            elif not self.closest_conn_to_core[1] and ct.get_entity_type(ct.get_tile_building_id(tile)) in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.SPLITTER] and ct.get_team(ct.get_tile_building_id(tile)) == ct.get_team() and ct.get_position().distance_squared(tile) < ct.get_position().distance_squared(self.closest_conn_to_core[0]):
                self.closest_conn_to_core[0] = tile
            if ct.get_tile_env(tile) == Environment.ORE_TITANIUM and ct.get_entity_type(ct.get_tile_building_id(tile)) != EntityType.HARVESTER and tile not in self.tit:
                self.tit.append(tile)
            elif ct.get_tile_env(tile) == Environment.ORE_AXIONITE and ct.get_entity_type(ct.get_tile_building_id(tile)) != EntityType.HARVESTER and tile not in self.ax:
                self.ax.append(tile)
    
    def heuristic_Chebyshev(self, next, target):     # Pass Positions
        return max(abs(next.x - target.x), abs(next.y - target.y))  # Chebyshev distance
    
    def heuristic_squaredEuclidean(self, next, target):
        return next.distance_squared(target)

    def pathfinder(self, ct, target, start=None, bridge=False, conv=False):       # Pass Position
        if start == None:
            start = ct.get_position()
        q = PriorityQueue()
        moveTile = 0        # Tie breakers for equal path lengths
        dist = 0
        q.put((0, moveTile, dist,  start))  # Priority list to choose which tile to check next
        came_from = {}      # Dictionary of movement path
        cost_so_far = {}    # Dictionary of cost of movement
        came_from[start] = None
        cost_so_far[start] = 0

        while not q.empty():
            current = q.get()   # Returns highest priority item on queue
            
            if current[3] == target:
                break
            
            check_tiles = []
            
            # Adds all surrounding

            if bridge:      # If bridge consider all tiles a bridge can be built to
                for i in range(7):
                    for j in range(7):
                        if (not (i == 3 and j == 3)) and ((((i-3)**2)+((j-3)**2))**(1/2) <= 3) and current[3].x + (i-3) >= 0 and current[3].x + (i-3) < len(self.map[0]) and current[3].y + (j-3) >= 0 and current[3].y + (j-3) < len(self.map) and (self.map[current[3].y + (j-3)][current[3].x + (i-3)][1] in [EntityType.BUILDER_BOT] or (self.map[current[3].y + (j-3)][current[3].x + (i-3)][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.MARKER, EntityType.ROAD, EntityType.CORE] and self.map[current[3].y + (j-3)][current[3].x + (i-3)][2] == ct.get_team()) or (self.map[current[3].y + (j-3)][current[3].x + (i-3)][1] == None and self.map[current[3].y + (j-3)][current[3].x + (i-3)][0] != Environment.WALL)):
                            check_tiles.append((current[3].x + (i-3), current[3].y + (j-3)))
            elif conv:      # If conveyor, consider only straight surrounding tiles
                for i in range(3):
                    for j in range(3):
                        if (not (abs(i-1) == abs(j-1))) and current[3].x + (i-1) >= 0 and current[3].x + (i-1) < len(self.map[0]) and current[3].y + (j-1) >= 0 and current[3].y + (j-1) < len(self.map) and (self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] in [EntityType.BUILDER_BOT] or (self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.MARKER, EntityType.ROAD, EntityType.CORE] and self.map[current[3].y + (j-1)][current[3].x + (i-1)][2] == ct.get_team()) or (self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] == None and self.map[current[3].y + (j-1)][current[3].x + (i-1)][0] != Environment.WALL)):
                            check_tiles.append((current[3].x + (i-1), current[3].y + (j-1)))
            else:           # If normal one square movement, consider all surrounding tiles from current position
                for i in range(3):
                    for j in range(3):
                        if (not (i == 1 and j == 1)) and current[3].x + (i-1) >= 0 and current[3].x + (i-1) < len(self.map[0]) and current[3].y + (j-1) >= 0 and current[3].y + (j-1) < len(self.map) and (self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] in [EntityType.BUILDER_BOT, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.MARKER, EntityType.ROAD, EntityType.CORE] or (self.map[current[3].y + (j-1)][current[3].x + (i-1)][1] == None and self.map[current[3].y + (j-1)][current[3].x + (i-1)][0] != Environment.WALL)):
                            check_tiles.append((current[3].x + (i-1), current[3].y + (j-1)))
            for tile in check_tiles:
                moveTile = 0
                dist = 3
                tile_pos = Position(tile[0], tile[1])
                #if current[3].distance_squared(tile_pos) > 1:   # Prefer to move in a straight line rather than diagonally
                    #counter += 1
                if self.map[tile[1]][tile[0]][1] == None:   # Prefer not to move over non-passable spaces (to save resources building extra paths)
                    moveTile += 1
                if bridge:
                    dist = dist - current[3].distance_squared(tile_pos) # Prefer to build longest bridge
                #ct.draw_indicator_dot(tile, 0, 0, 255)
                if bridge:
                    new_cost = cost_so_far[current[3]] + tile_pos.distance_squared(current[3])  # For bridges, squared euclidean distance matters
                else:
                    new_cost = cost_so_far[current[3]] + 1     # Each move costs one move cooldown whether straight or diagonal for general movement
                if tile_pos not in cost_so_far or new_cost < cost_so_far[tile_pos]:     # Considers tile if not considered before or new path gets to it quicker
                    cost_so_far[tile_pos] = new_cost    # Updates smallest cost for location
                    if bridge:      # Calculates which tile to move to based off heuristic
                        priority = new_cost + self.heuristic_squaredEuclidean(tile_pos, target)
                    else:
                        priority = new_cost + self.heuristic_Chebyshev(tile_pos, target)
                    q.put((priority, moveTile, dist, tile_pos))
                    came_from[tile_pos] = current[3]    # Updates check locations
            #break
        return came_from, cost_so_far
    
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

    def core_killer(self, ct):
        # Move to self.enemy_core_pos
        # Check vision radius for conveyors or bridges to their core
        # Destroy final conveyor/bridge to core
        # Build gunner in place

        # Move to self.enemy_core_pos
        if self.enemy_core_pos not in ct.get_nearby_tiles():
            came_from, cost = self.pathfinder(ct, self.core_pos)
            path = self.reconstruct_path(came_from, self.core_pos)
            if len(path) == 0:
                # Must explore to find path to core
                pass
            else:
                move_pos = path[1] # path[0] is current position

    

    def run(self, ct: Controller) -> None:
        etype = ct.get_entity_type()
        if etype == EntityType.CORE:
            if self.num_spawned < 1:
                # if we haven't spawned 1 builder bot yet, try to spawn one on a random tile
                spawn_pos = ct.get_position().add(random.choice(DIRECTIONS))
                if ct.can_spawn(spawn_pos):
                    ct.spawn_builder(spawn_pos)
                    self.num_spawned += 1
                    
        elif etype == EntityType.BUILDER_BOT:
            
            # Initialise map 2d array to map dimensions (ixj)
            if self.map == []:
                self.initialise_map(ct)

            # Update map with each tile in vision radius each turn
            self.update_map(ct)

            if self.core_pos == Position(1000, 1000):
                for building in ct.get_nearby_buildings(2):
                    if ct.get_entity_type(building) == EntityType.CORE:
                        self.core_pos = ct.get_position(building)
                        self.closest_conn_to_core[0] = ct.get_position(building)   # Positions of map raise error so set to core position as will be same distance

            
            if len(self.tit) != 0:  # If there is a titanium ore to mine

                if not self.built_harvester[0]:        # If have not built harvester, must move towards it and build

                    came_from_move_harvester, cost_move_harvester = self.pathfinder(ct, self.tit[0])    # Movement path from current location to ore
                    path_move_harvester = self.reconstruct_path(came_from_move_harvester, self.tit[0])
                    if len(path_move_harvester) == 0:
                        ct.draw_indicator_line(ct.get_position(), self.tit[0], 255, 0, 0)
                        ct.resign()

                    came_from_first_conv, cost_first_conv = self.pathfinder(ct, ct.get_position(), self.tit[0], conv=True) # Conveyor build path from ore to current location
                    path_first_conv = self.reconstruct_path(came_from_first_conv, ct.get_position())
                    if len(path_first_conv) == 0:
                        ct.draw_indicator_line(ct.get_position(), self.tit[0], 0, 255, 0)
                        ct.resign()

                    if self.built_harvester[1] != False:    # Moves on to first conveyor built next to harvester
                        if ct.can_move(ct.get_position().direction_to(self.built_harvester[1])):
                            ct.move(ct.get_position().direction_to(self.built_harvester[1]))
                            self.built_harvester[1] = False # Flags process complete
                        else:
                            ct.draw_indicator_line(ct.get_position(), ct.get_position().add(ct.get_position().direction_to(self.built_harvester[1])), 0, 0, 255)
                            ct.resign()

                    elif ct.can_build_conveyor(path_first_conv[1], Direction.NORTH):     # Check if can build conveyor next to ore
                        came_from_harvester_core, cost_from_harvester_core = self.pathfinder(ct, self.core_pos, path_first_conv[1], conv=True)
                        came_from_harvester_conn, cost_from_harvester_conn = self.pathfinder(ct, self.closest_conn_to_core[0], path_first_conv[1], conv=True)
                        if cost_from_harvester_core[self.core_pos] <= cost_from_harvester_conn[self.closest_conn_to_core[0]]:   # Must choose to build conveyors back to core or closest conveyor as stored
                            came_from_harvester = came_from_harvester_core
                            cost_from_harvester = cost_from_harvester_core
                            path_from_harvester = self.reconstruct_path(came_from_harvester, self.core_pos)
                        else:
                            came_from_harvester = came_from_harvester_conn
                            cost_from_harvester = cost_from_harvester_conn
                            path_from_harvester = self.reconstruct_path(came_from_harvester, self.closest_conn_to_core[0])
                        if len(path_from_harvester) == 0:
                            ct.draw_indicator_line(self.core_pos, path_first_conv[1], 255, 255, 0)
                            ct.resign()
                        else:
                            if ct.can_build_conveyor(path_from_harvester[0], path_from_harvester[0].direction_to(path_from_harvester[1])):
                                self.built_harvester[1] = path_from_harvester[0]
                                self.closest_conn_to_core[1] = True
                                ct.build_conveyor(path_from_harvester[0], path_from_harvester[0].direction_to(path_from_harvester[1]))
                            elif self.map[path_from_harvester[0].y][path_from_harvester[0].x][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.SPLITTER] and self.map[path_from_harvester[0].y][path_from_harvester[0].x][2] == ct.get_team():       # If already a friendly transport mechanism in space then move on
                                self.built_harvester[1] = path_from_harvester[0]
                                self.closest_conn_to_core[1] = True
                            else:
                                ct.draw_indicator_dot(path_from_harvester[0], 0, 0, 0)
                                ct.draw_indicator_line(path_from_harvester[0], path_from_harvester[1], 255, 0, 255)
                                ct.resign()

                    elif ct.can_build_harvester(self.tit[0]):     # If can build harvester, build it
                        self.built_harvester[0] = True          # Flag harvester is built so must now build path back
                        self.closest_conn_to_core[1] = True     # Ensures this happens in case that does not need to build any conveyors tp connect harvester
                        ct.build_harvester(self.tit[0])

                    else:       # Move towards ore if not close enough to do anything else
                        came_from_to_ore, cost_to_ore = self.pathfinder(ct, self.tit[0])
                        path_to_ore = self.reconstruct_path(came_from_to_ore, self.tit[0])
                        if len(path_to_ore) == 0:
                            ct.draw_indicator_line(ct.get_position(), self.tit[0], 0, 255, 255)
                            ct.resign()
                        else:
                            if ct.can_build_road(path_to_ore[1]):
                                ct.build_road(path_to_ore[1])
                            if ct.can_move(ct.get_position().direction_to(path_to_ore[1])):
                                ct.move(ct.get_position().direction_to(path_to_ore[1]))
                            else:
                                ct.draw_indicator_line(ct.get_position(), path_to_ore[1], 0, 0, 0)
                else:
                    came_from_built_harvester_core, cost_from_built_harvester_core = self.pathfinder(ct, self.core_pos, conv=True)
                    came_from_built_harvester_conn, cost_from_built_harvester_conn = self.pathfinder(ct, self.closest_conn_to_core[0], conv=True)
                    if cost_from_built_harvester_core[self.core_pos] <= cost_from_built_harvester_conn[self.closest_conn_to_core[0]]:   # Choose closest between core and stored closest cnveyor
                        came_from_built_harvester = came_from_built_harvester_core
                        cost_from_built_harvester = cost_from_built_harvester_core
                        path_from_built_harvester = self.reconstruct_path(came_from_built_harvester, self.core_pos)
                    else:
                        came_from_built_harvester = came_from_built_harvester_conn
                        cost_from_built_harvester = cost_from_built_harvester_conn
                        path_from_built_harvester = self.reconstruct_path(came_from_built_harvester, self.closest_conn_to_core[0])
                    if len(path_from_built_harvester) == 0:
                        ct.draw_indicator_line(ct.get_position(), self.core_pos, 255, 255, 255)
                        ct.resign()
                    elif len(path_from_built_harvester) == 1 or self.map[path_from_built_harvester[1].y][path_from_built_harvester[1].x][1] in [EntityType.CORE, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.SPLITTER] and self.map[path_from_built_harvester[1].y][path_from_built_harvester[1].x][2] == ct.get_team():  # Check for being at end of path
                        self.built_harvester[0] = False
                        self.closest_conn_to_core[1] = False
                        del self.tit[0]                         # Remove ore from build queue
                    else:
                        if self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).x][1] == EntityType.ROAD and self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).x][2] == ct.get_team() and ct.can_destroy(ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1]))):     # If a friendly road is on path, destroy it
                            ct.destroy(ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])))
                        if ct.can_build_conveyor(path_from_built_harvester[1], path_from_built_harvester[1].direction_to(path_from_built_harvester[2])):    # Build conveyor and move on to it
                            ct.build_conveyor(path_from_built_harvester[1], path_from_built_harvester[1].direction_to(path_from_built_harvester[2]))
                            if ct.can_move(ct.get_position().direction_to(path_from_built_harvester[1])):
                                ct.move(ct.get_position().direction_to(path_from_built_harvester[1]))
                            else:
                                ct.draw_indicator_line(ct.get_position(), path_from_built_harvester[1], 0, 255, 255)
                        else:
                            ct.draw_indicator_dot(path_from_built_harvester[1], 255, 0, 255)
                            ct.draw_indicator_line(path_from_built_harvester[1], path_from_built_harvester[1].add(path_from_built_harvester[1].direction_to(path_from_built_harvester[2])), 255, 255, 255)
                            ct.resign()


                '''
                if self.built_harvester[1] != False:    # Moves on to first conveyor built next to harvester
                    if ct.can_move(ct.get_position().direction_to(self.built_harvester[1])):
                        ct.move(ct.get_position().direction_to(self.built_harvester[1]))
                        self.built_harvester[1] = False
                    else:
                        ct.draw_indicator_line(ct.get_position(), ct.get_position().add(ct.get_position().direction_to(self.built_harvester[1])), 255, 0, 0)
                        ct.resign()
                elif ct.get_position().distance_squared(self.tit[0]) < 8 and ct.get_position().distance_squared(self.tit[0]) >= 2 and not self.built_harvester[0]:     # If a space straight (not diag) next to harvester is in action radius, build conveyor
                    came_from_first_conv, cost_first_conv = self.pathfinder(ct, ct.get_position(), self.tit[0], conv=True)
                    path_first_conv = self.reconstruct_path(came_from_first_conv, ct.get_position())
                    if len(path_first_conv) == 0:
                        ct.draw_indicator_dot(ct.get_position(), 0, 255, 0)
                        ct.resign()
                    else:
                        came_from_harvester_core, cost_from_harvester_core = self.pathfinder(ct, self.core_pos, path_first_conv[1], conv=True)
                        came_from_harvester_conn, cost_from_harvester_conn = self.pathfinder(ct, self.closest_conn_to_core[0], path_first_conv[1], conv=True)
                        if cost_from_harvester_core[self.core_pos] <= cost_from_harvester_conn[self.closest_conn_to_core[0]]:
                            came_from_harvester = came_from_harvester_core
                            cost_from_harvester = cost_from_harvester_core
                            path_from_harvester = self.reconstruct_path(came_from_harvester, self.core_pos)
                        else:
                            came_from_harvester = came_from_harvester_conn
                            cost_from_harvester = cost_from_harvester_conn
                            path_from_harvester = self.reconstruct_path(came_from_harvester, self.closest_conn_to_core[0])
                        if len(path_from_harvester) == 0:
                            ct.draw_indicator_line(self.core_pos, path_first_conv[1], 0, 255, 0)
                            ct.resign()
                        else:
                            if ct.can_build_conveyor(path_from_harvester[0], path_from_harvester[0].direction_to(path_from_harvester[1])):
                                self.built_harvester[1] = path_from_harvester[0]
                                self.closest_conn_to_core[1] = True
                                ct.build_conveyor(path_from_harvester[0], path_from_harvester[0].direction_to(path_from_harvester[1]))
                            elif self.map[path_from_harvester[0].y][path_from_harvester[0].x][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.SPLITTER] and self.map[path_from_harvester[0].y][path_from_harvester[0].x][2] == ct.get_team():
                                self.built_harvester[1] = path_from_harvester[0]
                                self.closest_conn_to_core[1] = True
                            else:
                                ct.draw_indicator_dot(path_from_harvester[0], 0, 0, 255)
                                ct.draw_indicator_line(path_from_harvester[0], path_from_harvester[1], 0, 0, 0)
                                ct.resign()
                elif not self.built_harvester[0] and ct.can_build_harvester(self.tit[0]):   # If can build a harvester, build it
                    self.built_harvester[0] = True
                    ct.build_harvester(self.tit[0])
                    del self.tit[0]
                elif self.built_harvester[0]:   # If built a harvester, connect it back to core
                    came_from_built_harvester_core, cost_from_built_harvester_core = self.pathfinder(ct, self.core_pos, conv=True)
                    came_from_built_harvester_conn, cost_from_built_harvester_conn = self.pathfinder(ct, self.closest_conn_to_core[0], conv=True)
                    if cost_from_built_harvester_core[self.core_pos] <= cost_from_built_harvester_conn[self.closest_conn_to_core[0]]:
                        came_from_built_harvester = came_from_built_harvester_core
                        cost_from_built_harvester = cost_from_built_harvester_core
                        path_from_built_harvester = self.reconstruct_path(came_from_built_harvester, self.core_pos)
                    else:
                        came_from_built_harvester = came_from_built_harvester_conn
                        cost_from_built_harvester = cost_from_built_harvester_conn
                        path_from_built_harvester = self.reconstruct_path(came_from_built_harvester, self.closest_conn_to_core[0])
                    if len(path_from_built_harvester) == 0:
                        ct.draw_indicator_line(ct.get_position(), self.core_pos, 255, 255, 0)
                        ct.resign()
                    elif self.map[path_from_built_harvester[1].y][path_from_built_harvester[1].x][1] in [EntityType.CORE, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.SPLITTER] and self.map[path_from_built_harvester[1].y][path_from_built_harvester[1].x][2] == ct.get_team():
                        self.built_harvester[0] = False
                        self.closest_conn_to_core[1] = False
                    else:
                        if self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).x][1] == EntityType.ROAD and self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).x][2] == ct.get_team() and ct.can_destroy(ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1]))):
                            ct.destroy(ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])))
                        if ct.can_build_conveyor(path_from_built_harvester[1], path_from_built_harvester[1].direction_to(path_from_built_harvester[2])):
                            ct.build_conveyor(path_from_built_harvester[1], path_from_built_harvester[1].direction_to(path_from_built_harvester[2]))
                            if ct.can_move(ct.get_position().direction_to(path_from_built_harvester[1])):
                                ct.move(ct.get_position().direction_to(path_from_built_harvester[1]))
                            else:
                                ct.draw_indicator_line(ct.get_position(), path_from_built_harvester[1], 0, 255, 255)
                        else:
                            ct.draw_indicator_dot(path_from_built_harvester[1], 255, 0, 255)
                            ct.draw_indicator_line(path_from_built_harvester[1], path_from_built_harvester[1].add(path_from_built_harvester[1].direction_to(path_from_built_harvester[2])), 255, 255, 255)
                            ct.resign()
                else:   # Move towards ore
                    came_from_to_ore, cost_to_ore = self.pathfinder(ct, self.tit[0])
                    path_to_ore = self.reconstruct_path(came_from_to_ore, self.tit[0])
                    if len(path_to_ore) == 0:
                        ct.draw_indicator_line(ct.get_position(), self.tit[0], 0, 255, 255)
                        ct.resign()
                    else:
                        if ct.can_build_road(path_to_ore[1]):
                            ct.build_road(path_to_ore[1])
                        if ct.can_move(ct.get_position().direction_to(path_to_ore[1])):
                            ct.move(ct.get_position().direction_to(path_to_ore[1]))
                        else:
                            ct.draw_indicator_line(ct.get_position(), path_to_ore[1], 0, 0, 255)
                '''
                #if ct.can_build_harvester(self.tit[0]):
                #    if ct.get_position().direction_to(self.tit[0]) in DIAGONALS:    # If diagonally next to a conveyor, must decide 45 deg left or right to start building a conveyor from
                #        if self.map[ct.get_position().add(self.tit[0].rotate_left()).y][ct.get_position().add(self.tit[0].rotate_left()).x][0] == Environment.EMPTY and (self.map[ct.get_position().add(self.tit[0].rotate_left()).y][ct.get_position().add(self.tit[0].rotate_left()).x][1] in [None, EntityType.MARKER, EntityType.ROAD] and self.map[ct.get_position().add(self.tit[0].rotate_left()).y][ct.get_position().add(self.tit[0].rotate_left()).x][2] == ct.get_team()) and not (self.map[ct.get_position().add(self.tit[0].rotate_right()).y][ct.get_position().add(self.tit[0].rotate_right()).x][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.SPLITTER] and self.map[ct.get_position().add(self.tit[0].rotate_right()).y][ct.get_position().add(self.tit[0].rotate_right()).x][2] == ct.get_team()):
                #            came_from, cost = self.pathfinder(ct, self.core_pos, ct.get_position().add(self.tit[0].rotate_left()),conv=True)
                #            if ct.can_build_conveyor(ct.get_position().add(self.tit[0].rotate_left()), came_from[0].direction_to(came_from[1])):
                #                ct.build_conveyor(ct.get_position().add(self.tit[0].rotate_left()), came_from[0].direction_to(came_from[1]))
                #            else:
                #                ct.draw_indicator_dot(ct.get_position().add(self.tit[0].rotate_left()), 255, 0, 0)
                #                ct.resign()
                #        elif self.map[ct.get_position().add(self.tit[0].rotate_right()).y][ct.get_position().add(self.tit[0].rotate_right()).x][0] == Environment.EMPTY and (self.map[ct.get_position().add(self.tit[0].rotate_right()).y][ct.get_position().add(self.tit[0].rotate_right()).x][1] in [None, EntityType.MARKER, EntityType.ROAD] and self.map[ct.get_position().add(self.tit[0].rotate_right()).y][ct.get_position().add(self.tit[0].rotate_right()).x][2] == ct.get_team()) and not (self.map[ct.get_position().add(self.tit[0].rotate_left()).y][ct.get_position().add(self.tit[0].rotate_left()).x][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.SPLITTER] and self.map[ct.get_position().add(self.tit[0].rotate_left()).y][ct.get_position().add(self.tit[0].rotate_left()).x][2] == ct.get_team()):
                #            came_from, cost = self.pathfinder(ct, self.core_pos, ct.get_position().add(self.tit[0].rotate_left()),conv=True)
                #            if ct.can_build_conveyor(ct.get_position().add(self.tit[0].rotate_right()), came_from[0].direction_to(came_from[1])):
                #                ct.build_conveyor(ct.get_position().add(self.tit[0].rotate_right()), came_from[0].direction_to(came_from[1]))
                #            else:
                #                ct.draw_indicator_dot(ct.get_position().add(self.tit[0].rotate_right()), 255, 0, 0)
                #                ct.resign()
                #    else:
                #        ct.build_harvester(self.tit[0])
                #        self.built_harvester = True
                #elif self.built_harvester:  # If have built harvester
                #    pass
                #else:   # Move to titanium ore
                #    came_from, cost = self.pathfinder(ct, self.tit[0])  # Find movement path to titanium ore


            elif self.enemy_core_pos != Position(1000, 1000):
                if self.pathfinder_start_pos == Position(1000, 1000):
                    self.pathfinder_start_pos = ct.get_position()
                    ct.draw_indicator_dot(self.pathfinder_start_pos, 255, 255, 255)
                else:
                    ct.draw_indicator_dot(self.pathfinder_start_pos, 255, 255, 255)
                count = 0
                came_from, cost = self.pathfinder(ct, self.core_pos, self.pathfinder_start_pos, True)
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
                    ct.resign()
                else:
                    # move in a random direction
                    move_dir = random.choice(DIRECTIONS)
                    move_pos = ct.get_position().add(move_dir)
                    # we need to place a conveyor or road to stand on, before we can move onto a tile
                    if ct.can_build_road(move_pos):
                        ct.build_road(move_pos)
                    if ct.can_move(move_dir):
                        ct.move(move_dir)
                
                #else:
                    #ct.draw_indicator_dot(ct.get_position(), 0, 0, 0)
                ct.draw_indicator_dot(self.enemy_core_pos, 255, 255, 0)
                ct.draw_indicator_dot(self.core_pos, 0, 255, 255)
                
            else:
                # move in a random direction
                move_dir = random.choice(DIRECTIONS)
                move_pos = ct.get_position().add(move_dir)
                # we need to place a conveyor or road to stand on, before we can move onto a tile
                if ct.can_build_road(move_pos):
                    ct.build_road(move_pos)
                if ct.can_move(move_dir):
                    ct.move(move_dir)

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
                    #if self.map[y][x][1] in [EntityType.BUILDER_BOT, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.MARKER, EntityType.ROAD]:
                    #    ct.draw_indicator_dot(Position(x,y), 0, 0, 0)
            #        elif self.map[y][x][0] == Environment.EMPTY:
            #            ct.draw_indicator_dot(Position(x,y), 0, 255, 0)
            #        elif self.map[y][x][0] == Environment.WALL:
            #            ct.draw_indicator_dot(Position(x,y), 255, 0, 0)
            #        elif self.map[y][x][0] == Environment.ORE_TITANIUM:
            #            ct.draw_indicator_dot(Position(x,y), 0, 0, 255)
            #        elif self.map[y][x][0] == Environment.ORE_AXIONITE:
            #            ct.draw_indicator_dot(Position(x,y), 255, 255, 0)
