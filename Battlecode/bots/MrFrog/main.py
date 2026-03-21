import random

from cambc import *

DIRECTIONS = [d for d in Direction if d != Direction.CENTRE]

class Player:
    def __init__(self):
        self.num_spawned = 0 # number of builder bots spawned so far (core)
        self.dir = Direction.CENTRE  #Arbitrary
        self.core_pos = Position(1000,1000) #Arbitrary farr outside map range
        self.closest_conveyor = Position(1000,1000)
        self.connect_harvester = False
    
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


    def run(self, ct: Controller) -> None:

        etype = ct.get_entity_type()

        if etype == EntityType.CORE:        # ADD MARKER STUFF

            # Returns positions of titanium and axionite in vision of core
            tit, ax = self.find_ores(ct)
            # Should change such that one bot spawned in each direction and ensure only one bot moves towards taking ores in a particular direction
            # Spawn a builder for every titatium ore in closest position to ore or three minimum baseline (TO ADD)

            if self.num_spawned < len(tit):
                spawn_dir = ct.get_position().direction_to(self.move_pos(ct, tit[self.num_spawned]))    # Spawns in unnoccupied tile closest to titanium ore in index
                spawn_pos = ct.get_position().add(spawn_dir)
            elif self.num_spawned < 3:
                spawn_dir = random.choice(DIRECTIONS)   # Randomly chooses position to spawn
                spawn_pos = ct.get_position().add(spawn_dir)
            if (self.num_spawned < len(tit) or self.num_spawned < 3) and ct.can_spawn(spawn_pos):
                ct.spawn_builder(spawn_pos)
                self.num_spawned += 1
                if ct.can_place_marker(spawn_pos.add(spawn_dir)):  # Marker to tell bot that it has just spawned
                    ct.place_marker(spawn_pos.add(spawn_dir), 0)

        elif etype == EntityType.BUILDER_BOT:

            # Check vision radius
            vision_tiles = ct.get_nearby_tiles()
            marker_id_check = 99999999999999    # Arbitrarily large
            marker_tile = Position(1000,1000)
            for tile in vision_tiles:
                # Read Marker (marker_id can be adapted to reading of other building types in vision radius)
                building_id = ct.get_tile_building_id(tile)

                if ct.get_entity_type(building_id) == EntityType.MARKER:
                    marker_value = ct.get_marker_value(building_id)
                    if marker_value == 0 and self.core_pos == Position(1000, 1000) and building_id < marker_id_check:   # Bot has just spwaned
                        marker_id_check = building_id
                        marker_tile = tile
                # CHECK IF CONVEYOR FRIENDLY OR ENEMY
                
                # Searches for closest conveyor in vision to itself every turn (NEED to ensure only friendly conveyors)
                building_team_for_conveyor = ct.get_team(building_id)

                elif (ct.get_entity_type(building_id) == EntityType.CONVEYOR or ct.get_entity_type(building_id) == EntityType.ARMOURED_CONVEYOR) and tile != ct.get_position() and not self.connect_harvester and building_team == Team.A:
                    if ct.get_position().distance_squared(tile) <= ct.get_position().distance_squared(self.closest_conveyor):
                        self.closest_conveyor = tile
                            
            if marker_id_check != 99999999999999:   # Ensures bot destroys its own 0 marker and not that of another bot (core spawns two bots before any bot takes a turn)
                self.core_pos = ct.get_position()
                if ct.can_destroy(marker_tile):   # Destroy marker so other bots do not read it incorrectly at later date
                    ct.destroy(marker_tile)

            # Check action radius
            for d in Direction:
                check_pos = ct.get_position().add(d)    #MUST ACCOUNT FOR RUNNING OUT OF TITANIUM

                # Attempt to build harvester
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

            tit, ax = self.find_ores(ct)    # OREINTATION OF CONVEYORS DO NOT WORK GOING BACK
            if self.connect_harvester:  # MAY try to go diagonal which is not closer as cannot move diagonally.
                if ct.get_position().distance_squared(self.closest_conveyor) < ct.get_position().distance_squared(self.core_pos):
                    move_dir = ct.get_position().direction_to(self.move_pos(ct, self.closest_conveyor, True))
                    new_pos = ct.get_position().add(move_dir)
                else:
                    move_dir = ct.get_position().direction_to(self.move_pos(ct, self.core_pos, True))
                    new_pos = ct.get_position().add(move_dir)
                if ct.get_entity_type(ct.get_tile_building_id(new_pos)) == EntityType.ROAD:
                    if ct.can_destroy(new_pos):
                        ct.destroy(new_pos)
                if ct.can_build_conveyor(new_pos, move_dir): # Build conveyor back in direction it has come from (does not orientate correctly)
                    ct.build_conveyor(new_pos, move_dir)
                elif ct.get_action_cooldown() == 0:
                    self.connect_harvester = False
            elif len(tit) != 0 and ct.get_action_cooldown() == 0:   # If there is a titanium ore in range, move towards it
                move_dir = ct.get_position().direction_to(self.move_pos(ct, tit[0], True))    # Direction to move to new position determined by function
                new_pos = ct.get_position().add(move_dir)   # New position that will be moved to
                if (ct.get_position().distance_squared(self.closest_conveyor) <= 1 or ct.get_position().distance_squared(self.core_pos) <= 1 or ct.get_position().distance_squared(tit[0]) <= 4) and ct.can_build_conveyor(new_pos, move_dir.opposite()): # Build conveyor back in direction it has come from
                    ct.build_conveyor(new_pos, move_dir.opposite())
                elif ct.can_build_road(new_pos):  #CHange both back to road
                    move_dir = ct.get_position().direction_to(self.move_pos(ct, tit[0]))
                    new_pos = ct.get_position().add(move_dir)
                    if ct.can_build_road(new_pos):
                        ct.build_road(new_pos)
            elif ct.get_action_cooldown() == 0:   # Move in same direction as currently facing
                mov_pos = ct.get_position().add(self.dir)
                move_dir = ct.get_position().direction_to(self.move_pos(ct, mov_pos)) #REMOVE TRUE   # Direction to move to new position determined by function
                new_pos = ct.get_position().add(move_dir)   # New position that will be moved to
                if ct.can_build_road(new_pos):  #CHange both back to road
                    ct.build_road(new_pos)
            #else:      #Fail safe
                #move_dir = self.dir
            self.dir = move_dir # Stores direction currently facing every turn

            # New version of above should build conveyor if it is connected to core
            # Otherwise build road up to harvester and then retrace steps to nearest conveyor or core (whichever closer)
            
            if ct.can_move(move_dir):   # Move to intended position if it can
                ct.move(move_dir)

            

            # place a marker on an adjacent tile with the current round number
            #marker_pos = ct.get_position().add(random.choice(DIRECTIONS))
            #if ct.can_place_marker(marker_pos):
                #ct.place_marker(marker_pos, ct.get_current_round())