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


def pathfinder(self, ct, target, start=None, bridge=False, conv=False, avoid=False, any=False):       # Pass Position
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
                if ( 0 <= self.target.add(d).y < ct.get_map_height() and 0 <= self.target.add(d).x < ct.get_map_width() and ct.get_tile_building_id(self.target.add(d)) is not None and
                        ct.get_entity_type(ct.get_tile_building_id(self.target.add(d))) in [EntityType.SPLITTER, EntityType.FOUNDRY] and 
                        ct.can_build_sentinel(self.target, self.target.direction_to(self.core_pos).opposite())):
                    ct.build_sentinel(self.target, self.target.direction_to(self.core_pos).opposite())
                elif ( 0 <= self.target.add(d).y < ct.get_map_height() and 0 <= self.target.add(d).x < ct.get_map_width() and ct.get_tile_building_id(self.target.add(d)) is not None and 
                        ct.get_entity_type(ct.get_tile_building_id(self.target.add(d))) in [EntityType.SPLITTER, EntityType.FOUNDRY] and 
                        ct.can_build_gunner(self.target, d.opposite())):
                    ct.build_gunner(self.target, d.opposite())

        if pos == self.target:
            for d in DIRECTIONS:
                if ct.can_move(d):
                    ct.move(d)

        #if not(ct.get_position().add(ct.get_position().direction_to(self.target)) == self.target):
            #self.explore(ct)