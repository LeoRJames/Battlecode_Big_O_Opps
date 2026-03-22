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

    def initialise_map(self, ct):
        for j in range(ct.get_map_width()):
            row = []
            for i in range(ct.get_map_height()):
                row.append([0, 0, 0])
            self.map.append(row)

    def update_map(self, ct):
        for tile in ct.get_nearby_tiles():
            self.map[tile.y][tile.x][0] = ct.get_tile_env(tile)    # Sets environment type of tile (EMPTY, WALL, ORE_TITANIUM, ORE_AXIONITE)
            self.map[tile.y][tile.x][1] = ct.get_entity_type(ct.get_tile_building_id(tile))    # Sets Entity_Type on tile (BUILDER_BOT, CORE, GUNNER, SENTINEL, BREACH, LAUNCHER, CONVEYOR, SPLITTER, ARMOURED_CONVEYOR, BRIDGE, HARVESTER, FOUNDRY, ROAD, BARRIER, MARKER, None)
            self.map[tile.y][tile.x][2] = ct.get_team(ct.get_tile_building_id(tile))  # Sets the team of the building
            if ct.get_entity_type(ct.get_tile_building_id(tile)) == EntityType.CORE and ct.get_team(ct.get_tile_building_id(tile)) == ct.get_team(ct.get_id()):
                self.core_pos == tile
                ct.draw_indicator_dot(tile, 0, 255, 0)
            elif ct.get_entity_type(ct.get_tile_building_id(tile)) == EntityType.CORE and ct.get_team(ct.get_tile_building_id(tile)) != ct.get_team(ct.get_id()):
                self.enemy_core_pos == tile     # Should be algorithm to get central position
                ct.draw_indicator_dot(tile, 0, 0, 255)

    def core_killer(self, ct):
        # Move to self.enemy_core_pos
        # Check vision radius for conveyors or bridges to their core
        # Destroy final conveyor/bridge to core
        # Build gunner in place

        # Move to self.enemy_core_pos
        pass

    def heuristic(self, ct, next, target):     # Passes Positions
        return next.distance_squared(target)

    def pathfinder(self, ct, target):       # Passes position
        q = PriorityQueue()
        q.put((ct.get_position(), 0))
        came_from = {}
        cost_so_far = {}
        came_from[ct.get_position()] = None
        cost_so_far[ct.get_position()] = 0

        while not q.empty():
            current = q.get()   # Returns highest priority item on queue
            
            if current == target:
                break
            
            check_tiles = []
            
            # Adds all surrounding 
            for i in range(3):
                for j in range(3):
                    if self.map[current.x + (i-1)][current.y + (j-1)][1] == (EntityType.BUILDER_BOT or EntityType.ARMOURED_CONVEYOR or EntityType.BRIDGE or EntityType.CONVEYOR or EntityType.MARKER or EntityType.ROAD) and current.x + (i-1) >= 0 and current.x + (i-1) < len(self.map[0]) and current.y + (j-1) >= 0 and current.y + (j-1) < len(self.map):
                        check_tiles.append((current.x + (i-1), current.y + (j-1)))
            for tile in check_tiles:
                tile_pos = Position(tile[0], tile[1])
                new_cost = cost_so_far[current] + 1     # Each move costs one move cooldown whether straight or diagonal
                if tile_pos not in cost_so_far or new_cost < cost_so_far[tile_pos]:
                    cost_so_far[tile_pos] = new_cost
                    priority = new_cost + self.heuristic(tile_pos, target)
                    q.put((tile_pos, priority))
                    came_from[tile_pos] = current
        return came_from, cost_so_far

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
            
            # move in a random direction
            move_dir = random.choice(DIRECTIONS)
            move_pos = ct.get_position().add(move_dir)
            # we need to place a conveyor or road to stand on, before we can move onto a tile
            if ct.can_build_road(move_pos):
                ct.build_road(move_pos)
            if ct.can_move(move_dir):
                ct.move(move_dir)

            if self.enemy_core_pos != Position(1000, 1000):
                ct.draw_indicator_dot(ct.get_position(), 255, 0, 0)
                path, cost = self.pathfinder(ct, self.core_pos)
                for tile in path:
                    ct.draw_indicator_dot(tile, 100, 100, 100)

            #for y in range(len(self.map)):
            #    for x in range(len(self.map[y])):
            #        if self.map[y][x][1] == EntityType.CORE:
            #            ct.draw_indicator_dot(Position(x,y), 100, 100, 100)
            #        elif self.map[y][x][0] == Environment.EMPTY:
            #            ct.draw_indicator_dot(Position(x,y), 0, 255, 0)
            #        elif self.map[y][x][0] == Environment.WALL:
            #            ct.draw_indicator_dot(Position(x,y), 255, 0, 0)
            #        elif self.map[y][x][0] == Environment.ORE_TITANIUM:
            #            ct.draw_indicator_dot(Position(x,y), 0, 0, 255)
            #        elif self.map[y][x][0] == Environment.ORE_AXIONITE:
            #            ct.draw_indicator_dot(Position(x,y), 255, 255, 0)
