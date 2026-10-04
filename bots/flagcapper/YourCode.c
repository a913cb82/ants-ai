#include "ants.h"

#include <time.h>
#include <limits.h>
#include <float.h>

#define PTRCAST long

#define UP -Info->cols
#define DOWN Info->cols
#define LEFT -1
#define RIGHT 1



/*

	INTRODUCTION
	------------
	Hello there! This bot is an entry for the Ants AI Challenge
	of Fall 2011. It was created by me, FlagCapper, which is an online
	name I use for a variety of websites, games and activities. If you
	wish to read more about the bot and a more in depth analysis of my
	thought process, head on over to flagcapper.com, where you should
	find an article about this bot and some other things I've written.

	Enjoy!



	CONSTANTS AND STRUCTURES
	------------------------
	This section contains exactly what the name implies.
	Some important ones that may not be entirely self-explanatory:

	PERCENT_CAPTURED -- percent of the map currently in vision

	DOMINANT_PERCENT -- the percentage of enemy ants that are from the
						enemy player with the largest number of ants

	MAX_GROUP_SIZE -- the maximum amount of ants permitted in a single
					  iteration of battle resolution code. This can be
					  tweeked depending on your performance needs

	sd_pair -- source destination pair, used for storing information
			   about the destination of a particular ant (source)

	test_ant -- ant used for testing battle resolution


	The rest should be either self explainitory or are not that important.

*/

int CURRENT_TURN = 0;
int OPPONENT_NUM = 0;
double TIME_LIMIT = 1;
float ANT_DENSITY = 0;
float PERCENT_CAPTURED = 0;
float DOMINANT_PERCENT = 1;
float PERCENT_VISITED = 0;
clock_t INITIAL_CLOCK;
int LAST_HIVE_COUNT = 0;
int EXPLORE_REFINEMENT = 1;
int HEAT_RADIUS = 25;
int MAX_GROUP_SIZE = 11;

typedef struct sd_pair {
	int id;
	int row;
	int col;
	char suggest;
	char state;
	int priority;
	int dist;
	int ignore[5];
	int type;
} sd_pair;

typedef struct previous_info {
	int row;
	int col;
	int starting_turn;
} previous_info;

typedef struct dist_detail {
	int from;
	int to;
	int dist;
} dist_detail;

typedef struct test_ant {
	int id;
	int offset;
	int t_offset[5];
	char player;
	int flags;
	int depth;
	int dir;
	int ignore_battle[5];
	int ignore_position[5];
} test_ant;

typedef struct val_id_pair {
	int id;
	int val;
} val_id_pair;

int dist_compare(const void *arg1, const void *arg2) {
	return (*((val_id_pair *) arg1)).val - (*((val_id_pair *) arg2)).val;
}

int in_radius(int a, int b, int r_sq, struct game_info *Info) {
	int a_row = a / Info->cols;
	int a_col = a % Info->cols;
	int b_row = b / Info->cols;
	int b_col = b % Info->cols;

	if (euc_distance_sq(a_row, a_col, b_row, b_col, Info) <= r_sq)
		return 1;

	return 0;
}

/*
	INFORMATIONAL MAPS
	-----------------
	These are very important as they are used throughout the code.

	Note: the term "practical distance" is used to denote the actual, practical
		  minimum walking distance an ant would have to travel to reach a particular
		  destination.

	PushMap -- A distance map where a hive owned by the bot is given a very
			   large value and each square that is in vision is given that same
			   value minus the minimum practical (actual) distance to that
			   square. Ants will use this map to proceed away from hills by
			   searching for a square with the lowest value within a particular
			   range, which is why it is said that this map "pushes" ants away.

	BaseMap -- An outdated map that accomplishes the same function as the PushMap.
			   It is left in the code as a backup.

	PureHeatMap -- A map where all friendly ants are given a value, and the
				   practical distance from that ant is given a value of the initial
				   value divided by 2^(practical distance). The cumulative sum of
				   all these values for all friendly ants is recorded here.

	HeatMap -- A map created by adding the BaseMap and HeatMap together. Like the
			   BaseMap, it is used only as a backup.

	LastVisitedMap -- gives a negative value or 0 that indicates how many turns ago
					  that square was last seen. A value larger than turnlimit will
					  be given for squares that have never been seen.

	Visited -- Marks squares that have been visited (seen) with a 1, while squares
			   that never been seen are given a -1

	MOVE_LOOKUP -- An array that contains cached results for each square on the map
				   that tell the user the result of calling North(), East(), South(),
				   and West() on that square. This is used for optimization.
*/


long *PushMap = 0;
long *BaseMap = 0;
long *PureHeatMap = 0;
long *HeatMap = 0;
long *LastVisitedMap = 0;
long *Visited = 0;
int *MOVE_LOOKUP = 0;

/*
	DIRECTIONS
	----------
	In this bot, the (row, col) representation of position is often discarded
	in favour of the value of the offset in a one-dimensional array that
	represents the map. So for example, in a 20x20 map, the position (2, 3)
	would simply be 20*2 + 3 or 43.

	In order to move around the map, the bot calls the functions North(),
	East(), South(), and West(). Actually, it often calls the indexed versions
	(iNorth(), iEast()... etc.), or uses the MOVE_LOOKUP map directly. The
	MOVE_LOOKUP map is initialized with these functions.

	get_func(), get_num() and get_letter() translate the various representations
	of a direction into functional, numerical (0 - 4, where 4 is no movement),
	and the charceters N, E, S, W (as it is represented in the bot output).

	get_dirs() initializes an array of directions containing the only directions
	needed to travel from a source to a destination assuming there is no
	blockages.

*/


int North(int offset, struct game_info *Info) {
	int row = offset / Info->cols;

	if (row != 0)
		return offset + UP;

	return offset + (Info->rows - 1)*Info->cols;
}

int East(int offset, struct game_info *Info) {
	int col = offset % Info->cols;

	if (col != Info->cols - 1)
		return offset + RIGHT;

	return offset - (Info->cols - 1);
}

int South(int offset, struct game_info *Info) {
	int row = offset / Info->cols;

	if (row != Info->rows - 1)
		return offset + DOWN;

	return offset - (Info->rows - 1)*Info->cols;
}

int West(int offset, struct game_info *Info) {
	int col = offset % Info->cols;

	if (col != 0)
		return offset + LEFT;

	return offset + Info->cols - 1;
}

int Stop(int offset, struct game_info *Info) {
	return offset;
}

inline int iNorth(int offset) {
	return *(MOVE_LOOKUP + offset*4);
}

inline int iEast(int offset) {
	return *(MOVE_LOOKUP + offset*4 + 1);
}

inline int iSouth(int offset) {
	return *(MOVE_LOOKUP + offset*4 + 2);
}

inline int iWest(int offset) {
	return *(MOVE_LOOKUP + offset*4 + 3);
}

inline int iStop(int offset) {
	return offset;
}

void *get_func(char dir) {
	switch(dir) {
		case 'N':
			return North;
		case 'E':
			return East;
		case 'S':
			return South;
		case 'W':
			return West;
		default:
			return Stop;
	}
}

int get_num(char dir) {
	switch(dir) {
		case 'N':
			return 0;
		case 'E':
			return 1;
		case 'S':
			return 2;
		case 'W':
			return 3;
		case 0:
			return 4;
		case 1:
			return 4;
		default:
			return -1;
	}
}

char get_letter(int dir) {
	switch (dir) {
		case 0:
			return 'N';
		case 1:
			return 'E';
		case 2:
			return 'S';
		case 3:
			return 'W';
		case 4:
			return 1;
		default:
			return -1;
	}
}

void get_dirs(int dist, int row1, int row2, int col1, int col2, int *ignore, int *max_depth, int *dirs, struct game_info *Info) {

	int dindex = -1;
	*max_depth = 0;

	int vert_diff = abs(row1 - row2);
	int horz_diff = abs(col1 - col2);

	int vert_diff2 = Info->rows - vert_diff;
	int horz_diff2 = Info->cols - horz_diff;

	int small_vert = vert_diff;
	int small_horz = horz_diff;

	if (vert_diff2 < vert_diff)
		small_vert = vert_diff2;

	if (horz_diff2 < horz_diff)
		small_horz = horz_diff2;

	int jump = 0;

	if (small_horz > small_vert)
		jump = 1;

	if (jump)
		goto LeftToRight;


	UpAndDown:

	if (vert_diff2 < vert_diff) {
		if (row1 > row2)
			dirs[++dindex] = 2;

		else if (row1 < row2)
			dirs[++dindex] = 0;

		*max_depth += dist;
	}
	else if (row1 > row2) {
		*max_depth += vert_diff;
		dirs[++dindex] = 0;
	}
	else if (row1 < row2) {
		*max_depth -= vert_diff;
		dirs[++dindex] = 2;
	}

	if (jump)
		goto EndJump;


	LeftToRight:

	if (horz_diff2 < horz_diff) {
		if (col1 > col2)
			dirs[++dindex] = 1;

		else if (col1 < col2)
			dirs[++dindex] = 3;

		*max_depth += dist;
	}
	else if (col1 > col2) {
		*max_depth += horz_diff;
		dirs[++dindex] = 3;
	}
	else if (col1 < col2) {
		*max_depth -= horz_diff;
		dirs[++dindex] = 1;
	}

	if (jump)
		goto UpAndDown;


	EndJump:

	++*max_depth;
	dirs[++dindex] = -1;
}

/*
	STATS AND VISION
	----------------
	Just some functions that get vision and initialize some global variables.
	No big deal.

*/


