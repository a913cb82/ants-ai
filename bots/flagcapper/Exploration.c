/*
	PATHFINDING AND EXPLORATION
	---------------------
	Basically anything that's not related to fighting code is found in
	here. So exploring, going for food, etc.

	check_path() -- returns a direction (N, E, S, W, -1 on error) by
					attempting to find a path between a source and a
					destination. [recursive]

	map_practical_distances() -- maps the practical distance from a given
								 square to all other squares within a given
								 depth

	increase_heat() -- used to create the PureHeatMap[], it basically
					   increases or decreases the value of the practical
					   area surrounding a given point, based on some rules
					   given to the function

	set_practical_area() -- sets a practical area of a certain depth to a
							given value.

	set_radial_area() -- sets a radial area of a certain radius to a given
						 value.

	do_spread() -- this function is responsible for finding the lowest
				   value of a nearby square on a given input map
				   (see the INFORMATIONAL_MAPS section for more details),
				   and returning the direction an ant should go to get to
				   that square. This is used heavily in exploration.

	assign_ants() -- assigns a destination from a set of destinations to
					 a given set of ants based on the distance to those
					 destinations and whether or not the ant can reach
					 them. A very similar process is used for finding
					 food; this function is typically used for rallying
					 ants to an enemy.

*/

char check_path(int current, int goal, int radius, char *moves, int *dir, int flags,
				int depth, int max_depth, char *map, int *depth_map, struct game_info *Info) {

	char current_obj = map[current];

	if (depth_map[current] <= depth
		|| (current_obj == '%' && (!(flags & 2) || depth == 1))
		|| current_obj == '\x01'
		|| (depth == 1 && current_obj == '*')
		|| Visited[current] == -1
		|| (flags & 1 && depth > 0 && current_obj == 'a')
		)
		return -1;

	if (in_radius(current, goal, radius, Info)) {
		if (depth_map[current] > depth)
			depth_map[current] = depth;
		return depth;
	}

	if (depth > max_depth)
		return -1;

	depth_map[current] = depth;

	int i;

	int path[5];
	for (i = 0; i < 5; ++i)
		path[i] = -1;

	i = 0;

	while (dir[i] != -1) {
		if (moves != 0) {
			moves[depth] = dir[i];
		}

		path[i] = check_path(*(MOVE_LOOKUP + current*4 + dir[i]), goal, radius, moves, dir, flags, depth + 1, max_depth, map, depth_map, Info);

		++i;
	}

	int shortest_dist = INT_MAX;
	int chosen_dir = -1;

	for (i = 0; i < 5; ++i) {
		if (path[i] == -1)
			continue;

		if (path[i] < shortest_dist) {
			chosen_dir = i;
			shortest_dist = path[i];
		}
	}


	if (chosen_dir != -1) {
		if (depth > 0)
			return path[chosen_dir];

		return get_letter(dir[chosen_dir]);
	}

	if (depth > 0)
		return -1;

	return 0;
}

void map_practical_distances(int current, int depth, int *map, struct game_info *Info) {

	if (Info->map[current] == '%' || Visited[current] == -1 || depth <= map[current])
		return;

	map[current] = depth;

	if (depth - 1 <= 0)
		return;

	map_practical_distances(*(MOVE_LOOKUP + current*4), depth - 1, map, Info);
	map_practical_distances(*(MOVE_LOOKUP + current*4 + 1), depth - 1, map, Info);
	map_practical_distances(*(MOVE_LOOKUP + current*4 + 2), depth - 1, map, Info);
	map_practical_distances(*(MOVE_LOOKUP + current*4 + 3), depth - 1, map, Info);
}

void increase_heat(int offset, float base, long step, int radius, long *map, int flags, struct game_info *Info) {

	int i;
	int map_len = Info->rows*Info->cols;
	int *dist_map = malloc(sizeof(int)*map_len);

	if (flags & 1) {
		memset(dist_map, 0, sizeof(int)*map_len);
	}
	else {
		for (i = 0; i < map_len; ++i) {
			dist_map[i] = INT_MIN;
		}
	}



	int height = radius*2;
	long heat_cache[height];

	if (height > Info->rows) {
		height = Info->rows;
		radius = height/2;
	}
	if (height > Info->cols) {
		height = Info->cols;
		radius = height/2;
	}


	map_practical_distances(offset, radius - 1, dist_map, Info);

	if (flags & 0x2) {
		for (i = 0; i < radius; ++i) {
			heat_cache[radius - i - 1] = (long) (pow(base, -i)*((double) step)); // (step - base*i);
			if (heat_cache[radius - i - 1] < 0)
				heat_cache[radius - i - 1] = 0;

//			fprintf(stderr, "%li, ", heat_cache[height - i - 1]);
		}
	}
	else {
		for (i = 0; i < radius; ++i) {
			heat_cache[i] = (long) ((pow(base, i))*step);
		}
	}


	int tmp_offset = offset;

	for (i = 0; i < radius; ++i)
		tmp_offset = North(tmp_offset, Info);

	for (i = 0; i < height; ++i) {

		int y = radius - i;
		int x = (int) sqrt(radius*radius - y*y);

		int j = 0;
		int line_len = x*2 + 1;

		int tmp2_offset = tmp_offset;

		for (j = 0; j < x; ++j)
			tmp2_offset = West(tmp2_offset, Info);

		int max = radius;

		for (j = 0; j < line_len; ++j) {

			if (dist_map[tmp2_offset] == INT_MIN) {
				tmp2_offset = East(tmp2_offset, Info);
				continue;
			}

			int index = dist_map[tmp2_offset];

			if (index <= radius) {
				map[tmp2_offset] += heat_cache[index];
			}

			tmp2_offset = East(tmp2_offset, Info);
		}

		tmp_offset = South(tmp_offset, Info);
	}


	free(dist_map);
}

