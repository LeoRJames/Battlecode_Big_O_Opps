import random
from queue import PriorityQueue

from cambc import Controller, Direction, EntityType, Environment, Position

# non-centre directions
DIRECTIONS = [d for d in Direction if d != Direction.CENTRE]

class Player:
    def __init__(self):
        self.num_spawned = 0 # number of builder bots spawned so far (core)
        self.map = []
        self.core_pos = Position(1000, 1000)
        self.enemy_core_pos = Position(1000, 1000)  # Records a (central) core position
        self.pathfinder_start_pos = Position(1000, 1000)

    def initialise_map(self, ct):
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
            if ct.get_entity_type(ct.get_tile_building_id(tile)) == EntityType.CORE and ct.get_team(ct.get_tile_building_id(tile)) == ct.get_team(ct.get_id()):
                self.core_pos = tile
                #ct.draw_indicator_dot(tile, 0, 255, 0)
            elif ct.get_entity_type(ct.get_tile_building_id(tile)) == EntityType.CORE and ct.get_team(ct.get_tile_building_id(tile)) != ct.get_team(ct.get_id()):
                self.enemy_core_pos = tile     # Should be algorithm to get central position
                #ct.draw_indicator_dot(tile, 0, 0, 255)
    
    def heuristic_Chebyshev(self, next, target):     # Pass Positions
        return max(abs(next.x - target.x), abs(next.y - target.y))  # Chebyshev distance
    
    def heuristic_squaredEuclidean(self, next, target):
        return next.distance_squared(target)

    def pathfinder(self, ct, target, start = None, bridge=False):       # Pass Position
        if start == None:
            start = ct.get_position()
        q = PriorityQueue()
        moveTile = 0
        dist = 0
        q.put((0, moveTile, dist,  start))
        came_from = {}
        cost_so_far = {}
        came_from[start] = None
        cost_so_far[start] = 0

        while not q.empty():
            current = q.get()   # Returns highest priority item on queue
            
            if current[3] == target:
                break
            
            check_tiles = []
            
            # Adds all surrounding

            if bridge:
                for i in range(7):
                    for j in range(7):
                        if (not (i == 3 and j == 3)) and ((((i-3)**2)+((j-3)**2))**(1/2) <= 3) and current[3].x + (i-3) >= 0 and current[3].x + (i-3) < len(self.map[0]) and current[3].y + (j-3) >= 0 and current[3].y + (j-3) < len(self.map) and (self.map[current[3].y + (j-3)][current[3].x + (i-3)][1] in [EntityType.BUILDER_BOT] or (self.map[current[3].y + (j-3)][current[3].x + (i-3)][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.MARKER, EntityType.ROAD, EntityType.CORE] and self.map[current[3].y + (j-3)][current[3].x + (i-3)][2] == ct.get_team()) or (self.map[current[3].y + (j-3)][current[3].x + (i-3)][1] == None and self.map[current[3].y + (j-3)][current[3].x + (i-3)][0] != Environment.WALL)):
                            check_tiles.append((current[3].x + (i-3), current[3].y + (j-3)))
            else:
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
                dist = dist - current[3].distance_squared(tile_pos) # Prefer to build longest bridge
                #ct.draw_indicator_dot(tile, 0, 0, 255)
                if bridge:
                    new_cost = cost_so_far[current[3]] + tile_pos.distance_squared(current[3])
                else:
                    new_cost = cost_so_far[current[3]] + 1     # Each move costs one move cooldown whether straight or diagonal
                if tile_pos not in cost_so_far or new_cost < cost_so_far[tile_pos]:
                    cost_so_far[tile_pos] = new_cost
                    if bridge:
                        priority = new_cost + self.heuristic_squaredEuclidean(tile_pos, target)
                    else:
                        priority = new_cost + self.heuristic_Chebyshev(tile_pos, target)
                    q.put((priority, moveTile, dist, tile_pos))
                    came_from[tile_pos] = current[3]
            #break
        return came_from, cost_so_far
    
    def reconstruct_path(self, came_from, goal):
        if goal not in came_from:
            return []  # no path found
        path = []
        cur = goal
        while cur is not None:
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
            
            

            if self.enemy_core_pos != Position(1000, 1000):
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