enum STAT_TYPE {
	STAT_DENSITY,
	STAT_PERCENT_VISIBLE,
	STAT_PERCENT_VISITED
} stat_type;

void set_radial_area(int, int, int, long *, struct game_info *);
void set_practical_area(int, int, int, long *, int *, struct game_info *);



void get_practical_vision(long *map, struct game_info *Info) {
	int map_len = Info->rows*Info->cols;
	int i;

	int test_map[map_len];
	memset(test_map, -1, sizeof(int)*map_len);

	for (i = 0; i < map_len; ++i) {
		if (Info->map[i] == 'a') {
			set_practical_area(i, Info->viewradius_sq, 1, map, test_map, Info);
		}
	}
}

void get_vision(long *map, struct game_info *Info) {
	int map_len = Info->rows*Info->cols;
	int i;

	for (i = 0; i < map_len; ++i) {
		if (Info->map[i] == 'a') {
			set_radial_area(i, Info->viewradius_sq, 1, map, Info);
		}
	}
}

void get_enemy_vision(long *map, struct game_info *Info) {
	int map_len = Info->rows*Info->cols;
	int i;

	for (i = 0; i < map_len; ++i) {
		if (Info->map[i] > 'a' && Info->map[i] <= 'z') {
			set_radial_area(i, Info->viewradius_sq, 1, map, Info);
		}
	}
}

float get_stat(struct game_state *Game, struct game_info *Info, enum STAT_TYPE stat_type) {

	int vision_num = 0;
	int i;
	int map_len = Info->rows*Info->cols;


	if (stat_type == STAT_DENSITY) {

		for (i = 0; i < map_len; ++i) {
			if (Visited[i] != -1)
				++vision_num;
		}

		return (((float) Game->my_count)/((float) vision_num))*100.0;
	}
	if (stat_type == STAT_PERCENT_VISIBLE) {

		long *vision_map = malloc(map_len*sizeof(long));
		memset(vision_map, -1, map_len*sizeof(long));

		get_vision(vision_map, Info);

		for (i = 0; i < map_len; ++i)
			if (vision_map[i] != -1 && (stat_type == STAT_PERCENT_VISIBLE))
				++vision_num;

		free(vision_map);

		return ((float) vision_num)/((float) map_len);
	}
	if (stat_type == STAT_PERCENT_VISITED) {
		for (i = 0; i < map_len; ++i) {
			if (Visited[i] != -1)
				++vision_num;
		}

		return ((float) vision_num)/((float) map_len);
	}
}

#include "Exploration.c"
#include "BattleResolution.c"


