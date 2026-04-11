harvest_ore

came_from_first_conv, cost_first_conv, best_tile_first_conv = self.pathfinder(ct, ore, conv=True) # Conveyor build path from current location to ore
            path_first_conv = self.reconstruct_path(came_from_first_conv, best_tile_first_conv)
            if len(path_first_conv) == 0:
                ct.draw_indicator_line(ct.get_position(), ore, 0, 255, 0)
                ct.resign()
            elif len(path_first_conv) == 1 and ct.get_position().distance_squared(ore) > 2:
                came_from_first_conv, cost_first_conv, best_tile_first_conv = self.pathfinder(ct, ore, bridge=True) # Bridge build path from current location to ore    I THINK WILL CAUSE SOME ERRORS
                path_first_conv = self.reconstruct_path(came_from_first_conv, best_tile_first_conv)
            if len(path_first_conv) < 2 and ct.get_position().distance_squared(ore) > 2:
                if ore in self.tit:
                    self.tit.remove(ore)    # Strange case so just give up to orevent error
                elif ore in self.ax:
                    self.ax.remove(ore)
                else:
                    ct.draw_indicator_line(ct.get_position(), self.core_pos, 0, 0, 0)
                return
            if len(path_first_conv) > 1 and self.map[path_first_conv[-2].y][path_first_conv[-2].x][1] == EntityType.ROAD and self.map[path_first_conv[-2].y][path_first_conv[-2].x][2] == ct.get_team() and ct.can_destroy(path_first_conv[-2]) and ct.get_position().distance_squared(ore) <= 5:
                ct.destroy(path_first_conv[-2])
            elif ore not in path_first_conv and self.map[path_first_conv[-1].y][path_first_conv[-1].x][1] == EntityType.ROAD and self.map[path_first_conv[-1].y][path_first_conv[-1].x][2] == ct.get_team() and ct.can_destroy(path_first_conv[-1]) and ct.get_position().distance_squared(ore) <= 5:
                ct.destroy(path_first_conv[-1])
            elif len(path_first_conv) > 1 and self.map[path_first_conv[-2].y][path_first_conv[-2].x][2] != ct.get_team() and ct.get_position().distance_squared(ore) <= 5:
                if ore in self.tit:
                    self.tit.remove(ore)    # If other team have built a building where you want to build conveyor just forget about it
                elif ore in self.ax:
                    self.ax.remove(ore)
                else:
                    ct.draw_indicator_line(ct.get_position(), self.core_pos, 255, 0, 0)
            elif len(path_first_conv) > 1 and ct.get_position() != path_first_conv[-2] and self.map[path_first_conv[-2].y][path_first_conv[-2].x][1] in [EntityType.CONVEYOR] and self.map[path_first_conv[-2].y][path_first_conv[-2].x][2] == ct.get_team() and ct.get_position().distance_squared(ore) <= 5:    # May be other builder bot sitting and waiting for money to build harvester    ct.get_entity_type(ct.get_tile_builder_bot_id(path_first_conv[-2])) == EntityType.BUILDER_BOT
                if ore in self.tit:
                    self.tit.remove(ore)
                elif ore in self.ax:
                    self.ax.remove(ore)
                else:
                    ct.draw_indicator_line(ct.get_position(), self.core_pos, 0, 255, 0)
            elif self.map[ore.y][ore.x][2] != ct.get_team() and not self.map[ore.y][ore.x][1] in [EntityType.MARKER, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.ROAD, EntityType.BRIDGE, EntityType.BUILDER_BOT, None] and ct.get_position().distance_squared(ore) <= 5:
                if ore in self.tit:
                    self.tit.remove(ore)
                elif ore in self.ax:
                    self.ax.remove(ore)
                else:
                    ct.draw_indicator_line(ct.get_position(), self.core_pos, 0, 255, 255)
            if len(path_first_conv) > 1 and ct.can_build_conveyor(path_first_conv[-2], Direction.NORTH) and ct.get_position().distance_squared(ore) <= 5 and path_first_conv[-2].distance_squared(ore) == 1:     # Check if can build conveyor next to ore
                came_from_harvester_core, cost_from_harvester_core, best_tile_harvester_core = self.pathfinder(ct, self.core_pos, path_first_conv[-2], conv=True)
                came_from_harvester_conn, cost_from_harvester_conn, best_tile_harvester_conn = self.pathfinder(ct, self.closest_conn_to_core[0], path_first_conv[-2], conv=True)
                if cost_from_harvester_core[best_tile_harvester_core] <= cost_from_harvester_conn[best_tile_harvester_conn]:   # Must choose to build conveyors back to core or closest conveyor as stored
                    path_from_harvester = self.reconstruct_path(came_from_harvester_core, best_tile_harvester_core)
                    if len(path_from_harvester) <= 4 or len(path_from_harvester) > 5 + (path_first_conv[-2].distance_squared(best_tile_harvester_core))**(1/2):   # Uses bridge if cost of a bridge path around obstacle is less than conveyor path (based on scaling factor)
                        came_from_harvester, cost_from_harvester, best_tile_harvester_core = self.pathfinder(ct, self.core_pos, path_first_conv[-2], bridge=True)
                        path_from_harvester = self.reconstruct_path(came_from_harvester, best_tile_harvester_core)
                        if len(path_from_harvester) > 1:
                            came_from_harvester_conv_check, cost_from_harvester_conv_check, best_tile_harvester_core_conv_check = self.pathfinder(ct, path_from_harvester[1], path_first_conv[-2], conv=True)
                            if best_tile_harvester_core_conv_check == path_from_harvester[1] and cost_from_harvester_conv_check[best_tile_harvester_core_conv_check] == (abs(path_from_harvester[1].x - path_first_conv[-2].x) + abs(path_from_harvester[1].y - path_first_conv[-2].y)):        # If can build conveyors between these points directly
                                came_from_harvester = came_from_harvester_conv_check
                                cost_from_harvester = cost_from_harvester_conv_check
                                path_from_harvester = self.reconstruct_path(came_from_harvester, best_tile_harvester_core_conv_check)
                    else:
                        came_from_harvester = came_from_harvester_core
                        cost_from_harvester = cost_from_harvester_core
                else:
                    path_from_harvester = self.reconstruct_path(came_from_harvester_conn, best_tile_harvester_conn)
                    if len (path_from_harvester) <= 4 or len(path_from_harvester) > 5 + (path_first_conv[-2].distance_squared(best_tile_harvester_conn))**(1/2):
                        came_from_harvester, cost_from_harvester, best_tile_harvester_conn = self.pathfinder(ct, self.closest_conn_to_core[0], path_first_conv[-2], bridge=True)
                        path_from_harvester = self.reconstruct_path(came_from_harvester, best_tile_harvester_conn)
                        if len(path_from_harvester) > 1:
                            came_from_harvester_conv_check, cost_from_harvester_conv_check, best_tile_harvester_conn_conv_check = self.pathfinder(ct, path_from_harvester[1], path_first_conv[-2], conv=True)
                            if best_tile_harvester_conn_conv_check == path_from_harvester[1] and cost_from_harvester_conv_check[best_tile_harvester_conn_conv_check] == (abs(path_from_harvester[1].x - path_first_conv[-2].x) + abs(path_from_harvester[1].y - path_first_conv[-2].y)):        # If can build conveyors between these points directly
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
                    elif ct.can_build_bridge(path_from_harvester[0], path_from_harvester[1]):   # MAY CAUSE ERROR
                        self.closest_conn_to_core[1] = True
                        ct.build_bridge(path_from_harvester[0], path_from_harvester[1])
                        self.built_harvester[1] = path_from_harvester[1]
                        ct.draw_indicator_line(path_from_harvester[0], path_from_harvester[1], 255, 255, 255)
                    elif self.map[path_from_harvester[0].y][path_from_harvester[0].x][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.SPLITTER] and self.map[path_from_harvester[0].y][path_from_harvester[0].x][2] == ct.get_team():       # If already a friendly transport mechanism in space then move on
                        self.closest_conn_to_core[1] = True
                    else:
                        ct.draw_indicator_dot(path_from_harvester[0], 0, 0, 0)
                        ct.draw_indicator_line(path_from_harvester[0], path_from_harvester[1], 255, 0, 255)
                        #ct.resign()    # Probbaly ran out of money
                    if ct.can_move(ct.get_position().direction_to(path_from_harvester[0])): # Moves on to built conveyor or bridge
                        ct.move(ct.get_position().direction_to(path_from_harvester[0]))
                    else:   # Ran out of money
                        ct.draw_indicator_line(ct.get_position(), ct.get_position().add(ct.get_position().direction_to(path_from_harvester[0])), 0, 0, 255)
                        #ct.resign()
            elif self.map[path_first_conv[-1].y][path_first_conv[-1].x][1] == EntityType.ROAD and self.map[path_first_conv[-1].y][path_first_conv[-1].x][2] == ct.get_team() and ct.can_destroy(path_first_conv[-1]) and ct.get_position().distance_squared(ore) <= 1:
                ct.destroy(path_first_conv[-1])     # Destroy road built over ore
            elif self.map[ore.y][ore.x][1] in [EntityType.ROAD, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE] and self.map[ore.y][ore.x][2] != ct.get_team() and ((ct.can_move(ct.get_position().direction_to(ore)) and ct.get_position().distance_squared(ore) <= 2) or ct.get_position() == ore):
                
                if ct.get_position().distance_squared(ore) > 0 and ct.get_position().distance_squared(ore) <= 2 and ct.can_move(ct.get_position().direction_to(ore)):
                    self.built_harvester[1] = ct.get_position()
                    ct.move(ct.get_position().direction_to(ore))
                if ct.can_fire(ct.get_position()):
                    ct.fire(ct.get_position())
                if ct.get_tile_building_id(ct.get_position()) == None:
                    if self.map[self.built_harvester[1].y][self.built_harvester[1].x][1] in [EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and self.map[self.built_harvester[1].y][self.built_harvester[1].x][2] == ct.get_team() and ct.can_move(ct.get_position().direction_to(self.built_harvester[1])):
                        ct.move(ct.get_position().direction_to(self.built_harvester[1]))
                        self.built_harvester[1] = ct.get_position()
                return
            elif ct.can_build_harvester(ore) and (ore in self.tit or ore in self.ax) and (self.built_harvester[1] != False or (self.map[ct.get_position().y][ct.get_position().x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE] and self.map[ct.get_position().y][ct.get_position().x][2] == ct.get_team())) and ct.get_position().distance_squared(ore) == 1:     # If can build harvester, build it
                ct.draw_indicator_dot(path_first_conv[-2], 0, 0, 255)
                self.built_harvester[0] = True          # Flag harvester is built so must now build path back
                self.closest_conn_to_core[1] = True     # Ensures this happens in case that does not need to build any conveyors tp connect harvester
                ct.build_harvester(ore)
                if self.map[ct.get_position().y][ct.get_position().x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and self.map[ct.get_position().y][ct.get_position().x][2] == ct.get_team():
                    self.built_harvester[1] = False     # Reset if built conveyor next to ore
            elif ct.get_position().distance_squared(ore) <= 2:  # If ran out of money to build harvester
                pass

            else:       # Move towards ore if not close enough to do anything else      
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
            if self.built_harvester[1] != False:    # If bridge built
                if ct.get_position().distance_squared(self.built_harvester[1]) <= 2:    # If directly next to position it needs to move to
                    came_from_built_harvester_core, cost_from_built_harvester_core, best_tile_built_harvester_core = self.pathfinder(ct, self.core_pos, self.built_harvester[1], conv=True)
                    came_from_built_harvester_conn, cost_from_built_harvester_conn, best_tile_built_harvester_conn = self.pathfinder(ct, self.closest_conn_to_core[0], self.built_harvester[1], conv=True)
                    if cost_from_built_harvester_core[best_tile_built_harvester_core] <= cost_from_built_harvester_conn[best_tile_built_harvester_conn]:   # Choose closest between core and stored closest cnveyor
                        path_from_built_harvester = self.reconstruct_path(came_from_built_harvester_core, best_tile_built_harvester_core)
                        if len(path_from_built_harvester) <= 4 or len(path_from_built_harvester) > 5 + (self.built_harvester[1].distance_squared(best_tile_built_harvester_core))**(1/2):   # Uses bridge if cost of a bridge path around obstacle is less than conveyor path (based on scaling factor):
                            came_from_built_harvester, cost_from_built_harvester, best_tile_built_harvester_core = self.pathfinder(ct, self.core_pos, self.built_harvester[1], bridge=True)
                            path_from_built_harvester = self.reconstruct_path(came_from_built_harvester, best_tile_built_harvester_core)
                            if len(path_from_built_harvester) > 1:
                                came_from_built_harvester_conv_check, cost_from_built_harvester_conv_check, best_tile_built_harvester_core_conv_check = self.pathfinder(ct, path_from_built_harvester[1], self.built_harvester[1], conv=True)
                                if best_tile_built_harvester_core_conv_check == path_from_built_harvester[1] and cost_from_built_harvester_conv_check[best_tile_built_harvester_core_conv_check] == (abs(path_from_built_harvester[1].x - self.built_harvester[1].x) + abs(path_from_built_harvester[1].y - self.built_harvester[1].y)):        # If can build conveyors between these points directly
                                    came_from_built_harvester = came_from_built_harvester_conv_check
                                    cost_from_built_harvester = cost_from_built_harvester_conv_check
                                    path_from_built_harvester = self.reconstruct_path(came_from_built_harvester, best_tile_built_harvester_core_conv_check)
                        else:
                            came_from_built_harvester = came_from_built_harvester_core  # Not updating target of path here (if not conveyor path exists)
                            cost_from_built_harvester = cost_from_built_harvester_core
                        
                    else:
                        path_from_built_harvester = self.reconstruct_path(came_from_built_harvester_conn, best_tile_built_harvester_conn)
                        if len(path_from_built_harvester) <= 4 or len(path_from_built_harvester) > 5 + (self.built_harvester[1].distance_squared(best_tile_built_harvester_conn))**(1/2):
                            came_from_built_harvester, cost_from_built_harvester, best_tile_built_harvester_conn = self.pathfinder(ct, self.closest_conn_to_core[0], self.built_harvester[1], bridge=True)
                            path_from_built_harvester = self.reconstruct_path(came_from_built_harvester, best_tile_built_harvester_conn)
                            for i in range(len(path_from_built_harvester)):
                                ct.draw_indicator_dot(path_from_built_harvester[i], 255, 255, 0)
                            if len(path_from_built_harvester) > 1:
                                came_from_built_harvester_conv_check, cost_from_built_harvester_conv_check, best_tile_built_harvester_conn_conv_check = self.pathfinder(ct, path_from_built_harvester[1], self.built_harvester[1], conv=True)
                                if best_tile_built_harvester_conn_conv_check == path_from_built_harvester[1] and cost_from_built_harvester_conv_check[best_tile_built_harvester_conn_conv_check] == (abs(path_from_built_harvester[1].x - self.built_harvester[1].x) + abs(path_from_built_harvester[1].y - self.built_harvester[1].y)):        # If can build conveyors between these points directly
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
                        if ore in self.tit:
                            self.tit.remove(ore)                      # Remove ore from build queue
                        elif ore in self.ax:
                            self.ax.remove(ore)
                        else:
                            ct.draw_indicator_line(ct.get_position(), self.core_pos, 0, 0, 255)
                    else:
                        if self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0])).x][1] == EntityType.ROAD and self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0])).x][2] == ct.get_team() and ct.can_destroy(ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0]))):     # If a friendly road is on path, destroy it
                            ct.destroy(ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0])))
                        if path_from_built_harvester[0].distance_squared(path_from_built_harvester[1]) == 1 and ct.can_build_conveyor(path_from_built_harvester[0], path_from_built_harvester[0].direction_to(path_from_built_harvester[1])):    # Build conveyor and move on to it
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
                            #if ct.get_conveyor_cost()[0] < ct.get
                            ct.draw_indicator_dot(path_from_built_harvester[0], 255, 0, 255)
                            ct.draw_indicator_line(path_from_built_harvester[0], path_from_built_harvester[1], 255, 255, 255)
                            #ct.resign()    # So that does not fail if not enough resources
                            if path_from_built_harvester[0].distance_squared(path_from_built_harvester[1]) > 1:
                                self.built_harvester[1] = path_from_built_harvester[0]
                    
                else:
                    self.target = self.built_harvester[1]
                    self.explore(ct, self.built_harvester[1])
            else:   # Connect harvester with conveyors
                came_from_built_harvester_core, cost_from_built_harvester_core, best_tile_built_harvester_core = self.pathfinder(ct, self.core_pos, conv=True)
                #if cost_from_built_harvester_core[best_tile_built_harvester_core] > 0 + ct.get_position().distance_squared(best_tile_built_harvester_core):   # Uses bridge if cost of a bridge path around obstacle is less than conveyor path (based on scaling factor)
                #    came_from_built_harvester_core, cost_from_built_harvester_core, best_tile_built_harvester_core = self.pathfinder(ct, self.core_pos, bridge=True)
                came_from_built_harvester_conn, cost_from_built_harvester_conn, best_tile_built_harvester_conn = self.pathfinder(ct, self.closest_conn_to_core[0], conv=True)
                #if cost_from_built_harvester_conn[best_tile_built_harvester_conn] > 0 + ct.get_position().distance_squared(best_tile_built_harvester_conn):   # Uses bridge if cost of a bridge path around obstacle is less than conveyor path (based on scaling factor)
                #    came_from_built_harvester_conn, cost_from_built_harvester_conn, best_tile_built_harvester_conn = self.pathfinder(ct, self.closest_conn_to_core[0], bridge=True)
                if cost_from_built_harvester_core[best_tile_built_harvester_core] <= cost_from_built_harvester_conn[best_tile_built_harvester_conn]:   # Choose closest between core and stored closest cnveyor
                    path_from_built_harvester = self.reconstruct_path(came_from_built_harvester_core, best_tile_built_harvester_core)   # BOTTOM LEFT FAILS BECAUSE THE OPTIMAL CONVEYOR POSITION CHANGES TO RIGHT NEXT TO ITSELF WHICH MEANS IT DOESNT CONSIDER CONVEYOR PATH SO ASSUMES IT HAS COMPLETE ROUTE AS CONSTRUCTS ROUTE OF LENGTH ONE
                    if len(path_from_built_harvester) <= 4 or len(path_from_built_harvester) > 5 + (ct.get_position().distance_squared(best_tile_built_harvester_core))**(1/2) or (len(path_from_built_harvester) == 2 and path_from_built_harvester[1] not in [EntityType.ARMOURED_CONVEYOR, EntityType.CONVEYOR, EntityType.CORE, EntityType.BRIDGE, EntityType.SPLITTER]) or (len(path_from_built_harvester) == 1 and best_tile_built_harvester_core != self.core_pos):    # NOT PERFECT METRIC (COULD CONVERT THIS BACK TO HOW IT WAS BEFORE)
                        if ct.get_tile_building_id(ct.get_position()) != None and ct.get_entity_type(ct.get_tile_building_id(ct.get_position().add(ct.get_direction(ct.get_tile_building_id(ct.get_position()))))) != EntityType.HARVESTER:
                            came_from_built_harvester, cost_from_built_harvester, best_tile_built_harvester_core = self.pathfinder(ct, self.core_pos, ct.get_position().add(ct.get_direction(ct.get_tile_building_id(ct.get_position()))), bridge=True)
                        else:
                            came_from_built_harvester, cost_from_built_harvester, best_tile_built_harvester_core = self.pathfinder(ct, self.core_pos, bridge=True)
                        path_from_built_harvester = self.reconstruct_path(came_from_built_harvester, best_tile_built_harvester_core)
                        ct.draw_indicator_line(ct.get_position(), best_tile_built_harvester_core, 255, 0, 255)
                        for i in range(len(path_from_built_harvester) - 1):
                            ct.draw_indicator_line(path_from_built_harvester[i], path_from_built_harvester[i+1], 0, 255, 255)
                        if len(path_from_built_harvester) > 1:
                            came_from_built_harvester_conv_check, cost_from_built_harvester_conv_check, best_tile_built_harvester_core_conv_check = self.pathfinder(ct, path_from_built_harvester[1], conv=True)
                            if best_tile_built_harvester_core_conv_check == path_from_built_harvester[1] and cost_from_built_harvester_conv_check[best_tile_built_harvester_core_conv_check] == (abs(path_from_built_harvester[1].x - ct.get_position().x) + abs(path_from_built_harvester[1].y - ct.get_position().y)):        # If can build conveyors between these points directly
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
                            if best_tile_built_harvester_conn_conv_check == path_from_built_harvester[1] and cost_from_built_harvester_conv_check[best_tile_built_harvester_conn_conv_check] == (abs(path_from_built_harvester[1].x - ct.get_position().x) + abs(path_from_built_harvester[1].y - ct.get_position().y)):        # If can build conveyors between these points directly
                                came_from_built_harvester = came_from_built_harvester_conv_check
                                cost_from_built_harvester = cost_from_built_harvester_conv_check
                                path_from_built_harvester = self.reconstruct_path(came_from_built_harvester, best_tile_built_harvester_conn_conv_check)
                    else:
                        came_from_built_harvester = came_from_built_harvester_conn
                        cost_from_built_harvester = cost_from_built_harvester_conn
                if len(path_from_built_harvester) == 0:
                    ct.draw_indicator_line(ct.get_position(), self.core_pos, 255, 255, 255)
                    ct.resign()
                elif len(path_from_built_harvester) == 1 or (ct.get_position().distance_squared(path_from_built_harvester[1]) == 1 and self.map[path_from_built_harvester[1].y][path_from_built_harvester[1].x][1] in [EntityType.CORE, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.SPLITTER] and self.map[path_from_built_harvester[1].y][path_from_built_harvester[1].x][2] == ct.get_team() and not (self.map[path_from_built_harvester[1].y][path_from_built_harvester[1].x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and self.map[path_from_built_harvester[1].y][path_from_built_harvester[1].x][3][0] == ct.get_position().direction_to(path_from_built_harvester[1]).opposite()) and self.map[ct.get_position().y][ct.get_position().x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and self.map[ct.get_position().y][ct.get_position().x][3][0] == ct.get_position().direction_to(path_from_built_harvester[1])) or ((ct.get_position().distance_squared(path_from_built_harvester[0]) == 1 and self.map[path_from_built_harvester[0].y][path_from_built_harvester[0].x][1] in [EntityType.CORE, EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.SPLITTER] and self.map[path_from_built_harvester[0].y][path_from_built_harvester[0].x][2] == ct.get_team())):  # Check for being at end of path MAY NEED To ADD TO FOR BRIDGE STUFF
                    self.built_harvester[0] = False
                    self.closest_conn_to_core[1] = False
                    ct.draw_indicator_dot(ct.get_position().add(Direction.NORTH), 255, 255, 255)
                    if len(path_from_built_harvester) > 1:
                        ct.draw_indicator_dot(path_from_built_harvester[1], 0, 0, 0)
                    elif len(path_from_built_harvester) > 0:
                        ct.draw_indicator_line(path_from_built_harvester[0], self.core_pos, 0, 255, 0)
                    if ore in self.tit:
                        self.tit.remove(ore)                      # Remove ore from build queue
                    elif ore in self.ax:
                        self.ax.remove(ore)
                    else:
                        ct.draw_indicator_line(ct.get_position(), self.core_pos, 255, 255, 0)
                else:
                    if ct.get_position().distance_squared(path_from_built_harvester[1]) == 1 and (self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).x][1] == EntityType.ROAD and self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).x][2] == ct.get_team() or self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).x][2] == ct.get_team() and self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).x][3] == ct.get_position().direction_to(path_from_built_harvester[1]).opposite()) and ct.can_destroy(ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1]))):     # If a friendly road is on path, destroy it
                        ct.destroy(ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])))
                    elif ct.get_position().distance_squared(path_from_built_harvester[0]) == 1 and self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0])).x][1] == EntityType.ROAD and self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0])).x][2] == ct.get_team() and ct.can_destroy(ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0]))):     # If a friendly road is on path, destroy it
                        ct.destroy(ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[0])))
                    elif self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).x][1] == EntityType.HARVESTER and self.map[ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).y][ct.get_position().add(ct.get_position().direction_to(path_from_built_harvester[1])).x][2] == ct.get_team() and path_from_built_harvester[0] == ct.get_position() and self.map[ct.get_position().y][ct.get_position().x][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.CONVEYOR, EntityType.ROAD, EntityType.MARKER] and self.map[ct.get_position().y][ct.get_position().x][2] == ct.get_team() and ct.can_destroy(ct.get_position()):
                        ct.destroy(ct.get_position())
                    if ct.get_tile_building_id(ct.get_position()) != None and ((ct.get_position().distance_squared(path_from_built_harvester[1]) == 1 and ct.get_direction(ct.get_tile_building_id(ct.get_position())) != ct.get_position().direction_to(path_from_built_harvester[1])) or (ct.get_position().distance_squared(path_from_built_harvester[0]) == 1 and ct.get_direction(ct.get_tile_building_id(ct.get_position())) != ct.get_position().direction_to(path_from_built_harvester[0])) or (ct.get_position() == path_from_built_harvester[0] and ct.get_position().distance_squared(path_from_built_harvester[1]) > 1)) and self.map[ct.get_position().y][ct.get_position().x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and self.map[ct.get_position().y][ct.get_position().x][2] == ct.get_team() and ct.can_destroy(ct.get_position()):      # If finds new path that is more optimal but current conveyor faces in the wrong direction must rebuild
                        ct.destroy(ct.get_position())
                    if len(path_from_built_harvester) > 2 and ct.can_destroy(path_from_built_harvester[1]) and ct.get_entity_type(ct.get_tile_building_id(path_from_built_harvester[1])) in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and ((path_from_built_harvester[1].distance_squared(path_from_built_harvester[2]) == 1 and ct.get_direction(ct.get_tile_building_id(path_from_built_harvester[1])) != path_from_built_harvester[1].direction_to(path_from_built_harvester[2]))):# or (path_from_built_harvester[0].distance_squared(path_from_built_harvester[1]) == 1 and ct.get_direction(ct.get_tile_building_id(path_from_built_harvester[0])) != path_from_built_harvester[0].direction_to(path_from_built_harvester[1]))): #or (path_from_built_harvester[0] == path_from_built_harvester[1] and ct.get_position().distance_squared(path_from_built_harvester[1]) > 1)) and self.map[ct.get_position().y][ct.get_position().x][1] in [EntityType.CONVEYOR, EntityType.ARMOURED_CONVEYOR] and self.map[ct.get_position().y][ct.get_position().x][2] == ct.get_team() and ct.can_destroy(ct.get_position()):      # If finds new path that is more optimal but current conveyor faces in the wrong direction must rebuild
                        ct.destroy(path_from_built_harvester[1])
                    if ct.get_position().distance_squared(path_from_built_harvester[1]) == 1 and ct.can_build_conveyor(ct.get_position(), ct.get_position().direction_to(path_from_built_harvester[1])):
                        ct.build_conveyor(ct.get_position(), ct.get_position().direction_to(path_from_built_harvester[1]))
                    elif ct.can_build_harvester(path_from_built_harvester[1]):
                        ct.build_harvester(path_from_built_harvester[1])
                        if path_from_built_harvester[1] in self.tit:
                            self.tit.remove(path_from_built_harvester[1])   # Can remove this as still connecting other ore
                        elif path_from_built_harvester[1] in self.ax:
                            self.ax.remove(path_from_built_harvester[1])
                    elif len(path_from_built_harvester) > 2 and path_from_built_harvester[1].distance_squared(path_from_built_harvester[2]) == 1 and ct.can_build_conveyor(path_from_built_harvester[1], path_from_built_harvester[1].direction_to(path_from_built_harvester[2])) and self.map[path_from_built_harvester[1].y][path_from_built_harvester[1].x][0] not in [Environment.ORE_AXIONITE, Environment.ORE_TITANIUM]:    # Build conveyor and move on to it
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
                        #if path_from_built_harvester[0].distance_squared(path_from_built_harvester[1]) > 1:
                            #self.built_harvester[1] = path_from_built_harvester[0]
                        #ct.resign()


explore

def explore(self, ct, target=None):
        if target == None or target == Position(1000, 1000) or ct.get_position() == target:
            target = self.target
        closest_tile = Position(1000, 1000)
        #ct.draw_indicator_line(ct.get_position(), target, 0, 255, 0)
        for tile in ct.get_nearby_tiles():  # Find closest passable tile to target in vision
            if ct.get_position() != tile and tile.distance_squared(target) < closest_tile.distance_squared(target) and ct.get_tile_builder_bot_id(tile) == None and self.map[tile.y][tile.x][0] != Environment.WALL and ((self.map[tile.y][tile.x][1] == EntityType.CORE and self.map[tile.y][tile.x][2] == ct.get_team()) or self.map[tile.y][tile.x][1] in [EntityType.ARMOURED_CONVEYOR, EntityType.BRIDGE, EntityType.CONVEYOR, EntityType.MARKER, EntityType.ROAD, None]):
                closest_tile = tile
        if closest_tile.distance_squared(self.target) < self.explore_target.distance_squared(self.target):
            print(self.explore_target, self.target, closest_tile)
            self.explore_target = closest_tile
            self.move_dir = Direction.CENTRE
        if closest_tile != Position(1000, 1000):
            came_from_explore, cost_explore, best_tile_unused_1 = self.pathfinder(ct, self.explore_target)
            path_explore = self.reconstruct_path(came_from_explore, self.explore_target)
            ct.draw_indicator_line(ct.get_position(), self.explore_target, 0, 0, 255)
            if len(path_explore) == 0:      # If there is no moveable path to target
                if self.explore_left:
                    if self.move_dir == Direction.CENTRE:
                        self.move_dir = ct.get_position().direction_to(self.explore_target)
                    if self.move_dir in DIAGONALS:
                        check_pos = ct.get_position().add(self.move_dir.rotate_right().rotate_right().rotate_right())
                        if self.map[check_pos.y][check_pos.x][0] == Environment.WALL:
                            move_dir = self.move_dir.rotate_right().rotate_right()
                        else:
                            move_dir = self.move_dir
                    elif self.move_dir in STRAIGHTS:
                        check_pos = ct.get_position().add(self.move_dir.rotate_right().rotate_right())
                        if self.map[check_pos.y][check_pos.x][0] == Environment.WALL:
                            move_dir = self.move_dir.rotate_right()
                        else:
                            move_dir = self.move_dir
                    for i in range(8):
                        check_pos = ct.get_position().add(move_dir)
                        if ct.get_tile_builder_bot_id(check_pos) != None:
                            break
                        if check_pos.x < 0 or check_pos.x >= ct.get_map_width() or check_pos.y < 0 or check_pos.y >= ct.get_map_height():
                            self.explore_left = False
                            break
                        ct.draw_indicator_dot(check_pos, 255, 0, 0)
                        if ct.can_build_road(check_pos):
                            ct.build_road(check_pos)
                        if ct.can_move(move_dir):
                            ct.move(move_dir)
                            self.move_dir = move_dir
                            break
                        move_dir = move_dir.rotate_left()
                    if ct.get_move_cooldown() == 0:
                        ct.draw_indicator_line(ct.get_position(), ct.get_position().add(move_dir), 255, 0, 0)
                        #ct.resign()
                else:
                    if self.move_dir == Direction.CENTRE:
                        self.move_dir = ct.get_position().direction_to(self.explore_target)
                    else:
                        self.move_dir = self.move_dir.opposite()
                    if self.move_dir in DIAGONALS:
                        check_pos = ct.get_position().add(self.move_dir.rotate_left().rotate_left().rotate_left())
                        if self.map[check_pos.y][check_pos.x][0] == Environment.WALL:
                            move_dir = self.move_dir.rotate_left().rotate_left()
                        else:
                            move_dir = self.move_dir
                    elif self.move_dir in STRAIGHTS:
                        check_pos = ct.get_position().add(self.move_dir.rotate_left().rotate_left())
                        if self.map[check_pos.y][check_pos.x][0] == Environment.WALL:
                            move_dir = self.move_dir.rotate_left()
                        else:
                            move_dir = self.move_dir
                    for i in range(8):
                        check_pos = ct.get_position().add(move_dir)
                        if ct.get_tile_builder_bot_id(check_pos) != None:
                            break
                        if check_pos.x < 0 or check_pos.x >= ct.get_map_width() or check_pos.y < 0 or check_pos.y >= ct.get_map_height():
                            self.explore_left = True    # Temporary but should actually change target as wil otherwise just continue in loop
                            break
                        ct.draw_indicator_dot(check_pos, 255, 0, 0)
                        if ct.can_build_road(check_pos):
                            ct.build_road(check_pos)
                        if ct.can_move(move_dir):
                            ct.move(move_dir)
                            self.move_dir = move_dir
                            break
                        move_dir = move_dir.rotate_right()
                    if ct.get_move_cooldown() == 0:
                        ct.draw_indicator_line(ct.get_position(), ct.get_position().add(move_dir), 255, 0, 0)
                        #ct.resign()
            else:
                for i in range(len(path_explore)):
                    ct.draw_indicator_dot(path_explore[i], 0, 255, 255)
                if len(path_explore) > 1:    # If next to target but cannot move there as there is a builder bot this condition is not satisfied so will just wait
                    if ct.can_build_road(path_explore[1]):  # Fails if trying to build on to core
                        ct.build_road(path_explore[1])
                    if ct.can_move(ct.get_position().direction_to(path_explore[1])):
                        ct.move(ct.get_position().direction_to(path_explore[1]))
                    else:
                        if ct.get_tile_builder_bot_id(path_explore[1]) != None:
                            move_dir = ct.get_position().direction_to(path_explore[1])
                            for i in range(8):
                                move_dir = move_dir.rotate_left()   # Try to move anticlockwise around target
                                if ct.can_build_road(ct.get_position().add(move_dir)):
                                    ct.build_road(ct.get_position().add(move_dir))
                                if ct.can_move(move_dir):
                                    ct.move(move_dir)
                                    self.move_dir = move_dir
                                else:
                                    ct.draw_indicator_dot(ct.get_position().add(move_dir), 255, 0, 0)
                        else:
                            ct.draw_indicator_line(ct.get_position(), ct.get_position().add(ct.get_position().direction_to(path_explore[1])), 0, 255, 0)
                            #ct.resign()
                                # Ran out of money
        else:
            self.explore(ct, self.explore_target)
        #if self.explore_target == self.target:
            #self.explore_target = Position(1000, 1000)