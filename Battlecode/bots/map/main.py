import random

from cambc import Controller, Direction, EntityType, Environment, Position

# non-centre directions
DIRECTIONS = [d for d in Direction if d != Direction.CENTRE]

class Player:
    def __init__(self):
        self.num_spawned = 0 # number of builder bots spawned so far (core)
        self.map = []

    def run(self, ct: Controller) -> None:
        etype = ct.get_entity_type()
        if etype == EntityType.CORE:
            if self.num_spawned < 1:
                # if we haven't spawned 3 builder bots yet, try to spawn one on a random tile
                spawn_pos = ct.get_position().add(random.choice(DIRECTIONS))
                if ct.can_spawn(spawn_pos):
                    ct.spawn_builder(spawn_pos)
                    self.num_spawned += 1
        elif etype == EntityType.BUILDER_BOT:
            # if we are adjacent to an ore tile, build a harvester on it
            
            # Initialise map 2d array to map dimensions (ixj)
            if self.map == []:
                row = []
                for j in range(ct.get_map_width()):
                    row.append([0, 0, 0])
                for i in range(ct.get_map_height()):
                    self.map.append(row)

            for tile in ct.get_nearby_tiles():
                self.map[tile][0] = ct.get_tile_env(tile)    # Sets environment type of tile (EMPTY, WALL, ORE_TITANIUM, ORE_AXIONITE)
                self.map[tile][1] = ct.get_entity_type(ct.get_tile_building_id(tile))    # Sets Entity_Type on tile (BUILDER_BOT, CORE, GUNNER, SENTINEL, BREACH, LAUNCHER, CONVEYOR, SPLITTER, ARMOURED_CONVEYOR, BRIDGE, HARVESTER, FOUNDRY, ROAD, BARRIER, MARKER)
                self.map[tile][2] = ct.get_team(ct.get_tile_building_id(tile))  # Sets the team of the building

            for d in Direction:
                check_pos = ct.get_position().add(d)
                if ct.can_build_conveyor(check_pos, d):
                    ct.build_conveyor(check_pos, d)
                    break
            
            # move in a random direction
            move_dir = random.choice(DIRECTIONS)
            move_pos = ct.get_position().add(move_dir)
            # we need to place a conveyor or road to stand on, before we can move onto a tile
            if ct.can_build_road(move_pos):
                ct.build_road(move_pos)
            if ct.can_move(move_dir):
                ct.move(move_dir)

            for tile in self.map:
                if self.map[tile][0] == Environment.EMPTY:
                    ct.draw_indicator_dot(tile, 0, 255, 0)
                elif self.map[tile][0] == Environment.WALL:
                    ct.draw_indicator_dot(tile, 255, 0, 0)
                elif self.map[tile][0] == Environment.ORE_TITANIUM:
                    ct.draw_indicator_dot(tile, 0, 0, 255)
                elif self.map[tile][0] == Environment.ORE_AXIONITE:
                    ct.draw_indicator_dot(tile, 255, 255, 0)