void set_practical_area(int offset, int radius_sq, int value, long *map, int *dist_map, struct game_info *Info) {

	int map_len = Info->rows*Info->cols;

	map_practical_distances(offset, ((int) sqrt(radius_sq) + 1)*2, dist_map, Info);


	int i;
	int tmp_offset = offset;
	int radius = ((int) sqrt(radius_sq)) + 1;

	for (i = 0; i < radius; ++i) {
		tmp_offset = North(tmp_offset, Info);
		tmp_offset = West(tmp_offset, Info);
	}

	for (i = 0; i < radius*2; ++i) {
		int y = radius - i;

		int j;

		int tmp_offset2 = tmp_offset;

		for (j = 0; j < radius*2; ++j) {
			int x = j - radius;

			if (x*x + y*y <= radius_sq && dist_map[tmp_offset2] != -1) {
				map[tmp_offset2] = value;
			}

			tmp_offset2 = East(tmp_offset2, Info);
		}

		tmp_offset = South(tmp_offset, Info);
	}
}

void set_radial_area(int offset, int radius_sq, int value, long *map, struct game_info *Info) {

	int i;
	int tmp_offset = offset;
	int radius = ((int) sqrt(radius_sq)) + 1;

	for (i = 0; i < radius; ++i) {
		tmp_offset = North(tmp_offset, Info);
		tmp_offset = West(tmp_offset, Info);
	}

	for (i = 0; i < radius*2; ++i) {
		int y = radius - i;

		int j;

		int tmp_offset2 = tmp_offset;

		for (j = 0; j < radius*2; ++j) {
			int x = j - radius;

			if (x*x + y*y <= radius_sq) {
				map[tmp_offset2] = value;
			}

			tmp_offset2 = East(tmp_offset2, Info);
		}

		tmp_offset = South(tmp_offset, Info);
	}
}