void do_turn(struct game_state *Game, struct game_info *Info) {

	/*
		THE BOT (SECTION 0)
		-------
		The most exciting part of the code. The part that plays ants.

		But first, we have to do a bunch of boring stuff. The first
		section of unorganized statements allocates memory, initializes
		maps, prints debug information and sets timeout limits. If
		you enjoy boring things, this section of code is for you.
		Otherwise, scroll down to the next comment.

	*/


	TIME_LIMIT = ((double) Info->turntime)/(1000.0);

	int i, j;
	int map_len = Info->rows*Info->cols;

	char *unmodified_map = malloc(sizeof(char)*map_len);
	memcpy(unmodified_map, Info->map, sizeof(char)*map_len);

	for (i = 0; i < map_len; ++i)
		Info->map[i] &= ~0x80;



	++CURRENT_TURN;

	fprintf(stderr, "turn %i: ", CURRENT_TURN);
	fflush(stderr);

	clock_t previous_clock = clock();
	INITIAL_CLOCK = previous_clock;


	if (Visited == 0) {
		Visited = malloc(map_len*sizeof(long));
		memset(Visited, -1, map_len*sizeof(long));
	}

	get_vision(Visited, Info);


	long *vision_map = malloc(map_len*sizeof(long));
	memset(vision_map, -1, map_len*sizeof(long));

	get_vision(vision_map, Info);

	long *enemy_vision_map = malloc(map_len*sizeof(long));
	memset(enemy_vision_map, -1, map_len*sizeof(long));

	get_enemy_vision(enemy_vision_map, Info);


	ANT_DENSITY = get_stat(Game, Info, STAT_DENSITY);
	PERCENT_CAPTURED = get_stat(Game, Info, STAT_PERCENT_VISIBLE);
	PERCENT_VISITED = get_stat(Game, Info, STAT_PERCENT_VISITED);

	if (MOVE_LOOKUP == 0) {
		MOVE_LOOKUP = malloc(map_len*4*sizeof(int));

		for (i = 0; i < map_len; ++i) {
			*(MOVE_LOOKUP + i*4) = North(i, Info);
			*(MOVE_LOOKUP + i*4 + 1) = East(i, Info);
			*(MOVE_LOOKUP + i*4 + 2) = South(i, Info);
			*(MOVE_LOOKUP + i*4 + 3) = West(i, Info);
		}
	}

	if (HeatMap == 0) {
		HeatMap = malloc(Info->rows*Info->cols*sizeof(long));
		memset(HeatMap, 0, Info->rows*Info->cols*sizeof(long));
	}
	else {
		for (i = 0; i < map_len; ++i) {
			HeatMap[i] /= 32;
		}
	}

	if (PureHeatMap == 0) {
		PureHeatMap = malloc(Info->rows*Info->cols*sizeof(long));
		memset(PureHeatMap, 0, Info->rows*Info->cols*sizeof(long));
	}
	else {
		for (i = 0; i < map_len; ++i)
			PureHeatMap[i] = 0;
	}

	if (LastVisitedMap == 0) {
		LastVisitedMap = malloc(Info->rows*Info->cols*sizeof(long));
		memset(LastVisitedMap, 0, Info->rows*Info->cols*sizeof(long));
	}


	if (BaseMap == 0) {
		BaseMap = malloc(Info->rows*Info->cols*sizeof(long));
	}

	/*

		Well, I did say initializing maps is boring, but this is no
		oridinary map. This is the PushMap. This is the heart of
		exploration. The soul of the hivemind. Or... something like
		that.

		Basically, it's a map that sets the value of a square containing
		a friendly hive to INT_MAX/2, and sets all the squares around
		it in vision to (INT_MAX/2 - walking_distance). It is iteratively
		updated each turn to be more consistent with area that has
		been explored, and updated to not lead ants into dead ends when
		it discovers that it can no longer go any further in a particular
		direction.

		I suppose you could consider it an elaborate form of the bfs
		algorithmn, with a few addtions here and there to make it specific
		to ants, but considering I invented it myself without any real
		knowledge of how bfs works (I like to keep myself ignorant
		of major algorithmns for the challenge appeal, it's a personal
		thing), I'm rather proud of it.

	*/


	if (PushMap == 0) {

		/*

			If the PushMap has never been initialized before,
			initialize it.

		*/

		PushMap = malloc(Info->rows*Info->cols*sizeof(long));
		memset(PushMap, 0, map_len*sizeof(long));


		for (i = 0; i < Game->hive_count; ++i) {
			if (Game->hives[i].player != 'a')
				continue;

			int test_map[map_len];
			memset(test_map, 0, map_len*sizeof(int));

			map_practical_distances(Game->hives[i].row*Info->cols + Game->hives[i].col, INT_MAX/2, test_map, Info);

			for (j = 0; j < map_len; ++j) {
				if (test_map[j] > (int) PushMap[j])
					PushMap[j] = (long) test_map[j];
			}
		}
	}
	else {

		/*

			Try to update the map based on new information that has come into vision.

		*/

		int map_finalized = 0;

		while (!map_finalized) {

			map_finalized = 1;
			int stable = 0;

			int add_map[map_len];

			//	This first section is responsible for expanding the map into new squares
			//	that have come into vision.

			while (!stable) {

				stable = 1;
				memset(add_map, 0, map_len*sizeof(int));

				for (i = 0; i < map_len; ++i) {
					if (Visited[i] != 1 || PushMap[i] >= (INT_MAX/2) || Info->map[i] == '%')
						continue;

					int beside_i[4] = {
						iNorth(i),
						iEast(i),
						iSouth(i),
						iWest(i)
					};

					int largest_neighbour = 0;

					for (j = 0; j < 4; ++j) {
						if (PushMap[beside_i[j]] > largest_neighbour)
							largest_neighbour = PushMap[beside_i[j]];
					}

					if (largest_neighbour == 0)
						continue;

					if (PushMap[i] == 0) {
						add_map[i] = largest_neighbour - 1;
						stable = 0;
					}
				}

				for (i = 0; i < map_len; ++i)
					PushMap[i] += (long) add_map[i];

				if (!stable)
					map_finalized = 0;
			}

			stable = 0;

			//	This section section is responsible for backing out of dead ends by determining
			//	if a square has reached a minimum value for the PushMap, and increasing the value
			//	to be level with the rest of the PushMap.

			while (!stable) {

				stable = 1;
				memset(add_map, 0, sizeof(int)*map_len);

				for (i = 0; i < map_len; ++i) {
					if (Visited[i] != 1 || PushMap[i] >= (INT_MAX/2) || Info->map[i] == '%' || PushMap[i] == 0)
						continue;

					int beside_i[4] = {
						iNorth(i),
						iEast(i),
						iSouth(i),
						iWest(i)
					};

					for (j = 0; j < 4; ++j) {
						if (Info->map[beside_i[j]] != '%' && PushMap[beside_i[j]] < PushMap[i])
							break;
					}

					if (j == 4) {
						add_map[i] += 1;
						stable = 0;
					}
				}

				for (i = 0; i < map_len; ++i)
					PushMap[i] += (long) add_map[i];

				if (!stable)
					map_finalized = 0;
			}
		}
	}

	int my_hive_count = 0;

	for (i = 0; i < Game->hive_count; ++i) {
		if (Game->hives[i].player == 'a')
			++my_hive_count;
	}



	long A_BIG_NUM = (long) (((double) LONG_MAX)/pow(2, 30));


	if (Game->hive_count != LAST_HIVE_COUNT) {
		memset(BaseMap, 0, Info->rows*Info->cols*sizeof(long));
	}


	if (CURRENT_TURN == 1 || Game->hive_count != LAST_HIVE_COUNT)  {

		//	This is for some outdated map initializing code. It's not important.

		for (i = 0; i < Game->hive_count; ++i) {
			if (Game->hives[i].player == 'a') {
				increase_heat(Game->hives[i].row*Info->cols + Game->hives[i].col, 1.001, INT_MAX, 100/my_hive_count, BaseMap, 0x2, Info);
			}
			else
				increase_heat(Game->hives[i].row*Info->cols + Game->hives[i].col, 1.001, INT_MIN, 100, BaseMap, 0x2, Info);
		}
	}

	LAST_HIVE_COUNT = Game->hive_count;


    int opponent_num = 0;
	int num_ants[26];
	memset(num_ants, 0, 26*sizeof(int));

	for (i = 0; i < Game->enemy_count; ++i) {
		unsigned char enemy_id = Game->enemy_ants[i].player - 'a';

		++num_ants[Game->enemy_ants[i].player - 'a'];

		if (enemy_id > opponent_num)
			opponent_num = enemy_id;
	}

	int largest_ant_pop = 0;

	for (i = 0; i < 26; ++i) {
		if (num_ants[i] > largest_ant_pop) {
			largest_ant_pop = num_ants[i];
		}
	}

	if (largest_ant_pop != 0) {
		DOMINANT_PERCENT = ((float) largest_ant_pop)/((float) Game->enemy_count);
	}

	if (opponent_num > OPPONENT_NUM)
		OPPONENT_NUM = opponent_num;



	/*

		SECTION 1:

		We've reached checkpoint 1. Up till now, everything has been initialization,
		if you were smart, you probably skipped over most of it. This next section
		is short, because work has been outsourced overseas to the do_battles
		function.

	*/


	fprintf(stderr, "(1) %04g, ", ((double) clock() - (double) previous_clock)/ (double) CLOCKS_PER_SEC);
	previous_clock = clock();

	int complete = 0;
	sd_pair sd_pair[Game->my_count];
	memset(sd_pair, -1, sizeof(struct sd_pair)*Game->my_count);


	struct sd_pair temp_pair[Game->my_count];
	memcpy(temp_pair, sd_pair, sizeof(struct sd_pair)*Game->my_count);

	do_battles(&complete, sd_pair, Game, Info);


	/*

		SECTION 2:

		We've battled hard! Some of us died. Luckily we're ants, and are easily
		disposable. But for the rest of us, there's still work to do. We're needed
		to collect "objectives".

	*/

	fprintf(stderr, "(2) %04g, ", ((double) clock() - (double) previous_clock)/ (double) CLOCKS_PER_SEC);
	previous_clock = clock();

	int viewradius = ((int) sqrt(Info->viewradius_sq)) + 1;


	//	Find some enemy hives that are undefended and go attack them. If they are
	//	defended, we'll just end up attacking the ants around them later.

	if (my_hive_count < Game->hive_count) {

		struct basic_ant targets[Game->hive_count - my_hive_count];
		int target_index = 0;

		for (i = 0; i < Game->hive_count; ++i) {
			if (Game->hives[i].player != 'a') {
				int my_closest = INT_MAX;
				int enemy_closest = INT_MAX;

				for (j = 0; j < Game->my_count; ++j) {
					int dist = distance(Game->hives[i].row, Game->hives[i].col,
										Game->my_ants[j].row, Game->my_ants[j].col, Info);

					if (dist < my_closest)
						my_closest = dist;
				}

				for (j = 0; j < Game->enemy_count; ++j) {
					int dist = distance(Game->hives[i].row, Game->hives[i].col,
										Game->enemy_ants[j].row, Game->enemy_ants[j].col, Info);

					if (dist < enemy_closest)
						enemy_closest = dist;
				}

				if (my_closest + ((int) sqrt(Info->attackradius_sq)) < enemy_closest) {

					targets[target_index].row = Game->hives[i].row;
					targets[target_index].col = Game->hives[i].col;
					++target_index;
				}
			}
		}

		if (target_index > 0)
			assign_ants(&complete, INT_MAX, sd_pair, 0, targets, sizeof(struct basic_ant), target_index, 0x0, 100, Info, Game);
	}

	/*

		It's time to gather food.

		If you've read the write up I made about this, or caught on from the code itself,
		I actually don't know that much about AI development. After all, I decided to
		write an AI in C. But besides that, I'm not really familiar with the basic
		but common algorithmns that everyone else uses to do relatively trivial things,
		and I like to challenge myself with comming up with my own.

		As far as I know, bfs was the most common and most sucessful method of gathering
		food. This one functions just as well, albeit a little less efficiently, but
		it has the added advantage that I came up with it myself. It goes something like
		this:

		First, the minimum walking distance between every one of my ants and every piece
		of food is calculated. This is the distance we will have to travel if there is
		nothing in our way. We will first attempt to find a path using only two directions
		(the unobstructed directions from an ant to a piece of food) to see if such an
		optimal and simple path exists. After that, we try to find a more complex path
		containing all four directions, and update the array of distances to contain the
		correct value.

		An ant is assigned to a piece of food based on whether or not it is the closest
		of all other ants to a piece of food. If an ant is the closest to multiple pieces
		of food, it will chose the closest food, and the remainder of the food will be
		assigned to some other ant. In other words, we generate a set of ant-food
		distances and chose the smallest ones so that no ant goes to the same food.

		If you understood that, then there's also no reason to look at the assign_ants()
		function because it works exactly the same way. If you're wondering why I didn't
		instead use the assign_ants() function for food, it's because food has a few
		subtle additions to it that I don't want to get into, but just know that I'm not
		trying to make the code any more convoluted than it already is.

	*/


	int ant_indexD[Game->my_count][Game->food_count];
	memset(ant_indexD, 0, Game->my_count*Game->food_count*sizeof(int));

	int ant_indexE[Game->enemy_count][Game->food_count];
	memset(ant_indexE, 0, Game->enemy_count*Game->food_count*sizeof(int));

	for (i = 0; i < Game->my_count; ++i) {
		for (j = 0; j < Game->food_count; ++j) {
			ant_indexD[i][j] = distance(Game->my_ants[i].row, Game->my_ants[i].col,
									   Game->food[j].row, Game->food[j].col, Info);

			if (Info->spawnradius_sq > 1) {
				if (Game->my_ants[i].row != Game->food[j].row)
					--ant_indexD[i][j];

				if (Game->my_ants[i].col != Game->food[j].col)
					--ant_indexD[i][j];
			}
		}
	}

	for (i = 0; i < Game->enemy_count; ++i) {
		for (j = 0; j < Game->food_count; ++j) {
			ant_indexE[i][j] = distance(Game->enemy_ants[i].row, Game->enemy_ants[i].col,
										Game->food[j].row, Game->food[j].col, Info);

			if (Info->spawnradius_sq > 1) {
				if (Game->enemy_ants[i].row != Game->food[j].row)
					--ant_indexE[i][j];

				if (Game->enemy_ants[i].col != Game->food[j].col)
					--ant_indexE[i][j];
			}
		}
	}

	int can_steal[Game->food_count];

    for (i = 0; i < Game->food_count; ++i)
        can_steal[i] = INT_MAX;

	if (Game->enemy_count > 0) {
		for (i = 0; i < Game->food_count; ++i) {
			int my_min = INT_MAX;
			int enemy_min = INT_MAX;

			for (j = 0; j < Game->my_count; ++j) {
				if (ant_indexD[j][i] < my_min)
					my_min = ant_indexD[j][i];
			}

			for (j = 0; j < Game->enemy_count; ++j) {
				if (ant_indexE[j][i] < enemy_min)
					enemy_min = ant_indexE[j][i];
			}

			can_steal[i] = enemy_min - my_min;
		}
	}

	i = 0;


	int dec = (int) (log10((double) Game->my_count)/log10(5.0));

	int attackradius = ((int) sqrt(Info->attackradius_sq)) + 1;

	double time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));

	while (my_hive_count > 0 && i < Game->food_count && time_spent < TIME_LIMIT*0.82) {

        int small_dist = (22 - dec) + 1;

		int source = -1;
		int dest = -1;

		for (j = 0; j < Game->my_count; ++j) {
			if (sd_pair[j].id != -1)
				continue;

			int k;
			for (k = 0; k < Game->food_count; ++k) {
				unsigned int test = (unsigned int) ant_indexD[j][k];

				int l;
				int hopeless = 0;

				if (can_steal[k] <= -attackradius) {
					hopeless = 1;
				}

				if (hopeless)
					continue;

				int passby_test = INT_MAX;

				if (Game->my_count < Game->food_count && ANT_DENSITY < 0.7) {
					for (l = 0; l < Game->my_count; ++l) {
						if (sd_pair[l].id == -1)
							continue;

						int passby_id = sd_pair[l].id;
						int test_dist = sd_pair[l].dist + distance(sd_pair[l].row, sd_pair[l].col,
																   Game->food[k].row, Game->food[k].col, Info);

						if (test_dist < passby_test) {
							passby_test = test_dist;
						}
					}
				}

				if (Game->enemy_count == 0 && passby_test != INT_MAX)
					passby_test = (passby_test*2)/3;

				if (test < small_dist && test < passby_test) {
					small_dist = test;
					source = j;
					dest = k;
				}
			}
		}

		if (source != -1) {

			int source_offset = Game->my_ants[source].row*Info->cols + Game->my_ants[source].col;
			int dest_offset = Game->food[dest].row*Info->cols + Game->food[dest].col;

			int dirs[5];
			int max_depth = 0;

			get_dirs(ant_indexD[source][dest], Game->my_ants[source].row, Game->food[dest].row,
					 Game->my_ants[source].col, Game->food[dest].col, sd_pair[source].ignore, &max_depth, dirs, Info);

			int NTest = iNorth(source_offset);
			int ETest = iEast(source_offset);
			int STest = iSouth(source_offset);
			int WTest = iWest(source_offset);

			char original_map[4] = {
				Info->map[NTest],
				Info->map[ETest],
				Info->map[STest],
				Info->map[WTest]
			};

			if (sd_pair[source].ignore[0] == 1)
				Info->map[NTest] = '\x01';

			if (sd_pair[source].ignore[1] == 1)
				Info->map[ETest] = '\x01';

			if (sd_pair[source].ignore[2] == 1)
				Info->map[STest] = '\x01';

			if (sd_pair[source].ignore[3] == 1)
				Info->map[WTest] = '\x01';

			int depth_map[map_len];
			for (j = 0; j < map_len; ++j)
				depth_map[j] = INT_MAX;

			char can_move = check_path(source_offset, dest_offset, Info->spawnradius_sq, (char *) 0, dirs, 0, 0,
									   ant_indexD[source][dest] - 1, Info->map, depth_map, Info);

			if (!can_move) {
				for (j = 0; j < map_len; ++j)
					depth_map[j] = INT_MAX;

				for (j = 0; j < 4; ++j) {
					dirs[j] = j;
				}
				dirs[4] = -1;

				can_move = check_path(source_offset, dest_offset, Info->spawnradius_sq, (char *) 0, dirs, 0, 0,
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
				memset(ant_indexD[source], -1, Game->food_count*sizeof(int));

				for (j = 0; j < Game->my_count; ++j) {
					ant_indexD[j][dest] = -1;
				}

				sd_pair[source].id = source;
				sd_pair[source].row = Game->food[dest].row;
				sd_pair[source].col = Game->food[dest].col;
				sd_pair[source].suggest = can_move;
				if (sd_pair[source].priority < 999)
					sd_pair[source].priority = 999;
				sd_pair[source].dist = small_dist;

				++i;


				int (*func) (int offset, struct game_info *Info) = get_func(can_move);
				int new_square = func(source_offset, Info);

				for (j = 0; j < Game->my_count; ++j) {
					if (j == source)
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

				memcpy(&temp_pair[source], &sd_pair[source], sizeof(struct sd_pair));
			}
			else
				ant_indexD[source][dest] = -1;
		}
		else
			break;

		redo_find:
			continue;
	}

	complete += i;

	//	Sometimes we want to protect our own hills or go stand near them for
	//	various reasons (enemy attacks!). This section of the code is
	//	responsible for that.

	int hill_in_danger = -1;
	int NEAREST_THREAT_DIST = INT_MAX;

	if (Game->enemy_count > 0
		&& (my_hive_count > 1 || Game->enemy_count*3 > Game->my_count*2)
		&& Game->my_count > (int) pow(2, my_hive_count)
		&& Game->my_count > (Game->food_count + my_hive_count)*3) {

		int enemies_per_hill[Game->hive_count];
		memset(enemies_per_hill, 0, Game->hive_count*sizeof(int));

		for (i = 0; i < Game->enemy_count; ++i) {
			int nearest_dist = INT_MAX;
			int hill_id = -1;

			for (j = 0; j < Game->hive_count; ++j) {
				if (Game->hives[j].player != 'a')
					continue;

				int test_dist = euc_distance_sq(Game->enemy_ants[i].row, Game->enemy_ants[i].col,
												Game->hives[j].row, Game->hives[j].col, Info);

				if (test_dist < nearest_dist) {
					nearest_dist = test_dist;
					hill_id = j;
				}

				if (test_dist < NEAREST_THREAT_DIST) {
					NEAREST_THREAT_DIST = test_dist;
					hill_in_danger = j;
				}
			}

			if (hill_id != -1)
				++enemies_per_hill[hill_id];
		}
	}

	int vuln_hill_num = 0;
	int rally_ants = 0;

	if (Game->enemy_count*3 > Game->my_count*2 && my_hive_count >= 1) {

		struct basic_ant need_defending[my_hive_count];
		memset(need_defending, -1, sizeof(struct basic_ant)*my_hive_count);

		for (i = 0; i < Game->hive_count; ++i) {
			if (Game->hives[i].player == 'a') {
				int offset = Game->hives[i].row*Info->cols + Game->hives[i].col;

				if (Info->map[offset] == 'a' && (hill_in_danger == -1 || hill_in_danger == i))
					continue;

				int min_dist = INT_MAX;

				for (j = 0; j < Game->my_count; ++j) {
					int test_dist = euc_distance_sq(Game->hives[i].row, Game->hives[i].col,
													 Game->my_ants[j].row, Game->my_ants[j].col, Info);

					if (test_dist < min_dist)
						min_dist = test_dist;
				}

				int enemy_min_dist = INT_MAX;

				for (j = 0; j < Game->enemy_count; ++j) {
					int test_dist = euc_distance_sq(Game->hives[i].row, Game->hives[i].col,
												    Game->enemy_ants[j].row, Game->enemy_ants[j].col, Info);

					if (test_dist < enemy_min_dist) {
						enemy_min_dist = test_dist;
					}
				}

				if (enemy_min_dist <= (int) pow(sqrt((float) min_dist) + sqrt((float) Info->attackradius_sq), 2)) {
					need_defending[vuln_hill_num].row = Game->hives[i].row;
					need_defending[vuln_hill_num].col = Game->hives[i].col;
					++vuln_hill_num;
					rally_ants = 1;
				}
				else if (my_hive_count == 1) {
					need_defending[vuln_hill_num].row = Game->hives[i].row;
					need_defending[vuln_hill_num].col = Game->hives[i].col;
					++vuln_hill_num;
				}
			}
		}

		if (vuln_hill_num > 0) {
			int originally_complete = complete;

			assign_ants(&complete, INT_MAX, sd_pair, 0, need_defending, sizeof(struct basic_ant), vuln_hill_num, 0, 1000, Info, Game);
		}
	}


	if (my_hive_count == 1 && Game->enemy_count > Game->my_count) {

		int vuln_hill_num = 0;
		struct basic_ant need_defending[my_hive_count];
		memset(need_defending, -1, sizeof(struct basic_ant)*my_hive_count);

		for (i = 0; i < Game->hive_count; ++i) {
			if (Game->hives[i].player == 'a') {
				int min_dist = INT_MAX;

				for (j = 0; j < Game->my_count; ++j) {
					int test_dist = euc_distance(Game->hives[i].row, Game->hives[i].col,
													 Game->my_ants[j].row, Game->my_ants[j].col, Info);

					if (test_dist < min_dist)
						min_dist = test_dist;
				}

				int enemy_min_dist = INT_MAX;

				for (j = 0; j < Game->enemy_count; ++j) {
					int test_dist = euc_distance(Game->hives[i].row, Game->hives[i].col,
												 Game->enemy_ants[j].row, Game->enemy_ants[j].col, Info);

					if (test_dist < enemy_min_dist)
						enemy_min_dist = test_dist;
				}

				if (min_dist <= viewradius/2 && enemy_min_dist < min_dist + ((int) sqrt(Info->attackradius_sq)) + 1) {
					need_defending[vuln_hill_num].row = Game->hives[i].row;
					need_defending[vuln_hill_num].col = Game->hives[i].col;
					++vuln_hill_num;
				}
			}
		}

		if (vuln_hill_num > 0)
			assign_ants(&complete, INT_MAX, sd_pair, 0, need_defending, sizeof(struct basic_ant), vuln_hill_num, 0x0, 1000, Info, Game);
	}


	//	This code handles the obscure situation of when we want to sacrifice an
	//	ant to collide with another ant over a piece of food because we know
	//	a second one of our ants will be able to get there to claim the food.
	//	It's an obscure piece of code I wrote during the beta, and since it is
	//	rarely used I'm not sure if it still works. Let's assume it does.

	for (i = 0; i < Game->food_count; ++i) {
		if (abs(can_steal[i]) >= ((int) sqrt(Info->attackradius_sq)))
			continue;

		int my_backup = -1;
		int backup_dist = INT_MAX;

        int small_dist = 22 - dec;

		for (j = 0; j < Game->my_count; ++j) {
			if (sd_pair[j].id != -1)
				continue;

            int backup_dist_test = distance(Game->my_ants[j].row, Game->my_ants[j].col, Game->food[i].row, Game->food[i].col, Info);

            if (backup_dist_test > small_dist)
                continue;

			if (backup_dist_test < backup_dist) {
				my_backup = j;
				backup_dist = backup_dist_test;
			}
		}

		if (my_backup == -1)
			continue;

		int closer_enemies = 0;

		for (j = 0; j < Game->enemy_count; ++j) {
			if (ant_indexE[j][i] < backup_dist)
				++closer_enemies;
		}

		if (closer_enemies >= 2) {
			continue;
        }

		int source_offset = Game->my_ants[my_backup].row*Info->cols + Game->my_ants[my_backup].col;
		int dest_offset = Game->food[i].row*Info->cols + Game->food[i].col;

		int dirs[5];
		int max_depth = 0;

		get_dirs(backup_dist, Game->my_ants[my_backup].row, Game->food[i].row,
				 Game->my_ants[my_backup].col, Game->food[i].col, sd_pair[my_backup].ignore, &max_depth, dirs, Info);

		int NTest = iNorth(source_offset);
		int ETest = iEast(source_offset);
		int STest = iSouth(source_offset);
		int WTest = iWest(source_offset);

		char original_map[4] = {
			Info->map[NTest],
			Info->map[ETest],
			Info->map[STest],
			Info->map[WTest]
		};

		if (sd_pair[my_backup].ignore[0] == 1)
			Info->map[NTest] = '\x01';

		if (sd_pair[my_backup].ignore[1] == 1)
			Info->map[ETest] = '\x01';

		if (sd_pair[my_backup].ignore[2] == 1)
			Info->map[STest] = '\x01';

		if (sd_pair[my_backup].ignore[3] == 1)
			Info->map[WTest] = '\x01';

		int depth_map[map_len];
		for (j = 0; j < map_len; ++j)
			depth_map[j] = INT_MAX;

		char can_move = check_path(source_offset, dest_offset, Info->spawnradius_sq, (char *) 0, dirs, 0, 0, backup_dist - 1, Info->map,depth_map, Info);

		Info->map[NTest] = original_map[0];
		Info->map[ETest] = original_map[1];
		Info->map[STest] = original_map[2];
		Info->map[WTest] = original_map[3];

		if (can_move) {
			memset(ant_indexD[my_backup], -1, Game->food_count*sizeof(int));

			for (j = 0; j < Game->my_count; ++j) {
				ant_indexD[j][i] = -1;
			}

			sd_pair[my_backup].id = my_backup;
			sd_pair[my_backup].row = Game->food[i].row;
			sd_pair[my_backup].col = Game->food[i].col;
			sd_pair[my_backup].suggest = can_move;
			if (sd_pair[my_backup].priority < 998)
				sd_pair[my_backup].priority = 998;
			sd_pair[my_backup].dist = backup_dist;


			int (*func) (int offset, struct game_info *Info) = get_func(can_move);
			int new_square = func(source_offset, Info);

			for (j = 0; j < Game->my_count; ++j) {
				if (j == my_backup)
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

            ++complete;
		}
		else
			ant_indexD[my_backup][i] = -1;

		time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));
	}

	/*

		SECTION 3:

		No more objectives! From now on, code we write is either responsible
		for being aggressive or for wandering aimlessly (some might call it "exploring").

		The first thing we do is calculate the values for an outdated HeatMap that I
		don't really use much any more. Skip to the next comment if you'd like.

	*/


	fprintf(stderr, "(3) %04g, ", ((double) clock() - (double) previous_clock)/ (double) CLOCKS_PER_SEC);
	previous_clock = clock();

	time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));


	if (time_spent < TIME_LIMIT*0.8) {
		time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));

		for (i = 0; i < Game->enemy_count; ++i) {
			if (i % 10 == 6) {
				time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));
				if (time_spent > TIME_LIMIT*0.8) {
					if (HEAT_RADIUS > 15) {
						HEAT_RADIUS -= 2;
					}
					break;
				}
			}

			increase_heat(Game->enemy_ants[i].row*Info->cols + Game->enemy_ants[i].col, 2, 8, HEAT_RADIUS, PureHeatMap, 0x0, Info);
		}

		for (i = 0; i < Game->my_count; ++i) {

			if (i % 10 == 6) {
				time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));
				if (time_spent > TIME_LIMIT*0.8) {
					if (HEAT_RADIUS > 15) {
						HEAT_RADIUS -= 2;
					}
					break;
				}
			}

			int ant_offset = Game->my_ants[i].row*Info->cols + Game->my_ants[i].col;
			increase_heat(ant_offset, 2, 8, HEAT_RADIUS, PureHeatMap, 0x0, Info);
		}
	}

	/*

		Here we update the vision map. This will determine where our ants will explore for food.
		This is because one of the things ants do is check to see what squares or areas
		were seen last and what is the most recently unexplored area that they can explore,
		so this "LastVisitedMap" is very important.

	*/


	long *prac_vision_map = malloc(map_len*sizeof(long));
	memset(prac_vision_map, -1, map_len*sizeof(long));

	get_practical_vision(prac_vision_map, Info);

	for (i = 0; i < map_len; ++i) {
		if (prac_vision_map[i] == 1)
			LastVisitedMap[i] = 0;
		else if (enemy_vision_map[i] == 1)
			LastVisitedMap[i] = 0;
		else
			LastVisitedMap[i] -= 1;
	}


	long LastVisitedMap_copy[map_len];
	memcpy(LastVisitedMap_copy, LastVisitedMap, map_len*sizeof(long));

	for (i = 0; i < Game->my_count; ++i) {
		if (sd_pair[i].priority == 999 && sd_pair[i].id != -1) {
			int dest_offset = sd_pair[i].row*Info->cols + sd_pair[i].col;

			int test_map[map_len];
			memset(test_map, -1, sizeof(int)*map_len);

			set_practical_area(dest_offset, Info->viewradius_sq, 0, LastVisitedMap_copy, test_map, Info);
		}
	}

	for (i = 0; i < map_len; ++i) {
		HeatMap[i] += (BaseMap[i] + PureHeatMap[i]);
	}


	if (complete < Game->my_count && Game->enemy_count > 0) {

		/*

			SECTION 4:

			Inside this if statement we are now rallying ants to different locations
			where they either are or will be needed to do battle.

			This first section (from now until the next comment) tests to see if any
			of our hills are surrounded by more ants than we have ants at that hill,
			in which case we try an emergency retreat to save the hill (this rarely
			happens).

		*/

		fprintf(stderr, "(4) %04g, ", ((double) clock() - (double) previous_clock)/ (double) CLOCKS_PER_SEC);
		previous_clock = clock();

		time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));

		if (time_spent < TIME_LIMIT*0.8) {

			int originally_complete = complete;

			struct basic_ant all_ants[Game->my_count + Game->enemy_count];
			int total_ant_num = Game->my_count + Game->enemy_count;

			for (i = 0; i < Game->my_count; ++i) {
				all_ants[i].row = Game->my_ants[i].row;
				all_ants[i].col = Game->my_ants[i].col;
				all_ants[i].player = 'a';
			}

			for (; (i - Game->my_count) < Game->enemy_count; ++i) {
				all_ants[i].row = Game->enemy_ants[(i - Game->my_count)].row;
				all_ants[i].col = Game->enemy_ants[(i - Game->my_count)].col;
				all_ants[i].player = Game->enemy_ants[(i - Game->my_count)].player;
			}

			struct val_id_pair hive_distances[total_ant_num];


			for (i = 0; i < total_ant_num; ++i) {
				int closest_dist = INT_MAX;
				hive_distances[i].id = i;

				for (j = 0; j < Game->hive_count; ++j) {
					int test_dist = distance(all_ants[i].row, all_ants[i].col, Game->hives[j].row, Game->hives[j].col, Info);

					if (test_dist < closest_dist)
						closest_dist = test_dist;
				}

				hive_distances[i].val = closest_dist;
			}

			qsort(hive_distances, total_ant_num, sizeof(struct val_id_pair), dist_compare);

			int my_num = 0;
			int enemy_num = 0;
			int harvest = 0;


			for (i = 0; i < total_ant_num; ++i) {
				int id = hive_distances[i].id;
				int offset;
				if (id < Game->my_count) {
					offset = Game->my_ants[id].row*Info->cols + Game->my_ants[id].col;
				}
				else {
					offset = Game->enemy_ants[(id - Game->my_count)].row*Info->cols + Game->enemy_ants[(id - Game->my_count)].col;
				}

				if (Info->map[offset] == 'a')
					++my_num;
				else
					++enemy_num;

				if (enemy_num >= my_num)
					harvest = enemy_num;
			}

			if (harvest > 0 && my_hive_count == 1) {


				struct food harvest_enemies[harvest];
				int enemies_harvested = 0;

				for (i = 0; i < total_ant_num; ++i) {
					if (enemies_harvested >= harvest)
						break;

					int id = hive_distances[i].id;
					int offset;
					if (id < Game->my_count) {
						offset = Game->my_ants[id].row*Info->cols + Game->my_ants[id].col;
					}
					else {
						offset = Game->enemy_ants[(id - Game->my_count)].row*Info->cols + Game->enemy_ants[(id - Game->my_count)].col;
					}

					if (Info->map[offset] != 'a') {
						harvest_enemies[enemies_harvested].row = offset / Info->cols;
						harvest_enemies[enemies_harvested].col = offset % Info->cols;
						++enemies_harvested;
					}
				}

				while (time_spent < TIME_LIMIT*0.8) {
					int current_complete = complete;

					assign_ants(&complete, Game->my_count, sd_pair, 1, harvest_enemies, sizeof(struct food), enemies_harvested, 0x1, 100, Info, Game);

					if (complete == current_complete)
						break;


					time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));
				}

			}

			/*

				This next section is important because it assigns an enemy ant or groups of
				enemy ants to friendly ants. These friendly ants will be rallied to the enemy
				ants, and later used as "anchors" for other ants to be rallied to them. This
				effectively creates a chain of ants that will end up sending exactly how
				many ants are needed and no more into battle.

				Note: Sending more than the required ant count into battle only occurs as a
				natural result of the exploration code, and is not included here.

			*/


			int visited_squares = (int) (PERCENT_VISITED*((float) map_len));

			int my_nearest[Game->enemy_count];
			char move_to_enemy[Game->enemy_count];
			int ants_requested[Game->my_count];

			memset(my_nearest, -1, sizeof(int)*Game->enemy_count);
			memset(move_to_enemy, 0, sizeof(char)*Game->enemy_count);
			memset(ants_requested, -1, Game->my_count*sizeof(int));

			for (i = 0; i < Game->enemy_count; ++i) {

				int cannot_reach[Game->my_count];
				memset(cannot_reach, 0, Game->my_count*sizeof(int));

				int nearest_mine;

				while (1) {

					nearest_mine = -1;
					int smallest_dist = INT_MAX;

					for (j = 0; j < Game->my_count; ++j) {
						int test_dist =  distance(Game->enemy_ants[i].row, Game->enemy_ants[i].col,
									 			  Game->my_ants[j].row, Game->my_ants[j].col, Info);

						if (test_dist < smallest_dist && !cannot_reach[j] && (sd_pair[j].priority != 999 || sd_pair[j].ignore[4] == 1)) {
							nearest_mine = j;
							smallest_dist = test_dist;
						}
					}

					if (nearest_mine == -1 || sd_pair[nearest_mine].id != -1)
						break;
					else {

						//	try path
						int source_offset = Game->my_ants[nearest_mine].row*Info->cols + Game->my_ants[nearest_mine].col;
						int dest_offset = Game->enemy_ants[i].row*Info->cols + Game->enemy_ants[i].col;

						int dirs[5];
						int max_depth = 0;

						get_dirs(smallest_dist, Game->my_ants[nearest_mine].row, Game->enemy_ants[i].row,
								 Game->my_ants[nearest_mine].col, Game->enemy_ants[i].col, sd_pair[nearest_mine].ignore, &max_depth, dirs, Info);


						int NTest = iNorth(source_offset);
						int ETest = iEast(source_offset);
						int STest = iSouth(source_offset);
						int WTest = iWest(source_offset);

						char original_map[4] = {
							Info->map[NTest],
							Info->map[ETest],
							Info->map[STest],
							Info->map[WTest]
						};

						if (sd_pair[nearest_mine].ignore[0] == 1)
							Info->map[NTest] = '\x01';

						if (sd_pair[nearest_mine].ignore[1] == 1)
							Info->map[ETest] = '\x01';

						if (sd_pair[nearest_mine].ignore[2] == 1)
							Info->map[STest] = '\x01';

						if (sd_pair[nearest_mine].ignore[3] == 1)
							Info->map[WTest] = '\x01';

						int depth_map[map_len];
						for (j = 0; j < map_len; ++j)
							depth_map[j] = INT_MAX;

						char can_move = check_path(source_offset, dest_offset, 0, (char *) 0, dirs, 0x1, 0, smallest_dist, Info->map, depth_map, Info);

						Info->map[NTest] = original_map[0];
						Info->map[ETest] = original_map[1];
						Info->map[STest] = original_map[2];
						Info->map[WTest] = original_map[3];

						if (can_move) {

							move_to_enemy[i] = can_move;

							break;
						}
						else
							cannot_reach[nearest_mine] = 1;
					}

				}

				my_nearest[i] = nearest_mine;
				ants_requested[nearest_mine] += 1;
			}

			for (i = 0; i < Game->my_count; ++i) {
				int shortest_dist = INT_MAX;
				int move_id = -1;

				for (j = 0; j < Game->enemy_count; ++j) {
					if (my_nearest[j] == i && move_to_enemy[j] != 0) {
						int dist = distance(Game->my_ants[i].row, Game->my_ants[i].col,
											Game->enemy_ants[j].row, Game->enemy_ants[j].col, Info);

						if (dist < shortest_dist) {
							shortest_dist = dist;
							move_id = j;
						}
					}
				}

				if (move_id != -1) {
					sd_pair[i].id = i;
					sd_pair[i].row = Game->enemy_ants[move_id].row;
					sd_pair[i].col = Game->enemy_ants[move_id].col;
					sd_pair[i].suggest = move_to_enemy[move_id];
					if (sd_pair[i].priority < 100)
						sd_pair[i].priority = 100;
					sd_pair[i].dist = shortest_dist;
					sd_pair[i].type = 1;

					++complete;
				}
			}



			/*

				So far we've created a set of "anchors" that will later be used as guide ants for
				ant rallying, but what about ants that are already nearby and don't need anchors
				to find enemies? This leftover set of ants is rallied to an enemy here. Some
				excess "rallying" will inevitably occur, but it is allowed because the ants are
				already near enemies anyway and it is a convenient use for them.

			*/

			struct sd_pair previous_pair[Game->my_count];
			memcpy(previous_pair, sd_pair, sizeof(struct sd_pair)*Game->my_count);


			if (complete < Game->my_count) {
				int iter = 0;

				while (time_spent < TIME_LIMIT*0.8) {
					int current_complete = complete;

					assign_ants(&complete, Game->my_count, sd_pair, 1, Game->enemy_ants, sizeof(struct basic_ant), Game->enemy_count, 0x3, -1, Info, Game);

					++iter;

					if (complete == current_complete)
						break;

					time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));
				}
			}

			for (i = 0; i < Game->my_count; ++i) {
				if (sd_pair[i].id != previous_pair[i].id) {
					for (j = 0; j < Game->enemy_count; ++j) {
						if (sd_pair[i].row == Game->enemy_ants[j].row && sd_pair[i].col == Game->enemy_ants[j].col) {
							--ants_requested[my_nearest[j]];
						}
					}
				}
			}

			int depth = -1;
			time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));


			/*

				Finally we use the anchor ants to send ants from long distances to fight enemies. In this
				section, ants close to anchor ants but not close enough to be rallied to an enemy are
				instead rallied to anchor ants. These ants now become 2nd generation anchor ants, and
				will in turn be rallied to until enough ants have been sent into battle to account for
				all the enemies.

			*/


			while (complete < Game->my_count && time_spent < TIME_LIMIT*0.8) {
				++depth;

				int no_more_requests;

				for (i = 0; i < Game->my_count; ++i) {
					if (previous_pair[i].id != sd_pair[i].id && sd_pair[i].type == 1) {
						int dest = sd_pair[i].row*Info->cols + sd_pair[i].col;

						int request_feed = -1;

						for (j = 0; j < Game->my_count; ++j) {
							int my_offset = Game->my_ants[j].row*Info->cols + Game->my_ants[j].col;
							if (my_offset == dest) {
								request_feed = j;
								break;
							}
						}

						if (request_feed != -1)
							ants_requested[i] = ants_requested[request_feed] - 1;
					}
				}

				time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));

				int diff_num = 0;

				for (i = 0; i < Game->my_count; ++i)
					if (temp_pair[i].id != sd_pair[i].id && sd_pair[i].type == 1 && ants_requested[i] > 0)
						++diff_num;

				if (diff_num == 0)
					break;

				struct food try_node[diff_num];
				diff_num = -1;

				for (i = 0; i < Game->my_count; ++i) {
					if (temp_pair[i].id != sd_pair[i].id && sd_pair[i].type == 1 && ants_requested[i] > 0) {
						++diff_num;
						try_node[diff_num].row = Game->my_ants[sd_pair[i].id].row;
						try_node[diff_num].col = Game->my_ants[sd_pair[i].id].col;
						--ants_requested[i];
					}
				}
				++diff_num;

				if (complete >= Game->my_count)
					break;
				else {
					memcpy(previous_pair, sd_pair, sizeof(struct sd_pair)*Game->my_count);

					int current_complete = complete;

					assign_ants(&complete, Game->my_count, sd_pair, 0, try_node, sizeof(struct food), diff_num, 0x1, -1, Info, Game);

					time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));
				}
			}

		}


		fprintf(stderr, "(5) %04g, ", ((double) clock() - (double) previous_clock)/ (double) CLOCKS_PER_SEC);
		previous_clock = clock();

	}

	time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));

	/*

		SECTION 5: Exploration

		Second perhaps only to the battle resolution, this is one of the most interesting
		portions of the bot. The philosphy itself is very simple.

		First, each ant attempts to find the nearby square which hasn't been seen for the
		longest time, and travels to it. Since food is more likely to have turned up in
		an unknown area over a longer period of time rather than a shorter period of time,
		this makes intutive sense.

		Second, all leftover ants that do not have an unknown area of their own to travel
		to (an ant that travels to an unknown square is considered to also travel to all
		squares within viewradius of that square, as it will see these squares as well)
		use the PushMap to move as far away from friendly hills as possible. Effectively
		exploring the map. In order to ensure that ants are moving as far away as possible
		from friendly hills in all directions, the first direction searched, and therefore
		the default direction in the case of a tiebreak, is decided based on the smallest
		value of adjacent squares to the exploring ant using the PureHeatMap.


		This paricular section of code immediately below this comment is creating a new
		sd_pair array, this time specifcally for exploring, because often we want to
		override decisions made in earlier sections of the code when we feel exploring
		is a more important objective. A second sd_pair array is created so we can
		compare the two options.

	*/


	struct sd_pair spread_pair[Game->my_count];
	memset(spread_pair, -1, sizeof(struct sd_pair)*Game->my_count);

	complete = 0;

	for (i = 0; i < Game->my_count; ++i) {
		int had_ignores = 0;

		for (j = 0; j < 5; ++j) {
			if (sd_pair[i].ignore[j] == 1) {
				spread_pair[i].ignore[j] = 1;
				had_ignores = 1;
			}
		}


		if (had_ignores == 1 || sd_pair[i].priority == 1000) {
			if (sd_pair[i].id != -1 || (sd_pair[i].priority == 999 && sd_pair[i].ignore[4] == -1)) {
				spread_pair[i].id = -2;
				++complete;
			}
			continue;
		}
	}


	if (complete < Game->my_count && time_spent < TIME_LIMIT*0.8) {

		int current_complete = -1;

		/*

			We're about to enter the exploration loop. Hold on!

		*/

		while ((current_complete - complete) != 0) {

			//	First we initialize the set of ants that has yet to be accounted for
			//	and does not have a destination to explore.

			current_complete = complete;

			struct my_ant leftovers[Game->my_count - complete];
			memset(leftovers, -1, sizeof(struct my_ant)*(Game->my_count - complete));
			int left_len = 0;

			if (complete != 0) {
				for (i = 0; i < Game->my_count; ++i) {
					int not_gone = 0;

					if (spread_pair[i].id == -1)
						not_gone = 1;

					if (not_gone) {
						leftovers[left_len].id = i;
						leftovers[left_len].row = Game->my_ants[i].row;
						leftovers[left_len].col = Game->my_ants[i].col;
						++left_len;
					}
				}
			}
			else {
				for (i = 0; i < Game->my_count; ++i) {
					leftovers[left_len].id = i;
					leftovers[left_len].row = Game->my_ants[i].row;
					leftovers[left_len].col = Game->my_ants[i].col;
					++left_len;
				}
			}

			int vision = (int) sqrt(Info->viewradius_sq)*1.5 + 1;

			int dist_to_target[left_len][3];
			memset(dist_to_target, 0, left_len*sizeof(int)*3);



			//	We will now attempt to find an exploration destination for all our ants.

			for (i = 0; i < left_len; ++i) {

				time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));

				if (time_spent > TIME_LIMIT*0.8) {
					++EXPLORE_REFINEMENT;
					break;
				}

				//	This next bit basically just prepares a call to do_spread()

				int spread_id = -1;
				char spread_move = -1;
				int spread_dist = -1;

				int source_offset = leftovers[i].row*Info->cols + leftovers[i].col;

				int index = leftovers[i].id;
				int true_id = Game->my_ants[index].id;

				int new_priority = -1;


				int dec = (int) (log10((double) Game->my_count)/log10(5.0));
				int depth = 14 - dec;

				if (depth < 8)
					depth = 8;

				int nearest_mysterious = 14;

				for (j = 0; j < map_len; ++j) {
					if (Visited[j] == -1) {
						int dist = distance(j / Info->cols, j % Info->cols, source_offset / Info->cols, source_offset % Info->cols, Info);

						if (dist < nearest_mysterious)
							nearest_mysterious = dist;
					}
				}

				if (depth >= nearest_mysterious)
					depth = nearest_mysterious - 1;


				int dirs[5];
				int ignore[5];

				memset(dirs, -1, sizeof(int)*5);

				int adjacent_squares[4] = {
					iNorth(source_offset),
					iEast(source_offset),
					iSouth(source_offset),
					iWest(source_offset)
				};

				int start = Game->my_ants[leftovers[i].id].id % 4;

				for (j = 0; j < 4; ++j) {
					long lowest_value = LONG_MAX;
					int k;

					int next = -1;

					for (k = 0; k < 4; ++k) {
						int l;
						for (l = 0; l < 4; ++l) {
							if (dirs[l] == k) {
								break;
							}
						}
						if (l != 4)
							continue;

						if (PureHeatMap[adjacent_squares[k]] < lowest_value) {
							lowest_value = PureHeatMap[adjacent_squares[k]];
							next = k;
						}
					}

					dirs[j] = next;
					ignore[j] = spread_pair[index].ignore[next];
				}

				dirs[4] = -1;
				ignore[4] = -1;

				int depth_map[map_len];
				new_priority = 500;

				for (j = 0; j < map_len; ++j)
					depth_map[j] = INT_MAX;


				//	First we try to find a destionation via the vision map.


				int new_dir = do_spread(source_offset, 0, viewradius*2, dirs, 4, ignore, depth_map, LastVisitedMap_copy, Visited, 0x6, Info);
				dist_to_target[i][0] = 0;
				dist_to_target[i][1] = depth_map[0];
				dist_to_target[i][2] = depth_map[1];

				if (new_dir == -1) {
					for (j = 0; j < map_len; ++j)
						depth_map[j] = INT_MAX;

					//	Failing the use of the vision map, we then try the PushMap

					new_dir = do_spread(source_offset, 0, depth, dirs, 4, ignore, depth_map, PushMap, Visited, 0x1, Info);

					dist_to_target[i][0] = 1;
					dist_to_target[i][1] = depth_map[0];
					dist_to_target[i][2] = depth_map[1];

					new_priority = -1;
				}

				if (new_dir == -1) {
					for (j = 0; j < map_len; ++j)
						depth_map[j] = INT_MAX;

					//	If all else fails, we can try the backup exploration map, but it will probably suck.

					new_dir = do_spread(source_offset, 0, depth, dirs, 4, ignore, depth_map, HeatMap, Visited, 0x1, Info);

					dist_to_target[i][0] = 2;
					dist_to_target[i][1] = depth_map[0];
					dist_to_target[i][2] = depth_map[1];

					new_priority = -1;
				}

				if (new_dir != -1) {

					//	If we've chosen a move, set it.

					char can_move = get_letter(new_dir);

					spread_id =  dist_to_target[i][2];
					spread_dist = distance(spread_id / Info->cols, spread_id % Info->cols,
									   leftovers[i].row, leftovers[i].col, Info);

					spread_move = can_move;

				}

				if (spread_move != -1) {

					//	Writing the move data

					spread_pair[index].id = index;
					spread_pair[index].row = spread_id / Info->cols;
					spread_pair[index].col = spread_id % Info->cols;
					spread_pair[index].suggest = spread_move;
					if (new_priority == -1 && spread_pair[index].priority < spread_dist*3)
						spread_pair[index].priority = spread_dist*3;
					else if (spread_pair[index].priority < new_priority)
						spread_pair[index].priority = new_priority;
					spread_pair[index].dist = spread_dist;

					++complete;


					int (*func) (int offset, struct game_info *Info) = get_func(spread_move);
					int new_square = func(source_offset, Info);

					for (j = 0; j < Game->my_count; ++j) {
						if (j == index)
							continue;

						int k;

						for (k = 0; k < 4; ++k) {
							if (*(MOVE_LOOKUP + (Game->my_ants[j].row*Info->cols + Game->my_ants[j].col)*4 + k) == new_square) {
								spread_pair[j].ignore[k] = 1;
							}
						}

						if (Game->my_ants[j].row*Info->cols + Game->my_ants[j].col == new_square) {
							spread_pair[j].ignore[4] = 1;
						}
					}
				}

				//	This section of the code sets areas that now have explorers to "Visited", and unsets
				//	moves for any overlapping explorers, forcing them to try the whole process again

				for (i = 0; i < left_len; ++i) {
					if (dist_to_target[i][0] != 0)
						continue;

					int id = leftovers[i].id;

					if (spread_pair[id].id == -1 || spread_pair[id].type == 2)
						continue;

					int spread_offset = spread_pair[id].row*Info->cols + spread_pair[id].col;


					int test_map[map_len];
					memset(test_map, -1, sizeof(int)*map_len);

					set_practical_area(spread_offset, Info->viewradius_sq, 0, LastVisitedMap_copy, test_map, Info);

					int min_dist = dist_to_target[i][1];
					int selected_ant = i;

					for (j = 0; j < left_len; ++j) {
						if (dist_to_target[j][0] != 0 || i == j)
							continue;

						int id2 = leftovers[j].id;
						int spread_offset2 = spread_pair[id2].row*Info->cols + spread_pair[id2].col;

						if (spread_pair[id2].type == 2 || spread_pair[id2].id == -1)
							continue;

						if (LastVisitedMap_copy[spread_offset2] == 0) {

							if (dist_to_target[j][1] < min_dist) {
								selected_ant = j;
								min_dist = dist_to_target[j][1];
							}
						}
					}

					for (j = 0; j < left_len; ++j) {
						if (dist_to_target[j][0] != 0 || j == selected_ant)
							continue;

						int id2 = leftovers[j].id;
						int spread_offset2 = spread_pair[id2].row*Info->cols + spread_pair[id2].col;

						if (spread_pair[id2].type == 2 || spread_pair[id2].id == -1)
							continue;

						if (LastVisitedMap_copy[spread_offset2] == 0) {
							spread_pair[id2].id = -1;
							--complete;
						}
					}

					int selected_id = leftovers[selected_ant].id;
					int selected_offset = spread_pair[selected_id].row*Info->cols + spread_pair[selected_id].col;

					spread_pair[selected_id].type = 2;
				}

				// 	Now we loop back around and settle descrepancies, or
				//	exit this loop if everything appears to be in order.
			}
		}
	}

	//	Now that we're done exploring, see which ants have yet to decide on a move
	//	and can be assigned to explore, and override any moves that are less
	//	important than exploring and don't match certain "priority rules"

	for (i = 0; i < Game->my_count; ++i) {
		if ((spread_pair[i].priority == 500 && sd_pair[i].priority < 100)
			 || (sd_pair[i].id == -1 && (sd_pair[i].priority != 999 || sd_pair[i].ignore[4] == 1))) {
			memcpy(&sd_pair[i], &spread_pair[i], sizeof(struct sd_pair));
		}
	}

	/*

		SECTION 6:

		This section simply checks for collisions between ant moves. It's probably like
		most collision-checking code, except of course that it's written in C and much
		longer, so I won't go into detail explaining it. One interesting thing to note,
		however, is that the code attempts to re-route ants that get into a collision
		to a new destination.

	*/

	fprintf(stderr, "(6) %04g, ", ((double) clock() - (double) previous_clock)/ (double) CLOCKS_PER_SEC);
	previous_clock = clock();

	for (i = 0; i < Game->my_count; ++i) {
		if (sd_pair[i].id == -1 && (sd_pair[i].priority != 999 || sd_pair[i].ignore[4] == 1)) {
			for (j = 0; j < 5; ++j) {
				if (sd_pair[i].ignore[j] == -1) {
					sd_pair[i].id = i;
					sd_pair[i].suggest = get_letter(j);
					sd_pair[i].dist = 0;
					sd_pair[i].priority = 1;
				}
			}
		}
	}


	int crashed = 1;
	char *fake_map = malloc(Info->rows*Info->cols);
	memcpy(fake_map, Info->map, Info->rows*Info->cols);

	for (i = 0; i < Game->my_count; ++i) {
		if (sd_pair[i].id == -1) {
			sd_pair[i].id = i;
			sd_pair[i].suggest = 1;
			sd_pair[i].dist = 0;
			sd_pair[i].priority = 0;
			continue;
		}
	}

	time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));

	while (crashed && time_spent < TIME_LIMIT*0.85) {
		crashed = 0;

		time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));

        int two_dirs[2];

		for (i = 0; i < Game->my_count; ++i) {
			if (sd_pair[i].id == -1)
				continue;

			int offset1 = Game->my_ants[i].row*Info->cols + Game->my_ants[i].col;
			int (*func1) (int offset, struct game_info *Info) = get_func(sd_pair[i].suggest);
			two_dirs[0] = get_num(sd_pair[i].suggest);

			int new_offset = func1(offset1, Info);

			if (fake_map[new_offset] == '%' || fake_map[new_offset] == '*') {
				sd_pair[i].ignore[two_dirs[0]] = 1;
				sd_pair[i].suggest = 0;

				crashed = 1;
				break;
			}

			for (j = i + 1; j < Game->my_count; ++j) {
				if (sd_pair[j].id == -1 || i == j)
					continue;

				int (*func2) (int offset, struct game_info *Info) = get_func(sd_pair[j].suggest);
				int offset2 = Game->my_ants[j].row*Info->cols + Game->my_ants[j].col;
				two_dirs[1] = get_num(sd_pair[j].suggest);

				int new_offset2 = func2(offset2, Info);

				if (fake_map[new_offset2] == '%' || fake_map[new_offset2] == '*') {
					sd_pair[j].ignore[two_dirs[1]] = 1;
					sd_pair[j].suggest = 0;

					crashed = 1;
					break;
				}

				if (new_offset == new_offset2) {

                    int pri_dir, sec_dir, pri_index, sec_index;

                    if (sd_pair[i].priority > sd_pair[j].priority) {
                        pri_dir = two_dirs[0];
                        sec_dir = two_dirs[1];
                        pri_index = i;
                        sec_index = j;
                    }
                    else {
                        sec_dir = two_dirs[0];
                        pri_dir = two_dirs[1];
                        sec_index = i;
                        pri_index = j;
                    }

					if (sec_dir != 4) {
						sd_pair[sec_index].ignore[sec_dir] = 1;
						sd_pair[sec_index].suggest = 0;

						crashed = 1;
					}
					else {
						if (pri_dir != 4) {
							sd_pair[pri_index].ignore[pri_dir] = 1;
							sd_pair[pri_index].suggest = 0;

							crashed = 1;
						}
					}

				}
			}
		}

		if (crashed == 1) {
			crashed = 0;

			for (i = 0; i < Game->my_count; ++i) {
				if (sd_pair[i].suggest != 0)
					continue;

				if (sd_pair[i].dist != 0) {
					int source_offset = Game->my_ants[i].row*Info->cols + Game->my_ants[i].col;
					int goal = sd_pair[i].row*Info->cols + sd_pair[i].col;
					int dist = distance(Game->my_ants[i].row, Game->my_ants[i].col,
										sd_pair[i].row, sd_pair[i].col, Info);

//					int (*dirs[5]) (int offset, struct game_info *Info);
					int dirs[5];
					int max_depth = 0;

					get_dirs(dist, Game->my_ants[i].row, sd_pair[i].row,
							 Game->my_ants[i].col, sd_pair[i].col, sd_pair[i].ignore, &max_depth, dirs, Info);

					int NTest = iNorth(source_offset);
					int ETest = iEast(source_offset);
					int STest = iSouth(source_offset);
					int WTest = iWest(source_offset);

					char original_map[4] = {
						fake_map[NTest],
						fake_map[ETest],
						fake_map[STest],
						fake_map[WTest]
					};

					int blocked_num = 0;

					if (sd_pair[i].ignore[0] == 1)
						fake_map[NTest] = '\x01';

					if (sd_pair[i].ignore[1] == 1)
						fake_map[ETest] = '\x01';

					if (sd_pair[i].ignore[2] == 1)
						fake_map[STest] = '\x01';

					if (sd_pair[i].ignore[3] == 1)
						fake_map[WTest] = '\x01';

					char current = fake_map[source_offset];

					if (current == '%')
						fake_map[source_offset] = '.';


					int depth_map[map_len];
					for (j = 0; j < map_len; ++j)
						depth_map[j] = INT_MAX;

					char can_move = check_path(source_offset, goal, 0, (char *) 0, dirs, 0, 0, dist, fake_map, depth_map, Info);

					fake_map[source_offset] = current;

					fake_map[NTest] = original_map[0];
					fake_map[ETest] = original_map[1];
					fake_map[STest] = original_map[2];
					fake_map[WTest] = original_map[3];

					if (can_move == 0)
						can_move = 1;

					if (can_move) {
						sd_pair[i].suggest = can_move;
					}
					else if (sd_pair[i].state != 0) {
						sd_pair[i].suggest = sd_pair[i].state;
						sd_pair[i].state = 0;
					}
				}
				else {
					for (j = 0; j < 5; ++j) {
						if (sd_pair[i].ignore[j] == -1) {
							sd_pair[i].suggest = get_letter(j);
							break;
						}
					}
				}

				crashed = 1;
			}
		}
	}

	free(fake_map);

	/*

		SECTION 7:

		At long last, we output our moves. After this there is some outdated code that's needed
		to initlaize the BaseMap, some memory allocation stuff and some debugging info, but
		beyond this point no real work needs to be done. We have successfully completed our
		turn.

	*/

	fprintf(stderr, "(7) %04g ", ((double) clock() - (double) previous_clock)/ (double) CLOCKS_PER_SEC);

	for (i = 0; i < Game->my_count; ++i) {
		if (sd_pair[i].id == -1) {
			continue;
		}

		#define ID sd_pair[i].id

		if (sd_pair[i].suggest > 1) {
			move(ID, sd_pair[i].suggest, Game, Info);
		}
	}

	if (CURRENT_TURN > 0) {
		long largest_value = 0;

		long BufferMap[map_len];
		memset(BufferMap, 0, sizeof(long)*map_len);

		int success = 1;
		int tries = 0;

		double time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));

		while (success && time_spent < TIME_LIMIT*0.8) {

			double time_spent = ((((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC));

			++tries;
			success = 0;

			for (i = 0; i < map_len; ++i) {
				if (Visited[i] == 1 && BaseMap[i] != 0) {
					int beside_i[4] = {
						iNorth(i),
						iEast(i),
						iSouth(i),
						iWest(i)
					};

					for (j = 0; j < 4; ++j) {

						if (Visited[beside_i[j]] == 1 && Info->map[beside_i[j]] != '%' && BaseMap[beside_i[j]] == 0 && BufferMap[beside_i[j]] == 0) {

							BufferMap[beside_i[j]] = (long) (((double) BaseMap[i])/1.001);
							if (BufferMap[beside_i[j]] > 0)
								success = 1;

						}

					}
				}

				if (abs(BaseMap[i]) > largest_value)
					largest_value = abs(BaseMap[i]);
			}

		}

		for (i = 0; i < map_len; ++i) {
			if (BaseMap[i] != 0 && Info->map[i] != '%' && vision_map[i] == 1) {
				int beside_i[4] = {
					iNorth(i),
					iEast(i),
					iSouth(i),
					iWest(i)
				};

				for (j = 0; j < 4; ++j) {
					if (Visited[beside_i[j]] == -1
						|| (Info->map[beside_i[j]] != '%' && BaseMap[beside_i[j]] < BaseMap[i]))
						break;
				}

				if (j == 4 && BaseMap[i] < LONG_MAX/16) {
					BufferMap[i] = ((long) (((double) BaseMap[i])*1.001)) - BaseMap[i];
				}
			}
		}

		for (i = 0; i < map_len; ++i) {
			BaseMap[i] += BufferMap[i];
		}

		if (largest_value > (long) (((double) LONG_MAX)/32)) {
			for (i = 0; i < map_len; ++i) {
				BaseMap[i] /= 10;
			}
		}
	}


	memcpy(Info->map, unmodified_map, sizeof(char)*map_len);

	free(unmodified_map);
	free(vision_map);
	free(prac_vision_map);
	free(enemy_vision_map);

	fprintf(stderr, "|| %04g (%04g/%04g, %04g) { %i, %i } \n", ((double) clock() - (double) INITIAL_CLOCK)/ (double) CLOCKS_PER_SEC,
				ANT_DENSITY, PERCENT_CAPTURED, my_hive_count, Game->my_count, Game->enemy_count);
}
