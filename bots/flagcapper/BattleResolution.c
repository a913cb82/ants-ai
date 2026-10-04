/*
	BATTLE RESOLUTION
	-----------------
	This is the fun part. Additonal comments are added inside do_battles(), otherwise
	all the rest of the information about battle functions can be found here.

	resolve_battles_pwr() -- simply takes a set of ants and sets a flag based on who
							 lives and who dies

	iterate_battles() -- this function "iterates" through all possible battle senerios.
						 Everytime it is called, it changes the current directions of
						 the "test_ants" to the next possible battle senerio

	select_battle_ants() -- Recursively selects a neighbourhood of related ants that
							may come into conflict in the next turn based on a "seed"
							ant. The most important of these ants will be selected,
							and battle resolution will be preformed on this subset
							of ants. Eventually, all ants within range of an enemy
							will be selected at least once.

	do_battles() -- exactly what the name implies. See the comments inside the function
					for more details


*/

void resolve_battles_pwr(test_ant *ants, int ant_len, int *attack_lookup, struct game_info *Info) {

	int i, j;
	int enemy_num[ant_len];
	memset(enemy_num, 0, ant_len*sizeof(int));

	int radius_index[ant_len][ant_len];

	memset(radius_index, 0, ant_len*ant_len*sizeof(int));

	for (i = 0; i < ant_len; ++i) {
		if (ants[i].ignore_battle[ants[i].dir])
			continue;

		for (j = i; j < ant_len; ++j) {
			if (ants[i].player == ants[j].player || ants[j].ignore_battle[ants[j].dir])
				continue;

			if (*(attack_lookup + i*25*ant_len + ants[i].dir*5*ant_len + j*5 + ants[j].dir)) {
				++enemy_num[i];
				++enemy_num[j];

				radius_index[i][j] = 1;
				radius_index[j][i] = 1;
			}
		}
	}

	for (i = 0; i < ant_len; ++i) {
		if (ants[i].flags & 2 || ants[i].ignore_battle[ants[i].dir])
			continue;

		int min_enemy_weakness = INT_MAX;
		int enemy = -1;

		for (j = 0; j < ant_len; ++j) {
			if (ants[i].player == ants[j].player || enemy_num[j] >= min_enemy_weakness || ants[j].ignore_battle[ants[j].dir])
				continue;

			if (radius_index[i][j]) {
				min_enemy_weakness = enemy_num[j];
				enemy = j;
			}
		}

		if (min_enemy_weakness < enemy_num[i]) {
			ants[i].flags |= 2;
		}
		else if (min_enemy_weakness == enemy_num[i]) {
			ants[i].flags |= 2;
			ants[enemy].flags |= 2;
		}
	}
}

int iterate_battles(test_ant *ants, int ant_len, long *pow_index_5, struct game_info *Info) {
	int i, j, k;
	int skipped = 0;
	int advance;
	int tries = 0;

	int completed_rotation = 0;

	try_again:

	advance = 0;
	j = 0;

	for (i = 0; i < ant_len; ++i) {
		if (ants[i].flags & 24) {
//			skipped += pow_index_5[i + 1];
			continue;
		}

		if (j == 5) {
//			ants[i].dir = 4;
//			ants[i].flags |= 16;

			j = 0;
			continue;
		}

		if (ants[i].dir < 4) {
			++ants[i].dir;

			if (ants[i].ignore_position[ants[i].dir]) {
				--i;
				++j;
				continue;
			}

			char location_data = Info->map[ ants[i].t_offset[ants[i].dir] ];

			if (location_data == '%' || location_data == '*') {
				ants[i].ignore_position[ants[i].dir] = 1;
				--i;
				++j;
				continue;
			}

			if (!advance)
				break;
		}
		else {
			ants[i].dir = 0;

			if (ants[i].ignore_position[0]) {
				--i;
				++j;
				advance = 1;
				continue;
			}

			char location_data = Info->map[ ants[i].t_offset[0] ];

			if (location_data == '%' || location_data == '*') {
				ants[i].ignore_position[0] = 1;
				--i;
				++j;
				advance = 1;
				continue;
			}
		}

		advance = 0;
		j = 0;
	}

	if (i == ant_len) {
		if (!completed_rotation)
			completed_rotation = 1;
		else
			return -1;
	}

	if (tries < pow_index_5[ant_len]) {
		for (j = 0; j < ant_len; ++j) {
			for (k = j + 1; k < ant_len; ++k) {
				if (ants[j].t_offset[ants[j].dir] == ants[k].t_offset[ants[k].dir]) {
					++tries;
					goto try_again;
				}
			}
		}
	}

	if (completed_rotation)
		return -1;

	return skipped;
}

int select_battle_ants(test_ant *ants, int ant_num, int node_id, int depth, int flags, struct game_info *Info) {


	int number = 1;
	int i;

	int (*dirs[5]) (int offset, struct game_info *Info);
	dirs[0] = North;
	dirs[1] = East;
	dirs[2] = South;
	dirs[3] = West;
	dirs[4] = 0;

	ants[node_id].flags |= 1;
	ants[node_id].depth = depth;

	for (i = 0; i < ant_num; ++i) {
		if (ants[i].player == ants[node_id].player || (ants[node_id].player != 'a' && ants[i].player != 'a') || ants[i].flags & 1)
			continue;

		int progress_type = 0;

		if (ants[i].flags & 4)
			progress_type = 1;
		else if (ants[i].flags & 8 && ~flags & 2)
			progress_type = 2;


		if (progress_type) {
			int expand = 2;

			if (in_radius(ants[i].offset, ants[node_id].offset, (int) pow(sqrt(Info->attackradius_sq) + expand, 2), Info)) {
				number += select_battle_ants(ants, ant_num, i, depth + 1, progress_type, Info);
			}
		}
	}

	return number;
}

