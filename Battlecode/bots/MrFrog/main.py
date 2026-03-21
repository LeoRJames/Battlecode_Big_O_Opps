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
                for j in range(ct.get_map_width()):
                    row = []
                    for i in range(ct.get_map_height()):
                        row.append([0, 0, 0])
                    self.map.append(row)

            for tile in ct.get_nearby_tiles():
                self.map[tile.y][tile.x][0] = ct.get_tile_env(tile)    # Sets environment type of tile (EMPTY, WALL, ORE_TITANIUM, ORE_AXIONITE)
                self.map[tile.y][tile.x][1] = ct.get_entity_type(ct.get_tile_building_id(tile))    # Sets Entity_Type on tile (BUILDER_BOT, CORE, GUNNER, SENTINEL, BREACH, LAUNCHER, CONVEYOR, SPLITTER, ARMOURED_CONVEYOR, BRIDGE, HARVESTER, FOUNDRY, ROAD, BARRIER, MARKER)
                self.map[tile.y][tile.x][2] = ct.get_team(ct.get_tile_building_id(tile))  # Sets the team of the building

        def find_ores(self, ct):        # COULD ACCOUNT FOR WALLS
            # List to store position of un-mined ores in vision
            tit = []
            ax = []
            # Get all tiles in vision radius
            vision_tiles = ct.get_nearby_tiles()
            # Loops through all tiles and checks if they are an ore
            for tile in vision_tiles:
                if ct.get_tile_env(tile) == Environment.ORE_TITANIUM and ct.is_tile_empty(tile):
                    tit.append(tile)
                elif ct.get_tile_env(tile) == Environment.ORE_AXIONITE and ct.is_tile_empty(tile):
                    ax.append(tile)
            return tit, ax

        def move_pos(self, ct, pos, conv=False):    # Return best tile to spawn/move to to get closer to passed pos DOES NOT PROPERLY ACCOUNT FOR WALLS YET

            vision_tiles = ct.get_nearby_tiles(2)   # Get position of tiles in action radius
            vision_tiles.remove(ct.get_position())  # Removes current position tile from list so will always move
            retpos = Position(1000,1000)    # Initialised far away so should not be returned

            for tile in vision_tiles:
                # Only consider tiles that are passable and empty environment type (does not move over ore) or tile does not contain building and if a conveyor must be built then do not consider diagonal tiles
                if (ct.is_tile_passable(tile) and ct.get_tile_env(tile) == Environment.EMPTY or ct.is_tile_empty(tile)) and (not (conv and (ct.get_position().direction_to(tile) == Direction.NORTHEAST or ct.get_position().direction_to(tile) == Direction.NORTHWEST or ct.get_position().direction_to(tile) == Direction.SOUTHEAST or ct.get_position().direction_to(tile) == Direction.SOUTHWEST))):
                    if pos.distance_squared(tile) < pos.distance_squared(retpos):   # If closer passable tile, set as tile to move to
                        retpos = tile
            return retpos
    
            #for d in Direction:
            check_pos = ct.get_position().add(d)
            if ct.can_build_harvester(check_pos):
                    check_dir = ct.get_position().direction_to(check_pos)   # If in position diagonal to harvester then first build conveyor until alongside
                    if check_dir == Direction.NORTHEAST or check_dir == Direction.NORTHWEST or check_dir == Direction.SOUTHEAST or check_dir == Direction.SOUTHWEST:
                        # Try to build conveyor 45 deg to left of direction to ore, otherwise try right (does not account for failing in both cases)
                        if ct.can_build_conveyor(ct.get_position().add(check_dir.rotate_left()), check_dir.rotate_left().opposite()) and ct.get_tile_env(ct.get_position().add(check_dir.rotate_left())) == Environment.EMPTY and (ct.get_entity_type(ct.get_tile_building_id(ct.get_position().add(check_dir.rotate_right()))) != EntityType.CONVEYOR or ct.get_entity_type(ct.get_tile_building_id(ct.get_position().add(check_dir.rotate_right()))) != EntityType.ARMOURED_CONVEYOR): # and check that tile to 45 deg right does not contain a conveyor
                            move_dir = check_dir.rotate_left()
                            ct.build_conveyor(ct.get_position().add(check_dir.rotate_left()), check_dir.rotate_left().opposite())                           
                            break
                        elif ct.can_build_conveyor(ct.get_position().add(check_dir.rotate_right()), check_dir.rotate_right().opposite()) and ct.get_tile_env(ct.get_position().add(check_dir.rotate_right())) == Environment.EMPTY and (ct.get_entity_type(ct.get_tile_building_id(ct.get_position().add(check_dir.rotate_left()))) != EntityType.CONVEYOR or ct.get_entity_type(ct.get_tile_building_id(ct.get_position().add(check_dir.rotate_left()))) != EntityType.ARMOURED_CONVEYOR):   # and check that tile to 45 deg left does not contain a conveyor
                            move_dir = check_dir.rotate_right()
                            ct.build_conveyor(ct.get_position().add(check_dir.rotate_right()), check_dir.rotate_right().opposite())
                            break
                    else:   # If alongside ore then build harvester     OTHERWISE WAIT FOR ENOUGH CASH (do not build over it)
                        ct.build_harvester(check_pos)
                        self.connect_harvester = True
                        break

            
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
           #        if self.map[y][x][1] == EntityType.CORE:
           #            ct.draw_indicator_dot(Position(x,y), 100, 100, 100)
           #        elif self.map[y][x][0] == Environment.EMPTY:
           #            ct.draw_indicator_dot(Position(x,y), 0, 255, 0)
           #        elif self.map[y][x][0] == Environment.WALL:
           #             ct.draw_indicator_dot(Position(x,y), 255, 0, 0)
           #         elif self.map[y][x][0] == Environment.ORE_TITANIUM:
           #             ct.draw_indicator_dot(Position(x,y), 0, 0, 255)
           #         elif self.map[y][x][0] == Environment.ORE_AXIONITE:
           #             ct.draw_indicator_dot(Position(x,y), 255, 255, 0)