int do_spread(int offset, int depth, int max_depth, int *dir, int dir_num,
			  int *ignore, int *depth_map, long *map, long *Visited, int flags, struct game_info *Info) {

	int i;

	char current = Info->map[offset];

	int map_index = offset;

	if (depth_map[offset] <= depth || ((flags & 1) && Visited[offset] == -1) || current == '%' || (depth > 0 && Info->map[offset] == 'a')) {
		return -1;
	}

	depth_map[offset] = depth;

	int next_map_indexes[dir_num + 1];
	int next_map_depths[dir_num + 1];

	next_map_indexes[dir_num] = offset;
	next_map_depths[dir_num] = depth;

	if (depth == 0) {
		i = 0;

		while (dir[i] != -1) {
			if (ignore[i] != 1) {
				next_map_indexes[i] = do_spread(*(MOVE_LOOKUP + offset*4 + dir[i]), depth + 1, max_depth, dir, dir_num, ignore, depth_map, map, Visited, flags, Info);
				if (next_map_indexes[i] > -1)
					next_map_depths[i] = depth_map[next_map_indexes[i]];
			}
			else {
				next_map_indexes[i] = -1;
				next_map_depths[i] = INT_MAX;
			}

			++i;
		}
	}
	else if (depth <= max_depth) {

		for (i = 0; i < dir_num; ++i) {
			next_map_indexes[i] = do_spread(*(MOVE_LOOKUP + offset*4 + dir[i]), depth + 1, max_depth, dir, dir_num, ignore, depth_map, map, Visited, flags, Info);
			if (next_map_indexes[i] > -1)
				next_map_depths[i] = depth_map[next_map_indexes[i]];
		}
	}
	else
		return map_index;

	long min = LONG_MAX;
	int chosen_dir = -1;

	for (i = 0; i < dir_num + 1; ++i) {
		if (next_map_indexes[i] == -1)
			continue;

		if (map[next_map_indexes[i]] < min) {
			chosen_dir = i;
			min = map[next_map_indexes[i]];
		}
		else if (map[next_map_indexes[i]] == min) {
			if (i < dir_num && chosen_dir != -1) {
				if (next_map_indexes[i] == next_map_indexes[chosen_dir]) {
					if (next_map_depths[i] < next_map_depths[chosen_dir]) {
						chosen_dir = i;
						min = map[next_map_indexes[i]];
					}
					else if (next_map_depths[i] == next_map_depths[chosen_dir]) {
						int move1_offset = *(MOVE_LOOKUP + offset*4 + dir[chosen_dir]);
						int move2_offset = *(MOVE_LOOKUP + offset*4 + dir[i]);

						int dest = next_map_indexes[i];

						int dist1 = euc_distance_sq(move1_offset / Info->cols, move1_offset % Info->cols, dest / Info->cols, dest % Info->cols, Info);
						int dist2 = euc_distance_sq(move2_offset / Info->cols, move2_offset % Info->cols, dest / Info->cols, dest % Info->cols, Info);

						if (dist2 < dist1) {
							chosen_dir = i;
							min = map[next_map_indexes[i]];
						}
					}
				}
				else {

					if (next_map_depths[i] < next_map_depths[chosen_dir]) {
						chosen_dir = i;
						min = map[next_map_indexes[i]];
					}
				}
			}
			else {
				chosen_dir = i;
				min = map[next_map_indexes[i]];
			}
		}
	}

	if (chosen_dir != -1) {
		if (depth == 0) {
			map_index = dir[chosen_dir];
			depth_map[0] = next_map_depths[chosen_dir];
			depth_map[1] = next_map_indexes[chosen_dir];
		}
		else
			map_index = next_map_indexes[chosen_dir];//dirs[chosen_dir].id;
	}
	else {
		map_index = -1;
	}

	return map_index;
}