void do_battles(int *complete, struct sd_pair *sd_pair, struct game_state *Game, struct game_info *Info) {

	/*

		ATTACK!
		-------------
		The basic idea for this function is to isolate groups of ants, iterate
		through all the battle possibilites they encounter, and rank them.
		Then select the best possibility from that set and make your moves
		accordingly. If it sounds like alpha-beta, that's probably because it
		is, but I'm not familiar enough with algorithmns to tell you exactly
		what it qualifies as, so I'm just going to explain what it does.

	*/

	int i, j;
	int map_len = Info->rows*Info->cols;


	int (*dirs[5]) (int offset, struct game_info *Info);
	dirs[0] = North;
	dirs[1] = East;
	dirs[2] = South;
	dirs[3] = West;
	dirs[4] = Stop;

	int total_ants = Game->my_count + Game->enemy_count;


	/*

		This section initializes the set of ants that will be used to resolve
		battles. It includes both friendly and enemy ants, all of which are
		collectively called "collision_ants".

	*/


	test_ant collision_ants[total_ants];
	memset(collision_ants, 0, (total_ants)*sizeof(test_ant));

	for (i = 0; i < Game->my_count; ++i) {
		int offset = Game->my_ants[i].row*Info->cols + Game->my_ants[i].col;

		collision_ants[i].id = i;
		collision_ants[i].offset = offset;

		for (j = 0; j < 4; ++j)
			collision_ants[i].t_offset[j] = *(MOVE_LOOKUP + offset*4 + j); //dirs[j] (offset, Info);

		collision_ants[i].t_offset[4] = offset;
		collision_ants[i].player = 'a';

		if (sd_pair[i].id != -1) {
			collision_ants[i].flags |= 8;
			collision_ants[i].dir = get_num(sd_pair[i].suggest);
		}
		else {
			collision_ants[i].flags |= 4;
		}
	}

	for (; i < total_ants; ++i) {
		int relative_id = i - Game->my_count;
		int offset = Game->enemy_ants[relative_id].row*Info->cols + Game->enemy_ants[relative_id].col;

		for (j = 0; j < 4; ++j)
			collision_ants[i].t_offset[j] = *(MOVE_LOOKUP + offset*4 + j);// dirs[j] (offset, Info);

		collision_ants[i].t_offset[4] = offset;

		collision_ants[i].id = i;
		collision_ants[i].offset = offset;
		collision_ants[i].player = Game->enemy_ants[relative_id].player;
		collision_ants[i].flags |= 4;
	}

	/*

		This loop starts battle resolution. We will break out of this loop once
		all collision_ants are either out of battle range or have been through
		the battle resolution process at least once.


	*/

	while (Game->enemy_count > 0) {

		double time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));

		if (time_spent > TIME_LIMIT*0.8) {
			fprintf(stderr, " {broke %g} ", TIME_LIMIT*0.8);

			if (MAX_GROUP_SIZE > 8)
				--MAX_GROUP_SIZE;

			break;
		}

		//	Selects a seed ant based on its distance to its nearest enemy

		int seed_ant = -1;
		int smallest_enemy_dist = INT_MAX;

		for (i = 0; i < total_ants; ++i) {
			if (collision_ants[i].flags & 4 && collision_ants[i].player == 'a') {
				for (j = 0; j < total_ants; ++j) {
					if (collision_ants[j].player != 'a') {
						int dist = distance(collision_ants[i].offset / Info->cols, collision_ants[i].offset % Info->cols,
											collision_ants[j].offset / Info->cols, collision_ants[j].offset % Info->cols, Info);

						if (dist < smallest_enemy_dist) {
							smallest_enemy_dist = dist;
							seed_ant = i;
						}
					}
				}
			}
		}

		if (seed_ant == -1)
			break;

		//	This is code is used so that ants that are not part of the same set that is being tested
		// 	don't try to both move to the same square. It's not important for the overall understanding
		// 	of the program.

		int modification_made = 1;

		while (modification_made) {

			modification_made = 0;

			for (i = 0; i < Game->my_count; ++i) {
				int possible_dirs = 0;
				int dir = -1;

				for (j = 0; j < 5; ++j) {
					if (sd_pair[i].ignore[j] != 1) {
						++possible_dirs;
						dir = j;
					}
				}

				if (possible_dirs == 1) {
					for (j = 0; j < Game->my_count; ++j) {
						if (j == i)
							continue;

						int k;

						for (k = 0; k < 5; ++k) {
							if (collision_ants[i].t_offset[dir] == collision_ants[j].t_offset[k]
								&& (collision_ants[j].ignore_position[k] != 1 || sd_pair[j].ignore[k] != 1)) {
								collision_ants[j].ignore_position[k] = 1;
								sd_pair[j].ignore[k] = 1;

								modification_made = 1;
							}
						}
					}
				}
			}
		}


		//	Here we pass collision_ants and a seed_ant to the select_battle_ants() function,
		//	which sets some flags and some depth values that tell us information about the
		//	battlefield and the set of ants that are involved in the battle.

		int nearby_ant_num = select_battle_ants(collision_ants, total_ants, seed_ant, 0, 0x1, Info);

		if (nearby_ant_num == 1) {
			collision_ants[seed_ant].flags &= ~1;
			collision_ants[seed_ant].flags &= ~4;
			continue;
		}

		test_ant battle_ants[nearby_ant_num];
		memset(battle_ants, -1, sizeof(test_ant)*nearby_ant_num);

		int battle_num = 0;
		int enemy_num = 0;
		int my_num = 0;
		int fixed_num = 0;
		int my_fixed_num = 0;

		int MAX_NON_FIXED;

		if (nearby_ant_num > 8) {
			MAX_NON_FIXED = 8;
		}
		else
			MAX_NON_FIXED = nearby_ant_num;

		int my_group = 0;
		int enemy_group = 0;

		for (i = 0; i < total_ants; ++i) {
			if (collision_ants[i].flags & 1) {
				if (collision_ants[i].player == 'a')
					++my_group;
				else
					++enemy_group;
			}
		}

		//	This section sets a maximum depth from which ants will be selected for battle.
		//	The depth is a value that indicates at what level of recursion within
		//	select_battle_ants() an ant was found to be within radius of a battle zone.
		//	The lower the depth, the more relevent the ant to the battle. The higher the
		//	depth, the less relevent it is.

		int max_depth = 1;

		int largest_depth = 0;

		for (i = 0; i < total_ants; ++i) {
			if (!(collision_ants[i].flags & 1))
				continue;

			if (collision_ants[i].depth > largest_depth) {
				largest_depth = collision_ants[i].depth;
			}
		}

		while(1) {

			int test_depth = max_depth + 2;
			if (test_depth > largest_depth)
				test_depth = largest_depth;

			int relevent_ants = 0;
			int non_fixed_count = 0;

			for (i = 0; i < total_ants; ++i) {
				if ((collision_ants[i].flags & 8) || !(collision_ants[i].flags & 1))
					continue;

				++non_fixed_count;

				if (collision_ants[i].depth <= test_depth) {
					++relevent_ants;
				}
			}

			if (relevent_ants > MAX_NON_FIXED)
				break;
			else {
				max_depth = test_depth;
			}

			if (relevent_ants == non_fixed_count)
				break;
		}

		//	Now we iterate through collision_ants and use the selected battle ants to
		//	initialize the battle_ants array. Since there is limited room in our
		//	array for ants we want to test, we have to be extra picky in our selection.
		//	Specifically ants with lower depths, ants that are closer to the battle,
		//	and enemy ants will tend to be favoured. The seed ant, however, will
		//	always be included.

		int fulcrum = seed_ant;

		for (i = 0; i < total_ants; ++i) {
			if ((collision_ants[i].flags & 1)) {

				if (collision_ants[i].depth > max_depth) {
					collision_ants[i].flags &= ~1;
					continue;
				}

				int replace = -1;

				for (j = 0; j < MAX_NON_FIXED; ++j) {
					if (battle_ants[j].id == -1) {
						replace = j;
						break;
					}
				}

				if (replace == -1) {

					int highest_depth = INT_MIN;

					for (j = 0; j < battle_num; ++j) {
						if (battle_ants[j].depth > collision_ants[i].depth) {
							if (battle_ants[j].depth > highest_depth) {
								highest_depth = battle_ants[j].depth;
								replace = j;
							}
						}
					}

					if (replace == -1) {

					int in_range = 0;


					for (j = 0; j < MAX_NON_FIXED; ++j) {
						if (collision_ants[i].player == battle_ants[j].player)
							continue;

						if (in_radius(collision_ants[i].offset, battle_ants[j].offset, (int) pow(sqrt(Info->attackradius_sq) + 2, 2), Info)) {
							in_range = 1;
							break;
						}
					}

					if (!in_range && enemy_num > 0) {
						collision_ants[i].flags &= ~1;
						continue;
					}

					if (collision_ants[i].player != 'a') {
						int fulcrum_dist = INT_MIN;

						for (j = 0; j < MAX_NON_FIXED; ++j) {
							if (battle_ants[j].id == fulcrum)
								continue;

							if (battle_ants[j].player == 'a') {
								int test_dist = euc_distance_sq(battle_ants[j].offset / Info->cols,
															    battle_ants[j].offset % Info->cols,
															    collision_ants[fulcrum].offset / Info->cols,
															    collision_ants[fulcrum].offset % Info->cols, Info);

								if (test_dist > fulcrum_dist) {
									fulcrum_dist = test_dist;
									replace = j;
								}
							}
						}
					}


					}

					if (replace == -1) {
						for (j = 0; j < MAX_NON_FIXED; ++j) {
							if (battle_ants[j].id == fulcrum)
								continue;

							int new_dist = euc_distance(collision_ants[i].offset / Info->cols,
														collision_ants[i].offset % Info->cols,
														collision_ants[fulcrum].offset / Info->cols,
														collision_ants[fulcrum].offset % Info->cols, Info);

							if (collision_ants[i].player != 'a')
								new_dist -= (int) (sqrt(Info->attackradius_sq) + 2);

							int old_dist = euc_distance(battle_ants[j].offset / Info->cols,
														battle_ants[j].offset % Info->cols,
														collision_ants[fulcrum].offset / Info->cols,
														collision_ants[fulcrum].offset % Info->cols, Info);

							if (battle_ants[j].player != 'a')
								old_dist -= (int) (sqrt(Info->attackradius_sq) + 2);

							if (new_dist < old_dist) {
								replace = j;
								break;
							}
						}
					}

					if (replace == -1) {
						if (collision_ants[i].flags & 8 && MAX_NON_FIXED < MAX_GROUP_SIZE) {
							replace = MAX_NON_FIXED;
						}
					}

				}

				if (replace == -1) {
					collision_ants[i].flags &= ~1;
					continue;
				}

				if (replace >= battle_num)
					++battle_num;
				else {
					if (battle_ants[replace].player != 'a') {
						--enemy_num;
						collision_ants[battle_ants[replace].id].flags |= 4;
					}

					if (battle_ants[replace].flags & 8) {
						--fixed_num;
						if (battle_ants[replace].player == 'a')
							--my_fixed_num;
					}
					else if (battle_ants[replace].player == 'a') {
						collision_ants[battle_ants[replace].id].flags |= 4;
					}
				}

				collision_ants[i].flags &= ~1;
				memcpy(&battle_ants[replace], &collision_ants[i], sizeof(test_ant));

				if (battle_ants[replace].player == 'a')
					collision_ants[i].flags &= ~4;

	  			if (collision_ants[i].flags & 8) {
					++fixed_num;
					if (collision_ants[i].player == 'a')
						++my_fixed_num;

					if (MAX_NON_FIXED < MAX_GROUP_SIZE)
						++MAX_NON_FIXED;
				}
				else {
					battle_ants[replace].dir = 4;
				}

				if (collision_ants[i].player != 'a') {
					++enemy_num;
				}
			}
		}

		my_num += battle_num - enemy_num;

		//	If we ran through all the possibilities of all the ants, then we'd have a
		//	maximum runtime of 5^(num_ants). This is ridiculously high and not good.
		//	Therefore, we limit the amount of possibilities considered by excluding
		//	certain positions and certain battles that can either never happen, or are
		//	not important. This is what this next section does.


		for (i = 0; i < battle_num; ++i) {
			for (j = 0; j < 4; ++j) {
				int new_position = battle_ants[i].t_offset[j];
				int dont_ignore = 0;

				int k;

				for (k = 0; k < battle_num; ++k) {
					if (battle_ants[i].player == battle_ants[k].player)
						continue;

					int l;

					for (l = 0; l < 5; ++l) {
						if (in_radius(battle_ants[k].t_offset[l], new_position, Info->attackradius_sq, Info)) {
							dont_ignore = 1;
							break;
						}
					}

					if (dont_ignore)
						break;
				}

				if (!dont_ignore) {
					if (battle_ants[i].player != 'a')
						battle_ants[i].ignore_position[j] = 1;

					battle_ants[i].ignore_battle[j] = 1;
				}
			}
		}

		//	We still don't want to collide with ants that we are not resolving
		//	battles for, so we take them into account here.

		for (i = 0; i < battle_num; ++i) {
			if (battle_ants[i].player != 'a')
				continue;

			for (j = 0; j < 4; ++j) {
				int new_position = battle_ants[i].t_offset[j];

				if (Info->map[new_position] == 'a') {
					int k;

					int is_accounted_for = 0;

					for (k = 0; k < battle_num; ++k) {
						if (i == k || battle_ants[k].player != 'a')
							continue;

						if (battle_ants[k].offset == new_position) {
							is_accounted_for = 1;
							break;
						}
					}

					if (!is_accounted_for) {
						battle_ants[i].ignore_position[j] = 1;
					}
				}
			}
		}

		//	If it turns out that this seed is a dud, unset the seed flag
		//	(and the battle flag) for that ant and try again.

		if (battle_num == 1 || enemy_num == 0) {
			collision_ants[fulcrum].flags &= ~1;
			collision_ants[fulcrum].flags &= ~4;
			continue;
		}


		//	Sometimes food will get in the way of our battle. No matter, we'll
		//	just have to account for it too.

		int nearby_food = 0;

		for (i = 0; i < Game->food_count; ++i) {
			int food_offset = Game->food[i].row*Info->cols + Game->food[i].col;

			for (j = 0; j < battle_num; ++j) {
				if (battle_ants[j].player != 'a')
					continue;

				if (in_radius(battle_ants[j].offset, food_offset, (int) pow(sqrt(Info->attackradius_sq) + 2, 2), Info)) {
					++nearby_food;
					break;
				}
			}
		}

		int relevent_food[nearby_food][4];

		if (nearby_food > 0) {
			nearby_food = 0;

			for (i = 0; i < Game->food_count; ++i) {
				int food_offset = Game->food[i].row*Info->cols + Game->food[i].col;

				for (j = 0; j < battle_num; ++j) {
					if (battle_ants[j].player != 'a')
						continue;

					if (in_radius(battle_ants[j].offset, food_offset, (int) pow(sqrt(Info->attackradius_sq) + 2, 2), Info)) {
						relevent_food[nearby_food][0] = food_offset;
						relevent_food[nearby_food][1] = i;
						++nearby_food;
						break;
					}
				}
			}

			for (i = 0; i < nearby_food; ++i) {
				char closest_passive = -1;
				int passive_distance = INT_MAX;

				for (j = 0; j < total_ants; ++j) {
					int food_dist = distance(collision_ants[j].offset / Info->cols, collision_ants[j].offset % Info->cols,
											 Game->food[relevent_food[i][1]].row, Game->food[relevent_food[i][1]].col, Info);

					if (food_dist < passive_distance) {
						int k;
						int is_passive = 1;

						for (k = 0; k < battle_num; ++k) {
							if (collision_ants[j].offset == battle_ants[k].offset) {
								is_passive = 0;
								break;
							}
						}

						if (is_passive) {
							passive_distance = food_dist;
							closest_passive = collision_ants[j].player;
						}
					}
				}

				if (closest_passive == 'a') {
					relevent_food[i][2] = (5*enemy_num)/my_num;
					relevent_food[i][3] = (-10*my_num)/enemy_num;
				}
				else {
					relevent_food[i][2] = 1;
					relevent_food[i][3] = 0;
				}

			}
		}

		//	Not only can food get in the way of battles, so can hives!

		int relevent_hives[Game->hive_count];
		int relevent_hive_num = 0;

		for (i = 0; i < Game->hive_count; ++i) {
			if (Game->hives[i].player != 'a') {
				for (j = 0; j < battle_num; ++j) {
					if (battle_ants[j].player == 'a') {
						int dist = euc_distance(Game->hives[i].row, Game->hives[i].col,
												battle_ants[j].offset / Info->cols, battle_ants[j].offset % Info->cols, Info);

						if (dist == 1) {
							relevent_hives[relevent_hive_num] = Game->hives[i].row*Info->cols + Game->hives[i].col;
							++relevent_hive_num;
						}
					}
				}
			}
		}

		int protect_hive = 0;
		int rel_hive_count = 0;

		for (i = 0; i < Game->hive_count; ++i) {
			if (Game->hives[i].player == 'a')
				++rel_hive_count;
		}

		int enemy_hive_dist_sq = INT_MAX;

		for (i = 0; i < battle_num; ++i) {
			for (j = 0; j < Game->hive_count; ++j) {
				if (Game->hives[j].player != 'a') {
					int new_dist = euc_distance_sq(battle_ants[i].offset / Info->cols,
												   battle_ants[i].offset % Info->cols,
												   Game->hives[j].row,
												   Game->hives[j].col,
												   Info);

					if (new_dist < enemy_hive_dist_sq)
						enemy_hive_dist_sq = new_dist;
				}
			}
		}

		if (Game->enemy_count > 0) {

			for (i = 0; i < Game->hive_count; ++i) {
				if (Game->hives[i].player == 'a' || my_num > enemy_num) {
					int min_dist_enemy = INT_MAX;

					for (j = 0; j < battle_num; ++j) {
						if (battle_ants[j].player == 'a')
							continue;

						int test_dist = euc_distance_sq(Game->hives[i].row, Game->hives[i].col,
														battle_ants[j].offset / Info->cols, battle_ants[j].offset % Info->cols, Info);

						if (test_dist < min_dist_enemy)
							min_dist_enemy = test_dist;
					}

					int my_min_dist = INT_MAX;

					for (j = 0; j < Game->my_count; ++j) {
						int test_dist = euc_distance_sq(Game->hives[i].row, Game->hives[i].col,
													Game->my_ants[j].row, Game->my_ants[j].col, Info);

						if (test_dist < my_min_dist)
							my_min_dist = test_dist;
					}

					if (min_dist_enemy <= (int) pow((((int) sqrt(Info->attackradius_sq)) + 3), 2)
						&& ((int) (sqrt(min_dist_enemy) - sqrt(my_min_dist))) <= (((int) sqrt((double) Info->attackradius_sq)) + 4)) {
						protect_hive = 1;
						break;
					}
				}
			}
		}

		// 	Here's some important bits.
		//
		//	The maximum option number, as given by option_num, is
		//	defined as the the number of unique combinationes of
		//	directions that my moving ants can take.
		//
		//	The scores array keeps track of the score of a particular
		//	option. The tests array keeps track of the number of
		//	tests for that option, and the best_dirs array keeps
		//	track of the best option for a particular ant


		int cycle_length = (int) pow(5, battle_num);
		int option_num = (int) pow(5, battle_num - enemy_num - my_fixed_num);

		long *scores = malloc(option_num*sizeof(long));
		int *tests = malloc(option_num*sizeof(int));
		int best_dirs[battle_num];

		memset(scores, 0, sizeof(long)*option_num);
		memset(tests, 0, sizeof(int)*option_num);

		// 	optimize, optimize, OPTIMIZE

		long pow_index_5[battle_num + 1];

		for (i = 0; i < battle_num + 1; ++i) {
			pow_index_5[i] = (long) pow((double) 5, (double) i);
		}



		//	Some might consider the next piece of code an abomination. I think it's awesome.
		//
		//	Basically, it's (up to) 6 loops nested inside each other. Plus, we're already
		//	inside a loop that breaks whenever a recursive function siezes to return a valid
		//	set of ants that have yet to be resolved, based on some far more crazy code that
		//	is yet to come. It probably violates every coding standard out there, which is
		//	the very thing that makes it great. I have no idea how I even came up with it.
		//
		//	In case you're wondering, it initializes the following array for caching purposes.
		//	It's just a performance boost (believe me, we need it).

		int attack_lookup[battle_num][5][battle_num][5];
		memset(attack_lookup, 0, battle_num*battle_num*25*sizeof(int));

		int not_options_i = 0;


		for (i = 0; i < battle_num; ++i) {
			int my_option_i = 1;

			if (battle_ants[i].player != 'a' || battle_ants[i].flags & 24) {
				my_option_i = 0;
				++not_options_i;
			}

			for (j = 0; j < 5; ++j) {
				if (battle_ants[i].flags & 24 && j != battle_ants[i].dir)
					continue;

				int j_offset = battle_ants[i].t_offset[j];// dirs[j] (battle_ants[i].offset, Info);

				int k;
				int my_option_k = 1;
				int not_options_k = not_options_i;

				for (k = i + 1; k < battle_num; ++k) {
					if (battle_ants[k].player != 'a' || battle_ants[k].flags & 24) {
						my_option_k = 0;
						++not_options_k;
					}

					int l;

					for (l = 0; l < 5; ++l) {
						if (battle_ants[k].flags & 24 && l != battle_ants[k].dir)
							continue;


						int l_offset = battle_ants[k].t_offset[l]; // dirs[l] (battle_ants[k].offset, Info);

						if (battle_ants[i].player == battle_ants[k].player) {
							if (j_offset == l_offset && my_option_i && my_option_k) {

								int subsection_k = option_num;
								int subsection_i = option_num;
								int m;

								for (m = 0; m < k - not_options_k; ++m)
									subsection_k /= 5;

								for (m = 0; m < i - not_options_i; ++m)
									subsection_i /= 5;

								for (m = (subsection_i/5)*j; m < option_num; m += subsection_i) {
									int n;

									for (n = (subsection_k/5)*l; n < (subsection_i/5); n += subsection_k) {
										int o;

										for (o = 0; o < subsection_k/5; ++o) {
											scores[m + n + o] = LONG_MIN/2 - 1;
										}
									}
								}
							}
							else if (j_offset == l_offset) {
								if (my_option_i) {
									int subsection_i = option_num;
									int m;

									for (m = 0; m < i - not_options_i; ++m)
										subsection_i /= 5;

									for (m = (subsection_i/5)*j; m < option_num; m += subsection_i) {
										int n;

										for (n = 0; n < (subsection_i/5); ++n)
											scores[n + m] = LONG_MIN/2 - 1;
									}
								}
								else if (my_option_k) {
									int subsection_k = option_num;
									int m;

									for (m = 0; m < k - not_options_k; ++m)
										subsection_k /= 5;

									for (m = (subsection_k/5)*l; m < option_num; m += subsection_k) {
										int n;

										for (n = 0; n < (subsection_k/5); ++n)
											scores[n + m] = LONG_MIN/2 - 1;
									}
								}
							}
						}
						else if (in_radius(j_offset, l_offset, Info->attackradius_sq, Info)) {
							attack_lookup[i][j][k][l] = 1;
							attack_lookup[k][l][i][j] = 1;
						}
					}
				}
			}
		}

		//	So, where have we arrived?
		//
		//	So far, we've selected some ants that can do battle, pruned them down to
		//	some ants that are likely to do battle or are considered important, cached
		//	some things, optimized some things, managed a whole bunch of memory and
		//	wrote a whole bunch of C.
		//
		//	Now it's time do a battle.
		//
		//	But first, we need something to base our battles on. The following array,
		//	atply named "good_or_bad", determines if a result is good or bad, and
		//	what value that result should be awarded. The first box is 0 if an ant
		//	lives, and 1 if it dies. The second box is 0 if the ant is mine, and
		//	1 if the ant is an enemy ant. You'll notice that the first two options
		//	aren't used much. They were set to 0 because they appeared to be
		//	sub-optimal, but are perfectly functional.
		//
		//	Obviously, different situations in the game need battles resolved in
		//	different ways, so some magic heuristics are computed, some fairies are
		//	summoned, and our values are initialized.

		long i;

		memset(best_dirs, -1, battle_num*sizeof(int));

		int good_or_bad[2][2];
		int max_score = 0;

		int kill_magnitude = ((int) ( ( ((float) Game->enemy_count) / (((float) Game->my_count*my_group)*DOMINANT_PERCENT*PERCENT_CAPTURED*PERCENT_CAPTURED) ) )) + 15;

		if (protect_hive && my_num >= enemy_num) {
			good_or_bad[0][0] = 0;
			good_or_bad[0][1] = 0;
			good_or_bad[1][0] = 20;
			good_or_bad[1][1] = -5;
			max_score = 20;
		}
		else if (Game->my_count >= Game->enemy_count) {
			if ((enemy_hive_dist_sq < Info->viewradius_sq && my_num > enemy_num)) {
				good_or_bad[0][0] = 0;
				good_or_bad[0][1] = 0;
				good_or_bad[1][0] = 20;
				good_or_bad[1][1] = -5;
				max_score = 20;
			}
			else {
				good_or_bad[0][0] = 0;
				good_or_bad[0][1] = 0;
				good_or_bad[1][0] = 10;
				good_or_bad[1][1] = -kill_magnitude;
				max_score = kill_magnitude;
			}
		}
		else {
			good_or_bad[0][0] = 0;
			good_or_bad[0][1] = 0;
			good_or_bad[1][0] = 10;
			good_or_bad[1][1] = -kill_magnitude;
			max_score = kill_magnitude;
		}

		if (PERCENT_CAPTURED > 0.9 && Game->my_count > Game->enemy_count*4) {
			good_or_bad[1][0] = 500;
			max_score = 0;
		}

		int temp_cycle = (int) pow(5, battle_num - fixed_num);
		int timeout = 0;

		int no_dec = kill_magnitude/2;

		if (no_dec <= 0)
			no_dec = 1;

		long decrement_score = ((int) pow(5, MAX_GROUP_SIZE)); // value to decrement a score when losing more than killed

		int conflict_occured = 0;


		//	Here comes the all important loop of death. Inside this loop,
		//	the battle state is iterated and scores are calculated
		//	based on a particular position. This is the most computationally
		//	expensive portion of the entire program.


		for (i = 0; 1 + 1 == 2; ++i) {
			int skipped_positions;

			skipped_positions = iterate_battles(battle_ants, battle_num, pow_index_5, Info);

			if (i > 625 && i % 625 == 42) {
				double time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));

				if (time_spent > TIME_LIMIT*0.8) {
					fprintf(stderr, " {broke %g} ", TIME_LIMIT*0.8);
					timeout = 1;
					break;
				}
			}

			if (i > 0) {
				if (skipped_positions == -1)
					break;
			}


			int score_id = 0;
			int my_temp = my_num - my_fixed_num;

			for (j = 0; j < battle_num; ++j) {
				if (battle_ants[j].player != 'a' || battle_ants[j].flags & 8)
					continue;

				--my_temp;
				score_id += pow_index_5[my_temp]*battle_ants[j].dir;
			}

			//	If we have an absurdly low negative score, we assume it's not worth
			//	pursuing further.

			if (scores[score_id] < ((long) -(decrement_score/2))) {
				--scores[score_id];
				continue;
			}

			resolve_battles_pwr(battle_ants, battle_num, (int *) attack_lookup, Info);

			int new_score = 0;

			int my_dead = 0;
			int enemy_dead = 0;

			for (j = 0; j < battle_num; ++j) {
				if (battle_ants[j].player == 'a' && battle_ants[j].flags & 8)
					continue;

				int is_dead = ((battle_ants[j].flags & 2) > 0);
				int is_mine = ((battle_ants[j].player == 'a') > 0);

				if (is_dead) {
					if (is_mine)
						++my_dead;
					else
						++enemy_dead;

					conflict_occured = 1;
				}
				else {
					if (relevent_hive_num > 0 && is_mine) {
						int k;

						for (k = 0; k < relevent_hive_num; ++k) {
							if (relevent_hives[k] == battle_ants[j].t_offset[battle_ants[j].dir])
								new_score += decrement_score;
						}
					}

					if (nearby_food > 0) {
						int k;

						for (k = 0; k < nearby_food; ++k) {
							if (in_radius(relevent_food[k][0], battle_ants[j].t_offset[battle_ants[j].dir], Info->spawnradius_sq, Info)) {
								if (is_mine)
									new_score += relevent_food[k][2];
								else
									new_score += relevent_food[k][3];
							}
						}
					}
				}

				new_score += good_or_bad[is_dead][is_mine];

				battle_ants[j].flags &= ~2;
			}

			if (my_dead > enemy_dead && no_dec > enemy_dead)
				new_score -= decrement_score;


			scores[score_id] += new_score;
			++tests[score_id];
		}

		if (!conflict_occured)
			continue;

		for (i = 0; i < option_num; ++i) {
			if (tests[i] > 0)
				scores[i] /= tests[i];
			else
				scores[i] = LONG_MIN;
		}


		int final_configuration = -1;

		long top_score = LONG_MIN/2;

		for (i = 0; i < option_num; ++i) {
			if (scores[i] > top_score) {
				top_score = scores[i];
				final_configuration = i;
			}
			else if (scores[i] == top_score) {
				final_configuration = i;
			}
		}

		//	Finally! We have resolved all the battles. The wars have ended.
		//	Something something peace at last.
		//
		//	Sometimes, however, an ants position on the battlefield turns
		//	out to not really be that important. Specifically, the final score
		//	may not be any different if a specific ant moves East or West,
		//	and we want to free that ant from his fighting obligations.

		//	That is what this next section does. It's a convoluted and confusing
		//	section; I'm not entirely convinced that it works correctly,
		//	but at the very least it works somewhat correctly some of the
		//	time.



		int tmp_final_configuration = final_configuration;

		for (i = battle_num - 1; i >= 0; --i) {
			if (battle_ants[i].player != 'a' || battle_ants[i].flags & 8)
				continue;

			best_dirs[i] = final_configuration % 5;
			final_configuration /= 5;
		}

		final_configuration = tmp_final_configuration;

		int is_relevant[battle_num];

		for (i = 0; i < battle_num; ++i)
			is_relevant[i] = 1;

		int irrelevent_ants = 0;

		int enemies = 0;

		for (i = 0; i < battle_num; ++i) {
			int index = battle_num - 1 - i;

			if (battle_ants[index].player != 'a' || battle_ants[index].flags & 8) {
				++enemies;
				continue;
			}

			int rel_i = i - enemies;

			int collisions = 5;
			int collision_dir[5][2];

			for (j = 0; j < 5; ++j) {
				collision_dir[j][0] = 1;
				collision_dir[j][1] = 0;
			}

			int senerios_to_test = (int) pow(5, irrelevent_ants);
			int tests_done[battle_num];
			int pre_test_config;

			for (j = 0; j < battle_num; ++j) {
				tests_done[j] = 4;
			}

			//	If you really want to know what we're doing in here, we're basically
			//	running each ant through a bunch of senerios and declaring it "relevent"
			//	or "irrelevent"; or more specifically, we declare certain directions "relevent"
			//	and certain directions "irrelevent" for certain ants. In order for a
			//	direction to be considered "relevent", all possibilities resulting from
			//	movements of that ant to that direction and the possibilities of other
			//	ants who have been released from duty (found "irrelevent") need to result
			//	in the same top score.
			//
			//	If you're confused, don't worry, I wrote it and I am too.

			for (j = 0; 42; ++j) {


				if (j > 625 && j % 625 == 42) {
					double time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));

					if (time_spent > TIME_LIMIT*0.8) {
						fprintf(stderr, " {broke %g} ", TIME_LIMIT*0.8);
						timeout = 1;
						break;
					}
				}

				int k;


				pre_test_config = 0;
				int my_temp = my_num - my_fixed_num;
				int did_increment = 0;


				for (k = 0; k < battle_num; ++k) {
					if (battle_ants[k].player != 'a' || battle_ants[k].flags & 8)
						continue;

					int test_dir;

					if (is_relevant[k] == 0) {
						if (!did_increment) {
							if (tests_done[k] < 4) {
								++tests_done[k];
								test_dir = tests_done[k];
								did_increment = 1;
							}
							else {
								tests_done[k] = 0;
								test_dir = tests_done[k];
							}
						}
						else
							test_dir = tests_done[k];
					}
					else
						test_dir = best_dirs[k];


					--my_temp;
					pre_test_config += pow_index_5[my_temp]*test_dir;
				}

				for (k = 0; k < 5; ++k) {
					int test_config = pre_test_config + (k - best_dirs[index])*((int) pow(5, rel_i));

					if (scores[test_config] != scores[pre_test_config] || tests[test_config] != tests[pre_test_config]) {
						if (collision_dir[k][0]) {
							collision_dir[k][0] = 0;
							--collisions;
						}
					}
				}

				if (j > 0 && !did_increment)
					break;

			}

			if (timeout)
				break;

			if (collisions > 1) {

				for (j = 0; j < 5; ++j) {
					if (!collision_dir[j][0]) {
						sd_pair[battle_ants[index].id].ignore[j] = 1;
					}
				}

				is_relevant[index] = 0;
				++irrelevent_ants;

				//	By setting the priority to 999, we indicate that although we want
				//	this ant to be released from duty, we don't want it doing any
				//	frivilous tasks (tasks with a priority of less than 999). That is,
				//	if it would be more useful to stick around for the battle, do so,
				//	but try to find something more productive to do first.

				sd_pair[battle_ants[index].id].priority = 999;

			}
		}

		//	Now we just copy all the moves into our move storage array (sd_pair), and
		//	loop around again for another iteration of battle resolution. Phew!

		for (i = 0; i < battle_num; ++i) {
			int id = battle_ants[i].id;

			if (battle_ants[i].player != 'a' || battle_ants[i].flags & 8 || sd_pair[id].id != -1 || best_dirs[i] == -1) {
				continue;
			}

			if (!is_relevant[i]) {
				if (enemy_num >= my_num)
					sd_pair[id].type = 1;
				sd_pair[id].priority = 999;
				continue;
			}

			int dest_offset = dirs[best_dirs[i]] (battle_ants[i].offset, Info);

			int dest_row = dest_offset / Info->cols;
			int dest_col = dest_offset % Info->cols;

			sd_pair[id].id = id;
			sd_pair[id].row = dest_row;
			sd_pair[id].col = dest_col;
			sd_pair[id].suggest = get_letter(best_dirs[i]);
			sd_pair[id].priority = 1001;
			sd_pair[id].dist = 0;

			if (enemy_num > my_num)
				sd_pair[id].type = 1;

			for (j = 0; j < 5; ++j) {
				if (j == best_dirs[i])
					continue;

				sd_pair[id].ignore[j] = 1;
			}

			if (collision_ants[id].player == 'a') {
				collision_ants[id].flags |= 8;
				collision_ants[id].dir = get_num(sd_pair[id].suggest);
			}

			int true_id = Game->my_ants[id].id;

			++*complete;

			for (j = 0; j < total_ants; ++j) {
				if (collision_ants[j].player != 'a' || collision_ants[j].id == battle_ants[i].id)
					continue;

				int k;

				for (k = 0; k < 4; ++k) {
					if (collision_ants[j].t_offset[k] == dest_offset) {
						collision_ants[j].ignore_position[k] = 1;
					}
				}
			}

			for (j = 0; j < Game->my_count; ++j) {
				if (j == battle_ants[i].id)
					continue;

				int k;

				for (k = 0; k < 4; ++k) {
					if (*(MOVE_LOOKUP + (Game->my_ants[j].row*Info->cols + Game->my_ants[j].col)*4 + k) == dest_offset) {
						sd_pair[j].ignore[k] = 1;
					}
				}

				if (Game->my_ants[j].row*Info->cols + Game->my_ants[j].col == dest_offset) {
					sd_pair[j].ignore[4] = 1;
				}
			}
		}

		free(scores);
		free(tests);
	}
}
