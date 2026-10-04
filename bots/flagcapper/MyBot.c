#include "ants.h"

inline int abs(int x) {
    if (x >= 0)
        return x;
    return -x;
}

int euc_distance(int row1, int col1, int row2, int col2, struct game_info *Info) {
    int dr, dc;
    int abs1, abs2;

    abs1 = abs(row1 - row2);
    abs2 = Info->rows - abs(row1 - row2);

    if (abs1 > abs2)
        dr = abs2;
    else
        dr = abs1;

    abs1 = abs(col1 - col2);
    abs2 = Info->cols - abs(col1 - col2);

    if (abs1 > abs2)
        dc = abs2;
    else
        dc = abs1;

    return sqrt(((int) pow(dr, 2)) + ((int) pow(dc, 2)));
}

int euc_distance_sq(int row1, int col1, int row2, int col2, struct game_info *Info) {
    int dr, dc;
    int abs1, abs2;

    abs1 = abs(row1 - row2);
    abs2 = Info->rows - abs(row1 - row2);

    if (abs1 > abs2)
        dr = abs2;
    else
        dr = abs1;

    abs1 = abs(col1 - col2);
    abs2 = Info->cols - abs(col1 - col2);

    if (abs1 > abs2)
        dc = abs2;
    else
        dc = abs1;

    return ((int) pow(dr, 2)) + ((int) pow(dc, 2));
}

int distance(int row1, int col1, int row2, int col2, struct game_info *Info) {
    int dr, dc;
    int abs1, abs2;

    abs1 = abs(row1 - row2);
    abs2 = Info->rows - abs(row1 - row2);

    if (abs1 > abs2)
        dr = abs2;
    else
        dr = abs1;

    abs1 = abs(col1 - col2);
    abs2 = Info->cols - abs(col1 - col2);

    if (abs1 > abs2)
        dc = abs2;
    else
        dc = abs1;

    return dr + dc;
}

void move(int index, char dir, struct game_state* Game, struct game_info* Info) {
    fprintf(stdout, "o %i %i %c\n", Game->my_ants[index].row, Game->my_ants[index].col, dir);

    switch (dir) {
        case 'N':
            if (Game->my_ants[index].row != 0)
                Game->my_ants[index].row -= 1;
            else
                Game->my_ants[index].row = Info->rows - 1;
            break;
        case 'E':
            if (Game->my_ants[index].col != Info->cols - 1)
                Game->my_ants[index].col += 1;
            else
                Game->my_ants[index].col = 0;
            break;
        case 'S':
            if (Game->my_ants[index].row != Info->rows - 1)
                Game->my_ants[index].row += 1;
            else
                Game->my_ants[index].row = 0;
            break;
        case 'W':
            if (Game->my_ants[index].col != 0)
                Game->my_ants[index].col -= 1;
            else
                Game->my_ants[index].col = Info->cols - 1;
            break;
    }
}

char *get_line(char *text) {
    char *tmp_ptr = text;
    int len = 0;

    while (*tmp_ptr != '\n') {
        ++tmp_ptr;
        ++len;
    }

    char *return_str = malloc(len + 1);
    memset(return_str, 0, len + 1);

    int i = 0;
    for (; i < len; ++i) {
        return_str[i] = text[i];
    }

    return return_str;
}

int main(int argc, char *argv[]) {
    int action = -1;

    struct game_info Info;
    struct game_state Game;
    Info.map = 0;

    Game.my_ants = 0;
    Game.enemy_ants = 0;
    Game.food = 0;
    Game.dead_ants = 0;
	Game.hives = 0;

	while (42) {
        int initial_buffer = 100000;

        char *data = malloc(initial_buffer);
        memset(data, 0, initial_buffer);

        *data = '\n';

        char *ins_data = data + 1;

        int i = 0;

        while (1 > 0) {
            ++i;

            if (i >= initial_buffer) {
                initial_buffer *= 2;
                data = realloc(data, initial_buffer);
				ins_data = data + i;
                memset(ins_data, 0, initial_buffer - i);
            }

            *ins_data = getchar();

            if (*ins_data == '\n') {
                char *backup = ins_data;

                while (*(backup - 1) != '\n') {
                    --backup;
                }

                char *test_cmd = get_line(backup);

                if (strcmp(test_cmd, "go") == 0) {
                    action = 0;
                    free(test_cmd);
                    break;
                }
                else if (strcmp(test_cmd, "ready") == 0) {
                    action = 1;
                    free(test_cmd);
                    break;
                }
                else if (strcmp(test_cmd, "end") == 0) {
                    action = 2;
                    free(test_cmd);
                    break;
                }

                free(test_cmd);
            }

            ++ins_data;
        }

        if (action == 0) {
            char *skip_line = data + 1;
            while (*++skip_line != '\n');
            ++skip_line;

            _init_map(skip_line, &Info, &Game);
            _init_game(&Info, &Game);
            do_turn(&Game, &Info);
            fprintf(stdout, "go\n");
            fflush(stdout);
        }
        else if (action == 1) {
            _init_ants(data + 1, &Info);

            Game.my_ant_index = -1;

            fprintf(stdout, "go\n");
            fflush(stdout);
        }
        else if (action == 2) {
            fprintf(stdout, "go\n");
            fflush(stdout);
            free(data);
            break;
        }

        free(data);
	}
}
