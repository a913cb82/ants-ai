from ants import *
from random import shuffle
from random import random
"""
TODO
"""
class MyBot:
	#A* pathfinding
	#find shortest path from loc1 to loc2 (tuples)
	def pathfinding(self,ants,loc1,loc2):
		closedset=[]
		openset=[loc1]
		came_from={}
		came_from[loc1]=0
		
		g_score=h_score=f_score={}
		g_score[loc1]=0
		h_score[loc1]=ants.distance(loc1,loc2)
		f_score=[[g_score[loc1]+h_score[loc1] , loc1],[1e6,loc1]]
		
		n=0
		while openset:
			n+=1
			#choose lowest f_score node
			f_score.sort()
			for dist,x in f_score:
				if x in openset:
					break
			if x==loc2 or n>self.depth or (ants.time_remaining()<100 and len(came_from)>1):
				return self.reconstruct_path(came_from, x)
			#remove x from openset and add to closedset
			openset.remove(x)
			closedset.append(x)
			#get neighbours
			neighbor_nodes=[]
			for direction in ['n','e','s','w']:
				neighbor_nodes.append(ants.destination(x,direction))
			#for each neighbour
			for y in neighbor_nodes:
				if ants.unoccupied(y):# and y not in self.danger_list:
					#if neighbour already visited
					if y in closedset:
						continue
					
					tentative_g_score=g_score[x]+1
					if y not in openset:
						openset.append(y)
						tentative_is_better='TRUE'
					elif tentative_g_score < g_score[y]:
						tentative_is_better='TRUE'
					else:
						tentative_is_better='FALSE'
					
					if tentative_is_better=='TRUE':
						came_from[y]=x
						g_score[y]=tentative_g_score
						h_score[y]=ants.distance(y,loc2)
						f_score.append([g_score[y]+h_score[y] , y])
		return loc1[0],loc1[1],loc2[0],loc2[1]

	def reconstruct_path(self,came_from, current_node):
		if came_from[current_node]:
			p=self.reconstruct_path(came_from, came_from[current_node])
			return (p + current_node)
		else:
			return current_node

	def getdir(self,ants,loc1,loc2):
		path=self.pathfinding(ants,loc1,loc2)
		loc2=(path[2],path[3])
		dir=ants.direction(loc1,loc2)
		return dir[0]
	
	
	#define class level variables, will be remembered between turns
	def __init__(self):
		pass
	
	#initialize data structures after learning the game settings
	def do_setup(self, ants):
		self.depth=100
		#store hills sighted
		self.hills = []
		#'flag' tiles for exploring
		self.flags = []
		#ants.viewradius2 dist between each
		dist=ants.viewradius2**.5/2
		for flag_row in range(int(ants.rows/dist)):
			for flag_col in range(int(ants.cols/dist)):
				self.flags.append((int(flag_row*dist),int(flag_col*dist)))
				
	
	def do_turn(self, ants):
		#issue move command if possible and safe (no enemy ants nearby)
		orders = {}
		potential_orders = {}
		def do_move_direction(loc, direction):
			new_loc = ants.destination(loc, direction)
			safe=1
			if len(ants.enemy_ants())>len(ants.my_ants())/10 and ants.turns_remaining()>75:
				if new_loc in danger_list:
					nearby_ants[danger_list[new_loc]].append(new_loc)
					#print 'ENEMY ANT',[danger_list[new_loc]]
					#print 'NANTS',nearby_ants
					#print len(nearby_ants[danger_list[new_loc]])
					if len(nearby_ants[danger_list[new_loc]])<2:
						safe=0
					else:
						#print 'KILL'
						for other_ant_new_loc in nearby_ants[danger_list[new_loc]]:
							if other_ant_new_loc not in orders and other_ant_new_loc in potential_orders:
								orders[other_ant_new_loc]=potential_orders[other_ant_new_loc]
							
			if ants.unoccupied(new_loc) and new_loc not in orders and new_loc not in potential_orders:
				if safe:
					orders[new_loc] = loc
					return True
				else:
					potential_orders[new_loc] = loc
					#print 'POT ORDERS',potential_orders
					
			else:
				return False
				orders[loc] = loc

		#try to move towards target, store final target so others won't aim for it
		targets = {}
		def do_move_location(loc, dest):
			if loc!=dest:
				direction = self.getdir(ants, loc, dest)
				if do_move_direction(loc, direction):
					targets[dest] = loc
					return True
				return False
				
		danger_list = {}
		#key=dangerous location
		#value=ant causing that
		nearby_ants = {}
		#key=enemy_ant
		#value=my ants near it
		#create danger list (all LAND/DEAD within sqrt(5) of enemy ant) 
		for ant_loc, owner in ants.enemy_ants():
			for a in range(-2,3):
				dest1=ants.destination(ant_loc, 'n', a)
				maxb=int((5-a**2)**.5)
				for b in range(-maxb,maxb+1):
					dest2=ants.destination(dest1, 'e', b)
					if ants.unoccupied(dest2) and dest2 not in danger_list:
						danger_list[dest2]=ant_loc
						nearby_ants[ant_loc]=[]
						
		#HILL SECTION: Priority over food if v close to hill, else food priority
		#prevent moving onto own hill
		for hill_loc in ants.my_hills():
			orders[hill_loc] = None
		#remember sighted hills
		for hill_loc, hill_owner in ants.enemy_hills():
			if hill_loc not in self.hills:
				self.hills.append(hill_loc)	
		#clear taken hills
		for hill_loc in self.hills:
			if hill_loc in ants.my_ants():
				self.hills.remove(hill_loc)
		#ATTACK ENEMY HILL	
		ant_hill_dist = []
		for hill_loc in self.hills:
			for ant_loc in ants.my_ants():
				if ant_loc not in orders.values():
					dist = ants.distance(ant_loc, hill_loc)
					ant_hill_dist.append((dist, ant_loc, hill_loc))
		ant_hill_dist.sort()
		for dist, ant_loc, hill_loc in ant_hill_dist:
			if dist<7 and ant_loc not in orders.values() and len(ants.my_ants())>len(ants.my_hills())*7:
				do_move_location(ant_loc, hill_loc)
			if ants.time_remaining()<200:
				break
		
		#GATHER FOOD
		ant_dist = []
		for food_loc in ants.food():
			for ant_loc in ants.my_ants():
				if ant_loc not in orders.values():
					dist = ants.distance(ant_loc, food_loc)
					#if dist<30:
					ant_dist.append((dist, ant_loc, food_loc))
				if ants.time_remaining()<400:
					break
			if ants.time_remaining()<400:
				break
		ant_dist.sort()
		if ant_dist:
			for dist, ant_loc, food_loc in ant_dist:
				if food_loc not in targets and ant_loc not in orders.values():
					do_move_location(ant_loc, food_loc)
				if ants.time_remaining()<200:
					break
				
		#HILL DEFEND
		#count enemy ants near my hills
		hill_nearby_ants={}
		for hill_loc in ants.my_hills():
			hill_nearby_ants[hill_loc]=0
			for enemy_loc, owner in ants.enemy_ants():
				dist=ants.distance(enemy_loc, hill_loc)
				if dist<20:
					hill_nearby_ants[hill_loc]+=1
		#form formation around hill
		if (len(ants.enemy_ants())>len(ants.my_ants())/20 and len(ants.my_ants())>len(ants.my_hills())*10) or len(ants.my_ants())>len(ants.my_hills())*20:
			for hill_loc in ants.my_hills():
				if hill_nearby_ants[hill_loc]>1:
					c1=ants.destination(hill_loc,'ne')
					c2=ants.destination(hill_loc,'nw')
					c3=ants.destination(hill_loc,'se')
					c4=ants.destination(hill_loc,'sw')
					corners=[c1,c2,c3,c4]
					for pos in corners:
						if ants.unoccupied(pos):
							ant_dist = []
							for ant_loc in ants.my_ants():
								if ant_loc not in orders.values():
									dist=ants.distance(ant_loc,pos)
									ant_dist.append([dist,ant_loc])
							ant_dist.sort()
							if ant_dist and (ant_dist[0][1] not in orders.values()):
								do_move_location(ant_dist[0][1], pos)
						elif ants.passable(pos):
							orders[pos]=pos
						if ants.time_remaining()<200:
							break
					if ants.time_remaining()<200:
						break
		if (len(ants.enemy_ants())>len(ants.my_ants())/10 and len(ants.my_ants())>len(ants.my_hills())*20) or len(ants.my_ants())>len(ants.my_hills())*30:
			for hill_loc in ants.my_hills():
				if hill_nearby_ants[hill_loc]>3:
					c1=ants.destination(ants.destination(hill_loc,'ne'),'ne')
					c2=ants.destination(ants.destination(hill_loc,'nw'),'nw')
					c3=ants.destination(ants.destination(hill_loc,'se'),'se')
					c4=ants.destination(ants.destination(hill_loc,'sw'),'sw')
					c5=ants.destination(ants.destination(hill_loc,'n'),'n')
					c6=ants.destination(ants.destination(hill_loc,'e'),'e')
					c7=ants.destination(ants.destination(hill_loc,'s'),'s')
					c8=ants.destination(ants.destination(hill_loc,'w'),'w')
					corners=[c1,c2,c3,c4]
					for pos in corners:
						if ants.unoccupied(pos):
							ant_dist = []
							for ant_loc in ants.my_ants():
								if ant_loc not in orders.values():
									dist=ants.distance(ant_loc,pos)
									ant_dist.append([dist,ant_loc])
							ant_dist.sort()
							if ant_dist and (ant_dist[0][1] not in orders.values()):
								do_move_location(ant_dist[0][1], pos)
						elif ants.passable(pos):
							orders[pos]=pos
						if ants.time_remaining()<200:
							break
					if ants.time_remaining()<200:
						break

		#HILL ATTACK
		if len(ants.my_ants())>len(ants.enemy_ants())*2 or len(ants.my_ants())>len(ants.my_hills())*40:
			for dist, ant_loc, hill_loc in ant_hill_dist:
				if ant_loc not in orders.values():
					do_move_location(ant_loc, hill_loc)
					
					
		#EXPLORATION
		#for each ant, move to closest non-visible flag
		ant_dist = []
		for flag_loc in self.flags:
			if not ants.visible(flag_loc):
				for ant_loc in ants.my_ants():
					if ant_loc not in orders.values():
						dist = ants.distance(ant_loc, flag_loc)
						#if dist<30:
						ant_dist.append((dist, ant_loc, flag_loc))
					if ants.time_remaining()<200:
						break
			if ants.time_remaining()<200:
				break
		ant_dist.sort()
		if ant_dist:
			for dist, ant_loc, flag_loc in ant_dist:
				if flag_loc not in targets and ant_loc not in orders.values():
					do_move_location(ant_loc, flag_loc)
				if ants.time_remaining()<100:
					break
				
		#WALK OFF HILL
		for hill_loc in ants.my_hills():
			if hill_loc in ants.my_ants() and hill_loc not in orders.values():
				for direction in ('s','e','w','n'):
				   if do_move_direction(hill_loc, direction):
						break
				
		#issue orders
		for new_loc in orders:
			ant_loc=orders[new_loc]
			if ant_loc and ant_loc!=new_loc:
				direction=ants.direction(ant_loc, new_loc)
				ants.issue_order((ant_loc, direction[0]))
			if ants.time_remaining()<50:
				break
				
		if ants.time_remaining()<200 or self.depth>2000/len(ants.my_ants()):
			self.depth=int(self.depth*.8)+1
		elif ants.time_remaining()>400 and self.depth<2000/len(ants.my_ants()):
			self.depth=int(self.depth*1.1)
			
if __name__ == '__main__':
	#psyco may speed python up
	try:
		import psyco
		psyco.full()
	except ImportError:
		pass
	
	try:
		#run bot
		Ants.run(MyBot())
	except KeyboardInterrupt:
		print('ctrl-c, leaving ...')