void assign_ants(int *complete, int max_complete, struct sd_pair *sd_pair, int check_radius, void *data, int dataType_len, int data_len, int flags, int priority, struct game_info *Info, struct game_state *Game) {

	int i, j;

	struct my_ant leftovers[Game->my_count - *complete];
	memset(leftovers, -1, sizeof(struct my_ant)*(Game->my_count - *complete));
	int left_len = 0;

	for (i = 0; i < Game->my_count; ++i) {
		int not_gone = 0;

		if (sd_pair[i].id == -1 && sd_pair[i].priority != 999)
			not_gone = 1;

		if (not_gone) {
			leftovers[left_len].id = i;
			leftovers[left_len].row = Game->my_ants[i].row;
			leftovers[left_len].col = Game->my_ants[i].col;
			++left_len;
		}
	}


	int dec = (int) (log10((double) Game->my_count)/log10(5.0));

	int ant_indexD[left_len][data_len];
	memset(ant_indexD, 0, left_len*data_len*sizeof(int));

	for (i = 0; i < left_len; ++i) {
		for (j = 0; j < data_len; ++j) {
			int dest_row = *((int *) (data + j*dataType_len));
			int dest_col = *((int *) (data + j*dataType_len + sizeof(int)));
			if (dest_row == leftovers[i].row && dest_col == leftovers[i].col)
				ant_indexD[i][j] = -1;
			else
				ant_indexD[i][j] = distance(leftovers[i].row, leftovers[i].col, dest_row, dest_col, Info);
		}
	}
	i = 0;

	double time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));

	int consecutive_failures = 0;

	while (i < data_len && time_spent < TIME_LIMIT*0.82) {

		if (*complete >= max_complete)
			break;

		if (consecutive_failures > 5)
			break;

		time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));

		int small_dist = 22 - dec;
		long heat_difference = LONG_MIN;

		int source = -1;
		int dest = -1;

		if (flags & 4) {
			for (j = 0; j < left_len; ++j) {
				int k;

				for (k = 0; k < data_len; ++k) {

					unsigned int test = (unsigned int) ant_indexD[j][k];

					if (test >= small_dist)
						continue;

					int dest_row = *((int *) (data + k*dataType_len));
					int dest_col = *((int *) (data + k*dataType_len + sizeof(int)));

					long test2 =   BaseMap[leftovers[j].row*Info->cols + leftovers[j].col]
							     - BaseMap[dest_row*Info->cols + dest_col];

					if (test2 < 0)
						continue;


					small_dist = test;

					source = j;
					dest = k;
				}
			}
		}

		if (source == -1) {
			for (j = 0; j < left_len; ++j) {
				int k;
				for (k = 0; k < data_len; ++k) {
					unsigned int test = (unsigned int) ant_indexD[j][k];

					if (test < small_dist) {
						small_dist = test;

						source = j;
						dest = k;
					}
				}
			}
		}

		if (source != -1) {

			int id = leftovers[source].id;

			int dest_row = *((int *) (data + dest*dataType_len));
			int dest_col = *((int *) (data + dest*dataType_len + sizeof(int)));

			int source_offset = leftovers[source].row*Info->cols + leftovers[source].col;

			int dirs[5];
			int max_depth = 0;

			get_dirs(ant_indexD[source][dest], leftovers[source].row, dest_row,
					 leftovers[source].col, dest_col, sd_pair[id].ignore, &max_depth, dirs, Info);

			int dest_offset = dest_row*Info->cols + dest_col;

			int NTest = North(source_offset, Info);
			int ETest = East(source_offset, Info);
			int STest = South(source_offset, Info);
			int WTest = West(source_offset, Info);

			char original_map[4] = {
				Info->map[NTest],
				Info->map[ETest],
				Info->map[STest],
				Info->map[WTest]
			};

			if (sd_pair[id].ignore[0] == 1)
				Info->map[NTest] = '\x01';

			if (sd_pair[id].ignore[1] == 1) {
				Info->map[ETest] = '\x01';
			}

			if (sd_pair[id].ignore[2] == 1)
				Info->map[STest] = '\x01';

			if (sd_pair[id].ignore[3] == 1)
				Info->map[WTest] = '\x01';

			int map_len = Info->rows*Info->cols;

			int depth_map[map_len];
			for (j = 0; j < map_len; ++j)
				depth_map[j] = INT_MAX;

			char can_move;

			if (flags & 2)
				can_move = check_path(source_offset, dest_offset, check_radius, (char *) 0, dirs, 0, 0, small_dist - ((int) sqrt(check_radius)) + 1, Info->map, depth_map, Info);
			else
				can_move = check_path(source_offset, dest_offset, check_radius, (char *) 0, dirs, 0x1, 0, small_dist - ((int) sqrt(check_radius)) + 1, Info->map, depth_map, Info);

			if (!can_move) {
				for (j = 0; j < map_len; ++j)
					depth_map[j] = INT_MAX;

				for (j = 0; j < 4; ++j) {
					dirs[j] = j;
				}
				dirs[4] = -1;

				can_move = check_path(source_offset, dest_offset, check_radius, (char *) 0, dirs, 0x1, 0,
									  22 - dec, Info->map, depth_map, Info);

				if (can_move && ant_indexD[source][dest] < depth_map[dest_offset] + 1) {
					ant_indexD[source][dest] = depth_map[dest_offset] + 1;
					Info->map[NTest] = original_map[0];
					Info->map[ETest] = original_map[1];
					Info->map[STest] = original_map[2];
					Info->map[WTest] = original_map[3];
					goto redo_find;
				}
			}

			Info->map[NTest] = original_map[0];
			Info->map[ETest] = original_map[1];
			Info->map[STest] = original_map[2];
			Info->map[WTest] = original_map[3];

			if (can_move) {

				memset(ant_indexD[source], -1, data_len*sizeof(int));

				for (j = 0; j < left_len; ++j)
					ant_indexD[j][dest] = -1;

				int true_id = Game->my_ants[id].id;

				sd_pair[id].id = leftovers[source].id;
				sd_pair[id].row = dest_row;
				sd_pair[id].col = dest_col;
				sd_pair[id].suggest = can_move;

				if (priority == -1) {
					if (sd_pair[id].priority < small_dist*2)
						sd_pair[id].priority = small_dist*2;
				}
				else {
					if (sd_pair[id].priority < priority)
						sd_pair[id].priority = priority;
				}

				sd_pair[id].dist = small_dist;
				sd_pair[id].type = -1;


				int (*func) (int offset, struct game_info *Info) = get_func(can_move);
				int new_square = func(source_offset, Info);

				for (j = 0; j < Game->my_count; ++j) {
					if (j == leftovers[source].id)
						continue;

					int k;

					for (k = 0; k < 4; ++k) {
						if (*(MOVE_LOOKUP + (Game->my_ants[j].row*Info->cols + Game->my_ants[j].col)*4 + k) == new_square) {
							sd_pair[j].ignore[k] = 1;
						}
					}

					if (Game->my_ants[j].row*Info->cols + Game->my_ants[j].col == new_square) {
						sd_pair[j].ignore[4] = 1;
					}
				}

				if (flags & 1)
					sd_pair[id].type = 1;

				consecutive_failures = 0;

				++*complete;
				++i;
			}
			else {
				ant_indexD[source][dest] = -1;
				++consecutive_failures;
			}
		}
		else
			break;

		redo_find:
			continue;
	}
}
